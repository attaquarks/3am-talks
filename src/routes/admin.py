"""
routes/admin.py — Platform administration and analytics endpoints.
"""
from __future__ import annotations

import datetime as dt
from datetime import datetime
from typing import Optional, Dict

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from core.helpers import (
    ALLOWED_ACCOUNT_STATUSES,
    ALLOWED_ROLES,
    _build_user_metrics_by_user,
    _coerce_role,
    _ensure_admin_id,
    _get_account_status,
    _get_profile_persistent,
    _log_admin_action,
    _parse_iso_datetime,
    _require_confirm_token,
    _select_optional_table,
    _is_missing_table_error,
    get_manager,
    require_admin,
)
from core.sessions import clear_user_sessions, update_user_sessions
from database import normalize_postgrest_value

import logging
logger = logging.getLogger("3am-admin")
router = APIRouter()

class AdminUserStatusUpdateRequest(BaseModel):
    status: Optional[str] = None
    reason: Optional[str] = None
    suspended_until: Optional[datetime] = None
    confirm: Optional[str] = None

class AdminUserRoleUpdateRequest(BaseModel):
    role: Optional[str] = None
    reason: Optional[str] = None
    confirm: Optional[str] = None

class AdminUserDeleteRequest(BaseModel):
    reason: Optional[str] = None
    confirm: Optional[str] = None

class AdminReportUpdateRequest(BaseModel):
    status: Optional[str] = None

class AdminFeedbackUpdateRequest(BaseModel):
    status: Optional[str] = None

class TherapistVerificationReviewRequest(BaseModel):
    status: Optional[str] = None
    review_notes: Optional[str] = None

class AnnouncementCreateRequest(BaseModel):
    title: str
    body: str
    audience: Optional[str] = "all"
    expires_at: Optional[datetime] = None


@router.get("/api/admin/overview")
def admin_overview(request: Request):
    """Platform-level admin analytics and queue overview."""
    require_admin(request)

    profiles = _select_optional_table("user_profiles")
    reports = _select_optional_table("moderation_reports")
    feedback = _select_optional_table("platform_feedback")
    conversations = _select_optional_table("conversations")

    now = datetime.utcnow()
    seven_days_ago = now - dt.timedelta(days=7)

    role_counts = {"patient": 0, "therapist": 0, "admin": 0}
    status_counts = {"active": 0, "suspended": 0, "banned": 0}
    new_users_7d = 0

    for profile in profiles:
        role = _coerce_role(profile.get("role"))
        status = _get_account_status(profile)
        role_counts[role] = role_counts.get(role, 0) + 1
        status_counts[status] = status_counts.get(status, 0) + 1

        created_at = _parse_iso_datetime(profile.get("created_at"))
        if created_at and created_at.replace(tzinfo=None) >= seven_days_ago:
            new_users_7d += 1

    conversations_7d = 0
    total_minutes_7d = 0
    for conv in conversations:
        created_at = _parse_iso_datetime(conv.get("created_at"))
        if created_at and created_at.replace(tzinfo=None) >= seven_days_ago:
            conversations_7d += 1
            total_minutes_7d += int(conv.get("duration_minutes") or 0)

    open_report_statuses = {"open", "in_review"}
    pending_feedback_statuses = {"open"}
    open_reports = [r for r in reports if str(r.get("status") or "open").lower() in open_report_statuses]
    pending_feedback = [f for f in feedback if str(f.get("status") or "open").lower() in pending_feedback_statuses]

    recent_reports = sorted(reports, key=lambda r: str(r.get("created_at") or ""), reverse=True)[:5]
    recent_feedback = sorted(feedback, key=lambda f: str(f.get("created_at") or ""), reverse=True)[:5]

    return {
        "total_users": len(profiles),
        "role_counts": role_counts,
        "status_counts": status_counts,
        "new_users_7d": new_users_7d,
        "conversations_7d": conversations_7d,
        "total_minutes_7d": total_minutes_7d,
        "open_reports": len(open_reports),
        "pending_feedback": len(pending_feedback),
        "recent_reports": recent_reports,
        "recent_feedback": recent_feedback,
    }


