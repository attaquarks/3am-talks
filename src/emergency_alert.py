"""
Emergency alert service — Twilio WhatsApp/SMS notifier + countdown controller.

Architecture:
- `Notifier` interface: swappable send transport.
- `TwilioWhatsAppNotifier`: primary channel. Graceful no-op when credentials
  are missing (logs a warning, returns a stub result) — lets the rest of the
  crisis pipeline run end-to-end without Twilio set up.
- `TwilioSMSNotifier`: fallback. Same no-op behavior when unconfigured.
- `start_countdown` / `cancel_countdown`: manages the cancellable window
  between detection and dispatch. Records go through Supabase so frontend
  polling + backend race resolve consistently.
- `fire_alerts`: actually dispatches the messages, updates crisis_events.

Nothing in here bypasses consent — callers must check
`crisis_safety_settings.emergency_alerts_enabled` before invoking.
"""
from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Protocol

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Notifier interface + implementations
# ---------------------------------------------------------------------------


@dataclass
class NotificationResult:
    channel: str
    to: str
    success: bool
    provider_sid: Optional[str] = None
    error: Optional[str] = None


class Notifier(Protocol):
    def send(self, to: str, body: str) -> NotificationResult: ...


class TwilioWhatsAppNotifier:
    """Sends via Twilio WhatsApp. Sandbox works for any number that has sent
    `join <code>` to the sandbox number. Production requires an approved
    template — not in scope for MVP."""

    def __init__(self) -> None:
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.from_ = os.getenv("TWILIO_WHATSAPP_FROM", "")  # e.g. "whatsapp:+14155238886"
        self._enabled = bool(self.account_sid and self.auth_token and self.from_)
        if not self._enabled:
            logger.warning(
                "TwilioWhatsAppNotifier disabled (missing TWILIO_ACCOUNT_SID / "
                "TWILIO_AUTH_TOKEN / TWILIO_WHATSAPP_FROM). Alerts will no-op."
            )

    @property
    def enabled(self) -> bool:
        return self._enabled

    def send(self, to: str, body: str) -> NotificationResult:
        if not self._enabled:
            return NotificationResult(
                channel="whatsapp",
                to=to,
                success=False,
                error="twilio_not_configured",
            )
        # Import lazily so the module loads even if twilio isn't installed yet.
        try:
            from twilio.rest import Client  # type: ignore
        except ImportError:
            logger.error("twilio package not installed; cannot send WhatsApp alert")
            return NotificationResult(
                channel="whatsapp", to=to, success=False, error="twilio_not_installed"
            )

        to_whatsapp = to if to.startswith("whatsapp:") else f"whatsapp:{to}"
        try:
            client = Client(self.account_sid, self.auth_token)
            msg = client.messages.create(from_=self.from_, to=to_whatsapp, body=body)
            return NotificationResult(
                channel="whatsapp", to=to, success=True, provider_sid=msg.sid
            )
        except Exception as exc:
            logger.error(f"WhatsApp send failed to {to}: {exc}")
            return NotificationResult(
                channel="whatsapp", to=to, success=False, error=str(exc)[:200]
            )


class TwilioSMSNotifier:
    """SMS fallback. Only usable in PK once a sender ID is PTA-approved."""

    def __init__(self) -> None:
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.from_ = os.getenv("TWILIO_SMS_FROM", "")
        self._enabled = bool(self.account_sid and self.auth_token and self.from_)

    @property
    def enabled(self) -> bool:
        return self._enabled

    def send(self, to: str, body: str) -> NotificationResult:
        if not self._enabled:
            return NotificationResult(
                channel="sms", to=to, success=False, error="twilio_sms_not_configured"
            )
        try:
            from twilio.rest import Client  # type: ignore
        except ImportError:
            return NotificationResult(
                channel="sms", to=to, success=False, error="twilio_not_installed"
            )

        try:
            client = Client(self.account_sid, self.auth_token)
            msg = client.messages.create(from_=self.from_, to=to, body=body)
            return NotificationResult(channel="sms", to=to, success=True, provider_sid=msg.sid)
        except Exception as exc:
            logger.error(f"SMS send failed to {to}: {exc}")
            return NotificationResult(channel="sms", to=to, success=False, error=str(exc)[:200])


