from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ..auth.deps import require_verified_user
from ..config import RL_MATCH_ACCEPT_LIMIT, RL_MATCH_DECLINE_LIMIT, RL_MATCH_FEEDBACK_LIMIT, RL_WINDOW_SECONDS
from ..services.rate_limit import rate_limit_dependency
from ..services.explanations import build_safe_explanation_v2

router = APIRouter()
scaffold_router = APIRouter()

RL_MATCH_ACCEPT = rate_limit_dependency("match_accept", RL_MATCH_ACCEPT_LIMIT, RL_WINDOW_SECONDS)
RL_MATCH_DECLINE = rate_limit_dependency("match_decline", RL_MATCH_DECLINE_LIMIT, RL_WINDOW_SECONDS)
RL_MATCH_FEEDBACK = rate_limit_dependency("match_feedback", RL_MATCH_FEEDBACK_LIMIT, RL_WINDOW_SECONDS)


def _repo_get_current_match_compat(m, *, user_id: str, tenant_id: str | None):
    try:
        return m.repo_get_current_match(user_id=user_id, now=datetime.now(timezone.utc), tenant_id=tenant_id)
    except TypeError:
        return m.repo_get_current_match(user_id=user_id, now=datetime.now(timezone.utc))


def _repo_update_current_match_status_compat(m, *, user_id: str, action: str, tenant_id: str | None):
    try:
        return m.repo_update_current_match_status(
            user_id=user_id,
            action=action,
            now=datetime.now(timezone.utc),
            tenant_id=tenant_id,
        )
    except TypeError:
        return m.repo_update_current_match_status(
            user_id=user_id,
            action=action,
            now=datetime.now(timezone.utc),
        )


def _repo_submit_match_feedback_compat(m, *, user_id: str, answers: dict[str, Any], tenant_id: str | None):
    try:
        return m.repo_submit_match_feedback(
            user_id=user_id,
            now=datetime.now(timezone.utc),
            answers=answers,
            tenant_id=tenant_id,
        )
    except TypeError:
        return m.repo_submit_match_feedback(
            user_id=user_id,
            now=datetime.now(timezone.utc),
            answers=answers,
        )


@scaffold_router.get("/health")
def match_scaffold_health() -> dict[str, str]:
    return {"status": "ok", "module": "match"}


@router.get("/matches/current")
def get_current_match(current_user: dict[str, Any] = Depends(require_verified_user)) -> dict[str, Any]:
    from .. import main as m

    user_id = str(current_user["id"])
    tenant_id = m._tenant_id_from_user(current_user)
    row = _repo_get_current_match_compat(m, user_id=user_id, tenant_id=tenant_id)
    if not row:
        return {
            "match": None,
            "message": "No match has been assigned for this week yet",
            "explanation": {"bullets": [], "icebreakers": []},
            "explanation_v2": {
                "overall": "No match has been assigned for this week yet.",
                "pros": [
                    "We will evaluate your profile again in the next cycle.",
                    "Your account stays eligible while your profile remains complete.",
                ],
                "cons": [
                    "There is no active match to review right now.",
                    "Timing and cohort availability can vary week to week.",
                ],
                "version": "2026-02-12",
            },
        }

    payload = {
        "match": row,
        "message": "You’re matched for this week. Take a look and decide if you want to connect offline." if row.get("status") != "no_match" else ("This match is unavailable due to your safety settings. You will be considered again next week." if (row.get("score_breakdown") or {}).get("reason") == "blocked_match_hidden" else "No match this week. We are improving recommendations."),
        "explanation": row.get("explanation") or {"bullets": [], "icebreakers": []},
        "explanation_v2": row.get("explanation_v2") or build_safe_explanation_v2(row.get("score_breakdown") or {}, {}, {}),
        "feedback": row.get("feedback") or {"eligible": False, "already_submitted": False, "due_met_question": False},
    }
    with m.SessionLocal() as db:
        m.log_product_event(
            db,
            event_name="match_viewed",
            user_id=str(current_user["id"]),
            tenant_id=m._tenant_id_from_user(current_user),
            properties={"status": (row or {}).get("status")},
        )
        db.commit()
    return payload


@router.get("/matches/history")
def get_matches_history(limit: int = 12, current_user: dict[str, Any] = Depends(require_verified_user)) -> dict[str, Any]:
    from .. import main as m

    rows = m.auth_repo.list_match_history(
        str(current_user["id"]),
        limit=limit,
        tenant_id=m._tenant_id_from_user(current_user),
    )
    with m.SessionLocal() as db:
        user_traits = m._fetch_traits(db, str(current_user["id"]))
        matched_traits_by_user: dict[str, dict[str, Any] | None] = {}
        for r in rows:
            mid = r.get("matched_user_id")
            if not mid:
                continue
            mid_s = str(mid)
            if mid_s not in matched_traits_by_user:
                matched_traits_by_user[mid_s] = m._fetch_traits(db, mid_s)

    history: list[dict[str, Any]] = []
    for r in rows:
        mid_s = str(r.get("matched_user_id")) if r.get("matched_user_id") else ""
        explanation_v2 = build_safe_explanation_v2(
            r.get("score_breakdown") or {},
            user_traits or {},
            (matched_traits_by_user.get(mid_s) or {}) if mid_s else {},
        )
        history.append(
            {
                "week_start_date": str(r.get("week_start_date")),
                "status": str(r.get("status") or ""),
                "matched_profile": {
                    "id": str(r.get("matched_user_id")) if r.get("matched_user_id") else None,
                    "email": r.get("matched_email"),
                    "phone_number": r.get("matched_phone_number"),
                    "instagram_handle": r.get("matched_instagram_handle"),
                    "display_name": r.get("matched_display_name"),
                    "cbs_year": r.get("matched_cbs_year"),
                    "hometown": r.get("matched_hometown"),
                    "photo_urls": r.get("matched_photo_urls") if isinstance(r.get("matched_photo_urls"), list) else [],
                },
                "explanation_v2": explanation_v2,
            }
        )
    return {"history": history}


