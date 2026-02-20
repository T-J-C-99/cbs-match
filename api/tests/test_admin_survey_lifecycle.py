from __future__ import annotations

import uuid

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

import app.main as m
from app.routes import admin as admin_routes


def _client(monkeypatch) -> TestClient:
    monkeypatch.setattr(m, "wait_for_db", lambda *args, **kwargs: None)
    monkeypatch.setattr(m, "run_migrations", lambda *args, **kwargs: None)
    monkeypatch.setattr(m.survey_admin_repo, "count_definitions", lambda: 1)
    monkeypatch.setattr(m, "ADMIN_TOKEN", "admin-secret")
    return TestClient(m.app)


def _admin_headers() -> dict[str, str]:
    return {"X-Admin-Token": "admin-secret"}


def test_survey_initialize_from_empty_then_publish_then_rollback(monkeypatch):
    client = _client(monkeypatch)

    state = {
        "published": [],
        "draft": None,
        "active": None,
        "next_version": 1,
    }

    def _make_row(version: int, status: str, is_active: bool):
        return {
            "id": str(uuid.uuid4()),
            "slug": "match-core-v3",
            "version": version,
            "status": status,
            "is_active": is_active,
            "definition_json": {"screens": [{"key": f"k{version}", "items": []}], "option_sets": {}},
            "created_at": "2026-02-19T00:00:00Z",
        }

    monkeypatch.setattr(admin_routes, "validate_survey_definition", lambda _definition: [])
    monkeypatch.setattr(admin_routes, "SURVEY_SLUG", "match-core-v3")
    monkeypatch.setattr(admin_routes, "SURVEY_VERSION", 1)
    monkeypatch.setattr(admin_routes, "SessionLocal", lambda: type("_S", (), {"__enter__": lambda s: s, "__exit__": lambda s, *a: False})())

    monkeypatch.setattr(
        admin_routes.survey_admin_repo,
        "initialize_active_from_code",
        lambda slug, definition_json, actor_user_id, force=False: {
            "initialized": True,
            "active": state.update({"active": _make_row(state["next_version"], "published", True)}) or state["active"],
        },
    )

    def _get_active(_slug):
        return state["active"]

    def _get_latest_draft(_slug):
        return state["draft"]

    def _list_published(_slug):
        rows = list(state["published"])
        if state["active"] and state["active"] not in rows:
            rows.append(state["active"])
        return rows

    def _create_draft(_slug, _actor):
        base = state["active"]
        if not base:
            return None
        version = base["version"] + 1
        state["draft"] = _make_row(version, "draft", False)
        return state["draft"]

    def _update_draft(_slug, definition_json, _actor):
        if not state["draft"]:
            return None
        state["draft"]["definition_json"] = definition_json
        return state["draft"]

    def _publish(_slug, _actor):
        if not state["draft"]:
            return None
        state["active"] = {**state["draft"], "status": "published", "is_active": True}
        state["published"].append(state["active"])
        state["draft"] = None
        return state["active"]

    def _rollback(_slug, version, _actor):
        for row in state["published"]:
            if row["version"] == version:
                state["active"] = {**row, "is_active": True}
                return state["active"]
        return None

    monkeypatch.setattr(admin_routes.survey_admin_repo, "get_active_definition", _get_active)
    monkeypatch.setattr(admin_routes.survey_admin_repo, "get_latest_draft", _get_latest_draft)
    monkeypatch.setattr(admin_routes.survey_admin_repo, "list_published_definitions", _list_published)
    monkeypatch.setattr(admin_routes.survey_admin_repo, "create_draft_from_active", _create_draft)
    monkeypatch.setattr(admin_routes.survey_admin_repo, "update_latest_draft", _update_draft)
    monkeypatch.setattr(admin_routes.survey_admin_repo, "publish_latest_draft", _publish)
    monkeypatch.setattr(admin_routes.survey_admin_repo, "rollback_to_published_version", _rollback)

    import app.survey_loader as survey_loader
    monkeypatch.setattr(survey_loader, "get_file_survey_definition", lambda: {"screens": [], "option_sets": {}})

    import app.repo as auth_repo
    monkeypatch.setattr(auth_repo, "create_admin_audit_event", lambda **kwargs: {"ok": True})

    init_res = client.post("/admin/survey/initialize-from-code", headers=_admin_headers(), json={})
    assert init_res.status_code == 200
    assert init_res.json()["active"] is not None

    draft_res = client.post("/admin/survey/draft/from-active", headers=_admin_headers())
    assert draft_res.status_code == 200
    assert draft_res.json()["draft"]["status"] == "draft"

    save_res = client.put(
        "/admin/survey/draft/latest",
        headers=_admin_headers(),
        json={"definition_json": {"screens": [{"key": "updated", "items": []}], "option_sets": {}}},
    )
    assert save_res.status_code == 200

    validate_res = client.post("/admin/survey/draft/latest/validate", headers=_admin_headers())
    assert validate_res.status_code == 200
    assert validate_res.json()["valid"] is True

    publish_res = client.post("/admin/survey/draft/latest/publish", headers=_admin_headers())
    assert publish_res.status_code == 200
    active_after_publish = publish_res.json()["active"]
    assert active_after_publish is not None
    assert active_after_publish["status"] == "published"

    rollback_res = client.post(
        "/admin/survey/rollback",
        headers=_admin_headers(),
        json={"version": active_after_publish["version"]},
    )
    assert rollback_res.status_code == 200
    assert rollback_res.json()["active"]["version"] == active_after_publish["version"]


