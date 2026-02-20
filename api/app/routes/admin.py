from datetime import date, datetime, timedelta, timezone
import json
from typing import Any
import uuid

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ValidationError
from sqlalchemy import text

from .. import survey_admin_repo
from ..auth.admin_deps import get_current_admin, require_admin_role
from ..auth.security import create_admin_access_token, hash_password, verify_password
from ..config import (
    ADMIN_BOOTSTRAP_EMAIL,
    ADMIN_BOOTSTRAP_PASSWORD,
    ADMIN_SESSION_TTL_MINUTES,
    DEFAULT_MATCHING_CONFIG,
    LOOKBACK_WEEKS,
    MATCH_TIMEZONE,
    SURVEY_SLUG,
    SURVEY_VERSION,
)
from ..database import SessionLocal
from ..services.calibration import compute_calibration_report
from ..services.matching import fetch_eligibility_debug_counts, get_week_start_date
from ..services.metrics import metrics_funnel_summary, metrics_weekly_funnel
from ..services.seeding import backfill_existing_users_survey_data, seed_all_tenants_dummy_data, seed_dummy_data
from ..services.survey_validation import validate_survey_definition
from ..services.survey_reconciliation import reconcile_all_users, reconcile_and_recompute_user, get_user_survey_status
from ..services.survey_runtime import get_active_survey_runtime
from ..services.tenancy import get_tenant_by_slug, sync_tenants_from_shared_config

router = APIRouter()
scaffold_router = APIRouter()


class SurveyDraftUpdate(BaseModel):
    definition_json: Any


def _json(data: Any) -> Any:
    return jsonable_encoder(data)


def _rows_and_count(value: Any) -> tuple[list[dict[str, Any]], int]:
    if isinstance(value, tuple) and len(value) == 2:
        rows, count = value
        if isinstance(rows, list):
            return rows, int(count or 0)
    if isinstance(value, list):
        return value, len(value)
    return [], 0


def _detail(*, message: str, hint: str | None = None, errors: list[dict[str, Any]] | None = None, trace_id: str | None = None) -> dict[str, Any]:
    return {
        "success": False,
        "message": message,
        "hint": hint,
        "errors": errors or [],
        "trace_id": trace_id or str(uuid.uuid4()),
    }


def _bootstrap_admin_if_needed() -> None:
    if not ADMIN_BOOTSTRAP_EMAIL or not ADMIN_BOOTSTRAP_PASSWORD:
        return
    from .. import repo as auth_repo

    if auth_repo.get_admin_user_by_email(ADMIN_BOOTSTRAP_EMAIL):
        return
    auth_repo.ensure_bootstrap_admin(
        email=ADMIN_BOOTSTRAP_EMAIL,
        password_hash=hash_password(ADMIN_BOOTSTRAP_PASSWORD),
        role="admin",
    )


def _run_weekly_matching_compat(m, *, now: datetime, tenant_slug: str | None = None, force: bool = False) -> dict[str, Any]:
    try:
        return m.repo_run_weekly_matching(now=now, tenant_slug=tenant_slug, force=force)
    except TypeError:
        return m.repo_run_weekly_matching(now=now)


def _tenant_id_from_slug(tenant_slug: str | None) -> str | None:
    if not tenant_slug:
        return None
    with SessionLocal() as db:
        t = get_tenant_by_slug(db, tenant_slug)
    if not t:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return str(t["id"])


@scaffold_router.get("/health")
def admin_scaffold_health() -> dict[str, str]:
    return {"status": "ok", "module": "admin"}


@router.post("/admin/auth/login", dependencies=[])
def admin_auth_login(payload: dict[str, Any]) -> dict[str, Any]:
    from .. import repo as auth_repo

    _bootstrap_admin_if_needed()
    email = str(payload.get("email") or "").strip().lower()
    password = str(payload.get("password") or "")
    if not email or not password:
        raise HTTPException(status_code=400, detail="email and password required")

    admin = auth_repo.get_admin_user_by_email(email)
    if not admin or not bool(admin.get("is_active")):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not verify_password(password, str(admin.get("password_hash") or "")):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    expires_at = datetime.now(timezone.utc) + timedelta(minutes=ADMIN_SESSION_TTL_MINUTES)
    session = auth_repo.create_admin_session(str(admin["id"]), expires_at)
    token = create_admin_access_token(
        admin_id=str(admin["id"]),
        email=str(admin["email"]),
        role=str(admin.get("role") or "viewer"),
        ttl_minutes=ADMIN_SESSION_TTL_MINUTES,
        session_id=str((session or {}).get("id") or ""),
    )
    auth_repo.update_admin_last_login(str(admin["id"]))
    auth_repo.create_admin_audit_event(
        action="admin_login",
        admin_user_id=str(admin["id"]),
        payload_json={"email": email},
    )
    return _json({
        "access_token": token,
        "token_type": "bearer",
        "expires_in": ADMIN_SESSION_TTL_MINUTES * 60,
        "admin": {
            "id": str(admin["id"]),
            "email": str(admin["email"]),
            "role": str(admin.get("role") or "viewer"),
        },
    })


@router.post("/admin/auth/logout")
def admin_auth_logout(
    admin_user: dict[str, Any] = Depends(get_current_admin),
) -> dict[str, Any]:
    from .. import repo as auth_repo

    session_id = admin_user.get("session_id")
    if session_id:
        auth_repo.revoke_admin_session(str(session_id))
    auth_repo.create_admin_audit_event(
        action="admin_logout",
        admin_user_id=str(admin_user.get("id") or "") or None,
        payload_json={"auth_mode": admin_user.get("auth_mode")},
    )
    return {"ok": True}


@router.get("/admin/auth/me")
def admin_auth_me(admin_user: dict[str, Any] = Depends(get_current_admin)) -> dict[str, Any]:
    return _json({
        "admin": {
            "id": admin_user.get("id"),
            "email": admin_user.get("email"),
            "role": admin_user.get("role"),
            "auth_mode": admin_user.get("auth_mode"),
        }
    })


