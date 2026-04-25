import uuid
import json
from typing import Dict, Any, Optional, List
from enum import Enum
from datetime import datetime
from app.llm_tools.llm_handler import LLMHandler
from app.llm_tools.knowledge_base import (
    get_all_ngos,
    get_ngo_by_id,
    get_available_ngos,
    update_ngo_capacity,
)
from app.database.db_crud import db_create

class WorkflowState(Enum):
    START = "start"
    WAITING_FOR_INFO = "waiting_for_info"
    COMPLETE = "complete"
    ERROR = "error"


class Session:
    """Manages conversation state for a single user session"""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.accumulated_info = {}  # Store extracted fields
        self.full_history = []  # Store all user inputs
        self.conversation_history = []
        self.state = WorkflowState.START
        self.created_at = datetime.now().isoformat()
        self.matched_ngos = []  # Store matched NGOs
    
    def add_message(self, role: str, content: str):
        """Add message to conversation history"""
        self.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
    
    def add_user_input(self, user_input: str):
        """Store user input in full history"""
        self.full_history.append(user_input)
    
    def update_accumulated_info(self, data: Dict[str, Any]):
        """Merge new data with existing accumulated info"""
        if data:
            for key, value in data.items():
                if value and value not in [None, "", []]:
                    self.accumulated_info[key] = value
    
    def build_complete_context_prompt(self, current_input: str) -> str:
        """
        Build a complete prompt with all previous context
        This ensures llm knows everything that was already provided
        """
        context_parts = []
        
        # Add all previous user inputs
        if self.full_history:
            context_parts.append("Previous user messages: ")
            for i, msg in enumerate(self.full_history[:-1], 1):
                context_parts.append(f"Message {i}: {msg}")
            context_parts.append("")
        
        # Add currently extracted information
        if self.accumulated_info:
            context_parts.append("Currently extracted information: ")
            for key, value in self.accumulated_info.items():
                if key == "food_items" and isinstance(value, list):
                    items_str = ", ".join([f"{item.get('quantity', '')} {item.get('name', '')} ({item.get('type', 'unknown')})" for item in value])
                    context_parts.append(f"- {key}: {items_str}")
                else:
                    context_parts.append(f"- {key}: {value}")
            context_parts.append("")
        
        # Add current message
        context_parts.append(f"Current user message: \n{current_input}")
        context_parts.append("\nPlease combine the previously extracted information with this new message to create a complete donation record. If the current message provides missing fields, update them.")
        
        return "\n".join(context_parts)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "state": self.state.value,
            "accumulated_info": self.accumulated_info,
            "full_history": self.full_history,
            "conversation_history": self.conversation_history[-5:],
            "created_at": self.created_at,
            "matched_ngos": self.matched_ngos
        }


