from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text

from ..config import SURVEY_SLUG, SURVEY_VERSION
from ..traits import TRAITS_VERSION, compute_traits
from .explanations import generate_profile_insights
from .survey_fingerprint import build_question_index, survey_fingerprint
from .survey_runtime import get_active_survey_runtime


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _scalar(v: Any) -> Any:
    if isinstance(v, dict) and "value" in v:
        return v.get("value")
    return v


def _ocean_scores_from_traits(traits: dict[str, Any] | None) -> dict[str, int]:
    t = traits or {}
    big5 = t.get("big5") or t.get("big_five") or {}
    emo = t.get("emotional_regulation") or {}
    inferred_n = 1.0 - float(emo.get("stability", 0.5))
    return {
        "openness": round(float(big5.get("openness", 0.5)) * 100),
        "conscientiousness": round(float(big5.get("conscientiousness", 0.5)) * 100),
        "extraversion": round(float(big5.get("extraversion", 0.5)) * 100),
        "agreeableness": round(float(big5.get("agreeableness", 0.5)) * 100),
        "neuroticism": round(float(big5.get("neuroticism", inferred_n)) * 100),
    }


def _definitions_for_slug(db, slug: str) -> list[dict[str, Any]]:
    rows = db.execute(
        text(
            """
            SELECT id, slug, version, status, is_active, definition_json, definition_hash
            FROM survey_definition
            WHERE slug = :slug
            ORDER BY version DESC, created_at DESC
            """
        ),
        {"slug": slug},
    ).mappings().all()
    out: list[dict[str, Any]] = []
    for r in rows:
        item = dict(r)
        definition = item.get("definition_json") if isinstance(item.get("definition_json"), dict) else {}
        fp = survey_fingerprint(definition)
        item["definition_hash"] = str(item.get("definition_hash") or fp.get("hash") or "")
        item["question_index"] = build_question_index(definition)
        item["question_ids"] = set(item["question_index"].keys())
        out.append(item)
    return out


def _choose_definition_by_overlap(answer_keys: set[str], defs: list[dict[str, Any]]) -> dict[str, Any] | None:
    best: dict[str, Any] | None = None
    best_score = -1
    for d in defs:
        qids = d.get("question_ids") or set()
        if not qids:
            continue
        overlap = len(answer_keys.intersection(qids))
        if overlap > best_score:
            best_score = overlap
            best = d
    return best


def _fetch_latest_response(db, user_id: str, survey_slug: str) -> dict[str, Any] | None:
    s = db.execute(
        text(
            """
            SELECT id, user_id, survey_slug, survey_version, survey_hash, status, completed_at, started_at, tenant_id
            FROM survey_session
            WHERE user_id = :user_id
              AND survey_slug = :survey_slug
            ORDER BY COALESCE(completed_at, started_at) DESC
            LIMIT 1
            """
        ),
        {"user_id": user_id, "survey_slug": survey_slug},
    ).mappings().first()
    if not s:
        return None
    session = dict(s)
    answers_rows = db.execute(
        text(
            """
            SELECT question_code, answer_value
            FROM survey_answer
            WHERE session_id = CAST(:session_id AS uuid)
            """
        ),
        {"session_id": str(session["id"])},
    ).mappings().all()
    session["answers"] = {str(r["question_code"]): r["answer_value"] for r in answers_rows}
    return session


def _is_question_visible(item: dict[str, Any], answers: dict[str, Any]) -> bool:
    """Check if a question is visible based on visibility rules."""
    rules = item.get("rules") if isinstance(item.get("rules"), list) else []
    if not rules:
        return True  # No rules means always visible
    
    for rule in rules:
        rule_type = rule.get("type")
        if rule_type == "show_if":
            trigger_code = rule.get("trigger_question_code")
            trigger_values = rule.get("trigger_value")
            operator = rule.get("operator", "eq")
            
            if not trigger_code or trigger_values is None:
                continue
            
            trigger_answer = answers.get(trigger_code)
            if trigger_answer is None:
                return False  # Trigger question not answered yet
            
            # Extract scalar value
            if isinstance(trigger_answer, dict):
                trigger_answer = trigger_answer.get("value")
            
            if operator == "in":
                if trigger_answer not in trigger_values:
                    return False
            elif operator == "eq":
                if trigger_answer != trigger_values:
                    return False
            elif operator == "neq":
                if trigger_answer == trigger_values:
                    return False
    
    return True


