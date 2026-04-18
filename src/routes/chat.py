"""
routes/chat.py — AI conversation endpoints.

All /api/chat, /api/conversation, /api/message, and /api/mood routes.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from core import (
    require_user,
    get_manager,
    limiter,
    _backend_conversation_to_frontend,
    _backend_message_to_frontend,
    _select_optional_table,
    _get_stats_persistent,
)

logger = logging.getLogger("3am-chat")
router = APIRouter()

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None


class CreateConversationRequest(BaseModel):
    title: Optional[str] = None


class UpdateConversationRequest(BaseModel):
    conversation_id: str
    title: Optional[str] = None
    summary: Optional[str] = None
    is_active: Optional[bool] = None


class DeleteConversationRequest(BaseModel):
    conversation_id: str


class MoodEntry(BaseModel):
    mood: str
    notes: Optional[str] = None
    rating: Optional[int] = None
    timestamp: Optional[str] = None


class QuestionnaireAnswerRequest(BaseModel):
    answers: List[dict]


# ---------------------------------------------------------------------------
# Chat / conversation
# ---------------------------------------------------------------------------


@router.post("/api/chat")
@limiter.limit("30/minute")
def chat(body: ChatRequest, request: Request):
    """Send a message to the AI therapy assistant."""
    user = require_user(request)
    user_id = str(user["id"])
    message = (body.message or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail={"message": "Message cannot be empty"})

    mgr = get_manager()
    conversation_id = body.conversation_id

    # Ensure an active conversation exists
    if not conversation_id:
        active = mgr.user_service.get_active_conversation(user_id)
        if active and active.get("conversation_id"):
            conversation_id = active["conversation_id"]
        else:
            conv = mgr.user_service.create_conversation(user_id)
            conversation_id = conv.get("conversation_id")

    try:
        response_text, extra = mgr.chat(
            user_id=user_id,
            conversation_id=conversation_id,
            message=message,
        )
        return {
            "response": response_text,
            "conversation_id": conversation_id,
            **(extra or {}),
        }
    except Exception as e:
        logger.error(f"Chat error for {user_id}: {e}")
        raise HTTPException(status_code=500, detail={"message": "AI service error"})


@router.post("/api/conversations")
def create_conversation(body: CreateConversationRequest, request: Request):
    user = require_user(request)
    user_id = str(user["id"])
    try:
        conv = get_manager().user_service.create_conversation(
            user_id, title=body.title or None
        )
        return _backend_conversation_to_frontend(conv)
    except Exception as e:
        logger.error(f"Create conversation error for {user_id}: {e}")
        raise HTTPException(status_code=500, detail={"message": str(e)})


@router.get("/api/conversations")
def get_conversations(request: Request):
    user = require_user(request)
    user_id = str(user["id"])
    try:
        mgr = get_manager()
        rows = mgr.db_client.select(
            "conversations",
            filters={"user_id": f"eq.{user_id}"},
        )
        rows = sorted(rows, key=lambda c: (c.get("updated_at") or c.get("created_at") or ""), reverse=True)
        return {"conversations": [_backend_conversation_to_frontend(c) for c in rows]}
    except Exception as e:
        logger.error(f"Get conversations error for {user_id}: {e}")
        return {"conversations": []}


@router.get("/api/conversations/active")
def get_active_conversation(request: Request):
    user = require_user(request)
    user_id = str(user["id"])
    try:
        conv = get_manager().user_service.get_active_conversation(user_id)
        if conv:
            return {"conversation": _backend_conversation_to_frontend(conv)}
        return {"conversation": None}
    except Exception:
        return {"conversation": None}


@router.put("/api/conversations")
def update_conversation(body: UpdateConversationRequest, request: Request):
    user = require_user(request)
    user_id = str(user["id"])
    updates: dict = {"updated_at": datetime.utcnow().isoformat()}
    if body.title is not None:
        updates["title"] = body.title
    if body.summary is not None:
        updates["summary"] = body.summary
    if body.is_active is not None:
        updates["is_active"] = body.is_active
    try:
        mgr = get_manager()
        mgr.db_client.update(
            "conversations",
            updates,
            {"conversation_id": f"eq.{body.conversation_id}", "user_id": f"eq.{user_id}"},
        )
        row = mgr.db_client.select(
            "conversations",
            filters={"conversation_id": f"eq.{body.conversation_id}"},
        )
        return {"conversation": _backend_conversation_to_frontend(row[0]) if row else updates}
    except Exception as e:
        logger.error(f"Update conversation error: {e}")
        raise HTTPException(status_code=500, detail={"message": str(e)})


@router.delete("/api/conversations")
def delete_conversation(body: DeleteConversationRequest, request: Request):
    user = require_user(request)
    user_id = str(user["id"])
    try:
        mgr = get_manager()
        mgr.db_client.delete(
            "messages",
            {"conversation_id": f"eq.{body.conversation_id}"},
        )
        mgr.db_client.delete(
            "conversations",
            {"conversation_id": f"eq.{body.conversation_id}", "user_id": f"eq.{user_id}"},
        )
        return {"deleted": True, "conversation_id": body.conversation_id}
    except Exception as e:
        logger.error(f"Delete conversation error: {e}")
        raise HTTPException(status_code=500, detail={"message": str(e)})


@router.get("/api/conversations/{conversation_id}/messages")
def get_messages(conversation_id: str, request: Request):
    user = require_user(request)
    user_id = str(user["id"])
    try:
        mgr = get_manager()
        # Assert ownership
        conv = mgr.db_client.select(
            "conversations",
            filters={"conversation_id": f"eq.{conversation_id}", "user_id": f"eq.{user_id}"},
        )
        if not conv:
            raise HTTPException(status_code=404, detail={"message": "Conversation not found"})
        msgs = mgr.db_client.select(
            "messages",
            filters={"conversation_id": f"eq.{conversation_id}"},
        )
        msgs = sorted(msgs, key=lambda m: (m.get("created_at") or ""))
        return {"messages": [_backend_message_to_frontend(m) for m in msgs]}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get messages error: {e}")
        return {"messages": []}


@router.post("/api/end-session")
def end_session(request: Request):
    """End the current conversation and (optionally) generate a SOAP summary."""
    user = require_user(request)
    user_id = str(user["id"])
    try:
        mgr = get_manager()
        active = mgr.user_service.get_active_conversation(user_id)
        if not active:
            return {"message": "No active session", "summary": None}

        conversation_id = active.get("conversation_id")
        mgr.db_client.update(
            "conversations",
            {"is_active": False, "updated_at": datetime.utcnow().isoformat()},
            {"conversation_id": f"eq.{conversation_id}"},
        )

        msgs = mgr.db_client.select(
            "messages",
            filters={"conversation_id": f"eq.{conversation_id}"},
        )
        msgs_sorted = sorted(msgs, key=lambda m: (m.get("created_at") or ""))

        # Fire SOAP summary if available
        summary = None
        try:
            from routes.therapist import _generate_and_store_summary
            generate_fn = _generate_and_store_summary
        except ImportError:
            generate_fn = None
            
        if generate_fn and msgs_sorted:
            try:
                summary = generate_fn(user_id, conversation_id, msgs_sorted)
            except Exception as se:
                logger.warning(f"SOAP summary failed: {se}")

        return {"message": "Session ended", "conversation_id": conversation_id, "summary": summary}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"End session error for {user_id}: {e}")
        raise HTTPException(status_code=500, detail={"message": str(e)})


# ---------------------------------------------------------------------------
# Mood
# ---------------------------------------------------------------------------


@router.post("/api/mood")
def log_mood(body: MoodEntry, request: Request):
    user = require_user(request)
    user_id = str(user["id"])
    now = body.timestamp or datetime.utcnow().isoformat()
    try:
        row = get_manager().db_client.insert(
            "mood_entries",
            {
                "user_id": user_id,
                "mood": body.mood,
                "notes": body.notes,
                "rating": body.rating,
                "timestamp": now,
                "created_at": now,
            },
        )
        return {"message": "Mood logged", "entry": row}
    except Exception as e:
        logger.error(f"Mood log error for {user_id}: {e}")
        raise HTTPException(status_code=500, detail={"message": str(e)})


@router.get("/api/mood")
def get_mood_entries(request: Request):
    user = require_user(request)
    user_id = str(user["id"])
    try:
        rows = get_manager().db_client.select("mood_entries", filters={"user_id": f"eq.{user_id}"})
        rows = sorted(rows, key=lambda r: (r.get("timestamp") or r.get("created_at") or ""), reverse=True)
        return {"entries": rows}
    except Exception:
        return {"entries": []}


# ---------------------------------------------------------------------------
# Questionnaire
# ---------------------------------------------------------------------------


@router.post("/api/questionnaire/submit")
def submit_questionnaire(body: QuestionnaireAnswerRequest, request: Request):
    """Save questionnaire answers and update personality traits."""
    user = require_user(request)
    user_id = str(user["id"])
    answers = body.answers or []
    if not answers:
        raise HTTPException(status_code=400, detail={"message": "No answers provided"})

    try:
        from conversation.questionnaire import PersonalityQuestionnaire  # type: ignore
        q = PersonalityQuestionnaire()
        traits = q.evaluate(answers)
    except Exception as e:
        logger.warning(f"Questionnaire evaluation error: {e}")
        traits = {}

    now = datetime.utcnow().isoformat()
    mgr = get_manager()

    # Persist each answer
    for ans in answers:
        try:
            mgr.db_client.insert(
                "questionnaire_responses",
                {
                    "user_id": user_id,
                    "question_id": ans.get("question_id") or ans.get("id"),
                    "answer": ans.get("answer"),
                    "created_at": now,
                },
            )
        except Exception:
            pass

    # Update personality traits
    if traits:
        try:
            mgr.db_client.update(
                "user_profiles",
                {"personality_traits": traits, "updated_at": now},
                {"user_id": f"eq.{user_id}"},
            )
        except Exception as e:
            logger.warning(f"Trait update error for {user_id}: {e}")

    return {"message": "Questionnaire submitted", "traits": traits}
