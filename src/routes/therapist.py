"""
Therapist portal API routes.

Registered via `register_therapist_routes(app)` from api.py so we can reuse the
session helpers, get_manager, and audit utilities defined there without
creating circular imports.
"""
from __future__ import annotations

import io
import logging
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, FastAPI, HTTPException, Request, Response
from pydantic import BaseModel

from core.helpers import require_user, get_manager, _select_optional_table, _is_missing_table_error, _get_profile_persistent, _build_session_user_payload
from core.sessions import create_session, update_user_sessions
from database.supabase_client import SupabaseClient
from crisis.alert import cancel_active_countdown, fire_alerts, log_crisis_event

logger = logging.getLogger("therapist-routes")



router = APIRouter(prefix="/api/therapist", tags=["therapist"])
shared_router = APIRouter(tags=["therapist-shared"])
public_router = APIRouter(tags=["therapist-public"])
sb = SupabaseClient()
# ---------------------------------------------------------------------------
# Pydantic request models
# ---------------------------------------------------------------------------


class TherapistRegisterRequest(BaseModel):
    email: str
    password: str
    name: str = "Clinician"
    license_number: Optional[str] = None
    license_jurisdiction: Optional[str] = None
    specializations: Optional[List[str]] = None
    years_experience: Optional[int] = None
    bio: Optional[str] = None
    title: Optional[str] = None


class TherapistProfileUpdate(BaseModel):
    display_name: Optional[str] = None
    title: Optional[str] = None
    bio: Optional[str] = None
    pronouns: Optional[str] = None
    photo_url: Optional[str] = None
    specializations: Optional[List[str]] = None
    modalities: Optional[List[str]] = None
    languages: Optional[List[str]] = None
    years_experience: Optional[int] = None
    accepting_patients: Optional[bool] = None
    max_caseload: Optional[int] = None
    timezone: Optional[str] = None
    availability: Optional[Dict[str, Any]] = None


class VerificationResubmit(BaseModel):
    license_number: Optional[str] = None
    license_url: Optional[str] = None
    specializations: Optional[List[str]] = None
    years_of_experience: Optional[int] = None
    bio: Optional[str] = None


class InviteRequest(BaseModel):
    email: str
    note: Optional[str] = None


class LinkAcceptRequest(BaseModel):
    link_id: str


class ConsentConfirmRequest(BaseModel):
    consent_scope: Optional[Dict[str, bool]] = None


class LinkRevokeRequest(BaseModel):
    reason: Optional[str] = None


class NoteUpsertRequest(BaseModel):
    patient_id: str
    conversation_id: Optional[str] = None
    body: str
    tags: Optional[List[str]] = None
    follow_up_at: Optional[datetime] = None


class NoteUpdateRequest(BaseModel):
    body: Optional[str] = None
    tags: Optional[List[str]] = None
    follow_up_at: Optional[datetime] = None


class TreatmentPlanUpsertRequest(BaseModel):
    patient_id: str
    title: str
    primary_concern: Optional[str] = None
    goals: Optional[List[Dict[str, Any]]] = None
    interventions: Optional[List[str]] = None
    status: Optional[str] = "active"


class TreatmentPlanUpdateRequest(BaseModel):
    title: Optional[str] = None
    primary_concern: Optional[str] = None
    goals: Optional[List[Dict[str, Any]]] = None
    interventions: Optional[List[str]] = None
    status: Optional[str] = None


class HomeworkAssignRequest(BaseModel):
    patient_id: str
    title: str
    description: Optional[str] = None
    due_at: Optional[datetime] = None
    plan_id: Optional[str] = None


class HomeworkUpdateRequest(BaseModel):
    status: Optional[str] = None
    patient_reflection: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    due_at: Optional[datetime] = None


class MessageSendRequest(BaseModel):
    link_id: str
    body: str
    urgency: Optional[str] = "normal"


class CrisisEscalateRequest(BaseModel):
    patient_id: str
    severity: Optional[str] = "high"
    notes: Optional[str] = None
    locale: Optional[str] = "US"


class FeedbackSubmitRequest(BaseModel):
    target_therapist_id: Optional[str] = None
    rating: Optional[int] = None
    comment: str
    feedback_type: Optional[str] = "therapist"


class ReportSubmitRequest(BaseModel):
    reported_user_id: Optional[str] = None
    category: str
    description: str
    priority: Optional[str] = "medium"


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------



    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

def _require_therapist(request: Request) -> dict:
    user = require_user(request)
    role = str(user.get("role") or "").lower()
    if role != "therapist":
        raise HTTPException(status_code=403, detail={"message": "Therapist access required."})
    return user

def _get_therapist_profile(user_id: str) -> dict:
    rows = _select_optional_table("therapist_profiles", filters={"therapist_user_id": f"eq.{user_id}"})
    if rows:
        return rows[0]
    # Lazy create
    now = datetime.utcnow().isoformat()
    try:
        profile = get_manager().db_client.insert(
            "therapist_profiles",
            {
                "therapist_user_id": user_id,
                "created_at": now,
                "updated_at": now,
            },
        )
        return profile if isinstance(profile, dict) else {"therapist_user_id": user_id}
    except Exception as exc:
        if _is_missing_table_error(exc):
            logger.warning("therapist_profiles table missing — run therapist portal migration.")
        return {"therapist_user_id": user_id}

def _active_link(therapist_id: str, patient_id: str) -> Optional[dict]:
    rows = _select_optional_table(
        "patient_therapist_links",
        filters={
            "therapist_id": f"eq.{therapist_id}",
            "patient_id": f"eq.{patient_id}",
            "status": "eq.active",
        },
    )
    return rows[0] if rows else None

def _require_link(therapist_id: str, patient_id: str) -> dict:
    link = _active_link(therapist_id, patient_id)
    if not link:
        raise HTTPException(status_code=403, detail={"message": "No active link with this patient."})
    return link

def _has_scope(link: dict, scope: str) -> bool:
    """Check whether a therapist-patient link grants a specific consent scope.
    Fails closed: if consent_scope is missing, corrupt, or not a dict,
    deny access rather than granting it."""
    consent = link.get("consent_scope")
    if not isinstance(consent, dict):
        return False  # fail closed — deny by default
    return bool(consent.get(scope, False))

def _log_access(therapist_id: str, patient_id: str, resource: str, action: str, resource_id: str = None) -> None:
    try:
        get_manager().db_client.insert(
            "clinical_access_logs",
            {
                "therapist_id": therapist_id,
                "patient_id": patient_id,
                "resource": resource,
                "resource_id": resource_id,
                "action": action,
            },
        )
    except Exception as exc:
        if not _is_missing_table_error(exc):
            logger.warning(f"clinical_access_logs write failed: {exc}")

def _user_by_email(email: str) -> Optional[dict]:
    rows = _select_optional_table("user_profiles", filters={"email": f"eq.{email.lower()}"})
    if rows:
        return rows[0]
    rows = _select_optional_table("user_profiles", filters={"email": f"ilike.{email}"})
    return rows[0] if rows else None

def _user_summary(profile: dict) -> dict:
    return {
        "user_id": profile.get("user_id"),
        "name": profile.get("name"),
        "email": profile.get("email"),
        "role": profile.get("role"),
    }

