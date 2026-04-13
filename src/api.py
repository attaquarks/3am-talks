"""
3AM Talks (ELLA AI) — FastAPI Server
Bridges the React frontend with the Python backend ConversationManager.
Runs on port 5050. Frontend expects all endpoints under /api/*.
"""

import datetime as dt
import logging
import os
import sys
import uuid
import base64
import hashlib
import json
import secrets
import time
import urllib.parse
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from itsdangerous import BadSignature, TimestampSigner
from pydantic import BaseModel, EmailStr, Field

# ---------------------------------------------------------------------------
# Environment & path setup
# ---------------------------------------------------------------------------
load_dotenv()

# Ensure src/ is on the Python path so relative imports in backend modules work
SRC_DIR = Path(__file__).parent
ROOT_DIR = SRC_DIR.parent
sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(ROOT_DIR))

from database import normalize_postgrest_value

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("3am-api")


def _is_conflict_error(exc: BaseException) -> bool:
    """True when Supabase/PostgREST reports a unique-constraint conflict (HTTP 409)."""
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 409:
        return True
    msg = str(exc).lower()
    return "409" in msg or "conflict" in msg


# ---------------------------------------------------------------------------
# Secret key for cookie signing
# ---------------------------------------------------------------------------
SECRET_KEY = os.getenv("SESSION_SECRET", "3am-talks-dev-secret-change-in-production")
signer = TimestampSigner(SECRET_KEY)

# ---------------------------------------------------------------------------
# In-memory stores REMOVED - using Supabase for persistence
# ---------------------------------------------------------------------------

# Session store: maps session_token -> user data
sessions: Dict[str, dict] = {}

# Temporary one-time OAuth token store: maps ott -> user data (expires fast)
# Used to pass a session across the OAuth redirect without relying on
# Set-Cookie headers inside a 302 response (which Vite proxy drops).
temp_oauth_sessions: Dict[str, dict] = {}

# ---------------------------------------------------------------------------
# Pydantic models — request/response schemas
# ---------------------------------------------------------------------------


class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str = "User"


class LoginRequest(BaseModel):
    email: str
    password: str


class SocialLoginRequest(BaseModel):
    email: str
    name: str = "User"
    provider: str = "google"


class OAuthSessionRequest(BaseModel):
    access_token: str


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    conversation_history: Optional[List[dict]] = None


class VoiceChatRequest(BaseModel):
    user_id: str
    message: str
    conversation_id: Optional[str] = None


class VoiceBootstrapRequest(BaseModel):
    user_id: str


class UpdateEmailRequest(BaseModel):
    new_email: str


class UpdatePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class DataBody(BaseModel):
    """Generic body for CRUD data endpoints."""

    model_config = {"extra": "allow"}