@router.get("/users/me/matches/history")
def get_user_match_history(limit: int = 20, current_user: dict[str, Any] = Depends(require_verified_user)) -> dict[str, Any]:
    from .. import main as m

    rows = m.auth_repo.list_match_history(
        str(current_user["id"]),
        limit=limit,
        tenant_id=m._tenant_id_from_user(current_user),
    )
    return {
        "history": [
            {
                **r,
                "week_start_date": str(r.get("week_start_date")),
                "matched_photo_urls": r.get("matched_photo_urls") if isinstance(r.get("matched_photo_urls"), list) else [],
            }
            for r in rows
        ]
    }


@router.post("/matches/current/accept")
def accept_current_match(current_user: dict[str, Any] = Depends(require_verified_user), _: None = RL_MATCH_ACCEPT) -> dict[str, Any]:
    from .. import main as m

    out = _repo_update_current_match_status_compat(
        m,
        user_id=str(current_user["id"]),
        action="accept",
        tenant_id=m._tenant_id_from_user(current_user),
    )
    with m.SessionLocal() as db:
        m.log_product_event(
            db,
            event_name="match_accepted",
            user_id=str(current_user["id"]),
            tenant_id=m._tenant_id_from_user(current_user),
            properties={"status": out.get("status")},
        )
        db.commit()
    return out


@router.post("/matches/current/decline")
def decline_current_match(current_user: dict[str, Any] = Depends(require_verified_user), _: None = RL_MATCH_DECLINE) -> dict[str, Any]:
    from .. import main as m

    out = _repo_update_current_match_status_compat(
        m,
        user_id=str(current_user["id"]),
        action="decline",
        tenant_id=m._tenant_id_from_user(current_user),
    )
    with m.SessionLocal() as db:
        m.log_product_event(
            db,
            event_name="match_declined",
            user_id=str(current_user["id"]),
            tenant_id=m._tenant_id_from_user(current_user),
            properties={"status": out.get("status")},
        )
        db.commit()
    return out


@router.post("/matches/current/feedback")
def submit_current_feedback(
    payload: dict[str, Any],
    current_user: dict[str, Any] = Depends(require_verified_user),
    _: None = RL_MATCH_FEEDBACK,
) -> dict[str, Any]:
    from .. import main as m

    answers = payload.get("answers")
    if not isinstance(answers, dict):
        raise HTTPException(status_code=400, detail="answers must be an object")
    out = _repo_submit_match_feedback_compat(
        m,
        user_id=str(current_user["id"]),
        answers=answers,
        tenant_id=m._tenant_id_from_user(current_user),
    )
    with m.SessionLocal() as db:
        m.log_product_event(
            db,
            event_name="feedback_submitted",
            user_id=str(current_user["id"]),
            tenant_id=m._tenant_id_from_user(current_user),
            properties={"fields": sorted(list((out.get("answers") or {}).keys()))},
        )
        if bool((out.get("answers") or {}).get("met")):
            m.log_product_event(
                db,
                event_name="met_self_reported",
                user_id=str(current_user["id"]),
                tenant_id=m._tenant_id_from_user(current_user),
                properties={},
            )
        if "chemistry" in (out.get("answers") or {}):
            m.log_product_event(
                db,
                event_name="chemistry_rating_submitted",
                user_id=str(current_user["id"]),
                tenant_id=m._tenant_id_from_user(current_user),
                properties={"chemistry": (out.get("answers") or {}).get("chemistry")},
            )
        db.commit()
    return out


@router.post("/matches/current/contact-click")
def track_contact_click(payload: dict[str, Any], current_user: dict[str, Any] = Depends(require_verified_user)) -> dict[str, Any]:
    from .. import main as m

    channel = str(payload.get("channel") or "").strip().lower()
    if channel not in {"email", "phone", "instagram"}:
        raise HTTPException(status_code=400, detail="channel must be one of: email, phone, instagram")
    with m.SessionLocal() as db:
        m.log_product_event(
            db,
            event_name=f"contact_clicked_{'ig' if channel == 'instagram' else channel}",
            user_id=str(current_user["id"]),
            tenant_id=m._tenant_id_from_user(current_user),
            properties={"channel": channel},
        )
        m.log_product_event(
            db,
            event_name="contact_clicked",
            user_id=str(current_user["id"]),
            tenant_id=m._tenant_id_from_user(current_user),
            properties={"channel": channel},
        )
        db.commit()
    return {"status": "ok", "channel": channel}