@router.get("/admin/dashboard")
def admin_dashboard(
    tenant_slug: str | None = None,
    admin_user: dict[str, Any] = Depends(require_admin_role("viewer")),
) -> dict[str, Any]:
    from .. import repo as auth_repo
    from .. import main as m

    _ = admin_user
    tenant_id = _tenant_id_from_slug(tenant_slug)
    open_reports_rows, _ = _rows_and_count(auth_repo.list_match_reports_admin(tenant_id=tenant_id, status="open", limit=20))
    today = datetime.now(timezone.utc)
    week_start = get_week_start_date(today, MATCH_TIMEZONE)

    with SessionLocal() as db:
        users_total = db.execute(
            m.text(
                "SELECT COUNT(1) FROM user_account WHERE disabled_at IS NULL AND (:tenant_id IS NULL OR tenant_id = CAST(:tenant_id AS uuid))"
            ),
            {"tenant_id": tenant_id},
        ).scalar() or 0
        onboarding_done = db.execute(
            m.text(
                """
                SELECT COUNT(DISTINCT ua.id)
                FROM user_account ua
                JOIN survey_session ss ON CAST(ss.user_id AS text) = CAST(ua.id AS text) AND ss.completed_at IS NOT NULL
                WHERE ua.disabled_at IS NULL
                  AND (:tenant_id IS NULL OR ua.tenant_id = CAST(:tenant_id AS uuid))
                """
            ),
            {"tenant_id": tenant_id},
        ).scalar() or 0
        eligible = db.execute(
            m.text(
                """
                SELECT COUNT(DISTINCT ua.id)
                FROM user_account ua
                JOIN user_traits ut ON CAST(ut.user_id AS text) = CAST(ua.id AS text)
                LEFT JOIN user_preferences pref ON pref.user_id = ua.id
                WHERE ua.disabled_at IS NULL
                  AND COALESCE(pref.pause_matches, FALSE) = FALSE
                  AND (:tenant_id IS NULL OR ua.tenant_id = CAST(:tenant_id AS uuid))
                """
            ),
            {"tenant_id": tenant_id},
        ).scalar() or 0
        assignments_this_week = db.execute(
            m.text(
                """
                SELECT COUNT(1)
                FROM weekly_match_assignment
                WHERE week_start_date = :week_start
                  AND (:tenant_id IS NULL OR tenant_id = CAST(:tenant_id AS uuid))
                """
            ),
            {"week_start": week_start, "tenant_id": tenant_id},
        ).scalar() or 0
        accepts = db.execute(
            m.text(
                """
                SELECT COUNT(1)
                FROM match_event
                WHERE week_start_date = :week_start
                  AND event_type='accept'
                  AND (:tenant_id IS NULL OR tenant_id = CAST(:tenant_id AS uuid))
                """
            ),
            {"week_start": week_start, "tenant_id": tenant_id},
        ).scalar() or 0
        feedback_count = db.execute(
            m.text(
                """
                SELECT COUNT(1)
                FROM match_feedback
                WHERE week_start_date = :week_start
                  AND (:tenant_id IS NULL OR tenant_id = CAST(:tenant_id AS uuid))
                """
            ),
            {"week_start": week_start, "tenant_id": tenant_id},
        ).scalar() or 0
        open_reports = db.execute(
            m.text(
                """
                SELECT COUNT(1)
                FROM match_report
                WHERE status='open'
                  AND (:tenant_id IS NULL OR tenant_id = CAST(:tenant_id AS uuid))
                """
            ),
            {"tenant_id": tenant_id},
        ).scalar() or 0
        outbox_pending = db.execute(
            m.text(
                """
                SELECT COUNT(1)
                FROM notifications_outbox
                WHERE status='pending'
                  AND (:tenant_id IS NULL OR tenant_id = CAST(:tenant_id AS uuid))
                """
            ),
            {"tenant_id": tenant_id},
        ).scalar() or 0

    accept_rate = float(accepts) / float(assignments_this_week) if assignments_this_week else 0.0
    return _json({
        "tenant_slug": tenant_slug,
        "week_start_date": str(week_start),
        "note": "weekly_match_assignment rows are per user (bidirectional pairs generate two rows)",
        "kpis": {
            "users_total": int(users_total),
            "onboarding_completion_pct": (float(onboarding_done) / float(users_total) * 100.0) if users_total else 0.0,
            "match_eligible_pct": (float(eligible) / float(users_total) * 100.0) if users_total else 0.0,
            "matches_generated_this_week_rows": int(assignments_this_week),
            "accept_rate": accept_rate,
            "feedback_count": int(feedback_count),
            "open_safety_reports_count": int(open_reports),
            "outbox_queued_count_v2": int(outbox_pending),
        },
        "recent_activity": {
            "audit": auth_repo.list_admin_audit_events(limit=20),
            "open_reports": open_reports_rows,
        },
    })


@router.get("/admin/tenants")
def admin_tenants_list(
    include_disabled: bool = False,
    admin_user: dict[str, Any] = Depends(require_admin_role("viewer")),
) -> dict[str, Any]:
    from .. import repo as auth_repo

    _ = admin_user
    # Defensive hardening: list endpoint self-heals tenant registry in case startup sync was skipped.
    with SessionLocal() as db:
        sync_tenants_from_shared_config(db)
        db.commit()
    if include_disabled:
        tenants = auth_repo.list_tenants_admin(include_disabled=True)
    else:
        tenants = auth_repo.list_tenants_admin()
    return _json({"tenants": tenants})


@router.get("/admin/audit")
def admin_audit_events(
    action: str | None = None,
    limit: int = 50,
    admin_user: dict[str, Any] = Depends(require_admin_role("viewer")),
) -> dict[str, Any]:
    from .. import repo as auth_repo

    _ = admin_user
    rows = auth_repo.list_admin_audit_events(limit=max(1, min(500, int(limit))))
    action_filter = str(action or "").strip().lower()
    if action_filter:
        rows = [r for r in rows if str(r.get("action") or "").lower() == action_filter]
    return _json({"events": rows, "count": len(rows)})


@router.post("/admin/tenants/resync-from-shared")
def admin_tenants_resync_from_shared(
    admin_user: dict[str, Any] = Depends(require_admin_role("admin")),
) -> dict[str, Any]:
    _ = admin_user
    with SessionLocal() as db:
        summary = sync_tenants_from_shared_config(db)
        db.commit()
    return _json(summary)


@router.post("/admin/tenants")
def admin_tenants_upsert(
    payload: dict[str, Any],
    admin_user: dict[str, Any] = Depends(require_admin_role("admin")),
) -> dict[str, Any]:
    from .. import repo as auth_repo

    slug = str(payload.get("slug") or "").strip().lower()
    name = str(payload.get("name") or "").strip()
    email_domains = payload.get("email_domains") or payload.get("emailDomains") or []
    theme = payload.get("theme") or {}
    timezone_value = str(payload.get("timezone") or "America/New_York")
    if not slug or not name:
        raise HTTPException(status_code=400, detail="slug and name are required")
    if not isinstance(email_domains, list):
        raise HTTPException(status_code=400, detail="email_domains must be an array")

    row = auth_repo.upsert_tenant_admin(
        slug=slug,
        name=name,
        email_domains=[str(x).strip().lower() for x in email_domains if str(x).strip()],
        theme=theme if isinstance(theme, dict) else {},
        timezone_value=timezone_value,
    )
    auth_repo.create_admin_audit_event(
        action="tenant_upsert",
        admin_user_id=str(admin_user.get("id") or "") or None,
        tenant_slug=slug,
        payload_json={"name": name},
    )
    return _json({"tenant": row})


@router.post("/admin/tenants/{tenant_slug}/disable")
def admin_tenants_disable(
    tenant_slug: str,
    admin_user: dict[str, Any] = Depends(require_admin_role("admin")),
) -> dict[str, Any]:
    from .. import repo as auth_repo

    row = auth_repo.disable_tenant_admin(tenant_slug)
    if not row:
        raise HTTPException(status_code=404, detail="Tenant not found")
    auth_repo.create_admin_audit_event(
        action="tenant_disable",
        admin_user_id=str(admin_user.get("id") or "") or None,
        tenant_slug=tenant_slug,
    )
    return _json({"tenant": row})


@router.get("/admin/users")
def admin_users_list(
    tenant_slug: str | None = None,
    onboarding_status: str | None = None,
    search: str | None = None,
    eligible_only: bool = False,
    paused_only: bool = False,
    offset: int = 0,
    limit: int = 200,
    admin_user: dict[str, Any] = Depends(require_admin_role("viewer")),
) -> dict[str, Any]:
    from .. import repo as auth_repo

    _ = admin_user
    tenant_id = _tenant_id_from_slug(tenant_slug)
    rows, total_count = _rows_and_count(
        auth_repo.list_users_admin(
        tenant_id=tenant_id,
        onboarding_status=onboarding_status,
        search=search,
        eligible_only=eligible_only,
        paused_only=paused_only,
        offset=offset,
        limit=limit,
        )
    )
    return _json({"users": rows, "count": int(total_count), "offset": int(offset), "limit": int(limit)})


@router.post("/admin/users/{user_id}/pause")
def admin_users_pause(
    user_id: str,
    pause_matches: bool,
    admin_user: dict[str, Any] = Depends(require_admin_role("operator")),
) -> dict[str, Any]:
    from .. import repo as auth_repo

    pref = auth_repo.update_user_pause_matches_admin(user_id, pause_matches=pause_matches)
    auth_repo.create_admin_audit_event(
        action="user_pause_matches",
        admin_user_id=str(admin_user.get("id") or "") or None,
        payload_json={"user_id": user_id, "pause_matches": pause_matches},
    )
    return _json({"preferences": pref})


