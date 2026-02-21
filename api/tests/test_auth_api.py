from datetime import datetime, timezone

import pytest

pytest.importorskip("fastapi")
from fastapi import HTTPException
from fastapi.testclient import TestClient

import app.main as m
from app.routes import auth as auth_routes


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
    monkeypatch.setattr(auth_routes, "resolve_tenant_for_email", lambda db, email: {"id": None, "slug": "cbs"})
    monkeypatch.setattr(m, "SessionLocal", lambda: _DummySession())
    monkeypatch.setattr(auth_routes, "SessionLocal", lambda: _DummySession())
    return TestClient(m.app)


def test_auth_registration_domain_restriction(monkeypatch):
    client = _client(monkeypatch)
    res = client.post(
        "/auth/register",
        json={
            "email": "user@gmail.com",
            "password": "verysecurepw",
            "gender_identity": "man",
            "seeking_genders": ["woman"],
        },
    )
    assert res.status_code == 400
    assert "@gsb.columbia.edu" in res.json()["detail"]


def test_auth_register_login_verify_flow(monkeypatch):
    client = _client(monkeypatch)
    store = {
        "users_by_email": {},
        "users_by_id": {},
        "verification_by_user": {},
        "refresh": {},
    }

    def create_user(email: str, password_hash: str, username: str | None = None, tenant_id: str | None = None):
        user = {
            "id": "11111111-1111-1111-1111-111111111111",
            "email": email,
            "password_hash": password_hash,
            "is_email_verified": False,
            "disabled_at": None,
            "username": username,
            "tenant_id": tenant_id,
        }
        store["users_by_email"][email] = user
        store["users_by_id"][user["id"]] = user
        return user

    def get_user_by_email(email: str):
        return store["users_by_email"].get(email)

    def get_user_by_id(user_id: str):
        return store["users_by_id"].get(user_id)

    def create_email_verification_token(user_id: str, token: str, expires_at: datetime, code_hash: str | None = None):
        row = {
            "id": "22222222-2222-2222-2222-222222222222",
            "user_id": user_id,
            "token": token,
            "code_hash": code_hash,
            "expires_at": expires_at,
            "used_at": None,
            "failed_attempts": 0,
        }
        store["verification_by_user"][user_id] = row
        return row

    def get_latest_active_verification_for_user(user_id: str):
        row = store["verification_by_user"].get(user_id)
        if not row:
            return None
        return row if row.get("used_at") is None else None

    def invalidate_active_verification_tokens(user_id: str):
        row = store["verification_by_user"].get(user_id)
        if row and row.get("used_at") is None:
            row["used_at"] = datetime.now(timezone.utc)

    def increment_verification_failed_attempts(token_id: str):
        for row in store["verification_by_user"].values():
            if row["id"] == token_id:
                row["failed_attempts"] = int(row.get("failed_attempts") or 0) + 1

    def set_user_verified(user_id: str):
        store["users_by_id"][user_id]["is_email_verified"] = True

    def mark_token_used(token_id: str):
        for row in store["verification_by_user"].values():
            if row["id"] == token_id:
                row["used_at"] = datetime.now(timezone.utc)

    monkeypatch.setattr(m.auth_repo, "create_user", create_user)
    monkeypatch.setattr(m.auth_repo, "get_user_by_email", get_user_by_email)
    monkeypatch.setattr(m.auth_repo, "get_user_by_id", get_user_by_id)
    monkeypatch.setattr(m.auth_repo, "create_email_verification_token", create_email_verification_token)
    monkeypatch.setattr(m.auth_repo, "get_latest_active_verification_for_user", get_latest_active_verification_for_user)
    monkeypatch.setattr(m.auth_repo, "invalidate_active_verification_tokens", invalidate_active_verification_tokens)
    monkeypatch.setattr(m.auth_repo, "increment_verification_failed_attempts", increment_verification_failed_attempts)
    monkeypatch.setattr(m.auth_repo, "set_user_verified", set_user_verified)
    monkeypatch.setattr(m.auth_repo, "mark_token_used", mark_token_used)
    monkeypatch.setattr(m.auth_repo, "update_user_profile", lambda **kwargs: {"id": kwargs.get("user_id")})
    monkeypatch.setattr(m.auth_repo, "update_last_login", lambda *args, **kwargs: None)
    monkeypatch.setattr(m.auth_repo, "create_refresh_token_row", lambda user_id, token_hash, expires_at: store["refresh"].update({token_hash: {"user_id": user_id, "expires_at": expires_at, "revoked_at": None}}))
    monkeypatch.setattr(auth_routes, "create_one_time_token", lambda: "verify-token")
    monkeypatch.setattr(auth_routes, "create_verification_code", lambda: "123456")
    monkeypatch.setattr(auth_routes, "hash_verification_code", lambda code: f"code::{code}")
    monkeypatch.setattr(auth_routes, "verify_verification_code", lambda code, code_hash: f"code::{code}" == code_hash)
    monkeypatch.setattr(auth_routes, "create_access_token", lambda **kwargs: "access-token")
    monkeypatch.setattr(auth_routes, "create_refresh_token", lambda: "refresh-token")
    monkeypatch.setattr(auth_routes, "hash_refresh_token", lambda token: f"h::{token}")

    reg = client.post(
        "/auth/register",
        json={
            "email": "test@gsb.columbia.edu",
            "password": "longpassword1",
            "gender_identity": "man",
            "seeking_genders": ["woman"],
        },
    )
    assert reg.status_code == 201

    verify = client.post("/auth/verify-email", json={"email": "test@gsb.columbia.edu", "code": "123456"})
    assert verify.status_code == 200
    assert store["users_by_email"]["test@gsb.columbia.edu"]["is_email_verified"] is True

    login = client.post("/auth/login", json={"email": "test@gsb.columbia.edu", "password": "longpassword1"})
    assert login.status_code == 200
    out = login.json()
    # Auth now uses httpOnly cookies - check for user info instead of tokens
    assert "id" in out
    assert out["email"] == "test@gsb.columbia.edu"
    # Check that session cookie was set
    assert "session" in login.cookies or any("session" in c for c in client.cookies)


