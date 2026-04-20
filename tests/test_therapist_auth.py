"""
Authorization primitives for the therapist portal.

These four helpers (`_has_scope`, `_require_therapist`, `_active_link`,
`_require_link`) gate every protected therapist-portal endpoint. Testing them
directly proves SEC-003 (consent fail-closed), AUTH-002 (link-required
enforcement), and AUTH-003 (homework-update link check) hold — without needing
a live Supabase or HTTP stack.
"""
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException, Request

from core import _parse_pagination
from routes import therapist as t


# ---------------------------------------------------------------------------
# _has_scope — SEC-003: must FAIL CLOSED on malformed consent data
# ---------------------------------------------------------------------------


class TestHasScopeFailsClosed:
    """If consent_scope is anything other than a dict with scope=True, deny."""

    def test_none_consent_scope_denies(self):
        assert t._has_scope({"consent_scope": None}, "read_notes") is False

    def test_missing_consent_scope_key_denies(self):
        assert t._has_scope({}, "read_notes") is False

    def test_string_consent_scope_denies(self):
        # SEC-003 regression: if DB stores consent as a string, never grant.
        assert t._has_scope({"consent_scope": "all"}, "read_notes") is False

    def test_list_consent_scope_denies(self):
        assert t._has_scope({"consent_scope": ["read_notes"]}, "read_notes") is False

    def test_integer_consent_scope_denies(self):
        assert t._has_scope({"consent_scope": 1}, "read_notes") is False

    def test_empty_dict_denies(self):
        assert t._has_scope({"consent_scope": {}}, "read_notes") is False

    def test_scope_explicitly_false_denies(self):
        link = {"consent_scope": {"read_notes": False}}
        assert t._has_scope(link, "read_notes") is False

    def test_unrelated_scope_granted_denies_target(self):
        # Granting read_messages must NOT leak into read_notes.
        link = {"consent_scope": {"read_messages": True}}
        assert t._has_scope(link, "read_notes") is False

    def test_scope_explicitly_true_grants(self):
        link = {"consent_scope": {"read_notes": True}}
        assert t._has_scope(link, "read_notes") is True


# ---------------------------------------------------------------------------
# _require_therapist — role-based gate on every therapist endpoint
# ---------------------------------------------------------------------------


def _mock_request_with_user(monkeypatch, user_payload):
    """Stub require_user to return a preset payload without a live session."""
    monkeypatch.setattr(t, "require_user", lambda request: user_payload)
    return MagicMock(spec=Request)


class TestRequireTherapistRole:
    def test_therapist_role_allowed(self, monkeypatch):
        req = _mock_request_with_user(monkeypatch, {"id": "u1", "role": "therapist"})
        assert t._require_therapist(req)["id"] == "u1"

    def test_therapist_role_case_insensitive(self, monkeypatch):
        req = _mock_request_with_user(monkeypatch, {"id": "u1", "role": "Therapist"})
        assert t._require_therapist(req)["id"] == "u1"

    def test_patient_role_rejected(self, monkeypatch):
        req = _mock_request_with_user(monkeypatch, {"id": "u1", "role": "patient"})
        with pytest.raises(HTTPException) as exc:
            t._require_therapist(req)
        assert exc.value.status_code == 403

    def test_admin_role_rejected(self, monkeypatch):
        # Admins are NOT therapists — portal access must be explicit.
        req = _mock_request_with_user(monkeypatch, {"id": "u1", "role": "admin"})
        with pytest.raises(HTTPException) as exc:
            t._require_therapist(req)
        assert exc.value.status_code == 403

    def test_missing_role_rejected(self, monkeypatch):
        req = _mock_request_with_user(monkeypatch, {"id": "u1"})
        with pytest.raises(HTTPException) as exc:
            t._require_therapist(req)
        assert exc.value.status_code == 403

    def test_null_role_rejected(self, monkeypatch):
        req = _mock_request_with_user(monkeypatch, {"id": "u1", "role": None})
        with pytest.raises(HTTPException) as exc:
            t._require_therapist(req)
        assert exc.value.status_code == 403


# ---------------------------------------------------------------------------
# _active_link / _require_link — AUTH-002: therapist must have active link
# ---------------------------------------------------------------------------


class TestActiveLinkRequirement:
    def test_active_link_returned_when_present(self, monkeypatch):
        preset = [{"link_id": "L1", "status": "active", "consent_scope": {"read_notes": True}}]
        monkeypatch.setattr(t, "_select_optional_table", lambda table, filters=None: preset)
        link = t._active_link("therapist-1", "patient-1")
        assert link is not None
        assert link["link_id"] == "L1"

    def test_no_link_returns_none(self, monkeypatch):
        monkeypatch.setattr(t, "_select_optional_table", lambda table, filters=None: [])
        assert t._active_link("therapist-1", "patient-1") is None

    def test_require_link_raises_when_no_active_link(self, monkeypatch):
        monkeypatch.setattr(t, "_select_optional_table", lambda table, filters=None: [])
        with pytest.raises(HTTPException) as exc:
            t._require_link("therapist-1", "patient-1")
        assert exc.value.status_code == 403

    def test_require_link_returns_link_when_active(self, monkeypatch):
        preset = [{"link_id": "L1", "status": "active"}]
        monkeypatch.setattr(t, "_select_optional_table", lambda table, filters=None: preset)
        link = t._require_link("therapist-1", "patient-1")
        assert link["link_id"] == "L1"

    def test_active_link_filters_include_status_eq_active(self, monkeypatch):
        """AUTH-002 guard: the DB query must scope to status=active, not any status."""
        captured = {}

        def spy(table, filters=None):
            captured["table"] = table
            captured["filters"] = filters
            return []

        monkeypatch.setattr(t, "_select_optional_table", spy)
        t._active_link("therapist-1", "patient-1")
        assert captured["filters"]["status"] == "eq.active"
        assert captured["filters"]["therapist_id"] == "eq.therapist-1"
        assert captured["filters"]["patient_id"] == "eq.patient-1"


# ---------------------------------------------------------------------------
# _parse_pagination — PERF-004: bounded, safe pagination for list endpoints
# ---------------------------------------------------------------------------


def _fake_request(params: dict) -> Request:
    req = MagicMock(spec=Request)
    req.query_params = params
    return req


class TestParsePagination:
    def test_defaults_when_params_missing(self):
        limit, offset = _parse_pagination(_fake_request({}), default_limit=50)
        assert limit == 50
        assert offset == 0

    def test_explicit_values_used(self):
        limit, offset = _parse_pagination(_fake_request({"limit": "25", "offset": "100"}))
        assert (limit, offset) == (25, 100)

    def test_limit_clamped_to_max(self):
        # Client requesting 10_000 must not be honored — DoS protection.
        limit, _ = _parse_pagination(_fake_request({"limit": "10000"}), max_limit=200)
        assert limit == 200

    def test_limit_clamped_to_at_least_one(self):
        limit, _ = _parse_pagination(_fake_request({"limit": "0"}))
        assert limit == 1

    def test_negative_offset_clamped_to_zero(self):
        _, offset = _parse_pagination(_fake_request({"offset": "-5"}))
        assert offset == 0

    def test_garbage_params_fall_back_to_defaults(self):
        limit, offset = _parse_pagination(
            _fake_request({"limit": "notanumber", "offset": "junk"}),
            default_limit=50,
        )
        assert (limit, offset) == (50, 0)