@router.post("/admin/users/{user_id}/delete")
def admin_users_delete(
    user_id: str,
    admin_user: dict[str, Any] = Depends(require_admin_role("admin")),
) -> dict[str, Any]:
    from .. import repo as auth_repo

    auth_repo.anonymize_and_disable_user(user_id)
    auth_repo.create_admin_audit_event(
        action="user_delete",
        admin_user_id=str(admin_user.get("id") or "") or None,
        payload_json={"user_id": user_id},
    )
    return _json({"ok": True, "user_id": user_id})


@router.get("/admin/users/{user_id}")
def admin_user_detail(
    user_id: str,
    admin_user: dict[str, Any] = Depends(require_admin_role("viewer")),
) -> dict[str, Any]:
    from .. import repo as auth_repo

    _ = admin_user
    user = auth_repo.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    profile = auth_repo.get_user_public_profile(user_id)
    matches = auth_repo.list_match_history(user_id, limit=52)

    with SessionLocal() as db:
        sessions = db.execute(
            text(
                """
                SELECT id, survey_slug, survey_version, status, started_at, completed_at
                FROM survey_session
                WHERE user_id = CAST(:user_id AS uuid)
                ORDER BY started_at DESC
                LIMIT 20
                """
            ),
            {"user_id": user_id},
        ).mappings().all()
        latest_traits = db.execute(
            text(
                """
                SELECT survey_slug, survey_version, computed_at, traits
                FROM user_traits
                WHERE user_id = CAST(:user_id AS uuid)
                ORDER BY computed_at DESC
                LIMIT 1
                """
            ),
            {"user_id": user_id},
        ).mappings().first()
        latest_session_id = str(sessions[0]["id"]) if sessions else None
        answers: list[dict[str, Any]] = []
        if latest_session_id:
            answers = [
                dict(r)
                for r in db.execute(
                    text(
                        """
                        SELECT question_code, answer_value, answered_at
                        FROM survey_answer
                        WHERE session_id = CAST(:session_id AS uuid)
                        ORDER BY answered_at ASC
                        """
                    ),
                    {"session_id": latest_session_id},
                ).mappings().all()
            ]

    return _json(
        {
            "user": user,
            "profile": profile,
            "sessions": [dict(s) for s in sessions],
            "latest_session_answers": answers,
            "latest_traits": dict(latest_traits) if latest_traits else None,
            "match_history": matches,
        }
    )


@router.post("/admin/users/{user_id}/disable")
def admin_users_disable(
    user_id: str,
    admin_user: dict[str, Any] = Depends(require_admin_role("operator")),
) -> dict[str, Any]:
    from .. import repo as auth_repo

    row = auth_repo.disable_user_admin(user_id)
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    auth_repo.create_admin_audit_event(
        action="user_disable",
        admin_user_id=str(admin_user.get("id") or "") or None,
        payload_json={"user_id": user_id},
    )
    return _json({"user": row})


@router.post("/admin/users/{user_id}/password-reset")
def admin_users_password_reset(
    user_id: str,
    payload: dict[str, Any],
    admin_user: dict[str, Any] = Depends(require_admin_role("admin")),
) -> dict[str, Any]:
    from .. import repo as auth_repo

    new_password = str(payload.get("new_password") or "")
    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="new_password must be at least 8 characters")
    if not auth_repo.get_user_by_id(user_id):
        raise HTTPException(status_code=404, detail="User not found")
    auth_repo.update_user_password(user_id, hash_password(new_password))
    auth_repo.create_admin_audit_event(
        action="user_password_reset",
        admin_user_id=str(admin_user.get("id") or "") or None,
        payload_json={"user_id": user_id},
    )
    return _json({"ok": True, "user_id": user_id})


@router.get("/admin/sessions/{session_id}/dump")
def admin_session_dump(
    session_id: str,
    admin_user: dict[str, Any] = Depends(require_admin_role("viewer")),
) -> dict[str, Any]:
    from .. import main as m

    _ = admin_user
    return m.repo_dump_session(session_id)


@router.get("/admin/reports")
def admin_reports_list(
    tenant_slug: str | None = None,
    week_start: str | None = None,
    status: str | None = None,
    reason: str | None = None,
    reporter_user_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    offset: int = 0,
    limit: int = 200,
    admin_user: dict[str, Any] = Depends(require_admin_role("viewer")),
) -> dict[str, Any]:
    from .. import repo as auth_repo

    _ = admin_user
    tenant_id = _tenant_id_from_slug(tenant_slug)
    week_parsed = date.fromisoformat(week_start) if week_start else None
    rows, total_count = _rows_and_count(
        auth_repo.list_match_reports_admin(
        tenant_id=tenant_id,
        week_start_date=week_parsed,
        status=status,
        reason=reason,
        reporter_user_id=reporter_user_id,
        date_from=date_from,
        date_to=date_to,
        offset=offset,
        limit=limit,
        )
    )
    return _json({"reports": rows, "count": int(total_count), "offset": int(offset), "limit": int(limit)})