def _link_counterparty(link: dict, viewer_id: str) -> dict:
    viewer_is_patient = str(link.get("patient_id")) == str(viewer_id)
    other_id = link.get("therapist_id") if viewer_is_patient else link.get("patient_id")
    profile = _select_optional_table("user_profiles", filters={"user_id": f"eq.{other_id}"})
    base = profile[0] if profile else {"user_id": other_id}
    result = _user_summary(base)
    if not viewer_is_patient:
        return result
    # Viewer is patient — enrich with therapist display info
    tprof = _select_optional_table("therapist_profiles", filters={"therapist_user_id": f"eq.{other_id}"})
    if tprof:
        tp = tprof[0]
        result.update({
            "display_name": tp.get("display_name"),
            "title": tp.get("title"),
            "specializations": tp.get("specializations") or [],
            "modalities": tp.get("modalities") or [],
            "photo_url": tp.get("photo_url"),
            "bio": tp.get("bio"),
        })
    return result

# =======================================================================
# Therapist self-service
# =======================================================================

@router.post("/register")
def therapist_register(body: TherapistRegisterRequest, response: Response):
    """Register a therapist account; starts in pending_verification state."""
    try:
        mgr = get_manager()
        result = mgr.register_user(body.email, body.password)
        user_id = result["user_id"]
        now = datetime.utcnow().isoformat()

        try:
            mgr.db_client.update(
                "user_profiles",
                {
                    "name": body.name,
                    "email": body.email,
                    "role": "therapist",
                    "account_status": "pending_verification",
                    "updated_at": now,
                },
                {"user_id": f"eq.{user_id}"},
            )
        except Exception as exc:
            logger.warning(f"Could not set therapist profile defaults: {exc}")

        try:
            mgr.db_client.insert(
                "therapist_profiles",
                {
                    "therapist_user_id": user_id,
                    "display_name": body.name,
                    "title": body.title,
                    "license_number": body.license_number,
                    "license_jurisdiction": body.license_jurisdiction,
                    "specializations": body.specializations or [],
                    "years_experience": body.years_experience,
                    "bio": body.bio,
                    "accepting_patients": True,
                    "created_at": now,
                    "updated_at": now,
                },
            )
        except Exception as exc:
            if not _is_missing_table_error(exc):
                logger.warning(f"therapist_profiles insert failed: {exc}")

        try:
            mgr.db_client.insert(
                "therapist_verifications",
                {
                    "user_id": user_id,
                    "license_number": body.license_number,
                    "specializations": body.specializations or [],
                    "years_of_experience": body.years_experience,
                    "bio": body.bio,
                    "status": "pending",
                },
            )
        except Exception as exc:
            if not _is_missing_table_error(exc):
                logger.warning(f"therapist_verifications insert failed: {exc}")

        user_data = _build_session_user_payload(
            user_id=user_id, email=body.email, username=body.name, created_at=now,
        )
        user_data["role"] = "therapist"
        user_data["account_status"] = "pending_verification"
        create_session(user_data, response)
        return user_data
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Therapist registration failed: {exc}")
        raise HTTPException(status_code=400, detail={"message": str(exc)})

@router.get("/me")
def therapist_me(request: Request):
    user = require_user(request)
    role = str(user.get("role") or "").lower()
    if role != "therapist":
        raise HTTPException(status_code=403, detail={"message": "Therapist access required."})
    user_id = str(user["id"])
    profile = _get_profile_persistent(user_id)
    tprof = _get_therapist_profile(user_id)
    verifications = _select_optional_table("therapist_verifications", filters={"user_id": f"eq.{user_id}"})
    latest_verification = None
    if verifications:
        latest_verification = sorted(
            verifications, key=lambda v: str(v.get("submitted_at") or ""), reverse=True,
        )[0]
    return {
        "user": _user_summary(profile),
        "account_status": profile.get("account_status"),
        "therapist_profile": tprof,
        "verification": latest_verification,
    }

@router.patch("/me")
def therapist_update_me(body: TherapistProfileUpdate, request: Request):
    user = _require_therapist(request)
    user_id = str(user["id"])
    updates = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if not updates:
        return _get_therapist_profile(user_id)
    updates["updated_at"] = datetime.utcnow().isoformat()
    _get_therapist_profile(user_id)  # ensure row
    try:
        get_manager().db_client.update(
            "therapist_profiles", updates, {"therapist_user_id": f"eq.{user_id}"},
        )
    except Exception as exc:
        if _is_missing_table_error(exc):
            raise HTTPException(status_code=503, detail={"message": "therapist_profiles missing — run migration."})
        raise
    return _get_therapist_profile(user_id)

@router.post("/me/verification")
def therapist_resubmit_verification(body: VerificationResubmit, request: Request):
    user = require_user(request)
    if str(user.get("role") or "").lower() != "therapist":
        raise HTTPException(status_code=403, detail={"message": "Therapist access required."})
    user_id = str(user["id"])
    payload = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    payload.update({
        "user_id": user_id,
        "status": "pending",
        "submitted_at": datetime.utcnow().isoformat(),
    })
    try:
        row = get_manager().db_client.insert("therapist_verifications", payload)
    except Exception as exc:
        if _is_missing_table_error(exc):
            raise HTTPException(status_code=503, detail={"message": "therapist_verifications missing."})
        raise
    return row

# =======================================================================
# Caseload
# =======================================================================

@router.get("/patients")
def therapist_patients(request: Request):
    """List the therapist's active patients with at-a-glance stats.

    Queries are scoped to linked patient IDs only — never loads full tables.
    """
    user = _require_therapist(request)
    therapist_id = str(user["id"])
    links = _select_optional_table(
        "patient_therapist_links",
        filters={"therapist_id": f"eq.{therapist_id}", "status": "eq.active"},
    )
    if not links:
        return {"patients": [], "total": 0}

    patient_ids = [str(lk.get("patient_id")) for lk in links]

    # Fetch data scoped to linked patients only (not entire tables)
    by_uid: Dict[str, dict] = {}
    by_patient_convs: Dict[str, List[dict]] = {}
    mood_by_patient: Dict[str, List[dict]] = {}
    crisis_by_patient: Dict[str, List[dict]] = {}

    for pid in patient_ids:
        profs = _select_optional_table("user_profiles", filters={"user_id": f"eq.{pid}"})
        if profs:
            by_uid[pid] = profs[0]
        for c in _select_optional_table("conversations", filters={"user_id": f"eq.{pid}"}):
            by_patient_convs.setdefault(pid, []).append(c)
        for m in _select_optional_table("mood_entries", filters={"user_id": f"eq.{pid}"}):
            mood_by_patient.setdefault(pid, []).append(m)
        for c in _select_optional_table("crisis_events", filters={"patient_id": f"eq.{pid}"}):
            crisis_by_patient.setdefault(pid, []).append(c)

    patients = []
    for link in links:
        pid = str(link.get("patient_id"))
        prof = by_uid.get(pid, {})
        patient_convs = by_patient_convs.get(pid, [])
        patient_convs_sorted = sorted(patient_convs, key=lambda c: str(c.get("created_at") or ""), reverse=True)
        last_conv = patient_convs_sorted[0] if patient_convs_sorted else None
        patient_moods = sorted(mood_by_patient.get(pid, []), key=lambda m: str(m.get("date") or m.get("created_at") or ""), reverse=True)[:7]
        patient_crisis = sorted(crisis_by_patient.get(pid, []), key=lambda c: str(c.get("created_at") or ""), reverse=True)
        latest_crisis = patient_crisis[0] if patient_crisis else None
        patients.append({
            "link_id": link.get("link_id"),
            "patient_id": pid,
            "name": prof.get("name"),
            "email": prof.get("email"),
            "linked_since": link.get("patient_consented_at") or link.get("created_at"),
            "last_session_at": last_conv.get("created_at") if last_conv else None,
            "total_sessions": len(patient_convs),
            "recent_mood": [
                {"date": m.get("date"), "mood": m.get("mood")}
                for m in patient_moods
            ],
            "risk_level": (latest_crisis or {}).get("severity") if latest_crisis and not latest_crisis.get("resolved_at") else "none",
            "unresolved_crisis": bool(latest_crisis and not latest_crisis.get("resolved_at")),
        })
    patients.sort(key=lambda p: str(p.get("last_session_at") or ""), reverse=True)
    return {"patients": patients, "total": len(patients)}