# Module-level singletons (lazy)
_whatsapp: Optional[TwilioWhatsAppNotifier] = None
_sms: Optional[TwilioSMSNotifier] = None


def get_whatsapp_notifier() -> TwilioWhatsAppNotifier:
    global _whatsapp
    if _whatsapp is None:
        _whatsapp = TwilioWhatsAppNotifier()
    return _whatsapp


def get_sms_notifier() -> TwilioSMSNotifier:
    global _sms
    if _sms is None:
        _sms = TwilioSMSNotifier()
    return _sms


# ---------------------------------------------------------------------------
# Alert body composition
# ---------------------------------------------------------------------------


PRODUCT_NAME = "Ella by 3AM Talks"


def _relationship_phrase(relationship: Optional[str]) -> str:
    """Map stored relationship to a possessive phrase ("Your sister")."""
    rel = (relationship or "").strip().lower()
    if not rel:
        return "Your friend/family member"
    # Common values; fallback echoes whatever the user stored.
    known = {
        "mother", "mom", "father", "dad", "parent",
        "sister", "brother", "sibling",
        "son", "daughter", "child",
        "spouse", "husband", "wife", "partner",
        "friend", "best friend", "cousin", "uncle", "aunt",
        "guardian", "roommate", "colleague", "neighbor",
    }
    if rel in known:
        return f"Your {rel}"
    return f"Your {rel}"


