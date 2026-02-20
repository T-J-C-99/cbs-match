from datetime import datetime, timezone
from typing import Any
import uuid

from fastapi import APIRouter, Depends, HTTPException

from ..auth.deps import require_verified_user

router = APIRouter()
scaffold_router = APIRouter()


def _resolve_user_id_from_identifier_compat(m, *, blocked_identifier: str, current_user_id: str, tenant_id: str | None):
    try:
        return m.auth_repo.resolve_user_id_from_identifier(
            blocked_identifier,
            exclude_user_id=current_user_id,
            tenant_id=tenant_id,
        )
    except TypeError:
        return m.auth_repo.resolve_user_id_from_identifier(
            blocked_identifier,
            exclude_user_id=current_user_id,
        )


def _create_user_block_compat(m, *, current_user_id: str, blocked_user_id: str, tenant_id: str | None):
    try:
        return m.auth_repo.create_user_block(current_user_id, blocked_user_id, tenant_id=tenant_id)
    except TypeError:
        return m.auth_repo.create_user_block(current_user_id, blocked_user_id)


def _fetch_current_row_compat(m, *, db, current_user_id: str, week_start, tenant_id: str | None):
    try:
        return m._fetch_current_row(db, current_user_id, week_start, tenant_id=tenant_id)
    except TypeError:
        return m._fetch_current_row(db, current_user_id, week_start)


def _repo_get_current_match_compat(m, *, user_id: str, tenant_id: str | None):
    try:
        return m.repo_get_current_match(
            user_id=user_id,
            now=datetime.now(timezone.utc),
            tenant_id=tenant_id,
        )
    except TypeError:
        return m.repo_get_current_match(
            user_id=user_id,
            now=datetime.now(timezone.utc),
        )


def _create_match_report_compat(
    m,
    *,
    week_start_date,
    user_id: str,
    matched_user_id: str,
    reason: str,
    details: str | None,
    tenant_id: str | None,
):
    try:
        return m.auth_repo.create_match_report(
            week_start_date=week_start_date,
            user_id=user_id,
            matched_user_id=matched_user_id,
            reason=reason,
            details=details,
            tenant_id=tenant_id,
        )
    except TypeError:
        return m.auth_repo.create_match_report(
            week_start_date=week_start_date,
            user_id=user_id,
            matched_user_id=matched_user_id,
            reason=reason,
            details=details,
        )


@scaffold_router.get("/health")
def safety_scaffold_health() -> dict[str, str]:
    return {"status": "ok", "module": "safety"}


@router.post("/safety/block")
def safety_block(payload: dict[str, Any], current_user: dict[str, Any] = Depends(require_verified_user)) -> dict[str, Any]:
    from .. import main as m

    blocked_identifier = str(payload.get("blocked_user_id", "")).strip()
    if not blocked_identifier:
        raise HTTPException(status_code=400, detail="blocked_user_id required")

    try:
        potential_uuid = str(uuid.UUID(blocked_identifier))
        if potential_uuid == str(current_user["id"]):
            raise HTTPException(status_code=400, detail="Cannot block yourself")
    except ValueError:
        pass

    blocked_user_id = _resolve_user_id_from_identifier_compat(
        m,
        blocked_identifier=blocked_identifier,
        current_user_id=str(current_user["id"]),
        tenant_id=m._tenant_id_from_user(current_user),
    )
    if not blocked_user_id:
        raise HTTPException(status_code=404, detail="User not found for provided block identifier")
    if blocked_user_id == str(current_user["id"]):
        raise HTTPException(status_code=400, detail="Cannot block yourself")
    tenant_id = m._tenant_id_from_user(current_user)
    ok = _create_user_block_compat(
        m,
        current_user_id=str(current_user["id"]),
        blocked_user_id=blocked_user_id,
        tenant_id=tenant_id,
    )
    if not ok:
        raise HTTPException(status_code=400, detail="Could not create block")

    now = datetime.now(timezone.utc)
    week_start = m.get_week_start_date(now, m.MATCH_TIMEZONE)
    with m.SessionLocal() as db:
        row = _fetch_current_row_compat(
            m,
            db=db,
            current_user_id=str(current_user["id"]),
            week_start=week_start,
            tenant_id=tenant_id,
        )
        if row and row.get("matched_user_id") and str(row.get("matched_user_id")) == blocked_user_id:
            m._apply_status(db, row, "blocked")
            m.log_match_event(
                db,
                user_id=str(current_user["id"]),
                week_start_date=week_start,
                event_type="blocked_current_match",
                payload={"blocked_user_id": blocked_user_id},
                tenant_id=tenant_id,
            )
            m.log_product_event(
                db,
                event_name="safety_block_created",
                user_id=str(current_user["id"]),
                tenant_id=tenant_id,
                properties={"blocked_user_id": blocked_user_id},
            )
            db.commit()
    return {"status": "blocked", "blocked_user_id": blocked_user_id}


@router.post("/safety/unblock")
def safety_unblock(payload: dict[str, Any], current_user: dict[str, Any] = Depends(require_verified_user)) -> dict[str, Any]:
    from .. import main as m

    blocked_user_id = str(payload.get("blocked_user_id", "")).strip()
    if not blocked_user_id:
        raise HTTPException(status_code=400, detail="blocked_user_id required")
    removed = m.auth_repo.remove_user_block(
        str(current_user["id"]),
        blocked_user_id,
        tenant_id=m._tenant_id_from_user(current_user),
    )
    return {"status": "unblocked", "blocked_user_id": blocked_user_id, "removed": removed}


@router.get("/safety/blocks")
def safety_blocks(current_user: dict[str, Any] = Depends(require_verified_user)) -> dict[str, Any]:
    from .. import main as m

    rows = m.auth_repo.list_user_blocks(str(current_user["id"]), tenant_id=m._tenant_id_from_user(current_user))
    return {"blocks": rows}


@router.post("/safety/report")
def safety_report(payload: dict[str, Any], current_user: dict[str, Any] = Depends(require_verified_user)) -> dict[str, Any]:
    from .. import main as m

    reason = str(payload.get("reason", "")).strip()
    details_raw = payload.get("details")
    details = str(details_raw).strip() if details_raw is not None else None
    if not reason:
        raise HTTPException(status_code=400, detail="reason required")

    row = _repo_get_current_match_compat(
        m,
        user_id=str(current_user["id"]),
        tenant_id=m._tenant_id_from_user(current_user),
    )
    if not row or not row.get("matched_user_id") or row.get("status") == "no_match":
        raise HTTPException(status_code=400, detail="No active match to report")

    report = _create_match_report_compat(
        m,
        week_start_date=row["week_start_date"],
        user_id=str(current_user["id"]),
        matched_user_id=str(row["matched_user_id"]),
        reason=reason,
        details=details,
        tenant_id=m._tenant_id_from_user(current_user),
    )
    with m.SessionLocal() as db:
        m.log_product_event(
            db,
            event_name="safety_report_created",
            user_id=str(current_user["id"]),
            tenant_id=m._tenant_id_from_user(current_user),
            properties={"reason": reason},
        )
        db.commit()
    return {"status": "reported", "report": report}