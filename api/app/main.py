import json
import os
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from .config import (
    ADMIN_TOKEN,
    DEFAULT_MATCHING_CONFIG,
    LOOKBACK_WEEKS,
    MATCH_ALGO_MODE,
    MATCH_EXPIRY_HOURS,
    MATCH_TOP_K,
    MATCH_TIMEZONE,
    MIN_SCORE,
    RL_MATCH_ACCEPT_LIMIT,
    RL_MATCH_DECLINE_LIMIT,
    RL_MATCH_FEEDBACK_LIMIT,
    RL_SESSION_ANSWERS_LIMIT,
    RL_WINDOW_SECONDS,
    SURVEY_SLUG,
    SURVEY_VERSION,
)
from .database import SessionLocal
from .services.calibration import compute_calibration_report
from .services.events import log_analytics_event, log_match_event, log_product_event, log_profile_event
from .services.explanations import build_safe_explanation, build_safe_explanation_v2, generate_profile_insights
from .services.matching import (
    build_candidate_pairs,
    create_weekly_assignments,
    fetch_eligible_users,
    fetch_eligibility_debug_counts,
    fetch_recent_pairs,
    fetch_recent_pairs_for_tenant,
    get_week_start_date,
    stable_match,
)
from .services.seeding import seed_dummy_data
from .services.metrics import metrics_funnel_summary, metrics_weekly_funnel
from .services.tenancy import get_default_tenant, get_tenant_by_slug, sync_tenants_from_shared_config
from .services.state_machine import transition_status
from .services.rate_limit import rate_limit_dependency
from .services.survey_validation import validate_survey_definition
from .services.survey_runtime import get_active_survey_runtime
from .services.vibe_card import generate_vibe_card
from .services.survey_reconciliation import (
    get_user_survey_status,
    reconcile_user_survey_to_current,
)
from .http_helpers import validate_username
from .deps import parse_actor_user_id as _parse_actor_user_id
from .deps import tenant_context_from_user as _tenant_context_from_user
from .deps import tenant_id_from_user as _tenant_id_from_user
from .deps import validate_admin_token as _validate_admin_token_impl
from .routes import include_modular_routers
from .survey_loader import get_file_survey_definition, get_survey_definition
from . import survey_admin_repo
from .traits import compute_traits
from . import repo as auth_repo
from .auth.deps import get_current_user, require_verified_user

app = FastAPI(title="CBS Match API")
include_modular_routers(app)

UPLOADS_DIR = Path(__file__).resolve().parents[1] / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")

# CORS configuration - specific origins required for credentials: "include"
# Cannot use wildcard "*" with credentials mode
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,  # Required for cookie-based auth
    allow_methods=["*"],
    allow_headers=["*"],
)

RL_SESSION_ANSWERS = rate_limit_dependency("session_answers", RL_SESSION_ANSWERS_LIMIT, RL_WINDOW_SECONDS)
RL_MATCH_ACCEPT = rate_limit_dependency("match_accept", RL_MATCH_ACCEPT_LIMIT, RL_WINDOW_SECONDS)
RL_MATCH_DECLINE = rate_limit_dependency("match_decline", RL_MATCH_DECLINE_LIMIT, RL_WINDOW_SECONDS)
RL_MATCH_FEEDBACK = rate_limit_dependency("match_feedback", RL_MATCH_FEEDBACK_LIMIT, RL_WINDOW_SECONDS)



def run_migrations() -> None:
    env_dir = os.getenv("MIGRATIONS_DIR", "").strip()
    docker_dir = Path("/app/migrations")
    local_dir = Path(__file__).resolve().parents[1] / "migrations"

    if env_dir:
        migrations_dir = Path(env_dir)
    elif docker_dir.exists():
        migrations_dir = docker_dir
    else:
        migrations_dir = local_dir

    if not migrations_dir.exists() or not migrations_dir.is_dir():
        raise FileNotFoundError(
            "Migrations directory not found. Checked: "
            f"MIGRATIONS_DIR={env_dir or '<unset>'}, {docker_dir}, {local_dir}"
        )

    files = sorted([f.name for f in migrations_dir.iterdir() if f.is_file() and f.suffix == ".sql"])
    with SessionLocal() as db:
        for fname in files:
            sql = (migrations_dir / fname).read_text(encoding="utf-8")
            db.execute(text(sql))
        db.commit()


def wait_for_db(max_attempts: int = 20, delay_seconds: float = 1.5) -> None:
    last_err: Exception | None = None
    for _ in range(max_attempts):
        try:
            with SessionLocal() as db:
                db.execute(text("SELECT 1"))
                db.commit()
            return
        except OperationalError as exc:
            last_err = exc
            time.sleep(delay_seconds)
    if last_err:
        raise last_err


