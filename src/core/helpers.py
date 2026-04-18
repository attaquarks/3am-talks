"""
core/helpers.py — auth guards, DB helpers, and schema translation utilities.

All helpers that were previously defined inline in the monolithic api.py now
live here so every route module can import them cleanly from `core`.
"""
from __future__ import annotations

import datetime as dt
import logging
import os
import secrets
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from fastapi import HTTPException, Request

from .sessions import (
    VOICE_AGENT_SECRET,
    clear_user_sessions,
    get_current_user,
    sessions,
    update_user_sessions,
)

logger = logging.getLogger("3am-core")

ROOT_DIR = Path(__file__).parent.parent.parent  # project root

# ---------------------------------------------------------------------------
# Role / status constants
# ---------------------------------------------------------------------------

ALLOWED_ROLES = {"patient", "therapist", "admin"}
ALLOWED_ACCOUNT_STATUSES = {"active", "suspended", "banned"}

# ---------------------------------------------------------------------------
# ConversationManager — lazy singleton
# ---------------------------------------------------------------------------

_conversation_manager = None


def get_manager():
    """Lazily initialize the ConversationManager so startup doesn't block."""
    global _conversation_manager
    if _conversation_manager is None:
        try:
            from conversation.manager import ConversationManager  # type: ignore

            _conversation_manager = ConversationManager(
                model_name="psychocounsel",
                personality_model_path=str(ROOT_DIR / "Models" / "bert-base-personality"),
                enable_rag=True,
                enable_personality=True,
            )
            logger.info("ConversationManager initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize ConversationManager: {e}")
            raise HTTPException(
                status_code=503,
                detail=f"Backend AI services unavailable: {e}",
            )
    return _conversation_manager


# ---------------------------------------------------------------------------
# Datetime helpers
# ---------------------------------------------------------------------------


def _parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Account-status helpers
# ---------------------------------------------------------------------------


def _get_account_status(profile: Optional[dict]) -> str:
    if not profile:
        return "active"
    status = str(profile.get("account_status") or "active").lower()
    if status == "suspended":
        suspended_until = _parse_iso_datetime(profile.get("suspended_until"))
        if suspended_until:
            if suspended_until.tzinfo is None:
                suspended_until = suspended_until.replace(tzinfo=dt.timezone.utc)
            if suspended_until <= datetime.now(dt.timezone.utc):
                return "active"
    return status if status in ALLOWED_ACCOUNT_STATUSES else "active"


def _status_block_message(profile: Optional[dict]) -> Optional[str]:
    status = _get_account_status(profile)
    if status == "banned":
        return "Your account has been banned. Contact support for assistance."
    if status == "suspended":
        suspended_until = _parse_iso_datetime(
            profile.get("suspended_until") if profile else None
        )
        if suspended_until:
            return f"Your account is suspended until {suspended_until.isoformat()}."
        return "Your account is suspended. Contact support for assistance."
    return None


# ---------------------------------------------------------------------------
# Auth guards
# ---------------------------------------------------------------------------


