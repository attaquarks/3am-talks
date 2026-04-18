"""
Crisis safety API routes.

Registered via `register_crisis_routes(app)` from api.py so we reuse the
session helpers and `require_user` dependency without circular imports.

Endpoints (all require authenticated user):
- GET  /api/v1/crisis/settings       — get current consent + config
- POST /api/v1/crisis/settings       — upsert consent + config
- GET  /api/v1/crisis/contacts       — list emergency contacts
- POST /api/v1/crisis/contacts       — add contact
- PUT  /api/v1/crisis/contacts/{id}  — update contact
- DELETE /api/v1/crisis/contacts/{id}— soft-remove contact (is_active=false)
- POST /api/v1/crisis/cancel-alert   — cancel active countdown
- GET  /api/v1/crisis/events         — user's past crisis events
- POST /api/v1/crisis/test-alert     — send a test alert to all active contacts
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from core.helpers import require_user, get_manager, _select_optional_table, _is_missing_table_error, _get_profile_persistent, _build_session_user_payload
from core.sessions import create_session, update_user_sessions
from database.supabase_client import SupabaseClient
from ..crisis.alert import cancel_active_countdown, fire_alerts, log_crisis_event

logger = logging.getLogger("crisis-routes")

E164_RE = re.compile(r"^\+[1-9][0-9]{6,14}$")



router = APIRouter(prefix="/api/v1/crisis", tags=["crisis"])
sb = SupabaseClient()
# ---------------------------------------------------------------------------
# Pydantic request models
# ---------------------------------------------------------------------------


class CrisisSettingsUpdate(BaseModel):
    emergency_alerts_enabled: bool
    location_sharing_consent: bool = False
    consent_text_shown: str = Field(..., min_length=20, max_length=4000)
    countdown_seconds: int = Field(30, ge=10, le=120)
    country_code: str = Field("PK", min_length=2, max_length=3)
    user_phone: Optional[str] = None  # E.164, used in alert body so contacts can call back


class ContactCreate(BaseModel):
    contact_name: str = Field(..., min_length=1, max_length=120)
    contact_phone: str
    relationship: Optional[str] = None
    notification_channel: str = Field("whatsapp", pattern=r"^(whatsapp|sms|both)$")


class ContactUpdate(BaseModel):
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    relationship: Optional[str] = None
    notification_channel: Optional[str] = None
    is_active: Optional[bool] = None


class LocationUpdate(BaseModel):
    lat: float
    lng: float
    accuracy: Optional[float] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _validate_e164(phone: str) -> str:
    phone = (phone or "").strip().replace(" ", "").replace("-", "")
    if not E164_RE.match(phone):
        raise HTTPException(
            status_code=400,
            detail="contact_phone must be E.164 format, e.g. +923001234567",
        )
    return phone


def _get_settings_or_default(sb, user_id: str) -> Dict[str, Any]:
    rows = sb.select(
        "crisis_safety_settings",
        filters={"user_id": f"eq.{user_id}"},
    )
    if rows:
        return rows[0]
    return {
        "user_id": user_id,
        "emergency_alerts_enabled": False,
        "location_sharing_consent": False,
        "consent_given_at": None,
        "consent_text_shown": None,
        "countdown_seconds": 30,
        "country_code": "PK",
        "last_known_location": None,
        "user_phone": None,
    }


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------



    # -----------------------------------------------------------------------
    # Settings
    # -----------------------------------------------------------------------

@router.get("/settings")
def get_crisis_settings(request: Request):
    user = require_user(request)
    return _get_settings_or_default(sb, str(user["id"]))

@router.post("/settings")
def upsert_crisis_settings(body: CrisisSettingsUpdate, request: Request):
    user = require_user(request)
    user_id = str(user["id"])
    now = datetime.now(timezone.utc).isoformat()

    existing = sb.select(
        "crisis_safety_settings",
        columns="id",
        filters={"user_id": f"eq.{user_id}"},
    )

    payload = {
        "user_id": user_id,
        "emergency_alerts_enabled": body.emergency_alerts_enabled,
        "location_sharing_consent": body.location_sharing_consent,
        "consent_text_shown": body.consent_text_shown,
        "countdown_seconds": body.countdown_seconds,
        "country_code": body.country_code.upper(),
        "updated_at": now,
    }
    if body.user_phone is not None:
        phone = body.user_phone.strip()
        if phone:
            payload["user_phone"] = _validate_e164(phone)
        else:
            payload["user_phone"] = None
    # Only stamp consent_given_at when the user first opts in.
    if body.emergency_alerts_enabled:
        payload["consent_given_at"] = now

    try:
        if existing:
            sb.update(
                "crisis_safety_settings",
                payload,
                {"user_id": f"eq.{user_id}"},
            )
        else:
            sb.insert("crisis_safety_settings", payload)
    except Exception as exc:
        logger.exception(f"Failed to upsert crisis settings: {exc}")
        raise HTTPException(status_code=500, detail="Failed to save settings")

    return _get_settings_or_default(sb, user_id)

@router.post("/location")
def update_location(body: LocationUpdate, request: Request):
    """Stored only if location_sharing_consent is true — enforced here."""
    user = require_user(request)
    user_id = str(user["id"])
    settings = _get_settings_or_default(sb, user_id)
    if not settings.get("location_sharing_consent"):
        raise HTTPException(status_code=403, detail="Location sharing not consented")
    loc = {
        "lat": body.lat,
        "lng": body.lng,
        "accuracy": body.accuracy,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    sb.update(
        "crisis_safety_settings",
        {"last_known_location": loc, "updated_at": loc["updated_at"]},
        {"user_id": f"eq.{user_id}"},
    )
    return {"ok": True}

# -----------------------------------------------------------------------
# Contacts
# -----------------------------------------------------------------------

@router.get("/contacts")
def list_contacts(request: Request):
    user = require_user(request)
    user_id = str(user["id"])
    rows = sb.select(
        "emergency_contacts",
        filters={"user_id": f"eq.{user_id}", "is_active": "eq.true"},
    )
    return {"contacts": rows or []}

@router.post("/contacts")
def add_contact(body: ContactCreate, request: Request):
    user = require_user(request)
    user_id = str(user["id"])
    phone = _validate_e164(body.contact_phone)
    try:
        inserted = sb.insert(
            "emergency_contacts",
            {
                "user_id": user_id,
                "contact_name": body.contact_name,
                "contact_phone": phone,
                "relationship": body.relationship,
                "notification_channel": body.notification_channel,
                "is_active": True,
            },
        )
    except Exception as exc:
        logger.exception(f"Failed to insert contact: {exc}")
        raise HTTPException(status_code=500, detail="Failed to add contact")
    return inserted

@router.put("/contacts/{contact_id}")
def update_contact(contact_id: str, body: ContactUpdate, request: Request):
    user = require_user(request)
    user_id = str(user["id"])
    existing = sb.select(
        "emergency_contacts",
        columns="id,user_id",
        filters={"id": f"eq.{contact_id}"},
    )
    if not existing or existing[0].get("user_id") != user_id:
        raise HTTPException(status_code=404, detail="Contact not found")

    patch: Dict[str, Any] = {}
    if body.contact_name is not None:
        patch["contact_name"] = body.contact_name
    if body.contact_phone is not None:
        patch["contact_phone"] = _validate_e164(body.contact_phone)
    if body.relationship is not None:
        patch["relationship"] = body.relationship
    if body.notification_channel is not None:
        if body.notification_channel not in ("whatsapp", "sms", "both"):
            raise HTTPException(status_code=400, detail="Invalid notification_channel")
        patch["notification_channel"] = body.notification_channel
    if body.is_active is not None:
        patch["is_active"] = body.is_active
    patch["updated_at"] = datetime.now(timezone.utc).isoformat()

    try:
        sb.update("emergency_contacts", patch, {"id": f"eq.{contact_id}"})
    except Exception as exc:
        logger.exception(f"Failed to update contact: {exc}")
        raise HTTPException(status_code=500, detail="Failed to update")
    return {"ok": True}

@router.delete("/contacts/{contact_id}")
def delete_contact(contact_id: str, request: Request):
    user = require_user(request)
    user_id = str(user["id"])
    existing = sb.select(
        "emergency_contacts",
        columns="id,user_id",
        filters={"id": f"eq.{contact_id}"},
    )
    if not existing or existing[0].get("user_id") != user_id:
        raise HTTPException(status_code=404, detail="Contact not found")
    sb.update(
        "emergency_contacts",
        {"is_active": False, "updated_at": datetime.now(timezone.utc).isoformat()},
        {"id": f"eq.{contact_id}"},
    )
    return {"ok": True}

# -----------------------------------------------------------------------
# Cancel countdown
# -----------------------------------------------------------------------

@router.post("/cancel-alert")
def cancel_alert(request: Request):
    user = require_user(request)
    cancelled = cancel_active_countdown(sb, str(user["id"]))
    return {"cancelled": cancelled}

# -----------------------------------------------------------------------
# Events (read-only)
# -----------------------------------------------------------------------

@router.get("/events")
def list_events(request: Request, limit: int = 50):
    user = require_user(request)
    user_id = str(user["id"])
    limit = max(1, min(int(limit or 50), 200))
    rows = sb.select(
        "crisis_events",
        columns="event_id,severity,severity_score,intervention_type,"
        "emergency_alerts_sent,contacts_notified,created_at,triggered_by",
        filters={
            "patient_id": f"eq.{user_id}",
            "order": "created_at.desc",
            "limit": str(limit),
        },
    )
    return {"events": rows or []}

# -----------------------------------------------------------------------
# Test alert
# -----------------------------------------------------------------------

@router.post("/test-alert")
def test_alert(request: Request):
    user = require_user(request)
    user_id = str(user["id"])
    settings = _get_settings_or_default(sb, user_id)
    country = settings.get("country_code", "PK")

    # Log a synthetic event so the user sees their test in events history.
    synthetic = {
        "risk_level": "LOW",
        "severity_score": 0.0,
        "keyword_matches": [],
        "ml_scores": {},
        "keyword_tier": "test",
        "llm_verdict": None,
        "detection_ms": 0.0,
    }
    event = log_crisis_event(
        sb,
        user_id=user_id,
        session_id=None,
        crisis_result_dict=synthetic,
        trigger_text="[test alert requested by user]",
        intervention_type="test_alert",
    )
    event_id = event.get("event_id")
    result = fire_alerts(
        sb,
        user_id=user_id,
        event_id=event_id,
        country_code=country,
        is_test=True,
    )
    return {"event_id": event_id, **result}