def test_auth_register_dev_mode_token_gating(monkeypatch):
    client = _client(monkeypatch)
    created_users = 0

    def create_user(email: str, password_hash: str, username: str | None = None, tenant_id: str | None = None):
        nonlocal created_users
        created_users += 1
        return {
            "id": f"00000000-0000-0000-0000-{created_users:012d}",
            "email": email,
            "password_hash": password_hash,
            "is_email_verified": False,
            "disabled_at": None,
            "username": username,
            "tenant_id": tenant_id,
        }

    monkeypatch.setattr(m.auth_repo, "create_user", create_user)
    monkeypatch.setattr(m.auth_repo, "get_user_by_email", lambda email: None)
    monkeypatch.setattr(m.auth_repo, "set_user_verified", lambda user_id: None)
    monkeypatch.setattr(m.auth_repo, "update_user_profile", lambda **kwargs: {"id": kwargs.get("user_id")})
    monkeypatch.setattr(m.auth_repo, "invalidate_active_verification_tokens", lambda *args, **kwargs: None)
    monkeypatch.setattr(m.auth_repo, "create_email_verification_token", lambda *args, **kwargs: None)
    monkeypatch.setattr(m.auth_repo, "create_refresh_token_row", lambda *args, **kwargs: None)
    monkeypatch.setattr(auth_routes, "create_one_time_token", lambda: "verify-token")
    monkeypatch.setattr(auth_routes, "create_verification_code", lambda: "654321")
    monkeypatch.setattr(auth_routes, "hash_verification_code", lambda code: f"code::{code}")
    monkeypatch.setattr(auth_routes, "create_access_token", lambda **kwargs: "access-token")
    monkeypatch.setattr(auth_routes, "create_refresh_token", lambda: "refresh-token")
    monkeypatch.setattr(auth_routes, "hash_refresh_token", lambda token: f"h::{token}")

    monkeypatch.setattr(auth_routes, "DEV_MODE", False)
    res_prod = client.post(
        "/auth/register",
        json={
            "email": "prod@gsb.columbia.edu",
            "password": "longpassword1",
            "gender_identity": "man",
            "seeking_genders": ["woman"],
        },
    )
    assert res_prod.status_code == 201
    body_prod = res_prod.json()
    # Auth now uses httpOnly cookies - check for user info instead of tokens in body
    assert "id" in body_prod
    assert "email" in body_prod
    assert "dev_only" not in body_prod

    monkeypatch.setattr(auth_routes, "DEV_MODE", True)
    res_dev = client.post(
        "/auth/register",
        json={
            "email": "dev@gsb.columbia.edu",
            "password": "longpassword1",
            "gender_identity": "woman",
            "seeking_genders": ["man"],
        },
    )
    assert res_dev.status_code == 201
    body_dev = res_dev.json()
    # Auth now uses httpOnly cookies - check for user info instead of tokens in body
    assert "id" in body_dev
    assert "email" in body_dev
    assert "dev_only" not in body_dev


