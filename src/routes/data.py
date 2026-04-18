"""
routes/data.py — Generic CRUD endpoints for persistent data
"""
from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request

from core.helpers import (
    require_user,
    get_manager,
    _get_profile_persistent,
    _get_stats_persistent,
    _get_mood_entries_persistent,
    _backend_conversation_to_frontend,
    _backend_message_to_frontend,
    _is_conflict_error,
)
from database import normalize_postgrest_value

logger = logging.getLogger("3am-data")
router = APIRouter()


@router.get("/api/data/{table}")
def get_table_data(table: str, request: Request):
    """List all records for a table, scoped to the current user."""
    user = require_user(request)
    user_id = str(user["id"])

    try:
        if table == "conversations":
            mgr = get_manager()
            convs = mgr.user_service.db.select(
                "conversations",
                filters={"user_id": f"eq.{user_id}"},
            )
            return [_backend_conversation_to_frontend(c) for c in convs]

        elif table == "messages":
            conv_id = request.query_params.get("conversation_id")
            if not conv_id:
                return []
            conv_id = normalize_postgrest_value(conv_id)
            mgr = get_manager()
            msgs = mgr.user_service.get_conversation_history(conv_id)
            return [_backend_message_to_frontend(m) for m in msgs]

        elif table == "profiles":
            profile = _get_profile_persistent(user_id)
            return profile

        elif table == "user_stats":
            stats = _get_stats_persistent(user_id)
            return stats

        elif table == "mood_entries":
            entries = _get_mood_entries_persistent(user_id)
            return entries

        else:
            raise HTTPException(status_code=404, detail=f"Unknown table: {table}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"GET /api/data/{table} failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/data/{table}/{record_id}")
def get_table_record(table: str, record_id: str, request: Request):
    """Get a single record by ID."""
    user = require_user(request)
    user_id = str(user["id"])

    try:
        mgr = get_manager()
        
        if table == "conversations":
            rid = normalize_postgrest_value(record_id)
            conv = mgr.user_service.get_conversation(rid)
            if not conv:
                raise HTTPException(status_code=404, detail="Conversation not found")
            return _backend_conversation_to_frontend(conv)

        elif table == "messages":
            rid = normalize_postgrest_value(record_id)
            msgs = mgr.user_service.get_conversation_history(rid)
            return [_backend_message_to_frontend(m) for m in msgs]

        elif table == "profiles":
            profile = _get_profile_persistent(user_id)
            return profile

        elif table == "user_stats":
            stats = _get_stats_persistent(user_id)
            return stats

        elif table == "mood_entries":
            rid = normalize_postgrest_value(record_id)
            entries = mgr.db_client.select("mood_entries", filters={"id": f"eq.{rid}", "user_id": f"eq.{user_id}"})
            if not entries:
                raise HTTPException(status_code=404, detail="Mood entry not found")
            return entries[0]

        else:
            raise HTTPException(status_code=404, detail=f"Unknown table: {table}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"GET /api/data/{table}/{record_id} failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/data/{table}")
def create_table_record(table: str, request: Request, body: dict = {}):
    """Create a new record in a table."""
    user = require_user(request)
    user_id = str(user["id"])
    now = datetime.utcnow().isoformat()
    mgr = get_manager()

    try:
        if table == "conversations":
            session_result = mgr.start_session(user_id)
            conv_id = session_result["conversation_id"]
            conv = mgr.user_service.get_conversation(conv_id) or {}
            frontend_conv = _backend_conversation_to_frontend(conv)
            
            # Apply frontend fields
            frontend_conv.update({k: v for k, v in body.items() if k in ["title", "mood", "tags", "duration_minutes"]})
            return frontend_conv

        elif table == "messages":
            conv_id = body.get("conversation_id")
            if conv_id is not None:
                conv_id = normalize_postgrest_value(str(conv_id))
            content = body.get("content", "")
            is_user = body.get("is_user", True)

            if not conv_id:
                raise HTTPException(status_code=400, detail="conversation_id required")

            conv = mgr.user_service.get_conversation(conv_id)
            turn = (conv.get("total_turns", 0) + 1) if conv else 1
            role = "user" if is_user else "assistant"
            
            msg = mgr.user_service.add_message(
                conversation_id=conv_id,
                user_id=user_id,
                role=role,
                content=content,
                turn_index=turn,
            )
            mgr.user_service.update_conversation_turns(conv_id, increment=1)
            return _backend_message_to_frontend(msg)

        elif table == "profiles":
            allowed = {"name", "emergency_contact", "phone"}
            updates = {k: v for k, v in body.items() if k in allowed}
            if "mood_preference" in body:
                profile = mgr.user_service.get_user_profile(user_id)
                prefs = profile.get("preferences", {})
                prefs["mood_preference"] = body["mood_preference"]
                updates["preferences"] = prefs

            if updates:
                updates["updated_at"] = now
                mgr.db_client.update("user_profiles", updates, {"user_id": f"eq.{user_id}"})
            return _get_profile_persistent(user_id)

        elif table == "user_stats":
            data = {k:v for k,v in body.items() if k in ["current_streak", "total_sessions", "total_minutes"]}
            data["user_id"] = user_id
            try:
                return mgr.db_client.insert("user_stats", data)
            except Exception as e:
                if _is_conflict_error(e):
                    return _get_stats_persistent(user_id)
                raise

        elif table == "mood_entries":
            entry = {
                "user_id": user_id,
                "date": body.get("date", now[:10]),
                "mood": body.get("mood", "neutral"),
                "note": body.get("note"),
                "prompt": body.get("prompt"),
                "prompt_answer": body.get("prompt_answer"),
                "created_at": now,
                "updated_at": now,
            }
            return mgr.db_client.insert("mood_entries", entry)

        else:
            raise HTTPException(status_code=404, detail=f"Unknown table: {table}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"POST /api/data/{table} failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/api/data/{table}/{record_id}")
def update_table_record(table: str, record_id: str, request: Request, body: dict = {}):
    """Update a record by ID."""
    user = require_user(request)
    user_id = str(user["id"])
    now = datetime.utcnow().isoformat()
    mgr = get_manager()

    try:
        if table == "conversations":
            rid = normalize_postgrest_value(record_id)
            updates = {k: v for k, v in body.items() if k in ["is_active", "duration_minutes", "title", "mood", "summary", "tags"]}
            if updates:
                mgr.db_client.update("conversations", updates, {"conversation_id": f"eq.{rid}"})
            
            conv = mgr.user_service.get_conversation(rid)
            return _backend_conversation_to_frontend(conv)

        elif table == "profiles":
            updates = {k: v for k, v in body.items() if k in ("name", "deleted")}
            updates["updated_at"] = now
            if "mood_preference" in body:
                profile = mgr.user_service.get_user_profile(user_id)
                prefs = profile.get("preferences", {})
                prefs["mood_preference"] = body["mood_preference"]
                updates["preferences"] = prefs
            
            mgr.db_client.update("user_profiles", updates, {"user_id": f"eq.{user_id}"})
            return _get_profile_persistent(user_id)

        elif table == "user_stats":
            updates = {k: v for k, v in body.items() if k in ["current_streak", "total_sessions", "total_minutes", "mood_improvement_percentage", "last_session_date"]}
            if updates:
                updates["updated_at"] = now
                mgr.db_client.update("user_stats", updates, {"user_id": f"eq.{user_id}"})
            return _get_stats_persistent(user_id)

        elif table == "mood_entries":
            rid = normalize_postgrest_value(record_id)
            updates = {k: v for k, v in body.items() if k in ["mood", "note", "prompt", "prompt_answer"]}
            if updates:
                updates["updated_at"] = now
                mgr.db_client.update("mood_entries", updates, {"id": f"eq.{rid}", "user_id": f"eq.{user_id}"})
            
            entries = mgr.db_client.select("mood_entries", filters={"id": f"eq.{rid}"})
            return entries[0] if entries else {}

        else:
            raise HTTPException(status_code=404, detail=f"Unknown table: {table}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PATCH /api/data/{table}/{record_id} failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/data/{table}/{record_id}")
def delete_table_record(table: str, record_id: str, request: Request):
    """Delete a record by ID."""
    user = require_user(request)
    user_id = str(user["id"])
    mgr = get_manager()

    try:
        if table == "conversations":
            conv_id = normalize_postgrest_value(record_id)
            try:
                mgr.db_client.delete("messages", {"conversation_id": f"eq.{conv_id}"})
            except Exception as msg_exc:
                logger.warning(f"Could not delete messages for {conv_id}: {msg_exc}")
            try:
                mgr.end_session(conv_id)
            except Exception:
                pass
            mgr.db_client.delete("conversations", {"conversation_id": f"eq.{conv_id}", "user_id": f"eq.{user_id}"})
            return {"message": "Conversation deleted"}

        elif table == "profiles":
            mgr.db_client.update("user_profiles", {"deleted": True}, {"user_id": f"eq.{user_id}"})
            return {"message": "Profile deleted"}

        elif table == "user_stats":
            mgr.db_client.delete("user_stats", {"user_id": f"eq.{user_id}"})
            return {"message": "Stats deleted"}

        elif table == "mood_entries":
            rid = normalize_postgrest_value(record_id)
            mgr.db_client.delete("mood_entries", {"id": f"eq.{rid}", "user_id": f"eq.{user_id}"})
            return {"message": "Mood entry deleted"}

        else:
            raise HTTPException(status_code=404, detail=f"Unknown table: {table}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"DELETE /api/data/{table}/{record_id} failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
