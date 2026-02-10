import os
from typing import Optional
import httpx
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
load_dotenv()


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
            logger.error(f"Error inserting into {table}: {e}")
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
        except Exception as e:
            logger.error(f"Sign in failed: {e}")
            raise

    def close(self):
        """Close the HTTP client"""
        self.client.close()
