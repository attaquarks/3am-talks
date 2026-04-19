import os
from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")

class Config:
    """Central configuration for 3AM Talks."""
    SUPABASE_URL = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
    PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "")
    SESSION_SECRET = os.getenv("SESSION_SECRET", "")
    ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

    # Conversation persistence controls.
    # Modes:
    # - immediate: current behavior (write every turn synchronously)
    # - buffered: enqueue writes and flush in batches/end-session
    CONVERSATION_PERSISTENCE_MODE = os.getenv(
        "CONVERSATION_PERSISTENCE_MODE", "buffered"
    ).strip().lower()
    CONVERSATION_FLUSH_INTERVAL_SECONDS = int(
        os.getenv("CONVERSATION_FLUSH_INTERVAL_SECONDS", "20")
    )
    CONVERSATION_FLUSH_TURN_THRESHOLD = int(
        os.getenv("CONVERSATION_FLUSH_TURN_THRESHOLD", "2")
    )

config = Config()
