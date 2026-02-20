from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ..auth.deps import get_current_user
from ..config import RL_SESSION_ANSWERS_LIMIT, RL_WINDOW_SECONDS
from ..database import SessionLocal
from ..services.rate_limit import rate_limit_dependency
from ..survey_loader import get_survey_definition
from ..services.survey_runtime import get_active_survey_runtime, list_question_codes
from ..services.survey_reconciliation import (
    get_user_survey_status,
    recompute_user_traits_if_ready,
    reconcile_user_survey_to_current,
    upsert_reconciled_answers,
)

router = APIRouter()
scaffold_router = APIRouter()

RL_SESSION_ANSWERS = rate_limit_dependency("session_answers", RL_SESSION_ANSWERS_LIMIT, RL_WINDOW_SECONDS)


def _require_session_owner(session_id: str, user_id: str) -> dict[str, Any]:
    from .. import main as m

    payload = m.repo_get_session_with_answers(session_id)
    if not payload:
        raise HTTPException(status_code=404, detail="Session not found")
    if str(payload["session"].get("user_id")) != str(user_id):
        raise HTTPException(status_code=403, detail="Forbidden")
    session_tenant = str(payload["session"].get("tenant_id")) if payload["session"].get("tenant_id") else None
    if session_tenant:
        user_tenant = m.auth_repo.get_tenant_id_for_user(str(user_id))
        if user_tenant and str(user_tenant) != str(session_tenant):
            raise HTTPException(status_code=403, detail="Forbidden")
    return payload


def _get_survey_definition_for_user(current_user: dict[str, Any]) -> dict[str, Any]:
    try:
        return get_survey_definition(current_user.get("tenant_slug"))
    except TypeError:
        return get_survey_definition()


@scaffold_router.get("/health")
def survey_scaffold_health() -> dict[str, str]:
    return {"status": "ok", "module": "survey"}


@router.get("/survey/active")
def get_active_survey(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    return _get_survey_definition_for_user(current_user)


@router.post("/sessions")
def create_session(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, str]:
    from .. import main as m

    runtime = get_active_survey_runtime(current_user.get("tenant_slug"))
    survey_slug = str(runtime.get("slug"))
    survey_version = int(runtime.get("version"))
    survey_hash = str(runtime.get("hash") or "")
    survey_def = runtime.get("definition") if isinstance(runtime.get("definition"), dict) else {}

    existing_current = m.repo_get_latest_in_progress_session(
        user_id=str(current_user["id"]),
        survey_slug=survey_slug,
        survey_version=survey_version,
        survey_hash=survey_hash,
    )
    if existing_current and existing_current.get("id"):
        return {"session_id": str(existing_current["id"]), "user_id": str(current_user["id"])}

    carry_forward_answers: dict[str, Any] = {}
    latest_any = m.repo_get_latest_session_for_slug(user_id=str(current_user["id"]), survey_slug=survey_slug)
    if latest_any and latest_any.get("id"):
        previous = m.repo_get_session_with_answers(str(latest_any["id"]))
        previous_answers = (previous or {}).get("answers") if isinstance((previous or {}).get("answers"), dict) else {}
        if previous_answers:
            allowed_codes = list_question_codes(survey_def)
            carry_forward_answers = {
                code: value
                for code, value in previous_answers.items()
                if code in allowed_codes
            }

    created = m.repo_create_session(
        user_id=str(current_user["id"]),
        survey_slug=survey_slug,
        survey_version=survey_version,
        survey_hash=survey_hash,
        tenant_id=m._tenant_id_from_user(current_user),
    )
    if carry_forward_answers:
        m.repo_upsert_answers(
            created["session_id"],
            [
                {"question_code": code, "answer_value": value}
                for code, value in carry_forward_answers.items()
            ],
        )
    return created


@router.get("/sessions/{session_id}")
def get_session(session_id: str, current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    return _require_session_owner(session_id, str(current_user["id"]))


@router.post("/sessions/{session_id}/answers")
def upsert_answers(
    session_id: str,
    payload: dict[str, Any],
    current_user: dict[str, Any] = Depends(get_current_user),
    _: None = RL_SESSION_ANSWERS,
) -> dict[str, Any]:
    from .. import main as m

    _require_session_owner(session_id, str(current_user["id"]))
    answers = payload.get("answers", [])
    if not isinstance(answers, list):
        raise HTTPException(status_code=400, detail="answers must be a list")
    saved_count = m.repo_upsert_answers(session_id, answers)
    return {"status": "saved", "saved_count": saved_count}


@router.post("/sessions/{session_id}/complete")
def complete_session(session_id: str, current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    from .. import main as m

    _require_session_owner(session_id, str(current_user["id"]))
    return m.repo_complete_session(
        session_id=session_id,
        survey_def=_get_survey_definition_for_user(current_user),
    )


@router.get("/survey/status")
def survey_status(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    tenant_id = str(current_user.get("tenant_id")) if current_user.get("tenant_id") else None
    tenant_slug = str(current_user.get("tenant_slug")) if current_user.get("tenant_slug") else None
    with SessionLocal() as db:
        status = get_user_survey_status(db, str(current_user["id"]), tenant_id=tenant_id, tenant_slug=tenant_slug)
        db.commit()
    return status


@router.post("/survey/reconcile")
def survey_reconcile(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    tenant_id = str(current_user.get("tenant_id")) if current_user.get("tenant_id") else None
    tenant_slug = str(current_user.get("tenant_slug")) if current_user.get("tenant_slug") else None
    with SessionLocal() as db:
        out = reconcile_user_survey_to_current(db, str(current_user["id"]), tenant_id=tenant_id, tenant_slug=tenant_slug)
        db.commit()
    return out


@router.post("/survey/continue")
def survey_continue(payload: dict[str, Any], current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    answers = payload.get("answers")
    if not isinstance(answers, dict):
        raise HTTPException(status_code=400, detail="answers must be an object keyed by question id")

    tenant_id = str(current_user.get("tenant_id")) if current_user.get("tenant_id") else None
    tenant_slug = str(current_user.get("tenant_slug")) if current_user.get("tenant_slug") else None
    with SessionLocal() as db:
        status = upsert_reconciled_answers(
            db,
            user_id=str(current_user["id"]),
            tenant_id=tenant_id,
            tenant_slug=tenant_slug,
            answers_patch=answers,
        )
        traits = recompute_user_traits_if_ready(
            db,
            user_id=str(current_user["id"]),
            tenant_id=tenant_id,
            tenant_slug=tenant_slug,
        )
        db.commit()
    return {"status": status, "traits": traits}