@router.get("/patients/{patient_id}")
def therapist_patient_detail(patient_id: str, request: Request):
    user = _require_therapist(request)
    therapist_id = str(user["id"])
    link = _require_link(therapist_id, patient_id)
    _log_access(therapist_id, patient_id, "profile", "view")

    profile = _get_profile_persistent(patient_id)
    stats_rows = _select_optional_table("user_stats", filters={"user_id": f"eq.{patient_id}"})
    stats = stats_rows[0] if stats_rows else {}
    return {
        "patient": _user_summary(profile),
        "personality": {
            "extroversion": profile.get("extroversion"),
            "neuroticism": profile.get("neuroticism"),
            "agreeableness": profile.get("agreeableness"),
            "conscientiousness": profile.get("conscientiousness"),
            "openness": profile.get("openness"),
        },
        "stats": stats,
        "link": link,
    }

@router.get("/patients/{patient_id}/conversations")
def therapist_patient_conversations(patient_id: str, request: Request):
    user = _require_therapist(request)
    therapist_id = str(user["id"])
    link = _require_link(therapist_id, patient_id)
    if not _has_scope(link, "conversations"):
        raise HTTPException(status_code=403, detail={"message": "Patient has not shared conversations."})
    _log_access(therapist_id, patient_id, "conversations", "list")

    convs = _select_optional_table("conversations", filters={"user_id": f"eq.{patient_id}"})
    convs_sorted = sorted(convs, key=lambda c: str(c.get("created_at") or ""), reverse=True)

    summaries = _select_optional_table("session_summaries", filters={"patient_id": f"eq.{patient_id}"})
    by_conv = {str(s.get("conversation_id")): s for s in summaries}
    for c in convs_sorted:
        s = by_conv.get(str(c.get("conversation_id")))
        if s:
            c["summary_preview"] = {
                "themes": s.get("themes"),
                "mood_trajectory": s.get("mood_trajectory"),
                "risk_flags": s.get("risk_flags"),
                "generated_at": s.get("generated_at"),
            }
    return {"conversations": convs_sorted, "total": len(convs_sorted)}

@router.get("/patients/{patient_id}/conversations/{conv_id}")
def therapist_patient_conversation_detail(patient_id: str, conv_id: str, request: Request):
    user = _require_therapist(request)
    therapist_id = str(user["id"])
    link = _require_link(therapist_id, patient_id)
    if not _has_scope(link, "conversations"):
        raise HTTPException(status_code=403, detail={"message": "Patient has not shared conversations."})
    _log_access(therapist_id, patient_id, "conversation", "view", conv_id)

    mgr = get_manager()
    conv_rows = _select_optional_table("conversations", filters={"conversation_id": f"eq.{conv_id}", "user_id": f"eq.{patient_id}"})
    if not conv_rows:
        raise HTTPException(status_code=404, detail={"message": "Conversation not found."})
    messages = mgr.user_service.get_conversation_history(conv_id)
    summary_rows = _select_optional_table("session_summaries", filters={"conversation_id": f"eq.{conv_id}"})

    # Lazy-generate summary if missing
    summary = summary_rows[0] if summary_rows else None
    if not summary and messages:
        try:
            summary = _generate_and_store_summary(patient_id, conv_id, messages)
        except Exception as exc:
            logger.warning(f"Lazy summary generation failed: {exc}")

    return {
        "conversation": conv_rows[0],
        "messages": messages,
        "summary": summary,
    }

@router.get("/patients/{patient_id}/mood")
def therapist_patient_mood(patient_id: str, request: Request):
    user = _require_therapist(request)
    therapist_id = str(user["id"])
    link = _require_link(therapist_id, patient_id)
    if not _has_scope(link, "mood"):
        raise HTTPException(status_code=403, detail={"message": "Patient has not shared mood data."})
    _log_access(therapist_id, patient_id, "mood", "list")
    rows = _select_optional_table("mood_entries", filters={"user_id": f"eq.{patient_id}"})
    rows_sorted = sorted(rows, key=lambda m: str(m.get("date") or m.get("created_at") or ""), reverse=True)
    return {"mood_entries": rows_sorted}

@router.get("/patients/{patient_id}/journals")
def therapist_patient_journals(patient_id: str, request: Request):
    user = _require_therapist(request)
    therapist_id = str(user["id"])
    link = _require_link(therapist_id, patient_id)
    if not _has_scope(link, "journals"):
        raise HTTPException(status_code=403, detail={"message": "Patient has not shared journals."})
    _log_access(therapist_id, patient_id, "journals", "list")
    rows = _select_optional_table("mood_entries", filters={"user_id": f"eq.{patient_id}"})
    with_notes = [r for r in rows if (r.get("note") or r.get("prompt_answer"))]
    with_notes.sort(key=lambda m: str(m.get("date") or m.get("created_at") or ""), reverse=True)
    return {"journals": with_notes}

@router.get("/patients/{patient_id}/prep-brief")
def therapist_prep_brief(patient_id: str, request: Request):
    from conversation.summary import generate_prep_brief
    user = _require_therapist(request)
    therapist_id = str(user["id"])
    link = _require_link(therapist_id, patient_id)
    _log_access(therapist_id, patient_id, "prep_brief", "generate")

    # Build context from last ~3 summaries + recent moods
    summaries = _select_optional_table("session_summaries", filters={"patient_id": f"eq.{patient_id}"})
    summaries_sorted = sorted(summaries, key=lambda s: str(s.get("generated_at") or ""), reverse=True)[:3]
    moods = _select_optional_table("mood_entries", filters={"user_id": f"eq.{patient_id}"})
    moods_sorted = sorted(moods, key=lambda m: str(m.get("date") or m.get("created_at") or ""), reverse=True)[:10]

    ctx_parts = []
    for s in summaries_sorted:
        ctx_parts.append(
            f"Session on {s.get('generated_at','?')}: Assessment: {s.get('assessment','')} | "
            f"Themes: {', '.join(s.get('themes') or [])} | Mood: {s.get('mood_trajectory','')}"
        )
    if moods_sorted:
        ctx_parts.append(
            "Recent moods: " + ", ".join(f"{m.get('date','?')}:{m.get('mood','?')}" for m in moods_sorted)
        )
    context = "\n".join(ctx_parts) or "No prior session data available."

    mgr = get_manager()
    try:
        brief = generate_prep_brief(getattr(mgr, "llm", None), context)
    except Exception as exc:
        logger.warning(f"Prep brief failed: {exc}")
        brief = {"top_concerns": [], "recent_shifts": "", "unresolved_topics": [], "suggested_focus": "", "risk_notes": ""}
    return brief

# =======================================================================
# Clinical: Notes
# =======================================================================

