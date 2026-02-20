import copy

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

import app.main as m


def _client(monkeypatch):
    monkeypatch.setattr(m, "wait_for_db", lambda *args, **kwargs: None)
    monkeypatch.setattr(m, "run_migrations", lambda *args, **kwargs: None)
    monkeypatch.setattr(m.survey_admin_repo, "count_definitions", lambda: 1)
    return TestClient(m.app)


def test_validate_latest_draft_returns_structured_errors(monkeypatch):
    client = _client(monkeypatch)
    monkeypatch.setattr(m, "ADMIN_TOKEN", "admin-secret")

    bad_draft = {
        "survey": {"slug": "cbs-match-v1", "version": 999, "name": "Bad", "status": "draft"},
        "option_sets": {
            "consent": [
                {"label": "Yes", "value": "yes"},
                {"label": "No", "value": "no"},
            ]
        },
        "screens": [
            {
                "key": "screen-a",
                "ordinal": 1,
                "title": "A",
                "items": [
                    {
                        "question": {
                            "code": "Q1",
                            "text": "Question 1",
                            "response_type": "single_select",
                            "is_required": True,
                            "allow_skip": False,
                        },
                        "options": "consent",
                        "rules": [],
                    }
                ],
            },
            {
                "key": "screen-a",
                "ordinal": 2,
                "title": "B",
                "items": [
                    {
                        "question": {
                            "code": "Q2",
                            "text": "Question 2",
                            "response_type": "single_select",
                            "is_required": True,
                            "allow_skip": False,
                        },
                        "options": "missing_set",
                        "rules": [
                            {
                                "type": "show_if",
                                "trigger_question_code": "Q1",
                                "operator": "in",
                                "trigger_value": "yes",
                            }
                        ],
                    }
                ],
            },
        ],
    }

    monkeypatch.setattr(m.survey_admin_repo, "get_latest_draft", lambda slug: {"definition_json": bad_draft})

    res = client.post("/admin/survey/draft/latest/validate", headers={"X-Admin-Token": "admin-secret"})
    assert res.status_code == 400
    detail = res.json()["detail"]
    assert detail["message"] == "Validation failed"
    assert isinstance(detail["errors"], list)
    assert any(err["code"] == "duplicate_screen_key" for err in detail["errors"])
    assert any(err["code"] == "missing_option_set" for err in detail["errors"])
    assert any(err["code"] == "invalid_trigger_value_shape" for err in detail["errors"])


def test_publish_promotes_only_one_active(monkeypatch):
    client = _client(monkeypatch)
    monkeypatch.setattr(m, "ADMIN_TOKEN", "admin-secret")

    base = m.get_file_survey_definition()
    state = {
        "active": {
            "id": "a1",
            "version": 1,
            "status": "published",
            "is_active": True,
            "definition_json": copy.deepcopy(base),
        },
        "draft": {
            "id": "d2",
            "version": 2,
            "status": "draft",
            "is_active": False,
            "definition_json": copy.deepcopy(base),
        },
        "published": [
            {"id": "a1", "version": 1, "status": "published", "is_active": True, "definition_json": copy.deepcopy(base)},
        ],
    }

    def fake_get_latest_draft(slug):
        return state["draft"]

    def fake_publish(slug, actor_user_id):
        state["active"]["is_active"] = False
        state["draft"]["status"] = "published"
        state["draft"]["is_active"] = True
        state["active"] = state["draft"]
        state["published"] = [
            {"id": "a1", "version": 1, "status": "published", "is_active": False, "definition_json": copy.deepcopy(base)},
            {"id": "d2", "version": 2, "status": "published", "is_active": True, "definition_json": copy.deepcopy(base)},
        ]
        return state["active"]

    monkeypatch.setattr(m.survey_admin_repo, "get_latest_draft", fake_get_latest_draft)
    monkeypatch.setattr(m.survey_admin_repo, "publish_latest_draft", fake_publish)
    monkeypatch.setattr(m.survey_admin_repo, "get_active_definition", lambda slug: state["active"])
    monkeypatch.setattr(m.survey_admin_repo, "list_published_definitions", lambda slug: state["published"])

    pub = client.post("/admin/survey/draft/latest/publish", headers={"X-Admin-Token": "admin-secret"})
    assert pub.status_code == 200
    assert pub.json()["active"]["version"] == 2

    admin_view = client.get("/admin/survey/active", headers={"X-Admin-Token": "admin-secret"})
    assert admin_view.status_code == 200
    versions = admin_view.json()["published_versions"]
    active_count = sum(1 for p in versions if p["is_active"])
    assert active_count == 1
