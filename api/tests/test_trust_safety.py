import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

import app.main as m
from app.routes import auth as auth_routes
from app.services import rate_limit


def _client(monkeypatch):
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

    monkeypatch.setattr(m, "wait_for_db", lambda *args, **kwargs: None)
    monkeypatch.setattr(m, "run_migrations", lambda *args, **kwargs: None)
    monkeypatch.setattr(m.survey_admin_repo, "count_definitions", lambda: 1)
    monkeypatch.setattr(m, "SessionLocal", lambda: _DummySession())
    monkeypatch.setattr(auth_routes, "SessionLocal", lambda: _DummySession())
    monkeypatch.setattr(auth_routes, "resolve_tenant_for_email", lambda db, email: {"id": None, "slug": "cbs"})
    return TestClient(m.app)


def test_report_endpoint_uses_current_match_server_side(monkeypatch):
    client = _client(monkeypatch)

    captured = {}

    m.app.dependency_overrides[m.require_verified_user] = lambda: {
        "id": "11111111-1111-1111-1111-111111111111",
        "email": "u@gsb.columbia.edu",
        "is_email_verified": True,
    }

    monkeypatch.setattr(
        m,
        "repo_get_current_match",
        lambda user_id, now: {
            "week_start_date": "2026-02-09",
            "matched_user_id": "22222222-2222-2222-2222-222222222222",
            "status": "revealed",
            "score_breakdown": {},
        },
    )

    def fake_create_match_report(week_start_date, user_id, matched_user_id, reason, details):
        captured.update(
            {
                "week_start_date": str(week_start_date),
                "user_id": user_id,
                "matched_user_id": matched_user_id,
                "reason": reason,
                "details": details,
            }
        )
        return {"id": "r1", **captured}

    monkeypatch.setattr(m.auth_repo, "create_match_report", fake_create_match_report)

    res = client.post("/safety/report", json={"reason": "inappropriate", "details": "details here"})
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "reported"
    assert captured["matched_user_id"] == "22222222-2222-2222-2222-222222222222"
    assert captured["week_start_date"] == "2026-02-09"

    m.app.dependency_overrides = {}


def test_blocked_current_match_returns_safe_message(monkeypatch):
    client = _client(monkeypatch)

    m.app.dependency_overrides[m.require_verified_user] = lambda: {
        "id": "11111111-1111-1111-1111-111111111111",
        "email": "u@gsb.columbia.edu",
        "is_email_verified": True,
    }

    monkeypatch.setattr(
        m,
        "repo_get_current_match",
        lambda user_id, now: {
            "status": "no_match",
            "score_breakdown": {"reason": "blocked_match_hidden"},
            "explanation": {"bullets": [], "icebreakers": []},
            "feedback": {"eligible": False, "already_submitted": False, "due_met_question": False},
        },
    )

    res = client.get("/matches/current")
    assert res.status_code == 200
    body = res.json()
    assert body["match"]["status"] == "no_match"
    assert "unavailable due to your safety settings" in body["message"].lower()

    m.app.dependency_overrides = {}


def test_rate_limit_returns_429(monkeypatch):
    client = _client(monkeypatch)
    rate_limit.limiter._events.clear()

    monkeypatch.setattr(
        m.auth_repo,
        "get_user_by_email",
        lambda email: {
            "id": "11111111-1111-1111-1111-111111111111",
            "email": email,
            "password_hash": "hash",
            "is_email_verified": True,
            "disabled_at": None,
        },
    )
    monkeypatch.setattr(auth_routes, "verify_password", lambda raw, hashed: True)
    monkeypatch.setattr(m.auth_repo, "update_last_login", lambda user_id: None)
    monkeypatch.setattr(auth_routes, "_issue_tokens", lambda user: {"access_token": "a", "refresh_token": "r", "token_type": "bearer", "expires_in": 900})

    status_codes = []
    for _ in range(auth_routes.RL_AUTH_LOGIN_LIMIT + 1):
        resp = client.post("/auth/login", json={"email": "u@gsb.columbia.edu", "password": "longpassword1"})
        status_codes.append(resp.status_code)

    assert status_codes[-1] == 429