@router.get("/notes")
def notes_list(request: Request):
    user = _require_therapist(request)
    therapist_id = str(user["id"])
    patient_id = request.query_params.get("patient_id")
    filters = {"therapist_id": f"eq.{therapist_id}"}
    if patient_id:
        _require_link(therapist_id, patient_id)
        filters["patient_id"] = f"eq.{patient_id}"
    rows = _select_optional_table("therapist_notes", filters=filters)
    rows.sort(key=lambda r: str(r.get("updated_at") or r.get("created_at") or ""), reverse=True)
    return {"notes": rows}

@router.post("/notes")
def notes_create(body: NoteUpsertRequest, request: Request):
    user = _require_therapist(request)
    therapist_id = str(user["id"])
    _require_link(therapist_id, body.patient_id)
    payload = {
        "therapist_id": therapist_id,
        "patient_id": body.patient_id,
        "conversation_id": body.conversation_id,
        "body": body.body,
        "tags": body.tags or [],
        "follow_up_at": body.follow_up_at.isoformat() if body.follow_up_at else None,
        "is_private": True,
    }
    row = get_manager().db_client.insert("therapist_notes", payload)
    _log_access(therapist_id, body.patient_id, "note", "create", (row or {}).get("note_id"))
    return row

@router.patch("/notes/{note_id}")
def notes_update(note_id: str, body: NoteUpdateRequest, request: Request):
    user = _require_therapist(request)
    therapist_id = str(user["id"])
    existing = _select_optional_table("therapist_notes", filters={"note_id": f"eq.{note_id}", "therapist_id": f"eq.{therapist_id}"})
    if not existing:
        raise HTTPException(status_code=404, detail={"message": "Note not found."})
    updates = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if body.follow_up_at:
        updates["follow_up_at"] = body.follow_up_at.isoformat()
    updates["updated_at"] = datetime.utcnow().isoformat()
    get_manager().db_client.update("therapist_notes", updates, {"note_id": f"eq.{note_id}"})
    refreshed = _select_optional_table("therapist_notes", filters={"note_id": f"eq.{note_id}"})
    return refreshed[0] if refreshed else {"note_id": note_id}

@router.delete("/notes/{note_id}")
def notes_delete(note_id: str, request: Request):
    user = _require_therapist(request)
    therapist_id = str(user["id"])
    existing = _select_optional_table("therapist_notes", filters={"note_id": f"eq.{note_id}", "therapist_id": f"eq.{therapist_id}"})
    if not existing:
        raise HTTPException(status_code=404, detail={"message": "Note not found."})
    get_manager().db_client.delete("therapist_notes", {"note_id": f"eq.{note_id}"})
    return {"deleted": True, "note_id": note_id}

# =======================================================================
# Clinical: Treatment plans
# =======================================================================

@router.get("/treatment-plans")
def plans_list(request: Request):
    user = _require_therapist(request)
    therapist_id = str(user["id"])
    patient_id = request.query_params.get("patient_id")
    filters = {"therapist_id": f"eq.{therapist_id}"}
    if patient_id:
        _require_link(therapist_id, patient_id)
        filters["patient_id"] = f"eq.{patient_id}"
    rows = _select_optional_table("treatment_plans", filters=filters)
    rows.sort(key=lambda r: str(r.get("updated_at") or ""), reverse=True)
    return {"plans": rows}

@router.post("/treatment-plans")
def plans_create(body: TreatmentPlanUpsertRequest, request: Request):
    user = _require_therapist(request)
    therapist_id = str(user["id"])
    _require_link(therapist_id, body.patient_id)
    payload = {
        "therapist_id": therapist_id,
        "patient_id": body.patient_id,
        "title": body.title,
        "primary_concern": body.primary_concern,
        "goals": body.goals or [],
        "interventions": body.interventions or [],
        "status": body.status or "active",
    }
    row = get_manager().db_client.insert("treatment_plans", payload)
    return row

@router.patch("/treatment-plans/{plan_id}")
def plans_update(plan_id: str, body: TreatmentPlanUpdateRequest, request: Request):
    user = _require_therapist(request)
    therapist_id = str(user["id"])
    existing = _select_optional_table("treatment_plans", filters={"plan_id": f"eq.{plan_id}", "therapist_id": f"eq.{therapist_id}"})
    if not existing:
        raise HTTPException(status_code=404, detail={"message": "Plan not found."})
    updates = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    updates["updated_at"] = datetime.utcnow().isoformat()
    get_manager().db_client.update("treatment_plans", updates, {"plan_id": f"eq.{plan_id}"})
    refreshed = _select_optional_table("treatment_plans", filters={"plan_id": f"eq.{plan_id}"})
    return refreshed[0] if refreshed else {"plan_id": plan_id}

# =======================================================================
# Clinical: Homework (therapist-side + patient-side endpoints)
# =======================================================================

@router.get("/homework")
def homework_list_therapist(request: Request):
    user = _require_therapist(request)
    therapist_id = str(user["id"])
    patient_id = request.query_params.get("patient_id")
    filters = {"therapist_id": f"eq.{therapist_id}"}
    if patient_id:
        _require_link(therapist_id, patient_id)
        filters["patient_id"] = f"eq.{patient_id}"
    rows = _select_optional_table("patient_homework", filters=filters)
    rows.sort(key=lambda r: str(r.get("due_at") or r.get("created_at") or ""), reverse=True)
    return {"homework": rows}

@router.post("/homework")
def homework_assign(body: HomeworkAssignRequest, request: Request):
    user = _require_therapist(request)
    therapist_id = str(user["id"])
    _require_link(therapist_id, body.patient_id)
    payload = {
        "therapist_id": therapist_id,
        "patient_id": body.patient_id,
        "plan_id": body.plan_id,
        "title": body.title,
        "description": body.description,
        "due_at": body.due_at.isoformat() if body.due_at else None,
        "status": "assigned",
    }
    row = get_manager().db_client.insert("patient_homework", payload)
    return row

@public_router.patch("/api/patient/homework/{homework_id}")
@router.patch("/homework/{homework_id}")
def homework_update_any(homework_id: str, body: HomeworkUpdateRequest, request: Request):
    """Both therapist (owner) and patient (recipient) can update status/reflection."""
    user = require_user(request)
    viewer = str(user["id"])
    existing = _select_optional_table("patient_homework", filters={"homework_id": f"eq.{homework_id}"})
    if not existing:
        raise HTTPException(status_code=404, detail={"message": "Homework not found."})
    row = existing[0]
    hw_therapist = str(row.get("therapist_id") or "")
    hw_patient = str(row.get("patient_id") or "")
    if viewer not in {hw_therapist, hw_patient}:
        raise HTTPException(status_code=403, detail={"message": "Not authorized."})
    # Verify the therapist-patient link is still active before allowing updates
    if not _active_link(hw_therapist, hw_patient):
        raise HTTPException(status_code=403, detail={"message": "Therapist-patient link is no longer active."})

    updates = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if body.due_at:
        updates["due_at"] = body.due_at.isoformat()
    if updates.get("status") == "completed":
        updates["completed_at"] = datetime.utcnow().isoformat()
    updates["updated_at"] = datetime.utcnow().isoformat()

    # Patients cannot reassign/retitle, only update status/reflection
    if viewer == str(row.get("patient_id")):
        allowed = {"status", "patient_reflection", "completed_at", "updated_at"}
        updates = {k: v for k, v in updates.items() if k in allowed}

    get_manager().db_client.update("patient_homework", updates, {"homework_id": f"eq.{homework_id}"})
    refreshed = _select_optional_table("patient_homework", filters={"homework_id": f"eq.{homework_id}"})
    return refreshed[0] if refreshed else row