@router.post("/admin/reports/{report_id}/resolve")
def admin_reports_resolve(
    report_id: str,
    payload: dict[str, Any],
    admin_user: dict[str, Any] = Depends(require_admin_role("operator")),
) -> dict[str, Any]:
    from .. import repo as auth_repo

    row = auth_repo.resolve_match_report_admin(
        report_id=report_id,
        admin_user_id=str(admin_user.get("id") or ""),
        resolution_notes=str(payload.get("resolution_notes") or "").strip() or None,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Report not found")
    return _json({"report": row})


@router.post("/admin/matches/run-weekly")
def run_weekly_matching(
    tenant_slug: str | None = None,
    force: bool = False,
    admin_user: dict[str, Any] = Depends(require_admin_role("operator")),
) -> dict[str, Any]:
    from .. import main as m
    from .. import repo as auth_repo

    if force and not tenant_slug:
        raise HTTPException(status_code=400, detail="tenant_slug is required when force=true for tenant-scoped run")
    out = _run_weekly_matching_compat(m, now=datetime.now(timezone.utc), tenant_slug=tenant_slug, force=force)
    if force:
        auth_repo.create_admin_audit_event(
            action="force_rerun_weekly",
            admin_user_id=str(admin_user.get("id") or "") or None,
            tenant_slug=tenant_slug,
            week_start_date=out.get("week_start_date"),
            payload_json={"deleted_counts": out.get("deleted_counts")},
        )
        out["deleted_counts_by_table"] = out.get("deleted_counts", {})
    return _json(out)


@router.post("/admin/matches/run-weekly-all")
def run_weekly_matching_all_tenants(
    force: bool = True,
    admin_user: dict[str, Any] = Depends(require_admin_role("admin")),
) -> dict[str, Any]:
    from .. import main as m
    from .. import repo as auth_repo

    with SessionLocal() as db:
        tenant_rows = db.execute(m.text("SELECT slug FROM tenant ORDER BY created_at ASC")).mappings().all()

    results: list[dict[str, Any]] = []
    for row in tenant_rows:
        slug = str(row.get("slug") or "").strip()
        if not slug:
            continue
        one = _run_weekly_matching_compat(m, now=datetime.now(timezone.utc), tenant_slug=slug, force=force)
        if force:
            one["deleted_counts_by_table"] = one.get("deleted_counts", {})
            auth_repo.create_admin_audit_event(
                action="force_rerun_weekly",
                admin_user_id=str(admin_user.get("id") or "") or None,
                tenant_slug=slug,
                week_start_date=one.get("week_start_date"),
                payload_json={"deleted_counts": one.get("deleted_counts")},
            )
        results.append(one)

    return _json({"force": force, "tenants_processed": len(results), "results": results})


@router.get("/admin/metrics/summary")
def admin_metrics_summary(
    date_from: str,
    date_to: str,
    tenant_slug: str | None = None,
    admin_user: dict[str, Any] = Depends(require_admin_role("viewer")),
) -> dict[str, Any]:
    _ = admin_user
    try:
        d_from = date.fromisoformat(date_from)
        d_to = date.fromisoformat(date_to)
    except ValueError:
        raise HTTPException(status_code=400, detail="date_from/date_to must be YYYY-MM-DD")
    tenant_id = _tenant_id_from_slug(tenant_slug)
    with SessionLocal() as db:
        return _json(metrics_funnel_summary(db, date_from=d_from, date_to=d_to, tenant_id=tenant_id))


@router.get("/admin/metrics/funnel")
def admin_metrics_funnel(
    week_start: str,
    tenant_slug: str | None = None,
    admin_user: dict[str, Any] = Depends(require_admin_role("viewer")),
) -> dict[str, Any]:
    _ = admin_user
    try:
        week = date.fromisoformat(week_start)
    except ValueError:
        raise HTTPException(status_code=400, detail="week_start must be YYYY-MM-DD")
    tenant_id = _tenant_id_from_slug(tenant_slug)
    with SessionLocal() as db:
        return _json(metrics_weekly_funnel(db, week_start=week, tenant_id=tenant_id))


@router.get("/admin/metrics/weekly")
def admin_metrics_weekly(
    week_start: str,
    tenant_slug: str | None = None,
    admin_user: dict[str, Any] = Depends(require_admin_role("viewer")),
) -> dict[str, Any]:
    return admin_metrics_funnel(week_start=week_start, tenant_slug=tenant_slug, admin_user=admin_user)


@router.get("/admin/notifications/outbox-v2")
def admin_notifications_outbox_v2(
    status: str = "pending",
    notification_type: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    offset: int = 0,
    limit: int = 100,
    tenant_slug: str | None = None,
    admin_user: dict[str, Any] = Depends(require_admin_role("viewer")),
) -> dict[str, Any]:
    from .. import repo as auth_repo

    _ = admin_user
    tenant_id = _tenant_id_from_slug(tenant_slug)
    rows, total_count = _rows_and_count(
        auth_repo.list_notifications_outbox(
        status=status,
        tenant_id=tenant_id,
        notification_type=notification_type,
        date_from=date_from,
        date_to=date_to,
        offset=offset,
        limit=limit,
        )
    )
    return _json({"status": status, "rows": rows, "count": int(total_count), "offset": int(offset), "limit": int(limit)})


@router.get("/admin/diagnostics")
def admin_diagnostics(
    admin_user: dict[str, Any] = Depends(require_admin_role("viewer")),
) -> dict[str, Any]:
    from .. import repo as auth_repo

    _ = admin_user
    now = datetime.now(timezone.utc)
    week_start = get_week_start_date(now, MATCH_TIMEZONE)

    tenants = auth_repo.list_tenants_admin(include_disabled=False)
    by_tenant: list[dict[str, Any]] = []
    with SessionLocal() as db:
        for t in tenants:
            tenant_id = str(t.get("id"))
            users_total = db.execute(
                text("SELECT COUNT(1) FROM user_account WHERE disabled_at IS NULL AND tenant_id = CAST(:tenant_id AS uuid)"),
                {"tenant_id": tenant_id},
            ).scalar() or 0
            assignments = db.execute(
                text("SELECT COUNT(1) FROM weekly_match_assignment WHERE tenant_id = CAST(:tenant_id AS uuid) AND week_start_date = :week_start"),
                {"tenant_id": tenant_id, "week_start": week_start},
            ).scalar() or 0
            eligible_users = db.execute(
                text(
                    """
                    SELECT COUNT(DISTINCT ua.id)
                    FROM user_account ua
                    JOIN user_traits ut ON CAST(ut.user_id AS text) = CAST(ua.id AS text)
                    LEFT JOIN user_preferences pref ON pref.user_id = ua.id
                    WHERE ua.disabled_at IS NULL
                      AND ua.tenant_id = CAST(:tenant_id AS uuid)
                      AND COALESCE(pref.pause_matches, FALSE) = FALSE
                    """
                ),
                {"tenant_id": tenant_id},
            ).scalar() or 0
            accepts = db.execute(
                text(
                    """
                    SELECT COUNT(1)
                    FROM match_event
                    WHERE tenant_id = CAST(:tenant_id AS uuid)
                      AND week_start_date = :week_start
                      AND event_type = 'accept'
                    """
                ),
                {"tenant_id": tenant_id, "week_start": week_start},
            ).scalar() or 0
            feedback_count = db.execute(
                text(
                    """
                    SELECT COUNT(1)
                    FROM match_feedback
                    WHERE tenant_id = CAST(:tenant_id AS uuid)
                      AND week_start_date = :week_start
                    """
                ),
                {"tenant_id": tenant_id, "week_start": week_start},
            ).scalar() or 0
            notifications_pending = db.execute(
                text("SELECT COUNT(1) FROM notifications_outbox WHERE tenant_id = CAST(:tenant_id AS uuid) AND status = 'pending'"),
                {"tenant_id": tenant_id},
            ).scalar() or 0
            open_reports = db.execute(
                text("SELECT COUNT(1) FROM match_report WHERE tenant_id = CAST(:tenant_id AS uuid) AND status = 'open'"),
                {"tenant_id": tenant_id},
            ).scalar() or 0
            by_tenant.append(
                {
                    "tenant_slug": t.get("slug"),
                    "tenant_name": t.get("name"),
                    "users_total": int(users_total),
                    "eligible_users": int(eligible_users),
                    "assignments_current_week": int(assignments),
                    "unique_pairs_current_week": int(assignments // 2),
                    "accepts_current_week": int(accepts),
                    "feedback_count_current_week": int(feedback_count),
                    "notifications_pending": int(notifications_pending),
                    "open_safety_reports": int(open_reports),
                }
            )

    active = survey_admin_repo.get_active_definition(SURVEY_SLUG)
    latest_draft = survey_admin_repo.get_latest_draft(SURVEY_SLUG)
    totals = {
        "users_total": sum(int(r.get("users_total") or 0) for r in by_tenant),
        "eligible_users": sum(int(r.get("eligible_users") or 0) for r in by_tenant),
        "assignments_current_week": sum(int(r.get("assignments_current_week") or 0) for r in by_tenant),
        "unique_pairs_current_week": sum(int(r.get("unique_pairs_current_week") or 0) for r in by_tenant),
        "accepts_current_week": sum(int(r.get("accepts_current_week") or 0) for r in by_tenant),
        "feedback_count_current_week": sum(int(r.get("feedback_count_current_week") or 0) for r in by_tenant),
        "notifications_pending": sum(int(r.get("notifications_pending") or 0) for r in by_tenant),
        "open_safety_reports": sum(int(r.get("open_safety_reports") or 0) for r in by_tenant),
    }

    return _json(
        {
            "week_start_date": str(week_start),
            "tenants_count": len(tenants),
            "overall": totals,
            "survey": {
                "active_exists": bool(active),
                "latest_draft_exists": bool(latest_draft),
                "active_version": active.get("version") if active else None,
                "latest_draft_version": latest_draft.get("version") if latest_draft else None,
            },
            "by_tenant": by_tenant,
        }
    )


@router.get("/admin/diagnostics/tenant-coverage")
def admin_tenant_coverage(
    admin_user: dict[str, Any] = Depends(require_admin_role("viewer")),
) -> dict[str, Any]:
    from .. import repo as auth_repo

    _ = admin_user
    now = datetime.now(timezone.utc)
    week_start = get_week_start_date(now, MATCH_TIMEZONE)
    tenants = auth_repo.list_tenants_admin(include_disabled=False)
    by_tenant: list[dict[str, Any]] = []

    with SessionLocal() as db:
      for t in tenants:
          tenant_id = str(t.get("id"))
          users_total = db.execute(
              text("SELECT COUNT(1) FROM user_account WHERE disabled_at IS NULL AND tenant_id = CAST(:tenant_id AS uuid)"),
              {"tenant_id": tenant_id},
          ).scalar() or 0
          users_with_completed_survey = db.execute(
              text(
                  """
                  SELECT COUNT(DISTINCT ua.id)
                  FROM user_account ua
                  JOIN survey_session ss ON CAST(ss.user_id AS text) = CAST(ua.id AS text) AND ss.completed_at IS NOT NULL
                  WHERE ua.disabled_at IS NULL
                    AND ua.tenant_id = CAST(:tenant_id AS uuid)
                  """
              ),
              {"tenant_id": tenant_id},
          ).scalar() or 0
          users_with_traits = db.execute(
              text(
                  """
                  SELECT COUNT(DISTINCT ua.id)
                  FROM user_account ua
                  JOIN user_traits ut ON CAST(ut.user_id AS text) = CAST(ua.id AS text)
                  WHERE ua.disabled_at IS NULL
                    AND ua.tenant_id = CAST(:tenant_id AS uuid)
                  """
              ),
              {"tenant_id": tenant_id},
          ).scalar() or 0
          eligibility = fetch_eligibility_debug_counts(db, SURVEY_SLUG, SURVEY_VERSION, tenant_id=tenant_id)
          weekly_assignment_rows = db.execute(
              text("SELECT COUNT(1) FROM weekly_match_assignment WHERE tenant_id = CAST(:tenant_id AS uuid) AND week_start_date = :week_start"),
              {"tenant_id": tenant_id, "week_start": week_start},
          ).scalar() or 0
          outbox_pending = db.execute(
              text("SELECT COUNT(1) FROM notifications_outbox WHERE tenant_id = CAST(:tenant_id AS uuid) AND status = 'pending'"),
              {"tenant_id": tenant_id},
          ).scalar() or 0
          open_reports = db.execute(
              text("SELECT COUNT(1) FROM match_report WHERE tenant_id = CAST(:tenant_id AS uuid) AND status = 'open'"),
              {"tenant_id": tenant_id},
          ).scalar() or 0
          by_tenant.append(
              {
                  "tenant_slug": t.get("slug"),
                  "tenant_name": t.get("name"),
                  "users_total": int(users_total),
                  "users_with_completed_survey": int(users_with_completed_survey),
                  "users_with_traits": int(users_with_traits),
                  "eligibility_debug": eligibility,
                  "weekly_assignment_rows": int(weekly_assignment_rows),
                  "outbox_pending": int(outbox_pending),
                  "open_reports": int(open_reports),
              }
          )
    return _json({"week_start_date": str(week_start), "by_tenant": by_tenant})


@router.post("/admin/notifications/process")
def admin_notifications_process(
    limit: int = 100,
    tenant_slug: str | None = None,
    admin_user: dict[str, Any] = Depends(require_admin_role("operator")),
) -> dict[str, Any]:
    from .. import repo as auth_repo

    _ = admin_user
    tenant_id = _tenant_id_from_slug(tenant_slug)
    return _json(auth_repo.process_notifications_outbox(limit=limit, tenant_id=tenant_id))


@router.post("/admin/notifications/retry/{notification_id}")
def admin_notifications_retry(
    notification_id: str,
    admin_user: dict[str, Any] = Depends(require_admin_role("operator")),
) -> dict[str, Any]:
    from .. import repo as auth_repo

    _ = admin_user
    row = auth_repo.retry_notification(notification_id)
    if not row:
        raise HTTPException(status_code=404, detail="Notification not found")
    return _json({"notification": row})


@router.get("/admin/calibration/current-week")
def admin_calibration_current_week(admin_user: dict[str, Any] = Depends(require_admin_role("viewer"))) -> dict[str, Any]:
    _ = admin_user
    now = datetime.now(timezone.utc)
    week_start = get_week_start_date(now, MATCH_TIMEZONE)
    with SessionLocal() as db:
        return _json(compute_calibration_report(
            db,
            survey_slug=SURVEY_SLUG,
            survey_version=SURVEY_VERSION,
            week_start_date=week_start,
            cfg=DEFAULT_MATCHING_CONFIG,
            lookback_weeks=LOOKBACK_WEEKS,
        ))


@router.get("/admin/matches/week/{week_start_date}")
def get_weekly_summary(
    week_start_date: str,
    tenant_slug: str | None = None,
    admin_user: dict[str, Any] = Depends(require_admin_role("viewer")),
) -> dict[str, Any]:
    from .. import main as m

    _ = admin_user
    try:
        parsed = date.fromisoformat(week_start_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="week_start_date must be YYYY-MM-DD")
    tenant_id = _tenant_id_from_slug(tenant_slug)
    return m.repo_week_summary(parsed, tenant_id=tenant_id)


@router.post("/admin/survey/initialize-from-code")
def admin_survey_initialize_from_code(
    payload: dict[str, Any] | None = None,
    admin_user: dict[str, Any] = Depends(require_admin_role("operator")),
) -> dict[str, Any]:
    from .. import repo as auth_repo
    from ..survey_loader import get_file_survey_definition

    trace_id = str(uuid.uuid4())
    try:
        body = payload or {}
        force = bool(body.get("force", False))
        code_definition = get_file_survey_definition()
        if not isinstance(code_definition, dict):
            raise HTTPException(status_code=500, detail=_detail(message="Code survey definition is invalid", trace_id=trace_id))

        errors = validate_survey_definition(code_definition)
        if errors:
            raise HTTPException(status_code=400, detail=_detail(message="Code survey validation failed", errors=errors, trace_id=trace_id))

        out = survey_admin_repo.initialize_active_from_code(
            slug=SURVEY_SLUG,
            definition_json=code_definition,
            actor_user_id=str(admin_user.get("id") or "") or None,
            force=force,
        )
        active = out.get("active") if isinstance(out, dict) else None
        initialized = bool((out or {}).get("initialized"))
        auth_repo.create_admin_audit_event(
            action="survey_initialize_from_code",
            admin_user_id=str(admin_user.get("id") or "") or None,
            payload_json={
                "survey_slug": SURVEY_SLUG,
                "force": force,
                "initialized": initialized,
                "active_version": (active or {}).get("version"),
            },
        )
        return {
            "initialized": initialized,
            "active": active,
            "latest_draft": survey_admin_repo.get_latest_draft(SURVEY_SLUG),
            "published_versions": [
                {
                    "id": p.get("id"),
                    "version": p.get("version"),
                    "is_active": p.get("is_active", False),
                    "created_at": p.get("created_at"),
                }
                for p in survey_admin_repo.list_published_definitions(SURVEY_SLUG)
            ],
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=_detail(message="Failed to initialize survey from code", hint=str(exc), trace_id=trace_id))


@router.post("/admin/seed")
def admin_seed(
    payload: dict[str, Any],
    admin_user: dict[str, Any] = Depends(require_admin_role("operator")),
) -> dict[str, Any]:
    from .. import main as m

    _ = admin_user
    n_users = int(payload.get("n_users", 100))
    n_users_per_tenant = int(payload.get("n_users_per_tenant", n_users))
    reset = bool(payload.get("reset", False))
    clustered = bool(payload.get("clustered", False))
    tenant_slug = str(payload.get("tenant_slug") or "").strip().lower() or None
    all_tenants = bool(payload.get("all_tenants", False))
    backfill_existing = bool(payload.get("backfill_existing_users", False))
    force_reseed = bool(payload.get("force_reseed", False))
    include_qa_login = bool(payload.get("include_qa_login", True))
    qa_password = str(payload.get("qa_password") or "community123")

    with SessionLocal() as db:
        if backfill_existing:
            summary = backfill_existing_users_survey_data(
                db=db,
                survey_slug=SURVEY_SLUG,
                survey_version=SURVEY_VERSION,
                tenant_slug=tenant_slug,
                all_tenants=all_tenants,
                seed=int(payload.get("seed", 42)),
                clustered=clustered,
                force_reseed=force_reseed,
            )
        elif all_tenants:
            summary = seed_all_tenants_dummy_data(
                db=db,
                survey_def=m.get_survey_definition(),
                survey_slug=SURVEY_SLUG,
                survey_version=SURVEY_VERSION,
                n_users_per_tenant=n_users_per_tenant,
                reset=reset,
                seed=int(payload.get("seed", 42)),
                clustered=clustered,
                include_qa_login=include_qa_login,
                qa_password=qa_password,
            )
        else:
            summary = seed_dummy_data(
                db=db,
                survey_def=m.get_survey_definition(),
                survey_slug=SURVEY_SLUG,
                survey_version=SURVEY_VERSION,
                n_users=n_users,
                reset=reset,
                seed=int(payload.get("seed", 42)),
                clustered=clustered,
                tenant_slug=tenant_slug,
                include_qa_login=include_qa_login,
                qa_password=qa_password,
            )

    if include_qa_login is not True:
        if isinstance(summary, dict):
            summary = {**summary, "qa_credentials": []}
    return summary


@router.get("/admin/survey/active")
def admin_survey_active(admin_user: dict[str, Any] = Depends(require_admin_role("viewer"))) -> dict[str, Any]:
    _ = admin_user
    active = survey_admin_repo.get_active_definition(SURVEY_SLUG)
    latest_draft = survey_admin_repo.get_latest_draft(SURVEY_SLUG)
    published = survey_admin_repo.list_published_definitions(SURVEY_SLUG)
    return {
        "active": active,
        "latest_draft": latest_draft,
        "published_versions": [
            {
                "id": p.get("id"),
                "version": p.get("version"),
                "is_active": p.get("is_active", False),
                "created_at": p.get("created_at"),
            }
            for p in published
        ],
    }


@router.get("/admin/survey/preview")
def admin_survey_preview(
    tenant_slug: str | None = None,
    admin_user: dict[str, Any] = Depends(require_admin_role("viewer")),
) -> dict[str, Any]:
    from ..survey_loader import filter_survey_for_tenant, get_runtime_code_definition

    _ = admin_user
    trace_id = str(uuid.uuid4())
    try:
        active = survey_admin_repo.get_active_definition(SURVEY_SLUG)
        active_db_survey = (
            filter_survey_for_tenant(active["definition_json"], tenant_slug)
            if active and isinstance(active.get("definition_json"), dict)
            else None
        )
        runtime_code_survey = get_runtime_code_definition(tenant_slug=tenant_slug)
        effective_source = "active_db" if active_db_survey is not None else "runtime_code"
        effective_survey = active_db_survey if active_db_survey is not None else runtime_code_survey
        return {
            "survey": effective_survey,
            "source": effective_source,
            "active_db_survey": active_db_survey,
            "runtime_code_survey": runtime_code_survey,
            "tenant_slug": tenant_slug,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=_detail(message="Failed to load survey preview", hint=str(exc), trace_id=trace_id))


@router.post("/admin/survey/draft/from-active")
def admin_survey_create_draft_from_active(
    admin_user: dict[str, Any] = Depends(require_admin_role("operator")),
) -> dict[str, Any]:
    trace_id = str(uuid.uuid4())
    try:
        created = survey_admin_repo.create_draft_from_active(SURVEY_SLUG, admin_user.get("id"))
        if not created:
            raise HTTPException(status_code=404, detail=_detail(message="No active survey definition found", hint="Initialize from code or publish an active definition first.", trace_id=trace_id))
        return {"draft": created}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=_detail(message="Failed to create draft from active", hint=str(exc), trace_id=trace_id))


@router.get("/admin/survey/draft/latest")
def admin_survey_latest_draft(admin_user: dict[str, Any] = Depends(require_admin_role("viewer"))) -> dict[str, Any]:
    _ = admin_user
    draft = survey_admin_repo.get_latest_draft(SURVEY_SLUG)
    if not draft:
        raise HTTPException(status_code=404, detail=_detail(message="No draft survey definition found", hint="Create draft from active first."))
    return {"draft": draft}


@router.put("/admin/survey/draft/latest")
def admin_survey_update_latest_draft(
    payload: Any = Body(...),
    admin_user: dict[str, Any] = Depends(require_admin_role("operator")),
) -> dict[str, Any]:
    trace_id = str(uuid.uuid4())
    try:
        try:
            parsed = SurveyDraftUpdate.model_validate(payload)
            definition_json = parsed.definition_json
        except ValidationError:
            raise HTTPException(
                status_code=400,
                detail=_detail(
                    message="Invalid survey schema",
                    errors=[{"path": "definition_json", "message": "definition_json is required"}],
                    hint="Send {\"definition_json\": {...}}",
                    trace_id=trace_id,
                ),
            )

        if isinstance(definition_json, str):
            raise HTTPException(
                status_code=400,
                detail=_detail(
                    message="Invalid survey schema",
                    errors=[{"path": "definition_json", "message": "definition_json must be an object"}],
                    hint="Send {\"definition_json\": {...}}",
                    trace_id=trace_id,
                ),
            )
        if not isinstance(definition_json, dict):
            raise HTTPException(
                status_code=400,
                detail=_detail(
                    message="Invalid survey schema",
                    errors=[{"path": "definition_json", "message": "definition_json must be an object"}],
                    hint="Send {\"definition_json\": {...}}",
                    trace_id=trace_id,
                ),
            )
        errors = validate_survey_definition(definition_json)
        if errors:
            raise HTTPException(status_code=400, detail=_detail(message="Invalid survey schema", errors=errors, trace_id=trace_id))
        updated = survey_admin_repo.update_latest_draft(SURVEY_SLUG, definition_json, admin_user.get("id"))
        if not updated:
            raise HTTPException(status_code=404, detail=_detail(message="No draft, create draft first", hint="Call /admin/survey/draft/from-active", trace_id=trace_id))
        return {"draft": updated}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=_detail(message="Failed to update draft", hint=str(exc), trace_id=trace_id))


