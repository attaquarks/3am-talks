"""
routes/ — FastAPI route modules for 3AM Talks API.

Each module registers its own APIRouter which is included in main.py.
"""
from .auth import router as auth_router
from .chat import router as chat_router
from .user import router as user_router
from .admin import router as admin_router
from .crisis import router as crisis_router
from .therapist import router as therapist_router
from .voice import router as voice_router
from .data import router as data_router

__all__ = [
    "auth_router",
    "chat_router",
    "user_router",
    "admin_router",
    "crisis_router",
    "therapist_router",
    "voice_router",
    "data_router",
]