@router.get("/api/admin/users")
def admin_users(request: Request):
    """List users across the platform for admin oversight."""
    require_admin(request)

    role_filter = str(request.query_params.get("role") or "all").lower()
    status_filter = str(request.query_params.get("status") or "all").lower()
    search = str(request.query_params.get("search") or "").strip().lower()

    profiles = _select_optional_table("user_profiles")
    metrics_by_user = _build_user_metrics_by_user()

    users = []
    for profile in profiles:
        user_id = str(profile.get("user_id") or "")
        if not user_id:
            continue

        role = _coerce_role(profile.get("role"))
        account_status = _get_account_status(profile)

        if role_filter != "all" and role != role_filter:
            continue
        if status_filter != "all" and account_status != status_filter:
            continue

        name = str(profile.get("name") or "User")
        email = str(profile.get("email") or "")
        haystack = f"{name} {email} {user_id}".lower()
        if search and search not in haystack:
            continue

        metrics = metrics_by_user.get(user_id, {
            "total_sessions": 0,
            "total_minutes": 0,
            "mood_improvement_percentage": 0,
            "last_session_date": None,
        })

        users.append({
            "user_id": user_id,
            "name": name,
            "email": email,
            "role": role,
            "account_status": account_status,
            "suspended_until": profile.get("suspended_until"),
            "status_reason": profile.get("status_reason"),
            "created_at": profile.get("created_at"),
            "updated_at": profile.get("updated_at"),
            "total_sessions": int(metrics.get("total_sessions") or 0),
            "total_minutes": int(metrics.get("total_minutes") or 0),
            "mood_improvement_percentage": int(metrics.get("mood_improvement_percentage") or 0),
            "last_session_date": metrics.get("last_session_date"),
        })

    users_sorted = sorted(users, key=lambda u: str(u.get("created_at") or ""), reverse=True)
    return {
        "users": users_sorted,
        "total": len(users_sorted),
    }