def _resume_or_start_conversation(mgr, user_id: str) -> str:
    """
    Resume the user's conversation for voice sessions.

    Preference order:
    1) Active conversation (is_active=true)
    2) Most recent conversation by created_at (if available)
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
            convs_sorted = sorted(
                convs,
                key=lambda c: (c.get("created_at") or ""),
                reverse=True,
            )
            latest = convs_sorted[0]
            conv_id = latest.get("conversation_id")
            if conv_id:
                # Mark active so next time we resume consistently
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
# ConversationManager — lazy initialization
# ---------------------------------------------------------------------------
conversation_manager = None


def get_manager():
    """Lazily initialize the ConversationManager so startup doesn't block."""
    global conversation_manager
    if conversation_manager is None:
        try:
            from conversation_manager import ConversationManager

            conversation_manager = ConversationManager(
                model_name="psychocounsel",
                personality_model_path=str(
                    ROOT_DIR / "Models" / "bert-base-personality"
                ),
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
    return conversation_manager


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------

SESSION_COOKIE = "session_token"
SESSION_MAX_AGE = 60 * 60 * 24 * 7  # 7 days


def create_session(user_data: dict, response: Response, secure: bool = False) -> str:
    """Create a new session and set the cookie on the response."""
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
    """Extract the current user from the session cookie."""
    signed_token = request.cookies.get(SESSION_COOKIE)
    if not signed_token:
        return None
    try:
        token = signer.unsign(signed_token, max_age=SESSION_MAX_AGE).decode()
        return sessions.get(token)
    except BadSignature:
        return None


def require_user(request: Request) -> dict:
    """Get the current user or raise 401."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


# ---------------------------------------------------------------------------
# Voice-agent authentication (server-to-server)
# ---------------------------------------------------------------------------

VOICE_AGENT_SECRET = os.getenv("VOICE_AGENT_SECRET", "dev-voice-agent-secret")

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
BACKEND_PUBLIC_URL = os.getenv("BACKEND_PUBLIC_URL", "http://localhost:5050")

OAUTH_COOKIE = "oauth_pkce"
OAUTH_MAX_AGE_SECONDS = 10 * 60


def require_voice_agent(request: Request) -> None:
    auth = request.headers.get("authorization") or ""
    if not auth.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing voice agent authorization")
    token = auth.split(" ", 1)[1].strip()
    if token != VOICE_AGENT_SECRET:
        raise HTTPException(status_code=403, detail="Invalid voice agent authorization")


def clear_user_sessions(user_id: str) -> None:
    """Remove all local cookie sessions belonging to a user."""
    to_remove = [
        token for token, data in sessions.items() if str(data.get("id")) == str(user_id)
    ]
    for token in to_remove:
        sessions.pop(token, None)


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _pkce_challenge(verifier: str) -> str:
    return _b64url(hashlib.sha256(verifier.encode("utf-8")).digest())


def _set_oauth_cookie(response: Response, payload: dict) -> None:
    signed = signer.sign(json.dumps(payload)).decode()
    response.set_cookie(
        key=OAUTH_COOKIE,
        value=signed,
        httponly=True,
        samesite="lax",
        max_age=OAUTH_MAX_AGE_SECONDS,
        path="/",
    )


def _read_oauth_cookie(request: Request) -> dict:
    signed = request.cookies.get(OAUTH_COOKIE)
    if not signed:
        raise HTTPException(status_code=400, detail={"message": "Missing OAuth cookie"})
    try:
        raw = signer.unsign(signed, max_age=OAUTH_MAX_AGE_SECONDS).decode()
        return json.loads(raw)
    except BadSignature:
        raise HTTPException(status_code=400, detail={"message": "Invalid or expired OAuth cookie"})
    except Exception:
        raise HTTPException(status_code=400, detail={"message": "Malformed OAuth cookie"})


def _clear_oauth_cookie(response: Response) -> None:
    response.delete_cookie(OAUTH_COOKIE, path="/")


def _supabase_auth_headers() -> dict:
    key = os.getenv("SUPABASE_KEY")
    if not key:
        raise HTTPException(status_code=503, detail={"message": "SUPABASE_KEY is not configured"})
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def _oauth_error_redirect(message: str) -> RedirectResponse:
    """
    Redirect back to the frontend auth page with a friendly error message.
    """
    msg = urllib.parse.quote(message[:500])
    return RedirectResponse(url=f"{FRONTEND_URL}/auth?oauth_error={msg}", status_code=302)


# ---------------------------------------------------------------------------
# Database Helpers (Persistent)
# ---------------------------------------------------------------------------


def _get_profile_persistent(user_id: str) -> dict:
    """Fetch user profile from Supabase."""
    mgr = get_manager()
    profile = mgr.user_service.get_user_profile(user_id)
    if not profile:
        # Should have been created at register, but create if missing
        profile = mgr.user_service.create_user_profile(user_id)
    
    # Enrich with frontend-expected fields if missing
    if "name" not in profile:
        profile["name"] = "User"
    if "mood_preference" not in profile:
        profile["mood_preference"] = profile.get("preferences", {}).get("mood_preference", "neutral")
        
    return profile


def _get_stats_persistent(user_id: str) -> dict:
    """Fetch user stats from Supabase."""
    mgr = get_manager()
    try:
        stats = mgr.db_client.select("user_stats", filters={"user_id": f"eq.{user_id}"})
        if stats:
            return stats[0]
        
        # Create default stats if missing
        now = datetime.utcnow().isoformat()
        new_stats = {
            "user_id": user_id,
            "current_streak": 0,
            "total_sessions": 0,
            "total_minutes": 0,
            "mood_improvement_percentage": 0,
            "created_at": now,
            "updated_at": now
        }
        try:
            return mgr.db_client.insert("user_stats", new_stats)
        except Exception as insert_err:
            # Concurrent requests can race and one insert wins; fetch the row instead of surfacing 500.
            if _is_conflict_error(insert_err):
                existing = mgr.db_client.select("user_stats", filters={"user_id": f"eq.{user_id}"})
                if existing:
                    return existing[0]
            raise
    except Exception as e:
        logger.error(f"Error fetching stats for {user_id}: {e}")
        # Fallback to empty default to prevent crash
        return {
            "user_id": user_id,
            "current_streak": 0,
            "total_sessions": 0,
            "total_minutes": 0
        }


def _get_mood_entries_persistent(user_id: str) -> List[dict]:
    """Fetch mood entries from Supabase."""
    mgr = get_manager()
    try:
        # Order by date descending
        return mgr.db_client.select(
            "mood_entries", 
            filters={"user_id": f"eq.{user_id}"},
        )
        # Note: simplistic select, sorting handled in client or by Supabase if we add order param support
    except Exception as e:
        logger.error(f"Error fetching mood entries for {user_id}: {e}")
        return []


# ---------------------------------------------------------------------------
# Lifespan — startup & shutdown
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("3AM Talks API starting on port 5050")
    logger.info("Frontend expected at http://localhost:5173")
    # #region agent log — proves which oauth routes THIS process registered (catch stale uvicorn)
    try:
        _oauth = []
        for route in app.routes:
            p = getattr(route, "path", None)
            if p and "oauth" in p:
                _oauth.append(
                    {"path": p, "methods": sorted(list(getattr(route, "methods", ()) or []))}
                )
        _lp = ROOT_DIR / "debug-a2dded.log"
        with open(_lp, "a", encoding="utf-8") as _df:
            _df.write(
                json.dumps(
                    {
                        "sessionId": "a2dded",
                        "location": "api.py:lifespan:startup",
                        "message": "oauth routes in this process",
                        "data": {"oauth_routes": _oauth},
                        "timestamp": int(time.time() * 1000),
                    }
                )
                + "\n"
            )
    except Exception:
        pass
    # #endregion
    yield
    # Shutdown: clean up ConversationManager if it was initialized
    if conversation_manager is not None:
        try:
            conversation_manager.close()
            logger.info("ConversationManager closed")
        except Exception as e:
            logger.warning(f"Error closing ConversationManager: {e}")
    logger.info("3AM Talks API shut down")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="3AM Talks API",
    description="Backend API for ELLA AI therapy chatbot",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5050",
        "http://127.0.0.1:5050",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def agent_log_unmatched_api(request: Request, call_next):
    """Record 404s on /api* for debug (see debug-a2dded.log)."""
    response = await call_next(request)
    if response.status_code == 404 and request.url.path.startswith("/api"):
        # #region agent log
        try:
            _lp = ROOT_DIR / "debug-a2dded.log"
            _payload = {
                "sessionId": "a2dded",
                "hypothesisId": "H-404",
                "location": "api.py:agent_log_unmatched_api",
                "message": "404 on api path",
                "data": {"path": request.url.path, "method": request.method},
                "runId": "not-found",
                "timestamp": int(time.time() * 1000),
            }
            with open(_lp, "a", encoding="utf-8") as _df:
                _df.write(json.dumps(_payload) + "\n")
        except Exception:
            pass
        # #endregion
    return response


# ===================================================================
# AUTH ENDPOINTS
# ===================================================================


@app.post("/api/register")
def register(body: RegisterRequest, response: Response):
    """Register a new user via Supabase Auth, create persistent profile/stats, start session."""
    try:
        mgr = get_manager()
        result = mgr.register_user(body.email, body.password)
        user_id = result["user_id"]
        
        # Update profile with name (using raw update to profile table)
        try:
             mgr.db_client.update(
                "user_profiles",
                {"name": body.name},
                {"user_id": f"eq.{user_id}"}
            )
        except Exception as e:
            logger.warning(f"Could not sets name on profile: {e}")

        # Ensure persistent stats exist
        _get_stats_persistent(user_id)

        # Build user object matching frontend User interface
        user_data = {
            "id": user_id,
            "username": body.name,
            "email": body.email,
            "createdAt": datetime.utcnow().isoformat(),
        }

        create_session(user_data, response)
        return user_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration failed: {e}")
        raise HTTPException(status_code=400, detail={"message": str(e)})


@app.post("/api/login")
def login(body: LoginRequest, response: Response):
    """Login an existing user via Supabase Auth."""
    try:
        mgr = get_manager()
        result = mgr.login_user(body.email, body.password)
        user_id = result["user_id"]
        
        # Fetch profile for name
        profile = _get_profile_persistent(user_id)
        name = profile.get("name", body.email.split("@")[0])

        user_data = {
            "id": user_id,
            "username": name,
            "email": body.email,
            "createdAt": profile.get("created_at", datetime.utcnow().isoformat()),
        }
        
        # Ensure persistent stats exist
        _get_stats_persistent(user_id)

        create_session(user_data, response)
        return user_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login failed: {e}")
        raise HTTPException(status_code=401, detail={"message": str(e)})


@app.post("/api/auth/social")
def social_login(body: SocialLoginRequest, response: Response):
    """Social login requires real provider integration in production."""
    raise HTTPException(
        status_code=501,
        detail={
            "message": "Social login is not enabled. Configure real provider integration before using this endpoint."
        },
    )


@app.get("/api/auth/oauth/{provider}/start")
def oauth_start(provider: str):
    """
    Start Supabase OAuth implicit flow.

    Redirects the browser straight to Supabase /authorize with only the
    `redirect_to` parameter.  We deliberately do NOT pass `state`,
    `code_challenge`, or `code_challenge_method` — those are Supabase-internal
    fields; overriding them breaks Supabase's own state validation and causes
    the `bad_oauth_state` error.

    Supabase manages state internally, completes the OAuth dance with
    Google/Facebook, then redirects the browser to `redirect_to` with the
    tokens in the URL hash fragment:
      #access_token=...&refresh_token=...&token_type=bearer&...

    The frontend reads the hash and POSTs the access_token to
    /api/auth/oauth/session to create a backend cookie session.
    """
    provider = provider.strip().lower()
    if provider not in {"google", "facebook"}:
        raise HTTPException(status_code=400, detail={"message": "Unsupported provider"})

    supabase_url = os.getenv("SUPABASE_URL")
    if not supabase_url:
        raise HTTPException(status_code=503, detail={"message": "SUPABASE_URL is not configured"})

    # Redirect to a frontend page that can read the hash fragment
    frontend_callback = f"{FRONTEND_URL}/auth/oauth-success"
    authorize_url = (
        f"{supabase_url}/auth/v1/authorize"
        f"?provider={provider}"
        f"&redirect_to={urllib.parse.quote(frontend_callback, safe='')}"
    )

    # #region agent log
    try:
        _lp = ROOT_DIR / "debug-a2dded.log"
        _payload = {
            "sessionId": "a2dded",
            "hypothesisId": "H1-H3",
            "location": "api.py:oauth_start",
            "message": "oauth authorize URL built",
            "data": {
                "FRONTEND_URL": FRONTEND_URL,
                "frontend_callback": frontend_callback,
                "supabase_host": urllib.parse.urlparse(supabase_url).netloc,
                "redirect_to_quoted_prefix": urllib.parse.quote(frontend_callback, safe="")[:80],
            },
            "runId": "pre-fix",
            "timestamp": int(time.time() * 1000),
        }
        with open(_lp, "a", encoding="utf-8") as _df:
            _df.write(json.dumps(_payload) + "\n")
    except Exception:
        pass
    # #endregion

    return RedirectResponse(url=authorize_url, status_code=302)


@app.post("/api/oauth/session")
@app.post("/api/auth/oauth/session")
def oauth_session(body: OAuthSessionRequest, response: Response):
    """
    Exchange a Supabase access_token for a backend cookie session.

    The token is sent in the JSON body (not the query string) so long JWTs are
    not truncated by browser or proxy URL length limits.
    """
    import httpx

    access_token = body.access_token.strip()
    if not access_token:
        raise HTTPException(status_code=400, detail={"message": "Missing access_token"})

    # #region agent log
    try:
        _lp = ROOT_DIR / "debug-a2dded.log"
        _payload = {
            "sessionId": "a2dded",
            "hypothesisId": "H-A",
            "location": "api.py:oauth_session",
            "message": "oauth session body received",
            "data": {"token_len": len(access_token)},
            "runId": "session-fix",
            "timestamp": int(time.time() * 1000),
        }
        with open(_lp, "a", encoding="utf-8") as _df:
            _df.write(json.dumps(_payload) + "\n")
    except Exception:
        pass
    # #endregion

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    if not supabase_url or not supabase_key:
        raise HTTPException(status_code=503, detail={"message": "Supabase not configured"})

    try:
        r = httpx.get(
            f"{supabase_url}/auth/v1/user",
            headers={
                "apikey": supabase_key,
                "Authorization": f"Bearer {access_token}",
            },
            timeout=15.0,
        )
        if r.status_code >= 400:
            # #region agent log
            try:
                _lp = ROOT_DIR / "debug-a2dded.log"
                _payload = {
                    "sessionId": "a2dded",
                    "hypothesisId": "H-B",
                    "location": "api.py:oauth_session:supabase_user",
                    "message": "supabase auth/v1/user non-OK",
                    "data": {"http_status": r.status_code},
                    "runId": "session-fix",
                    "timestamp": int(time.time() * 1000),
                }
                with open(_lp, "a", encoding="utf-8") as _df:
                    _df.write(json.dumps(_payload) + "\n")
            except Exception:
                pass
            # #endregion
        r.raise_for_status()
        sb_user = r.json()
    except httpx.HTTPStatusError as e:
        logger.error("OAuth token validation failed: %s %s", e, e.response.text[:300])
        raise HTTPException(status_code=401, detail={"message": "Invalid or expired OAuth token"})
    except Exception as e:
        logger.error(f"OAuth token validation failed: {e}")
        raise HTTPException(status_code=401, detail={"message": "Invalid or expired OAuth token"})

    user_id = sb_user.get("id")
    email = (sb_user.get("email") or "").strip().lower()
    meta = sb_user.get("user_metadata") or {}
    name = (
        meta.get("full_name")
        or meta.get("name")
        or (email.split("@")[0] if email else "User")
    )

    if not user_id:
        raise HTTPException(status_code=401, detail={"message": "Could not identify user"})

    # Ensure app profile/stats exist
    mgr = get_manager()
    try:
        profile = mgr.user_service.get_user_profile(user_id)
        if not profile:
            mgr.user_service.create_user_profile(user_id)
        try:
            mgr.db_client.update(
                "user_profiles",
                {"name": name},
                {"user_id": f"eq.{user_id}"},
            )
        except Exception:
            pass
        _get_stats_persistent(user_id)
    except Exception as e:
        logger.warning(f"Post-OAuth profile init failed: {e}")

    user_data = {
        "id": user_id,
        "username": name,
        "email": email,
        "createdAt": datetime.utcnow().isoformat(),
        "provider": "oauth",
    }
    create_session(user_data, response)
    return user_data


@app.get("/api/user")
def get_user(request: Request):
    """Return the currently authenticated user from the session cookie."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail={"message": "Not authenticated"})
    return user


@app.post("/api/logout")
def logout(request: Request, response: Response):
    """Clear the session cookie."""
    signed_token = request.cookies.get(SESSION_COOKIE)
    if signed_token:
        try:
            token = signer.unsign(signed_token, max_age=SESSION_MAX_AGE).decode()
            sessions.pop(token, None)
        except BadSignature:
            pass
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"message": "Logged out"}


