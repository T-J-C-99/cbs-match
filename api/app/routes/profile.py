from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy import text

from .. import repo as auth_repo
from ..auth.deps import get_current_user, require_verified_user
from ..config import SURVEY_SLUG, SURVEY_VERSION
from ..database import SessionLocal
from ..http_helpers import sanitize_profile_payload, store_uploaded_photo, validate_username
from ..services.events import log_product_event, log_profile_event
from ..services.explanations import generate_profile_insights
from ..services.survey_runtime import get_active_survey_runtime
from ..services.survey_reconciliation import get_user_survey_status

router = APIRouter()
scaffold_router = APIRouter()


def _tenant_id_from_user(user: dict[str, Any]) -> str | None:
    value = user.get("tenant_id")
    return str(value) if value else None


def repo_get_user_state(user_id: str, tenant_slug: str | None = None) -> dict[str, Any]:
    runtime = get_active_survey_runtime(tenant_slug)
    active_slug = str(runtime.get("slug") or SURVEY_SLUG)
    active_version = int(runtime.get("version") or SURVEY_VERSION)
    active_hash = str(runtime.get("hash") or "")

    with SessionLocal() as db:
        current_traits = db.execute(
            text(
                """
                SELECT traits, computed_at, computed_for_survey_hash, ocean_scores, insights_json
                FROM user_traits
                WHERE user_id = :user_id
                  AND survey_slug = :survey_slug
                  AND survey_version = :survey_version
                ORDER BY computed_at DESC
                LIMIT 1
                """
            ),
            {
                "user_id": user_id,
                "survey_slug": active_slug,
                "survey_version": active_version,
            },
        ).mappings().first()

        sessions = db.execute(
            text(
                """
                SELECT id, status, started_at, completed_at
                FROM survey_session
                WHERE user_id = :user_id
                ORDER BY started_at DESC
                """
            ),
            {"user_id": user_id},
        ).mappings().all()

        latest_traits = db.execute(
            text(
                """
                SELECT traits, computed_at
                FROM user_traits
                WHERE user_id = :user_id
                ORDER BY computed_at DESC
                LIMIT 1
                """
            ),
            {"user_id": user_id},
        ).mappings().first()

        profile_row = db.execute(
            text(
                """
                SELECT
                  display_name,
                  cbs_year,
                  hometown,
                  COALESCE(photo_urls, '[]'::jsonb) AS photo_urls,
                  gender_identity,
                  COALESCE(seeking_genders, '[]'::jsonb) AS seeking_genders
                FROM user_account
                WHERE id = CAST(:user_id AS uuid)
                """
            ),
            {"user_id": user_id},
        ).mappings().first()
        survey_status = get_user_survey_status(db, user_id, tenant_id=None, tenant_slug=tenant_slug)

    active_session = next((row for row in sessions if row["status"] == "in_progress"), None)
    completed_session = next((row for row in sessions if row["status"] == "completed"), None)

    display_name = str((profile_row or {}).get("display_name") or "").strip()
    cbs_year = str((profile_row or {}).get("cbs_year") or "").strip()
    hometown = str((profile_row or {}).get("hometown") or "").strip()
    photo_urls = (profile_row or {}).get("photo_urls") if isinstance((profile_row or {}).get("photo_urls"), list) else []
    gender_identity = str((profile_row or {}).get("gender_identity") or "").strip().lower()
    seeking_genders = (profile_row or {}).get("seeking_genders") if isinstance((profile_row or {}).get("seeking_genders"), list) else []

    missing_profile_fields: list[str] = []
    if not display_name:
        missing_profile_fields.append("display_name")
    if cbs_year not in {"26", "27"}:
        missing_profile_fields.append("cbs_year")
    if not hometown:
        missing_profile_fields.append("hometown")
    if len([p for p in photo_urls if isinstance(p, str) and p.strip()]) < 1:
        missing_profile_fields.append("photo_urls")
    if gender_identity not in {"man", "woman", "nonbinary", "other"}:
        missing_profile_fields.append("gender_identity")
    cleaned_seeking = [str(v).strip().lower() for v in seeking_genders if str(v).strip()]
    if not cleaned_seeking:
        missing_profile_fields.append("seeking_genders")

    has_required_profile = len(missing_profile_fields) == 0

    return {
        "has_any_session": bool(sessions),
        "has_completed_survey": bool(survey_status.get("is_complete")),
        "survey_outdated": latest_traits is not None and current_traits is None,
        "active_session_id": str(active_session["id"]) if active_session else None,
        "latest_completed_session_at": completed_session["completed_at"] if completed_session else None,
        "active_survey_slug": active_slug,
        "active_survey_version": active_version,
        "active_survey_hash": active_hash,
        "survey_status": survey_status,
        "latest_traits": latest_traits["traits"] if latest_traits else None,
        "current_traits": current_traits["traits"] if current_traits else None,
        "latest_traits_computed_at": latest_traits["computed_at"] if latest_traits else None,
        "current_traits_computed_at": current_traits["computed_at"] if current_traits else None,
        "current_traits_survey_hash": current_traits["computed_for_survey_hash"] if current_traits else None,
        "ocean_scores": current_traits["ocean_scores"] if current_traits else None,
        "insights": current_traits["insights_json"] if current_traits else None,
        "has_required_profile": has_required_profile,
        "missing_profile_fields": missing_profile_fields,
    }