class Orchestrator:
    def __init__(self):
        self.llm = LLMHandler()
        self.sessions: Dict[str, Session] = {}
        self.session_timeout_minutes = 30

    def _looks_like_thanks(self, text: str) -> bool:
        t = (text or "").strip().lower()
        if not t:
            return False

        keywords = [
            "thank",
            "thanks",
            "thank you",
            "thx",
            "tq",
            "appreciate",
            "terima kasih",
        ]

        return any(k in t for k in keywords)
    
    def _get_or_create_session(self, session_id: Optional[str]) -> Session:
        if session_id and session_id in self.sessions:
            return self.sessions[session_id]

        new_session_id = session_id or str(uuid.uuid4())
        session = Session(new_session_id)
        self.sessions[new_session_id] = session
        return session
    
    def _cleanup_old_sessions(self):
        now = datetime.now()
        expired = []
        for sid, session in self.sessions.items():
            created = datetime.fromisoformat(session.created_at)
            if (now - created).total_seconds() > self.session_timeout_minutes * 60:
                expired.append(sid)
        for sid in expired:
            del self.sessions[sid]
    
    # ================================================================
    # NGO FUNCTIONS
    # ================================================================
    
    def get_all_ngo_list(self) -> List[Dict[str, Any]]:
        """Return list of all NGOs"""
        return get_all_ngos()
    
    def get_ngo_info(self, ngo_id: str) -> Optional[Dict[str, Any]]:
        """Get specific NGO by ID"""
        return get_ngo_by_id(ngo_id)
    
    def get_available_ngos_list(self, food_category: str = None) -> List[Dict[str, Any]]:
        """Get NGOs that have available capacity"""
        return get_available_ngos(food_category)
    
    def _parse_food_preferences(self, food_prefs) -> List[str]:
        """
        Parse food preferences from string to list
        Handles both string (semicolon-separated) and list formats
        """
        if isinstance(food_prefs, list):
            return food_prefs
        elif isinstance(food_prefs, str):
            return [p.strip() for p in food_prefs.split(';')]
        return []
    
    def _get_food_type_from_items(self, food_items: List[Dict]) -> str:
        """
        Extract food type from already-classified food items.
        The food_classifier_tool already adds 'type' to each food item.
        
        Returns:
            str: food type (cooked_meal, raw_food, beverage, baked_food, or unknown)
        """
        if not food_items:
            return "unknown"
        
        # Get the type from the first food item
        food_type = food_items[0].get("type", "unknown")
        
        # Map food_classifier types to NGO preference types
        # The food_classifier uses: cooked_meal, raw_food, beverage, baked_food
        # NGO preferences use: cooked_meal, raw, beverage, bakery
        
        type_mapping = {
            "cooked_meal": "cooked_meal",
            "raw_food": "raw",
            "beverage": "beverage",
            "baked_food": "bakery",
            "unknown": "cooked_meal"  # default
        }
        
        # If food type is not in mapping, use default
        mapped_type = type_mapping.get(food_type, "cooked_meal")
        
        return mapped_type
    
    def _match_ngos_by_food_and_distance(self, food_items: List[Dict]) -> List[Dict[str, Any]]:
        """
        Match NGOs based on:
        1. First: Food type from already-classified food items
        2. Second: Distance (nearest first)
        
        Returns top 3 matching NGOs sorted by distance
        """
        if not food_items:
            return []
        
        # Get food type from already-classified items
        food_type = self._get_food_type_from_items(food_items)
        
        # Get all NGOs
        all_ngos = get_all_ngos()
        matched = []
        
        for ngo in all_ngos:
            # Check if NGO has capacity
            if ngo.get("capacity_current", 0) >= ngo.get("capacity_daily", 0):
                continue
            
            # Parse food preferences
            food_prefs = self._parse_food_preferences(ngo.get("food_preferences", []))
            
            # Check if NGO accepts this food type
            if food_type in food_prefs:
                # Get distance (default to large number if not available)
                distance = ngo.get("distance_km", 999)
                matched.append({
                    "ngo": ngo,
                    "distance": distance
                })
        
        # Sort by distance (nearest first)
        matched.sort(key=lambda x: x["distance"])
        
        # Extract just the NGO dicts, return top 3
        result = [item["ngo"] for item in matched[:3]]
        
        return result
    
    def _contact_ngo(self, ngo: Dict[str, Any], donation_details: Dict[str, Any]) -> Dict[str, Any]:
        """
        Simulate contacting NGO with donation details
        Returns notification result
        """
        food_items_str = ", ".join([
            f"{item.get('quantity', '')} {item.get('name', '')}" 
            for item in donation_details.get("food_items", [])
        ])
        
        # Calculate total quantity for capacity update
        total_quantity = sum([
            int(item.get('quantity', 0)) if str(item.get('quantity', '0')).isdigit() else 0
            for item in donation_details.get("food_items", [])
        ])
        
        # Update NGO capacity in knowledge base
        update_ngo_capacity(ngo["id"], total_quantity)
        
        # Create notification message (Simulation purposes only)
        notification = {
            "ngo_name": ngo["name"],
            "contact_person": ngo["contact_person"],
            "phone": ngo["phone"],
            "email": ngo["email"],
            "distance_km": ngo.get("distance_km", "N/A"),
            "donation_details": {
                "restaurant": donation_details.get("restaurant_name"),
                "food": food_items_str,
                "quantity": total_quantity,
                "pickup_time": donation_details.get("pickup_time"),
                "expiry_time": donation_details.get("expiry_time"),
                "location": donation_details.get("location"),
                "donor_contact": donation_details.get("contact_number")
            },
            "message_sent": f"Notification sent to {ngo['name']} ({ngo['contact_person']}) at {ngo['phone']} (Distance: {ngo.get('distance_km', 'N/A')}km)"
        }
        
        return notification
    
    def _notify_matched_ngos(self, ngos: List[Dict[str, Any]], donation_details: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Notify all matched NGOs about the donation
        """
        results = []
        for ngo in ngos:
            result = self._contact_ngo(ngo, donation_details)
            results.append(result)
        return results
    
    # ================================================================
    # MAIN PROCESS FUNCTION
    # ================================================================
    
    def process(self, user_input: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        try:
            session = self._get_or_create_session(session_id)

            if session.state == WorkflowState.COMPLETE:
                if self._looks_like_thanks(user_input):
                    old_session_id = session.session_id
                    new_session_id = str(uuid.uuid4())
                    self.sessions[new_session_id] = Session(new_session_id)
                    if old_session_id in self.sessions:
                        del self.sessions[old_session_id]

                    return {
                        "status": "success",
                        "session_id": new_session_id,
                        "message": "You're welcome. If you have another donation, tell me the food type, quantity, pickup time, and location.",
                        "state": WorkflowState.START.value,
                    }

                new_session_id = str(uuid.uuid4())
                session = Session(new_session_id)
                self.sessions[new_session_id] = session

            # Store user input in full history
            session.add_user_input(user_input)
            session.add_message("user", user_input)
            
            # Build complete context prompt with ALL previous info
            prompt = session.build_complete_context_prompt(user_input)
            
            # Call LLM Handler
            llm_response = self.llm.extract_json(prompt)
            
            if llm_response.get("status") == "error":
                session.state = WorkflowState.ERROR
                return {
                    "status": "error",
                    "session_id": session.session_id,
                    "message": llm_response.get("message", "LLM processing failed"),
                    "state": session.state.value
                }
            
            # Handle incomplete response
            if llm_response.get("status") == "incomplete":
                session.state = WorkflowState.WAITING_FOR_INFO
                
                # Store any partial data that was extracted
                if "data" in llm_response:
                    session.update_accumulated_info(llm_response["data"])
                
                missing_fields = llm_response.get("missing_fields", [])
                question = llm_response.get("clarification_question", 
                    f"Please provide the following missing information: {', '.join(missing_fields)}")
                
                session.add_message("assistant", question)
                
                return {
                    "status": "need_info",
                    "session_id": session.session_id,
                    "message": question,
                    "missing_fields": missing_fields,
                    "partial_data": session.accumulated_info,
                    "state": session.state.value
                }
            
            # Handle complete response
            if llm_response.get("status") == "complete":
                data = llm_response.get("data", {})
                
                # NGO MATCHING & NOTIFICATION LOGIC
                # The food_items already have 'type' from food_classifier_tool
                matched_ngos = self._match_ngos_by_food_and_distance(data.get("food_items", []))
                session.matched_ngos = matched_ngos

                created_at = datetime.now().isoformat()
                for ngo in matched_ngos:
                    db_create(
                        "notifications",
                        request_id=session.session_id,
                        session_id=session.session_id,
                        created_at=created_at,
                        restaurant_name=data.get("restaurant_name"),
                        contact_number=data.get("contact_number"),
                        food_items=data.get("food_items", []),
                        pickup_time=data.get("pickup_time"),
                        expiry_time=data.get("expiry_time"),
                        location=data.get("location"),
                        ngo_id=ngo.get("id"),
                        ngo_name=ngo.get("name"),
                        distance_km=ngo.get("distance_km"),
                        ngo_status="pending",
                        accepted_ngo_id=None,
                    )
                
                # Send notifications to matched NGOs (this also updates capacity)
                notifications = self._notify_matched_ngos(matched_ngos, data)
                
                session.state = WorkflowState.COMPLETE
                session.add_message("assistant", "Food donation recorded successfully! Thank you for your contribution.")
                self._cleanup_old_sessions()

                # Build NGO list text
                ngo_names = [ngo['name'] for ngo in matched_ngos[:3]]
                ngo_text = ", ".join(ngo_names)

                message = f"Your donation listing has been sent to {len(matched_ngos)} NGOs: {ngo_text}. Please wait patiently for their response. The donation will be assigned to the NGO that accepts it first."

                return {
                    "status": "success",
                    "session_id": session.session_id,
                    "message": message,
                    "data": {
                        "restaurant_name": data.get("restaurant_name"),
                        "contact_number": data.get("contact_number"),
                        "food_items": data.get("food_items", []),
                        "pickup_time": data.get("pickup_time"),
                        "expiry_time": data.get("expiry_time"),
                        "location": data.get("location"),
                        "notes": data.get("notes", "")
                    },
                    "matched_ngos": [
                        {
                            "id": ngo.get("id"),
                            "name": ngo.get("name"),
                            "type": ngo.get("type"),
                            "contact_person": ngo.get("contact_person"),
                            "phone": ngo.get("phone"),
                            "email": ngo.get("email"),
                            "address": ngo.get("address"),
                            "distance_km": ngo.get("distance_km", "N/A")
                        }
                        for ngo in matched_ngos
                    ],
                    "notifications": notifications,
                    "state": session.state.value,
                    "timestamp": datetime.now().isoformat()
                }
            
            session.state = WorkflowState.ERROR
            return {
                "status": "error",
                "session_id": session.session_id,
                "message": f"Unknown status: {llm_response.get('status')}",
                "state": session.state.value
            }
            
        except Exception as e:
            session = self._get_or_create_session(session_id)
            session.state = WorkflowState.ERROR
            return {
                "status": "error",
                "session_id": session.session_id,
                "message": f"System error: {str(e)}",
                "state": session.state.value,
                "requires_retry": True
            }
    
    # ================================================================
    # SESSION MANAGEMENT FUNCTIONS
    # ================================================================
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        if session_id in self.sessions:
            return self.sessions[session_id].to_dict()
        return None
    
    def clear_session(self, session_id: str) -> Dict[str, Any]:
        if session_id in self.sessions:
            del self.sessions[session_id]
            return {"status": "cleared", "session_id": session_id}
        return {"status": "not_found", "session_id": session_id}
    
    def clear_all_sessions(self):
        count = len(self.sessions)
        self.sessions.clear()
        return {"status": "cleared", "count": count}