@shared_router.get("/api/patient/homework")
@public_router.get("/api/patient/homework")
def homework_list_patient(request: Request):
    user = require_user(request)
    patient_id = str(user["id"])
    rows = _select_optional_table("patient_homework", filters={"patient_id": f"eq.{patient_id}"})
    rows.sort(key=lambda r: str(r.get("due_at") or r.get("created_at") or ""), reverse=True)

    # Enrich with therapist display name
    therapist_ids = {str(r.get("therapist_id")) for r in rows if r.get("therapist_id")}
    if therapist_ids:
        tprofs = _select_optional_table("therapist_profiles")
        by_tid = {str(t.get("therapist_user_id")): t for t in tprofs}
        for r in rows:
            tp = by_tid.get(str(r.get("therapist_id")))
            if tp:
                r["therapist_name"] = tp.get("display_name") or tp.get("title")
    return {"homework": rows}

# =======================================================================
# Invitations & linking
# =======================================================================

@shared_router.post("/api/invite-therapist")
@public_router.post("/api/invite-therapist")
def patient_invite_therapist(body: InviteRequest, request: Request):
    user = require_user(request)
    if str(user.get("role") or "").lower() != "patient":
        raise HTTPException(status_code=403, detail={"message": "Only patients can invite therapists here."})
    return _create_invite_or_request(
        inviter=user,
        email=body.email,
        invite_type="patient_invites_therapist",
        expect_role="therapist",
    )

@router.post("/invite-patient")
def therapist_invite_patient(body: InviteRequest, request: Request):
    user = _require_therapist(request)
    return _create_invite_or_request(
        inviter=user,
        email=body.email,
        invite_type="therapist_invites_patient",
        expect_role="patient",
    )

def _create_invite_or_request(inviter: dict, email: str, invite_type: str, expect_role: str) -> dict:
    email_clean = (email or "").strip().lower()
    if not email_clean or "@" not in email_clean:
        raise HTTPException(status_code=400, detail={"message": "Valid email required."})
    inviter_id = str(inviter["id"])
    mgr = get_manager()

    # Does this email already belong to a user?
    existing = _user_by_email(email_clean)
    if existing:
        other_id = str(existing.get("user_id"))
        other_role = str(existing.get("role") or "").lower()
        if other_id == inviter_id:
            raise HTTPException(status_code=400, detail={"message": "You cannot invite yourself."})
        if expect_role and other_role != expect_role:
            raise HTTPException(status_code=400, detail={
                "message": f"That account exists but is not a {expect_role}. Current role: {other_role or 'unknown'}.",
            })

        patient_id = inviter_id if invite_type == "patient_invites_therapist" else other_id
        therapist_id = other_id if invite_type == "patient_invites_therapist" else inviter_id

        # Already linked?
        existing_link = _select_optional_table(
            "patient_therapist_links",
            filters={"patient_id": f"eq.{patient_id}", "therapist_id": f"eq.{therapist_id}"},
        )
        for lk in existing_link:
            status = lk.get("status")
            if status == "active":
                raise HTTPException(status_code=400, detail={"message": "You are already linked."})
            if status in {"pending_therapist", "pending_patient"}:
                raise HTTPException(status_code=400, detail={"message": "A request is already pending."})

        now = datetime.utcnow().isoformat()
        initial_status = "pending_therapist" if invite_type == "patient_invites_therapist" else "pending_patient"
        payload = {
            "patient_id": patient_id,
            "therapist_id": therapist_id,
            "status": initial_status,
            "initiated_by": inviter_id,
            "created_at": now,
            "updated_at": now,
        }
        if invite_type == "patient_invites_therapist":
            # Patient has already expressed intent — therapist must accept first,
            # then patient confirms consent scopes in consent step.
            payload["patient_consented_at"] = None  # set on final confirm-consent
        link = mgr.db_client.insert("patient_therapist_links", payload)
        return {
            "mode": "request",
            "status": initial_status,
            "link": link,
            "message": "Request sent. Waiting for the other party to accept.",
        }

    # Email invite to a non-user
    token = secrets.token_urlsafe(24)
    expires = (datetime.utcnow() + timedelta(days=14)).isoformat()
    try:
        invite = mgr.db_client.insert(
            "therapist_invites",
            {
                "token": token,
                "inviter_user_id": inviter_id,
                "invitee_email": email_clean,
                "invite_type": invite_type,
                "status": "pending",
                "expires_at": expires,
            },
        )
    except Exception as exc:
        if _is_missing_table_error(exc):
            raise HTTPException(status_code=503, detail={"message": "therapist_invites table missing."})
        raise
    logger.info(f"[INVITE] token={token} email={email_clean} type={invite_type}")
    return {
        "mode": "email_invite",
        "status": "pending",
        "invite": invite,
        "message": "Invite created. Share the link below with them.",
        "accept_url": f"/invite/accept?token={token}",
    }

@shared_router.get("/api/links/pending")
@public_router.get("/api/links/pending")
def links_pending(request: Request):
    user = require_user(request)
    uid = str(user["id"])
    role = str(user.get("role") or "").lower()
    if role == "therapist":
        rows = _select_optional_table(
            "patient_therapist_links",
            filters={"therapist_id": f"eq.{uid}", "status": "eq.pending_therapist"},
        )
    else:
        rows = _select_optional_table(
            "patient_therapist_links",
            filters={"patient_id": f"eq.{uid}", "status": "eq.pending_patient"},
        )
        # Also surface pending_therapist links initiated by the patient for display
        own_pending = _select_optional_table(
            "patient_therapist_links",
            filters={"patient_id": f"eq.{uid}", "status": "eq.pending_therapist"},
        )
        rows = (rows or []) + (own_pending or [])

    enriched = []
    for link in rows:
        counterparty = _link_counterparty(link, uid)
        enriched.append({**link, "counterparty": counterparty})
    return {"links": enriched}

@shared_router.get("/api/links")
@public_router.get("/api/links")
def links_all(request: Request):
    """All links for the current user, any status."""
    user = require_user(request)
    uid = str(user["id"])
    role = str(user.get("role") or "").lower()
    filt = {"therapist_id": f"eq.{uid}"} if role == "therapist" else {"patient_id": f"eq.{uid}"}
    rows = _select_optional_table("patient_therapist_links", filters=filt)
    rows.sort(key=lambda r: str(r.get("updated_at") or r.get("created_at") or ""), reverse=True)
    enriched = [{**r, "counterparty": _link_counterparty(r, uid)} for r in rows]
    return {"links": enriched}

@shared_router.post("/api/links/{link_id}/accept")
@public_router.post("/api/links/{link_id}/accept")
def links_accept(link_id: str, request: Request):
    """The party currently in 'pending_*' accepts. For patient-initiated:
    therapist accepts (moves to pending_patient for consent confirmation).
    For therapist-initiated: patient accepts (moves to pending_patient then
    immediately awaits explicit consent via /confirm-consent).
    """
    user = require_user(request)
    uid = str(user["id"])
    rows = _select_optional_table("patient_therapist_links", filters={"link_id": f"eq.{link_id}"})
    if not rows:
        raise HTTPException(status_code=404, detail={"message": "Link not found."})
    link = rows[0]
    status = link.get("status")
    now = datetime.utcnow().isoformat()
    updates: Dict[str, Any] = {"updated_at": now}

    if status == "pending_therapist":
        if str(link.get("therapist_id")) != uid:
            raise HTTPException(status_code=403, detail={"message": "Not authorized to accept."})
        updates["therapist_consented_at"] = now
        updates["status"] = "pending_patient"
    elif status == "pending_patient":
        if str(link.get("patient_id")) != uid:
            raise HTTPException(status_code=403, detail={"message": "Not authorized to accept."})
        # Patient accept requires explicit consent via /confirm-consent to activate.
        updates["patient_consented_at"] = None  # still need consent scope
        updates["status"] = "pending_patient"
        return {"message": "Please confirm data-sharing consent to activate the link.", "link": {**link, **updates}}
    else:
        raise HTTPException(status_code=400, detail={"message": f"Link is not pending (status={status})."})

    get_manager().db_client.update("patient_therapist_links", updates, {"link_id": f"eq.{link_id}"})
    refreshed = _select_optional_table("patient_therapist_links", filters={"link_id": f"eq.{link_id}"})
    return {"link": refreshed[0] if refreshed else {**link, **updates}}