@router.post("/admin/survey/draft/latest/validate")
def admin_survey_validate_latest_draft(
    admin_user: dict[str, Any] = Depends(require_admin_role("viewer")),
) -> dict[str, Any]:
    _ = admin_user
    trace_id = str(uuid.uuid4())
    try:
        draft = survey_admin_repo.get_latest_draft(SURVEY_SLUG)
        if not draft:
            raise HTTPException(status_code=409, detail=_detail(message="No draft survey definition found", hint="Create draft from active first.", trace_id=trace_id))

        definition = draft.get("definition_json")
        if not isinstance(definition, dict):
            raise HTTPException(status_code=400, detail=_detail(message="Draft definition_json must be an object", errors=[], trace_id=trace_id))
        errors = validate_survey_definition(definition)
        if errors:
            raise HTTPException(status_code=400, detail=_detail(message="Validation failed", errors=errors, trace_id=trace_id))
        return {"valid": True, "errors": []}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=_detail(message="Failed to validate draft", hint=str(exc), trace_id=trace_id))


@router.post("/admin/survey/draft/latest/publish")
def admin_survey_publish_latest_draft(
    admin_user: dict[str, Any] = Depends(require_admin_role("operator")),
) -> dict[str, Any]:
    trace_id = str(uuid.uuid4())
    try:
        draft = survey_admin_repo.get_latest_draft(SURVEY_SLUG)
        if not draft:
            raise HTTPException(status_code=409, detail=_detail(message="No draft survey definition found", hint="Create draft from active first.", trace_id=trace_id))

        definition = draft.get("definition_json")
        if not isinstance(definition, dict):
            raise HTTPException(status_code=400, detail=_detail(message="Draft definition_json must be an object", errors=[], trace_id=trace_id))
        errors = validate_survey_definition(definition)
        if errors:
            raise HTTPException(status_code=400, detail=_detail(message="Validation failed", errors=errors, trace_id=trace_id))

        published = survey_admin_repo.publish_latest_draft(SURVEY_SLUG, admin_user.get("id"))
        if not published:
            raise HTTPException(status_code=409, detail=_detail(message="No draft survey definition found", hint="Create draft from active first.", trace_id=trace_id))
        return {"active": published}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=_detail(message="Failed to publish draft", hint=str(exc), trace_id=trace_id))


