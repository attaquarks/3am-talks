"""
core/ — shared infrastructure for the 3AM API.

Exports the canonical session store, signing utilities, and
auth guards so every route module can import them from one place
without circular-import issues.
"""
from .sessions import (
    SECRET_KEY,
    SESSION_COOKIE,
    SESSION_MAX_AGE,
    VOICE_AGENT_SECRET,
    signer,
    sessions,
    temp_oauth_sessions,
    create_session,
    get_current_user,
    clear_user_sessions,
    update_user_sessions,
)
from .helpers import (
    ALLOWED_ROLES,
    ALLOWED_ACCOUNT_STATUSES,
    get_manager,
    require_user,
    require_admin,
    require_voice_agent,
    _get_profile_persistent,
    _get_stats_persistent,
    _get_mood_entries_persistent,
    _get_account_status,
    _status_block_message,
    _build_session_user_payload,
    _select_optional_table,
    _is_missing_table_error,
    _is_conflict_error,
    _ensure_admin_id,
    _log_admin_action,
    _require_confirm_token,
    _parse_iso_datetime,
    _resume_or_start_conversation,
    _coerce_role,
    _build_user_metrics_by_user,
    _backend_conversation_to_frontend,
    _backend_message_to_frontend,
)

__all__ = [
    # session
    "SECRET_KEY", "SESSION_COOKIE", "SESSION_MAX_AGE", "VOICE_AGENT_SECRET",
    "signer", "sessions", "temp_oauth_sessions",
    "create_session", "get_current_user", "clear_user_sessions", "update_user_sessions",
    # helpers
    "ALLOWED_ROLES", "ALLOWED_ACCOUNT_STATUSES",
    "get_manager", "require_user", "require_admin", "require_voice_agent",
    "_get_profile_persistent", "_get_stats_persistent", "_get_mood_entries_persistent",
    "_get_account_status", "_status_block_message", "_build_session_user_payload",
    "_select_optional_table", "_is_missing_table_error", "_is_conflict_error",
    "_ensure_admin_id", "_log_admin_action", "_require_confirm_token",
    "_parse_iso_datetime", "_resume_or_start_conversation",
    "_coerce_role", "_build_user_metrics_by_user",
    "_backend_conversation_to_frontend", "_backend_message_to_frontend",
]