@router.patch("/api/admin/users/{target_user_id}/status")
def admin_update_user_status(target_user_id: str, body: AdminUserStatusUpdateRequest, request: Request):
    """Suspend, ban, or reactivate platform users."""
    admin_user = require_admin(request)
    admin_user_id = str(admin_user["id"])
    admin_id = admin_user.get("admin_id")

    status = str(body.status or "").lower()
    if status not in ALLOWED_ACCOUNT_STATUSES:
        raise HTTPException(status_code=400, detail={"message": "Invalid status. Use active, suspended, or banned."})

    reason = (body.reason or "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail={"message": "A reason is required for this action."})

    _require_confirm_token(body.confirm)

    normalized_target = normalize_postgrest_value(target_user_id)
    if normalized_target == admin_user_id and status != "active":
        raise HTTPException(status_code=400, detail={"message": "You cannot suspend or ban your own admin account."})

    mgr = get_manager()
    existing = mgr.db_client.select("user_profiles", filters={"user_id": f"eq.{normalized_target}"})
    if not existing:
        raise HTTPException(status_code=404, detail={"message": "User not found."})

    previous_status = str(existing[0].get("account_status") or "active")

    suspended_until = None
    if status == "suspended":
        until = body.suspended_until or (datetime.utcnow() + dt.timedelta(days=7))
        suspended_until = until.isoformat() if hasattr(until, "isoformat") else until

    updates = {
        "account_status": status,
        "status_reason": reason,
        "suspended_until": suspended_until,
        "moderated_by": admin_user_id,
        "moderated_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }

    mgr.db_client.update("user_profiles", updates, {"user_id": f"eq.{normalized_target}"})

    update_user_sessions(normalized_target, {
        "account_status": status,
        "suspended_until": suspended_until,
    })
    if status != "active":
        clear_user_sessions(normalized_target)

    _log_admin_action(
        admin_user_id,
        admin_id,
        f"user_status_{status}",
        target_user_id=normalized_target,
        target_resource=f"user_profiles:{normalized_target}",
        reason=reason,
        metadata={"previous_status": previous_status, "suspended_until": suspended_until},
    )

    refreshed = mgr.db_client.select("user_profiles", filters={"user_id": f"eq.{normalized_target}"})
    return refreshed[0] if refreshed else {"message": "Status updated"}


@router.patch("/api/admin/users/{target_user_id}/role")
def admin_update_user_role(target_user_id: str, body: AdminUserRoleUpdateRequest, request: Request):
    """Promote or reassign a user's role across patient/therapist/admin."""
    admin_user = require_admin(request)
    admin_user_id = str(admin_user["id"])
    admin_id = admin_user.get("admin_id")

    role = str(body.role or "").lower()
    if role not in ALLOWED_ROLES:
        raise HTTPException(status_code=400, detail={"message": "Invalid role. Use patient, therapist, or admin."})

    reason = (body.reason or "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail={"message": "A reason is required for this action."})

    _require_confirm_token(body.confirm)

    normalized_target = normalize_postgrest_value(target_user_id)
    if normalized_target == admin_user_id and role != "admin":
        raise HTTPException(status_code=400, detail={"message": "You cannot remove your own admin role."})

    mgr = get_manager()
    existing = mgr.db_client.select("user_profiles", filters={"user_id": f"eq.{normalized_target}"})
    if not existing:
        raise HTTPException(status_code=404, detail={"message": "User not found."})

    previous_role = str(existing[0].get("role") or "patient")

    updates = {
        "role": role,
        "moderated_by": admin_user_id,
        "moderated_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }
    mgr.db_client.update("user_profiles", updates, {"user_id": f"eq.{normalized_target}"})
    update_user_sessions(normalized_target, {"role": role})

    # Auto-assign admin_id on promotion to admin.
    if role == "admin":
        refreshed_profile = mgr.db_client.select("user_profiles", filters={"user_id": f"eq.{normalized_target}"})
        profile_row = refreshed_profile[0] if refreshed_profile else {}
        _ensure_admin_id(normalized_target, profile_row)

    _log_admin_action(
        admin_user_id,
        admin_id,
        f"role_changed_to_{role}",
        target_user_id=normalized_target,
        target_resource=f"user_profiles:{normalized_target}",
        reason=reason,
        metadata={"previous_role": previous_role},
    )

    refreshed = mgr.db_client.select("user_profiles", filters={"user_id": f"eq.{normalized_target}"})
    return refreshed[0] if refreshed else {"message": "Role updated"}


@router.delete("/api/admin/users/{target_user_id}")
def admin_delete_user(target_user_id: str, body: AdminUserDeleteRequest, request: Request):
    """Hard-delete a user profile (and cascaded data)."""
    admin_user = require_admin(request)
    admin_user_id = str(admin_user["id"])
    admin_id = admin_user.get("admin_id")

    reason = (body.reason or "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail={"message": "A reason is required to delete a user."})

    _require_confirm_token(body.confirm)

    normalized_target = normalize_postgrest_value(target_user_id)
    if normalized_target == admin_user_id:
        raise HTTPException(status_code=400, detail={"message": "You cannot delete your own admin account."})

    mgr = get_manager()
    existing = mgr.db_client.select("user_profiles", filters={"user_id": f"eq.{normalized_target}"})
    if not existing:
        raise HTTPException(status_code=404, detail={"message": "User not found."})

    snapshot = {
        "name": existing[0].get("name"),
        "email": existing[0].get("email"),
        "role": existing[0].get("role"),
        "account_status": existing[0].get("account_status"),
    }

    try:
        mgr.db_client.delete("user_profiles", {"user_id": f"eq.{normalized_target}"})
    except Exception as exc:
        logger.error(f"Failed to delete user_profiles for {normalized_target}: {exc}")
        raise HTTPException(status_code=500, detail={"message": "Failed to delete user."})

    clear_user_sessions(normalized_target)

    _log_admin_action(
        admin_user_id,
        admin_id,
        "user_deleted",
        target_user_id=normalized_target,
        target_resource=f"user_profiles:{normalized_target}",
        reason=reason,
        metadata=snapshot,
    )

    return {"message": "User deleted", "user_id": normalized_target}


@router.get("/api/admin/reports")
def admin_reports(request: Request):
    require_admin(request)
    status_filter = str(request.query_params.get("status") or "all").lower()
    priority_filter = str(request.query_params.get("priority") or "all").lower()

    rows = _select_optional_table("moderation_reports")
    filtered = []
    for row in rows:
        status = str(row.get("status") or "open").lower()
        priority = str(row.get("priority") or "medium").lower()
        if status_filter != "all" and status != status_filter:
            continue
        if priority_filter != "all" and priority != priority_filter:
            continue
        filtered.append(row)

    filtered_sorted = sorted(filtered, key=lambda r: str(r.get("created_at") or ""), reverse=True)
    return {"reports": filtered_sorted, "total": len(filtered_sorted)}


@router.patch("/api/admin/reports/{report_id}")
def admin_update_report(report_id: str, body: AdminReportUpdateRequest, request: Request):
    admin_user = require_admin(request)
    status = str(body.status or "").lower()
    allowed = {"open", "in_review", "resolved", "dismissed"}
    if status not in allowed:
        raise HTTPException(status_code=400, detail={"message": "Invalid report status."})

    rid = normalize_postgrest_value(report_id)
    mgr = get_manager()
    updates = {
        "status": status,
        "updated_at": datetime.utcnow().isoformat(),
    }
    if status in {"resolved", "dismissed"}:
        updates["resolved_at"] = datetime.utcnow().isoformat()
        updates["resolved_by"] = str(admin_user["id"])

    mgr.db_client.update("moderation_reports", updates, {"report_id": f"eq.{rid}"})
    rows = _select_optional_table("moderation_reports", filters={"report_id": f"eq.{rid}"})
    return rows[0] if rows else {"message": "Report updated"}


@router.get("/api/admin/feedback")
def admin_feedback(request: Request):
    require_admin(request)
    status_filter = str(request.query_params.get("status") or "all").lower()
    rows = _select_optional_table("platform_feedback")

    filtered = []
    for row in rows:
        status = str(row.get("status") or "open").lower()
        if status_filter != "all" and status != status_filter:
            continue
        filtered.append(row)

    filtered_sorted = sorted(filtered, key=lambda r: str(r.get("created_at") or ""), reverse=True)
    return {"feedback": filtered_sorted, "total": len(filtered_sorted)}


@router.patch("/api/admin/feedback/{feedback_id}")
def admin_update_feedback(feedback_id: str, body: AdminFeedbackUpdateRequest, request: Request):
    admin_user = require_admin(request)
    status = str(body.status or "").lower()
    allowed = {"open", "reviewed", "dismissed"}
    if status not in allowed:
        raise HTTPException(status_code=400, detail={"message": "Invalid feedback status."})

    fid = normalize_postgrest_value(feedback_id)
    mgr = get_manager()
    updates = {
        "status": status,
        "reviewed_by": str(admin_user["id"]) if status in {"reviewed", "dismissed"} else None,
        "reviewed_at": datetime.utcnow().isoformat() if status in {"reviewed", "dismissed"} else None,
    }
    mgr.db_client.update("platform_feedback", updates, {"feedback_id": f"eq.{fid}"})
    rows = _select_optional_table("platform_feedback", filters={"feedback_id": f"eq.{fid}"})
    return rows[0] if rows else {"message": "Feedback updated"}


@router.get("/api/admin/me")
def admin_profile_me(request: Request):
    admin_user = require_admin(request)
    admin_user_id = str(admin_user["id"])
    profile = _get_profile_persistent(admin_user_id)

    logs = _select_optional_table(
        "admin_audit_logs",
        filters={"admin_user_id": f"eq.{admin_user_id}"},
    )
    logs_sorted = sorted(logs, key=lambda l: str(l.get("created_at") or ""), reverse=True)

    last_login = profile.get("last_login_at") or profile.get("updated_at") or profile.get("created_at")
    return {
        "user_id": admin_user_id,
        "admin_id": profile.get("admin_id"),
        "name": profile.get("name") or admin_user.get("username") or "Admin",
        "email": profile.get("email") or admin_user.get("email"),
        "role": "admin",
        "account_status": _get_account_status(profile),
        "created_at": profile.get("created_at"),
        "moderated_at": profile.get("moderated_at"),
        "last_login_at": last_login,
        "total_actions": len(logs),
        "recent_actions": logs_sorted[:10],
    }


@router.get("/api/admin/logs")
def admin_logs(request: Request):
    require_admin(request)

    action_filter = str(request.query_params.get("action") or "all").lower()
    actor_filter = str(request.query_params.get("admin_user_id") or "all")
    target_filter = str(request.query_params.get("target_user_id") or "all")

    try:
        limit = max(1, min(int(request.query_params.get("limit") or 200), 500))
    except ValueError:
        limit = 200

    rows = _select_optional_table("admin_audit_logs")
    filtered = []
    for row in rows:
        if action_filter != "all" and str(row.get("action") or "").lower() != action_filter:
            continue
        if actor_filter != "all" and str(row.get("admin_user_id") or "") != actor_filter:
            continue
        if target_filter != "all" and str(row.get("target_user_id") or "") != target_filter:
            continue
        filtered.append(row)

    filtered_sorted = sorted(filtered, key=lambda r: str(r.get("created_at") or ""), reverse=True)
    return {"logs": filtered_sorted[:limit], "total": len(filtered_sorted)}


@router.get("/api/admin/therapists/queue")
def admin_therapists_queue(request: Request):
    require_admin(request)

    status_filter = str(request.query_params.get("status") or "pending").lower()
    rows = _select_optional_table("therapist_verifications")

    filtered = []
    for row in rows:
        status = str(row.get("status") or "pending").lower()
        if status_filter != "all" and status != status_filter:
            continue
        filtered.append(row)

    profiles = _select_optional_table("user_profiles")
    by_uid = {str(p.get("user_id")): p for p in profiles}
    for row in filtered:
        linked = by_uid.get(str(row.get("user_id")), {})
        row["user_name"] = linked.get("name")
        row["user_email"] = linked.get("email")
        row["user_role"] = linked.get("role")

    filtered_sorted = sorted(filtered, key=lambda r: str(r.get("submitted_at") or ""), reverse=True)
    return {"queue": filtered_sorted, "total": len(filtered_sorted)}


@router.patch("/api/admin/therapists/{verification_id}")
def admin_review_therapist(verification_id: str, body: TherapistVerificationReviewRequest, request: Request):
    admin_user = require_admin(request)
    admin_user_id = str(admin_user["id"])
    admin_id = admin_user.get("admin_id")

    status = str(body.status or "").lower()
    if status not in {"approved", "rejected"}:
        raise HTTPException(status_code=400, detail={"message": "Invalid status. Use approved or rejected."})

    vid = normalize_postgrest_value(verification_id)
    mgr = get_manager()
    existing = _select_optional_table("therapist_verifications", filters={"verification_id": f"eq.{vid}"})
    if not existing:
        raise HTTPException(status_code=404, detail={"message": "Verification not found."})

    target_uid = str(existing[0].get("user_id") or "")

    mgr.db_client.update(
        "therapist_verifications",
        {
            "status": status,
            "reviewed_by": admin_user_id,
            "reviewed_at": datetime.utcnow().isoformat(),
            "review_notes": body.review_notes,
        },
        {"verification_id": f"eq.{vid}"},
    )

    if status == "approved" and target_uid:
        mgr.db_client.update(
            "user_profiles",
            {"role": "therapist", "updated_at": datetime.utcnow().isoformat()},
            {"user_id": f"eq.{target_uid}"},
        )
        update_user_sessions(target_uid, {"role": "therapist"})

    _log_admin_action(
        admin_user_id,
        admin_id,
        f"therapist_{status}",
        target_user_id=target_uid or None,
        target_resource=f"therapist_verifications:{vid}",
        reason=body.review_notes,
    )

    refreshed = _select_optional_table("therapist_verifications", filters={"verification_id": f"eq.{vid}"})
    return refreshed[0] if refreshed else {"message": "Verification updated"}


@router.get("/api/admin/announcements")
def admin_list_announcements(request: Request):
    require_admin(request)
    rows = _select_optional_table("announcements")
    rows_sorted = sorted(rows, key=lambda r: str(r.get("created_at") or ""), reverse=True)
    return {"announcements": rows_sorted, "total": len(rows_sorted)}


@router.post("/api/admin/announcements")
def admin_create_announcement(body: AnnouncementCreateRequest, request: Request):
    admin_user = require_admin(request)
    admin_user_id = str(admin_user["id"])
    admin_id = admin_user.get("admin_id")

    title = (body.title or "").strip()
    message = (body.body or "").strip()
    audience = str(body.audience or "all").lower()

    if not title or not message:
        raise HTTPException(status_code=400, detail={"message": "Title and body are required."})
    if audience not in {"all", "patients", "therapists", "inactive"}:
        raise HTTPException(status_code=400, detail={"message": "Invalid audience."})

    payload = {
        "admin_user_id": admin_user_id,
        "title": title,
        "body": message,
        "audience": audience,
        "expires_at": body.expires_at.isoformat() if body.expires_at else None,
    }

    try:
        row = get_manager().db_client.insert("announcements", payload)
    except Exception as exc:
        if _is_missing_table_error(exc):
            raise HTTPException(status_code=503, detail={"message": "Announcements table missing. Run the admin extensions migration."})
        raise

    _log_admin_action(
        admin_user_id,
        admin_id,
        "announcement_created",
        target_resource=f"announcements:{row[0].get('announcement_id') if isinstance(row, list) else row.get('announcement_id')}",
        metadata={"audience": audience, "title": title},
    )

    return row[0] if isinstance(row, list) else row


@router.delete("/api/admin/announcements/{announcement_id}")
def admin_deactivate_announcement(announcement_id: str, request: Request):
    admin_user = require_admin(request)
    admin_user_id = str(admin_user["id"])
    admin_id = admin_user.get("admin_id")

    aid = normalize_postgrest_value(announcement_id)
    try:
        get_manager().db_client.update(
            "announcements",
            {"active": False},
            {"announcement_id": f"eq.{aid}"},
        )
    except Exception as exc:
        if _is_missing_table_error(exc):
            raise HTTPException(status_code=503, detail={"message": "Announcements table missing."})
        raise

    _log_admin_action(
        admin_user_id,
        admin_id,
        "announcement_deactivated",
        target_resource=f"announcements:{aid}",
    )

    return {"message": "Announcement deactivated", "announcement_id": aid}


@router.get("/api/admin/analytics")
def admin_analytics(request: Request):
    require_admin(request)

    conversations = _select_optional_table("conversations")
    profiles = _select_optional_table("user_profiles")

    now = datetime.utcnow()
    one_day = now - dt.timedelta(days=1)
    seven_days = now - dt.timedelta(days=7)
    thirty_days = now - dt.timedelta(days=30)

    dau_users: set = set()
    wau_users: set = set()
    mau_users: set = set()
    total_minutes_30d = 0
    sessions_30d = 0

    for conv in conversations:
        uid = str(conv.get("user_id") or "")
        if not uid:
            continue
        created = _parse_iso_datetime(conv.get("created_at"))
        if not created:
            continue
        created_naive = created.replace(tzinfo=None) if created.tzinfo else created
        if created_naive >= one_day:
            dau_users.add(uid)
        if created_naive >= seven_days:
            wau_users.add(uid)
        if created_naive >= thirty_days:
            mau_users.add(uid)
            sessions_30d += 1
            total_minutes_30d += int(conv.get("duration_minutes") or 0)

    avg_session_minutes = round(total_minutes_30d / sessions_30d, 1) if sessions_30d else 0.0

    active_therapists = sum(
        1 for p in profiles
        if str(p.get("role") or "").lower() == "therapist"
        and _get_account_status(p) == "active"
    )

    return {
        "dau": len(dau_users),
        "wau": len(wau_users),
        "mau": len(mau_users),
        "sessions_30d": sessions_30d,
        "total_minutes_30d": total_minutes_30d,
        "avg_session_minutes": avg_session_minutes,
        "active_therapists": active_therapists,
    }