@router.post("/admin/survey/rollback")
def admin_survey_rollback(
    payload: dict[str, Any],
    admin_user: dict[str, Any] = Depends(require_admin_role("operator")),
) -> dict[str, Any]:
    trace_id = str(uuid.uuid4())
    try:
        version = payload.get("version") if isinstance(payload, dict) else None
        if not isinstance(version, int):
            raise HTTPException(status_code=400, detail=_detail(message="version must be an integer", hint="Send {\"version\": <int>}", trace_id=trace_id))
        active = survey_admin_repo.rollback_to_published_version(SURVEY_SLUG, version, admin_user.get("id"))
        if not active:
            raise HTTPException(status_code=404, detail=_detail(message=f"Published version {version} not found", trace_id=trace_id))
        return {"active": active}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=_detail(message="Failed to rollback survey", hint=str(exc), trace_id=trace_id))


@router.get("/admin/diagnostics/survey-version")
def admin_diagnostics_survey_version(
    tenant_slug: str | None = None,
    admin_user: dict[str, Any] = Depends(require_admin_role("viewer")),
) -> dict[str, Any]:
    """Extended diagnostics showing survey version drift per user/tenant."""
    from .. import repo as auth_repo

    _ = admin_user
    tenant_id = _tenant_id_from_slug(tenant_slug) if tenant_slug else None
    
    # Get current runtime survey fingerprint
    runtime = get_active_survey_runtime(tenant_slug)
    current_hash = str(runtime.get("hash") or "")
    current_version = int(runtime.get("version") or SURVEY_VERSION)
    current_slug = str(runtime.get("slug") or SURVEY_SLUG)
    
    tenants = auth_repo.list_tenants_admin(include_disabled=False)
    by_tenant: list[dict[str, Any]] = []
    
    with SessionLocal() as db:
        for t in tenants:
            tid = str(t.get("id"))
            if tenant_id and tid != tenant_id:
                continue
            
            # Get all users for this tenant
            users_total = db.execute(
                text("SELECT COUNT(1) FROM user_account WHERE disabled_at IS NULL AND tenant_id = CAST(:tenant_id AS uuid)"),
                {"tenant_id": tid},
            ).scalar() or 0
            
            # Users with any survey answers
            users_with_answers = db.execute(
                text(
                    """
                    SELECT COUNT(DISTINCT ua.id)
                    FROM user_account ua
                    JOIN survey_session ss ON CAST(ss.user_id AS text) = CAST(ua.id AS text)
                    WHERE ua.disabled_at IS NULL AND ua.tenant_id = CAST(:tenant_id AS uuid)
                    """
                ),
                {"tenant_id": tid},
            ).scalar() or 0
            
            # Users with survey_hash != current hash
            users_hash_mismatch = db.execute(
                text(
                    """
                    SELECT COUNT(DISTINCT ua.id)
                    FROM user_account ua
                    JOIN survey_session ss ON CAST(ss.user_id AS text) = CAST(ua.id AS text)
                    WHERE ua.disabled_at IS NULL 
                      AND ua.tenant_id = CAST(:tenant_id AS uuid)
                      AND ss.survey_hash IS NOT NULL
                      AND ss.survey_hash != :current_hash
                    """
                ),
                {"tenant_id": tid, "current_hash": current_hash},
            ).scalar() or 0
            
            # Users missing required questions for current survey
            users_missing_required = db.execute(
                text(
                    """
                    SELECT COUNT(DISTINCT ua.id)
                    FROM user_account ua
                    JOIN survey_reconciliation_state srs ON CAST(srs.user_id AS text) = CAST(ua.id AS text)
                    WHERE ua.disabled_at IS NULL 
                      AND ua.tenant_id = CAST(:tenant_id AS uuid)
                      AND srs.current_survey_hash = :current_hash
                      AND srs.needs_retake = TRUE
                    """
                ),
                {"tenant_id": tid, "current_hash": current_hash},
            ).scalar() or 0
            
            # Users missing OCEAN/insights
            users_missing_traits = db.execute(
                text(
                    """
                    SELECT COUNT(DISTINCT ua.id)
                    FROM user_account ua
                    LEFT JOIN user_traits ut ON CAST(ut.user_id AS text) = CAST(ua.id AS text)
                    WHERE ua.disabled_at IS NULL 
                      AND ua.tenant_id = CAST(:tenant_id AS uuid)
                      AND (ut.id IS NULL OR ut.ocean_scores IS NULL OR ut.insights_json IS NULL)
                    """
                ),
                {"tenant_id": tid},
            ).scalar() or 0
            
            # Eligible users for matching
            eligible_users = db.execute(
                text(
                    """
                    SELECT COUNT(DISTINCT ua.id)
                    FROM user_account ua
                    JOIN user_traits ut ON CAST(ut.user_id AS text) = CAST(ua.id AS text)
                    LEFT JOIN user_preferences pref ON pref.user_id = ua.id
                    WHERE ua.disabled_at IS NULL
                      AND ua.tenant_id = CAST(:tenant_id AS uuid)
                      AND COALESCE(pref.pause_matches, FALSE) = FALSE
                    """
                ),
                {"tenant_id": tid},
            ).scalar() or 0
            
            by_tenant.append({
                "tenant_slug": t.get("slug"),
                "tenant_name": t.get("name"),
                "users_total": int(users_total),
                "users_with_any_survey_answers": int(users_with_answers),
                "users_survey_hash_mismatch": int(users_hash_mismatch),
                "users_missing_required_questions": int(users_missing_required),
                "users_missing_ocean_insights": int(users_missing_traits),
                "eligible_users_for_matching": int(eligible_users),
            })
    
    return _json({
        "current_survey": {
            "slug": current_slug,
            "version": current_version,
            "hash": current_hash,
        },
        "tenants": by_tenant,
    })


