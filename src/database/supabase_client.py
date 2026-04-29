import os
from typing import Optional
import httpx
import logging
from dotenv import load_dotenv
from pathlib import Path

logger = logging.getLogger(__name__)
ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")


def normalize_postgrest_value(value: Optional[str]) -> str:
    """
    Strip PostgREST-style 'eq.' prefixes from filter values.

    The frontend sometimes sends values like 'eq.<uuid>' or 'eq.eq.<uuid>';
    code that prepends another 'eq.' must normalize first to avoid invalid
    queries (e.g. conversation_id=eq.eq.<uuid>).
    """
    if value is None:
        return ""
    v = str(value).strip()
    while v.startswith("eq."):
        v = v[3:].strip()
    return v


class SupabaseClient:
    """Client for interacting with Supabase database"""
    
    def __init__(self):
        self.url = os.getenv("SUPABASE_URL")
        self.key = os.getenv("SUPABASE_KEY")
        
        if not self.url or not self.key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in .env file")
        
        self.headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }
        
        # Use a longer timeout and automatic retries for production stability
        self.client = httpx.Client(
            timeout=60.0,
            transport=httpx.HTTPTransport(retries=3)
        )
        logger.info("Supabase client initialized")
    
    def _build_url(self, table: str) -> str:
        """Build the REST API URL for a table"""
        return f"{self.url}/rest/v1/{table}"
    
    def select(self, table: str, columns: str = "*", filters: Optional[dict] = None) -> dict:
        """
        Select data from a table
        
        Args:
            table: Table name
            columns: Columns to select (default "*")
            filters: Dictionary of filters e.g., {"user_id": "eq.123"}
        """
        url = self._build_url(table)
        params = {"select": columns}
        
        if filters:
            params.update(filters)
        
        try:
            response = self.client.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error selecting from {table}: {e}")
            raise
    
    def insert(self, table: str, data: dict) -> dict:
        """Insert data into a table"""
        url = self._build_url(table)
        
        try:
            response = self.client.post(url, headers=self.headers, json=data)
            response.raise_for_status()
            result = response.json()
            return result[0] if isinstance(result, list) and len(result) > 0 else result
        except Exception as e:
            if isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 409:
                logger.debug(f"Conflict inserting into {table}: {e}")
            elif isinstance(e, httpx.HTTPStatusError):
                body = (e.response.text or "")[:1500]
                logger.error(
                    "Error inserting into %s: %s | response=%s",
                    table,
                    e,
                    body,
                )
            else:
                logger.error(f"Error inserting into {table}: {e}")
            raise

    def insert_many(self, table: str, rows: list[dict]) -> list[dict]:
        """Insert multiple rows into a table in one request."""
        if not rows:
            return []

        url = self._build_url(table)

        try:
            response = self.client.post(url, headers=self.headers, json=rows)
            response.raise_for_status()
            result = response.json()
            return result if isinstance(result, list) else [result]
        except Exception as e:
            if isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 409:
                logger.debug(f"Conflict inserting batch into {table}: {e}")
            elif isinstance(e, httpx.HTTPStatusError):
                body = (e.response.text or "")[:1500]
                logger.error(
                    "Error inserting batch into %s: %s | response=%s",
                    table,
                    e,
                    body,
                )
            else:
                logger.error(f"Error inserting batch into {table}: {e}")
            raise
    
    def update(self, table: str, data: dict, filters: dict) -> dict:
        """Update data in a table"""
        url = self._build_url(table)
        
        try:
            response = self.client.patch(
                url, 
                headers=self.headers, 
                json=data,
                params=filters
            )
            response.raise_for_status()
            result = response.json()
            return result[0] if isinstance(result, list) and len(result) > 0 else result
        except Exception as e:
            if isinstance(e, httpx.HTTPStatusError):
                body = (e.response.text or "")[:1500]
                logger.error(
                    "Error updating %s: %s | response=%s",
                    table,
                    e,
                    body,
                )
            else:
                logger.error(f"Error updating {table}: {e}")
            raise
    
    def delete(self, table: str, filters: dict) -> dict:
        """Delete data from a table"""
        url = self._build_url(table)
        
        try:
            response = self.client.delete(
                url,
                headers=self.headers,
                params=filters
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error deleting from {table}: {e}")
            raise
    
    def rpc(self, function_name: str, params: dict = None) -> dict:
        """Call a Supabase RPC function"""
        url = f"{self.url}/rest/v1/rpc/{function_name}"
        
        try:
            response = self.client.post(
                url,
                headers=self.headers,
                json=params or {}
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error calling RPC {function_name}: {e}")
            raise
    
    def sign_up(self, email: str, password: str) -> dict:
        """Register a new user with Supabase Auth"""
        url = f"{self.url}/auth/v1/signup"
        try:
            response = self.client.post(
                url,
                headers=self.headers,
                json={"email": email, "password": password}
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            body = e.response.text[:500] if e.response is not None else "<no body>"
            logger.error(
                f"Sign up failed: HTTP {e.response.status_code} — Supabase said: {body}"
            )
            raise
        except Exception as e:
            logger.error(f"Sign up failed: {e}")
            raise

    def sign_in(self, email: str, password: str) -> dict:
        """Authenticate an existing user"""
        url = f"{self.url}/auth/v1/token?grant_type=password"
        try:
            response = self.client.post(
                url,
                headers=self.headers,
                json={"email": email, "password": password}
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            body = e.response.text[:500] if e.response is not None else "<no body>"
            logger.error(
                f"Sign in failed: HTTP {e.response.status_code} — Supabase said: {body}"
            )
            raise
        except Exception as e:
            logger.error(f"Sign in failed: {e}")
            raise

    def admin_update_user(self, user_id: str, attributes: dict) -> dict:
        """Update a Supabase Auth user via Admin API (requires service role key)."""
        url = f"{self.url}/auth/v1/admin/users/{user_id}"
        try:
            response = self.client.put(url, headers=self.headers, json=attributes)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Admin update user failed: {e}")
            raise

    def admin_delete_user(self, user_id: str, should_soft_delete: bool = False) -> dict:
        """Delete a Supabase Auth user via Admin API (requires service role key)."""
        url = f"{self.url}/auth/v1/admin/users/{user_id}"
        params = {"should_soft_delete": "true" if should_soft_delete else "false"}
        try:
            response = self.client.delete(url, headers=self.headers, params=params)
            response.raise_for_status()
            if response.text:
                return response.json()
            return {"success": True}
        except Exception as e:
            logger.error(f"Admin delete user failed: {e}")
            raise

    def close(self):
        """Close the HTTP client"""
        self.client.close()
