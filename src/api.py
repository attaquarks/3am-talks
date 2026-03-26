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
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("3am-api")

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


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    conversation_history: Optional[List[dict]] = None


class DataBody(BaseModel):
    """Generic body for CRUD data endpoints."""

    model_config = {"extra": "allow"}


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


def create_session(user_data: dict, response: Response) -> str:
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
        return mgr.db_client.insert("user_stats", new_stats)
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
    """Mock social login — creates a local session. NOT persistent across server restarts/machines unless matched by email."""
    # TODO: Implement real social auth via Supabase
    user_id = str(uuid.uuid4())
    user_data = {
        "id": user_id,
        "username": body.name,
        "email": body.email,
        "createdAt": datetime.utcnow().isoformat(),
        "provider": body.provider,
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
            conv = mgr.user_service.get_conversation(record_id)
            if not conv:
                raise HTTPException(status_code=404, detail="Conversation not found")
            return _backend_conversation_to_frontend(conv)

        elif table == "messages":
            msgs = mgr.user_service.get_conversation_history(record_id)
            return [_backend_message_to_frontend(m) for m in msgs]

        elif table == "profiles":
            profile = _get_profile_persistent(user_id)
            return profile

        elif table == "user_stats":
            stats = _get_stats_persistent(user_id)
            return stats

        elif table == "mood_entries":
            entries = mgr.db_client.select("mood_entries", filters={"id": f"eq.{record_id}", "user_id": f"eq.{user_id}"})
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
            return mgr.db_client.insert("user_stats", data)

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
            updates = {k: v for k, v in body.items() if k in ["is_active", "duration_minutes", "title", "mood", "summary", "tags"]}
            if updates:
                mgr.db_client.update("conversations", updates, {"conversation_id": f"eq.{record_id}"})
            
            # Return current state
            conv = mgr.user_service.get_conversation(record_id)
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
            updates = {k: v for k, v in body.items() if k in ["mood", "note", "prompt", "prompt_answer"]}
            if updates:
                updates["updated_at"] = now
                mgr.db_client.update("mood_entries", updates, {"id": f"eq.{record_id}", "user_id": f"eq.{user_id}"})
            
            # Fetch updated
            entries = mgr.db_client.select("mood_entries", filters={"id": f"eq.{record_id}"})
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
            mgr.end_session(record_id)
            return {"message": "Conversation ended"}

        elif table == "profiles":
            # Soft delete? Or hard delete? "deleted" field suggests soft.
            mgr.db_client.update("user_profiles", {"deleted": True}, {"user_id": f"eq.{user_id}"})
            return {"message": "Profile deleted"}

        elif table == "user_stats":
            mgr.db_client.delete("user_stats", {"user_id": f"eq.{user_id}"})
            return {"message": "Stats deleted"}

        elif table == "mood_entries":
            mgr.db_client.delete("mood_entries", {"id": f"eq.{record_id}", "user_id": f"eq.{user_id}"})
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

        room_name = f"ella-voice-{uuid.uuid4().hex[:8]}"

        token = (
            lk_api.AccessToken(api_key=lk_api_key, api_secret=lk_api_secret)
            .with_identity(f"user-{user_id[:8]}")
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
        "api:app",
        host="0.0.0.0",
        port=5050,
        reload=True,
        log_level="info",
    )
