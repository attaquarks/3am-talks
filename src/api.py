"""
3AM Talks (ELLA AI) — FastAPI Server
Bridges the React frontend with the Python backend ConversationManager.
Runs on port 5050. Frontend expects all endpoints under /api/*.
"""

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
# In-memory stores for tables the backend doesn't have yet
# These can be migrated to Supabase tables later.
# ---------------------------------------------------------------------------
profiles_store: Dict[str, dict] = {}       # keyed by user_id
user_stats_store: Dict[str, dict] = {}     # keyed by user_id
mood_entries_store: Dict[str, list] = {}   # keyed by user_id -> list of entries

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
                ollama_base_url="http://127.0.0.1:11434",
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
# In-memory store helpers
# ---------------------------------------------------------------------------

def _ensure_profile(user_id: str, name: str = "User") -> dict:
    """Ensure a profile exists for the user in the in-memory store."""
    if user_id not in profiles_store:
        now = datetime.utcnow().isoformat()
        profiles_store[user_id] = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "name": name,
            "mood_preference": "neutral",
            "deleted": False,
            "created_at": now,
            "updated_at": now,
        }
    return profiles_store[user_id]


def _ensure_stats(user_id: str) -> dict:
    """Ensure user stats exist in the in-memory store."""
    if user_id not in user_stats_store:
        now = datetime.utcnow().isoformat()
        user_stats_store[user_id] = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "current_streak": 0,
            "total_sessions": 0,
            "total_minutes": 0,
            "mood_improvement_percentage": 0,
            "last_session_date": None,
            "created_at": now,
            "updated_at": now,
        }
    return user_stats_store[user_id]


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
    """Register a new user via Supabase Auth, create profile, start session."""
    try:
        mgr = get_manager()
        result = mgr.register_user(body.email, body.password)
        user_id = result["user_id"]

        # Build user object matching frontend User interface
        user_data = {
            "id": user_id,
            "username": body.name,
            "email": body.email,
            "createdAt": datetime.utcnow().isoformat(),
        }

        # Create in-memory profile and stats
        _ensure_profile(user_id, body.name)
        _ensure_stats(user_id)

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

        user_data = {
            "id": user_id,
            "username": body.email.split("@")[0],
            "email": body.email,
            "createdAt": datetime.utcnow().isoformat(),
        }

        # Ensure in-memory stores exist
        _ensure_profile(user_id)
        _ensure_stats(user_id)

        create_session(user_data, response)
        return user_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login failed: {e}")
        raise HTTPException(status_code=401, detail={"message": str(e)})


@app.post("/api/auth/social")
def social_login(body: SocialLoginRequest, response: Response):
    """Mock social login — creates a local session without Supabase Auth."""
    user_id = str(uuid.uuid4())
    user_data = {
        "id": user_id,
        "username": body.name,
        "email": body.email,
        "createdAt": datetime.utcnow().isoformat(),
        "provider": body.provider,
    }

    _ensure_profile(user_id, body.name)
    _ensure_stats(user_id)

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
    """Clear the session cookie and remove the server-side session."""
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

    This is the endpoint that replaces supabase.functions.invoke('ai-chat').
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
# Handles: conversations, messages, profiles, mood_entries, user_stats
# Translates between frontend and backend schemas.
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
        "updated_at": conv.get("updated_at", conv.get("created_at", datetime.utcnow().isoformat())),
    }