def _get_visible_required_questions(runtime: dict[str, Any], answers: dict[str, Any]) -> set[str]:
    """Get the set of required questions that are visible given current answers."""
    current_def = runtime.get("definition") if isinstance(runtime.get("definition"), dict) else {}
    screens = current_def.get("screens") if isinstance(current_def.get("screens"), list) else []
    
    visible_required = set()
    for screen in screens:
        items = screen.get("items") if isinstance(screen.get("items"), list) else []
        for item in items:
            question = item.get("question") if isinstance(item.get("question"), dict) else {}
            is_required = bool(question.get("is_required"))
            if is_required and _is_question_visible(item, answers):
                code = question.get("code")
                if code:
                    visible_required.add(str(code))
    
    return visible_required


def reconcile_user_survey_to_current(db, user_id: str, tenant_id: str | None, tenant_slug: str | None = None) -> dict[str, Any]:
    runtime = get_active_survey_runtime(tenant_slug)
    current_slug = str(runtime.get("slug") or SURVEY_SLUG)
    current_version = int(runtime.get("version") or SURVEY_VERSION)
    current_hash = str(runtime.get("hash") or "")
    current_def = runtime.get("definition") if isinstance(runtime.get("definition"), dict) else {}
    current_q = runtime.get("question_index") if isinstance(runtime.get("question_index"), dict) else build_question_index(current_def)
    required_ids = set(runtime.get("required_question_ids") if isinstance(runtime.get("required_question_ids"), list) else [])

    latest = _fetch_latest_response(db, user_id, current_slug)
    definitions = _definitions_for_slug(db, current_slug)
    defs_by_hash = {str(d.get("definition_hash") or ""): d for d in definitions}

    answers_old = (latest or {}).get("answers") if isinstance((latest or {}).get("answers"), dict) else {}
    old_hash = str((latest or {}).get("survey_hash") or "")
    old_def: dict[str, Any] | None = defs_by_hash.get(old_hash)

    if not old_def and latest and latest.get("survey_version") is not None:
        sv = int(latest.get("survey_version") or 0)
        for d in definitions:
            if int(d.get("version") or 0) == sv:
                old_def = d
                old_hash = str(d.get("definition_hash") or "")
                break

    if not old_def and answers_old:
        inferred = _choose_definition_by_overlap(set(answers_old.keys()), definitions)
        if inferred:
            old_def = inferred
            old_hash = str(inferred.get("definition_hash") or "")

    old_q = old_def.get("question_index") if isinstance((old_def or {}).get("question_index"), dict) else {}

    answers_current: dict[str, Any] = {}
    missing: list[str] = []
    carried_forward: list[str] = []
    changed_semantics: list[str] = []
    new_questions: list[str] = []

    if not latest:
        missing = sorted(list(required_ids))
    else:
        for qid, meta in current_q.items():
            required = bool(meta.get("is_required"))
            if qid in answers_old:
                old_meta = old_q.get(qid) if isinstance(old_q, dict) else None
                if old_meta and str(old_meta.get("question_hash") or "") == str(meta.get("question_hash") or ""):
                    answers_current[qid] = answers_old[qid]
                    carried_forward.append(qid)
                elif old_meta is None and str(old_hash) == str(current_hash):
                    answers_current[qid] = answers_old[qid]
                    carried_forward.append(qid)
                else:
                    if required:
                        missing.append(qid)
                    changed_semantics.append(qid)
            else:
                if required:
                    missing.append(qid)
                new_questions.append(qid)

    needs_retake = len(missing) > 0
    report = {
        "user_id": user_id,
        "tenant_id": tenant_id,
        "current": {"slug": current_slug, "version": current_version, "hash": current_hash},
        "source": {
            "session_id": str((latest or {}).get("id")) if latest else None,
            "status": (latest or {}).get("status") if latest else None,
            "survey_version": (latest or {}).get("survey_version") if latest else None,
            "survey_hash": old_hash or None,
        },
        "counts": {
            "old_answers": len(answers_old),
            "carried_forward": len(carried_forward),
            "missing_required": len(missing),
            "changed_semantics": len(changed_semantics),
            "new_questions": len(new_questions),
        },
        "carried_forward": sorted(carried_forward),
        "changed_semantics": sorted(changed_semantics),
        "new_questions": sorted(new_questions),
    }

    db.execute(
        text(
            """
            INSERT INTO survey_reconciliation_state (
              id, user_id, tenant_id, survey_slug, current_survey_hash, source_survey_hash,
              source_survey_version, answers_current, missing_question_ids, needs_retake,
              migration_report, updated_at, created_at
            )
            VALUES (
              CAST(:id AS uuid),
              CAST(:user_id AS uuid),
              CAST(NULLIF(:tenant_id, '') AS uuid),
              :survey_slug,
              :current_survey_hash,
              :source_survey_hash,
              :source_survey_version,
              CAST(:answers_current AS jsonb),
              CAST(:missing_question_ids AS jsonb),
              :needs_retake,
              CAST(:migration_report AS jsonb),
              NOW(), NOW()
            )
            ON CONFLICT (user_id, survey_slug, current_survey_hash)
            DO UPDATE SET
              tenant_id = EXCLUDED.tenant_id,
              source_survey_hash = EXCLUDED.source_survey_hash,
              source_survey_version = EXCLUDED.source_survey_version,
              answers_current = EXCLUDED.answers_current,
              missing_question_ids = EXCLUDED.missing_question_ids,
              needs_retake = EXCLUDED.needs_retake,
              migration_report = EXCLUDED.migration_report,
              updated_at = NOW()
            """
        ),
        {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "tenant_id": tenant_id or "",
            "survey_slug": current_slug,
            "current_survey_hash": current_hash,
            "source_survey_hash": old_hash or None,
            "source_survey_version": (latest or {}).get("survey_version"),
            "answers_current": json.dumps(answers_current),
            "missing_question_ids": json.dumps(sorted(set(missing))),
            "needs_retake": bool(needs_retake),
            "migration_report": json.dumps(report),
        },
    )

    return {
        "user_id": user_id,
        "tenant_id": tenant_id,
        "survey_slug": current_slug,
        "survey_version": current_version,
        "current_survey_hash": current_hash,
        "source_survey_hash": old_hash or None,
        "source_survey_version": (latest or {}).get("survey_version") if latest else None,
        "answers_current": answers_current,
        "missing_question_ids": sorted(set(missing)),
        "needs_retake": bool(needs_retake),
        "migration_report": report,
    }