@app.patch("/api/account/email")
def update_account_email(body: UpdateEmailRequest, request: Request):
    """Update authenticated user's email in Supabase Auth and local profile table."""
    user = require_user(request)
    user_id = str(user["id"])
    new_email = body.new_email.strip().lower()
    if not new_email:
        raise HTTPException(status_code=400, detail={"message": "new_email is required"})

    mgr = get_manager()
    try:
        mgr.db_client.admin_update_user(user_id, {"email": new_email})

        # Keep local session/user profile consistent.
        user["email"] = new_email
        try:
            mgr.db_client.update(
                "user_profiles",
                {"email": new_email, "updated_at": datetime.utcnow().isoformat()},
                {"user_id": f"eq.{user_id}"},
            )
        except Exception:
            pass

        return {"message": "Email updated successfully", "email": new_email}
    except Exception as e:
        logger.error(f"Email update failed for {user_id}: {e}")
        raise HTTPException(status_code=400, detail={"message": str(e)})


@app.patch("/api/account/password")
def update_account_password(body: UpdatePasswordRequest, request: Request):
    """Update authenticated user's password after verifying current password."""
    user = require_user(request)
    user_id = str(user["id"])
    email = str(user.get("email", "")).strip().lower()
    old_password = body.old_password
    new_password = body.new_password

    if not old_password or not new_password:
        raise HTTPException(
            status_code=400, detail={"message": "old_password and new_password are required"}
        )
    if len(new_password) < 6:
        raise HTTPException(
            status_code=400,
            detail={"message": "new_password must be at least 6 characters long"},
        )

    mgr = get_manager()
    try:
        # Verify old password by attempting standard auth login.
        mgr.db_client.sign_in(email, old_password)
    except Exception:
        raise HTTPException(status_code=401, detail={"message": "Current password is incorrect"})

    try:
        mgr.db_client.admin_update_user(user_id, {"password": new_password})
        return {"message": "Password updated successfully"}
    except Exception as e:
        logger.error(f"Password update failed for {user_id}: {e}")
        raise HTTPException(status_code=400, detail={"message": str(e)})


