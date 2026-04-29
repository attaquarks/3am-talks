"""
core/session.py — session store, cookie signing, and session helpers.

This module owns the SINGLE in-memory sessions dict and all cookie-level
operations so every route module imports from here — not from api.py —
to avoid sharing sessions across module-reload boundaries.
"""

import os
import uuid
from pathlib import Path
from typing import Dict, Optional

from fastapi import Request, Response
from dotenv import load_dotenv
from itsdangerous import BadSignature, TimestampSigner

# ---------------------------------------------------------------------------
# Secret / signing
# ---------------------------------------------------------------------------

# Ensure .env is loaded no matter how the app is started (uvicorn module path,
# direct script execution, tests, etc.).
ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")

SECRET_KEY = os.getenv("SESSION_SECRET")
if not SECRET_KEY:
    raise RuntimeError(
        "SESSION_SECRET environment variable is required. "
        "Set it in your .env file (e.g. SESSION_SECRET=some-random-string-here)."
    )
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


def is_https_request(request: Optional[Request]) -> bool:
    """Return True when the originating request was HTTPS.

    Trusts the X-Forwarded-Proto header set by upstream proxies (ngrok,
    Vercel rewrite). Falls back to the immediate request scheme when no
    forwarded header is present. Modern browsers reject Secure=False
    cookies on HTTPS pages, so we need this to set the right flag.
    """
    if request is None:
        return False
    forwarded = request.headers.get("x-forwarded-proto", "")
    if forwarded:
        return forwarded.split(",")[0].strip().lower() == "https"
    return request.url.scheme == "https"


def create_session(
    user_data: dict,
    response: Response,
    request: Optional[Request] = None,
    *,
    secure: Optional[bool] = None,
) -> str:
    """Create a new session, sign the token, and set it as an httpOnly cookie.

    The Secure flag is auto-detected from `request` so the same code works
    on HTTP localhost and HTTPS production behind Vercel/ngrok. Pass `secure=`
    explicitly to override.
    """
    token = str(uuid.uuid4())
    signed_token = signer.sign(token).decode()
    sessions[token] = user_data

    if secure is None:
        secure = is_https_request(request)

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
