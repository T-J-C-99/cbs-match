from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import text

from .database import SessionLocal
from .services.survey_fingerprint import survey_fingerprint


def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    for key in ("id", "created_by_user_id"):
        if key in out and out[key] is not None:
            out[key] = str(out[key])
    return out


def count_definitions() -> int:
    with SessionLocal() as db:
        value = db.execute(text("SELECT COUNT(1) FROM survey_definition")).scalar() or 0
    return int(value)


def get_active_definition(slug: str) -> dict[str, Any] | None:
    with SessionLocal() as db:
        row = db.execute(
            text(
                """
                SELECT id, slug, version, status, is_active, definition_json, definition_hash, fingerprint_created_at, created_at, created_by_user_id
                FROM survey_definition
                WHERE slug=:slug AND is_active=true
                LIMIT 1
                """
            ),
            {"slug": slug},
        ).mappings().first()
    return _normalize_row(row) if row else None


def get_latest_draft(slug: str) -> dict[str, Any] | None:
    with SessionLocal() as db:
        row = db.execute(
            text(
                """
                SELECT id, slug, version, status, is_active, definition_json, definition_hash, fingerprint_created_at, created_at, created_by_user_id
                FROM survey_definition
                WHERE slug=:slug AND status='draft'
                ORDER BY version DESC, created_at DESC
                LIMIT 1
                """
            ),
            {"slug": slug},
        ).mappings().first()
    return _normalize_row(row) if row else None


def list_published_definitions(slug: str) -> list[dict[str, Any]]:
    with SessionLocal() as db:
        rows = db.execute(
            text(
                """
                SELECT id, slug, version, status, is_active, definition_json, definition_hash, fingerprint_created_at, created_at, created_by_user_id
                FROM survey_definition
                WHERE slug=:slug AND status='published'
                ORDER BY version DESC, created_at DESC
                """
            ),
            {"slug": slug},
        ).mappings().all()
    return [_normalize_row(r) for r in rows]


def _insert_change_log(
    db,
    survey_definition_id: str,
    action: str,
    actor_user_id: str | None,
    diff_summary: str,
    diff_json: dict[str, Any] | None = None,
) -> None:
    db.execute(
        text(
            """
            INSERT INTO survey_change_log (id, survey_definition_id, action, actor_user_id, diff_summary, diff_json)
            VALUES (:id, CAST(:survey_definition_id AS uuid), :action, CAST(:actor_user_id AS uuid), :diff_summary, CAST(:diff_json AS jsonb))
            """
        ),
        {
            "id": str(uuid.uuid4()),
            "survey_definition_id": survey_definition_id,
            "action": action,
            "actor_user_id": actor_user_id,
            "diff_summary": diff_summary,
            "diff_json": json.dumps(diff_json) if diff_json is not None else None,
        },
    )


def bootstrap_initial_definition(slug: str, version: int, definition_json: dict[str, Any]) -> dict[str, Any]:
    existing = get_active_definition(slug)
    if existing:
        return existing

    fp = survey_fingerprint(definition_json)
    with SessionLocal() as db:
        new_id = str(uuid.uuid4())
        db.execute(
            text(
                """
                INSERT INTO survey_definition (id, slug, version, status, is_active, definition_json, definition_hash, fingerprint_created_at, created_by_user_id)
                VALUES (:id, :slug, :version, 'published', true, CAST(:definition_json AS jsonb), :definition_hash, NOW(), NULL)
                """
            ),
            {
                "id": new_id,
                "slug": slug,
                "version": version,
                "definition_json": json.dumps(definition_json),
                "definition_hash": str(fp.get("hash") or ""),
            },
        )
        _insert_change_log(
            db,
            survey_definition_id=new_id,
            action="bootstrap",
            actor_user_id=None,
            diff_summary="Bootstrapped initial active survey from questions.json",
        )
        db.commit()

    return get_active_definition(slug) or {}


def create_draft_from_active(slug: str, actor_user_id: str | None) -> dict[str, Any] | None:
    with SessionLocal() as db:
        active = db.execute(
            text(
                """
                SELECT id, version, definition_json
                FROM survey_definition
                WHERE slug=:slug AND is_active=true
                LIMIT 1
                """
            ),
            {"slug": slug},
        ).mappings().first()
        if not active:
            return None

        max_version = db.execute(
            text("SELECT COALESCE(MAX(version), 0) FROM survey_definition WHERE slug=:slug"),
            {"slug": slug},
        ).scalar() or 0
        new_version = int(max_version) + 1
        new_id = str(uuid.uuid4())

        fp = survey_fingerprint(active["definition_json"] if isinstance(active.get("definition_json"), dict) else {})
        db.execute(
            text(
                """
                INSERT INTO survey_definition (id, slug, version, status, is_active, definition_json, definition_hash, fingerprint_created_at, created_by_user_id)
                VALUES (:id, :slug, :version, 'draft', false, CAST(:definition_json AS jsonb), :definition_hash, NOW(), CAST(:created_by_user_id AS uuid))
                """
            ),
            {
                "id": new_id,
                "slug": slug,
                "version": new_version,
                "definition_json": json.dumps(active["definition_json"]),
                "definition_hash": str(fp.get("hash") or ""),
                "created_by_user_id": actor_user_id,
            },
        )
        _insert_change_log(
            db,
            survey_definition_id=new_id,
            action="create_draft_from_active",
            actor_user_id=actor_user_id,
            diff_summary=f"Draft v{new_version} cloned from active v{active['version']}",
        )
        db.commit()

    return get_latest_draft(slug)