@app.on_event("startup")
def on_startup() -> None:
    wait_for_db()
    run_migrations()
    with SessionLocal() as db:
        sync_tenants_from_shared_config(db)
        db.commit()
    # Bootstrap per SURVEY_SLUG, not global row count, to avoid "active: none"
    # when legacy rows exist under other slugs.
    if not survey_admin_repo.get_active_definition(SURVEY_SLUG):
        survey_admin_repo.bootstrap_initial_definition(
            slug=SURVEY_SLUG,
            version=SURVEY_VERSION,
            definition_json=get_file_survey_definition(),
        )


def _validate_admin_token(token: str | None) -> None:
    _validate_admin_token_impl(token, ADMIN_TOKEN)


def repo_create_session(user_id: str, survey_slug: str, survey_version: int, survey_hash: str | None = None, tenant_id: str | None = None) -> dict[str, str]:
    session_id = str(uuid.uuid4())
    with SessionLocal() as db:
        db.execute(
            text(
                """
                INSERT INTO survey_session (id, user_id, survey_slug, survey_version, status, tenant_id)
                VALUES (:id, :user_id, :survey_slug, :survey_version, 'in_progress', CAST(NULLIF(:tenant_id, '') AS uuid))
                """
            ),
            {
                "id": session_id,
                "user_id": user_id,
                "survey_slug": survey_slug,
                "survey_version": survey_version,
                "tenant_id": tenant_id or "",
            },
        )
        log_product_event(
            db,
            event_name="survey_started",
            user_id=user_id,
            tenant_id=tenant_id,
            session_id=session_id,
            properties={"survey_slug": survey_slug, "survey_version": survey_version},
        )
        if survey_hash:
            db.execute(
                text("UPDATE survey_session SET survey_hash=:survey_hash WHERE id=CAST(:id AS uuid)"),
                {"id": session_id, "survey_hash": survey_hash},
            )
        log_analytics_event(
            db,
            event_name="survey_started",
            user_id=user_id,
            tenant_id=tenant_id,
            properties={"survey_slug": survey_slug, "survey_version": survey_version},
            source="api",
        )
        db.commit()
    return {"session_id": session_id, "user_id": user_id}


def repo_get_latest_in_progress_session(user_id: str, survey_slug: str, survey_version: int, survey_hash: str | None = None) -> dict[str, Any] | None:
    with SessionLocal() as db:
        row = db.execute(
            text(
                """
                SELECT id, user_id, survey_slug, survey_version, status, started_at, completed_at, tenant_id
                FROM survey_session
                WHERE user_id = :user_id
                  AND survey_slug = :survey_slug
                  AND survey_version = :survey_version
                  AND (:survey_hash IS NULL OR survey_hash = :survey_hash)
                  AND status = 'in_progress'
                ORDER BY started_at DESC
                LIMIT 1
                """
            ),
            {
                "user_id": user_id,
                "survey_slug": survey_slug,
                "survey_version": survey_version,
                "survey_hash": survey_hash,
            },
        ).mappings().first()
    return dict(row) if row else None


def repo_get_latest_session_for_slug(user_id: str, survey_slug: str) -> dict[str, Any] | None:
    with SessionLocal() as db:
        row = db.execute(
            text(
                """
                SELECT id, user_id, survey_slug, survey_version, status, started_at, completed_at, tenant_id
                FROM survey_session
                WHERE user_id = :user_id
                  AND survey_slug = :survey_slug
                ORDER BY COALESCE(completed_at, started_at) DESC
                LIMIT 1
                """
            ),
            {
                "user_id": user_id,
                "survey_slug": survey_slug,
            },
        ).mappings().first()
    return dict(row) if row else None


def repo_get_session_with_answers(session_id: str) -> dict[str, Any] | None:
    with SessionLocal() as db:
        session_row = db.execute(text("SELECT * FROM survey_session WHERE id = :id"), {"id": session_id}).mappings().first()
        if not session_row:
            return None

        answer_rows = db.execute(
            text("SELECT question_code, answer_value FROM survey_answer WHERE session_id = :sid"),
            {"sid": session_id},
        ).mappings().all()

    return {
        "session": dict(session_row),
        "answers": {r["question_code"]: r["answer_value"] for r in answer_rows},
    }