@shared_router.post("/api/links/{link_id}/decline")
@public_router.post("/api/links/{link_id}/decline")
def links_decline(link_id: str, request: Request):
    user = require_user(request)
    uid = str(user["id"])
    rows = _select_optional_table("patient_therapist_links", filters={"link_id": f"eq.{link_id}"})
    if not rows:
        raise HTTPException(status_code=404, detail={"message": "Link not found."})
    link = rows[0]
    if uid not in {str(link.get("patient_id")), str(link.get("therapist_id"))}:
        raise HTTPException(status_code=403, detail={"message": "Not authorized."})
    get_manager().db_client.update(
        "patient_therapist_links",
        {"status": "declined", "updated_at": datetime.utcnow().isoformat()},
        {"link_id": f"eq.{link_id}"},
    )
    return {"declined": True, "link_id": link_id}

@shared_router.post("/api/links/{link_id}/confirm-consent")
@public_router.post("/api/links/{link_id}/confirm-consent")
def links_confirm_consent(link_id: str, body: ConsentConfirmRequest, request: Request):
    """Patient confirms consent with scopes. Activates the link."""
    user = require_user(request)
    if str(user.get("role") or "").lower() != "patient":
        raise HTTPException(status_code=403, detail={"message": "Only patients confirm consent."})
    uid = str(user["id"])
    rows = _select_optional_table("patient_therapist_links", filters={"link_id": f"eq.{link_id}"})
    if not rows:
        raise HTTPException(status_code=404, detail={"message": "Link not found."})
    link = rows[0]
    if str(link.get("patient_id")) != uid:
        raise HTTPException(status_code=403, detail={"message": "Not your link."})
    if link.get("status") not in {"pending_patient", "pending_therapist"}:
        raise HTTPException(status_code=400, detail={"message": "Link is not awaiting patient consent."})

    consent = body.consent_scope or {
        "conversations": True, "journals": True, "mood": True,
        "reports": True, "personality": True,
    }
    now = datetime.utcnow().isoformat()
    updates = {
        "consent_scope": consent,
        "patient_consented_at": now,
        "updated_at": now,
    }
    # Only activate if therapist already accepted
    if link.get("therapist_consented_at") or link.get("status") == "pending_patient":
        updates["status"] = "active"
    get_manager().db_client.update("patient_therapist_links", updates, {"link_id": f"eq.{link_id}"})
    refreshed = _select_optional_table("patient_therapist_links", filters={"link_id": f"eq.{link_id}"})
    return {"link": refreshed[0] if refreshed else {**link, **updates}}

@shared_router.post("/api/links/{link_id}/revoke")
@public_router.post("/api/links/{link_id}/revoke")
def links_revoke(link_id: str, body: LinkRevokeRequest, request: Request):
    user = require_user(request)
    uid = str(user["id"])
    rows = _select_optional_table("patient_therapist_links", filters={"link_id": f"eq.{link_id}"})
    if not rows:
        raise HTTPException(status_code=404, detail={"message": "Link not found."})
    link = rows[0]
    if uid not in {str(link.get("patient_id")), str(link.get("therapist_id"))}:
        raise HTTPException(status_code=403, detail={"message": "Not authorized."})
    now = datetime.utcnow().isoformat()
    get_manager().db_client.update(
        "patient_therapist_links",
        {
            "status": "revoked",
            "revoked_at": now,
            "revoked_by": uid,
            "revoke_reason": body.reason,
            "updated_at": now,
        },
        {"link_id": f"eq.{link_id}"},
    )
    return {"revoked": True, "link_id": link_id}

@shared_router.get("/api/invite/info")
@public_router.get("/api/invite/info")
def invite_info(request: Request):
    token = request.query_params.get("token")
    if not token:
        raise HTTPException(status_code=400, detail={"message": "Missing token."})
    rows = _select_optional_table("therapist_invites", filters={"token": f"eq.{token}"})
    if not rows:
        raise HTTPException(status_code=404, detail={"message": "Invite not found or expired."})
    invite = rows[0]
    inviter = _select_optional_table("user_profiles", filters={"user_id": f"eq.{invite.get('inviter_user_id')}"})
    invite["inviter"] = _user_summary(inviter[0]) if inviter else None
    return invite

@shared_router.post("/api/invite/accept")
@public_router.post("/api/invite/accept")
def invite_accept(request: Request, body: dict = {}):
    token = (body or {}).get("token") or request.query_params.get("token")
    if not token:
        raise HTTPException(status_code=400, detail={"message": "Missing token."})
    user = require_user(request)
    uid = str(user["id"])
    rows = _select_optional_table("therapist_invites", filters={"token": f"eq.{token}"})
    if not rows:
        raise HTTPException(status_code=404, detail={"message": "Invite not found."})
    invite = rows[0]
    if invite.get("status") != "pending":
        raise HTTPException(status_code=400, detail={"message": f"Invite status: {invite.get('status')}"})

    inviter_id = str(invite.get("inviter_user_id"))
    invite_type = invite.get("invite_type")
    now = datetime.utcnow().isoformat()

    patient_id = inviter_id if invite_type == "patient_invites_therapist" else uid
    therapist_id = uid if invite_type == "patient_invites_therapist" else inviter_id

    mgr = get_manager()
    mgr.db_client.update(
        "therapist_invites",
        {"status": "accepted", "accepted_user_id": uid, "accepted_at": now},
        {"invite_id": f"eq.{invite.get('invite_id')}"},
    )
    link = mgr.db_client.insert(
        "patient_therapist_links",
        {
            "patient_id": patient_id,
            "therapist_id": therapist_id,
            "status": "pending_patient",
            "initiated_by": inviter_id,
            "therapist_consented_at": now if therapist_id == uid or invite_type == "therapist_invites_patient" else None,
            "created_at": now,
            "updated_at": now,
        },
    )
    return {"link": link, "message": "Invite accepted. Patient must confirm consent."}

# =======================================================================
# Messaging
# =======================================================================

@router.post("/messages")
def messages_send(body: MessageSendRequest, request: Request):
    user = require_user(request)
    uid = str(user["id"])
    rows = _select_optional_table("patient_therapist_links", filters={"link_id": f"eq.{body.link_id}", "status": "eq.active"})
    if not rows:
        raise HTTPException(status_code=403, detail={"message": "No active link."})
    link = rows[0]
    if uid not in {str(link.get("patient_id")), str(link.get("therapist_id"))}:
        raise HTTPException(status_code=403, detail={"message": "Not authorized."})
    recipient = str(link.get("therapist_id") if str(link.get("patient_id")) == uid else link.get("patient_id"))
    thread_id = str(link.get("link_id"))
    urgency = body.urgency if body.urgency in {"normal", "priority", "urgent"} else "normal"
    msg = get_manager().db_client.insert(
        "therapist_messages",
        {
            "thread_id": thread_id,
            "link_id": body.link_id,
            "sender_id": uid,
            "recipient_id": recipient,
            "body": body.body,
            "urgency": urgency,
        },
    )
    return msg