@router.get("/admin/diagnostics/survey-version/users")
def admin_diagnostics_survey_version_users(
    tenant_slug: str | None = None,
    limit: int = 50,
    admin_user: dict[str, Any] = Depends(require_admin_role("viewer")),
) -> dict[str, Any]:
    """Sample users showing version mismatch details."""
    from .. import repo as auth_repo

    _ = admin_user
    tenant_id = _tenant_id_from_slug(tenant_slug) if tenant_slug else None
    
    runtime = get_active_survey_runtime(tenant_slug)
    current_hash = str(runtime.get("hash") or "")
    current_slug = str(runtime.get("slug") or SURVEY_SLUG)
    
    with SessionLocal() as db:
        # Get users with hash mismatch
        rows = db.execute(
            text(
                """
                SELECT 
                    ua.id as user_id,
                    t.slug as tenant_slug,
                    ss.survey_hash as answered_hash,
                    ss.survey_version as answered_version,
                    srs.needs_retake as needs_retake,
                    srs.missing_question_ids as missing_question_ids,
                    ut.ocean_scores IS NOT NULL as has_ocean,
                    ut.insights_json IS NOT NULL as has_insights
                FROM user_account ua
                JOIN survey_session ss ON CAST(ss.user_id AS text) = CAST(ua.id AS text)
                LEFT JOIN tenant t ON t.id = ua.tenant_id
                LEFT JOIN survey_reconciliation_state srs ON CAST(srs.user_id AS text) = CAST(ua.id AS text) 
                    AND srs.survey_slug = :current_slug
                LEFT JOIN user_traits ut ON CAST(ut.user_id AS text) = CAST(ua.id AS text)
                WHERE ua.disabled_at IS NULL
                  AND (:tenant_id IS NULL OR ua.tenant_id = CAST(:tenant_id AS uuid))
                  AND ss.survey_hash IS NOT NULL
                  AND ss.survey_hash != :current_hash
                ORDER BY ss.completed_at DESC
                LIMIT :limit
                """
            ),
            {"tenant_id": tenant_id or "", "current_hash": current_hash, "current_slug": current_slug, "limit": limit},
        ).mappings().all()
        
        user_samples = []
        for r in rows:
            user_samples.append({
                "user_id": str(r.get("user_id")),
                "tenant_slug": str(r.get("tenant_slug") or "cbs"),
                "answered_survey_hash": str(r.get("answered_hash") or ""),
                "answered_survey_version": r.get("answered_version"),
                "needs_retake": bool(r.get("needs_retake")),
                "missing_question_ids": r.get("missing_question_ids") if isinstance(r.get("missing_question_ids"), list) else [],
                "has_ocean": bool(r.get("has_ocean")),
                "has_insights": bool(r.get("has_insights")),
                "current_survey_hash": current_hash,
            })
    
    return _json({
        "current_survey_hash": current_hash,
        "users": user_samples,
    })