def repo_upsert_answers(session_id: str, answers: list[dict[str, Any]]) -> int:
    with SessionLocal() as db:
        exists = db.execute(text("SELECT 1 FROM survey_session WHERE id=:id"), {"id": session_id}).first()
        if not exists:
            raise HTTPException(status_code=404, detail="Session not found")

        saved_count = 0
        for ans in answers:
            question_code = ans.get("question_code")
            if not question_code:
                continue
            answer_value = ans.get("answer_value")
            db.execute(
                text(
                    """
                    INSERT INTO survey_answer (id, session_id, question_code, answer_value)
                    VALUES (:id, :session_id, :question_code, CAST(:answer_value AS jsonb))
                    ON CONFLICT (session_id, question_code)
                    DO UPDATE SET answer_value = EXCLUDED.answer_value, answered_at = NOW()
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "session_id": session_id,
                    "question_code": question_code,
                    "answer_value": json.dumps(answer_value),
                },
            )
            saved_count += 1
        db.commit()
    return saved_count


def repo_complete_session(session_id: str, survey_def: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        session_row = db.execute(text("SELECT * FROM survey_session WHERE id = :id"), {"id": session_id}).mappings().first()
        if not session_row:
            raise HTTPException(status_code=404, detail="Session not found")

        answer_rows = db.execute(
            text("SELECT question_code, answer_value FROM survey_answer WHERE session_id = :sid"),
            {"sid": session_id},
        ).mappings().all()
        answers = {r["question_code"]: r["answer_value"] for r in answer_rows}
        runtime = get_active_survey_runtime(str((session_row or {}).get("tenant_slug")) if (session_row or {}).get("tenant_slug") else None)
        survey_hash = str((runtime or {}).get("hash") or "")

        db.execute(
            text("UPDATE survey_session SET survey_hash = COALESCE(survey_hash, :survey_hash) WHERE id = CAST(:id AS uuid)"),
            {"id": session_id, "survey_hash": survey_hash},
        )

        reconcile_user_survey_to_current(
            db,
            user_id=str(session_row["user_id"]),
            tenant_id=str(session_row.get("tenant_id")) if session_row.get("tenant_id") else None,
        )
        status = get_user_survey_status(
            db,
            user_id=str(session_row["user_id"]),
            tenant_id=str(session_row.get("tenant_id")) if session_row.get("tenant_id") else None,
        )
        answers_effective = status.get("answers_current") if isinstance(status.get("answers_current"), dict) else answers
        traits = compute_traits(survey_def, answers_effective)

        big5 = (traits or {}).get("big5") or (traits or {}).get("big_five") or {}
        emo = (traits or {}).get("emotional_regulation") or {}
        inferred_n = 1.0 - float(emo.get("stability", 0.5))
        ocean_scores = {
            "openness": round(float(big5.get("openness", 0.5)) * 100),
            "conscientiousness": round(float(big5.get("conscientiousness", 0.5)) * 100),
            "extraversion": round(float(big5.get("extraversion", 0.5)) * 100),
            "agreeableness": round(float(big5.get("agreeableness", 0.5)) * 100),
            "neuroticism": round(float(big5.get("neuroticism", inferred_n)) * 100),
        }
        insights = generate_profile_insights(traits, {}, count=4)

        db.execute(
            text("UPDATE survey_session SET status = 'completed', completed_at = :completed_at WHERE id = :id"),
            {"id": session_id, "completed_at": now},
        )

        db.execute(
            text(
                """
                INSERT INTO user_traits (id, user_id, survey_slug, survey_version, traits, tenant_id)
                VALUES (:id, :user_id, :survey_slug, :survey_version, CAST(:traits AS jsonb), CAST(NULLIF(:tenant_id, '') AS uuid))
                ON CONFLICT (user_id, survey_slug, survey_version)
                DO UPDATE SET
                  traits = EXCLUDED.traits,
                  computed_at = NOW(),
                  tenant_id = EXCLUDED.tenant_id,
                  computed_for_survey_hash = :computed_for_survey_hash,
                  traits_schema_version = :traits_schema_version,
                  ocean_scores = CAST(:ocean_scores AS jsonb),
                  insights_json = CAST(:insights_json AS jsonb)
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "user_id": session_row["user_id"],
                "survey_slug": session_row["survey_slug"],
                "survey_version": session_row["survey_version"],
                "traits": json.dumps(traits),
                "tenant_id": str(session_row.get("tenant_id") or ""),
                "computed_for_survey_hash": survey_hash,
                "traits_schema_version": 3,
                "ocean_scores": json.dumps(ocean_scores),
                "insights_json": json.dumps(insights),
            },
        )

        tenant_ctx = (
            db.execute(
                text("SELECT id, slug, name, email_domains, timezone FROM tenant WHERE id=CAST(:id AS uuid)"),
                {"id": str(session_row.get("tenant_id"))},
            ).mappings().first()
            if session_row.get("tenant_id")
            else None
        )
        if not tenant_ctx:
            tenant_ctx = get_default_tenant(db)

        vibe = generate_vibe_card(
            user_id=str(session_row["user_id"]),
            survey_slug=str(session_row["survey_slug"]),
            survey_version=int(session_row["survey_version"]),
            traits=traits,
            copy_only=(traits or {}).get("copy_only") if isinstance(traits, dict) else None,
            tenant_ctx=dict(tenant_ctx),
            safety_flags={"allow_sensitive": False},
        )
        auth_repo.upsert_user_vibe_card(
            user_id=str(session_row["user_id"]),
            tenant_id=str(session_row.get("tenant_id")) if session_row.get("tenant_id") else None,
            survey_slug=str(session_row["survey_slug"]),
            survey_version=int(session_row["survey_version"]),
            vibe_json=vibe,
        )
        auth_repo.save_user_vibe_card_snapshot(
            user_id=str(session_row["user_id"]),
            tenant_id=str(session_row.get("tenant_id")) if session_row.get("tenant_id") else None,
            survey_slug=str(session_row["survey_slug"]),
            survey_version=int(session_row["survey_version"]),
            vibe_version=str(((vibe.get("meta") or {}).get("version") or "vibe-card-legacy")),
            vibe_json=vibe,
        )

        log_product_event(
            db,
            event_name="survey_completed",
            user_id=str(session_row["user_id"]),
            tenant_id=str(session_row.get("tenant_id")) if session_row.get("tenant_id") else None,
            session_id=session_id,
            properties={"survey_slug": session_row["survey_slug"], "survey_version": session_row["survey_version"]},
        )
        log_analytics_event(
            db,
            event_name="survey_completed",
            user_id=str(session_row["user_id"]),
            tenant_id=str(session_row.get("tenant_id")) if session_row.get("tenant_id") else None,
            properties={"survey_slug": session_row["survey_slug"], "survey_version": session_row["survey_version"]},
            source="api",
        )
        db.commit()

    return {"status": "completed", "completed_at": now.isoformat(), "traits": traits, "vibe_card": vibe}


