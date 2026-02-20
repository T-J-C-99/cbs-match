from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

import app.main as m
import app.repo as auth_repo
import app.survey_loader as survey_loader
from app.routes import admin as admin_routes
from app.services import seeding as seeding_service
from app.services.tenancy import get_shared_tenant_definitions


class _ScalarResult:
    def __init__(self, value: int = 0):
        self._value = value

    def scalar(self):
        return self._value

    def mappings(self):
        return self

    def first(self):
        return None

    def all(self):
        return []


class _DashboardSession:
    def __init__(self, scalar_values: list[int] | None = None):
        self._scalar_values = scalar_values or [0] * 8
        self._idx = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, *args, **kwargs):
        if self._idx < len(self._scalar_values):
            out = _ScalarResult(self._scalar_values[self._idx])
            self._idx += 1
            return out
        return _ScalarResult(0)

    def commit(self):
        return None


def _client(monkeypatch) -> TestClient:
    monkeypatch.setattr(m, "wait_for_db", lambda *args, **kwargs: None)
    monkeypatch.setattr(m, "run_migrations", lambda *args, **kwargs: None)
    monkeypatch.setattr(m.survey_admin_repo, "count_definitions", lambda: 1)
    monkeypatch.setattr(m, "ADMIN_TOKEN", "admin-secret")
    return TestClient(m.app)


def _admin_headers() -> dict[str, str]:
    return {"X-Admin-Token": "admin-secret"}


def test_admin_tenants_contract_and_count(monkeypatch):
    client = _client(monkeypatch)
    monkeypatch.setattr(admin_routes, "sync_tenants_from_shared_config", lambda db: {"loaded": 7, "upserted": 7})
    defs = get_shared_tenant_definitions()
    rows = [
        {
            "id": uuid.uuid4(),
            "slug": d["slug"],
            "name": d["name"],
            "email_domains": d["email_domains"],
            "theme": d["theme"],
            "timezone": d.get("timezone") or "America/New_York",
            "created_at": datetime.now(timezone.utc),
            "disabled_at": None,
        }
        for d in defs
    ]
    monkeypatch.setattr(auth_repo, "list_tenants_admin", lambda: rows)

    res = client.get("/admin/tenants", headers=_admin_headers())
    assert res.status_code == 200
    body = res.json()
    tenants = body.get("tenants")
    assert isinstance(tenants, list)
    assert len(tenants) >= 7

    for tenant in tenants:
        assert isinstance(tenant.get("id"), str)
        assert isinstance(tenant.get("slug"), str)
        assert isinstance(tenant.get("name"), str)
        assert isinstance(tenant.get("email_domains"), list)
        assert all(isinstance(v, str) for v in tenant.get("email_domains") or [])
        assert isinstance(tenant.get("theme"), dict)
        tz = tenant.get("timezone")
        assert tz is None or isinstance(tz, str)
        disabled_at = tenant.get("disabled_at")
        assert disabled_at is None or isinstance(disabled_at, str)


def test_admin_tenants_not_scoped_by_tenant_header(monkeypatch):
    client = _client(monkeypatch)
    monkeypatch.setattr(admin_routes, "sync_tenants_from_shared_config", lambda db: {"loaded": 7, "upserted": 7})
    defs = get_shared_tenant_definitions()
    rows = [
        {
            "id": uuid.uuid4(),
            "slug": d["slug"],
            "name": d["name"],
            "email_domains": d["email_domains"],
            "theme": d["theme"],
            "timezone": d.get("timezone") or "America/New_York",
            "created_at": datetime.now(timezone.utc),
            "disabled_at": None,
        }
        for d in defs
    ]
    monkeypatch.setattr(auth_repo, "list_tenants_admin", lambda include_disabled=False: rows)

    res = client.get("/admin/tenants", headers={**_admin_headers(), "X-Tenant-Slug": "cbs"})
    assert res.status_code == 200
    tenants = res.json().get("tenants") or []
    assert len(tenants) == len(rows)
    assert {t.get("slug") for t in tenants} == {r["slug"] for r in rows}


