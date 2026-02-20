import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.config import SURVEY_SLUG, SURVEY_VERSION
from app.services.events import log_profile_event


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_gender(value: Any) -> str | None:
    if value is None:
        return None
    v = str(value).strip().lower()
    return v or None


def _normalize_seeking(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    out: list[str] = []
    for value in values:
        v = str(value or "").strip().lower()
        if not v:
            continue
        if v not in out:
            out.append(v)
    return sorted(out)


def create_user(email: str, password_hash: str, username: str | None = None, tenant_id: str | None = None) -> dict[str, Any] | None:
    user_id = str(uuid.uuid4())
    try:
        with SessionLocal() as db:
            db.execute(
                text(
                    """
                    INSERT INTO user_account (id, email, password_hash, username, is_email_verified, tenant_id)
                    VALUES (:id, :email, :password_hash, :username, true, CAST(NULLIF(:tenant_id, '') AS uuid))
                    """
                ),
                {"id": user_id, "email": email, "password_hash": password_hash, "username": username, "tenant_id": tenant_id or ""},
            )
            db.commit()
    except IntegrityError:
        return None
    return get_user_by_id(user_id)


def get_user_by_email(email: str, tenant_id: str | None = None) -> dict[str, Any] | None:
    with SessionLocal() as db:
        row = db.execute(
            text(
                """
                SELECT *
                FROM user_account
                WHERE email=:email
                  AND (:tenant_id IS NULL OR tenant_id = CAST(:tenant_id AS uuid))
                """
            ),
            {"email": email, "tenant_id": tenant_id},
        ).mappings().first()
    return dict(row) if row else None


def get_user_by_username(username: str, tenant_id: str | None = None) -> dict[str, Any] | None:
    with SessionLocal() as db:
        row = db.execute(
            text(
                """
                SELECT *
                FROM user_account
                WHERE LOWER(username)=LOWER(:username)
                  AND (:tenant_id IS NULL OR tenant_id = CAST(:tenant_id AS uuid))
                """
            ),
            {"username": username, "tenant_id": tenant_id},
        ).mappings().first()
    return dict(row) if row else None


def get_user_by_id(user_id: str) -> dict[str, Any] | None:
    with SessionLocal() as db:
        row = db.execute(text("SELECT * FROM user_account WHERE id=CAST(:id AS uuid)"), {"id": user_id}).mappings().first()
    return dict(row) if row else None


def get_tenant_id_for_user(user_id: str) -> str | None:
    with SessionLocal() as db:
        row = db.execute(
            text("SELECT tenant_id FROM user_account WHERE id=CAST(:id AS uuid)"),
            {"id": user_id},
        ).mappings().first()
    if not row or not row.get("tenant_id"):
        return None
    return str(row["tenant_id"])


def resolve_user_id_from_identifier(
    identifier: str,
    exclude_user_id: str | None = None,
    tenant_id: str | None = None,
) -> str | None:
    raw = str(identifier or "").strip()
    if not raw:
        return None

    try:
        as_uuid = str(uuid.UUID(raw))
        row = get_user_by_id(as_uuid)
        if row and tenant_id and str(row.get("tenant_id") or "") != tenant_id:
            row = None
        if row and (exclude_user_id is None or str(row["id"]) != str(exclude_user_id)):
            return str(row["id"])
    except ValueError:
        pass

    needle = raw.lower()
    with SessionLocal() as db:
        row = db.execute(
            text(
                """
                SELECT id
                FROM user_account
                WHERE disabled_at IS NULL
                  AND (:tenant_id IS NULL OR tenant_id = CAST(:tenant_id AS uuid))
                  AND (
                    LOWER(email) = :needle
                    OR LOWER(COALESCE(username, '')) = :needle
                    OR LOWER(COALESCE(display_name, '')) = :needle
                    OR LOWER(SPLIT_PART(email, '@', 1)) = :needle
                  )
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {"needle": needle, "tenant_id": tenant_id},
        ).mappings().first()

    if not row:
        return None
    resolved = str(row["id"])
    if exclude_user_id and resolved == str(exclude_user_id):
        return None
    return resolved


def get_user_public_profile(user_id: str) -> dict[str, Any] | None:
    with SessionLocal() as db:
        row = db.execute(
            text(
                """
                SELECT
                  ua.id,
                  ua.email,
                  ua.username,
                  COALESCE(up.display_name, ua.display_name, SPLIT_PART(ua.email, '@', 1)) AS display_name,
                  COALESCE(up.cbs_year, ua.cbs_year) AS cbs_year,
                  COALESCE(up.hometown, ua.hometown) AS hometown,
                  COALESCE(up.phone_number, ua.phone_number) AS phone_number,
                  COALESCE(up.instagram_handle, ua.instagram_handle) AS instagram_handle,
                  COALESCE(up.photo_urls, ua.photo_urls, '[]'::jsonb) AS photo_urls,
                  COALESCE(up.gender_identity, ua.gender_identity) AS gender_identity,
                  COALESCE(up.seeking_genders, ua.seeking_genders, '[]'::jsonb) AS seeking_genders,
                  COALESCE(pref.pause_matches, FALSE) AS pause_matches
                FROM user_account ua
                LEFT JOIN user_profile up ON up.user_id = ua.id
                LEFT JOIN user_preferences pref ON pref.user_id = ua.id
                WHERE ua.id=CAST(:id AS uuid)
                """
            ),
            {"id": user_id},
        ).mappings().first()
    return dict(row) if row else None


def get_user_preferences(user_id: str) -> dict[str, Any]:
    with SessionLocal() as db:
        row = db.execute(
            text(
                """
                INSERT INTO user_preferences (user_id)
                VALUES (CAST(:user_id AS uuid))
                ON CONFLICT (user_id) DO NOTHING
                """
            ),
            {"user_id": user_id},
        )
        _ = row
        pref = db.execute(
            text(
                """
                SELECT user_id, pause_matches, updated_at
                FROM user_preferences
                WHERE user_id = CAST(:user_id AS uuid)
                """
            ),
            {"user_id": user_id},
        ).mappings().first()
        db.commit()
    return dict(pref) if pref else {"user_id": user_id, "pause_matches": False, "updated_at": None}


def update_user_preferences(user_id: str, pause_matches: bool) -> dict[str, Any]:
    with SessionLocal() as db:
        db.execute(
            text(
                """
                INSERT INTO user_preferences (user_id, pause_matches, updated_at)
                VALUES (CAST(:user_id AS uuid), :pause_matches, NOW())
                ON CONFLICT (user_id)
                DO UPDATE SET pause_matches = EXCLUDED.pause_matches, updated_at = NOW()
                """
            ),
            {"user_id": user_id, "pause_matches": bool(pause_matches)},
        )
        db.commit()
    return get_user_preferences(user_id)


def upsert_user_profile(
    user_id: str,
    display_name: str,
    cbs_year: str | None,
    hometown: str | None,
    phone_number: str | None,
    instagram_handle: str | None,
    photo_urls: list[str],
    gender_identity: str | None,
    seeking_genders: list[str],
) -> dict[str, Any]:
    prior = get_user_public_profile(user_id) or {}
    prior_gender = _normalize_gender(prior.get("gender_identity"))
    prior_seeking = _normalize_seeking(prior.get("seeking_genders"))

    with SessionLocal() as db:
        db.execute(
            text(
                """
                INSERT INTO user_profile (user_id, display_name, cbs_year, hometown, phone_number, instagram_handle, photo_urls, gender_identity, seeking_genders, updated_at)
                VALUES (CAST(:user_id AS uuid), :display_name, :cbs_year, :hometown, :phone_number, :instagram_handle, CAST(:photo_urls AS jsonb), :gender_identity, CAST(:seeking_genders AS jsonb), NOW())
                ON CONFLICT (user_id)
                DO UPDATE SET
                  display_name = EXCLUDED.display_name,
                  cbs_year = EXCLUDED.cbs_year,
                  hometown = EXCLUDED.hometown,
                  phone_number = EXCLUDED.phone_number,
                  instagram_handle = EXCLUDED.instagram_handle,
                  photo_urls = EXCLUDED.photo_urls,
                  gender_identity = EXCLUDED.gender_identity,
                  seeking_genders = EXCLUDED.seeking_genders,
                  updated_at = NOW()
                """
            ),
            {
                "user_id": user_id,
                "display_name": display_name,
                "cbs_year": cbs_year,
                "hometown": hometown,
                "phone_number": phone_number,
                "instagram_handle": instagram_handle,
                "photo_urls": json.dumps(photo_urls),
                "gender_identity": gender_identity,
                "seeking_genders": json.dumps(seeking_genders),
            },
        )
        db.execute(
            text(
                """
                UPDATE user_account
                SET display_name = :display_name,
                    cbs_year = :cbs_year,
                    hometown = :hometown,
                    phone_number = :phone_number,
                    instagram_handle = :instagram_handle,
                    photo_urls = CAST(:photo_urls AS jsonb),
                    gender_identity = :gender_identity,
                    seeking_genders = CAST(:seeking_genders AS jsonb)
                WHERE id = CAST(:user_id AS uuid)
                """
            ),
            {
                "user_id": user_id,
                "display_name": display_name,
                "cbs_year": cbs_year,
                "hometown": hometown,
                "phone_number": phone_number,
                "instagram_handle": instagram_handle,
                "photo_urls": json.dumps(photo_urls),
                "gender_identity": gender_identity,
                "seeking_genders": json.dumps(seeking_genders),
            },
        )

        new_gender = _normalize_gender(gender_identity)
        new_seeking = _normalize_seeking(seeking_genders)
        if prior_gender != new_gender or prior_seeking != new_seeking:
            log_profile_event(
                db,
                user_id=user_id,
                event_type="identity_or_preference_changed",
                payload={
                    "before": {"gender_identity": prior_gender, "seeking_genders": prior_seeking},
                    "after": {"gender_identity": new_gender, "seeking_genders": new_seeking},
                },
            )

        db.commit()
    return get_user_public_profile(user_id) or {
        "id": user_id,
        "display_name": display_name,
        "cbs_year": cbs_year,
        "hometown": hometown,
        "photo_urls": photo_urls,
        "gender_identity": gender_identity,
        "seeking_genders": seeking_genders,
    }


def update_user_profile(
    user_id: str,
    display_name: str | None,
    cbs_year: str | None,
    hometown: str | None,
    phone_number: str | None,
    instagram_handle: str | None,
    photo_urls: list[str],
    gender_identity: str | None,
    seeking_genders: list[str],
) -> dict[str, Any] | None:
    safe_display_name = display_name or ""
    if not safe_display_name:
        existing = get_user_by_id(user_id)
        if not existing:
            return None
        safe_display_name = str(existing.get("display_name") or existing.get("email") or "").split("@")[0]
    return upsert_user_profile(
        user_id=user_id,
        display_name=safe_display_name,
        cbs_year=cbs_year,
        hometown=hometown,
        phone_number=phone_number,
        instagram_handle=instagram_handle,
        photo_urls=photo_urls,
        gender_identity=gender_identity,
        seeking_genders=seeking_genders,
    )


def list_match_history(user_id: str, limit: int = 20, tenant_id: str | None = None) -> list[dict[str, Any]]:
    with SessionLocal() as db:
        rows = db.execute(
            text(
                """
                SELECT
                  wma.week_start_date,
                  wma.status,
                  wma.matched_user_id,
                  wma.score_breakdown,
                  ua.email AS matched_email,
                  COALESCE(up.phone_number, ua.phone_number) AS matched_phone_number,
                  COALESCE(up.instagram_handle, ua.instagram_handle) AS matched_instagram_handle,
                  COALESCE(up.display_name, ua.display_name, SPLIT_PART(ua.email, '@', 1)) AS matched_display_name,
                  COALESCE(up.photo_urls, ua.photo_urls, '[]'::jsonb) AS matched_photo_urls,
                  ev.last_event_at,
                  ev.accepted_at,
                  COALESCE(up.cbs_year, ua.cbs_year) AS matched_cbs_year,
                  COALESCE(up.hometown, ua.hometown) AS matched_hometown
                FROM weekly_match_assignment wma
                LEFT JOIN user_account ua ON ua.id = wma.matched_user_id
                LEFT JOIN user_profile up ON up.user_id = ua.id
                LEFT JOIN LATERAL (
                  SELECT
                    MAX(me.created_at) AS last_event_at,
                    MAX(CASE WHEN me.event_type = 'accept' THEN me.created_at ELSE NULL END) AS accepted_at
                  FROM match_event me
                  WHERE me.user_id = wma.user_id
                    AND me.week_start_date = wma.week_start_date
                ) ev ON TRUE
                WHERE wma.user_id = CAST(:user_id AS uuid)
                  AND (:tenant_id IS NULL OR wma.tenant_id = CAST(:tenant_id AS uuid))
                ORDER BY wma.week_start_date DESC
                LIMIT :limit
                """
            ),
            {"user_id": user_id, "tenant_id": tenant_id, "limit": max(1, min(100, int(limit)))},
        ).mappings().all()
    return [dict(r) for r in rows]


def create_support_feedback(user_id: str, message: str) -> dict[str, Any]:
    feedback_id = str(uuid.uuid4())
    with SessionLocal() as db:
        db.execute(
            text(
                """
                INSERT INTO support_feedback (id, user_id, message)
                VALUES (CAST(:id AS uuid), CAST(:user_id AS uuid), :message)
                """
            ),
            {"id": feedback_id, "user_id": user_id, "message": message},
        )
        db.commit()
    return {"id": feedback_id, "user_id": user_id, "message": message}


def update_user_password(user_id: str, password_hash: str) -> None:
    with SessionLocal() as db:
        db.execute(
            text(
                """
                UPDATE user_account
                SET password_hash = :password_hash
                WHERE id = CAST(:user_id AS uuid)
                """
            ),
            {"user_id": user_id, "password_hash": password_hash},
        )
        db.commit()


def disable_user_admin(user_id: str) -> dict[str, Any] | None:
    with SessionLocal() as db:
        row = db.execute(
            text(
                """
                UPDATE user_account
                SET disabled_at = NOW()
                WHERE id = CAST(:user_id AS uuid)
                RETURNING id, email, username, disabled_at
                """
            ),
            {"user_id": user_id},
        ).mappings().first()
        db.execute(
            text(
                """
                INSERT INTO user_preferences (user_id, pause_matches, updated_at)
                VALUES (CAST(:user_id AS uuid), TRUE, NOW())
                ON CONFLICT (user_id)
                DO UPDATE SET pause_matches = TRUE, updated_at = NOW()
                """
            ),
            {"user_id": user_id},
        )
        db.commit()
    return dict(row) if row else None


def anonymize_and_disable_user(user_id: str) -> None:
    anon_email = f"deleted+{uuid.uuid4().hex}@deleted.local"
    replacement_hash = uuid.uuid4().hex
    with SessionLocal() as db:
        db.execute(
            text(
                """
                UPDATE user_account
                SET email = :anon_email,
                    username = NULL,
                    display_name = 'Deleted user',
                    hometown = NULL,
                    cbs_year = NULL,
                    photo_urls = '[]'::jsonb,
                    gender_identity = NULL,
                    seeking_genders = '[]'::jsonb,
                    password_hash = :password_hash,
                    is_email_verified = FALSE,
                    disabled_at = NOW()
                WHERE id = CAST(:user_id AS uuid)
                """
            ),
            {"user_id": user_id, "anon_email": anon_email, "password_hash": str(replacement_hash)},
        )

        db.execute(
            text(
                """
                UPDATE weekly_match_assignment
                SET matched_user_id = NULL,
                    score_total = NULL,
                    status = 'no_match',
                    score_breakdown = CAST(:score_breakdown AS jsonb)
                WHERE matched_user_id = CAST(:user_id AS uuid)
                """
            ),
            {
                "user_id": user_id,
                "score_breakdown": json.dumps({"reason": "counterpart_account_deleted"}),
            },
        )

        db.execute(
            text(
                """
                DELETE FROM weekly_match_assignment
                WHERE user_id = CAST(:user_id AS uuid)
                """
            ),
            {"user_id": user_id},
        )

        db.commit()


def is_username_available(username: str, exclude_user_id: str | None = None, tenant_id: str | None = None) -> bool:
    with SessionLocal() as db:
        row = db.execute(
            text(
                """
                SELECT id
                FROM user_account
                WHERE LOWER(username)=LOWER(:username)
                  AND (:tenant_id IS NULL OR tenant_id = CAST(:tenant_id AS uuid))
                """
            ),
            {"username": username, "tenant_id": tenant_id},
        ).mappings().first()
    if not row:
        return True
    if exclude_user_id and str(row["id"]) == str(exclude_user_id):
        return True
    return False


def update_username(user_id: str, username: str | None) -> dict[str, Any] | None:
    with SessionLocal() as db:
        db.execute(
            text(
                """
                UPDATE user_account
                SET username=:username
                WHERE id=CAST(:id AS uuid)
                """
            ),
            {"id": user_id, "username": username},
        )
        db.commit()
    return get_user_by_id(user_id)


def get_user_chat_threads(user_id: str, tenant_id: str | None = None) -> list[dict[str, Any]]:
    with SessionLocal() as db:
        rows = db.execute(
            text(
                """
                SELECT
                  t.id,
                  t.week_start_date,
                  t.created_at,
                  t.participant_a_id,
                  t.participant_b_id,
                  CASE
                    WHEN t.participant_a_id = CAST(:user_id AS uuid) THEN t.participant_b_id
                    ELSE t.participant_a_id
                  END AS other_user_id,
                  u.display_name AS other_display_name,
                  u.email AS other_email,
                  u.cbs_year AS other_cbs_year,
                  u.hometown AS other_hometown,
                  COALESCE(u.photo_urls, '[]'::jsonb) AS other_photo_urls,
                  lm.body AS latest_message_body,
                  lm.created_at AS latest_message_at
                FROM chat_thread t
                JOIN user_account u
                  ON u.id = (
                    CASE
                      WHEN t.participant_a_id = CAST(:user_id AS uuid) THEN t.participant_b_id
                      ELSE t.participant_a_id
                    END
                  )
                LEFT JOIN LATERAL (
                  SELECT m.body, m.created_at
                  FROM chat_message m
                  WHERE m.thread_id = t.id
                  ORDER BY m.created_at DESC
                  LIMIT 1
                ) lm ON TRUE
                WHERE (:tenant_id IS NULL OR t.tenant_id = CAST(:tenant_id AS uuid))
                  AND (
                    t.participant_a_id = CAST(:user_id AS uuid)
                   OR t.participant_b_id = CAST(:user_id AS uuid)
                  )
                ORDER BY COALESCE(lm.created_at, t.created_at) DESC
                """
            ),
            {"user_id": user_id, "tenant_id": tenant_id},
        ).mappings().all()
    return [dict(r) for r in rows]


def get_thread_by_id(thread_id: str, tenant_id: str | None = None) -> dict[str, Any] | None:
    with SessionLocal() as db:
        row = db.execute(
            text(
                """
                SELECT *
                FROM chat_thread
                WHERE id=CAST(:id AS uuid)
                  AND (:tenant_id IS NULL OR tenant_id = CAST(:tenant_id AS uuid))
                """
            ),
            {"id": thread_id, "tenant_id": tenant_id},
        ).mappings().first()
    return dict(row) if row else None


def get_thread_messages(thread_id: str, tenant_id: str | None = None) -> list[dict[str, Any]]:
    with SessionLocal() as db:
        rows = db.execute(
            text(
                """
                SELECT id, thread_id, sender_user_id, body, created_at
                FROM chat_message
                WHERE thread_id=CAST(:thread_id AS uuid)
                  AND (:tenant_id IS NULL OR tenant_id = CAST(:tenant_id AS uuid))
                ORDER BY created_at ASC
                """
            ),
            {"thread_id": thread_id, "tenant_id": tenant_id},
        ).mappings().all()
    return [dict(r) for r in rows]


def create_chat_message(thread_id: str, sender_user_id: str, body: str, tenant_id: str | None = None) -> dict[str, Any]:
    message_id = str(uuid.uuid4())
    with SessionLocal() as db:
        db.execute(
            text(
                """
                INSERT INTO chat_message (id, thread_id, sender_user_id, body, tenant_id)
                VALUES (:id, CAST(:thread_id AS uuid), CAST(:sender_user_id AS uuid), :body, CAST(NULLIF(:tenant_id, '') AS uuid))
                """
            ),
            {
                "id": message_id,
                "thread_id": thread_id,
                "sender_user_id": sender_user_id,
                "body": body,
                "tenant_id": tenant_id or "",
            },
        )
        db.commit()
    with SessionLocal() as db:
        row = db.execute(
            text(
                """
                SELECT id, thread_id, sender_user_id, body, created_at
                FROM chat_message
                WHERE id=CAST(:id AS uuid)
                  AND (:tenant_id IS NULL OR tenant_id = CAST(:tenant_id AS uuid))
                """
            ),
            {"id": message_id, "tenant_id": tenant_id},
        ).mappings().first()
    return dict(row) if row else {"id": message_id, "thread_id": thread_id, "sender_user_id": sender_user_id, "body": body}


def ensure_chat_thread(week_start_date: Any, user_a_id: str, user_b_id: str, tenant_id: str | None = None) -> dict[str, Any]:
    a, b = sorted([user_a_id, user_b_id])
    with SessionLocal() as db:
        existing = db.execute(
            text(
                """
                SELECT *
                FROM chat_thread
                WHERE week_start_date=:week_start_date
                  AND (:tenant_id IS NULL OR tenant_id = CAST(:tenant_id AS uuid))
                  AND participant_a_id=CAST(:a AS uuid)
                  AND participant_b_id=CAST(:b AS uuid)
                """
            ),
            {"week_start_date": week_start_date, "a": a, "b": b, "tenant_id": tenant_id},
        ).mappings().first()
        if existing:
            return dict(existing)

        thread_id = str(uuid.uuid4())
        db.execute(
            text(
                """
                INSERT INTO chat_thread (id, week_start_date, participant_a_id, participant_b_id, tenant_id)
                VALUES (:id, :week_start_date, CAST(:a AS uuid), CAST(:b AS uuid), CAST(NULLIF(:tenant_id, '') AS uuid))
                """
            ),
            {"id": thread_id, "week_start_date": week_start_date, "a": a, "b": b, "tenant_id": tenant_id or ""},
        )
        db.commit()

    row = get_thread_by_id(thread_id, tenant_id=tenant_id)
    return row or {
        "id": thread_id,
        "week_start_date": week_start_date,
        "participant_a_id": a,
        "participant_b_id": b,
    }


def create_email_verification_token(user_id: str, token: str, expires_at: datetime, code_hash: str | None = None) -> dict[str, Any]:
    token_id = str(uuid.uuid4())
    with SessionLocal() as db:
        db.execute(
            text(
                """
                INSERT INTO email_verification_token (id, user_id, token, code_hash, expires_at)
                VALUES (:id, CAST(:user_id AS uuid), :token, :code_hash, :expires_at)
                """
            ),
            {"id": token_id, "user_id": user_id, "token": token, "code_hash": code_hash, "expires_at": expires_at},
        )
        db.commit()
    return {"id": token_id, "token": token, "expires_at": expires_at.isoformat()}


def get_verification_token(token: str) -> dict[str, Any] | None:
    with SessionLocal() as db:
        row = db.execute(text("SELECT * FROM email_verification_token WHERE token=:token"), {"token": token}).mappings().first()
    return dict(row) if row else None


def get_latest_active_verification_for_user(user_id: str) -> dict[str, Any] | None:
    with SessionLocal() as db:
        row = db.execute(
            text(
                """
                SELECT *
                FROM email_verification_token
                WHERE user_id=CAST(:user_id AS uuid)
                  AND used_at IS NULL
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {"user_id": user_id},
        ).mappings().first()
    return dict(row) if row else None


def invalidate_active_verification_tokens(user_id: str) -> None:
    with SessionLocal() as db:
        db.execute(
            text(
                """
                UPDATE email_verification_token
                SET used_at=NOW()
                WHERE user_id=CAST(:user_id AS uuid)
                  AND used_at IS NULL
                """
            ),
            {"user_id": user_id},
        )
        db.commit()


def increment_verification_failed_attempts(token_id: str) -> None:
    with SessionLocal() as db:
        db.execute(
            text(
                """
                UPDATE email_verification_token
                SET failed_attempts = COALESCE(failed_attempts, 0) + 1
                WHERE id=CAST(:id AS uuid)
                """
            ),
            {"id": token_id},
        )
        db.commit()


def mark_token_used(token_id: str) -> None:
    with SessionLocal() as db:
        db.execute(text("UPDATE email_verification_token SET used_at=NOW() WHERE id=CAST(:id AS uuid)"), {"id": token_id})
        db.commit()


def set_user_verified(user_id: str) -> None:
    with SessionLocal() as db:
        db.execute(text("UPDATE user_account SET is_email_verified=true WHERE id=CAST(:id AS uuid)"), {"id": user_id})
        db.commit()


def create_refresh_token_row(user_id: str, token_hash: str, expires_at: datetime) -> dict[str, Any]:
    rt_id = str(uuid.uuid4())
    with SessionLocal() as db:
        db.execute(
            text(
                """
                INSERT INTO refresh_token (id, user_id, token_hash, expires_at)
                VALUES (:id, CAST(:user_id AS uuid), :token_hash, :expires_at)
                """
            ),
            {"id": rt_id, "user_id": user_id, "token_hash": token_hash, "expires_at": expires_at},
        )
        db.commit()
    return {"id": rt_id, "user_id": user_id, "token_hash": token_hash}


def upsert_user_vibe_card(
    *,
    user_id: str,
    tenant_id: str | None,
    survey_slug: str,
    survey_version: int,
    vibe_json: dict[str, Any],
) -> dict[str, Any]:
    with SessionLocal() as db:
        row = db.execute(
            text(
                """
                INSERT INTO user_vibe_card (id, user_id, tenant_id, survey_slug, survey_version, vibe_json)
                VALUES (
                  CAST(:id AS uuid),
                  CAST(:user_id AS uuid),
                  CAST(NULLIF(:tenant_id, '') AS uuid),
                  :survey_slug,
                  :survey_version,
                  CAST(:vibe_json AS jsonb)
                )
                ON CONFLICT (user_id, survey_slug, survey_version)
                DO UPDATE SET
                  tenant_id = EXCLUDED.tenant_id,
                  vibe_json = EXCLUDED.vibe_json,
                  created_at = NOW()
                RETURNING id, user_id, tenant_id, survey_slug, survey_version, vibe_json, created_at
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "tenant_id": tenant_id or "",
                "survey_slug": survey_slug,
                "survey_version": survey_version,
                "vibe_json": json.dumps(vibe_json),
            },
        ).mappings().first()
        db.commit()
    return dict(row) if row else {
        "user_id": user_id,
        "tenant_id": tenant_id,
        "survey_slug": survey_slug,
        "survey_version": survey_version,
        "vibe_json": vibe_json,
    }


def get_latest_user_vibe_card(user_id: str, survey_slug: str | None = None, survey_version: int | None = None) -> dict[str, Any] | None:
    sql = """
      SELECT id, user_id, tenant_id, survey_slug, survey_version, vibe_json, created_at
      FROM user_vibe_card
      WHERE user_id = CAST(:user_id AS uuid)
    """
    params: dict[str, Any] = {"user_id": user_id}
    if survey_slug:
        sql += " AND survey_slug = :survey_slug"
        params["survey_slug"] = survey_slug
    if survey_version is not None:
        sql += " AND survey_version = :survey_version"
        params["survey_version"] = survey_version
    sql += " ORDER BY created_at DESC LIMIT 1"

    with SessionLocal() as db:
        row = db.execute(text(sql), params).mappings().first()
    return dict(row) if row else None


def save_user_vibe_card_snapshot(
    *,
    user_id: str,
    tenant_id: str | None,
    survey_slug: str,
    survey_version: int,
    vibe_version: str,
    vibe_json: dict[str, Any],
) -> dict[str, Any]:
    with SessionLocal() as db:
        row = db.execute(
            text(
                """
                INSERT INTO vibe_card_snapshots (id, user_id, tenant_id, survey_slug, survey_version, vibe_version, payload_json)
                VALUES (
                  CAST(:id AS uuid),
                  CAST(:user_id AS uuid),
                  CAST(NULLIF(:tenant_id, '') AS uuid),
                  :survey_slug,
                  :survey_version,
                  :vibe_version,
                  CAST(:payload_json AS jsonb)
                )
                ON CONFLICT (tenant_id, user_id, survey_slug, survey_version, vibe_version)
                DO UPDATE SET
                  payload_json = EXCLUDED.payload_json,
                  created_at = NOW()
                RETURNING id, user_id, tenant_id, survey_slug, survey_version, vibe_version, payload_json, created_at
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "tenant_id": tenant_id or "",
                "survey_slug": survey_slug,
                "survey_version": survey_version,
                "vibe_version": vibe_version,
                "payload_json": json.dumps(vibe_json),
            },
        ).mappings().first()
        db.commit()
    return dict(row) if row else {
        "user_id": user_id,
        "tenant_id": tenant_id,
        "survey_slug": survey_slug,
        "survey_version": survey_version,
        "vibe_version": vibe_version,
        "payload_json": vibe_json,
    }


def get_saved_user_vibe_card(user_id: str, survey_slug: str | None = None, survey_version: int | None = None) -> dict[str, Any] | None:
    sql = """
      SELECT id, user_id, tenant_id, survey_slug, survey_version, vibe_version, payload_json, created_at
      FROM vibe_card_snapshots
      WHERE user_id = CAST(:user_id AS uuid)
    """
    params: dict[str, Any] = {"user_id": user_id}
    if survey_slug:
        sql += " AND survey_slug = :survey_slug"
        params["survey_slug"] = survey_slug
    if survey_version is not None:
        sql += " AND survey_version = :survey_version"
        params["survey_version"] = survey_version
    sql += " ORDER BY created_at DESC LIMIT 1"

    with SessionLocal() as db:
        row = db.execute(text(sql), params).mappings().first()
    return dict(row) if row else None


def list_vibe_card_samples(*, tenant_id: str | None, limit: int = 10) -> list[dict[str, Any]]:
    with SessionLocal() as db:
        rows = db.execute(
            text(
                """
                SELECT user_id, survey_slug, survey_version, vibe_version, payload_json, created_at
                FROM vibe_card_snapshots
                WHERE (:tenant_id IS NULL OR tenant_id = CAST(:tenant_id AS uuid))
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            {"tenant_id": tenant_id, "limit": max(1, min(100, int(limit)))},
        ).mappings().all()
    return [
        {
            "user_id": str(r.get("user_id")),
            "survey_slug": r.get("survey_slug"),
            "survey_version": r.get("survey_version"),
            "vibe_version": r.get("vibe_version"),
            "vibe_card": r.get("payload_json") if isinstance(r.get("payload_json"), dict) else {},
            "created_at": r.get("created_at"),
        }
        for r in rows
    ]


def enqueue_outbox_notification(
    *,
    tenant_id: str | None,
    user_id: str,
    notification_type: str,
    payload: dict[str, Any],
    scheduled_for: datetime,
    idempotency_key: str,
) -> dict[str, Any]:
    with SessionLocal() as db:
        row = db.execute(
            text(
                """
                INSERT INTO notifications_outbox (
                  id,
                  tenant_id,
                  user_id,
                  notification_type,
                  payload_json,
                  status,
                  scheduled_for,
                  idempotency_key,
                  created_at,
                  updated_at
                )
                VALUES (
                  CAST(:id AS uuid),
                  CAST(NULLIF(:tenant_id, '') AS uuid),
                  CAST(:user_id AS uuid),
                  :notification_type,
                  CAST(:payload_json AS jsonb),
                  'pending',
                  :scheduled_for,
                  :idempotency_key,
                  NOW(),
                  NOW()
                )
                ON CONFLICT (idempotency_key)
                DO UPDATE SET
                  payload_json = EXCLUDED.payload_json,
                  scheduled_for = LEAST(notifications_outbox.scheduled_for, EXCLUDED.scheduled_for),
                  updated_at = NOW()
                RETURNING id, tenant_id, user_id, notification_type, payload_json, status, scheduled_for, attempt_count, idempotency_key, created_at, updated_at
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "tenant_id": tenant_id or "",
                "user_id": user_id,
                "notification_type": notification_type,
                "payload_json": json.dumps(payload or {}),
                "scheduled_for": scheduled_for,
                "idempotency_key": idempotency_key,
            },
        ).mappings().first()
        db.commit()
    return dict(row) if row else {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "notification_type": notification_type,
        "payload_json": payload,
        "status": "pending",
        "scheduled_for": scheduled_for,
        "idempotency_key": idempotency_key,
    }


def list_notifications_outbox(
    *,
    status: str = "pending",
    tenant_id: str | None = None,
    notification_type: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    offset: int = 0,
    limit: int = 100,
) -> tuple[list[dict[str, Any]], int]:
    safe_limit = max(1, min(500, int(limit)))
    safe_offset = max(0, int(offset))
    status_filter = (status or "").strip().lower()
    type_filter = (notification_type or "").strip().lower()

    with SessionLocal() as db:
        rows = db.execute(
            text(
                """
                SELECT id, tenant_id, user_id, notification_type, payload_json, status,
                       scheduled_for, attempt_count, last_error, idempotency_key, created_at, updated_at
                FROM notifications_outbox
                WHERE (:status = '' OR status = :status)
                  AND (:tenant_id IS NULL OR tenant_id = CAST(:tenant_id AS uuid))
                  AND (:notification_type = '' OR notification_type = :notification_type)
                  AND (:date_from IS NULL OR created_at >= CAST(:date_from AS timestamptz))
                  AND (:date_to IS NULL OR created_at < CAST(:date_to AS timestamptz) + INTERVAL '1 day')
                ORDER BY scheduled_for ASC, created_at ASC
                OFFSET :offset
                LIMIT :limit
                """
            ),
            {
                "status": status_filter,
                "tenant_id": tenant_id,
                "notification_type": type_filter,
                "date_from": date_from,
                "date_to": date_to,
                "offset": safe_offset,
                "limit": safe_limit,
            },
        ).mappings().all()

        total = db.execute(
            text(
                """
                SELECT COUNT(1)
                FROM notifications_outbox
                WHERE (:status = '' OR status = :status)
                  AND (:tenant_id IS NULL OR tenant_id = CAST(:tenant_id AS uuid))
                  AND (:notification_type = '' OR notification_type = :notification_type)
                  AND (:date_from IS NULL OR created_at >= CAST(:date_from AS timestamptz))
                  AND (:date_to IS NULL OR created_at < CAST(:date_to AS timestamptz) + INTERVAL '1 day')
                """
            ),
            {
                "status": status_filter,
                "tenant_id": tenant_id,
                "notification_type": type_filter,
                "date_from": date_from,
                "date_to": date_to,
            },
        ).scalar() or 0
    return [dict(r) for r in rows], int(total)


def process_notifications_outbox(*, limit: int = 100, tenant_id: str | None = None) -> dict[str, Any]:
    processed = 0
    sent = 0
    failed = 0
    with SessionLocal() as db:
        rows = db.execute(
            text(
                """
                SELECT id, tenant_id, user_id, notification_type, payload_json, attempt_count
                FROM notifications_outbox
                WHERE status = 'pending'
                  AND scheduled_for <= NOW()
                  AND (:tenant_id IS NULL OR tenant_id = CAST(:tenant_id AS uuid))
                ORDER BY scheduled_for ASC, created_at ASC
                LIMIT :limit
                """
            ),
            {"limit": max(1, min(500, int(limit))), "tenant_id": tenant_id},
        ).mappings().all()

        for row in rows:
            processed += 1
            try:
                db.execute(
                    text(
                        """
                        INSERT INTO notifications_in_app (
                          id, tenant_id, user_id, notification_type, payload_json, created_at
                        ) VALUES (
                          CAST(:id AS uuid),
                          CAST(NULLIF(:tenant_id, '') AS uuid),
                          CAST(:user_id AS uuid),
                          :notification_type,
                          CAST(:payload_json AS jsonb),
                          NOW()
                        )
                        """
                    ),
                    {
                        "id": str(uuid.uuid4()),
                        "tenant_id": str(row.get("tenant_id") or ""),
                        "user_id": str(row.get("user_id")),
                        "notification_type": str(row.get("notification_type") or "generic"),
                        "payload_json": json.dumps(row.get("payload_json") if isinstance(row.get("payload_json"), dict) else {}),
                    },
                )
                db.execute(
                    text(
                        """
                        UPDATE notifications_outbox
                        SET status='sent',
                            updated_at=NOW(),
                            attempt_count = attempt_count + 1,
                            last_error = NULL
                        WHERE id=CAST(:id AS uuid)
                        """
                    ),
                    {"id": str(row.get("id"))},
                )
                sent += 1
            except Exception as exc:
                db.execute(
                    text(
                        """
                        UPDATE notifications_outbox
                        SET attempt_count = attempt_count + 1,
                            status = CASE WHEN attempt_count + 1 >= 5 THEN 'failed' ELSE 'pending' END,
                            last_error = :last_error,
                            scheduled_for = CASE
                              WHEN attempt_count + 1 >= 5 THEN scheduled_for
                              ELSE NOW() + (
                                CASE
                                  WHEN attempt_count < 1 THEN INTERVAL '2 minutes'
                                  WHEN attempt_count < 2 THEN INTERVAL '5 minutes'
                                  WHEN attempt_count < 3 THEN INTERVAL '15 minutes'
                                  ELSE INTERVAL '30 minutes'
                                END
                              )
                            END,
                            updated_at = NOW()
                        WHERE id=CAST(:id AS uuid)
                        """
                    ),
                    {"id": str(row.get("id")), "last_error": str(exc)[:1000]},
                )
                failed += 1

        db.commit()

    return {
        "processed": processed,
        "sent": sent,
        "failed": failed,
    }


def get_notification_preferences(user_id: str, tenant_id: str | None = None) -> dict[str, Any]:
    with SessionLocal() as db:
        db.execute(
            text(
                """
                INSERT INTO notification_preference (user_id, tenant_id)
                VALUES (CAST(:user_id AS uuid), CAST(NULLIF(:tenant_id, '') AS uuid))
                ON CONFLICT (user_id) DO NOTHING
                """
            ),
            {"user_id": user_id, "tenant_id": tenant_id or ""},
        )
        row = db.execute(
            text(
                """
                SELECT user_id, tenant_id, email_enabled, push_enabled,
                       quiet_hours_start_local, quiet_hours_end_local, timezone, updated_at
                FROM notification_preference
                WHERE user_id = CAST(:user_id AS uuid)
                """
            ),
            {"user_id": user_id},
        ).mappings().first()
        db.commit()
    return dict(row) if row else {
        "user_id": user_id,
        "tenant_id": tenant_id,
        "email_enabled": True,
        "push_enabled": False,
        "quiet_hours_start_local": None,
        "quiet_hours_end_local": None,
        "timezone": "America/New_York",
        "updated_at": None,
    }


def update_notification_preferences(
    *,
    user_id: str,
    tenant_id: str | None,
    email_enabled: bool,
    push_enabled: bool,
    quiet_hours_start_local: str | None,
    quiet_hours_end_local: str | None,
    timezone: str,
) -> dict[str, Any]:
    with SessionLocal() as db:
        db.execute(
            text(
                """
                INSERT INTO notification_preference (
                  user_id, tenant_id, email_enabled, push_enabled,
                  quiet_hours_start_local, quiet_hours_end_local, timezone, updated_at
                )
                VALUES (
                  CAST(:user_id AS uuid),
                  CAST(NULLIF(:tenant_id, '') AS uuid),
                  :email_enabled,
                  :push_enabled,
                  CAST(:quiet_hours_start_local AS time),
                  CAST(:quiet_hours_end_local AS time),
                  :timezone,
                  NOW()
                )
                ON CONFLICT (user_id)
                DO UPDATE SET
                  tenant_id = EXCLUDED.tenant_id,
                  email_enabled = EXCLUDED.email_enabled,
                  push_enabled = EXCLUDED.push_enabled,
                  quiet_hours_start_local = EXCLUDED.quiet_hours_start_local,
                  quiet_hours_end_local = EXCLUDED.quiet_hours_end_local,
                  timezone = EXCLUDED.timezone,
                  updated_at = NOW()
                """
            ),
            {
                "user_id": user_id,
                "tenant_id": tenant_id or "",
                "email_enabled": bool(email_enabled),
                "push_enabled": bool(push_enabled),
                "quiet_hours_start_local": quiet_hours_start_local,
                "quiet_hours_end_local": quiet_hours_end_local,
                "timezone": timezone,
            },
        )
        db.commit()
    return get_notification_preferences(user_id, tenant_id=tenant_id)


def enqueue_notification(
    *,
    user_id: str,
    tenant_id: str | None,
    channel: str,
    template_key: str,
    payload: dict[str, Any],
    idempotency_key: str,
    week_start_date: str | None = None,
    scheduled_for: datetime | None = None,
) -> dict[str, Any]:
    with SessionLocal() as db:
        row = db.execute(
            text(
                """
                INSERT INTO notification_outbox (
                  id, user_id, tenant_id, channel, template_key, payload, idempotency_key,
                  week_start_date, scheduled_for, next_attempt_at
                )
                VALUES (
                  CAST(:id AS uuid),
                  CAST(:user_id AS uuid),
                  CAST(NULLIF(:tenant_id, '') AS uuid),
                  :channel,
                  :template_key,
                  CAST(:payload AS jsonb),
                  :idempotency_key,
                  :week_start_date,
                  COALESCE(:scheduled_for, NOW()),
                  COALESCE(:scheduled_for, NOW())
                )
                ON CONFLICT (idempotency_key)
                DO UPDATE SET
                  payload = EXCLUDED.payload,
                  scheduled_for = LEAST(notification_outbox.scheduled_for, EXCLUDED.scheduled_for),
                  next_attempt_at = LEAST(notification_outbox.next_attempt_at, EXCLUDED.next_attempt_at)
                RETURNING id, user_id, tenant_id, channel, template_key, payload, idempotency_key, week_start_date,
                          scheduled_for, next_attempt_at, attempts, status, created_at
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "tenant_id": tenant_id or "",
                "channel": channel,
                "template_key": template_key,
                "payload": json.dumps(payload),
                "idempotency_key": idempotency_key,
                "week_start_date": week_start_date,
                "scheduled_for": scheduled_for,
            },
        ).mappings().first()
        db.commit()
    return dict(row) if row else {
        "user_id": user_id,
        "tenant_id": tenant_id,
        "channel": channel,
        "template_key": template_key,
        "payload": payload,
        "idempotency_key": idempotency_key,
        "week_start_date": week_start_date,
        "scheduled_for": scheduled_for,
        "status": "queued",
    }


def build_notification_idempotency_key(*, tenant_slug: str, user_id: str, week_start_date: str, template_key: str) -> str:
    return f"{template_key}:{tenant_slug}:{week_start_date}:{user_id}"


def list_failed_notifications(limit: int = 100) -> list[dict[str, Any]]:
    with SessionLocal() as db:
        rows = db.execute(
            text(
                """
                SELECT id, user_id, tenant_id, channel, template_key, payload, idempotency_key,
                       week_start_date, scheduled_for, next_attempt_at, attempts, sent_at, status, last_error, created_at
                FROM notification_outbox
                WHERE status = 'failed'
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            {"limit": max(1, min(500, int(limit)))},
        ).mappings().all()
    return [dict(r) for r in rows]


def list_notifications(
    *,
    status: str,
    limit: int = 100,
    tenant_id: str | None = None,
) -> list[dict[str, Any]]:
    with SessionLocal() as db:
        rows = db.execute(
            text(
                """
                SELECT id, user_id, tenant_id, channel, template_key, payload, idempotency_key,
                       week_start_date, scheduled_for, next_attempt_at, attempts, sent_at, status, last_error, created_at
                FROM notification_outbox
                WHERE status = :status
                  AND (:tenant_id IS NULL OR tenant_id = CAST(:tenant_id AS uuid))
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            {"status": status, "tenant_id": tenant_id, "limit": max(1, min(500, int(limit)))},
        ).mappings().all()
    return [dict(r) for r in rows]


def retry_notification(notification_id: str) -> dict[str, Any] | None:
    with SessionLocal() as db:
        row = db.execute(
            text(
                """
                UPDATE notification_outbox
                SET status = 'queued', last_error = NULL, scheduled_for = NOW(), next_attempt_at = NOW()
                WHERE id = CAST(:id AS uuid)
                RETURNING id, user_id, tenant_id, channel, template_key, payload, idempotency_key,
                          week_start_date, scheduled_for, next_attempt_at, attempts, sent_at, status, last_error, created_at
                """
            ),
            {"id": notification_id},
        ).mappings().first()
        db.commit()
    return dict(row) if row else None


def fetch_due_notifications(limit: int = 100) -> list[dict[str, Any]]:
    with SessionLocal() as db:
        rows = db.execute(
            text(
                """
                SELECT id, user_id, tenant_id, channel, template_key, payload, idempotency_key,
                       week_start_date, scheduled_for, next_attempt_at, attempts, sent_at, status, last_error, created_at
                FROM notification_outbox
                WHERE status IN ('queued', 'pending')
                  AND next_attempt_at <= NOW()
                  AND sent_at IS NULL
                ORDER BY next_attempt_at ASC, created_at ASC
                LIMIT :limit
                """
            ),
            {"limit": max(1, min(500, int(limit)))},
        ).mappings().all()
    return [dict(r) for r in rows]


def mark_notification_sent(notification_id: str) -> dict[str, Any] | None:
    with SessionLocal() as db:
        row = db.execute(
            text(
                """
                UPDATE notification_outbox
                SET status = 'sent', sent_at = NOW(), last_error = NULL
                WHERE id = CAST(:id AS uuid)
                RETURNING id, user_id, tenant_id, channel, template_key, payload, idempotency_key,
                          week_start_date, scheduled_for, next_attempt_at, attempts, sent_at, status, last_error, created_at
                """
            ),
            {"id": notification_id},
        ).mappings().first()
        db.commit()
    return dict(row) if row else None


def mark_notification_failed(notification_id: str, error: str, *, max_attempts: int = 8) -> dict[str, Any] | None:
    with SessionLocal() as db:
        row = db.execute(
            text(
                """
                UPDATE notification_outbox
                SET attempts = attempts + 1,
                    last_error = :error,
                    status = CASE WHEN attempts + 1 >= :max_attempts THEN 'failed' ELSE 'queued' END,
                    next_attempt_at = CASE
                      WHEN attempts + 1 >= :max_attempts THEN NOW()
                      ELSE NOW() + (
                        CASE
                          WHEN attempts < 1 THEN INTERVAL '2 minutes'
                          WHEN attempts < 2 THEN INTERVAL '5 minutes'
                          WHEN attempts < 3 THEN INTERVAL '15 minutes'
                          WHEN attempts < 4 THEN INTERVAL '30 minutes'
                          WHEN attempts < 5 THEN INTERVAL '1 hour'
                          ELSE INTERVAL '3 hours'
                        END
                      )
                    END
                WHERE id = CAST(:id AS uuid)
                RETURNING id, user_id, tenant_id, channel, template_key, payload, idempotency_key,
                          week_start_date, scheduled_for, next_attempt_at, attempts, sent_at, status, last_error, created_at
                """
            ),
            {"id": notification_id, "error": error[:2000], "max_attempts": max(1, int(max_attempts))},
        ).mappings().first()
        db.commit()
    return dict(row) if row else None


def get_refresh_token_row(token_hash: str) -> dict[str, Any] | None:
    with SessionLocal() as db:
        row = db.execute(text("SELECT * FROM refresh_token WHERE token_hash=:token_hash"), {"token_hash": token_hash}).mappings().first()
    return dict(row) if row else None


def revoke_refresh_token_row(token_hash: str) -> None:
    with SessionLocal() as db:
        db.execute(
            text("UPDATE refresh_token SET revoked_at=NOW() WHERE token_hash=:token_hash AND revoked_at IS NULL"),
            {"token_hash": token_hash},
        )
        db.commit()


def rotate_refresh_token(old_token_hash: str, user_id: str, new_token_hash: str, expires_at: datetime) -> None:
    with SessionLocal() as db:
        db.execute(
            text("UPDATE refresh_token SET revoked_at=NOW() WHERE token_hash=:token_hash AND revoked_at IS NULL"),
            {"token_hash": old_token_hash},
        )
        db.execute(
            text(
                """
                INSERT INTO refresh_token (id, user_id, token_hash, expires_at)
                VALUES (:id, CAST(:user_id AS uuid), :token_hash, :expires_at)
                """
            ),
            {"id": str(uuid.uuid4()), "user_id": user_id, "token_hash": new_token_hash, "expires_at": expires_at},
        )
        db.commit()


def update_last_login(user_id: str) -> None:
    with SessionLocal() as db:
        db.execute(text("UPDATE user_account SET last_login_at=:ts WHERE id=CAST(:id AS uuid)"), {"ts": datetime.now(timezone.utc), "id": user_id})
        db.commit()



def create_user_block(user_id: str, blocked_user_id: str, tenant_id: str | None = None) -> bool:
    if str(user_id) == str(blocked_user_id):
        return False
    try:
        with SessionLocal() as db:
            db.execute(
                text(
                    """
                    INSERT INTO user_block (id, user_id, blocked_user_id, tenant_id)
                    VALUES (:id, CAST(:user_id AS uuid), CAST(:blocked_user_id AS uuid), CAST(NULLIF(:tenant_id, '') AS uuid))
                    ON CONFLICT (tenant_id, user_id, blocked_user_id) DO NOTHING
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "user_id": user_id,
                    "blocked_user_id": blocked_user_id,
                    "tenant_id": tenant_id or "",
                },
            )
            db.commit()
        return True
    except Exception:
        return False


def remove_user_block(user_id: str, blocked_user_id: str, tenant_id: str | None = None) -> int:
    with SessionLocal() as db:
        res = db.execute(
            text(
                """
                DELETE FROM user_block
                WHERE user_id=CAST(:user_id AS uuid)
                  AND blocked_user_id=CAST(:blocked_user_id AS uuid)
                  AND (:tenant_id IS NULL OR tenant_id = CAST(:tenant_id AS uuid))
                """
            ),
            {"user_id": user_id, "blocked_user_id": blocked_user_id, "tenant_id": tenant_id},
        )
        db.commit()
        return int(res.rowcount or 0)


def list_user_blocks(user_id: str, tenant_id: str | None = None) -> list[dict[str, Any]]:
    with SessionLocal() as db:
        rows = db.execute(
            text(
                """
                SELECT blocked_user_id, created_at
                FROM user_block
                WHERE user_id=CAST(:user_id AS uuid)
                  AND (:tenant_id IS NULL OR tenant_id = CAST(:tenant_id AS uuid))
                ORDER BY created_at DESC
                """
            ),
            {"user_id": user_id, "tenant_id": tenant_id},
        ).mappings().all()
    return [dict(r) for r in rows]


def is_blocked_pair(user_a: str, user_b: str, tenant_id: str | None = None) -> bool:
    with SessionLocal() as db:
        row = db.execute(
            text(
                """
                SELECT 1
                FROM user_block
                WHERE (:tenant_id IS NULL OR tenant_id = CAST(:tenant_id AS uuid))
                  AND (
                    (user_id=CAST(:a AS uuid) AND blocked_user_id=CAST(:b AS uuid))
                    OR (user_id=CAST(:b AS uuid) AND blocked_user_id=CAST(:a AS uuid))
                  )
                LIMIT 1
                """
            ),
            {"a": user_a, "b": user_b, "tenant_id": tenant_id},
        ).first()
    return bool(row)


def get_block_pairs_for_matching(db, tenant_id: str | None = None) -> set[tuple[str, str]]:
    rows = db.execute(
        text(
            """
            SELECT user_id, blocked_user_id
            FROM user_block
            WHERE (:tenant_id IS NULL OR tenant_id = CAST(:tenant_id AS uuid))
            """
        ),
        {"tenant_id": tenant_id},
    ).mappings().all()
    out: set[tuple[str, str]] = set()
    for r in rows:
        a = str(r["user_id"])
        b = str(r["blocked_user_id"])
        out.add(tuple(sorted((a, b))))
    return out


def create_match_report(
    week_start_date: Any,
    user_id: str,
    matched_user_id: str,
    reason: str,
    details: str | None,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    report_id = str(uuid.uuid4())
    with SessionLocal() as db:
        db.execute(
            text(
                """
                INSERT INTO match_report (id, week_start_date, user_id, matched_user_id, reason, details, tenant_id)
                VALUES (:id, :week_start_date, CAST(:user_id AS uuid), CAST(:matched_user_id AS uuid), :reason, :details, CAST(NULLIF(:tenant_id, '') AS uuid))
                """
            ),
            {
                "id": report_id,
                "week_start_date": week_start_date,
                "user_id": user_id,
                "matched_user_id": matched_user_id,
                "reason": reason,
                "details": details,
                "tenant_id": tenant_id or "",
            },
        )
        db.commit()
    return {
        "id": report_id,
        "week_start_date": str(week_start_date),
        "user_id": user_id,
        "matched_user_id": matched_user_id,
        "reason": reason,
        "details": details,
    }


def list_reports_for_week(week_start_date: Any, tenant_id: str | None = None) -> list[dict[str, Any]]:
    with SessionLocal() as db:
        rows = db.execute(
            text(
                """
                SELECT id, week_start_date, user_id, matched_user_id, reason, details, created_at
                FROM match_report
                WHERE week_start_date=:week_start_date
                  AND (:tenant_id IS NULL OR tenant_id = CAST(:tenant_id AS uuid))
                ORDER BY created_at DESC
                """
            ),
            {"week_start_date": week_start_date, "tenant_id": tenant_id},
        ).mappings().all()
    return [dict(r) for r in rows]


def block_stats(tenant_id: str | None = None) -> dict[str, int]:
    with SessionLocal() as db:
        total = db.execute(
            text("SELECT COUNT(1) FROM user_block WHERE (:tenant_id IS NULL OR tenant_id = CAST(:tenant_id AS uuid))"),
            {"tenant_id": tenant_id},
        ).scalar() or 0
        distinct_users = db.execute(
            text("SELECT COUNT(DISTINCT user_id) FROM user_block WHERE (:tenant_id IS NULL OR tenant_id = CAST(:tenant_id AS uuid))"),
            {"tenant_id": tenant_id},
        ).scalar() or 0
    return {"total_blocks": int(total), "users_with_blocks": int(distinct_users)}


def ensure_bootstrap_admin(email: str, password_hash: str, role: str = "admin") -> dict[str, Any] | None:
    with SessionLocal() as db:
        row = db.execute(
            text(
                """
                INSERT INTO admin_user (id, email, password_hash, role, is_active, created_at, updated_at)
                VALUES (CAST(:id AS uuid), :email, :password_hash, :role, TRUE, NOW(), NOW())
                ON CONFLICT (email)
                DO UPDATE SET
                  password_hash = EXCLUDED.password_hash,
                  role = EXCLUDED.role,
                  is_active = TRUE,
                  updated_at = NOW()
                RETURNING id, email, role, is_active, created_at, updated_at, last_login_at
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "email": str(email or "").strip().lower(),
                "password_hash": password_hash,
                "role": role if role in {"admin", "operator", "viewer"} else "admin",
            },
        ).mappings().first()
        db.commit()
    return dict(row) if row else None


def get_admin_user_by_email(email: str) -> dict[str, Any] | None:
    with SessionLocal() as db:
        row = db.execute(
            text("SELECT id, email, password_hash, role, is_active, created_at, updated_at, last_login_at FROM admin_user WHERE LOWER(email)=LOWER(:email)"),
            {"email": str(email or "").strip().lower()},
        ).mappings().first()
    return dict(row) if row else None


def get_admin_user_by_id(admin_user_id: str) -> dict[str, Any] | None:
    with SessionLocal() as db:
        row = db.execute(
            text("SELECT id, email, password_hash, role, is_active, created_at, updated_at, last_login_at FROM admin_user WHERE id=CAST(:id AS uuid)"),
            {"id": admin_user_id},
        ).mappings().first()
    return dict(row) if row else None


def update_admin_last_login(admin_user_id: str) -> None:
    with SessionLocal() as db:
        db.execute(
            text("UPDATE admin_user SET last_login_at = NOW(), updated_at = NOW() WHERE id = CAST(:id AS uuid)"),
            {"id": admin_user_id},
        )
        db.commit()


def create_admin_session(admin_user_id: str, expires_at: datetime) -> dict[str, Any] | None:
    with SessionLocal() as db:
        row = db.execute(
            text(
                """
                INSERT INTO admin_session (id, admin_user_id, created_at, expires_at)
                VALUES (CAST(:id AS uuid), CAST(:admin_user_id AS uuid), NOW(), :expires_at)
                RETURNING id, admin_user_id, created_at, expires_at, revoked_at
                """
            ),
            {"id": str(uuid.uuid4()), "admin_user_id": admin_user_id, "expires_at": expires_at},
        ).mappings().first()
        db.commit()
    return dict(row) if row else None


def get_admin_session(session_id: str) -> dict[str, Any] | None:
    with SessionLocal() as db:
        row = db.execute(
            text(
                """
                SELECT id, admin_user_id, created_at, expires_at, revoked_at
                FROM admin_session
                WHERE id = CAST(:id AS uuid)
                """
            ),
            {"id": session_id},
        ).mappings().first()
    return dict(row) if row else None


def revoke_admin_session(session_id: str) -> None:
    with SessionLocal() as db:
        db.execute(
            text("UPDATE admin_session SET revoked_at = NOW() WHERE id = CAST(:id AS uuid) AND revoked_at IS NULL"),
            {"id": session_id},
        )
        db.commit()


def create_admin_audit_event(
    *,
    action: str,
    admin_user_id: str | None = None,
    tenant_slug: str | None = None,
    week_start_date: Any | None = None,
    payload_json: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    payload_json = payload_json or {}
    with SessionLocal() as db:
        row = db.execute(
            text(
                """
                INSERT INTO admin_audit_event (id, admin_user_id, action, tenant_slug, week_start_date, payload_json, created_at)
                VALUES (
                  CAST(:id AS uuid),
                  CAST(NULLIF(:admin_user_id, '') AS uuid),
                  :action,
                  :tenant_slug,
                  :week_start_date,
                  CAST(:payload_json AS jsonb),
                  NOW()
                )
                RETURNING id, admin_user_id, action, tenant_slug, week_start_date, payload_json, created_at
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "admin_user_id": admin_user_id or "",
                "action": action,
                "tenant_slug": tenant_slug,
                "week_start_date": week_start_date,
                "payload_json": json.dumps(payload_json),
            },
        ).mappings().first()
        db.commit()
    return dict(row) if row else None


def list_admin_audit_events(limit: int = 50) -> list[dict[str, Any]]:
    with SessionLocal() as db:
        rows = db.execute(
            text(
                """
                SELECT e.id, e.admin_user_id, au.email AS admin_email, e.action, e.tenant_slug,
                       e.week_start_date, e.payload_json, e.created_at
                FROM admin_audit_event e
                LEFT JOIN admin_user au ON au.id = e.admin_user_id
                ORDER BY e.created_at DESC
                LIMIT :limit
                """
            ),
            {"limit": max(1, min(500, int(limit)))},
        ).mappings().all()
    return [dict(r) for r in rows]


def list_admin_users(limit: int = 200) -> list[dict[str, Any]]:
    with SessionLocal() as db:
        rows = db.execute(
            text(
                """
                SELECT id, email, role, is_active, created_at, updated_at, last_login_at
                FROM admin_user
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            {"limit": max(1, min(1000, int(limit)))},
        ).mappings().all()
    return [dict(r) for r in rows]


def list_tenants_admin(*, include_disabled: bool = False) -> list[dict[str, Any]]:
    with SessionLocal() as db:
        rows = db.execute(
            text(
                """
                SELECT id, slug, name, email_domains, theme, timezone, created_at, disabled_at
                FROM tenant
                WHERE (:include_disabled = TRUE OR disabled_at IS NULL)
                ORDER BY created_at ASC
                """
            ),
            {"include_disabled": bool(include_disabled)},
        ).mappings().all()
    return [dict(r) for r in rows]


def upsert_tenant_admin(
    *,
    slug: str,
    name: str,
    email_domains: list[str],
    theme: dict[str, Any],
    timezone_value: str = "America/New_York",
) -> dict[str, Any] | None:
    with SessionLocal() as db:
        row = db.execute(
            text(
                """
                INSERT INTO tenant (id, slug, name, email_domains, theme, timezone)
                VALUES (CAST(:id AS uuid), :slug, :name, CAST(:email_domains AS jsonb), CAST(:theme AS jsonb), :timezone)
                ON CONFLICT (slug)
                DO UPDATE SET
                  name = EXCLUDED.name,
                  email_domains = EXCLUDED.email_domains,
                  theme = EXCLUDED.theme,
                  timezone = EXCLUDED.timezone,
                  disabled_at = NULL
                RETURNING id, slug, name, email_domains, theme, timezone, created_at, disabled_at
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "slug": slug.strip().lower(),
                "name": name,
                "email_domains": json.dumps(email_domains),
                "theme": json.dumps(theme or {}),
                "timezone": timezone_value or "America/New_York",
            },
        ).mappings().first()
        db.commit()
    return dict(row) if row else None


def disable_tenant_admin(slug: str) -> dict[str, Any] | None:
    with SessionLocal() as db:
        row = db.execute(
            text(
                """
                UPDATE tenant
                SET disabled_at = NOW()
                WHERE slug = :slug
                RETURNING id, slug, name, email_domains, theme, timezone, created_at, disabled_at
                """
            ),
            {"slug": slug.strip().lower()},
        ).mappings().first()
        db.commit()
    return dict(row) if row else None


def list_users_admin(
    *,
    tenant_id: str | None = None,
    onboarding_status: str | None = None,
    search: str | None = None,
    eligible_only: bool = False,
    paused_only: bool = False,
    offset: int = 0,
    limit: int = 200,
) -> tuple[list[dict[str, Any]], int]:
    onboarding_filter = (onboarding_status or "").strip().lower()
    search_filter = (search or "").strip().lower()
    safe_limit = max(1, min(1000, int(limit)))
    safe_offset = max(0, int(offset))

    where_parts = ["(:tenant_id IS NULL OR ua.tenant_id = CAST(:tenant_id AS uuid))"]
    if search_filter:
        where_parts.append(
            """
            (
              LOWER(COALESCE(ua.email, '')) LIKE :search
              OR LOWER(COALESCE(ua.username, '')) LIKE :search
              OR LOWER(COALESCE(ua.display_name, '')) LIKE :search
              OR CAST(ua.id AS text) LIKE :search
            )
            """
        )
    if paused_only:
        where_parts.append("COALESCE(pref.pause_matches, FALSE) = TRUE")
    if onboarding_filter == "not_started":
        where_parts.append("sess_current.completed_at IS NULL")
    elif onboarding_filter == "in_progress":
        where_parts.append("sess_current.completed_at IS NOT NULL AND ua.display_name IS NULL")
    elif onboarding_filter == "complete":
        where_parts.append("sess_current.completed_at IS NOT NULL AND ua.display_name IS NOT NULL")
    if eligible_only:
        where_parts.append(
            """
            (
              ua.display_name IS NOT NULL
              AND ua.gender_identity IS NOT NULL
              AND jsonb_array_length(COALESCE(ua.seeking_genders, '[]'::jsonb)) > 0
              AND jsonb_array_length(COALESCE(ua.photo_urls, '[]'::jsonb)) >= 1
              AND sess_current.completed_at IS NOT NULL
              AND ut_current.user_id IS NOT NULL
              AND COALESCE(pref.pause_matches, FALSE) = FALSE
              AND ua.disabled_at IS NULL
            )
            """
        )

    where_sql = " AND ".join(where_parts)

    with SessionLocal() as db:
        rows = db.execute(
            text(
                f"""
                SELECT
                  ua.id,
                  ua.tenant_id,
                  t.slug AS tenant_slug,
                  t.name AS tenant_name,
                  ua.email,
                  ua.username,
                  ua.display_name,
                  ua.cbs_year,
                  ua.hometown,
                  ua.phone_number,
                  ua.instagram_handle,
                  ua.gender_identity,
                  COALESCE(ua.seeking_genders, '[]'::jsonb) AS seeking_genders,
                  COALESCE(ua.photo_urls, '[]'::jsonb) AS photo_urls,
                  COALESCE(pref.pause_matches, FALSE) AS pause_matches,
                  ua.is_email_verified,
                  ua.created_at,
                  ua.last_login_at,
                  ua.disabled_at,
                  (
                    SELECT MAX(week_start_date)
                    FROM weekly_match_assignment w
                    WHERE w.user_id = ua.id
                  ) AS last_match_week,
                  (
                    SELECT COUNT(1)
                    FROM user_block ub
                    WHERE ub.user_id = ua.id OR ub.blocked_user_id = ua.id
                  ) AS blocks_count,
                  (sess_current.completed_at IS NOT NULL) AS has_completed_survey,
                  (ut_current.user_id IS NOT NULL) AS has_traits,
                  :survey_version AS traits_version,
                  (
                    ua.display_name IS NOT NULL
                    AND ua.gender_identity IS NOT NULL
                    AND jsonb_array_length(COALESCE(ua.seeking_genders, '[]'::jsonb)) > 0
                    AND jsonb_array_length(COALESCE(ua.photo_urls, '[]'::jsonb)) >= 1
                    AND sess_current.completed_at IS NOT NULL
                    AND ut_current.user_id IS NOT NULL
                    AND COALESCE(pref.pause_matches, FALSE) = FALSE
                    AND ua.disabled_at IS NULL
                  ) AS is_match_eligible
                FROM user_account ua
                LEFT JOIN tenant t ON t.id = ua.tenant_id
                LEFT JOIN user_preferences pref ON pref.user_id = ua.id
                LEFT JOIN LATERAL (
                  SELECT completed_at
                  FROM survey_session ss
                  WHERE CAST(ss.user_id AS text) = CAST(ua.id AS text)
                  ORDER BY ss.completed_at DESC NULLS LAST
                  LIMIT 1
                ) sess ON TRUE
                LEFT JOIN LATERAL (
                  SELECT completed_at
                  FROM survey_session ss
                  WHERE CAST(ss.user_id AS text) = CAST(ua.id AS text)
                    AND ss.status = 'completed'
                    AND ss.survey_slug = :survey_slug
                    AND ss.survey_version = :survey_version
                  ORDER BY ss.completed_at DESC NULLS LAST
                  LIMIT 1
                ) sess_current ON TRUE
                LEFT JOIN LATERAL (
                  SELECT user_id
                       ,survey_version
                  FROM user_traits ut
                  WHERE CAST(ut.user_id AS text) = CAST(ua.id AS text)
                  ORDER BY ut.computed_at DESC NULLS LAST
                  LIMIT 1
                ) ut ON TRUE
                LEFT JOIN LATERAL (
                  SELECT user_id
                  FROM user_traits ut
                  WHERE CAST(ut.user_id AS text) = CAST(ua.id AS text)
                    AND ut.survey_slug = :survey_slug
                    AND ut.survey_version = :survey_version
                  ORDER BY ut.computed_at DESC NULLS LAST
                  LIMIT 1
                ) ut_current ON TRUE
                WHERE {where_sql}
                ORDER BY ua.created_at DESC
                OFFSET :offset
                LIMIT :limit
                """
            ),
            {
                "tenant_id": tenant_id,
                "search": f"%{search_filter}%",
                "survey_slug": SURVEY_SLUG,
                "survey_version": SURVEY_VERSION,
                "offset": safe_offset,
                "limit": safe_limit,
            },
        ).mappings().all()

        count_value = db.execute(
            text(
                f"""
                SELECT COUNT(1)
                FROM user_account ua
                LEFT JOIN user_preferences pref ON pref.user_id = ua.id
                LEFT JOIN LATERAL (
                  SELECT completed_at
                  FROM survey_session ss
                  WHERE CAST(ss.user_id AS text) = CAST(ua.id AS text)
                    AND ss.status = 'completed'
                    AND ss.survey_slug = :survey_slug
                    AND ss.survey_version = :survey_version
                  ORDER BY ss.completed_at DESC NULLS LAST
                  LIMIT 1
                ) sess_current ON TRUE
                LEFT JOIN LATERAL (
                  SELECT user_id
                  FROM user_traits ut
                  WHERE CAST(ut.user_id AS text) = CAST(ua.id AS text)
                    AND ut.survey_slug = :survey_slug
                    AND ut.survey_version = :survey_version
                  ORDER BY ut.computed_at DESC NULLS LAST
                  LIMIT 1
                ) ut_current ON TRUE
                WHERE {where_sql}
                """
            ),
            {
                "tenant_id": tenant_id,
                "search": f"%{search_filter}%",
                "survey_slug": SURVEY_SLUG,
                "survey_version": SURVEY_VERSION,
            },
        ).scalar() or 0

    out = []
    for r in rows:
        row = dict(r)
        if row.get("has_completed_survey") and row.get("display_name"):
            row["onboarding_status"] = "complete"
        elif row.get("has_completed_survey"):
            row["onboarding_status"] = "in_progress"
        else:
            row["onboarding_status"] = "not_started"
        out.append(row)
    return out, int(count_value)


def update_user_pause_matches_admin(user_id: str, pause_matches: bool) -> dict[str, Any]:
    return update_user_preferences(user_id, pause_matches=pause_matches)


def reset_user_onboarding_state_admin(user_id: str) -> dict[str, Any]:
    with SessionLocal() as db:
        db.execute(
            text(
                """
                DELETE FROM survey_answer
                WHERE session_id IN (SELECT id FROM survey_session WHERE user_id=CAST(:user_id AS uuid))
                """
            ),
            {"user_id": user_id},
        )
        db.execute(text("DELETE FROM survey_session WHERE user_id=CAST(:user_id AS uuid)"), {"user_id": user_id})
        db.execute(text("DELETE FROM user_traits WHERE user_id=CAST(:user_id AS uuid)"), {"user_id": user_id})
        db.commit()
    return {"user_id": user_id, "onboarding_reset": True}


def list_match_reports_admin(
    *,
    tenant_id: str | None = None,
    week_start_date: Any | None = None,
    status: str = "",
    reason: str | None = None,
    reporter_user_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    offset: int = 0,
    limit: int = 200,
) -> tuple[list[dict[str, Any]], int]:
    safe_limit = max(1, min(1000, int(limit)))
    safe_offset = max(0, int(offset))
    reason_filter = (reason or "").strip().lower()
    status_filter = (status or "").strip().lower()

    with SessionLocal() as db:
        rows = db.execute(
            text(
                """
                SELECT
                  mr.id,
                  mr.tenant_id,
                  t.slug AS tenant_slug,
                  mr.week_start_date,
                  mr.user_id,
                  u1.email AS user_email,
                  mr.matched_user_id,
                  u2.email AS matched_user_email,
                  mr.reason,
                  mr.details,
                  mr.status,
                  mr.resolution_notes,
                  mr.resolved_at,
                  mr.resolved_by_admin_id,
                  au.email AS resolved_by_admin_email,
                  mr.created_at
                FROM match_report mr
                LEFT JOIN tenant t ON t.id = mr.tenant_id
                LEFT JOIN user_account u1 ON u1.id = mr.user_id
                LEFT JOIN user_account u2 ON u2.id = mr.matched_user_id
                LEFT JOIN admin_user au ON au.id = mr.resolved_by_admin_id
                WHERE (:tenant_id IS NULL OR mr.tenant_id = CAST(:tenant_id AS uuid))
                  AND (:week_start_date IS NULL OR mr.week_start_date = :week_start_date)
                  AND (:status = '' OR mr.status = :status)
                  AND (:reason = '' OR LOWER(COALESCE(mr.reason, '')) = :reason)
                  AND (:reporter_user_id IS NULL OR mr.user_id = CAST(:reporter_user_id AS uuid))
                  AND (:date_from IS NULL OR mr.created_at >= CAST(:date_from AS timestamptz))
                  AND (:date_to IS NULL OR mr.created_at < CAST(:date_to AS timestamptz) + INTERVAL '1 day')
                ORDER BY mr.created_at DESC
                OFFSET :offset
                LIMIT :limit
                """
            ),
            {
                "tenant_id": tenant_id,
                "week_start_date": week_start_date,
                "status": status_filter,
                "reason": reason_filter,
                "reporter_user_id": reporter_user_id,
                "date_from": date_from,
                "date_to": date_to,
                "offset": safe_offset,
                "limit": safe_limit,
            },
        ).mappings().all()

        total = db.execute(
            text(
                """
                SELECT COUNT(1)
                FROM match_report mr
                WHERE (:tenant_id IS NULL OR mr.tenant_id = CAST(:tenant_id AS uuid))
                  AND (:week_start_date IS NULL OR mr.week_start_date = :week_start_date)
                  AND (:status = '' OR mr.status = :status)
                  AND (:reason = '' OR LOWER(COALESCE(mr.reason, '')) = :reason)
                  AND (:reporter_user_id IS NULL OR mr.user_id = CAST(:reporter_user_id AS uuid))
                  AND (:date_from IS NULL OR mr.created_at >= CAST(:date_from AS timestamptz))
                  AND (:date_to IS NULL OR mr.created_at < CAST(:date_to AS timestamptz) + INTERVAL '1 day')
                """
            ),
            {
                "tenant_id": tenant_id,
                "week_start_date": week_start_date,
                "status": status_filter,
                "reason": reason_filter,
                "reporter_user_id": reporter_user_id,
                "date_from": date_from,
                "date_to": date_to,
            },
        ).scalar() or 0
    return [dict(r) for r in rows], int(total)


def resolve_match_report_admin(
    *,
    report_id: str,
    admin_user_id: str,
    resolution_notes: str | None,
) -> dict[str, Any] | None:
    with SessionLocal() as db:
        row = db.execute(
            text(
                """
                UPDATE match_report
                SET status='resolved',
                    resolution_notes = :resolution_notes,
                    resolved_at = NOW(),
                    resolved_by_admin_id = CAST(:admin_user_id AS uuid)
                WHERE id = CAST(:id AS uuid)
                RETURNING id, week_start_date, user_id, matched_user_id, reason, details, status,
                          resolution_notes, resolved_at, resolved_by_admin_id, created_at, tenant_id
                """
            ),
            {
                "id": report_id,
                "admin_user_id": admin_user_id,
                "resolution_notes": resolution_notes,
            },
        ).mappings().first()
        db.commit()
    return dict(row) if row else None