@router.get("/messages")
def messages_thread(request: Request):
    user = require_user(request)
    uid = str(user["id"])
    link_id = request.query_params.get("link_id")
    if not link_id:
        # Return thread summary list for the user
        role = str(user.get("role") or "").lower()
        links_filt = {"therapist_id": f"eq.{uid}"} if role == "therapist" else {"patient_id": f"eq.{uid}"}
        active_links = _select_optional_table("patient_therapist_links", filters={**links_filt, "status": "eq.active"})
        threads = []
        for lk in active_links:
            msgs = _select_optional_table("therapist_messages", filters={"link_id": f"eq.{lk.get('link_id')}"})
            msgs_sorted = sorted(msgs, key=lambda m: str(m.get("created_at") or ""), reverse=True)
            last = msgs_sorted[0] if msgs_sorted else None
            unread = sum(1 for m in msgs if str(m.get("recipient_id")) == uid and not m.get("read_at"))
            threads.append({
                "link_id": lk.get("link_id"),
                "counterparty": _link_counterparty(lk, uid),
                "last_message": last,
                "unread_count": unread,
            })
        threads.sort(key=lambda t: str((t.get("last_message") or {}).get("created_at") or ""), reverse=True)
        return {"threads": threads}

    rows = _select_optional_table("patient_therapist_links", filters={"link_id": f"eq.{link_id}"})
    if not rows:
        raise HTTPException(status_code=404, detail={"message": "Link not found."})
    link = rows[0]
    if uid not in {str(link.get("patient_id")), str(link.get("therapist_id"))}:
        raise HTTPException(status_code=403, detail={"message": "Not authorized."})
    msgs = _select_optional_table("therapist_messages", filters={"link_id": f"eq.{link_id}"})
    msgs.sort(key=lambda m: str(m.get("created_at") or ""))
    return {"messages": msgs, "counterparty": _link_counterparty(link, uid)}

@router.post("/messages/{message_id}/read")
def messages_mark_read(message_id: str, request: Request):
    user = require_user(request)
    uid = str(user["id"])
    rows = _select_optional_table("therapist_messages", filters={"message_id": f"eq.{message_id}"})
    if not rows:
        raise HTTPException(status_code=404, detail={"message": "Message not found."})
    msg = rows[0]
    if str(msg.get("recipient_id")) != uid:
        raise HTTPException(status_code=403, detail={"message": "Not the recipient."})
    if not msg.get("read_at"):
        get_manager().db_client.update(
            "therapist_messages",
            {"read_at": datetime.utcnow().isoformat()},
            {"message_id": f"eq.{message_id}"},
        )
    return {"read": True, "message_id": message_id}

# =======================================================================
# Crisis
# =======================================================================

@router.get("/crisis")
def crisis_list(request: Request, patient_id: Optional[str] = None):
    user = _require_therapist(request)
    therapist_id = str(user["id"])
    links = _select_optional_table(
        "patient_therapist_links",
        filters={"therapist_id": f"eq.{therapist_id}", "status": "eq.active"},
    )
    linked_ids = {str(lk.get("patient_id")) for lk in links}
    if not linked_ids:
        return {"events": []}
    if patient_id:
        if patient_id not in linked_ids:
            raise HTTPException(status_code=403, detail={"message": "Patient not linked to this therapist."})
        scope_ids = [patient_id]
    else:
        scope_ids = list(linked_ids)
    mine: List[dict] = []
    for pid in scope_ids:
        rows = _select_optional_table("crisis_events", filters={"patient_id": f"eq.{pid}"})
        mine.extend(rows)
    # Hide synthetic test-alert events — they are patient-initiated flow checks, not clinical events.
    mine = [e for e in mine if (e.get("intervention_type") or "") != "test_alert"]
    mine.sort(key=lambda c: str(c.get("created_at") or ""), reverse=True)
    return {"events": mine}

@router.post("/crisis/escalate")
def crisis_escalate(body: CrisisEscalateRequest, request: Request):
    from crisis.service import emergency_resources
    user = _require_therapist(request)
    therapist_id = str(user["id"])
    _require_link(therapist_id, body.patient_id)
    now = datetime.utcnow().isoformat()
    event = get_manager().db_client.insert(
        "crisis_events",
        {
            "patient_id": body.patient_id,
            "therapist_id": therapist_id,
            "triggered_by": "therapist",
            "severity": body.severity or "high",
            "context": {"notes": body.notes} if body.notes else {},
            "escalated_at": now,
        },
    )
    resources = emergency_resources(body.locale or "US")
    return {"event": event, "resources": resources}

@router.post("/crisis/{event_id}/resolve")
def crisis_resolve(event_id: str, request: Request):
    user = _require_therapist(request)
    therapist_id = str(user["id"])
    rows = _select_optional_table("crisis_events", filters={"event_id": f"eq.{event_id}"})
    if not rows:
        raise HTTPException(status_code=404, detail={"message": "Event not found."})
    event = rows[0]
    _require_link(therapist_id, str(event.get("patient_id")))
    now = datetime.utcnow().isoformat()
    get_manager().db_client.update(
        "crisis_events",
        {"resolved_at": now, "therapist_id": therapist_id},
        {"event_id": f"eq.{event_id}"},
    )
    return {"resolved": True, "event_id": event_id}

# =======================================================================
# Reports & Feedback (extending existing)
# =======================================================================

@shared_router.post("/api/reports")
@public_router.post("/api/reports")
def reports_submit(body: ReportSubmitRequest, request: Request):
    user = require_user(request)
    uid = str(user["id"])
    priority = body.priority if body.priority in {"low", "medium", "high", "urgent"} else "medium"
    payload = {
        "reporter_user_id": uid,
        "reported_user_id": body.reported_user_id,
        "category": body.category,
        "description": body.description,
        "priority": priority,
        "status": "open",
    }
    try:
        row = get_manager().db_client.insert("moderation_reports", payload)
    except Exception as exc:
        if _is_missing_table_error(exc):
            raise HTTPException(status_code=503, detail={"message": "moderation_reports table missing."})
        raise
    return row

@shared_router.post("/api/feedback")
@public_router.post("/api/feedback")
def feedback_submit(body: FeedbackSubmitRequest, request: Request):
    user = require_user(request)
    uid = str(user["id"])
    payload = {
        "user_id": uid,
        "target_therapist_id": body.target_therapist_id,
        "rating": body.rating,
        "comment": body.comment,
        "feedback_type": body.feedback_type or ("therapist" if body.target_therapist_id else "product"),
        "status": "open",
    }
    try:
        row = get_manager().db_client.insert("platform_feedback", payload)
    except Exception as exc:
        if _is_missing_table_error(exc):
            raise HTTPException(status_code=503, detail={"message": "platform_feedback table missing."})
        raise
    return row

@router.get("/feedback/me")
def therapist_feedback_for_me(request: Request):
    user = _require_therapist(request)
    therapist_id = str(user["id"])
    rows = _select_optional_table("platform_feedback", filters={"target_therapist_id": f"eq.{therapist_id}"})
    rows.sort(key=lambda r: str(r.get("created_at") or ""), reverse=True)
    return {"feedback": rows}

# =======================================================================
# PDF Export
# =======================================================================