@app.delete("/api/account")
def delete_account(request: Request, response: Response):
    """
    Permanently delete authenticated user's account and app data.
    """
    user = require_user(request)
    user_id = str(user["id"])
    mgr = get_manager()

    try:
        # Delete app data first.
        mgr.db_client.delete("messages", {"user_id": f"eq.{user_id}"})
        mgr.db_client.delete("conversations", {"user_id": f"eq.{user_id}"})
        mgr.db_client.delete("mood_entries", {"user_id": f"eq.{user_id}"})
        mgr.db_client.delete("user_stats", {"user_id": f"eq.{user_id}"})
        mgr.db_client.delete("user_profiles", {"user_id": f"eq.{user_id}"})
    except Exception as e:
        logger.warning(f"Some app data cleanup failed for {user_id}: {e}")

    try:
        # Delete auth identity in Supabase.
        mgr.db_client.admin_delete_user(user_id, should_soft_delete=False)
    except Exception as e:
        logger.error(f"Auth user deletion failed for {user_id}: {e}")
        raise HTTPException(status_code=400, detail={"message": str(e)})

    clear_user_sessions(user_id)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"message": "Account deleted successfully"}


# ===================================================================
# CHAT ENDPOINT — Core AI integration
# ===================================================================


@app.post("/api/chat")
def chat(body: ChatRequest, request: Request):
    """
    Process a user message through the full ConversationManager pipeline:
    personality detection, RAG retrieval, LLM response generation.
    """
    user = require_user(request)
    user_id = str(user["id"])

    try:
        mgr = get_manager()

        # If no conversation_id provided, start a new session
        conv_id = body.conversation_id
        if not conv_id:
            session_result = mgr.start_session(user_id, start_questionnaire=False)
            conv_id = session_result["conversation_id"]

        # Process the message through the full pipeline
        result = mgr.process_message(
            user_id=user_id,
            conversation_id=conv_id,
            user_message=body.message,
            is_questionnaire_response=False,
        )

        return {
            "response": result.get("response", "I'm here to listen."),
            "content": result.get("response", "I'm here to listen."),
            "conversation_id": conv_id,
            "turn": result.get("turn"),
            "personality_scores": result.get("personality_scores"),
            "rag_techniques_used": result.get("rag_techniques_used", 0),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat processing failed: {e}")
        # Return a graceful fallback instead of crashing
        return {
            "response": "I'm having a moment of reflection. Could you share that thought again?",
            "content": "I'm having a moment of reflection. Could you share that thought again?",
            "conversation_id": body.conversation_id,
            "error": str(e),
        }


# ===================================================================
# GENERIC CRUD — /api/data/{table}/{id?}
# Persistent Data Access
# ===================================================================

# --- Schema translation helpers ---


def _backend_conversation_to_frontend(conv: dict) -> dict:
    """Translate backend conversation schema to frontend schema."""
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
        "updated_at": conv.get(
            "updated_at", conv.get("created_at", datetime.utcnow().isoformat())
        ),
    }