def repo_dump_session(session_id: str) -> dict[str, Any]:
    with SessionLocal() as db:
        session_row = db.execute(text("SELECT * FROM survey_session WHERE id=:id"), {"id": session_id}).mappings().first()
        if not session_row:
            raise HTTPException(status_code=404, detail="Session not found")

        answers = db.execute(
            text("SELECT question_code, answer_value, answered_at FROM survey_answer WHERE session_id=:sid ORDER BY answered_at"),
            {"sid": session_id},
        ).mappings().all()

        traits = db.execute(
            text("SELECT * FROM user_traits WHERE user_id=:user_id AND survey_slug=:survey_slug AND survey_version=:survey_version"),
            {
                "user_id": session_row["user_id"],
                "survey_slug": session_row["survey_slug"],
                "survey_version": session_row["survey_version"],
            },
        ).mappings().first()

    return {"session": dict(session_row), "answers": [dict(a) for a in answers], "traits": dict(traits) if traits else None}


def _fetch_current_row(db, user_id: str, week_start: date, tenant_id: str | None = None) -> dict[str, Any] | None:
    row = db.execute(
        text(
            """
            SELECT * FROM weekly_match_assignment
            WHERE week_start_date=:week_start_date
              AND user_id=CAST(:user_id AS uuid)
              AND (:tenant_id IS NULL OR tenant_id = CAST(:tenant_id AS uuid))
            """
        ),
        {"week_start_date": week_start, "user_id": user_id, "tenant_id": tenant_id},
    ).mappings().first()
    return dict(row) if row else None


def _fetch_traits(db, user_id: str) -> dict[str, Any] | None:
    runtime = get_active_survey_runtime()
    active_slug = str(runtime.get("slug") or SURVEY_SLUG)
    active_version = int(runtime.get("version") or SURVEY_VERSION)
    row = db.execute(
        text(
            """
            SELECT traits
            FROM user_traits
            WHERE user_id=:user_id
              AND survey_slug=:survey_slug
              AND survey_version=:survey_version
            """
        ),
        {
            "user_id": user_id,
            "survey_slug": active_slug,
            "survey_version": active_version,
        },
    ).mappings().first()
    return row["traits"] if row else None


def _fetch_public_profile(db, user_id: str) -> dict[str, Any] | None:
    row = db.execute(
        text(
            """
            SELECT
              id,
              email,
              display_name,
              cbs_year,
              hometown,
              phone_number,
              instagram_handle,
              COALESCE(photo_urls, '[]'::jsonb) AS photo_urls,
              gender_identity,
              COALESCE(seeking_genders, '[]'::jsonb) AS seeking_genders
            FROM user_account
            WHERE id=CAST(:user_id AS uuid)
            """
        ),
        {"user_id": user_id},
    ).mappings().first()
    if not row:
        return None
    return {
        "id": str(row["id"]),
        "email": str(row["email"]),
        "display_name": row.get("display_name"),
        "cbs_year": row.get("cbs_year"),
        "hometown": row.get("hometown"),
        "phone_number": row.get("phone_number"),
        "instagram_handle": row.get("instagram_handle"),
        "photo_urls": row.get("photo_urls") if isinstance(row.get("photo_urls"), list) else [],
        "gender_identity": row.get("gender_identity"),
        "seeking_genders": row.get("seeking_genders") if isinstance(row.get("seeking_genders"), list) else [],
    }