def get_user_survey_status(db, user_id: str, tenant_id: str | None, tenant_slug: str | None = None) -> dict[str, Any]:
    runtime = get_active_survey_runtime(tenant_slug)
    current_slug = str(runtime.get("slug") or SURVEY_SLUG)
    current_hash = str(runtime.get("hash") or "")
    qindex = runtime.get("question_index") if isinstance(runtime.get("question_index"), dict) else {}
    required_ids = set(runtime.get("required_question_ids") if isinstance(runtime.get("required_question_ids"), list) else [])

    row = db.execute(
        text(
            """
            SELECT answers_current, missing_question_ids, needs_retake, source_survey_hash, source_survey_version, updated_at
            FROM survey_reconciliation_state
            WHERE user_id = CAST(:user_id AS uuid)
              AND survey_slug = :survey_slug
              AND current_survey_hash = :current_survey_hash
            ORDER BY updated_at DESC
            LIMIT 1
            """
        ),
        {"user_id": user_id, "survey_slug": current_slug, "current_survey_hash": current_hash},
    ).mappings().first()

    if not row:
        reconciled = reconcile_user_survey_to_current(db, user_id, tenant_id=tenant_id, tenant_slug=tenant_slug)
        answers_current = reconciled.get("answers_current") if isinstance(reconciled.get("answers_current"), dict) else {}
        missing_ids = reconciled.get("missing_question_ids") if isinstance(reconciled.get("missing_question_ids"), list) else []
        updated_at = _now()
        source_hash = reconciled.get("source_survey_hash")
        source_version = reconciled.get("source_survey_version")
    else:
        answers_current = row.get("answers_current") if isinstance(row.get("answers_current"), dict) else {}
        missing_ids = row.get("missing_question_ids") if isinstance(row.get("missing_question_ids"), list) else []
        updated_at = row.get("updated_at")
        source_hash = row.get("source_survey_hash")
        source_version = row.get("source_survey_version")

    # Recalculate missing based on visibility rules - this is the key fix
    # Questions that are conditionally hidden should not count as missing
    visible_required = _get_visible_required_questions(runtime, answers_current)
    missing_ids = [
        qid for qid in missing_ids
        if qid in visible_required and _scalar(answers_current.get(qid)) in (None, "")
    ]

    total_required = max(1, len(visible_required))
    answered_required = len([qid for qid in visible_required if _scalar(answers_current.get(qid)) not in (None, "")])
    completion_pct = round((answered_required / total_required) * 100.0, 2)
    missing_meta = [
        {
            "id": qid,
            "text": ((qindex.get(qid) or {}).get("question") or {}).get("text"),
            "response_type": ((qindex.get(qid) or {}).get("question") or {}).get("response_type"),
        }
        for qid in missing_ids
    ]

    return {
        "survey_slug": current_slug,
        "current_survey_hash": current_hash,
        "source_survey_hash": source_hash,
        "source_survey_version": source_version,
        "completion_pct": completion_pct,
        "missing_question_ids": missing_ids,
        "missing_questions": missing_meta,
        "answers_current": answers_current,
        "last_submitted_at": updated_at,
        "is_complete": len(missing_ids) == 0,
    }