@router.get("/patients/{patient_id}/export.pdf")
def export_patient_pdf(patient_id: str, request: Request):
    user = _require_therapist(request)
    therapist_id = str(user["id"])
    _require_link(therapist_id, patient_id)
    _log_access(therapist_id, patient_id, "export", "pdf")

    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
        from reportlab.lib.units import inch
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail={"message": "PDF export requires 'reportlab'. Run: pip install reportlab"},
        )

    profile = _get_profile_persistent(patient_id)
    notes = _select_optional_table("therapist_notes", filters={"therapist_id": f"eq.{therapist_id}", "patient_id": f"eq.{patient_id}"})
    plans = _select_optional_table("treatment_plans", filters={"therapist_id": f"eq.{therapist_id}", "patient_id": f"eq.{patient_id}"})
    summaries = _select_optional_table("session_summaries", filters={"patient_id": f"eq.{patient_id}"})
    summaries.sort(key=lambda s: str(s.get("generated_at") or ""), reverse=True)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, title=f"Patient Record — {profile.get('name','')}")
    styles = getSampleStyleSheet()
    h1 = styles["Heading1"]
    h2 = styles["Heading2"]
    normal = styles["BodyText"]

    story = []
    story.append(Paragraph("Patient Record", h1))
    story.append(Paragraph(f"<b>Name:</b> {profile.get('name','')} &nbsp; <b>Email:</b> {profile.get('email','')}", normal))
    story.append(Paragraph(f"<b>Generated:</b> {datetime.utcnow().isoformat()}", normal))
    story.append(Spacer(1, 0.2 * inch))

    story.append(Paragraph("Treatment Plans", h2))
    if not plans:
        story.append(Paragraph("No active plans.", normal))
    for p in plans:
        story.append(Paragraph(f"<b>{p.get('title','Plan')}</b> — {p.get('status','')}", normal))
        if p.get("primary_concern"):
            story.append(Paragraph(f"Primary concern: {p.get('primary_concern')}", normal))
        if p.get("interventions"):
            story.append(Paragraph(f"Interventions: {', '.join(p.get('interventions') or [])}", normal))
        story.append(Spacer(1, 0.1 * inch))

    story.append(PageBreak())
    story.append(Paragraph("Session Summaries (AI-generated — review before clinical use)", h2))
    if not summaries:
        story.append(Paragraph("No session summaries.", normal))
    for s in summaries[:10]:
        story.append(Paragraph(f"<b>{s.get('generated_at','')}</b>", normal))
        for field in ("subjective", "objective", "assessment", "plan"):
            if s.get(field):
                story.append(Paragraph(f"<b>{field.title()}:</b> {s.get(field)}", normal))
        story.append(Spacer(1, 0.15 * inch))

    story.append(PageBreak())
    story.append(Paragraph("Clinical Notes (private)", h2))
    if not notes:
        story.append(Paragraph("No notes.", normal))
    for n in sorted(notes, key=lambda x: str(x.get("created_at") or ""), reverse=True):
        story.append(Paragraph(f"<b>{n.get('created_at','')}</b> — Tags: {', '.join(n.get('tags') or [])}", normal))
        story.append(Paragraph(n.get("body", ""), normal))
        story.append(Spacer(1, 0.15 * inch))

    doc.build(story)
    buf.seek(0)
    headers = {"Content-Disposition": f"attachment; filename=patient-{patient_id[:8]}.pdf"}
    return Response(content=buf.getvalue(), media_type="application/pdf", headers=headers)

# =======================================================================
# Patient-side read endpoints (therapists the patient has linked)
# =======================================================================

@shared_router.get("/api/patient/therapists")
@public_router.get("/api/patient/therapists")
def patient_therapists(request: Request):
    user = require_user(request)
    uid = str(user["id"])
    rows = _select_optional_table("patient_therapist_links", filters={"patient_id": f"eq.{uid}"})
    rows.sort(key=lambda r: str(r.get("updated_at") or ""), reverse=True)
    enriched = [{**r, "therapist": _link_counterparty(r, uid)} for r in rows]
    return {"links": enriched}

@shared_router.get("/api/patient/access-log")
@public_router.get("/api/patient/access-log")
def patient_access_log(request: Request):
    user = require_user(request)
    uid = str(user["id"])
    rows = _select_optional_table("clinical_access_logs", filters={"patient_id": f"eq.{uid}"})
    rows.sort(key=lambda r: str(r.get("created_at") or ""), reverse=True)
    # Enrich with therapist display names
    tids = {str(r.get("therapist_id")) for r in rows}
    tprofs = _select_optional_table("therapist_profiles")
    by_tid = {str(t.get("therapist_user_id")): t for t in tprofs}
    for r in rows:
        tp = by_tid.get(str(r.get("therapist_id")))
        if tp:
            r["therapist_name"] = tp.get("display_name")
    return {"logs": rows[:200]}

# =======================================================================
# Auto-summary helper (called from end_session hook in api.py)
# =======================================================================

def _generate_and_store_summary(patient_id: str, conv_id: str, messages: List[dict]) -> dict:
    from conversation.summary import generate_soap_summary
    from crisis.service import scan_messages
    mgr = get_manager()
    summary = generate_soap_summary(getattr(mgr, "llm", None), messages)
    risk = scan_messages(messages)

    payload = {
        "conversation_id": conv_id,
        "patient_id": patient_id,
        **{k: summary.get(k) for k in ("subjective", "objective", "assessment", "plan",
                                         "themes", "action_items", "mood_trajectory",
                                         "generated_by", "generated_at")},
        "risk_flags": risk,
    }
    try:
        row = mgr.db_client.insert("session_summaries", payload)
    except Exception as exc:
        if _is_missing_table_error(exc):
            logger.warning("session_summaries table missing.")
            return payload
        # If already exists (unique on conversation_id) — update
        try:
            mgr.db_client.update(
                "session_summaries",
                {k: v for k, v in payload.items() if k != "conversation_id"},
                {"conversation_id": f"eq.{conv_id}"},
            )
            existing = _select_optional_table("session_summaries", filters={"conversation_id": f"eq.{conv_id}"})
            row = existing[0] if existing else payload
        except Exception:
            raise

    # If high/critical — create crisis_event and notify therapist(s)
    if risk.get("flagged") and risk.get("severity") in {"high", "critical"}:
        try:
            event = mgr.db_client.insert(
                "crisis_events",
                {
                    "patient_id": patient_id,
                    "triggered_by": "rule_engine",
                    "severity": risk.get("severity", "high"),
                    "context": {"conversation_id": conv_id, "categories": risk.get("categories"), "snippets": risk.get("snippets")},
                },
            )
            # Notify linked therapists
            links = _select_optional_table(
                "patient_therapist_links",
                filters={"patient_id": f"eq.{patient_id}", "status": "eq.active"},
            )
            for lk in links:
                try:
                    mgr.db_client.insert(
                        "therapist_messages",
                        {
                            "thread_id": str(lk.get("link_id")),
                            "link_id": str(lk.get("link_id")),
                            "sender_id": patient_id,
                            "recipient_id": str(lk.get("therapist_id")),
                            "body": f"⚠ Risk signal detected ({risk.get('severity')}). Review session {conv_id}.",
                            "urgency": "urgent",
                            "is_system": True,
                        },
                    )
                except Exception:
                    pass
        except Exception as exc:
            logger.warning(f"Crisis event write failed: {exc}")

    return row if isinstance(row, dict) else payload

# Expose the helper at module-level for the end-session hook

