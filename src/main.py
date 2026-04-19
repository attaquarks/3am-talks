"""
3AM Talks (ELLA AI) — FastAPI Server
Entry Point
"""
import json
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

import sys

# ---------------------------------------------------------------------------
# Environment & path setup
# ---------------------------------------------------------------------------
load_dotenv()

SRC_DIR = Path(__file__).parent
ROOT_DIR = SRC_DIR.parent
sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(ROOT_DIR))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("3am-api")

# Ensure core lazy manager is available
from core.helpers import _conversation_manager
from core import limiter
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

# Import all routers
from routes import (
    auth_router,
    chat_router,
    user_router,
    admin_router,
    crisis_router,
    therapist_router,
    therapist_shared_router,
    voice_router,
)
from routes.data import router as data_router

# ---------------------------------------------------------------------------
# Lifespan — startup & shutdown
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("3AM Talks API starting on port 5050")
    logger.info("Frontend expected at http://localhost:5173")
    
    # #region agent log
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
    if _conversation_manager is not None:
        try:
            _conversation_manager.close()
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

# Rate limiting (slowapi)
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

# Register route modules
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(user_router)
app.include_router(admin_router)
app.include_router(crisis_router)
app.include_router(therapist_router)
app.include_router(therapist_shared_router)
app.include_router(voice_router)
app.include_router(data_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=5050, reload=True)
