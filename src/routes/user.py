"""
routes/user.py — Basic user profile endpoints.
"""
from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from core import (
    require_user,
    get_manager,
    update_user_sessions,
    _get_profile_persistent,
    _get_stats_persistent,
)

logger = logging.getLogger("3am-user")
router = APIRouter()

class ProfileUpdateRequest(BaseModel):
    name: str
    mood_preference: str


@router.get("/api/profile")
def get_profile(request: Request):
    user = require_user(request)
    user_id = str(user["id"])
    return _get_profile_persistent(user_id)


@router.put("/api/profile")
def update_profile(body: ProfileUpdateRequest, request: Request):
    user = require_user(request)
    user_id = str(user["id"])

    # Keep session payload in sync
    user["username"] = body.name
    update_user_sessions(user_id, {"username": body.name})

    try:
        mgr = get_manager()
        mgr.db_client.update(
            "user_profiles",
            {
                "name": body.name,
                "preferences": {"mood_preference": body.mood_preference},
                "updated_at": datetime.utcnow().isoformat(),
            },
            {"user_id": f"eq.{user_id}"},
        )
        return _get_profile_persistent(user_id)
    except Exception as e:
        logger.error(f"Profile update error for {user_id}: {e}")
        raise HTTPException(status_code=500, detail={"message": str(e)})


@router.get("/api/stats")
def get_stats(request: Request):
    user = require_user(request)
    user_id = str(user["id"])
    stats = _get_stats_persistent(user_id)
    return {
        "current_streak": stats.get("current_streak", 0),
        "total_sessions": stats.get("total_sessions", 0),
        "total_minutes": stats.get("total_minutes", 0),
    }