def test_seed_all_tenants_calls_seed_per_tenant(monkeypatch):
    defs = get_shared_tenant_definitions()

    class _Rows:
        def __init__(self, rows):
            self._rows = rows

        def mappings(self):
            return self

        def all(self):
            return self._rows

    class _FakeDB:
        def execute(self, *_args, **_kwargs):
            return _Rows([{"slug": d["slug"]} for d in defs])

        def commit(self):
            return None

    called: list[str] = []

    monkeypatch.setattr(seeding_service, "sync_tenants_from_shared_config", lambda db: {"loaded": 7, "upserted": 7})

    def _fake_seed_dummy_data(**kwargs):
        slug = str(kwargs.get("tenant_slug") or "")
        called.append(slug)
        return {"tenant_slug": slug, "qa_credentials": []}

    monkeypatch.setattr(seeding_service, "seed_dummy_data", _fake_seed_dummy_data)

    summary = seeding_service.seed_all_tenants_dummy_data(
        db=_FakeDB(),
        survey_def={"screens": []},
        survey_slug="test",
        survey_version=1,
        n_users_per_tenant=3,
        reset=True,
        include_qa_login=False,
    )

    expected_slugs = [d["slug"] for d in defs]
    assert called == expected_slugs
    assert summary.get("tenants_seeded") == len(expected_slugs)


def test_admin_dashboard_uses_global_scope_when_tenant_slug_missing(monkeypatch):
    client = _client(monkeypatch)
    calls: list[str | None] = []
    monkeypatch.setattr(admin_routes, "_tenant_id_from_slug", lambda tenant_slug: calls.append(tenant_slug) or None)
    monkeypatch.setattr(admin_routes, "SessionLocal", lambda: _DashboardSession([21, 14, 12, 8, 3, 2, 1, 0]))
    monkeypatch.setattr(auth_repo, "list_admin_audit_events", lambda limit=20: [])
    monkeypatch.setattr(auth_repo, "list_match_reports_admin", lambda **kwargs: [])

    res = client.get("/admin/dashboard", headers=_admin_headers())
    assert res.status_code == 200
    assert calls == [None]
    assert res.json()["kpis"]["users_total"] == 21


def test_admin_users_contract_json_safe(monkeypatch):
    client = _client(monkeypatch)
    monkeypatch.setattr(admin_routes, "_tenant_id_from_slug", lambda tenant_slug: None)
    monkeypatch.setattr(
        auth_repo,
        "list_users_admin",
        lambda **kwargs: [
            {
                "id": uuid.uuid4(),
                "tenant_id": uuid.uuid4(),
                "tenant_slug": "cbs",
                "email": "u1@gsb.columbia.edu",
                "username": "u1",
                "display_name": "User One",
                "seeking_genders": ["woman"],
                "photo_urls": [],
                "pause_matches": False,
                "is_email_verified": True,
                "created_at": datetime.now(timezone.utc),
                "last_login_at": datetime.now(timezone.utc),
                "disabled_at": None,
                "onboarding_status": "complete",
                "is_match_eligible": True,
            }
        ],
    )

    res = client.get("/admin/users?tenant_slug=cbs&limit=1", headers=_admin_headers())
    assert res.status_code == 200
    payload = res.json()
    assert isinstance(payload.get("count"), int)
    users = payload.get("users")
    assert isinstance(users, list)
    assert len(users) == 1
    user = users[0]
    assert isinstance(user.get("id"), str)
    assert isinstance(user.get("email"), str)
    assert isinstance(user.get("display_name"), str)
    assert isinstance(user.get("created_at"), str)
    assert user.get("disabled_at") is None or isinstance(user.get("disabled_at"), str)


def test_admin_dashboard_contract_has_numeric_kpis(monkeypatch):
    client = _client(monkeypatch)
    monkeypatch.setattr(admin_routes, "_tenant_id_from_slug", lambda tenant_slug: None)
    monkeypatch.setattr(admin_routes, "SessionLocal", lambda: _DashboardSession([10, 8, 7, 6, 4, 3, 2, 1]))
    monkeypatch.setattr(
        auth_repo,
        "list_admin_audit_events",
        lambda limit=20: [{"id": uuid.uuid4(), "created_at": datetime.now(timezone.utc), "payload_json": {"ok": True}}],
    )
    monkeypatch.setattr(auth_repo, "list_match_reports_admin", lambda **kwargs: [])

    res = client.get("/admin/dashboard", headers=_admin_headers())
    assert res.status_code == 200
    body = res.json()
    kpis = body.get("kpis")
    assert isinstance(kpis, dict)
    for key in [
        "users_total",
        "onboarding_completion_pct",
        "match_eligible_pct",
        "matches_generated_this_week_rows",
        "accept_rate",
        "feedback_count",
        "open_safety_reports_count",
        "outbox_queued_count_v2",
    ]:
        assert key in kpis
        assert isinstance(kpis[key], (int, float))