def _backend_message_to_frontend(msg: dict) -> dict:
    """Translate backend message schema (role) to frontend schema (is_user)."""
    return {
        "id": msg.get("message_id", msg.get("id", "")),
        "conversation_id": msg.get("conversation_id", ""),
        "content": msg.get("content", ""),
        "is_user": msg.get("role") == "user"
        if "role" in msg
        else msg.get("is_user", False),
        "created_at": msg.get("created_at", datetime.utcnow().isoformat()),
    }


# --- GET ---


@app.get("/api/data/{table}")
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


@app.get("/api/data/{table}/{record_id}")
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


# --- POST ---


@app.post("/api/data/{table}")
def create_table_record(table: str, request: Request, body: dict = {}):
    """Create a new record in a table."""
    user = require_user(request)
    user_id = str(user["id"])
    now = datetime.utcnow().isoformat()
    mgr = get_manager()

    try:
        if table == "conversations":
            session_result = mgr.start_session(user_id, start_questionnaire=False)
            conv_id = session_result["conversation_id"]
            conv = mgr.user_service.get_conversation(conv_id) or {}
            frontend_conv = _backend_conversation_to_frontend(conv)
            
            # Apply frontend fields
            frontend_conv.update({k: v for k, v in body.items() if k in ["title", "mood", "tags", "duration_minutes"]})
            # Ideally store these in Supabase metadata column if available, for now returning them ephemeral
            return frontend_conv

        elif table == "messages":
            conv_id = body.get("conversation_id")
            if conv_id is not None:
                conv_id = normalize_postgrest_value(str(conv_id))
            content = body.get("content", "")
            is_user = body.get("is_user", True)

            if not conv_id:
                raise HTTPException(status_code=400, detail="conversation_id required")

            # Get current turn count
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
            # Update turn count
            mgr.user_service.update_conversation_turns(conv_id, increment=1)
            return _backend_message_to_frontend(msg)

        elif table == "profiles":
            # Updates profile
            updates = {k: v for k, v in body.items() if k in ("name")}
            if "mood_preference" in body:
                # Get current preferences to merge
                profile = mgr.user_service.get_user_profile(user_id)
                prefs = profile.get("preferences", {})
                prefs["mood_preference"] = body["mood_preference"]
                updates["preferences"] = prefs
            
            if updates:
                mgr.db_client.update("user_profiles", updates, {"user_id": f"eq.{user_id}"})
            return _get_profile_persistent(user_id)

        elif table == "user_stats":
            # Creating new stats usually happens automatically, but support manual creation
            data = {k:v for k,v in body.items() if k in ["current_streak", "total_sessions", "total_minutes"]}
            data["user_id"] = user_id
            try:
                return mgr.db_client.insert("user_stats", data)
            except Exception as e:
                # If stats already exist, treat POST as idempotent and return current stats.
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