def compose_alert_body(
    *,
    relationship: Optional[str] = None,
    user_name: Optional[str] = None,
    user_phone: Optional[str] = None,
    location: Optional[Dict[str, Any]] = None,
    country_code: str = "PK",
    is_test: bool = False,
) -> str:
    """Compose the WhatsApp/SMS body for one emergency contact.

    Personalized with the contact's relationship to the user, the user's
    name, callback phone (if provided), and last-known location (if shared).
    """
    who = _relationship_phrase(relationship)
    name_clause = f" ({user_name})" if user_name else ""

    if is_test:
        return (
            f"🧪 TEST — {PRODUCT_NAME} Safety Alert\n\n"
            f"{who}{name_clause} added you as an emergency contact in "
            f"{PRODUCT_NAME}, an AI mental-health companion. This is a test "
            "to confirm this number can receive their safety alerts. No "
            "action is needed.\n\n"
            "If you received this in error, please let them know."
        )

    lines = [
        f"🚨 URGENT — {PRODUCT_NAME} Safety Alert",
        "",
        f"{who}{name_clause} was speaking with Ella, our AI mental-health "
        "companion, and our system has detected they may need immediate "
        "support.",
        "",
        "Please reach out to them now — a phone call or visit could make a "
        "real difference.",
    ]

    if user_phone:
        lines.append("")
        lines.append(f"Their phone: {user_phone}")

    if location and location.get("lat") is not None and location.get("lng") is not None:
        lat = location.get("lat")
        lng = location.get("lng")
        lines.append(f"Last known location: https://maps.google.com/?q={lat},{lng}")

    if country_code.upper() == "PK":
        lines += [
            "",
            "If you believe they are in immediate danger, call 1122 (Pakistan Emergency).",
            "",
            "Crisis Helplines:",
            "- Umang Helpline: 0311-7786264",
            "- Rozan: 0304-1111741",
        ]
    else:
        lines += [
            "",
            "If you believe they are in immediate danger, call local emergency services.",
        ]

    lines += [
        "",
        f"This alert was sent with their prior consent through the "
        f"{PRODUCT_NAME} safety system.",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Countdown controller — uses Supabase as the source of truth for cancellation
# ---------------------------------------------------------------------------


def start_countdown(
    sb,
    *,
    user_id: str,
    event_id: Optional[str],
    seconds: int,
) -> Dict[str, Any]:
    """Insert a crisis_countdowns row. Returns the row including countdown_id."""
    now = datetime.now(timezone.utc)
    row = {
        "user_id": user_id,
        "event_id": event_id,
        "started_at": now.isoformat(),
        "fires_at": (now + timedelta(seconds=seconds)).isoformat(),
    }
    inserted = sb.insert("crisis_countdowns", row)
    return inserted


def cancel_active_countdown(sb, user_id: str) -> int:
    """Cancel any active countdown for this user. Returns count cancelled."""
    now = datetime.now(timezone.utc).isoformat()
    # PostgREST: use is.null for null filters, eq. for equality.
    existing = sb.select(
        "crisis_countdowns",
        columns="countdown_id",
        filters={
            "user_id": f"eq.{user_id}",
            "cancelled_at": "is.null",
            "fired_at": "is.null",
        },
    )
    if not existing:
        return 0
    count = 0
    for row in existing:
        try:
            sb.update(
                "crisis_countdowns",
                {"cancelled_at": now},
                {"countdown_id": f"eq.{row['countdown_id']}"},
            )
            count += 1
        except Exception as exc:
            logger.warning(f"Failed to cancel countdown {row.get('countdown_id')}: {exc}")
    return count


def _countdown_was_cancelled(sb, countdown_id: str) -> bool:
    rows = sb.select(
        "crisis_countdowns",
        columns="cancelled_at",
        filters={"countdown_id": f"eq.{countdown_id}"},
    )
    if not rows:
        return True  # treat missing as cancelled (safer than firing blind)
    return rows[0].get("cancelled_at") is not None


# ---------------------------------------------------------------------------
# Main dispatch: countdown then fire
# ---------------------------------------------------------------------------


async def run_countdown_and_fire(
    sb,
    *,
    user_id: str,
    event_id: str,
    countdown_id: str,
    seconds: int,
    country_code: str = "PK",
    location: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Sleep for `seconds`, re-check cancellation, then dispatch alerts.

    Intended to be scheduled as an asyncio task. Returns a summary dict for
    logging (never raises — errors are caught and recorded on the event row).
    """
    try:
        await asyncio.sleep(seconds)

        if _countdown_was_cancelled(sb, countdown_id):
            logger.info(f"Crisis countdown {countdown_id} cancelled — not firing")
            _update_event(
                sb, event_id, {"intervention_type": "user_cancelled"}
            )
            return {"fired": False, "reason": "cancelled"}

        # Mark countdown as fired.
        now = datetime.now(timezone.utc).isoformat()
        sb.update(
            "crisis_countdowns",
            {"fired_at": now},
            {"countdown_id": f"eq.{countdown_id}"},
        )

        result = fire_alerts(
            sb,
            user_id=user_id,
            event_id=event_id,
            country_code=country_code,
            location=location,
        )
        return {"fired": True, **result}
    except Exception as exc:
        logger.exception(f"run_countdown_and_fire failed: {exc}")
        _update_event(
            sb,
            event_id,
            {
                "intervention_type": "failed_dispatch_error",
                "resolution_notes": f"dispatch error: {str(exc)[:400]}",
            },
        )
        return {"fired": False, "reason": "error", "error": str(exc)[:200]}


def fire_alerts(
    sb,
    *,
    user_id: str,
    event_id: str,
    country_code: str = "PK",
    location: Optional[Dict[str, Any]] = None,
    is_test: bool = False,
) -> Dict[str, Any]:
    """Fetch contacts, dispatch WhatsApp (falling back to SMS), update the event."""
    contacts = sb.select(
        "emergency_contacts",
        columns="id,contact_name,contact_phone,notification_channel,relationship",
        filters={
            "user_id": f"eq.{user_id}",
            "is_active": "eq.true",
        },
    )

    if not contacts:
        logger.warning(f"Crisis fire_alerts: no contacts for user {user_id}")
        _update_event(
            sb,
            event_id,
            {
                "intervention_type": "failed_no_contacts",
                "emergency_alerts_sent": False,
            },
        )
        return {"contacts_notified": 0, "results": []}

    # User name (from user_profiles) + callback phone (from crisis_safety_settings)
    # are personalized into each alert body so contacts know who to call.
    user_name: Optional[str] = None
    user_phone: Optional[str] = None
    profile_phone: Optional[str] = None
    try:
        prof = sb.select(
            "user_profiles", columns="name,phone", filters={"user_id": f"eq.{user_id}"}
        )
        if prof:
            user_name = (prof[0].get("name") or "").strip() or None
            profile_phone = (prof[0].get("phone") or "").strip() or None
    except Exception as exc:
        logger.warning(f"fire_alerts: could not fetch user_profile for {user_id}: {exc}")
    try:
        s = sb.select(
            "crisis_safety_settings",
            columns="user_phone",
            filters={"user_id": f"eq.{user_id}"},
        )
        if s:
            user_phone = (s[0].get("user_phone") or "").strip() or None
    except Exception as exc:
        logger.warning(f"fire_alerts: could not fetch safety settings for {user_id}: {exc}")
    # Fall back to the profile-level phone when the safety settings form was
    # left blank — keeps the alert body useful even if the user only set their
    # number on the profile page.
    if not user_phone:
        user_phone = profile_phone

    whatsapp = get_whatsapp_notifier()
    sms = get_sms_notifier()

    results: List[NotificationResult] = []
    anonymized: List[str] = []
    for c in contacts:
        phone = c.get("contact_phone")
        channel = (c.get("notification_channel") or "whatsapp").lower()
        name = c.get("contact_name", "contact")
        relationship = c.get("relationship")
        if not phone:
            continue

        body = compose_alert_body(
            relationship=relationship,
            user_name=user_name,
            user_phone=user_phone,
            location=location,
            country_code=country_code,
            is_test=is_test,
        )

        sent = None
        if channel in ("whatsapp", "both"):
            sent = whatsapp.send(phone, body)
            results.append(sent)
            if sent.success:
                anonymized.append(f"{name[:1]}***({channel})")

        if channel in ("sms", "both") or (channel == "whatsapp" and sent and not sent.success):
            sms_result = sms.send(phone, body)
            results.append(sms_result)
            if sms_result.success:
                anonymized.append(f"{name[:1]}***(sms)")

    any_sent = any(r.success for r in results)
    _update_event(
        sb,
        event_id,
        {
            "emergency_alerts_sent": any_sent,
            "contacts_notified": anonymized,
            "intervention_type": "alerts_sent" if any_sent else "failed_dispatch",
        },
    )
    return {
        "contacts_notified": len(anonymized),
        "results": [r.__dict__ for r in results],
    }


# ---------------------------------------------------------------------------
# Crisis event logging
# ---------------------------------------------------------------------------


def log_crisis_event(
    sb,
    *,
    user_id: str,
    session_id: Optional[str],
    crisis_result_dict: Dict[str, Any],
    trigger_text: str,
    intervention_type: str = "modal_shown",
    location: Optional[Dict[str, Any]] = None,
    retain_trigger_days: int = 30,
) -> Dict[str, Any]:
    """Insert a crisis_events row. Returns the inserted row."""
    purge_at = (
        datetime.now(timezone.utc) + timedelta(days=retain_trigger_days)
    ).isoformat()
    row = {
        "patient_id": user_id,
        "session_id": session_id,
        "triggered_by": "realtime_detector",
        "severity": crisis_result_dict["risk_level"].lower(),
        "severity_score": crisis_result_dict["severity_score"],
        "trigger_text": trigger_text[:2000] if trigger_text else None,
        "keyword_matches": crisis_result_dict.get("keyword_matches", []),
        "ml_scores": crisis_result_dict.get("ml_scores", {}),
        "intervention_type": intervention_type,
        "user_location": location,
        "trigger_text_purge_at": purge_at,
        "context": {
            "keyword_tier": crisis_result_dict.get("keyword_tier"),
            "llm_verdict": crisis_result_dict.get("llm_verdict"),
            "detection_ms": crisis_result_dict.get("detection_ms"),
        },
    }
    try:
        inserted = sb.insert("crisis_events", row)
        return inserted
    except Exception as exc:
        logger.exception(f"Failed to log crisis event: {exc}")
        return {"event_id": None, "error": str(exc)[:200]}


def _update_event(sb, event_id: str, patch: Dict[str, Any]) -> None:
    if not event_id:
        return
    try:
        sb.update("crisis_events", patch, {"event_id": f"eq.{event_id}"})
    except Exception as exc:
        logger.warning(f"Failed to update crisis_event {event_id}: {exc}")
