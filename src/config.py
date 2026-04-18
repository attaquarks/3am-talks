import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Central configuration for 3AM Talks."""
    SUPABASE_URL = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
    PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "")
    SESSION_SECRET = os.getenv("SESSION_SECRET", "")
    ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

config = Config()