def upsert_reconciled_answers(
    db,
    *,
    user_id: str,
    tenant_id: str | None,
    answers_patch: dict[str, Any],
    tenant_slug: str | None = None,
) -> dict[str, Any]:
    status = get_user_survey_status(db, user_id, tenant_id=tenant_id, tenant_slug=tenant_slug)
    current = status.get("answers_current") if isinstance(status.get("answers_current"), dict) else {}
    merged = {**current, **answers_patch}
    runtime = get_active_survey_runtime(tenant_slug)
    slug = str(runtime.get("slug") or SURVEY_SLUG)
    hash_value = str(runtime.get("hash") or "")
    qindex = runtime.get("question_index") if isinstance(runtime.get("question_index"), dict) else {}
    required_ids = set(runtime.get("required_question_ids") if isinstance(runtime.get("required_question_ids"), list) else [])
    missing = sorted([qid for qid in required_ids if _scalar(merged.get(qid)) in (None, "")])

    db.execute(
        text(
            """
            UPDATE survey_reconciliation_state
            SET answers_current = CAST(:answers_current AS jsonb),
                missing_question_ids = CAST(:missing_question_ids AS jsonb),
                needs_retake = :needs_retake,
                updated_at = NOW()
            WHERE user_id = CAST(:user_id AS uuid)
              AND survey_slug = :survey_slug
              AND current_survey_hash = :current_survey_hash
            """
        ),
        {
            "user_id": user_id,
            "survey_slug": slug,
            "current_survey_hash": hash_value,
            "answers_current": json.dumps(merged),
            "missing_question_ids": json.dumps(missing),
            "needs_retake": bool(missing),
        },
    )

    completion_pct = round((len(required_ids) - len(missing)) / max(1, len(required_ids)) * 100.0, 2)
    return {
        "survey_slug": slug,
        "current_survey_hash": hash_value,
        "answers_current": merged,
        "missing_question_ids": missing,
        "missing_questions": [
            {
                "id": qid,
                "text": ((qindex.get(qid) or {}).get("question") or {}).get("text"),
                "response_type": ((qindex.get(qid) or {}).get("question") or {}).get("response_type"),
            }
            for qid in missing
        ],
        "is_complete": len(missing) == 0,
        "completion_pct": completion_pct,
    }


def recompute_user_traits_if_ready(db, user_id: str, tenant_id: str | None, tenant_slug: str | None = None) -> dict[str, Any]:
    status = get_user_survey_status(db, user_id, tenant_id=tenant_id, tenant_slug=tenant_slug)
    if not bool(status.get("is_complete")):
        return {"user_id": user_id, "skipped": True, "reason": "missing_required_questions"}

    runtime = get_active_survey_runtime(tenant_slug)
    current_slug = str(runtime.get("slug") or SURVEY_SLUG)
    current_version = int(runtime.get("version") or SURVEY_VERSION)
    current_hash = str(runtime.get("hash") or "")
    survey_def = runtime.get("definition") if isinstance(runtime.get("definition"), dict) else {}
    answers_current = status.get("answers_current") if isinstance(status.get("answers_current"), dict) else {}

    existing = db.execute(
        text(
            """
            SELECT id, computed_for_survey_hash, traits_schema_version, ocean_scores, insights_json
            FROM user_traits
            WHERE user_id = :user_id
              AND survey_slug = :survey_slug
              AND survey_version = :survey_version
            LIMIT 1
            """
        ),
        {"user_id": user_id, "survey_slug": current_slug, "survey_version": current_version},
    ).mappings().first()

    # Recompute if:
    # - No existing traits, OR
    # - computed_for_survey_hash is empty/different, OR  
    # - traits_schema_version is NULL or different, OR
    # - ocean_scores is NULL or empty, OR
    # - insights_json is NULL or empty
    needs = (
        not existing
        or not existing.get("computed_for_survey_hash")
        or not existing.get("traits_schema_version")
        or existing.get("ocean_scores") is None
        or existing.get("insights_json") is None
    )
    if not needs:
        return {"user_id": user_id, "skipped": True, "reason": "already_current"}

    traits = compute_traits(survey_def, answers_current)
    ocean = _ocean_scores_from_traits(traits)
    profile_row = db.execute(
        text(
            """
            SELECT display_name, cbs_year, hometown, COALESCE(photo_urls, '[]'::jsonb) AS photo_urls,
                   gender_identity, COALESCE(seeking_genders, '[]'::jsonb) AS seeking_genders
            FROM user_account
            WHERE id = CAST(:user_id AS uuid)
            """
        ),
        {"user_id": user_id},
    ).mappings().first()
    profile_data = dict(profile_row) if profile_row else {}
    insights = generate_profile_insights(traits, profile_data, count=4)

    db.execute(
        text(
            """
            INSERT INTO user_traits (
              id, user_id, survey_slug, survey_version, traits, tenant_id,
              computed_for_survey_hash, traits_schema_version, ocean_scores, insights_json, computed_at
            )
            VALUES (
              CAST(:id AS uuid),
              CAST(:user_id AS uuid),
              :survey_slug,
              :survey_version,
              CAST(:traits AS jsonb),
              CAST(NULLIF(:tenant_id, '') AS uuid),
              :computed_for_survey_hash,
              :traits_schema_version,
              CAST(:ocean_scores AS jsonb),
              CAST(:insights_json AS jsonb),
              NOW()
            )
            ON CONFLICT (user_id, survey_slug, survey_version)
            DO UPDATE SET
              traits = EXCLUDED.traits,
              tenant_id = EXCLUDED.tenant_id,
              computed_for_survey_hash = EXCLUDED.computed_for_survey_hash,
              traits_schema_version = EXCLUDED.traits_schema_version,
              ocean_scores = EXCLUDED.ocean_scores,
              insights_json = EXCLUDED.insights_json,
              computed_at = NOW()
            """
        ),
        {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "survey_slug": current_slug,
            "survey_version": current_version,
            "traits": json.dumps(traits),
            "tenant_id": tenant_id or "",
            "computed_for_survey_hash": current_hash,
            "traits_schema_version": int(TRAITS_VERSION),
            "ocean_scores": json.dumps(ocean),
            "insights_json": json.dumps(insights),
        },
    )
    return {
        "user_id": user_id,
        "recomputed": True,
        "survey_hash": current_hash,
        "traits_schema_version": int(TRAITS_VERSION),
        "ocean_scores": ocean,
        "insights": insights,
    }