def test_match_requires_verified_user(monkeypatch):
    client = _client(monkeypatch)

    def unverified_user():
        raise HTTPException(status_code=403, detail="Email verification required")

    m.app.dependency_overrides[m.require_verified_user] = unverified_user
    blocked = client.get("/matches/current")
    assert blocked.status_code == 403

    m.app.dependency_overrides[m.require_verified_user] = lambda: {
        "id": "11111111-1111-1111-1111-111111111111",
        "email": "verified@gsb.columbia.edu",
        "is_email_verified": True,
    }
    monkeypatch.setattr(m, "repo_get_current_match", lambda user_id, now: None)
    allowed = client.get("/matches/current")
    assert allowed.status_code == 200

    m.app.dependency_overrides = {}


def test_sessions_enforce_ownership(monkeypatch):
    client = _client(monkeypatch)

    sessions = {}

    def fake_create_session(user_id: str, survey_slug: str, survey_version: int, survey_hash: str = "", tenant_id: str | None = None):
        sid = "33333333-3333-3333-3333-333333333333"
        sessions[sid] = {
            "session": {
                "id": sid,
                "user_id": user_id,
                "survey_slug": survey_slug,
                "survey_version": survey_version,
                "survey_hash": survey_hash,
                "tenant_id": tenant_id,
                "status": "in_progress",
            },
            "answers": {},
        }
        return {"session_id": sid, "user_id": user_id}

    monkeypatch.setattr(m, "repo_create_session", fake_create_session)
    monkeypatch.setattr(m, "repo_get_session_with_answers", lambda session_id: sessions.get(session_id))
    monkeypatch.setattr(m, "repo_upsert_answers", lambda session_id, answers: len(answers))

    current = {"id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "email": "a@gsb.columbia.edu", "is_email_verified": True}

    def dep_user():
        return current

    m.app.dependency_overrides[m.get_current_user] = dep_user

    created = client.post("/sessions")
    sid = created.json()["session_id"]

    current["id"] = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    read_other = client.get(f"/sessions/{sid}")
    assert read_other.status_code == 403

    save_other = client.post(f"/sessions/{sid}/answers", json={"answers": [{"question_code": "BF_O_01", "answer_value": 4}]})
    assert save_other.status_code == 403

    m.app.dependency_overrides = {}


def test_admin_endpoints_require_token_including_dump(monkeypatch):
    client = _client(monkeypatch)
    monkeypatch.setattr(m, "ADMIN_TOKEN", "admin-secret")
    monkeypatch.setattr(m, "repo_run_weekly_matching", lambda now: {"ok": True})
    monkeypatch.setattr(m, "repo_dump_session", lambda session_id: {"session": {"id": session_id}, "answers": [], "traits": None})

    denied_run = client.post("/admin/matches/run-weekly")
    denied_dump = client.get("/admin/sessions/11111111-1111-1111-1111-111111111111/dump")
    assert denied_run.status_code == 401
    assert denied_dump.status_code == 401

    ok_run = client.post("/admin/matches/run-weekly", headers={"X-Admin-Token": "admin-secret"})
    ok_dump = client.get("/admin/sessions/11111111-1111-1111-1111-111111111111/dump", headers={"X-Admin-Token": "admin-secret"})
    assert ok_run.status_code == 200
    assert ok_dump.status_code == 200


def test_auth_me_endpoint(monkeypatch):
    client = _client(monkeypatch)

    m.app.dependency_overrides[m.get_current_user] = lambda: {
        "id": "12345678-1234-1234-1234-123456789012",
        "email": "me@gsb.columbia.edu",
        "is_email_verified": True,
    }

    res = client.get("/auth/me")
    assert res.status_code == 200
    body = res.json()
    assert body["email"] == "me@gsb.columbia.edu"
    assert body["is_email_verified"] is True

    m.app.dependency_overrides = {}


def test_auth_login_bearer_mode_returns_tokens(monkeypatch):
    """Test that X-Auth-Mode: bearer returns tokens in response body (for mobile)."""
    client = _client(monkeypatch)
    store = {
        "users_by_email": {},
        "users_by_id": {},
        "refresh": {},
    }

    def create_user(email: str, password_hash: str, username: str | None = None, tenant_id: str | None = None):
        user = {
            "id": "11111111-1111-1111-1111-111111111111",
            "email": email,
            "password_hash": password_hash,
            "is_email_verified": True,
            "disabled_at": None,
            "username": username,
            "tenant_id": tenant_id,
        }
        store["users_by_email"][email] = user
        store["users_by_id"][user["id"]] = user
        return user

    def get_user_by_email(email: str, tenant_id: str | None = None):
        return store["users_by_email"].get(email)

    monkeypatch.setattr(m.auth_repo, "create_user", create_user)
    monkeypatch.setattr(m.auth_repo, "get_user_by_email", get_user_by_email)
    monkeypatch.setattr(m.auth_repo, "set_user_verified", lambda user_id: None)
    monkeypatch.setattr(m.auth_repo, "update_user_profile", lambda **kwargs: {"id": kwargs.get("user_id")})
    monkeypatch.setattr(m.auth_repo, "update_last_login", lambda *args, **kwargs: None)
    monkeypatch.setattr(m.auth_repo, "create_refresh_token_row", lambda user_id, token_hash, expires_at: store["refresh"].update({token_hash: {"user_id": user_id, "expires_at": expires_at, "revoked_at": None}}))
    monkeypatch.setattr(auth_routes, "create_access_token", lambda **kwargs: "access-token")
    monkeypatch.setattr(auth_routes, "create_refresh_token", lambda: "refresh-token")
    monkeypatch.setattr(auth_routes, "hash_refresh_token", lambda token: f"h::{token}")
    monkeypatch.setattr(auth_routes, "verify_password", lambda pw, hash: True)

    # Register a user first
    reg = client.post(
        "/auth/register",
        json={
            "email": "mobile@gsb.columbia.edu",
            "password": "longpassword1",
        },
    )
    assert reg.status_code == 201

    # Login with bearer mode header
    login = client.post(
        "/auth/login",
        json={"email": "mobile@gsb.columbia.edu", "password": "longpassword1"},
        headers={"X-Auth-Mode": "bearer"},
    )
    assert login.status_code == 200
    out = login.json()
    # Bearer mode should return tokens in body
    assert "access_token" in out
    assert "refresh_token" in out
    assert out["token_type"] == "bearer"
    assert "expires_in" in out


def test_auth_login_default_mode_returns_user_info(monkeypatch):
    """Test that default login (no X-Auth-Mode) returns user info, not tokens (for web)."""
    client = _client(monkeypatch)
    store = {
        "users_by_email": {},
        "users_by_id": {},
        "refresh": {},
    }

    def create_user(email: str, password_hash: str, username: str | None = None, tenant_id: str | None = None):
        user = {
            "id": "22222222-2222-2222-2222-222222222222",
            "email": email,
            "password_hash": password_hash,
            "is_email_verified": True,
            "disabled_at": None,
            "username": username,
            "tenant_id": tenant_id,
        }
        store["users_by_email"][email] = user
        store["users_by_id"][user["id"]] = user
        return user

    def get_user_by_email(email: str, tenant_id: str | None = None):
        return store["users_by_email"].get(email)

    monkeypatch.setattr(m.auth_repo, "create_user", create_user)
    monkeypatch.setattr(m.auth_repo, "get_user_by_email", get_user_by_email)
    monkeypatch.setattr(m.auth_repo, "set_user_verified", lambda user_id: None)
    monkeypatch.setattr(m.auth_repo, "update_user_profile", lambda **kwargs: {"id": kwargs.get("user_id")})
    monkeypatch.setattr(m.auth_repo, "update_last_login", lambda *args, **kwargs: None)
    monkeypatch.setattr(m.auth_repo, "create_refresh_token_row", lambda user_id, token_hash, expires_at: store["refresh"].update({token_hash: {"user_id": user_id, "expires_at": expires_at, "revoked_at": None}}))
    monkeypatch.setattr(auth_routes, "create_access_token", lambda **kwargs: "access-token")
    monkeypatch.setattr(auth_routes, "create_refresh_token", lambda: "refresh-token")
    monkeypatch.setattr(auth_routes, "hash_refresh_token", lambda token: f"h::{token}")
    monkeypatch.setattr(auth_routes, "verify_password", lambda pw, hash: True)

    # Register a user first
    reg = client.post(
        "/auth/register",
        json={
            "email": "web@gsb.columbia.edu",
            "password": "longpassword1",
        },
    )
    assert reg.status_code == 201

    # Login WITHOUT bearer mode header (default - web behavior)
    login = client.post(
        "/auth/login",
        json={"email": "web@gsb.columbia.edu", "password": "longpassword1"},
    )
    assert login.status_code == 200
    out = login.json()
    # Default mode should return user info, NOT tokens in body
    assert "id" in out
    assert "email" in out
    assert "access_token" not in out
    assert "refresh_token" not in out


def test_auth_register_bearer_mode_returns_tokens(monkeypatch):
    """Test that X-Auth-Mode: bearer on register returns tokens in response body (for mobile)."""
    client = _client(monkeypatch)

    def create_user(email: str, password_hash: str, username: str | None = None, tenant_id: str | None = None):
        return {
            "id": "33333333-3333-3333-3333-333333333333",
            "email": email,
            "password_hash": password_hash,
            "is_email_verified": False,
            "disabled_at": None,
            "username": username,
            "tenant_id": tenant_id,
        }

    monkeypatch.setattr(m.auth_repo, "create_user", create_user)
    monkeypatch.setattr(m.auth_repo, "get_user_by_email", lambda email, tenant_id=None: None)
    monkeypatch.setattr(m.auth_repo, "set_user_verified", lambda user_id: None)
    monkeypatch.setattr(m.auth_repo, "update_user_profile", lambda **kwargs: {"id": kwargs.get("user_id")})
    monkeypatch.setattr(m.auth_repo, "create_refresh_token_row", lambda *args, **kwargs: None)
    monkeypatch.setattr(auth_routes, "create_access_token", lambda **kwargs: "access-token")
    monkeypatch.setattr(auth_routes, "create_refresh_token", lambda: "refresh-token")
    monkeypatch.setattr(auth_routes, "hash_refresh_token", lambda token: f"h::{token}")

    # Register with bearer mode header
    res = client.post(
        "/auth/register",
        json={
            "email": "mobile-reg@gsb.columbia.edu",
            "password": "longpassword1",
        },
        headers={"X-Auth-Mode": "bearer"},
    )
    assert res.status_code == 201
    out = res.json()
    # Bearer mode should return tokens in body
    assert "access_token" in out
    assert "refresh_token" in out
    assert out["token_type"] == "bearer"
    assert "expires_in" in out
