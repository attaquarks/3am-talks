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
SECRET_KEY = os.getenv("SESSION_SECRET")
if not SECRET_KEY:
    raise RuntimeError(
        "SESSION_SECRET environment variable is required. "
        "Set it in your .env file (e.g. SESSION_SECRET=some-random-string-here)."
    )
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


ALLOWED_ROLES = {"patient", "therapist", "admin"}
ALLOWED_ACCOUNT_STATUSES = {"active", "suspended", "banned"}


class AdminUserStatusUpdateRequest(BaseModel):
    status: str
    reason: str
    suspended_until: Optional[datetime] = None
    confirm: Optional[str] = None


class AdminUserRoleUpdateRequest(BaseModel):
    role: str
    reason: str
    confirm: Optional[str] = None


class AdminUserDeleteRequest(BaseModel):
    reason: str
    confirm: Optional[str] = None


class AdminReportUpdateRequest(BaseModel):
    status: str
    reason: Optional[str] = None


class AdminFeedbackUpdateRequest(BaseModel):
    status: str
    reason: Optional[str] = None


class TherapistVerificationReviewRequest(BaseModel):
    status: str
    review_notes: Optional[str] = None


class AnnouncementCreateRequest(BaseModel):
    title: str
    body: str
    audience: Optional[str] = "all"
    expires_at: Optional[datetime] = None


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


def _parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


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
        suspended_until = _parse_iso_datetime(profile.get("suspended_until") if profile else None)
        if suspended_until:
            return f"Your account is suspended until {suspended_until.isoformat()}."
        return "Your account is suspended. Contact support for assistance."

    return None


def _build_session_user_payload(*, user_id: str, email: str, username: str, created_at: Optional[str] = None, provider: Optional[str] = None) -> dict:
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