def _backend_message_to_frontend(msg: dict) -> dict:
    """Translate backend message schema (role) to frontend schema (is_user)."""
    return {
        "id": msg.get("message_id", msg.get("id", "")),
        "conversation_id": msg.get("conversation_id", ""),
        "content": msg.get("content", ""),
        "is_user": msg.get("role") == "user" if "role" in msg else msg.get("is_user", False),
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
            # Fetch all conversations for this user from Supabase
            convs = mgr.user_service.db.select(
                "conversations",
                filters={"user_id": f"eq.{user_id}"},
            )
            return [_backend_conversation_to_frontend(c) for c in convs]

        elif table == "messages":
            # Messages need a conversation_id filter from query params
            conv_id = request.query_params.get("conversation_id")
            if not conv_id:
                return []
            mgr = get_manager()
            msgs = mgr.user_service.get_conversation_history(conv_id)
            return [_backend_message_to_frontend(m) for m in msgs]

        elif table == "profiles":
            profile = _ensure_profile(user_id)
            return profile

        elif table == "user_stats":
            stats = _ensure_stats(user_id)
            return stats

        elif table == "mood_entries":
            entries = mood_entries_store.get(user_id, [])
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
        if table == "conversations":
            mgr = get_manager()
            conv = mgr.user_service.get_conversation(record_id)
            if not conv:
                raise HTTPException(status_code=404, detail="Conversation not found")
            return _backend_conversation_to_frontend(conv)

        elif table == "messages":
            mgr = get_manager()
            msgs = mgr.user_service.get_conversation_history(record_id)
            return [_backend_message_to_frontend(m) for m in msgs]

        elif table == "profiles":
            profile = _ensure_profile(user_id)
            return profile

        elif table == "user_stats":
            stats = _ensure_stats(user_id)
            return stats

        elif table == "mood_entries":
            entries = mood_entries_store.get(user_id, [])
            entry = next((e for e in entries if e["id"] == record_id), None)
            if not entry:
                raise HTTPException(status_code=404, detail="Mood entry not found")
            return entry

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

    try:
        if table == "conversations":
            mgr = get_manager()
            # Start a new session via ConversationManager
            session_result = mgr.start_session(user_id, start_questionnaire=False)
            conv_id = session_result["conversation_id"]

            # Fetch the created conversation and merge frontend fields
            conv = mgr.user_service.get_conversation(conv_id) or {}
            frontend_conv = _backend_conversation_to_frontend(conv)
            # Apply any frontend-specific fields from the request body
            frontend_conv["title"] = body.get("title", frontend_conv.get("title"))
            frontend_conv["mood"] = body.get("mood", frontend_conv.get("mood"))
            frontend_conv["tags"] = body.get("tags", frontend_conv.get("tags"))
            frontend_conv["duration_minutes"] = body.get("duration_minutes", 0)
            return frontend_conv

        elif table == "messages":
            mgr = get_manager()
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
            profile = _ensure_profile(user_id, body.get("name", "User"))
            profile.update({
                k: v for k, v in body.items()
                if k in ("name", "mood_preference")
            })
            profile["updated_at"] = now
            return profile

        elif table == "user_stats":
            stats = _ensure_stats(user_id)
            # Merge provided fields
            for key in ("current_streak", "total_sessions", "total_minutes",
                        "mood_improvement_percentage", "last_session_date"):
                if key in body:
                    stats[key] = body[key]
            stats["updated_at"] = now
            return stats

        elif table == "mood_entries":
            entry = {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "date": body.get("date", now[:10]),
                "mood": body.get("mood", "neutral"),
                "note": body.get("note"),
                "prompt": body.get("prompt"),
                "prompt_answer": body.get("prompt_answer"),
                "created_at": now,
                "updated_at": now,
            }
            mood_entries_store.setdefault(user_id, []).insert(0, entry)
            return entry

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

    try:
        if table == "conversations":
            mgr = get_manager()
            # Update frontend-specific fields — these live as extra metadata
            # For backend fields (is_active), proxy to Supabase
            backend_updates = {}
            if "is_active" in body:
                backend_updates["is_active"] = body["is_active"]
            if backend_updates:
                mgr.user_service.db.update(
                    "conversations",
                    backend_updates,
                    {"conversation_id": f"eq.{record_id}"},
                )
            # Return merged view
            conv = mgr.user_service.get_conversation(record_id) or {}
            result = _backend_conversation_to_frontend(conv)
            # Apply frontend-only updates
            for key in ("title", "mood", "summary", "tags", "duration_minutes"):
                if key in body:
                    result[key] = body[key]
            return result

        elif table == "profiles":
            profile = _ensure_profile(user_id)
            for key in ("name", "mood_preference", "deleted"):
                if key in body:
                    profile[key] = body[key]
            profile["updated_at"] = now
            return profile

        elif table == "user_stats":
            stats = _ensure_stats(user_id)
            for key in ("current_streak", "total_sessions", "total_minutes",
                        "mood_improvement_percentage", "last_session_date"):
                if key in body:
                    stats[key] = body[key]
            stats["updated_at"] = now
            return stats

        elif table == "mood_entries":
            entries = mood_entries_store.get(user_id, [])
            entry = next((e for e in entries if e["id"] == record_id), None)
            if not entry:
                raise HTTPException(status_code=404, detail="Mood entry not found")
            for key in ("mood", "note", "prompt", "prompt_answer"):
                if key in body:
                    entry[key] = body[key]
            entry["updated_at"] = now
            return entry

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

    try:
        if table == "conversations":
            mgr = get_manager()
            mgr.end_session(record_id)
            return {"message": "Conversation ended"}

        elif table == "profiles":
            profile = _ensure_profile(user_id)
            profile["deleted"] = True
            profile["updated_at"] = datetime.utcnow().isoformat()
            return {"message": "Profile deleted"}

        elif table == "user_stats":
            user_stats_store.pop(user_id, None)
            return {"message": "Stats deleted"}

        elif table == "mood_entries":
            entries = mood_entries_store.get(user_id, [])
            mood_entries_store[user_id] = [e for e in entries if e["id"] != record_id]
            return {"message": "Mood entry deleted"}

        else:
            raise HTTPException(status_code=404, detail=f"Unknown table: {table}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"DELETE /api/data/{table}/{record_id} failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