def _fetch_traits(db, user_id: str) -> dict[str, Any] | None:
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
            "survey_slug": SURVEY_SLUG,
            "survey_version": SURVEY_VERSION,
        },
    ).mappings().first()
    return row["traits"] if row else None


@scaffold_router.get("/health")
def profile_scaffold_health() -> dict[str, str]:
    return {"status": "ok", "module": "profile"}


@router.get("/users/me/state")
def user_state(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    state = repo_get_user_state(str(current_user["id"]), tenant_slug=current_user.get("tenant_slug"))
    return {
        "user": {
            "id": str(current_user["id"]),
            "email": str(current_user["email"]),
            "username": current_user.get("username"),
            "is_email_verified": bool(current_user["is_email_verified"]),
        },
        "onboarding": {
            "has_any_session": bool(state["has_any_session"]),
            "has_completed_survey": bool(state["has_completed_survey"]),
            "survey_outdated": bool(state.get("survey_outdated")),
            "active_survey_slug": state.get("active_survey_slug"),
            "active_survey_version": state.get("active_survey_version"),
            "active_survey_hash": state.get("active_survey_hash"),
            "active_session_id": state["active_session_id"],
            "latest_completed_session_at": state["latest_completed_session_at"],
            "survey_status": state.get("survey_status") or {},
        },
        "profile": {
            "has_required_profile": bool(state.get("has_required_profile")),
            "missing_fields": state.get("missing_profile_fields") or [],
        },
        "latest_traits": state["latest_traits"],
        "current_traits": state.get("current_traits"),
        "latest_traits_computed_at": state["latest_traits_computed_at"],
        "current_traits_computed_at": state.get("current_traits_computed_at"),
        "current_traits_survey_hash": state.get("current_traits_survey_hash"),
        "ocean_scores": state.get("ocean_scores"),
        "insights": state.get("insights"),
    }


@router.get("/users/me/profile")
def user_profile(current_user: dict[str, Any] = Depends(require_verified_user)) -> dict[str, Any]:
    profile = auth_repo.get_user_public_profile(str(current_user["id"]))
    if not profile:
        raise HTTPException(status_code=404, detail="User not found")
    with SessionLocal() as db:
        log_product_event(
            db,
            event_name="profile_started",
            user_id=str(current_user["id"]),
            tenant_id=_tenant_id_from_user(current_user),
            properties={"source": "users_me_profile_get"},
        )
        db.commit()
    return {
        "profile": {
            "id": str(profile["id"]),
            "email": str(profile["email"]),
            "username": profile.get("username"),
            "display_name": profile.get("display_name"),
            "cbs_year": profile.get("cbs_year"),
            "hometown": profile.get("hometown"),
            "phone_number": profile.get("phone_number"),
            "instagram_handle": profile.get("instagram_handle"),
            "photo_urls": profile.get("photo_urls") if isinstance(profile.get("photo_urls"), list) else [],
            "gender_identity": profile.get("gender_identity"),
            "seeking_genders": profile.get("seeking_genders") if isinstance(profile.get("seeking_genders"), list) else [],
        }
    }


@router.put("/users/me/profile")
def update_user_profile(payload: dict[str, Any], current_user: dict[str, Any] = Depends(require_verified_user)) -> dict[str, Any]:
    display_name, cbs_year, hometown, phone_number, instagram_handle, photo_urls, gender_identity, seeking_genders = sanitize_profile_payload(payload)
    if gender_identity is None:
        raise HTTPException(status_code=400, detail="gender_identity is required")
    if not seeking_genders:
        raise HTTPException(status_code=400, detail="seeking_genders is required")

    prior = auth_repo.get_user_public_profile(str(current_user["id"])) or {}
    before_gender = str(prior.get("gender_identity") or "").strip().lower() or None
    before_seeking = sorted({str(v or "").strip().lower() for v in (prior.get("seeking_genders") or []) if str(v or "").strip()})
    updated = auth_repo.update_user_profile(
        user_id=str(current_user["id"]),
        display_name=display_name,
        cbs_year=cbs_year,
        hometown=hometown,
        phone_number=phone_number,
        instagram_handle=instagram_handle,
        photo_urls=photo_urls,
        gender_identity=gender_identity,
        seeking_genders=seeking_genders,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="User not found")

    after_gender = str(updated.get("gender_identity") or "").strip().lower() or None
    after_seeking = sorted({str(v or "").strip().lower() for v in (updated.get("seeking_genders") or []) if str(v or "").strip()})
    if before_gender != after_gender or before_seeking != after_seeking:
        with SessionLocal() as db:
            log_profile_event(
                db,
                user_id=str(current_user["id"]),
                event_type="matching_preferences_changed",
                payload={
                    "before": {"gender_identity": before_gender, "seeking_genders": before_seeking},
                    "after": {"gender_identity": after_gender, "seeking_genders": after_seeking},
                    "note": "Preference change will be applied on next matching cycle run",
                },
            )
            db.commit()
    if updated.get("display_name") and updated.get("cbs_year") and updated.get("hometown"):
        with SessionLocal() as db:
            log_product_event(
                db,
                event_name="profile_completed",
                user_id=str(current_user["id"]),
                tenant_id=str(updated.get("tenant_id")) if updated.get("tenant_id") else None,
                properties={"source": "users_me_profile"},
            )
            db.commit()

    return {
        "profile": {
            "id": str(updated["id"]),
            "email": str(updated["email"]),
            "username": updated.get("username"),
            "display_name": updated.get("display_name"),
            "cbs_year": updated.get("cbs_year"),
            "hometown": updated.get("hometown"),
            "phone_number": updated.get("phone_number"),
            "instagram_handle": updated.get("instagram_handle"),
            "photo_urls": updated.get("photo_urls") if isinstance(updated.get("photo_urls"), list) else [],
            "gender_identity": updated.get("gender_identity"),
            "seeking_genders": updated.get("seeking_genders") if isinstance(updated.get("seeking_genders"), list) else [],
        }
    }


@router.get("/users/me/insights")
def get_user_insights(current_user: dict[str, Any] = Depends(require_verified_user)) -> dict[str, Any]:
    user_id = str(current_user["id"])

    with SessionLocal() as db:
        runtime = get_active_survey_runtime(current_user.get("tenant_slug"))
        active_slug = str(runtime.get("slug") or SURVEY_SLUG)
        active_version = int(runtime.get("version") or SURVEY_VERSION)
        active_hash = str(runtime.get("hash") or "")

        row = db.execute(
            text(
                """
                SELECT traits, ocean_scores, insights_json, computed_for_survey_hash
                FROM user_traits
                WHERE user_id=:user_id
                  AND survey_slug=:survey_slug
                  AND survey_version=:survey_version
                LIMIT 1
                """
            ),
            {"user_id": user_id, "survey_slug": active_slug, "survey_version": active_version},
        ).mappings().first()
        user_traits = row["traits"] if row and isinstance(row.get("traits"), dict) else _fetch_traits(db, user_id)
        stored_ocean = row.get("ocean_scores") if row and isinstance(row.get("ocean_scores"), dict) else None
        stored_insights = row.get("insights_json") if row and isinstance(row.get("insights_json"), list) else None
        computed_for_hash = str(row.get("computed_for_survey_hash") or "") if row else ""
        profile_row = db.execute(
            text(
                """
                SELECT
                  display_name,
                  cbs_year,
                  hometown,
                  COALESCE(photo_urls, '[]'::jsonb) AS photo_urls,
                  gender_identity,
                  COALESCE(seeking_genders, '[]'::jsonb) AS seeking_genders
                FROM user_account
                WHERE id = CAST(:user_id AS uuid)
                """
            ),
            {"user_id": user_id},
        ).mappings().first()

    profile_data = dict(profile_row) if profile_row else {}
    # Support both legacy traits payload (big5) and current match-core-v3 payload (big_five).
    # In v3, neuroticism is represented as emotional_regulation.stability (inverse of neuroticism).
    big5 = (user_traits or {}).get("big5") or (user_traits or {}).get("big_five") or {}
    emotional_regulation = (user_traits or {}).get("emotional_regulation") or {}
    inferred_neuroticism = 1.0 - float(emotional_regulation.get("stability", 0.5))
    ocean_scores = stored_ocean or {
        "openness": round(big5.get("openness", 0.5) * 100),
        "conscientiousness": round(big5.get("conscientiousness", 0.5) * 100),
        "extraversion": round(big5.get("extraversion", 0.5) * 100),
        "agreeableness": round(big5.get("agreeableness", 0.5) * 100),
        "neuroticism": round(float(big5.get("neuroticism", inferred_neuroticism)) * 100),
    }
    insights = stored_insights or generate_profile_insights(user_traits, profile_data, count=4)

    return {
        "insights": insights,
        "ocean_scores": ocean_scores,
        "has_traits": user_traits is not None,
        "computed_for_survey_hash": computed_for_hash,
        "current_survey_hash": active_hash,
        "is_current": bool(computed_for_hash and computed_for_hash == active_hash),
        "version": "2026-02-17-v2",
    }


@router.delete("/users/me/account")
def delete_my_account(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    auth_repo.anonymize_and_disable_user(str(current_user["id"]))
    return {"status": "deleted", "message": "Account deleted"}


@router.put("/users/me/username")
def update_user_username(payload: dict[str, Any], current_user: dict[str, Any] = Depends(require_verified_user)) -> dict[str, Any]:
    username = validate_username(str(payload.get("username") or ""))
    if not auth_repo.is_username_available(username, exclude_user_id=str(current_user["id"])):
        raise HTTPException(status_code=409, detail="Username is already taken")
    updated = auth_repo.update_username(str(current_user["id"]), username)
    if not updated:
        raise HTTPException(status_code=404, detail="User not found")
    return {"username": updated.get("username")}


@router.get("/users/me/preferences")
def get_user_preferences(current_user: dict[str, Any] = Depends(require_verified_user)) -> dict[str, Any]:
    pref = auth_repo.get_user_preferences(str(current_user["id"]))
    return {
        "preferences": {
            "pause_matches": bool(pref.get("pause_matches", False)),
            "updated_at": pref.get("updated_at"),
        }
    }


@router.put("/users/me/preferences")
def update_user_preferences(payload: dict[str, Any], current_user: dict[str, Any] = Depends(require_verified_user)) -> dict[str, Any]:
    pause_matches = bool(payload.get("pause_matches", False))
    pref = auth_repo.update_user_preferences(str(current_user["id"]), pause_matches)
    return {
        "preferences": {
            "pause_matches": bool(pref.get("pause_matches", False)),
            "updated_at": pref.get("updated_at"),
        }
    }


@router.get("/users/me/notification-preferences")
def get_notification_preferences(current_user: dict[str, Any] = Depends(require_verified_user)) -> dict[str, Any]:
    pref = auth_repo.get_notification_preferences(
        str(current_user["id"]),
        tenant_id=_tenant_id_from_user(current_user),
    )
    return {"preferences": pref}


@router.put("/users/me/notification-preferences")
def update_notification_preferences(payload: dict[str, Any], current_user: dict[str, Any] = Depends(require_verified_user)) -> dict[str, Any]:
    timezone_value = str(payload.get("timezone") or "America/New_York")
    updated = auth_repo.update_notification_preferences(
        user_id=str(current_user["id"]),
        tenant_id=_tenant_id_from_user(current_user),
        email_enabled=bool(payload.get("email_enabled", True)),
        push_enabled=bool(payload.get("push_enabled", False)),
        quiet_hours_start_local=payload.get("quiet_hours_start_local"),
        quiet_hours_end_local=payload.get("quiet_hours_end_local"),
        timezone=timezone_value,
    )
    return {"preferences": updated}


@router.get("/users/me/vibe-card")
def get_my_vibe_card(current_user: dict[str, Any] = Depends(require_verified_user)) -> dict[str, Any]:
    row = auth_repo.get_saved_user_vibe_card(
        str(current_user["id"]),
        survey_slug=SURVEY_SLUG,
        survey_version=SURVEY_VERSION,
    ) or auth_repo.get_latest_user_vibe_card(
        str(current_user["id"]),
        survey_slug=SURVEY_SLUG,
        survey_version=SURVEY_VERSION,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Vibe card not found")
    with SessionLocal() as db:
        log_product_event(
            db,
            event_name="vibe_card_viewed",
            user_id=str(current_user["id"]),
            tenant_id=_tenant_id_from_user(current_user),
            properties={"survey_slug": SURVEY_SLUG, "survey_version": SURVEY_VERSION},
        )
        db.commit()
    return {
        "survey_slug": row.get("survey_slug"),
        "survey_version": row.get("survey_version"),
        "vibe_card": row.get("payload_json") if isinstance(row.get("payload_json"), dict) else (row.get("vibe_json") if isinstance(row.get("vibe_json"), dict) else {}),
        "vibe": row.get("payload_json") if isinstance(row.get("payload_json"), dict) else (row.get("vibe_json") if isinstance(row.get("vibe_json"), dict) else {}),
        "created_at": row.get("created_at"),
        "saved": bool(row.get("payload_json")) and row.get("id") is not None,
    }


@router.post("/users/me/vibe-card/save")
def save_my_vibe_card(current_user: dict[str, Any] = Depends(require_verified_user)) -> dict[str, Any]:
    row = auth_repo.get_latest_user_vibe_card(
        str(current_user["id"]),
        survey_slug=SURVEY_SLUG,
        survey_version=SURVEY_VERSION,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Vibe card not found")

    vibe_json = row.get("vibe_json") if isinstance(row.get("vibe_json"), dict) else {}
    vibe_version = str(((vibe_json.get("meta") or {}).get("version") or "vibe-card-legacy"))
    saved = auth_repo.save_user_vibe_card_snapshot(
        user_id=str(current_user["id"]),
        tenant_id=_tenant_id_from_user(current_user),
        survey_slug=str(row.get("survey_slug") or SURVEY_SLUG),
        survey_version=int(row.get("survey_version") or SURVEY_VERSION),
        vibe_version=vibe_version,
        vibe_json=vibe_json,
    )
    with SessionLocal() as db:
        log_product_event(
            db,
            event_name="vibe_card_saved",
            user_id=str(current_user["id"]),
            tenant_id=_tenant_id_from_user(current_user),
            properties={"survey_slug": SURVEY_SLUG, "survey_version": SURVEY_VERSION},
        )
        db.commit()
    return {
        "status": "saved",
        "survey_slug": saved.get("survey_slug"),
        "survey_version": saved.get("survey_version"),
        "vibe_card": saved.get("payload_json") if isinstance(saved.get("payload_json"), dict) else vibe_json,
        "saved_at": saved.get("created_at"),
    }


@router.post("/users/me/profile/photos")
async def upload_profile_photos(
    request: Request,
    photos: list[UploadFile] = File(...),
    replace_index: int | None = Form(None),
    current_user: dict[str, Any] = Depends(require_verified_user),
) -> dict[str, Any]:
    if not photos:
        raise HTTPException(status_code=400, detail="No photos uploaded")

    user_id = str(current_user["id"])
    prior = auth_repo.get_user_public_profile(user_id) or {}
    existing_urls = [str(v or "").strip() for v in (prior.get("photo_urls") or []) if str(v or "").strip()][:3]

    if replace_index is not None:
        if replace_index < 0 or replace_index > 2:
            raise HTTPException(status_code=400, detail="replace_index must be between 0 and 2")
        if len(photos) != 1:
            raise HTTPException(status_code=400, detail="Replace mode accepts exactly 1 photo")

        new_url = await store_uploaded_photo(photos[0], user_id, request)
        merged_urls = list(existing_urls)
        if replace_index < len(merged_urls):
            merged_urls[replace_index] = new_url
        elif replace_index == len(merged_urls):
            merged_urls.append(new_url)
        else:
            raise HTTPException(status_code=400, detail="Fill earlier photo slots before skipping to a later slot")
    else:
        remaining_slots = 3 - len(existing_urls)
        if remaining_slots <= 0:
            raise HTTPException(status_code=400, detail="You already have 3 photos. Remove one before uploading a new photo")
        if len(photos) > remaining_slots:
            raise HTTPException(
                status_code=400,
                detail=f"You can upload up to {remaining_slots} more photo{'s' if remaining_slots != 1 else ''}",
            )
        new_urls = [await store_uploaded_photo(f, user_id, request) for f in photos[:remaining_slots]]
        merged_urls = [*existing_urls, *new_urls][:3]

    gender_identity = str(prior.get("gender_identity") or "").strip().lower() or None
    seeking_genders = [
        str(v or "").strip().lower()
        for v in (prior.get("seeking_genders") or [])
        if str(v or "").strip()
    ]

    updated = auth_repo.update_user_profile(
        user_id=user_id,
        display_name=prior.get("display_name"),
        cbs_year=prior.get("cbs_year"),
        hometown=prior.get("hometown"),
        phone_number=prior.get("phone_number"),
        instagram_handle=prior.get("instagram_handle"),
        photo_urls=merged_urls,
        gender_identity=gender_identity,
        seeking_genders=seeking_genders,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "photo_urls": updated.get("photo_urls") if isinstance(updated.get("photo_urls"), list) else merged_urls,
    }


@router.post("/users/me/support/feedback")
def submit_support_feedback(payload: dict[str, Any], current_user: dict[str, Any] = Depends(require_verified_user)) -> dict[str, Any]:
    message = str(payload.get("message") or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="message is required")
    if len(message) > 2000:
        raise HTTPException(status_code=400, detail="message must be 2000 characters or fewer")
    created = auth_repo.create_support_feedback(str(current_user["id"]), message)
    return {"feedback": created}
