import uuid
from datetime import datetime, timezone

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

import app.main as m
from app.routes import auth as auth_routes


def test_session_answer_complete_and_match_flow(monkeypatch):
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
    monkeypatch.setattr(m, "get_survey_definition", lambda: {"survey": {"slug": "cbs_match", "version": 1}, "screens": []})
    monkeypatch.setattr(m, "_validate_admin_token", lambda token: None)
    monkeypatch.setattr(m, "SessionLocal", lambda: _DummySession())
    monkeypatch.setattr(auth_routes, "SessionLocal", lambda: _DummySession())
    monkeypatch.setattr(auth_routes, "resolve_tenant_for_email", lambda db, email: {"id": None, "slug": "cbs"})
    monkeypatch.setattr(m.auth_repo, "ensure_chat_thread", lambda week_start_date, user_a_id, user_b_id: {"id": str(uuid.uuid4())})

    store = {"sessions": {}, "answers": {}, "traits": {}, "match": {}, "feedback": {}}

    def fake_create_session(user_id: str, survey_slug: str, survey_version: int, survey_hash: str = "", tenant_id: str | None = None):
        sid = str(uuid.uuid4())
        store["sessions"][sid] = {"id": sid, "user_id": user_id, "survey_slug": survey_slug, "survey_version": survey_version, "survey_hash": survey_hash, "tenant_id": tenant_id}
        store["answers"][sid] = {}
        return {"session_id": sid, "user_id": user_id}

    def fake_get_session_with_answers(session_id: str):
        s = store["sessions"].get(session_id)
        if not s:
            return None
        return {"session": s, "answers": store["answers"][session_id]}

    def fake_upsert_answers(session_id: str, answers):
        for a in answers:
            store["answers"][session_id][a["question_code"]] = a["answer_value"]
        return len(answers)

    def fake_complete_session(session_id: str, survey_def):
        user_id = store["sessions"][session_id]["user_id"]
        traits = {"traits_version": 2, "big5": {"openness": 0.6, "conscientiousness": 0.6, "extraversion": 0.6, "agreeableness": 0.6, "neuroticism": 0.4}, "life_constraints": {"kids_preference": "yes"}, "fun_answers": {"FUN_TRAVEL": "city"}}
        store["traits"][user_id] = traits
        return {
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "traits": traits,
            "vibe_card": {"title": "The Intentional Spark", "strengths": ["x", "y"]},
        }

    def fake_get_current_match(user_id: str, now: datetime):
        row = store["match"].get(user_id)
        if not row:
            return None
        row = dict(row)
        row["explanation"] = {"bullets": ["b1", "b2", "b3"], "icebreakers": ["i1", "i2"]}
        row["feedback"] = {"eligible": row.get("status") == "accepted", "already_submitted": user_id in store["feedback"], "due_met_question": True}
        return row

    def fake_update_current_match_status(user_id: str, action: str, now: datetime):
        row = store["match"].get(user_id)
        if row and action == "accept":
            row["status"] = "accepted"
        if row and action == "decline":
            row["status"] = "declined"
        return {"status": row["status"] if row else "none"}

    def fake_submit_feedback(user_id: str, now: datetime, answers):
        store["feedback"][user_id] = answers
        return {"status": "submitted", "answers": answers, "week_start_date": "2026-02-09"}

    def fake_run_weekly_matching(now: datetime):
        users = list(store["traits"].keys())
        if len(users) >= 2:
            a, b = users[0], users[1]
            base = {
                "week_start_date": "2026-02-09",
                "score_total": 0.72,
                "score_breakdown": {"big5_similarity": 0.8, "conflict_similarity": 0.7, "modifier_multiplier": 0.95},
                "status": "revealed",
                "expires_at": now.isoformat(),
            }
            store["match"][a] = {**base, "matched_user_id": b}
            store["match"][b] = {**base, "matched_user_id": a}
        return {"created_assignments": len(store["match"]), "matched_pairs": len(store["match"]) // 2, "no_match_count": 0}

    monkeypatch.setattr(m, "repo_create_session", fake_create_session)
    monkeypatch.setattr(m, "repo_get_session_with_answers", fake_get_session_with_answers)
    monkeypatch.setattr(m, "repo_upsert_answers", fake_upsert_answers)
    monkeypatch.setattr(m, "repo_complete_session", fake_complete_session)
    monkeypatch.setattr(m, "repo_get_current_match", fake_get_current_match)
    monkeypatch.setattr(m, "repo_update_current_match_status", fake_update_current_match_status)
    monkeypatch.setattr(m, "repo_submit_match_feedback", fake_submit_feedback)
    monkeypatch.setattr(m, "repo_run_weekly_matching", fake_run_weekly_matching)

    client = TestClient(m.app)

    user1 = str(uuid.uuid4())
    user2 = str(uuid.uuid4())

    active = {"id": user1, "email": "u1@gsb.columbia.edu", "is_email_verified": True}

    def dep_current_user():
        return active

    m.app.dependency_overrides[m.get_current_user] = dep_current_user
    m.app.dependency_overrides[m.require_verified_user] = dep_current_user

    s1 = client.post("/sessions").json()["session_id"]
    active["id"] = user2
    active["email"] = "u2@gsb.columbia.edu"
    s2 = client.post("/sessions").json()["session_id"]

    active["id"] = user1
    active["email"] = "u1@gsb.columbia.edu"
    save_resp = client.post(f"/sessions/{s1}/answers", json={"answers": [{"question_code": "BF_O_01", "answer_value": 4}]})
    assert save_resp.status_code == 200

    assert client.post(f"/sessions/{s1}/complete").status_code == 200
    active["id"] = user2
    active["email"] = "u2@gsb.columbia.edu"
    assert client.post(f"/sessions/{s2}/complete").status_code == 200

    run_resp = client.post("/admin/matches/run-weekly", headers={"X-Admin-Token": "dev-admin-token"})
    assert run_resp.status_code == 200

    active["id"] = user1
    assert client.post("/matches/current/accept").status_code == 200
    active["id"] = user2
    assert client.post("/matches/current/accept").status_code == 200

    active["id"] = user1
    cur = client.get("/matches/current")
    assert cur.status_code == 200
    payload = cur.json()
    assert "explanation" in payload
    assert len(payload["explanation"]["bullets"]) == 3

    fb = client.post("/matches/current/feedback", json={"answers": {"coffee_intent": 5, "met": True, "chemistry": 4, "respect": 5}})
    assert fb.status_code == 200
    assert fb.json()["status"] == "submitted"

    contact = client.post("/matches/current/contact-click", json={"channel": "instagram"})
    assert contact.status_code == 200
    assert contact.json()["channel"] == "instagram"

    m.app.dependency_overrides = {}
