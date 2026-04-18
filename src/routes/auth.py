"""
routes/auth.py — Authentication endpoints.

Handles registration, login, social/OAuth flows, session management,
and account self-service (email, password, delete).
"""
from __future__ import annotations

import json
import logging
import os
import time
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from itsdangerous import BadSignature
from pydantic import BaseModel

from core import (
    SESSION_COOKIE,
    SESSION_MAX_AGE,
    signer,
    sessions,
    create_session,
    get_current_user,
    clear_user_sessions,
    update_user_sessions,
    get_manager,
    require_user,
    _get_profile_persistent,
    _get_stats_persistent,
    _get_account_status,
    _status_block_message,
    _build_session_user_payload,
)

logger = logging.getLogger("3am-auth")
router = APIRouter()

ROOT_DIR = Path(__file__).parent.parent.parent

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

# ---------------------------------------------------------------------------
# Pydantic models
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


class UpdateEmailRequest(BaseModel):
    new_email: str


class UpdatePasswordRequest(BaseModel):
    old_password: str
    new_password: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/api/register")
def register(body: RegisterRequest, response: Response):
    """Register a new user via Supabase Auth, create persistent profile and stats."""
    try:
        mgr = get_manager()
        result = mgr.register_user(body.email, body.password)
        user_id = result["user_id"]

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
                {"user_id": f"eq.{user_id}"},
            )
        except Exception as e:
            logger.warning(f"Could not set full profile defaults during register: {e}")
            try:
                mgr.db_client.update(
                    "user_profiles",
                    {"name": body.name, "updated_at": datetime.utcnow().isoformat()},
                    {"user_id": f"eq.{user_id}"},
                )
            except Exception:
                pass

        _get_stats_persistent(user_id)

        user_data = _build_session_user_payload(
            user_id=user_id,
            email=body.email,
            username=body.name,
            created_at=datetime.utcnow().isoformat(),
        )

        logger.info(f"[register] New user registered: {user_id}")
        create_session(user_data, response)
        return user_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration failed: {e}")
        raise HTTPException(status_code=400, detail={"message": str(e)})


@router.post("/api/login")
def login(body: LoginRequest, response: Response):
    """Login an existing user via Supabase Auth."""
    try:
        mgr = get_manager()
        result = mgr.login_user(body.email, body.password)
        user_id = result["user_id"]

        profile = _get_profile_persistent(user_id)
        name = profile.get("name", body.email.split("@")[0])

        blocked_reason = _status_block_message(profile)
        if blocked_reason:
            raise HTTPException(
                status_code=403,
                detail={"message": blocked_reason, "account_status": _get_account_status(profile)},
            )

        user_data = _build_session_user_payload(
            user_id=user_id,
            email=body.email,
            username=name,
            created_at=profile.get("created_at", datetime.utcnow().isoformat()),
        )
        _get_stats_persistent(user_id)
        create_session(user_data, response)
        return user_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login failed: {e}")
        raise HTTPException(status_code=401, detail={"message": str(e)})


@router.post("/api/auth/social")
def social_login(body: SocialLoginRequest, response: Response):
    """Social login (stub — configure real provider integration)."""
    raise HTTPException(
        status_code=501,
        detail={"message": "Social login is not enabled. Configure real provider integration."},
    )


@router.get("/api/auth/oauth/{provider}/start")
def oauth_start(provider: str):
    """Start Supabase implicit OAuth flow — redirects browser to Supabase /authorize."""
    provider = provider.strip().lower()
    if provider not in {"google", "facebook"}:
        raise HTTPException(status_code=400, detail={"message": "Unsupported provider"})

    supabase_url = os.getenv("SUPABASE_URL")
    if not supabase_url:
        raise HTTPException(status_code=503, detail={"message": "SUPABASE_URL is not configured"})

    frontend_callback = f"{FRONTEND_URL}/auth/oauth-success"
    authorize_url = (
        f"{supabase_url}/auth/v1/authorize"
        f"?provider={provider}"
        f"&redirect_to={urllib.parse.quote(frontend_callback, safe='')}"
    )

    # Debug log
    try:
        _lp = ROOT_DIR / "debug-a2dded.log"
        with open(_lp, "a", encoding="utf-8") as _df:
            _df.write(
                json.dumps({
                    "location": "routes/auth.py:oauth_start",
                    "frontend_callback": frontend_callback,
                    "timestamp": int(time.time() * 1000),
                }) + "\n"
            )
    except Exception:
        pass

    return RedirectResponse(url=authorize_url, status_code=302)