def require_user(request: Request) -> dict:
    """Return the session user payload or raise HTTP 401/403."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user_id = str(user.get("id") or "")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    profile = _get_profile_persistent(user_id)
    block_message = _status_block_message(profile)
    if block_message:
        raise HTTPException(
            status_code=403,
            detail={"message": block_message, "account_status": _get_account_status(profile)},
        )

    # Keep session payload in sync with DB role/status.
    role = str(profile.get("role") or "patient").lower()
    if role in ALLOWED_ROLES:
        user["role"] = role
    user["account_status"] = _get_account_status(profile)
    user["suspended_until"] = profile.get("suspended_until")

    return user


def require_admin(request: Request) -> dict:
    user = require_user(request)
    role = str(user.get("role") or "patient").lower()
    if role != "admin":
        raise HTTPException(status_code=403, detail={"message": "Admin access required."})

    user_id = str(user.get("id") or "")
    profile = _get_profile_persistent(user_id)
    admin_id = profile.get("admin_id") or _ensure_admin_id(user_id, profile)
    if admin_id:
        user["admin_id"] = admin_id
    return user


def require_voice_agent(request: Request) -> None:
    import hmac as _hmac
    auth = request.headers.get("authorization") or ""
    if not auth.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing voice agent authorization")
    token = auth.split(" ", 1)[1].strip()
    if not _hmac.compare_digest(token, VOICE_AGENT_SECRET):
        raise HTTPException(status_code=403, detail="Invalid voice agent authorization")


# ---------------------------------------------------------------------------
# Error helpers
# ---------------------------------------------------------------------------


def _is_conflict_error(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 409:
        return True
    msg = str(exc).lower()
    return "409" in msg or "conflict" in msg


def _is_missing_table_error(exc: BaseException) -> bool:
    if not isinstance(exc, httpx.HTTPStatusError):
        return False
    text = (exc.response.text or "").lower()
    return "does not exist" in text or "relation" in text


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------


def _get_profile_persistent(user_id: str) -> dict:
    """Fetch user profile from Supabase, creating one if missing."""
    mgr = get_manager()
    profile = mgr.user_service.get_user_profile(user_id)
    if not profile:
        profile = mgr.user_service.create_user_profile(user_id)

    if "name" not in profile:
        profile["name"] = "User"
    if "mood_preference" not in profile:
        profile["mood_preference"] = profile.get("preferences", {}).get("mood_preference", "neutral")
    role = str(profile.get("role") or "patient").lower()
    profile["role"] = role if role in ALLOWED_ROLES else "patient"
    profile["account_status"] = _get_account_status(profile)
    return profile


def _get_stats_persistent(user_id: str) -> dict:
    """Fetch (or initialise) the user_stats row in Supabase."""
    mgr = get_manager()
    try:
        stats = mgr.db_client.select("user_stats", filters={"user_id": f"eq.{user_id}"})
        if stats:
            return stats[0]

        now = datetime.utcnow().isoformat()
        new_stats = {
            "user_id": user_id,
            "current_streak": 0,
            "total_sessions": 0,
            "total_minutes": 0,
            "mood_improvement_percentage": 0,
            "created_at": now,
            "updated_at": now,
        }
        try:
            return mgr.db_client.insert("user_stats", new_stats)
        except Exception as insert_err:
            if _is_conflict_error(insert_err):
                existing = mgr.db_client.select("user_stats", filters={"user_id": f"eq.{user_id}"})
                if existing:
                    return existing[0]
            raise
    except Exception as e:
        logger.error(f"Error fetching stats for {user_id}: {e}")
        return {"user_id": user_id, "current_streak": 0, "total_sessions": 0, "total_minutes": 0}


def _get_mood_entries_persistent(user_id: str) -> List[dict]:
    """Fetch mood entries from Supabase."""
    mgr = get_manager()
    try:
        return mgr.db_client.select("mood_entries", filters={"user_id": f"eq.{user_id}"})
    except Exception as e:
        logger.error(f"Error fetching mood entries for {user_id}: {e}")
        return []


def _select_optional_table(table: str, filters: Optional[dict] = None) -> List[dict]:
    """SELECT from an optional (possibly missing) Supabase table — never raises on 404."""
    mgr = get_manager()
    try:
        rows = mgr.db_client.select(table, filters=filters)
        return rows if isinstance(rows, list) else []
    except Exception as exc:
        if _is_missing_table_error(exc):
            logger.warning("Optional table '%s' is missing. Run Supabase admin migration.", table)
            return []
        raise


# ---------------------------------------------------------------------------
# Admin helpers
# ---------------------------------------------------------------------------


def _generate_admin_id() -> str:
    return f"ADM-{secrets.token_hex(3).upper()}"


def _ensure_admin_id(user_id: str, profile: Optional[dict] = None) -> Optional[str]:
    mgr = get_manager()
    if profile is None:
        rows = mgr.db_client.select("user_profiles", filters={"user_id": f"eq.{user_id}"})
        profile = rows[0] if rows else {}

    existing = profile.get("admin_id")
    if existing:
        return existing

    for _ in range(6):
        candidate = _generate_admin_id()
        try:
            clashes = mgr.db_client.select("user_profiles", filters={"admin_id": f"eq.{candidate}"})
        except Exception:
            clashes = []
        if clashes:
            continue
        try:
            mgr.db_client.update(
                "user_profiles",
                {"admin_id": candidate, "updated_at": datetime.utcnow().isoformat()},
                {"user_id": f"eq.{user_id}"},
            )
            profile["admin_id"] = candidate
            return candidate
        except Exception as exc:
            if _is_missing_table_error(exc):
                logger.warning("admin_id column missing. Run admin extensions migration.")
                return None
            logger.warning(f"Failed to persist admin_id for {user_id}: {exc}")
            return None
    return None


def _log_admin_action(
    admin_user_id: str,
    admin_id: Optional[str],
    action: str,
    *,
    target_user_id: Optional[str] = None,
    target_resource: Optional[str] = None,
    reason: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> None:
    """Insert an admin audit log row. Never raises on logging failure."""
    try:
        get_manager().db_client.insert(
            "admin_audit_logs",
            {
                "admin_user_id": admin_user_id,
                "admin_id": admin_id,
                "action": action,
                "target_user_id": target_user_id,
                "target_resource": target_resource,
                "reason": reason,
                "metadata": metadata or {},
            },
        )
    except Exception as exc:
        if _is_missing_table_error(exc):
            logger.warning("admin_audit_logs table missing. Run admin extensions migration.")
        else:
            logger.warning(f"Failed to write admin audit log ({action}): {exc}")


def _require_confirm_token(value: Optional[str]) -> None:
    if (value or "").strip().upper() != "CONFIRM":
        raise HTTPException(
            status_code=400,
            detail={"message": "Type CONFIRM to proceed with this destructive action."},
        )


# ---------------------------------------------------------------------------
# Session payload builder
# ---------------------------------------------------------------------------


def _build_session_user_payload(
    *,
    user_id: str,
    email: str,
    username: str,
    created_at: Optional[str] = None,
    provider: Optional[str] = None,
) -> dict:
    profile = _get_profile_persistent(user_id)
    role = str(profile.get("role") or "patient").lower()
    if role not in ALLOWED_ROLES:
        role = "patient"

    payload = {
        "id": user_id,
        "username": username,
        "email": email,
        "createdAt": created_at or profile.get("created_at", datetime.utcnow().isoformat()),
        "role": role,
        "account_status": _get_account_status(profile),
        "suspended_until": profile.get("suspended_until"),
        "admin_id": profile.get("admin_id"),
    }
    if provider:
        payload["provider"] = provider
    return payload


# ---------------------------------------------------------------------------
# Voice session helper
# ---------------------------------------------------------------------------


def _resume_or_start_conversation(mgr, user_id: str) -> str:
    """
    Resume the user's conversation for voice sessions.

    Preference order:
    1) Active conversation (is_active=true)
    2) Most recent conversation by created_at
    3) Create a new conversation
    """
    active = mgr.user_service.get_active_conversation(user_id)
    if active and active.get("conversation_id"):
        return active["conversation_id"]

    try:
        convs = mgr.db_client.select(
            "conversations",
            filters={"user_id": f"eq.{user_id}"},
        )
        if convs:
            convs_sorted = sorted(convs, key=lambda c: (c.get("created_at") or ""), reverse=True)
            latest = convs_sorted[0]
            conv_id = latest.get("conversation_id")
            if conv_id:
                try:
                    mgr.db_client.update(
                        "conversations",
                        {"is_active": True},
                        {"conversation_id": f"eq.{conv_id}"},
                    )
                except Exception:
                    pass
                return conv_id
    except Exception:
        pass

    conversation = mgr.user_service.create_conversation(user_id)
    return conversation["conversation_id"]


# ---------------------------------------------------------------------------
# Admin analytics helpers
# ---------------------------------------------------------------------------


def _coerce_role(value: Optional[str]) -> str:
    role = str(value or "patient").lower()
    return role if role in ALLOWED_ROLES else "patient"


def _build_user_metrics_by_user() -> Dict[str, dict]:
    stats_rows = _select_optional_table("user_stats")
    conv_rows = _select_optional_table("conversations")

    metrics: Dict[str, dict] = {}
    for row in stats_rows:
        uid = str(row.get("user_id") or "")
        if not uid:
            continue
        metrics[uid] = {
            "total_sessions": int(row.get("total_sessions") or 0),
            "total_minutes": int(row.get("total_minutes") or 0),
            "mood_improvement_percentage": int(row.get("mood_improvement_percentage") or 0),
            "last_session_date": row.get("last_session_date"),
        }

    conv_counts: Dict[str, int] = {}
    conv_minutes: Dict[str, int] = {}
    conv_last: Dict[str, str] = {}
    for conv in conv_rows:
        uid = str(conv.get("user_id") or "")
        if not uid:
            continue
        conv_counts[uid] = conv_counts.get(uid, 0) + 1
        conv_minutes[uid] = conv_minutes.get(uid, 0) + int(conv.get("duration_minutes") or 0)
        created_at = conv.get("created_at")
        if created_at and (uid not in conv_last or str(created_at) > str(conv_last[uid])):
            conv_last[uid] = str(created_at)

    for uid in set(list(conv_counts.keys()) + list(metrics.keys())):
        bucket = metrics.setdefault(uid, {
            "total_sessions": 0,
            "total_minutes": 0,
            "mood_improvement_percentage": 0,
            "last_session_date": None,
        })
        if not bucket.get("total_sessions"):
            bucket["total_sessions"] = conv_counts.get(uid, 0)
        if not bucket.get("total_minutes"):
            bucket["total_minutes"] = conv_minutes.get(uid, 0)
        if not bucket.get("last_session_date"):
            bucket["last_session_date"] = conv_last.get(uid)

    return metrics


# ---------------------------------------------------------------------------
# Schema translation helpers
# ---------------------------------------------------------------------------


def _backend_conversation_to_frontend(conv: dict) -> dict:
    return {
        "id": conv.get("conversation_id", conv.get("id", "")),
        "user_id": conv.get("user_id", ""),
        "title": conv.get("title", None),
        "mood": conv.get("mood", None),
        "summary": conv.get("summary", None),
        "tags": conv.get("tags", None),
        "duration_minutes": conv.get("duration_minutes", None),
        "is_active": conv.get("is_active", True),
        "total_turns": conv.get("total_turns", 0),
        "created_at": conv.get("created_at", datetime.utcnow().isoformat()),
        "updated_at": conv.get("updated_at", conv.get("created_at", datetime.utcnow().isoformat())),
    }


def _backend_message_to_frontend(msg: dict) -> dict:
    return {
        "id": msg.get("message_id", msg.get("id", "")),
        "conversation_id": msg.get("conversation_id", ""),
        "content": msg.get("content", ""),
        "is_user": msg.get("role") == "user" if "role" in msg else msg.get("is_user", False),
        "created_at": msg.get("created_at", datetime.utcnow().isoformat()),
    }