# --- PATCH ---


@app.patch("/api/data/{table}/{record_id}")
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
            
            # Return current state
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
            
            # Fetch updated
            entries = mgr.db_client.select("mood_entries", filters={"id": f"eq.{rid}"})
            return entries[0] if entries else {}

        else:
            raise HTTPException(status_code=404, detail=f"Unknown table: {table}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PATCH /api/data/{table}/{record_id} failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- DELETE ---


@app.delete("/api/data/{table}/{record_id}")
def delete_table_record(table: str, record_id: str, request: Request):
    """Delete a record by ID."""
    user = require_user(request)
    user_id = str(user["id"])
    mgr = get_manager()

    try:
        if table == "conversations":
            mgr.end_session(normalize_postgrest_value(record_id))
            return {"message": "Conversation ended"}

        elif table == "profiles":
            # Soft delete? Or hard delete? "deleted" field suggests soft.
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


# ===================================================================
# LIVEKIT VOICE — Token endpoint
# ===================================================================


@app.post("/api/livekit/token")
def livekit_token(request: Request):
    """Generate a LiveKit access token for a voice session.

    Returns connection details the frontend needs to join a LiveKit room
    and talk to the Ella voice agent.
    """
    user = require_user(request)
    user_id = str(user["id"])

    lk_api_key = os.getenv("LIVEKIT_API_KEY")
    lk_api_secret = os.getenv("LIVEKIT_API_SECRET")
    lk_url = os.getenv("LIVEKIT_URL", "ws://localhost:7880")

    if not lk_api_key or not lk_api_secret:
        raise HTTPException(
            status_code=503,
            detail="LiveKit credentials not configured on the server.",
        )

    try:
        from livekit import api as lk_api

        # Stable room per user so the agent can resume context for returning users.
        # LiveKit rooms are ephemeral, but room names can be reused across sessions.
        room_name = f"ella-voice-{user_id}"

        token = (
            lk_api.AccessToken(api_key=lk_api_key, api_secret=lk_api_secret)
            # Encode full user_id in identity so the voice agent can recover it from the room.
            .with_identity(f"user-{user_id}")
            .with_name(user.get("username", "User"))
            .with_grants(
                lk_api.VideoGrants(
                    room_join=True,
                    room=room_name,
                    can_publish=True,
                    can_subscribe=True,
                    can_publish_data=True,
                )
            )
            .with_ttl(dt.timedelta(minutes=30))
            .to_jwt()
        )

        return {
            "serverUrl": lk_url,
            "roomName": room_name,
            "participantName": user.get("username", "User"),
            "participantToken": token,
        }

    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="livekit-api package not installed. Run: pip install livekit-api",
        )
    except Exception as e:
        logger.error(f"LiveKit token generation failed: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to generate voice session token."
        )