def test_admin_tenant_coverage_endpoint_shape(monkeypatch):
    client = _client(monkeypatch)

    tenant_rows = [
        {
            "id": uuid.uuid4(),
            "slug": "cbs",
            "name": "CBS",
            "email_domains": ["gsb.columbia.edu"],
            "theme": {},
            "timezone": "America/New_York",
            "created_at": datetime.now(timezone.utc),
            "disabled_at": None,
        },
        {
            "id": uuid.uuid4(),
            "slug": "hbs",
            "name": "HBS",
            "email_domains": ["hbs.edu"],
            "theme": {},
            "timezone": "America/New_York",
            "created_at": datetime.now(timezone.utc),
            "disabled_at": None,
        },
    ]
    monkeypatch.setattr(auth_repo, "list_tenants_admin", lambda include_disabled=False: tenant_rows)

    # For each tenant coverage row route executes 6 scalar queries.
    monkeypatch.setattr(admin_routes, "SessionLocal", lambda: _DashboardSession([11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0]))

    res = client.get("/admin/diagnostics/tenant-coverage", headers=_admin_headers())
    assert res.status_code == 200
    body = res.json()
    rows = body.get("by_tenant")
    assert isinstance(rows, list)
    assert len(rows) == 2
    one = rows[0]
    for key in [
        "tenant_slug",
        "tenant_name",
        "users_total",
        "users_with_completed_survey",
        "users_with_traits",
        "weekly_assignment_rows",
        "outbox_pending",
        "open_reports",
    ]:
        assert key in one


def test_admin_seed_backfill_existing_users_calls_service(monkeypatch):
    client = _client(monkeypatch)

    monkeypatch.setattr(admin_routes, "SessionLocal", lambda: _DashboardSession())

    called: dict[str, object] = {}

    def _fake_backfill(**kwargs):
        called.update(kwargs)
        return {
            "mode": "backfill_existing_users",
            "users_seeded": 12,
            "users_skipped_existing": 3,
            "survey_slug": "match-core-v3",
            "survey_version": 1,
        }

    monkeypatch.setattr(admin_routes, "backfill_existing_users_survey_data", _fake_backfill)

    res = client.post(
        "/admin/seed",
        headers=_admin_headers(),
        json={"all_tenants": True, "backfill_existing_users": True, "force_reseed": False},
    )
    assert res.status_code == 200
    body = res.json()
    assert body.get("mode") == "backfill_existing_users"
    assert body.get("users_seeded") == 12
    assert called.get("all_tenants") is True
    assert called.get("force_reseed") is False


def test_admin_seed_backfill_repairs_missing_gender_preferences(monkeypatch):
    client = _client(monkeypatch)

    class _Rows:
        def __init__(self, rows):
            self._rows = rows

        def mappings(self):
            return self

        def all(self):
            return self._rows

        def first(self):
            return self._rows[0] if self._rows else None

    class _FakeDB:
        def __init__(self):
            self.updates = 0
            self._seeded = 0

        def execute(self, query, params=None):
            sql = str(query)
            if "FROM user_account ua" in sql:
                return _Rows([
                    {
                        "user_id": str(uuid.uuid4()),
                        "tenant_id": str(uuid.uuid4()),
                        "tenant_slug": "cbs",
                        "gender_identity": None,
                        "seeking_genders": [],
                    },
                    {
                        "user_id": str(uuid.uuid4()),
                        "tenant_id": str(uuid.uuid4()),
                        "tenant_slug": "cbs",
                        "gender_identity": "woman",
                        "seeking_genders": ["man"],
                    },
                ])
            if "FROM survey_session" in sql and "status = 'completed'" in sql:
                return _Rows([])
            if "FROM user_traits" in sql:
                return _Rows([])
            if "UPDATE user_account" in sql or "INSERT INTO user_profile" in sql:
                self.updates += 1
                return _Rows([])
            return _Rows([])

        def commit(self):
            return None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    fake_db = _FakeDB()
    monkeypatch.setattr(admin_routes, "SessionLocal", lambda: fake_db)

    def _fake_seed_for_user(*args, **kwargs):
        fake_db._seeded += 1
        return {}, {}

    monkeypatch.setattr(seeding_service, "_seed_survey_for_user", _fake_seed_for_user)
    monkeypatch.setattr(survey_loader, "get_survey_definition", lambda tenant_slug=None: {"screens": [], "option_sets": {}})

    res = client.post(
        "/admin/seed",
        headers=_admin_headers(),
        json={"all_tenants": True, "backfill_existing_users": True, "force_reseed": False},
    )
    assert res.status_code == 200
    body = res.json()
    assert body.get("users_seeded") == 2
    assert body.get("users_profile_defaults_applied") == 1
    assert fake_db.updates >= 2
