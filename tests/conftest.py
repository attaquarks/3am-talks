"""Shared test fixtures. Loads .env so tests that import src/ modules
(which touch SESSION_SECRET, SUPABASE_*, etc. at import time) don't crash."""
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT / "src"))