def _apply_status(db, row: dict[str, Any], new_status: str) -> None:
    if row["status"] == new_status:
        return
    db.execute(text("UPDATE weekly_match_assignment SET status=:status WHERE id=:id"), {"status": new_status, "id": row["id"]})
    if row.get("matched_user_id"):
        db.execute(
            text(
                """
                UPDATE weekly_match_assignment
                SET status=:status
                WHERE week_start_date=:week_start_date
                  AND user_id=CAST(:other_user AS uuid)
                  AND matched_user_id=CAST(:user_id AS uuid)
                """
            ),
            {
                "status": new_status,
                "week_start_date": row["week_start_date"],
                "other_user": str(row["matched_user_id"]),
                "user_id": str(row["user_id"]),
            },
        )


def _feedback_meta(db, row: dict[str, Any], user_id: str, now: datetime) -> dict[str, Any]:
    due_met = now.date() >= (row["week_start_date"] + timedelta(days=3))
    if not row.get("matched_user_id"):
        return {"eligible": False, "already_submitted": False, "due_met_question": due_met}
    if str(row.get("status") or "").lower() in {"no_match", "blocked"}:
        return {"eligible": False, "already_submitted": False, "due_met_question": due_met}

    submitted = db.execute(
        text(
            """
            SELECT 1
            FROM match_feedback
            WHERE week_start_date=:week_start_date
              AND user_id=CAST(:user_id AS uuid)
            """
        ),
        {"week_start_date": row["week_start_date"], "user_id": user_id},
    ).first()

    return {
        "eligible": True,
        "already_submitted": bool(submitted),
        "due_met_question": due_met,
    }


def repo_get_current_match(user_id: str, now: datetime, tenant_id: str | None = None) -> dict[str, Any] | None:
    week_start = get_week_start_date(now, MATCH_TIMEZONE)
    with SessionLocal() as db:
        row = _fetch_current_row(db, user_id, week_start, tenant_id=tenant_id)
        if not row:
            return None

        if row.get("matched_user_id") and auth_repo.is_blocked_pair(user_id, str(row["matched_user_id"]), tenant_id=tenant_id):
            log_match_event(
                db,
                user_id=user_id,
                week_start_date=week_start,
                event_type="blocked_match_hidden",
                payload={"matched_user_id": str(row["matched_user_id"])},
                tenant_id=tenant_id,
            )
            db.commit()
            return {
                **row,
                "matched_user_id": None,
                "matched_profile": None,
                "score_total": None,
                "score_breakdown": {"reason": "blocked_match_hidden"},
                "status": "no_match",
                "explanation": {"bullets": [], "icebreakers": []},
                "feedback": {"eligible": False, "already_submitted": False, "due_met_question": False},
            }

        new_status = transition_status(row["status"], "view", now, row["expires_at"])
        if new_status != row["status"]:
            _apply_status(db, row, new_status)
            if new_status == "revealed":
                log_match_event(
                    db,
                    user_id=user_id,
                    week_start_date=week_start,
                    event_type="match_revealed",
                    payload={"match_id": str(row["id"])},
                    tenant_id=tenant_id,
                )
            if new_status == "expired":
                log_match_event(db, user_id=user_id, week_start_date=week_start, event_type="expired", payload={"match_id": str(row["id"])}, tenant_id=tenant_id)
            row["status"] = new_status

        # Hide profile details for blocked rows.
        if str(row.get("status") or "").lower() == "blocked":
            row["matched_user_id"] = None
            row["matched_profile"] = None
            row["score_total"] = None
            row["score_breakdown"] = {"reason": "blocked_match_hidden"}
            row["feedback"] = {"eligible": False, "already_submitted": False, "due_met_question": False}
            log_match_event(db, user_id=user_id, week_start_date=week_start, event_type="blocked_match_hidden", payload={}, tenant_id=tenant_id)
            db.commit()
            return row

        user_traits = _fetch_traits(db, user_id)
        matched_traits = _fetch_traits(db, str(row["matched_user_id"])) if row.get("matched_user_id") else None
        row["matched_profile"] = _fetch_public_profile(db, str(row["matched_user_id"])) if row.get("matched_user_id") else None
        row["explanation"] = build_safe_explanation(row.get("score_breakdown") or {}, user_traits, matched_traits)
        row["explanation_v2"] = build_safe_explanation_v2(row.get("score_breakdown") or {}, user_traits, matched_traits)
        row["feedback"] = _feedback_meta(db, row, user_id, now)

        log_match_event(db, user_id=user_id, week_start_date=week_start, event_type="match_viewed", payload={"status": row["status"]}, tenant_id=tenant_id)
        db.commit()
        return row