# ===================================================================
# VOICE AGENT → BACKEND BRIDGE (uses ConversationManager pipeline)
# ===================================================================


@app.post("/api/voice/bootstrap")
def voice_bootstrap(body: VoiceBootstrapRequest, request: Request):
    """
    Server-to-server endpoint used by the LiveKit voice agent.
    Resolves the conversation_id to resume (or starts one) for the given user.
    """
    require_voice_agent(request)
    mgr = get_manager()

    # Ensure profile exists
    _get_profile_persistent(body.user_id)

    conv_id = _resume_or_start_conversation(mgr, body.user_id)
    return {"conversation_id": conv_id}


@app.post("/api/voice/chat")
def voice_chat(body: VoiceChatRequest, request: Request):
    """
    Server-to-server endpoint used by the LiveKit voice agent.
    Routes the message through the full ConversationManager pipeline so voice
    shares the exact same persona, memory, RAG, and personality adaptation.
    """
    require_voice_agent(request)
    mgr = get_manager()

    # Ensure profile exists
    _get_profile_persistent(body.user_id)

    conv_id = body.conversation_id or _resume_or_start_conversation(mgr, body.user_id)

    result = mgr.process_message(
        user_id=body.user_id,
        conversation_id=conv_id,
        user_message=body.message,
        is_questionnaire_response=False,
    )

    return {
        "conversation_id": conv_id,
        "response": result.get("response", "I'm here to listen."),
        "turn": result.get("turn"),
        "personality_scores": result.get("personality_scores"),
        "rag_techniques_used": result.get("rag_techniques_used", 0),
    }


# ===================================================================
# HEALTH CHECK
# ===================================================================


@app.get("/api/health")
def health_check():
    """Basic health check endpoint."""
    return {
        "status": "ok",
        "service": "3AM Talks API",
        "version": "1.0.0",
        "manager_initialized": conversation_manager is not None,
    }


# ===================================================================
# ENTRY POINT
# ===================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        # Import string required for reload=True; `src` is a package.
        "src.api:app",
        host="0.0.0.0",
        port=5050,
        reload=True,
        log_level="info",
    )
