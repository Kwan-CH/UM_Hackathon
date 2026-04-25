from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.llm_tools.orchestrator import Orchestrator
from app.database.db_crud import db_get, db_update_accept, db_update_reject

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

orchestrator = Orchestrator()


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class NgoDecisionRequest(BaseModel):
    request_id: str
    ngo_id: str
    decision: str


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/api/chat")
@app.post("/api/chat/stream")
async def chat(payload: ChatRequest) -> Dict[str, Any]:
    user_input = (payload.message or "").strip()
    if not user_input:
        return {
            "status": "error",
            "session_id": payload.session_id,
            "message": "Empty message.",
        }

    try:
        result: Dict[str, Any] = await asyncio.to_thread(
            orchestrator.process,
            user_input,
            payload.session_id,
        )

        session_id = result.get("session_id") or payload.session_id

        if result.get("status") == "error":
            return {
                "status": "error",
                "session_id": session_id,
                "message": "Server is not responding. Please retry again in a few minutes.",
            }

        result["session_id"] = session_id
        return result

    except Exception:
        return {
            "status": "error",
            "session_id": payload.session_id,
            "message": "Server is not responding. Please retry again in a few minutes.",
        }


@app.get("/api/ngo/requests")
def ngo_requests(ngo_id: str) -> Dict[str, Any]:
    res = db_get("notifications", ngo_id=ngo_id, ngo_status="pending")
    if not res or not getattr(res, "ok", False):
        return {"requests": []}

    rows = res.json()
    if not isinstance(rows, list):
        rows = []

    requests_out = []
    for r in rows:
        requests_out.append({
            "id": r.get("request_id"),
            "request_id": r.get("request_id"),
            "session_id": r.get("session_id"),
            "created_at": r.get("created_at"),
            "restaurant_name": r.get("restaurant_name"),
            "contact_number": r.get("contact_number"),
            "food_items": r.get("food_items") if isinstance(r.get("food_items"), list) else [],
            "pickup_time": r.get("pickup_time"),
            "expiry_time": r.get("expiry_time"),
            "location": r.get("location"),
            "distance_km": r.get("distance_km"),
            "ngo_status": r.get("ngo_status") or "pending",
        })

    return {"requests": requests_out}


@app.post("/api/ngo/requests/decision")
def ngo_decision(payload: NgoDecisionRequest) -> Dict[str, Any]:
    decision = (payload.decision or "").strip().lower()
    if decision not in ("accept", "reject"):
        return {"status": "error", "message": "Invalid decision."}

    if decision == "accept":
        existing = db_get("notifications", request_id=payload.request_id, ngo_status="accept")
        if existing and getattr(existing, "ok", False):
            existing_rows = existing.json()
            if isinstance(existing_rows, list) and existing_rows:
                accepted_ngo_id = existing_rows[0].get("accepted_ngo_id") or existing_rows[0].get("ngo_id")
                if accepted_ngo_id and accepted_ngo_id != payload.ngo_id:
                    db_update_accept(
                        "notifications",
                        payload.ngo_id,
                        payload.request_id,
                        ngo_status="reject",
                        accepted_ngo_id=accepted_ngo_id,
                    )
                    return {"status": "conflict", "message": "Already accepted by another NGO."}

        db_update_accept(
            "notifications",
            payload.ngo_id,
            payload.request_id,
            ngo_status="accept",
            accepted_ngo_id=payload.ngo_id,
        )
        db_update_reject(
            "notifications",
            payload.ngo_id,
            payload.request_id,
            ngo_status="reject",
            accepted_ngo_id=payload.ngo_id,
        )
        return {"status": "ok"}

    db_update_accept(
        "notifications",
        payload.ngo_id,
        payload.request_id,
        ngo_status="reject",
    )
    return {"status": "ok"}