"""
Shared crisis-detection integration for /api/chat and /api/voice/chat.

`run_pipeline` executes the therapy response and the crisis detector in
parallel, then — if the risk is HIGH/CRITICAL — logs an event, starts a
countdown, and schedules the alert dispatch. The caller attaches the returned
`crisis` payload to the response so the frontend modal can open.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple

from crisis.alert import (
    cancel_active_countdown,
    fire_alerts,
    log_crisis_event,
    run_countdown_and_fire,
    start_countdown,
)
from crisis.service import CrisisResult, RiskLevel, detect_crisis
from database.supabase_client import SupabaseClient

logger = logging.getLogger(__name__)

_DEFAULT_COUNTDOWN = 30
_HISTORY_WINDOW = 10


def _fetch_history(mgr, conversation_id: str) -> List[Dict[str, str]]:
    """Pull the last N messages for the LLM arbiter's context template."""
    try:
        msgs = mgr.user_service.get_conversation_history(
            conversation_id, limit=_HISTORY_WINDOW
        )
        history: List[Dict[str, str]] = []
        for m in msgs or []:
            role = m.get("role") or ("user" if m.get("is_user") else "assistant")
            content = m.get("content") or ""
            if content:
                history.append({"role": role, "content": content})
        return history
    except Exception as exc:
        logger.warning(f"crisis history fetch failed: {exc}")
        return []


def _session_has_prior_risk(sb, conversation_id: Optional[str]) -> bool:
    """True if this conversation already fired a HIGH/CRITICAL event.

    Used to bypass the fast-exit on calm-resignation messages that would
    otherwise slip through as LOW.
    """
    if not conversation_id:
        return False
    try:
        rows = sb.select(
            "crisis_events",
            columns="severity",
            filters={
                "session_id": f"eq.{conversation_id}",
                "order": "created_at.desc",
                "limit": "5",
            },
        )
        return any(
            (r.get("severity") or "").lower() in ("high", "critical")
            for r in (rows or [])
        )
    except Exception as exc:
        logger.warning(f"prior-risk lookup failed: {exc}")
        return False


def _get_countdown_seconds(sb, user_id: str) -> int:
    try:
        rows = sb.select(
            "crisis_safety_settings",
            columns="countdown_seconds,emergency_alerts_enabled",
            filters={"user_id": f"eq.{user_id}"},
        )
        if rows:
            secs = int(rows[0].get("countdown_seconds") or _DEFAULT_COUNTDOWN)
            return max(10, min(secs, 120))
    except Exception as exc:
        logger.warning(f"countdown settings lookup failed: {exc}")
    return _DEFAULT_COUNTDOWN


def _user_consent_enabled(sb, user_id: str) -> bool:
    try:
        rows = sb.select(
            "crisis_safety_settings",
            columns="emergency_alerts_enabled",
            filters={"user_id": f"eq.{user_id}"},
        )
        return bool(rows and rows[0].get("emergency_alerts_enabled"))
    except Exception:
        return False


def _country_and_location(sb, user_id: str) -> Tuple[str, Optional[Dict[str, Any]]]:
    try:
        rows = sb.select(
            "crisis_safety_settings",
            columns="country_code,last_known_location",
            filters={"user_id": f"eq.{user_id}"},
        )
        if rows:
            return (rows[0].get("country_code") or "PK"), rows[0].get("last_known_location")
    except Exception:
        pass
    return "PK", None


async def detect_and_maybe_alert(
    *,
    mgr,
    sb,
    user_id: str,
    conversation_id: str,
    message: str,
) -> Optional[Dict[str, Any]]:
    """Run crisis detection. If HIGH/CRITICAL, log event + start countdown.

    Returns the `crisis` payload to attach to the chat response, or None.
    """
    history = await asyncio.to_thread(_fetch_history, mgr, conversation_id)
    prior_risk = await asyncio.to_thread(
        _session_has_prior_risk, sb, conversation_id
    )

    result: CrisisResult = await asyncio.to_thread(
        detect_crisis,
        message,
        history=history,
        session_has_prior_risk=prior_risk,
    )

    if result.risk_level not in (RiskLevel.HIGH, RiskLevel.CRITICAL):
        return None

    # Cancel any lingering countdown before starting a fresh one.
    try:
        await asyncio.to_thread(cancel_active_countdown, sb, user_id)
    except Exception as exc:
        logger.warning(f"cancel_active_countdown failed: {exc}")

    event = await asyncio.to_thread(
        log_crisis_event,
        sb,
        user_id=user_id,
        session_id=conversation_id,
        crisis_result_dict=result.to_dict(),
        trigger_text=message,
        intervention_type="modal_shown",
    )
    event_id = (event or {}).get("event_id")

    payload: Dict[str, Any] = {
        "detected": True,
        "risk_level": result.risk_level.value,
        "severity_score": result.severity_score,
        "keyword_tier": result.keyword_tier,
        "llm_verdict": result.llm_verdict,
        "event_id": event_id,
    }

    # Only CRITICAL starts an emergency countdown — HIGH just shows the modal
    # and resources, no automated contact dispatch.
    if result.risk_level == RiskLevel.CRITICAL and event_id:
        consent = await asyncio.to_thread(_user_consent_enabled, sb, user_id)
        if consent:
            seconds = await asyncio.to_thread(_get_countdown_seconds, sb, user_id)
            try:
                cd = await asyncio.to_thread(
                    start_countdown,
                    sb,
                    user_id=user_id,
                    event_id=event_id,
                    seconds=seconds,
                )
                countdown_id = (cd or {}).get("countdown_id")
                country, location = await asyncio.to_thread(
                    _country_and_location, sb, user_id
                )
                if countdown_id:
                    asyncio.create_task(
                        run_countdown_and_fire(
                            sb,
                            user_id=user_id,
                            event_id=event_id,
                            countdown_id=countdown_id,
                            seconds=seconds,
                            country_code=country,
                            location=location,
                        )
                    )
                    payload["countdown"] = {
                        "seconds": seconds,
                        "countdown_id": countdown_id,
                    }
            except Exception as exc:
                logger.exception(f"start_countdown failed: {exc}")

    return payload


async def process_message_with_crisis(
    *,
    mgr,
    sb,
    user_id: str,
    conversation_id: str,
    message: str,
) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    """Run `mgr.process_message` and crisis detection concurrently.

    Returns (process_result, crisis_payload). crisis_payload is None if the
    message was LOW/MEDIUM risk.
    """
    chat_task = asyncio.create_task(
        asyncio.to_thread(
            mgr.process_message,
            user_id=user_id,
            conversation_id=conversation_id,
            user_message=message,
            is_questionnaire_response=False,
        )
    )
    crisis_task = asyncio.create_task(
        detect_and_maybe_alert(
            mgr=mgr,
            sb=sb,
            user_id=user_id,
            conversation_id=conversation_id,
            message=message,
        )
    )

    chat_result, crisis_payload = await asyncio.gather(
        chat_task, crisis_task, return_exceptions=True
    )

    if isinstance(chat_result, Exception):
        raise chat_result
    if isinstance(crisis_payload, Exception):
        logger.exception(f"crisis pipeline errored: {crisis_payload}")
        crisis_payload = None

    return chat_result, crisis_payload