def test_survey_preview_returns_db_and_runtime_sources(monkeypatch):
    client = _client(monkeypatch)

    active_definition = {"screens": [{"key": "db", "items": []}], "option_sets": {}}
    runtime_definition = {"screens": [{"key": "runtime", "items": []}], "option_sets": {}}

    monkeypatch.setattr(admin_routes, "SURVEY_SLUG", "match-core-v3")
    monkeypatch.setattr(
        admin_routes.survey_admin_repo,
        "get_active_definition",
        lambda _slug: {
            "id": str(uuid.uuid4()),
            "slug": "match-core-v3",
            "version": 1,
            "status": "published",
            "is_active": True,
            "definition_json": active_definition,
            "created_at": "2026-02-19T00:00:00Z",
        },
    )

    import app.survey_loader as survey_loader

    monkeypatch.setattr(survey_loader, "get_runtime_code_definition", lambda tenant_slug=None: runtime_definition)
    monkeypatch.setattr(survey_loader, "filter_survey_for_tenant", lambda definition, tenant_slug=None: definition)

    res = client.get("/admin/survey/preview", headers=_admin_headers())
    assert res.status_code == 200
    body = res.json()
    assert body["source"] == "active_db"
    assert body["survey"] == active_definition
    assert body["active_db_survey"] == active_definition
    assert body["runtime_code_survey"] == runtime_definition


def test_survey_update_rejects_invalid_json_payload(monkeypatch):
    client = _client(monkeypatch)

    monkeypatch.setattr(admin_routes, "SURVEY_SLUG", "match-core-v3")

    monkeypatch.setattr(
        admin_routes.survey_admin_repo,
        "update_latest_draft",
        lambda _slug, _definition_json, _actor: {
            "id": str(uuid.uuid4()),
            "slug": "match-core-v3",
            "version": 2,
            "status": "draft",
            "is_active": False,
            "definition_json": {"screens": [], "option_sets": {}},
            "created_at": "2026-02-19T00:00:00Z",
        },
    )

    res = client.put(
        "/admin/survey/draft/latest",
        headers=_admin_headers(),
        json={"definition_json": "x"},
    )

    assert res.status_code == 400
    body = res.json()
    assert isinstance(body.get("detail"), dict)
    detail = body["detail"]
    assert detail.get("message") == "Invalid survey schema"
    assert detail.get("success") is False
    errors = detail.get("errors") or []
    assert any(e.get("path") == "definition_json" for e in errors if isinstance(e, dict))
    assert isinstance(detail.get("trace_id"), str)


def test_survey_update_rejects_schema_invalid_object(monkeypatch):
    client = _client(monkeypatch)

    monkeypatch.setattr(admin_routes, "SURVEY_SLUG", "match-core-v3")

    res = client.put(
        "/admin/survey/draft/latest",
        headers=_admin_headers(),
        json={"definition_json": {}},
    )

    assert res.status_code == 400
    body = res.json()
    detail = body.get("detail")
    assert isinstance(detail, dict)
    assert detail.get("message") == "Invalid survey schema"
    assert detail.get("success") is False
    errors = detail.get("errors") or []
    assert any(isinstance(e, dict) and e.get("path") == "screens" for e in errors)
    assert isinstance(detail.get("trace_id"), str)


def test_validate_and_publish_without_draft_returns_409_with_trace_id(monkeypatch):
    client = _client(monkeypatch)
    monkeypatch.setattr(admin_routes, "SURVEY_SLUG", "match-core-v3")
    monkeypatch.setattr(admin_routes.survey_admin_repo, "get_latest_draft", lambda _slug: None)

    validate_res = client.post("/admin/survey/draft/latest/validate", headers=_admin_headers())
    assert validate_res.status_code == 409
    validate_detail = validate_res.json().get("detail")
    assert isinstance(validate_detail, dict)
    assert validate_detail.get("message") == "No draft survey definition found"
    assert validate_detail.get("success") is False
    assert isinstance(validate_detail.get("trace_id"), str)

    publish_res = client.post("/admin/survey/draft/latest/publish", headers=_admin_headers())
    assert publish_res.status_code == 409
    publish_detail = publish_res.json().get("detail")
    assert isinstance(publish_detail, dict)
    assert publish_detail.get("message") == "No draft survey definition found"
    assert publish_detail.get("success") is False
    assert isinstance(publish_detail.get("trace_id"), str)
