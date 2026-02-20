"""
Baseline router contract checks.

Purpose: lock core endpoint contracts before/while moving handlers out of main.py.
These are intentionally shape-focused (status + key response fields), not deep behavior tests.
"""

from datetime import datetime, timezone

import pytest

pytest.importorskip("fastapi")
from fastapi import HTTPException
from fastapi.testclient import TestClient

import app.main as m
from app.routes import admin as admin_routes
from app.routes import auth as auth_routes
from app.routes import chat as chat_routes
from app.routes import match as match_routes
from app.routes import profile as profile_routes
from app.routes import safety as safety_routes
from app.routes import survey as survey_routes
from app.services import rate_limit


class _DummyResult:
    def mappings(self):
        return self

    def first(self):
        return None

    def all(self):
        return []


class _DummySession:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, *args, **kwargs):
        return _DummyResult()

    def commit(self):
        return None


def _client(monkeypatch):
    rate_limit.limiter._events.clear()
    monkeypatch.setattr(m, "wait_for_db", lambda *args, **kwargs: None)
    monkeypatch.setattr(m, "run_migrations", lambda *args, **kwargs: None)
    monkeypatch.setattr(m.survey_admin_repo, "count_definitions", lambda: 1)
    monkeypatch.setattr(m, "SessionLocal", lambda: _DummySession())
    monkeypatch.setattr(auth_routes, "SessionLocal", lambda: _DummySession())
    monkeypatch.setattr(profile_routes, "SessionLocal", lambda: _DummySession())
    monkeypatch.setattr(admin_routes, "SessionLocal", lambda: _DummySession())
    monkeypatch.setattr(safety_routes, "require_verified_user", m.require_verified_user)
    monkeypatch.setattr(match_routes, "require_verified_user", m.require_verified_user)
    monkeypatch.setattr(chat_routes, "require_verified_user", m.require_verified_user)
    monkeypatch.setattr(auth_routes, "resolve_tenant_for_email", lambda db, email: {"id": None, "slug": "cbs"})
    monkeypatch.setattr(profile_routes, "log_product_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(profile_routes, "log_profile_event", lambda *args, **kwargs: None)
    return TestClient(m.app)


def test_auth_login_contract_shape(monkeypatch):
    client = _client(monkeypatch)
    monkeypatch.setattr(
        m.auth_repo,
        "get_user_by_email",
        lambda email, tenant_id=None: {
            "id": "11111111-1111-1111-1111-111111111111",
            "email": email,
            "password_hash": "hash",
            "is_email_verified": True,
            "disabled_at": None,
            "tenant_id": None,
        },
    )
    monkeypatch.setattr(auth_routes, "verify_password", lambda raw, hashed: True)
    monkeypatch.setattr(m.auth_repo, "update_last_login", lambda user_id: None)
    # Mock the _issue_tokens function to avoid database calls
    monkeypatch.setattr(
        auth_routes,
        "_issue_tokens_compat",
        lambda user, **kwargs: {"access_token": "test-token", "refresh_token": "test-refresh", "token_type": "bearer", "expires_in": 900},
    )

    res = client.post("/auth/login", json={"email": "u@gsb.columbia.edu", "password": "longpassword1"})
    assert res.status_code == 200
    body = res.json()
    # Auth now uses httpOnly cookies - check for user info instead of tokens in body
    assert set(["id", "email", "is_email_verified"]).issubset(body.keys())


def test_auth_me_contract_shape(monkeypatch):
    client = _client(monkeypatch)
    m.app.dependency_overrides[m.get_current_user] = lambda: {
        "id": "11111111-1111-1111-1111-111111111111",
        "email": "u@gsb.columbia.edu",
        "username": "user_1",
        "is_email_verified": True,
    }

    res = client.get("/auth/me")
    assert res.status_code == 200
    body = res.json()
    assert set(["id", "email", "username", "is_email_verified"]).issubset(body.keys())
    m.app.dependency_overrides = {}


def test_survey_session_contract_shape(monkeypatch):
    client = _client(monkeypatch)
    monkeypatch.setattr(
        m,
        "repo_create_session",
        lambda user_id, survey_slug, survey_version, survey_hash="", tenant_id=None: {"session_id": "s1", "user_id": user_id},
    )
    monkeypatch.setattr(
        m,
        "repo_complete_session",
        lambda session_id, survey_def: {"status": "completed", "completed_at": datetime.now(timezone.utc).isoformat(), "traits": {}},
    )
    monkeypatch.setattr(m, "repo_get_session_with_answers", lambda session_id: {"session": {"id": session_id, "user_id": "u1"}, "answers": {}})

    m.app.dependency_overrides[m.get_current_user] = lambda: {"id": "u1", "email": "u@gsb.columbia.edu", "is_email_verified": True}

    created = client.post("/sessions")
    assert created.status_code == 200
    assert set(["session_id", "user_id"]).issubset(created.json().keys())

    completed = client.post("/sessions/s1/complete")
    assert completed.status_code == 200
    assert set(["status", "completed_at", "traits"]).issubset(completed.json().keys())
    m.app.dependency_overrides = {}


def test_profile_get_put_contract_shape(monkeypatch):
    client = _client(monkeypatch)
    profile_row = {
        "id": "u1",
        "email": "u@gsb.columbia.edu",
        "username": "user_1",
        "display_name": "User",
        "cbs_year": "26",
        "hometown": "NYC",
        "phone_number": None,
        "instagram_handle": None,
        "photo_urls": [],
        "gender_identity": "man",
        "seeking_genders": ["woman"],
    }

    monkeypatch.setattr(m.auth_repo, "get_user_public_profile", lambda user_id: profile_row)
    monkeypatch.setattr(m.auth_repo, "update_user_profile", lambda **kwargs: {**profile_row, **kwargs})

    m.app.dependency_overrides[m.require_verified_user] = lambda: {"id": "u1", "email": "u@gsb.columbia.edu", "is_email_verified": True}

    got = client.get("/users/me/profile")
    assert got.status_code == 200
    assert "profile" in got.json()

    updated = client.put(
        "/users/me/profile",
        json={"display_name": "User", "cbs_year": "26", "hometown": "NYC", "gender_identity": "man", "seeking_genders": ["woman"]},
    )
    assert updated.status_code == 200
    assert "profile" in updated.json()
    m.app.dependency_overrides = {}


def test_match_current_accept_decline_contract_shape(monkeypatch):
    client = _client(monkeypatch)
    monkeypatch.setattr(
        m,
        "repo_get_current_match",
        lambda user_id, now: {
            "status": "revealed",
            "week_start_date": "2026-02-16",
            "matched_user_id": "u2",
            "matched_profile": {"id": "u2", "email": "m@gsb.columbia.edu", "display_name": "Match", "photo_urls": []},
            "score_breakdown": {},
            "explanation": {"bullets": [], "icebreakers": []},
            "explanation_v2": {"overall": "x", "pros": [], "cons": [], "version": "v"},
            "feedback": {"eligible": True, "already_submitted": False, "due_met_question": False},
        },
    )
    monkeypatch.setattr(m, "repo_update_current_match_status", lambda user_id, action, now: {"status": "accepted" if action == "accept" else "declined"})

    m.app.dependency_overrides[m.require_verified_user] = lambda: {"id": "u1", "email": "u@gsb.columbia.edu", "is_email_verified": True}

    cur = client.get("/matches/current")
    assert cur.status_code == 200
    body = cur.json()
    assert set(["match", "message", "explanation", "explanation_v2", "feedback"]).issubset(body.keys())

    acc = client.post("/matches/current/accept")
    dec = client.post("/matches/current/decline")
    assert acc.status_code == 200 and "status" in acc.json()
    assert dec.status_code == 200 and "status" in dec.json()
    m.app.dependency_overrides = {}


def test_match_contact_click_contract_shape(monkeypatch):
    client = _client(monkeypatch)
    m.app.dependency_overrides[m.require_verified_user] = lambda: {"id": "u1", "email": "u@gsb.columbia.edu", "is_email_verified": True}

    ok = client.post("/matches/current/contact-click", json={"channel": "email"})
    bad = client.post("/matches/current/contact-click", json={"channel": "fax"})

    assert ok.status_code == 200
    assert ok.json().get("status") == "ok"
    assert bad.status_code == 400
    m.app.dependency_overrides = {}


def test_safety_and_admin_contract_shape(monkeypatch):
    client = _client(monkeypatch)
    monkeypatch.setattr(m.auth_repo, "resolve_user_id_from_identifier", lambda identifier, exclude_user_id=None: "u2")
    monkeypatch.setattr(m.auth_repo, "create_user_block", lambda user_id, blocked_user_id: True)
    monkeypatch.setattr(m, "_fetch_current_row", lambda db, uid, week_start: None)
    monkeypatch.setattr(m, "repo_get_current_match", lambda user_id, now: {"week_start_date": "2026-02-16", "matched_user_id": "u2", "status": "revealed"})
    monkeypatch.setattr(
        m.auth_repo,
        "create_match_report",
        lambda week_start_date, user_id, matched_user_id, reason, details: {
            "id": "r1",
            "week_start_date": str(week_start_date),
            "user_id": user_id,
            "matched_user_id": matched_user_id,
            "reason": reason,
            "details": details,
        },
    )

    monkeypatch.setattr(m, "ADMIN_TOKEN", "admin-secret")
    monkeypatch.setattr(m, "repo_run_weekly_matching", lambda now, tenant_slug=None: {"created_assignments": 0})
    monkeypatch.setattr(m, "metrics_funnel_summary", lambda db, date_from, date_to, tenant_id=None: {"totals": {}})

    m.app.dependency_overrides[m.require_verified_user] = lambda: {"id": "u1", "email": "u@gsb.columbia.edu", "is_email_verified": True}

    block = client.post("/safety/block", json={"blocked_user_id": "u2"})
    report = client.post("/safety/report", json={"reason": "inappropriate"})
    assert block.status_code == 200 and "status" in block.json()
    assert report.status_code == 200 and "status" in report.json()

    run = client.post("/admin/matches/run-weekly", headers={"X-Admin-Token": "admin-secret"})
    summary = client.get(
        "/admin/metrics/summary",
        params={"date_from": "2026-02-01", "date_to": "2026-02-28"},
        headers={"X-Admin-Token": "admin-secret"},
    )
    assert run.status_code == 200
    assert summary.status_code == 200

    m.app.dependency_overrides = {}
