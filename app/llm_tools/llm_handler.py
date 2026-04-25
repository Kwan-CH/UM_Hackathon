import os
import re
import json
import requests
from typing import Dict, Any

from dotenv import load_dotenv
load_dotenv()
#Tools
from app.llm_tools.time_parser_tool import parse_time, infer_expiry, parse_time_with_inference
from app.llm_tools.quantity_extractor_tool import extract_quantity_items
from app.llm_tools.food_classifier_tool import classify_food_item

#API Details
API_KEY = os.getenv("AI_KEY")
API_URL = os.getenv("AI_URL")

#Initial System Prompt
SYSTEM_PROMPT = """
You are a food donation data extraction assistant.

Your job:
1. Extract structured JSON from restaurant messages.
2. Ensure all required fields are present.
3. If information is missing or unclear, ask follow-up questions.
4. Apply food safety reasoning.

Output rules:
- ALWAYS return valid JSON
- NEVER include explanations outside JSON
- If incomplete → return:
  {
    "status": "incomplete",
    "missing_fields": [...],
    "clarification_question": "..."
  }

- If complete → return:
  {
    "status": "complete",
    "data": { ... fully structured JSON ... }
  }

Required fields:
- restaurant_name
- contact_number
- food_items (list with name, quantity, type)
- pickup_time
- expiry_time
- location
- notes (optional)

Food safety rules:
- Reject expired food
- Flag unclear expiry times
"""

# Main LLM Handler
class LLMHandler:
    def __init__(self):
        self.headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        }

    def call_llm(self, messages: list) -> Dict:
        response = requests.post(
            API_URL,
            headers=self.headers,
            json={
                "model": "ilmu-glm-5.1",
                "messages": messages,
            },
            timeout=60
        )

        response.raise_for_status()
        return response.json()

    def extract_json(self, user_input: str) -> Dict[str, Any]:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_input}
        ]

        result = self.call_llm(messages)

        content = result["choices"][0]["message"]["content"]
        clean_json = re.sub(r"```json|```", "", content).strip()

        try:
            parsed_json = json.loads(clean_json)
        except json.JSONDecodeError:
            return {
                "status": "incomplete",
                "missing_fields": ["valid_json"],
                "clarification_question": "The response from the LLM was not valid JSON. Please ensure the output is strictly JSON formatted."
            }

        if parsed_json.get("status") == "complete":
            parsed_json["data"] = self.tools_post_process(parsed_json["data"])

        return parsed_json

    def tools_post_process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        #Normalize the time from JSON (TIME PARSER TOOL)
        pickup_time = parse_time(data.get("pickup_time"))
        expiry_time = parse_time_with_inference(data.get("expiry_time"), reference=pickup_time)

        expiry_time = infer_expiry(pickup_time, expiry_time)

        data["pickup_time"] = pickup_time.isoformat() if pickup_time else None
        data["expiry_time"] = expiry_time.isoformat() if expiry_time else None

        #Fix food items [FOOD CLASSIFY TOOL]
        cleaned_items = []

        for item in data.get("food_items", []):
            name = item.get("name", "")

            raw_text = f"{item.get('quantity', '')} {name}"
            extracted = extract_quantity_items(raw_text)

            if extracted:
                for e in extracted:
                    classified = classify_food_item(e["name"])
                    cleaned_items.append({
                        "name": e["name"],
                        "quantity": e["quantity"],
                        "unit": e["unit"],
                        "type": classified["type"],
                        "category": classified["category"]
                    })

            else:
                classified = classify_food_item(name)
                cleaned_items.append({
                    "name": name,
                    "quantity": item.get("quantity", 1),
                    "unit": item.get("unit", "pieces"),
                    "type": classified["type"],
                    "category": classified["category"]
                })

        data["food_items"] = cleaned_items
        return data
        