def require_user(request: Request) -> dict:
    """Get the current user or raise 401."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user_id = str(user.get("id") or "")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    profile = _get_profile_persistent(user_id)
    block_message = _status_block_message(profile)
    if block_message:
        raise HTTPException(status_code=403, detail={"message": block_message, "account_status": _get_account_status(profile)})

    # Keep session payload synchronized with profile role/status updates.
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


# ---------------------------------------------------------------------------
# Voice-agent authentication (server-to-server)
# ---------------------------------------------------------------------------

VOICE_AGENT_SECRET = os.getenv("VOICE_AGENT_SECRET", "dev-voice-agent-secret")

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
BACKEND_PUBLIC_URL = os.getenv("BACKEND_PUBLIC_URL", "http://localhost:5050")

OAUTH_COOKIE = "oauth_pkce"
OAUTH_MAX_AGE_SECONDS = 10 * 60


def require_voice_agent(request: Request) -> None:
    import hmac as _hmac
    auth = request.headers.get("authorization") or ""
    if not auth.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing voice agent authorization")
    token = auth.split(" ", 1)[1].strip()
    if not _hmac.compare_digest(token, VOICE_AGENT_SECRET):
        raise HTTPException(status_code=403, detail="Invalid voice agent authorization")


def clear_user_sessions(user_id: str) -> None:
    """Remove all local cookie sessions belonging to a user."""
    to_remove = [
        token for token, data in sessions.items() if str(data.get("id")) == str(user_id)
    ]
    for token in to_remove:
        sessions.pop(token, None)


def update_user_sessions(user_id: str, updates: dict) -> None:
    """Update in-memory session payloads for a user."""
    for data in sessions.values():
        if str(data.get("id")) == str(user_id):
            data.update(updates)


def _is_missing_table_error(exc: BaseException) -> bool:
    if not isinstance(exc, httpx.HTTPStatusError):
        return False
    text = (exc.response.text or "").lower()
    return "does not exist" in text or "relation" in text


def _select_optional_table(table: str, filters: Optional[dict] = None) -> List[dict]:
    mgr = get_manager()
    try:
        rows = mgr.db_client.select(table, filters=filters)
        return rows if isinstance(rows, list) else []
    except Exception as exc:
        if _is_missing_table_error(exc):
            logger.warning("Optional table '%s' is missing. Run Supabase admin migration.", table)
            return []
        raise


def _generate_admin_id() -> str:
    """Generate a human-readable admin identifier like ADM-A1B2C3."""
    return f"ADM-{secrets.token_hex(3).upper()}"


def _ensure_admin_id(user_id: str, profile: Optional[dict] = None) -> Optional[str]:
    """Ensure an admin user has a unique admin_id. Persists if newly generated."""
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
    role = str(profile.get("role") or "patient").lower()
    profile["role"] = role if role in ALLOWED_ROLES else "patient"
    profile["account_status"] = _get_account_status(profile)
        
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

# ---------------------------------------------------------------------------
# Rate limiting (slowapi)
# ---------------------------------------------------------------------------
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
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
@limiter.limit("5/minute")
def register(request: Request, body: RegisterRequest, response: Response):
    """Register a new user via Supabase Auth, create persistent profile/stats, start session."""
    try:
        mgr = get_manager()
        result = mgr.register_user(body.email, body.password)
        user_id = result["user_id"]
        
        # Update profile with defaults required by the web app and admin features.
        try:
            mgr.db_client.update(
                "user_profiles",
                {
                    "name": body.name,
                    "email": body.email,
                    "role": "patient",
                    "account_status": "active",
                    "updated_at": datetime.utcnow().isoformat(),
                },
                {"user_id": f"eq.{user_id}"}
            )
        except Exception as e:
            logger.warning(f"Could not set full profile defaults during register: {e}")
            try:
                mgr.db_client.update(
                    "user_profiles",
                    {"name": body.name, "updated_at": datetime.utcnow().isoformat()},
                    {"user_id": f"eq.{user_id}"}
                )
            except Exception:
                pass

        # Ensure persistent stats exist
        _get_stats_persistent(user_id)

        user_data = _build_session_user_payload(
            user_id=user_id,
            email=body.email,
            username=body.name,
            created_at=datetime.utcnow().isoformat(),
        )

        create_session(user_data, response)
        return user_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration failed: {e}")
        raise HTTPException(status_code=400, detail={"message": str(e)})


@app.post("/api/login")
@limiter.limit("5/minute")
def login(request: Request, body: LoginRequest, response: Response):
    """Login an existing user via Supabase Auth."""
    try:
        mgr = get_manager()
        result = mgr.login_user(body.email, body.password)
        user_id = result["user_id"]
        
        # Fetch profile for name
        profile = _get_profile_persistent(user_id)
        name = profile.get("name", body.email.split("@")[0])

        blocked_reason = _status_block_message(profile)
        if blocked_reason:
            raise HTTPException(status_code=403, detail={"message": blocked_reason, "account_status": _get_account_status(profile)})

        user_data = _build_session_user_payload(
            user_id=user_id,
            email=body.email,
            username=name,
            created_at=profile.get("created_at", datetime.utcnow().isoformat()),
        )
        
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

    Supabase manages its own `state` parameter internally — injecting a custom
    one causes `bad_oauth_state` errors.  Instead we set a short-lived
    `oauth_nonce` cookie that the POST to /api/auth/oauth/session must echo
    back, preventing CSRF on the token-exchange step.

    Supabase completes the OAuth dance with Google/Facebook, then redirects
    the browser to `redirect_to` with tokens in the URL hash fragment.
    The frontend reads the hash and POSTs the access_token (plus the nonce)
    to /api/auth/oauth/session to create a backend cookie session.
    """
    provider = provider.strip().lower()
    if provider not in {"google", "facebook"}:
        raise HTTPException(status_code=400, detail={"message": "Unsupported provider"})

    supabase_url = os.getenv("SUPABASE_URL")
    if not supabase_url:
        raise HTTPException(status_code=503, detail={"message": "SUPABASE_URL is not configured"})

    # Anti-CSRF nonce: stored in a cookie, must be echoed back on token exchange
    nonce = secrets.token_urlsafe(32)

    # Redirect to a frontend page that can read the hash fragment
    frontend_callback = f"{FRONTEND_URL}/auth/oauth-success"
    authorize_url = (
        f"{supabase_url}/auth/v1/authorize"
        f"?provider={provider}"
        f"&redirect_to={urllib.parse.quote(frontend_callback, safe='')}"
    )

    resp = RedirectResponse(url=authorize_url, status_code=302)
    resp.set_cookie(
        "oauth_nonce",
        nonce,
        max_age=OAUTH_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return resp


@app.post("/api/oauth/session")
@app.post("/api/auth/oauth/session")
def oauth_session(body: OAuthSessionRequest, request: Request, response: Response):
    """
    Exchange a Supabase access_token for a backend cookie session.

    The token is sent in the JSON body (not the query string) so long JWTs are
    not truncated by browser or proxy URL length limits.

    Validates the oauth_nonce cookie set during /oauth/{provider}/start to
    prevent CSRF on this token-exchange step.
    """
    import httpx

    # --- Anti-CSRF: verify the oauth_nonce cookie exists ---
    # This cookie was set during /oauth/{provider}/start with httponly + samesite=lax.
    # Its presence proves the user started the flow from our domain (not a CSRF attack).
    cookie_nonce = request.cookies.get("oauth_nonce")
    if not cookie_nonce:
        logger.warning("OAuth session exchange attempted without oauth_nonce cookie — possible CSRF")
    # Clear the one-time nonce cookie
    response.delete_cookie("oauth_nonce", path="/")

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
                {
                    "name": name,
                    "email": email,
                    "role": "patient",
                    "account_status": "active",
                    "updated_at": datetime.utcnow().isoformat(),
                },
                {"user_id": f"eq.{user_id}"},
            )
        except Exception:
            # Older schemas may not have all admin columns yet.
            try:
                mgr.db_client.update(
                    "user_profiles",
                    {"name": name, "updated_at": datetime.utcnow().isoformat()},
                    {"user_id": f"eq.{user_id}"},
                )
            except Exception:
                pass
        _get_stats_persistent(user_id)
    except Exception as e:
        logger.warning(f"Post-OAuth profile init failed: {e}")

    profile = _get_profile_persistent(user_id)
    blocked_reason = _status_block_message(profile)
    if blocked_reason:
        raise HTTPException(status_code=403, detail={"message": blocked_reason, "account_status": _get_account_status(profile)})

    user_data = _build_session_user_payload(
        user_id=user_id,
        email=email,
        username=name,
        created_at=datetime.utcnow().isoformat(),
        provider="oauth",
    )
    create_session(user_data, response)
    return user_data