def update_latest_draft(slug: str, definition_json: dict[str, Any], actor_user_id: str | None) -> dict[str, Any] | None:
    with SessionLocal() as db:
        fp = survey_fingerprint(definition_json)
        row = db.execute(
            text(
                """
                SELECT id, version
                FROM survey_definition
                WHERE slug=:slug AND status='draft'
                ORDER BY version DESC, created_at DESC
                LIMIT 1
                """
            ),
            {"slug": slug},
        ).mappings().first()
        if not row:
            return None

        db.execute(
            text(
                """
                UPDATE survey_definition
                SET definition_json=CAST(:definition_json AS jsonb),
                    definition_hash = :definition_hash,
                    fingerprint_created_at = NOW()
                WHERE id=CAST(:id AS uuid)
                """
            ),
            {"id": str(row["id"]), "definition_json": json.dumps(definition_json), "definition_hash": str(fp.get("hash") or "")},
        )
        _insert_change_log(
            db,
            survey_definition_id=str(row["id"]),
            action="update_draft",
            actor_user_id=actor_user_id,
            diff_summary=f"Updated draft v{row['version']}",
        )
        db.commit()

    return get_latest_draft(slug)


def publish_latest_draft(slug: str, actor_user_id: str | None) -> dict[str, Any] | None:
    with SessionLocal() as db:
        draft = db.execute(
            text(
                """
                SELECT id, version
                FROM survey_definition
                WHERE slug=:slug AND status='draft'
                ORDER BY version DESC, created_at DESC
                LIMIT 1
                """
            ),
            {"slug": slug},
        ).mappings().first()
        if not draft:
            return None

        db.execute(
            text("UPDATE survey_definition SET is_active=false WHERE slug=:slug AND is_active=true"),
            {"slug": slug},
        )
        db.execute(
            text("UPDATE survey_definition SET status='published', is_active=true WHERE id=CAST(:id AS uuid)"),
            {"id": str(draft["id"])},
        )
        _insert_change_log(
            db,
            survey_definition_id=str(draft["id"]),
            action="publish",
            actor_user_id=actor_user_id,
            diff_summary=f"Published version {draft['version']} as active",
        )
        db.commit()

    return get_active_definition(slug)


def rollback_to_published_version(slug: str, version: int, actor_user_id: str | None) -> dict[str, Any] | None:
    with SessionLocal() as db:
        target = db.execute(
            text(
                """
                SELECT id, version
                FROM survey_definition
                WHERE slug=:slug AND version=:version AND status='published'
                LIMIT 1
                """
            ),
            {"slug": slug, "version": version},
        ).mappings().first()
        if not target:
            return None

        db.execute(
            text("UPDATE survey_definition SET is_active=false WHERE slug=:slug AND is_active=true"),
            {"slug": slug},
        )
        db.execute(
            text("UPDATE survey_definition SET is_active=true WHERE id=CAST(:id AS uuid)"),
            {"id": str(target["id"])},
        )
        _insert_change_log(
            db,
            survey_definition_id=str(target["id"]),
            action="rollback",
            actor_user_id=actor_user_id,
            diff_summary=f"Rolled back active survey to version {target['version']}",
            diff_json={"target_version": version},
        )
        db.commit()

    return get_active_definition(slug)


def initialize_active_from_code(
    slug: str,
    definition_json: dict[str, Any],
    actor_user_id: str | None,
    force: bool = False,
) -> dict[str, Any]:
    """Create/replace active published definition from code in an idempotent way.

    - If active exists and force=False: no-op, returns current active.
    - Otherwise inserts a new published version and activates it atomically.
    """
    current_active = get_active_definition(slug)
    if current_active and not force:
        return {"initialized": False, "active": current_active}

    with SessionLocal() as db:
        fp = survey_fingerprint(definition_json)
        max_version = db.execute(
            text("SELECT COALESCE(MAX(version), 0) FROM survey_definition WHERE slug=:slug"),
            {"slug": slug},
        ).scalar() or 0
        next_version = int(max_version) + 1
        new_id = str(uuid.uuid4())

        db.execute(
            text("UPDATE survey_definition SET is_active=false WHERE slug=:slug AND is_active=true"),
            {"slug": slug},
        )
        db.execute(
            text(
                """
                INSERT INTO survey_definition (id, slug, version, status, is_active, definition_json, definition_hash, fingerprint_created_at, created_by_user_id)
                VALUES (
                  CAST(:id AS uuid),
                  :slug,
                  :version,
                  'published',
                  true,
                  CAST(:definition_json AS jsonb),
                  :definition_hash,
                  NOW(),
                  CAST(:created_by_user_id AS uuid)
                )
                """
            ),
            {
                "id": new_id,
                "slug": slug,
                "version": next_version,
                "definition_json": json.dumps(definition_json),
                "definition_hash": str(fp.get("hash") or ""),
                "created_by_user_id": actor_user_id,
            },
        )
        _insert_change_log(
            db,
            survey_definition_id=new_id,
            action="initialize_from_code",
            actor_user_id=actor_user_id,
            diff_summary=f"Initialized active survey from code as version {next_version}",
            diff_json={"force": bool(force)},
        )
        db.commit()

    return {"initialized": True, "active": get_active_definition(slug)}