def reconcile_and_recompute_user(db, user_id: str, tenant_id: str | None, tenant_slug: str | None = None) -> dict[str, Any]:
    rec = reconcile_user_survey_to_current(db, user_id, tenant_id=tenant_id, tenant_slug=tenant_slug)
    traits = recompute_user_traits_if_ready(db, user_id, tenant_id=tenant_id, tenant_slug=tenant_slug)
    return {
        "user_id": user_id,
        "reconciliation": rec,
        "traits": traits,
    }


def reconcile_all_users(db, *, tenant_slug: str | None = None, chunk_size: int = 200) -> dict[str, Any]:
    where_sql = "ua.disabled_at IS NULL"
    params: dict[str, Any] = {}
    if tenant_slug:
        where_sql += " AND t.slug = :tenant_slug"
        params["tenant_slug"] = tenant_slug

    users = db.execute(
        text(
            f"""
            SELECT ua.id, ua.tenant_id, t.slug AS tenant_slug
            FROM user_account ua
            LEFT JOIN tenant t ON t.id = ua.tenant_id
            WHERE {where_sql}
            ORDER BY ua.created_at ASC
            """
        ),
        params,
    ).mappings().all()

    per_tenant: dict[str, dict[str, int]] = {}
    for r in users:
        # Handle both string and UUID types from SQLAlchemy
        uid_raw = r.get("id")
        uid = str(uid_raw) if uid_raw else ""
        tid_raw = r.get("tenant_id")
        tid = str(tid_raw) if tid_raw else None
        tslug_raw = r.get("tenant_slug")
        tslug = str(tslug_raw) if tslug_raw else "cbs"
        out = reconcile_and_recompute_user(db, uid, tenant_id=tid, tenant_slug=tslug)
        bucket = per_tenant.setdefault(
            tslug,
            {
                "users_reconciled": 0,
                "users_now_complete": 0,
                "users_still_missing": 0,
                "users_traits_recomputed": 0,
            },
        )
        bucket["users_reconciled"] += 1
        missing = out.get("reconciliation", {}).get("missing_question_ids") if isinstance(out.get("reconciliation"), dict) else []
        if missing:
            bucket["users_still_missing"] += 1
        else:
            bucket["users_now_complete"] += 1
        if bool((out.get("traits") or {}).get("recomputed")):
            bucket["users_traits_recomputed"] += 1

    db.commit()

    return {
        "tenants": per_tenant,
        "users_processed": len(users),
        "chunk_size": int(chunk_size),
        "resumable": True,
    }