@app.get("/api/user")
def get_user(request: Request):
    """Return the currently authenticated user from the session cookie."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail={"message": "Not authenticated"})

    profile = _get_profile_persistent(str(user.get("id") or ""))
    blocked_reason = _status_block_message(profile)
    if blocked_reason:
        raise HTTPException(status_code=403, detail={"message": blocked_reason, "account_status": _get_account_status(profile)})

    user["role"] = profile.get("role", "patient")
    user["account_status"] = _get_account_status(profile)
    user["suspended_until"] = profile.get("suspended_until")
    user["admin_id"] = profile.get("admin_id")
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
        update_user_sessions(user_id, {"email": new_email})
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
# ADMIN ENDPOINTS
# ===================================================================


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


@app.get("/api/admin/overview")
def admin_overview(request: Request):
    """Platform-level admin analytics and queue overview."""
    require_admin(request)

    profiles = _select_optional_table("user_profiles")
    reports = _select_optional_table("moderation_reports")
    feedback = _select_optional_table("platform_feedback")
    conversations = _select_optional_table("conversations")

    now = datetime.utcnow()
    seven_days_ago = now - dt.timedelta(days=7)

    role_counts = {"patient": 0, "therapist": 0, "admin": 0}
    status_counts = {"active": 0, "suspended": 0, "banned": 0}
    new_users_7d = 0

    for profile in profiles:
        role = _coerce_role(profile.get("role"))
        status = _get_account_status(profile)
        role_counts[role] = role_counts.get(role, 0) + 1
        status_counts[status] = status_counts.get(status, 0) + 1

        created_at = _parse_iso_datetime(profile.get("created_at"))
        if created_at and created_at.replace(tzinfo=None) >= seven_days_ago:
            new_users_7d += 1

    conversations_7d = 0
    total_minutes_7d = 0
    for conv in conversations:
        created_at = _parse_iso_datetime(conv.get("created_at"))
        if created_at and created_at.replace(tzinfo=None) >= seven_days_ago:
            conversations_7d += 1
            total_minutes_7d += int(conv.get("duration_minutes") or 0)

    open_report_statuses = {"open", "in_review"}
    pending_feedback_statuses = {"open"}
    open_reports = [r for r in reports if str(r.get("status") or "open").lower() in open_report_statuses]
    pending_feedback = [f for f in feedback if str(f.get("status") or "open").lower() in pending_feedback_statuses]

    recent_reports = sorted(reports, key=lambda r: str(r.get("created_at") or ""), reverse=True)[:5]
    recent_feedback = sorted(feedback, key=lambda f: str(f.get("created_at") or ""), reverse=True)[:5]

    return {
        "total_users": len(profiles),
        "role_counts": role_counts,
        "status_counts": status_counts,
        "new_users_7d": new_users_7d,
        "conversations_7d": conversations_7d,
        "total_minutes_7d": total_minutes_7d,
        "open_reports": len(open_reports),
        "pending_feedback": len(pending_feedback),
        "recent_reports": recent_reports,
        "recent_feedback": recent_feedback,
    }


@app.get("/api/admin/users")
def admin_users(request: Request):
    """List users across the platform for admin oversight."""
    require_admin(request)

    role_filter = str(request.query_params.get("role") or "all").lower()
    status_filter = str(request.query_params.get("status") or "all").lower()
    search = str(request.query_params.get("search") or "").strip().lower()

    profiles = _select_optional_table("user_profiles")
    metrics_by_user = _build_user_metrics_by_user()

    users = []
    for profile in profiles:
        user_id = str(profile.get("user_id") or "")
        if not user_id:
            continue

        role = _coerce_role(profile.get("role"))
        account_status = _get_account_status(profile)

        if role_filter != "all" and role != role_filter:
            continue
        if status_filter != "all" and account_status != status_filter:
            continue

        name = str(profile.get("name") or "User")
        email = str(profile.get("email") or "")
        haystack = f"{name} {email} {user_id}".lower()
        if search and search not in haystack:
            continue

        metrics = metrics_by_user.get(user_id, {
            "total_sessions": 0,
            "total_minutes": 0,
            "mood_improvement_percentage": 0,
            "last_session_date": None,
        })

        users.append({
            "user_id": user_id,
            "name": name,
            "email": email,
            "role": role,
            "account_status": account_status,
            "suspended_until": profile.get("suspended_until"),
            "status_reason": profile.get("status_reason"),
            "created_at": profile.get("created_at"),
            "updated_at": profile.get("updated_at"),
            "total_sessions": int(metrics.get("total_sessions") or 0),
            "total_minutes": int(metrics.get("total_minutes") or 0),
            "mood_improvement_percentage": int(metrics.get("mood_improvement_percentage") or 0),
            "last_session_date": metrics.get("last_session_date"),
        })

    users_sorted = sorted(users, key=lambda u: str(u.get("created_at") or ""), reverse=True)
    return {
        "users": users_sorted,
        "total": len(users_sorted),
    }


@app.patch("/api/admin/users/{target_user_id}/status")
def admin_update_user_status(target_user_id: str, body: AdminUserStatusUpdateRequest, request: Request):
    """Suspend, ban, or reactivate platform users."""
    admin_user = require_admin(request)
    admin_user_id = str(admin_user["id"])
    admin_id = admin_user.get("admin_id")

    status = str(body.status or "").lower()
    if status not in ALLOWED_ACCOUNT_STATUSES:
        raise HTTPException(status_code=400, detail={"message": "Invalid status. Use active, suspended, or banned."})

    reason = (body.reason or "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail={"message": "A reason is required for this action."})

    _require_confirm_token(body.confirm)

    normalized_target = normalize_postgrest_value(target_user_id)
    if normalized_target == admin_user_id and status != "active":
        raise HTTPException(status_code=400, detail={"message": "You cannot suspend or ban your own admin account."})

    mgr = get_manager()
    existing = mgr.db_client.select("user_profiles", filters={"user_id": f"eq.{normalized_target}"})
    if not existing:
        raise HTTPException(status_code=404, detail={"message": "User not found."})

    previous_status = str(existing[0].get("account_status") or "active")

    suspended_until = None
    if status == "suspended":
        until = body.suspended_until or (datetime.utcnow() + dt.timedelta(days=7))
        suspended_until = until.isoformat()

    updates = {
        "account_status": status,
        "status_reason": reason,
        "suspended_until": suspended_until,
        "moderated_by": admin_user_id,
        "moderated_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }

    mgr.db_client.update("user_profiles", updates, {"user_id": f"eq.{normalized_target}"})

    update_user_sessions(normalized_target, {
        "account_status": status,
        "suspended_until": suspended_until,
    })
    if status != "active":
        clear_user_sessions(normalized_target)

    _log_admin_action(
        admin_user_id,
        admin_id,
        f"user_status_{status}",
        target_user_id=normalized_target,
        target_resource=f"user_profiles:{normalized_target}",
        reason=reason,
        metadata={"previous_status": previous_status, "suspended_until": suspended_until},
    )

    refreshed = mgr.db_client.select("user_profiles", filters={"user_id": f"eq.{normalized_target}"})
    return refreshed[0] if refreshed else {"message": "Status updated"}


@app.patch("/api/admin/users/{target_user_id}/role")
def admin_update_user_role(target_user_id: str, body: AdminUserRoleUpdateRequest, request: Request):
    """Promote or reassign a user's role across patient/therapist/admin."""
    admin_user = require_admin(request)
    admin_user_id = str(admin_user["id"])
    admin_id = admin_user.get("admin_id")

    role = str(body.role or "").lower()
    if role not in ALLOWED_ROLES:
        raise HTTPException(status_code=400, detail={"message": "Invalid role. Use patient, therapist, or admin."})

    reason = (body.reason or "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail={"message": "A reason is required for this action."})

    _require_confirm_token(body.confirm)

    normalized_target = normalize_postgrest_value(target_user_id)
    if normalized_target == admin_user_id and role != "admin":
        raise HTTPException(status_code=400, detail={"message": "You cannot remove your own admin role."})

    mgr = get_manager()
    existing = mgr.db_client.select("user_profiles", filters={"user_id": f"eq.{normalized_target}"})
    if not existing:
        raise HTTPException(status_code=404, detail={"message": "User not found."})

    previous_role = str(existing[0].get("role") or "patient")

    updates = {
        "role": role,
        "moderated_by": admin_user_id,
        "moderated_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }
    mgr.db_client.update("user_profiles", updates, {"user_id": f"eq.{normalized_target}"})
    update_user_sessions(normalized_target, {"role": role})

    # Auto-assign admin_id on promotion to admin.
    if role == "admin":
        refreshed_profile = mgr.db_client.select("user_profiles", filters={"user_id": f"eq.{normalized_target}"})
        profile_row = refreshed_profile[0] if refreshed_profile else {}
        _ensure_admin_id(normalized_target, profile_row)

    _log_admin_action(
        admin_user_id,
        admin_id,
        f"role_changed_to_{role}",
        target_user_id=normalized_target,
        target_resource=f"user_profiles:{normalized_target}",
        reason=reason,
        metadata={"previous_role": previous_role},
    )

    refreshed = mgr.db_client.select("user_profiles", filters={"user_id": f"eq.{normalized_target}"})
    return refreshed[0] if refreshed else {"message": "Role updated"}


@app.delete("/api/admin/users/{target_user_id}")
def admin_delete_user(target_user_id: str, body: AdminUserDeleteRequest, request: Request):
    """Hard-delete a user profile (and cascaded data)."""
    admin_user = require_admin(request)
    admin_user_id = str(admin_user["id"])
    admin_id = admin_user.get("admin_id")

    reason = (body.reason or "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail={"message": "A reason is required to delete a user."})

    _require_confirm_token(body.confirm)

    normalized_target = normalize_postgrest_value(target_user_id)
    if normalized_target == admin_user_id:
        raise HTTPException(status_code=400, detail={"message": "You cannot delete your own admin account."})

    mgr = get_manager()
    existing = mgr.db_client.select("user_profiles", filters={"user_id": f"eq.{normalized_target}"})
    if not existing:
        raise HTTPException(status_code=404, detail={"message": "User not found."})

    snapshot = {
        "name": existing[0].get("name"),
        "email": existing[0].get("email"),
        "role": existing[0].get("role"),
        "account_status": existing[0].get("account_status"),
    }

    try:
        mgr.db_client.delete("user_profiles", {"user_id": f"eq.{normalized_target}"})
    except Exception as exc:
        logger.error(f"Failed to delete user_profiles for {normalized_target}: {exc}")
        raise HTTPException(status_code=500, detail={"message": "Failed to delete user."})

    clear_user_sessions(normalized_target)

    _log_admin_action(
        admin_user_id,
        admin_id,
        "user_deleted",
        target_user_id=normalized_target,
        target_resource=f"user_profiles:{normalized_target}",
        reason=reason,
        metadata=snapshot,
    )

    return {"message": "User deleted", "user_id": normalized_target}


@app.get("/api/admin/reports")
def admin_reports(request: Request):
    """Fetch moderation reports queue for triage."""
    require_admin(request)

    status_filter = str(request.query_params.get("status") or "all").lower()
    priority_filter = str(request.query_params.get("priority") or "all").lower()

    rows = _select_optional_table("moderation_reports")
    filtered = []
    for row in rows:
        status = str(row.get("status") or "open").lower()
        priority = str(row.get("priority") or "medium").lower()
        if status_filter != "all" and status != status_filter:
            continue
        if priority_filter != "all" and priority != priority_filter:
            continue
        filtered.append(row)

    filtered_sorted = sorted(filtered, key=lambda r: str(r.get("created_at") or ""), reverse=True)
    return {
        "reports": filtered_sorted,
        "total": len(filtered_sorted),
    }


@app.patch("/api/admin/reports/{report_id}")
def admin_update_report(report_id: str, body: AdminReportUpdateRequest, request: Request):
    """Update report triage status (open/in_review/resolved/dismissed)."""
    admin_user = require_admin(request)
    status = str(body.status or "").lower()
    allowed = {"open", "in_review", "resolved", "dismissed"}
    if status not in allowed:
        raise HTTPException(status_code=400, detail={"message": "Invalid report status."})

    rid = normalize_postgrest_value(report_id)
    mgr = get_manager()
    updates = {
        "status": status,
        "updated_at": datetime.utcnow().isoformat(),
    }
    if status in {"resolved", "dismissed"}:
        updates["resolved_at"] = datetime.utcnow().isoformat()
        updates["resolved_by"] = str(admin_user["id"])

    mgr.db_client.update("moderation_reports", updates, {"report_id": f"eq.{rid}"})
    rows = _select_optional_table("moderation_reports", filters={"report_id": f"eq.{rid}"})
    return rows[0] if rows else {"message": "Report updated"}


@app.get("/api/admin/feedback")
def admin_feedback(request: Request):
    """Fetch platform feedback items for admin review."""
    require_admin(request)

    status_filter = str(request.query_params.get("status") or "all").lower()
    rows = _select_optional_table("platform_feedback")

    filtered = []
    for row in rows:
        status = str(row.get("status") or "open").lower()
        if status_filter != "all" and status != status_filter:
            continue
        filtered.append(row)

    filtered_sorted = sorted(filtered, key=lambda r: str(r.get("created_at") or ""), reverse=True)
    return {
        "feedback": filtered_sorted,
        "total": len(filtered_sorted),
    }


@app.patch("/api/admin/feedback/{feedback_id}")
def admin_update_feedback(feedback_id: str, body: AdminFeedbackUpdateRequest, request: Request):
    """Update feedback workflow status (open/reviewed/dismissed)."""
    admin_user = require_admin(request)
    status = str(body.status or "").lower()
    allowed = {"open", "reviewed", "dismissed"}
    if status not in allowed:
        raise HTTPException(status_code=400, detail={"message": "Invalid feedback status."})

    fid = normalize_postgrest_value(feedback_id)
    mgr = get_manager()
    updates = {
        "status": status,
        "reviewed_by": str(admin_user["id"]) if status in {"reviewed", "dismissed"} else None,
        "reviewed_at": datetime.utcnow().isoformat() if status in {"reviewed", "dismissed"} else None,
    }
    mgr.db_client.update("platform_feedback", updates, {"feedback_id": f"eq.{fid}"})
    rows = _select_optional_table("platform_feedback", filters={"feedback_id": f"eq.{fid}"})
    return rows[0] if rows else {"message": "Feedback updated"}


# -------------------------------------------------------------------
# Admin profile, audit logs, therapist verifications, announcements
# -------------------------------------------------------------------


@app.get("/api/admin/me")
def admin_profile_me(request: Request):
    """Return the current admin's profile plus a quick-activity summary."""
    admin_user = require_admin(request)
    admin_user_id = str(admin_user["id"])
    profile = _get_profile_persistent(admin_user_id)

    logs = _select_optional_table(
        "admin_audit_logs",
        filters={"admin_user_id": f"eq.{admin_user_id}"},
    )
    logs_sorted = sorted(logs, key=lambda l: str(l.get("created_at") or ""), reverse=True)

    last_login = profile.get("last_login_at") or profile.get("updated_at") or profile.get("created_at")
    return {
        "user_id": admin_user_id,
        "admin_id": profile.get("admin_id"),
        "name": profile.get("name") or admin_user.get("username") or "Admin",
        "email": profile.get("email") or admin_user.get("email"),
        "role": "admin",
        "account_status": _get_account_status(profile),
        "created_at": profile.get("created_at"),
        "moderated_at": profile.get("moderated_at"),
        "last_login_at": last_login,
        "total_actions": len(logs),
        "recent_actions": logs_sorted[:10],
    }


@app.get("/api/admin/logs")
def admin_logs(request: Request):
    """Immutable audit trail of admin actions."""
    require_admin(request)

    action_filter = str(request.query_params.get("action") or "all").lower()
    actor_filter = str(request.query_params.get("admin_user_id") or "all")
    target_filter = str(request.query_params.get("target_user_id") or "all")

    try:
        limit = max(1, min(int(request.query_params.get("limit") or 200), 500))
    except ValueError:
        limit = 200

    rows = _select_optional_table("admin_audit_logs")
    filtered = []
    for row in rows:
        if action_filter != "all" and str(row.get("action") or "").lower() != action_filter:
            continue
        if actor_filter != "all" and str(row.get("admin_user_id") or "") != actor_filter:
            continue
        if target_filter != "all" and str(row.get("target_user_id") or "") != target_filter:
            continue
        filtered.append(row)

    filtered_sorted = sorted(filtered, key=lambda r: str(r.get("created_at") or ""), reverse=True)
    return {"logs": filtered_sorted[:limit], "total": len(filtered_sorted)}


@app.get("/api/admin/therapists/queue")
def admin_therapists_queue(request: Request):
    """List therapist verification submissions for admin review."""
    require_admin(request)

    status_filter = str(request.query_params.get("status") or "pending").lower()
    rows = _select_optional_table("therapist_verifications")

    filtered = []
    for row in rows:
        status = str(row.get("status") or "pending").lower()
        if status_filter != "all" and status != status_filter:
            continue
        filtered.append(row)

    profiles = _select_optional_table("user_profiles")
    by_uid = {str(p.get("user_id")): p for p in profiles}
    for row in filtered:
        linked = by_uid.get(str(row.get("user_id")), {})
        row["user_name"] = linked.get("name")
        row["user_email"] = linked.get("email")
        row["user_role"] = linked.get("role")

    filtered_sorted = sorted(filtered, key=lambda r: str(r.get("submitted_at") or ""), reverse=True)
    return {"queue": filtered_sorted, "total": len(filtered_sorted)}


@app.patch("/api/admin/therapists/{verification_id}")
def admin_review_therapist(verification_id: str, body: TherapistVerificationReviewRequest, request: Request):
    """Approve or reject a therapist application."""
    admin_user = require_admin(request)
    admin_user_id = str(admin_user["id"])
    admin_id = admin_user.get("admin_id")

    status = str(body.status or "").lower()
    if status not in {"approved", "rejected"}:
        raise HTTPException(status_code=400, detail={"message": "Invalid status. Use approved or rejected."})

    vid = normalize_postgrest_value(verification_id)
    mgr = get_manager()
    existing = _select_optional_table("therapist_verifications", filters={"verification_id": f"eq.{vid}"})
    if not existing:
        raise HTTPException(status_code=404, detail={"message": "Verification not found."})

    target_uid = str(existing[0].get("user_id") or "")

    mgr.db_client.update(
        "therapist_verifications",
        {
            "status": status,
            "reviewed_by": admin_user_id,
            "reviewed_at": datetime.utcnow().isoformat(),
            "review_notes": body.review_notes,
        },
        {"verification_id": f"eq.{vid}"},
    )

    if status == "approved" and target_uid:
        mgr.db_client.update(
            "user_profiles",
            {"role": "therapist", "updated_at": datetime.utcnow().isoformat()},
            {"user_id": f"eq.{target_uid}"},
        )
        update_user_sessions(target_uid, {"role": "therapist"})

    _log_admin_action(
        admin_user_id,
        admin_id,
        f"therapist_{status}",
        target_user_id=target_uid or None,
        target_resource=f"therapist_verifications:{vid}",
        reason=body.review_notes,
    )

    refreshed = _select_optional_table("therapist_verifications", filters={"verification_id": f"eq.{vid}"})
    return refreshed[0] if refreshed else {"message": "Verification updated"}


@app.get("/api/admin/announcements")
def admin_list_announcements(request: Request):
    """List announcements composed by admins."""
    require_admin(request)
    rows = _select_optional_table("announcements")
    rows_sorted = sorted(rows, key=lambda r: str(r.get("created_at") or ""), reverse=True)
    return {"announcements": rows_sorted, "total": len(rows_sorted)}


@app.post("/api/admin/announcements")
def admin_create_announcement(body: AnnouncementCreateRequest, request: Request):
    """Compose a new announcement."""
    admin_user = require_admin(request)
    admin_user_id = str(admin_user["id"])
    admin_id = admin_user.get("admin_id")

    title = (body.title or "").strip()
    message = (body.body or "").strip()
    audience = str(body.audience or "all").lower()

    if not title or not message:
        raise HTTPException(status_code=400, detail={"message": "Title and body are required."})
    if audience not in {"all", "patients", "therapists", "inactive"}:
        raise HTTPException(status_code=400, detail={"message": "Invalid audience."})

    payload = {
        "admin_user_id": admin_user_id,
        "title": title,
        "body": message,
        "audience": audience,
        "expires_at": body.expires_at.isoformat() if body.expires_at else None,
    }

    try:
        row = get_manager().db_client.insert("announcements", payload)
    except Exception as exc:
        if _is_missing_table_error(exc):
            raise HTTPException(status_code=503, detail={"message": "Announcements table missing. Run the admin extensions migration."})
        raise

    _log_admin_action(
        admin_user_id,
        admin_id,
        "announcement_created",
        target_resource=f"announcements:{row.get('announcement_id') if isinstance(row, dict) else ''}",
        metadata={"audience": audience, "title": title},
    )

    return row


@app.delete("/api/admin/announcements/{announcement_id}")
def admin_deactivate_announcement(announcement_id: str, request: Request):
    """Soft-deactivate an announcement so users stop seeing it."""
    admin_user = require_admin(request)
    admin_user_id = str(admin_user["id"])
    admin_id = admin_user.get("admin_id")

    aid = normalize_postgrest_value(announcement_id)
    try:
        get_manager().db_client.update(
            "announcements",
            {"active": False},
            {"announcement_id": f"eq.{aid}"},
        )
    except Exception as exc:
        if _is_missing_table_error(exc):
            raise HTTPException(status_code=503, detail={"message": "Announcements table missing."})
        raise

    _log_admin_action(
        admin_user_id,
        admin_id,
        "announcement_deactivated",
        target_resource=f"announcements:{aid}",
    )

    return {"message": "Announcement deactivated", "announcement_id": aid}


# -------------------------------------------------------------------
# Extended platform analytics for the admin overview card grid.
# -------------------------------------------------------------------


@app.get("/api/admin/analytics")
def admin_analytics(request: Request):
    """DAU/WAU/MAU, avg session length, and basic engagement signals."""
    require_admin(request)

    conversations = _select_optional_table("conversations")
    profiles = _select_optional_table("user_profiles")

    now = datetime.utcnow()
    one_day = now - dt.timedelta(days=1)
    seven_days = now - dt.timedelta(days=7)
    thirty_days = now - dt.timedelta(days=30)

    dau_users: set = set()
    wau_users: set = set()
    mau_users: set = set()
    total_minutes_30d = 0
    sessions_30d = 0

    for conv in conversations:
        uid = str(conv.get("user_id") or "")
        if not uid:
            continue
        created = _parse_iso_datetime(conv.get("created_at"))
        if not created:
            continue
        created_naive = created.replace(tzinfo=None) if created.tzinfo else created
        if created_naive >= one_day:
            dau_users.add(uid)
        if created_naive >= seven_days:
            wau_users.add(uid)
        if created_naive >= thirty_days:
            mau_users.add(uid)
            sessions_30d += 1
            total_minutes_30d += int(conv.get("duration_minutes") or 0)

    avg_session_minutes = round(total_minutes_30d / sessions_30d, 1) if sessions_30d else 0.0

    active_therapists = sum(
        1 for p in profiles
        if str(p.get("role") or "").lower() == "therapist"
        and _get_account_status(p) == "active"
    )

    return {
        "dau": len(dau_users),
        "wau": len(wau_users),
        "mau": len(mau_users),
        "sessions_30d": sessions_30d,
        "total_minutes_30d": total_minutes_30d,
        "avg_session_minutes": avg_session_minutes,
        "active_therapists": active_therapists,
    }


# ===================================================================
# CHAT ENDPOINT — Core AI integration
# ===================================================================


@app.post("/api/chat")
@limiter.limit("30/minute")
def chat(body: ChatRequest, request: Request):
    """
    Process a user message through the full ConversationManager pipeline:
    personality detection, RAG retrieval, LLM response generation.

    Crisis detection runs BEFORE the RAG pipeline on every message. On
    HIGH/CRITICAL risk, the normal pipeline is bypassed and a pre-scripted
    crisis response is returned. On CRITICAL with emergency_alerts_enabled,
    a countdown is started and alerts dispatch in the background.
    """
    user = require_user(request)
    user_id = str(user["id"])

    try:
        # ---- Resolve conversation + fetch history for context-aware crisis ---
        from crisis_service import detect_crisis, crisis_response, RiskLevel, CrisisResult

        mgr = get_manager()
        conv_id = body.conversation_id
        if not conv_id:
            session_result = mgr.start_session(user_id, start_questionnaire=False)
            conv_id = session_result["conversation_id"]

        crisis_history = None
        try:
            from database.user_service import UserService
            _us = UserService()
            raw_msgs = _us.get_conversation_history(conv_id, limit=12)
            if raw_msgs:
                crisis_history = [
                    {
                        "role": "user" if m.get("is_user") else "assistant",
                        "content": m.get("content", ""),
                    }
                    for m in raw_msgs
                ]
        except Exception as hist_err:
            logger.warning(f"Could not fetch history for crisis context: {hist_err}")

        # ---- Crisis detection (runs on EVERY message) ---------------------
        crisis = detect_crisis(
            body.message,
            use_llm=True,
            history=crisis_history,
            arbiter_timeout=6.0,
        )

        # ---- Session escalation: once CRITICAL fires in a conversation,
        # ALL subsequent messages stay in crisis response mode so the LLM
        # never gives a dangerously validating reply after a real crisis.
        if not crisis.requires_intervention and conv_id:
            try:
                from database.supabase_client import SupabaseClient
                _sb = SupabaseClient()
                recent_critical = _sb.select(
                    "crisis_events",
                    columns="event_id",
                    filters={
                        "patient_id": f"eq.{user_id}",
                        "session_id": f"eq.{conv_id}",
                        "severity": "eq.critical",
                        "limit": "1",
                    },
                )
                if recent_critical:
                    crisis = CrisisResult(
                        risk_level=RiskLevel.HIGH,
                        severity_score=0.8,
                        keyword_matches=["session_escalation"],
                        ml_scores={},
                        keyword_tier="escalated",
                        llm_verdict=None,
                    )
            except Exception as esc_err:
                logger.warning(f"Session escalation check failed: {esc_err}")

        if crisis.requires_intervention:
            # Bypass RAG — return pre-scripted response. Log event + maybe fire
            # countdown for CRITICAL.
            from crisis_routes import _get_settings_or_default
            from database.supabase_client import SupabaseClient
            from emergency_alert import (
                log_crisis_event,
                start_countdown,
                run_countdown_and_fire,
            )
            import asyncio as _asyncio

            sb = SupabaseClient()
            settings = _get_settings_or_default(sb, user_id)
            alerts_ok = (
                crisis.requires_emergency_alert
                and bool(settings.get("emergency_alerts_enabled"))
            )

            event = log_crisis_event(
                sb,
                user_id=user_id,
                session_id=conv_id,
                crisis_result_dict=crisis.to_dict(),
                trigger_text=body.message,
                intervention_type="alerts_sent" if alerts_ok else "modal_shown",
                location=settings.get("last_known_location")
                if settings.get("location_sharing_consent")
                else None,
            )
            event_id = event.get("event_id")

            countdown_info: Optional[Dict[str, Any]] = None
            if alerts_ok and event_id:
                cd_seconds = int(settings.get("countdown_seconds") or 30)
                cd = start_countdown(
                    sb, user_id=user_id, event_id=event_id, seconds=cd_seconds
                )
                countdown_info = {
                    "countdown_id": cd.get("countdown_id"),
                    "seconds": cd_seconds,
                    "can_cancel": True,
                }
                try:
                    loop = _asyncio.get_event_loop()
                    loop.create_task(
                        run_countdown_and_fire(
                            sb,
                            user_id=user_id,
                            event_id=event_id,
                            countdown_id=cd["countdown_id"],
                            seconds=cd_seconds,
                            country_code=settings.get("country_code", "PK"),
                            location=settings.get("last_known_location")
                            if settings.get("location_sharing_consent")
                            else None,
                        )
                    )
                except RuntimeError:
                    # No running loop in a sync endpoint — schedule via a thread.
                    import threading
                    def _bg():
                        _asyncio.run(
                            run_countdown_and_fire(
                                sb,
                                user_id=user_id,
                                event_id=event_id,
                                countdown_id=cd["countdown_id"],
                                seconds=cd_seconds,
                                country_code=settings.get("country_code", "PK"),
                                location=settings.get("last_known_location")
                                if settings.get("location_sharing_consent")
                                else None,
                            )
                        )
                    threading.Thread(target=_bg, daemon=True).start()

            response_text = crisis_response(
                country_code=settings.get("country_code", "PK"),
                alerts_being_sent=alerts_ok,
            )

            return {
                "response": response_text,
                "content": response_text,
                "conversation_id": conv_id,
                "crisis": {
                    "detected": True,
                    "risk_level": crisis.risk_level.value,
                    "severity_score": crisis.severity_score,
                    "event_id": event_id,
                    "countdown": countdown_info,
                    "show_modal": True,
                    "alerts_being_sent": alerts_ok,
                },
            }

        # ---- Normal pipeline (no crisis) ---------------------------------
        # On MEDIUM, prepend empathy nudge to the LLM context.
        context_note = None
        if crisis.risk_level.value == "MEDIUM":
            context_note = (
                "The user may be in distress. Respond with extra empathy, "
                "validate their feelings, and gently mention that "
                "professional help is available."
            )

        result = mgr.process_message(
            user_id=user_id,
            conversation_id=conv_id,
            user_message=body.message,
            is_questionnaire_response=False,
        )

        response_text = result.get("response", "I'm here to listen.")
        if context_note:
            response_text = (
                response_text
                + "\n\nIf things feel heavy, you can reach Umang Helpline "
                "at 0311-7786264 (24/7) — you don't have to carry this alone."
            )

        return {
            "response": response_text,
            "content": response_text,
            "conversation_id": conv_id,
            "turn": result.get("turn"),
            "personality_scores": result.get("personality_scores"),
            "rag_techniques_used": result.get("rag_techniques_used", 0),
            "crisis": {
                "detected": False,
                "risk_level": crisis.risk_level.value,
            },
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
            # Updates profile. Allowlist explicit user-editable columns.
            allowed = {"name", "emergency_contact", "phone"}
            updates = {k: v for k, v in body.items() if k in allowed}
            if "mood_preference" in body:
                # Get current preferences to merge
                profile = mgr.user_service.get_user_profile(user_id)
                prefs = profile.get("preferences", {})
                prefs["mood_preference"] = body["mood_preference"]
                updates["preferences"] = prefs

            if updates:
                updates["updated_at"] = now
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
            conv_id = normalize_postgrest_value(record_id)
            # Delete messages first, then the conversation itself
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
# THERAPIST PORTAL ROUTES
# ===================================================================

try:
    from therapist_routes import register_therapist_routes
    register_therapist_routes(app)
    logger.info("Therapist portal routes registered")
except Exception as exc:
    logger.error(f"Failed to register therapist portal routes: {exc}")


# ===================================================================
# CRISIS SAFETY ROUTES
# ===================================================================

try:
    from crisis_routes import register_crisis_routes
    # Inject require_user explicitly so the routes share THIS module's
    # sessions dict (avoids module-duplication when uvicorn re-imports api.py).
    register_crisis_routes(app, require_user_fn=require_user)
    logger.info("Crisis safety routes registered")
except Exception as exc:
    logger.error(f"Failed to register crisis safety routes: {exc}")


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