@router.post("/admin/survey/reconcile-all")
def admin_survey_reconcile_all(
    tenant_slug: str | None = None,
    admin_user: dict[str, Any] = Depends(require_admin_role("admin")),
) -> dict[str, Any]:
    """Reconcile all users to current survey version and recompute traits."""
    _ = admin_user
    trace_id = str(uuid.uuid4())
    
    try:
        with SessionLocal() as db:
            result = reconcile_all_users(db, tenant_slug=tenant_slug)
        return _json({
            "success": True,
            "trace_id": trace_id,
            **result,
        })
    except Exception as exc:
        raise HTTPException(status_code=500, detail=_detail(
            message="Failed to reconcile all users",
            hint=str(exc),
            trace_id=trace_id,
        ))


@router.get("/admin/metrics/match-coverage")
def admin_metrics_match_coverage(
    tenant_slug: str | None = None,
    week_start: str | None = None,
    admin_user: dict[str, Any] = Depends(require_admin_role("viewer")),
) -> dict[str, Any]:
    """Get match coverage metrics per tenant - pairs generated vs eligible users."""
    from .. import repo as auth_repo

    _ = admin_user
    
    # Parse week_start or use current week
    if week_start:
        try:
            parsed_week = date.fromisoformat(week_start)
        except ValueError:
            raise HTTPException(status_code=400, detail="week_start must be YYYY-MM-DD")
    else:
        now = datetime.now(timezone.utc)
        parsed_week = get_week_start_date(now, MATCH_TIMEZONE)
    
    tenants = auth_repo.list_tenants_admin(include_disabled=False)
    by_tenant: list[dict[str, Any]] = []
    
    with SessionLocal() as db:
        for t in tenants:
            tid = str(t.get("id"))
            
            # Get eligible users count
            eligible_users = db.execute(
                text(
                    """
                    SELECT COUNT(DISTINCT ua.id)
                    FROM user_account ua
                    JOIN user_traits ut ON CAST(ut.user_id AS text) = CAST(ua.id AS text)
                    LEFT JOIN user_preferences pref ON pref.user_id = ua.id
                    WHERE ua.disabled_at IS NULL
                      AND ua.tenant_id = CAST(:tenant_id AS uuid)
                      AND COALESCE(pref.pause_matches, FALSE) = FALSE
                    """
                ),
                {"tenant_id": tid},
            ).scalar() or 0
            
            # Get unique pairs (assignments / 2)
            assignment_rows = db.execute(
                text(
                    """
                    SELECT COUNT(1)
                    FROM weekly_match_assignment
                    WHERE tenant_id = CAST(:tenant_id AS uuid)
                      AND week_start_date = :week_start
                    """
                ),
                {"tenant_id": tid, "week_start": parsed_week},
            ).scalar() or 0
            
            pairs_generated = assignment_rows // 2
            unmatched_eligible = eligible_users - (pairs_generated * 2)
            
            # Check if we meet the 10 pairs target or if it's explained
            min_pairs_target = 10
            max_possible_pairs = eligible_users // 2 if eligible_users >= 2 else 0
            
            meets_target = pairs_generated >= min_pairs_target
            is_maximized = eligible_users < 20 and pairs_generated >= max_possible_pairs
            
            explanation = None
            if not meets_target and not is_maximized:
                if eligible_users < 20:
                    explanation = f"Too few eligible users ({eligible_users}). Need at least 20 for reliable matching."
                else:
                    explanation = f"Algorithm constraints or data quality issues. Eligible users: {eligible_users}, Pairs: {pairs_generated}"
            
            by_tenant.append({
                "tenant_slug": t.get("slug"),
                "tenant_name": t.get("name"),
                "week_start_date": str(parsed_week),
                "eligible_users": int(eligible_users),
                "assignment_rows": int(assignment_rows),
                "pairs_generated": int(pairs_generated),
                "unmatched_eligible_users": int(max(0, unmatched_eligible)),
                "max_possible_pairs": int(max_possible_pairs),
                "meets_10_pairs_target": meets_target,
                "is_maximized_for_low_volume": is_maximized,
                "explanation": explanation,
            })
    
    return _json({
        "week_start_date": str(parsed_week),
        "tenants": by_tenant,
    })


@router.post("/admin/survey/reconcile-and-verify")
def admin_survey_reconcile_and_verify(
    tenant_slug: str | None = None,
    run_matching: bool = True,
    admin_user: dict[str, Any] = Depends(require_admin_role("admin")),
) -> dict[str, Any]:
    """Run reconciliation for all users, then verify match coverage >= 10 pairs."""
    from .. import main as m

    _ = admin_user
    trace_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    week_start = get_week_start_date(now, MATCH_TIMEZONE)
    
    try:
        # Step 1: Reconcile all users
        reconcile_result = reconcile_all_users(tenant_slug=tenant_slug)
        
        # Step 2: Run matching if requested
        matching_result = None
        if run_matching:
            if tenant_slug:
                matching_result = _run_weekly_matching_compat(m, now=now, tenant_slug=tenant_slug, force=True)
            else:
                # Run for all tenants
                matching_result = {"tenants_processed": 0, "results": []}
                tenants = m.text("SELECT slug FROM tenant ORDER BY created_at ASC")
                with SessionLocal() as db:
                    tenant_rows = db.execute(tenants).mappings().all()
                for row in tenant_rows:
                    slug = str(row.get("slug") or "").strip()
                    if slug:
                        one = _run_weekly_matching_compat(m, now=now, tenant_slug=slug, force=True)
                        matching_result["results"].append(one)
                        matching_result["tenants_processed"] += 1
        
        # Step 3: Check match coverage
        coverage_result = admin_metrics_match_coverage(
            tenant_slug=tenant_slug,
            week_start=str(week_start),
            admin_user=admin_user,
        )
        
        # Determine overall success
        tenants_results = coverage_result.get("tenants", [])
        all_tenants_meet_target = all(
            t.get("meets_10_pairs_target") or t.get("is_maximized_for_low_volume", False)
            for t in tenants_results
        )
        
        return _json({
            "success": all_tenants_meet_target,
            "trace_id": trace_id,
            "reconciliation": reconcile_result,
            "matching": matching_result,
            "coverage_verification": coverage_result,
            "verification_passed": all_tenants_meet_target,
            "week_start_date": str(week_start),
        })
        
    except Exception as exc:
        raise HTTPException(status_code=500, detail=_detail(
            message="Failed to reconcile and verify",
            hint=str(exc),
            trace_id=trace_id,
        ))