@router.post("/api/oauth/session")
@router.post("/api/auth/oauth/session")
def oauth_session(body: OAuthSessionRequest, response: Response):
    """Exchange a Supabase access_token for a backend httpOnly session cookie."""
    access_token = body.access_token.strip()
    if not access_token:
        raise HTTPException(status_code=400, detail={"message": "Missing access_token"})

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    if not supabase_url or not supabase_key:
        raise HTTPException(status_code=503, detail={"message": "Supabase not configured"})

    try:
        r = httpx.get(
            f"{supabase_url}/auth/v1/user",
            headers={"apikey": supabase_key, "Authorization": f"Bearer {access_token}"},
            timeout=15.0,
        )
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
        raise HTTPException(
            status_code=403,
            detail={"message": blocked_reason, "account_status": _get_account_status(profile)},
        )

    user_data = _build_session_user_payload(
        user_id=user_id,
        email=email,
        username=name,
        created_at=datetime.utcnow().isoformat(),
        provider="oauth",
    )
    create_session(user_data, response)
    return user_data


@router.get("/api/user")
def get_user(request: Request):
    """Return the currently authenticated user from the session cookie."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail={"message": "Not authenticated"})

    profile = _get_profile_persistent(str(user.get("id") or ""))
    blocked_reason = _status_block_message(profile)
    if blocked_reason:
        raise HTTPException(
            status_code=403,
            detail={"message": blocked_reason, "account_status": _get_account_status(profile)},
        )

    user["role"] = profile.get("role", "patient")
    user["account_status"] = _get_account_status(profile)
    user["suspended_until"] = profile.get("suspended_until")
    user["admin_id"] = profile.get("admin_id")
    return user


@router.post("/api/logout")
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


@router.patch("/api/account/email")
def update_account_email(body: UpdateEmailRequest, request: Request):
    """Update authenticated user's email in Supabase Auth and profile table."""
    user = require_user(request)
    user_id = str(user["id"])
    new_email = body.new_email.strip().lower()
    if not new_email:
        raise HTTPException(status_code=400, detail={"message": "new_email is required"})

    mgr = get_manager()
    try:
        mgr.db_client.admin_update_user(user_id, {"email": new_email})
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


@router.patch("/api/account/password")
def update_account_password(body: UpdatePasswordRequest, request: Request):
    """Update authenticated user's password after verifying current password."""
    user = require_user(request)
    user_id = str(user["id"])
    email = str(user.get("email", "")).strip().lower()

    if not body.old_password or not body.new_password:
        raise HTTPException(
            status_code=400,
            detail={"message": "old_password and new_password are required"},
        )
    if len(body.new_password) < 6:
        raise HTTPException(
            status_code=400,
            detail={"message": "new_password must be at least 6 characters long"},
        )

    mgr = get_manager()
    try:
        mgr.db_client.sign_in(email, body.old_password)
    except Exception:
        raise HTTPException(status_code=401, detail={"message": "Current password is incorrect"})

    try:
        mgr.db_client.admin_update_user(user_id, {"password": body.new_password})
        return {"message": "Password updated successfully"}
    except Exception as e:
        logger.error(f"Password update failed for {user_id}: {e}")
        raise HTTPException(status_code=400, detail={"message": str(e)})


@router.delete("/api/account")
def delete_account(request: Request, response: Response):
    """Permanently delete authenticated user's account and all app data."""
    user = require_user(request)
    user_id = str(user["id"])
    mgr = get_manager()

    try:
        mgr.db_client.delete("messages", {"user_id": f"eq.{user_id}"})
        mgr.db_client.delete("conversations", {"user_id": f"eq.{user_id}"})
        mgr.db_client.delete("mood_entries", {"user_id": f"eq.{user_id}"})
        mgr.db_client.delete("user_stats", {"user_id": f"eq.{user_id}"})
        mgr.db_client.delete("user_profiles", {"user_id": f"eq.{user_id}"})
    except Exception as e:
        logger.warning(f"Some app data cleanup failed for {user_id}: {e}")

    try:
        mgr.db_client.admin_delete_user(user_id, should_soft_delete=False)
    except Exception as e:
        logger.error(f"Auth user deletion failed for {user_id}: {e}")
        raise HTTPException(status_code=400, detail={"message": str(e)})

    clear_user_sessions(user_id)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"message": "Account deleted successfully"}