def repo_update_current_match_status(user_id: str, action: str, now: datetime, tenant_id: str | None = None) -> dict[str, Any]:
    week_start = get_week_start_date(now, MATCH_TIMEZONE)
    with SessionLocal() as db:
        row = _fetch_current_row(db, user_id, week_start, tenant_id=tenant_id)
        if not row:
            raise HTTPException(status_code=404, detail="No current match")

        new_status = transition_status(row["status"], action, now, row["expires_at"])
        if new_status != row["status"]:
            _apply_status(db, row, new_status)
            event_type = "accept" if action == "accept" and new_status == "accepted" else "decline" if action == "decline" and new_status == "declined" else "expired" if new_status == "expired" else None
            if event_type:
                log_match_event(db, user_id=user_id, week_start_date=week_start, event_type=event_type, payload={"from": row["status"], "to": new_status}, tenant_id=tenant_id)
            row["status"] = new_status
        db.commit()

    return {"status": row["status"]}


def repo_submit_match_feedback(user_id: str, now: datetime, answers: dict[str, Any], tenant_id: str | None = None) -> dict[str, Any]:
    week_start = get_week_start_date(now, MATCH_TIMEZONE)
    with SessionLocal() as db:
        row = _fetch_current_row(db, user_id, week_start, tenant_id=tenant_id)
        if not row or not row.get("matched_user_id"):
            raise HTTPException(status_code=404, detail="No current match")

        if str(row.get("status") or "").lower() in {"no_match", "blocked"}:
            raise HTTPException(status_code=400, detail="No eligible match for feedback")

        allowed = {"coffee_intent", "met", "chemistry", "respect"}
        clean = {k: v for k, v in answers.items() if k in allowed}

        due_met = now.date() >= (week_start + timedelta(days=3))
        if not due_met:
            clean.pop("met", None)
            clean.pop("chemistry", None)
            clean.pop("respect", None)

        if "coffee_intent" in clean:
            ci = int(clean["coffee_intent"])
            if ci < 1 or ci > 5:
                raise HTTPException(status_code=400, detail="coffee_intent must be 1-5")
            clean["coffee_intent"] = ci

        if "met" in clean:
            clean["met"] = bool(clean["met"])
            if clean["met"] is not True:
                clean.pop("chemistry", None)
                clean.pop("respect", None)

        for k in ("chemistry", "respect"):
            if k in clean:
                v = int(clean[k])
                if v < 1 or v > 5:
                    raise HTTPException(status_code=400, detail=f"{k} must be 1-5")
                clean[k] = v

        db.execute(
            text(
                """
                INSERT INTO match_feedback (id, week_start_date, user_id, matched_user_id, answers)
                VALUES (:id, :week_start_date, CAST(:user_id AS uuid), CAST(:matched_user_id AS uuid), CAST(:answers AS jsonb))
                ON CONFLICT (week_start_date, user_id)
                DO UPDATE SET answers=EXCLUDED.answers, submitted_at=NOW()
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "week_start_date": week_start,
                "user_id": user_id,
                "matched_user_id": str(row["matched_user_id"]),
                "answers": json.dumps(clean),
            },
        )

        log_match_event(
            db,
            user_id=user_id,
            week_start_date=week_start,
            event_type="match_feedback_submitted",
            payload={"fields": sorted(list(clean.keys()))},
            tenant_id=tenant_id,
        )
        db.commit()

    return {"status": "submitted", "week_start_date": str(week_start), "answers": clean}


def repo_run_weekly_matching(
    now: datetime,
    tenant_slug: str | None = None,
    force: bool = False,
    week_start_override: date | None = None,
) -> dict[str, Any]:
    week_start = week_start_override or get_week_start_date(now, MATCH_TIMEZONE)
    expires_at = now + timedelta(hours=MATCH_EXPIRY_HOURS)
    deleted_counts = {
        "weekly_match_assignment": 0,
        "match_event": 0,
        "match_feedback": 0,
        "notification_outbox": 0,
    }

    with SessionLocal() as db:
        tenant = get_tenant_by_slug(db, tenant_slug) if tenant_slug else get_default_tenant(db)
        if tenant_slug and not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        tenant_id = str((tenant or {}).get("id")) if tenant else None
        tenant_slug_out = str((tenant or {}).get("slug") or "cbs")
        runtime = get_active_survey_runtime(tenant_slug_out)
        runtime_slug = str(runtime.get("slug") or SURVEY_SLUG)
        runtime_version = int(runtime.get("version") or SURVEY_VERSION)

        existing = db.execute(
            text(
                """
                SELECT COUNT(1) as c
                FROM weekly_match_assignment
                WHERE week_start_date=:week_start_date
                  AND (:tenant_id IS NULL OR tenant_id = CAST(:tenant_id AS uuid))
                """
            ),
            {"week_start_date": week_start, "tenant_id": tenant_id},
        ).mappings().first()
        if existing and int(existing["c"]) > 0:
            if not force:
                return {
                    "week_start_date": str(week_start),
                    "tenant_slug": tenant_slug_out,
                    "created_assignments": 0,
                    "message": "Assignments already exist",
                }

            res = db.execute(
                text(
                    """
                    DELETE FROM weekly_match_assignment
                    WHERE week_start_date=:week_start_date
                      AND (:tenant_id IS NULL OR tenant_id = CAST(:tenant_id AS uuid))
                    """
                ),
                {"week_start_date": week_start, "tenant_id": tenant_id},
            )
            deleted_counts["weekly_match_assignment"] = int(res.rowcount or 0)

            res = db.execute(
                text(
                    """
                    DELETE FROM match_event
                    WHERE week_start_date=:week_start_date
                      AND (:tenant_id IS NULL OR tenant_id = CAST(:tenant_id AS uuid))
                    """
                ),
                {"week_start_date": week_start, "tenant_id": tenant_id},
            )
            deleted_counts["match_event"] = int(res.rowcount or 0)

            res = db.execute(
                text(
                    """
                    DELETE FROM match_feedback
                    WHERE week_start_date=:week_start_date
                      AND (:tenant_id IS NULL OR tenant_id = CAST(:tenant_id AS uuid))
                    """
                ),
                {"week_start_date": week_start, "tenant_id": tenant_id},
            )
            deleted_counts["match_feedback"] = int(res.rowcount or 0)

            res = db.execute(
                text(
                    """
                    DELETE FROM notification_outbox
                    WHERE week_start_date=:week_start_date
                      AND (:tenant_id IS NULL OR tenant_id = CAST(:tenant_id AS uuid))
                    """
                ),
                {"week_start_date": str(week_start), "tenant_id": tenant_id},
            )
            deleted_counts["notification_outbox"] = int(res.rowcount or 0)

        eligibility_debug = fetch_eligibility_debug_counts(db, runtime_slug, runtime_version, tenant_id=tenant_id)
        users = fetch_eligible_users(db, runtime_slug, runtime_version, tenant_id=tenant_id)
        recent_pairs = fetch_recent_pairs_for_tenant(db, week_start, LOOKBACK_WEEKS, tenant_id)
        blocked_pairs = auth_repo.get_block_pairs_for_matching(db, tenant_id=tenant_id)
        pairs = build_candidate_pairs(users, cfg=DEFAULT_MATCHING_CONFIG, recent_pairs=recent_pairs, blocked_pairs=blocked_pairs)
        assignments = stable_match(
            users,
            pairs,
            min_score=MIN_SCORE,
            top_k=MATCH_TOP_K,
            mode=MATCH_ALGO_MODE,
            week_start_date=week_start,
        )

        matched_users: set[str] = set()
        for pair in assignments:
            matched_users.add(pair.user_id)
            matched_users.add(pair.matched_user_id)

        unmatched_user_ids = {u["user_id"] for u in users if u["user_id"] not in matched_users}
        created = create_weekly_assignments(db, week_start, expires_at, assignments, unmatched_user_ids, tenant_id=tenant_id)

        for pair in assignments:
            for uid in [pair.user_id, pair.matched_user_id]:
                log_product_event(
                    db,
                    event_name="match_created",
                    user_id=uid,
                    tenant_id=tenant_id,
                    properties={"week_start_date": str(week_start), "score_total": pair.score_total},
                )
                log_analytics_event(
                    db,
                    event_name="match_created",
                    user_id=uid,
                    tenant_id=tenant_id,
                    properties={"week_start_date": str(week_start), "score_total": pair.score_total},
                    week_start_date=str(week_start),
                    source="api",
                )
                auth_repo.enqueue_notification(
                    user_id=uid,
                    tenant_id=tenant_id,
                    channel="email",
                    template_key="match_ready",
                    payload={"week_start_date": str(week_start)},
                    idempotency_key=auth_repo.build_notification_idempotency_key(
                        tenant_slug=tenant_slug_out,
                        user_id=uid,
                        week_start_date=str(week_start),
                        template_key="match_ready",
                    ),
                    week_start_date=str(week_start),
                )
                auth_repo.enqueue_outbox_notification(
                    tenant_id=tenant_id,
                    user_id=uid,
                    notification_type="new_match",
                    payload={"week_start_date": str(week_start)},
                    scheduled_for=now,
                    idempotency_key=f"{tenant_id or 'cbs'}:{uid}:{str(week_start)}:new_match",
                )
                auth_repo.enqueue_outbox_notification(
                    tenant_id=tenant_id,
                    user_id=uid,
                    notification_type="nudge_match_view",
                    payload={"week_start_date": str(week_start)},
                    scheduled_for=now + timedelta(hours=24),
                    idempotency_key=f"{tenant_id or 'cbs'}:{uid}:{str(week_start)}:nudge_match_view",
                )
                auth_repo.enqueue_outbox_notification(
                    tenant_id=tenant_id,
                    user_id=uid,
                    notification_type="nudge_feedback",
                    payload={"week_start_date": str(week_start)},
                    scheduled_for=now + timedelta(hours=48),
                    idempotency_key=f"{tenant_id or 'cbs'}:{uid}:{str(week_start)}:nudge_feedback",
                )

        for uid in unmatched_user_ids:
            log_match_event(db, user_id=uid, week_start_date=week_start, event_type="no_match", payload={"reason": "below_min_score_or_no_candidate"}, tenant_id=tenant_id)

        db.commit()

    return {
        "week_start_date": str(week_start),
        "tenant_slug": tenant_slug_out,
        "eligible_users": len(users),
        "candidate_pairs": len(pairs),
        "matched_pairs": len(assignments),
        "no_match_count": len(unmatched_user_ids),
        "created_assignments": created,
        "expires_at": expires_at.isoformat(),
        "lookback_weeks": LOOKBACK_WEEKS,
        "min_score": MIN_SCORE,
        "match_top_k": MATCH_TOP_K,
        "match_algo_mode": MATCH_ALGO_MODE,
        "survey_slug": runtime_slug,
        "survey_version": runtime_version,
        "eligibility_debug": eligibility_debug,
        "deleted_counts": deleted_counts,
    }




def _require_session_owner(session_id: str, user_id: str) -> dict[str, Any]:
    payload = repo_get_session_with_answers(session_id)
    if not payload:
        raise HTTPException(status_code=404, detail="Session not found")
    if str(payload["session"].get("user_id")) != str(user_id):
        raise HTTPException(status_code=403, detail="Forbidden")
    return payload


def _require_profile_payload(payload: dict[str, Any]) -> tuple[str, str | None, str | None, str | None, str | None, list[str], str | None, list[str]]:
    display_name, cbs_year, hometown, phone_number, instagram_handle, photo_urls, gender_identity, seeking_genders = _sanitize_profile_payload(payload, require_https_photo_urls=True)
    safe_name = str(display_name or "").strip()
    if not safe_name:
        raise HTTPException(status_code=400, detail="display_name is required")
    if gender_identity is None:
        raise HTTPException(status_code=400, detail="gender_identity is required")
    if not seeking_genders:
        raise HTTPException(status_code=400, detail="seeking_genders is required")
    return safe_name, cbs_year, hometown, phone_number, instagram_handle, photo_urls, gender_identity, seeking_genders

def repo_week_summary(week_start_date: date, tenant_id: str | None = None) -> dict[str, Any]:
    with SessionLocal() as db:
        rows = db.execute(
            text(
                """
                SELECT *
                FROM weekly_match_assignment
                WHERE week_start_date=:week_start_date
                  AND (:tenant_id IS NULL OR tenant_id = CAST(:tenant_id AS uuid))
                ORDER BY created_at
                """
            ),
            {"week_start_date": week_start_date, "tenant_id": tenant_id},
        ).mappings().all()
        event_rows = db.execute(
            text(
                """
                SELECT event_type, COUNT(1) as c
                FROM match_event
                WHERE week_start_date=:week_start_date
                  AND (:tenant_id IS NULL OR tenant_id = CAST(:tenant_id AS uuid))
                GROUP BY event_type
                """
            ),
            {"week_start_date": week_start_date, "tenant_id": tenant_id},
        ).mappings().all()

    status_counts: dict[str, int] = {}
    for row in rows:
        st = row["status"]
        status_counts[st] = status_counts.get(st, 0) + 1

    event_counts = {r["event_type"]: int(r["c"]) for r in event_rows}
    return {
        "week_start_date": str(week_start_date),
        "tenant_id": tenant_id,
        "total_assignments": len(rows),
        "status_counts": status_counts,
        "event_counts": event_counts,
        "assignments": [dict(r) for r in rows],
    }




@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
