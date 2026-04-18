"""
core/session.py — session store, cookie signing, and session helpers.

This module owns the SINGLE in-memory sessions dict and all cookie-level
operations so every route module imports from here — not from api.py —
to avoid sharing sessions across module-reload boundaries.
"""

import os
import uuid
from typing import Dict, Optional

from fastapi import Request, Response
from itsdangerous import BadSignature, TimestampSigner

# ---------------------------------------------------------------------------
# Secret / signing
# ---------------------------------------------------------------------------

SECRET_KEY = os.getenv("SESSION_SECRET", "3am-talks-dev-secret-change-in-production")
signer = TimestampSigner(SECRET_KEY)

# ---------------------------------------------------------------------------
# Auth constants
# ---------------------------------------------------------------------------

SESSION_COOKIE = "session_token"
SESSION_MAX_AGE = 60 * 60 * 24 * 7  # 7 days

VOICE_AGENT_SECRET = os.getenv("VOICE_AGENT_SECRET", "dev-voice-agent-secret")

# ---------------------------------------------------------------------------
# In-memory stores
# ---------------------------------------------------------------------------

# session_token  →  user payload dict
sessions: Dict[str, dict] = {}

# one-time OAuth token  →  user payload dict (short-lived)
temp_oauth_sessions: Dict[str, dict] = {}

# ---------------------------------------------------------------------------
# Cookie-level helpers
# ---------------------------------------------------------------------------


def create_session(user_data: dict, response: Response, secure: bool = False) -> str:
    """Create a new session, sign the token, and set it as an httpOnly cookie."""
    token = str(uuid.uuid4())
    signed_token = signer.sign(token).decode()
    sessions[token] = user_data
    response.set_cookie(
        key=SESSION_COOKIE,
        value=signed_token,
        httponly=True,
        samesite="lax",
        max_age=SESSION_MAX_AGE,
        path="/",
        secure=secure,
    )
    return token


def get_current_user(request: Request) -> Optional[dict]:
    """Extract the current user payload from the signed session cookie."""
    signed_token = request.cookies.get(SESSION_COOKIE)
    if not signed_token:
        return None
    try:
        token = signer.unsign(signed_token, max_age=SESSION_MAX_AGE).decode()
        return sessions.get(token)
    except BadSignature:
        return None


def clear_user_sessions(user_id: str) -> None:
    """Remove all in-memory sessions that belong to *user_id*."""
    to_remove = [
        token for token, data in sessions.items()
        if str(data.get("id")) == str(user_id)
    ]
    for token in to_remove:
        sessions.pop(token, None)


def update_user_sessions(user_id: str, updates: dict) -> None:
    """Patch in-memory session payloads for all sessions belonging to *user_id*."""
    for data in sessions.values():
        if str(data.get("id")) == str(user_id):
            data.update(updates)
