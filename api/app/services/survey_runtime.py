from __future__ import annotations

from typing import Any

from ..config import SURVEY_SLUG, SURVEY_VERSION
from ..survey_loader import get_survey_definition
from .. import survey_admin_repo
from .survey_fingerprint import build_question_index, survey_fingerprint


def get_active_survey_runtime(tenant_slug: str | None = None) -> dict[str, Any]:
    """Runtime source-of-truth for survey slug/version/definition.

    - Prefer DB active definition revision metadata.
    - Fallback to code config/version if DB active is absent.
    """
    active = None
    try:
        active = survey_admin_repo.get_active_definition(SURVEY_SLUG)
    except Exception:
        active = None

    definition = get_survey_definition(tenant_slug)
    slug = SURVEY_SLUG
    version = SURVEY_VERSION

    if active and isinstance(active.get("definition_json"), dict):
        slug = str(active.get("slug") or SURVEY_SLUG)
        version = int(active.get("version") or SURVEY_VERSION)
    else:
        survey_meta = definition.get("survey") if isinstance(definition, dict) else {}
        if isinstance(survey_meta, dict):
            slug = str(survey_meta.get("slug") or SURVEY_SLUG)
            version = int(survey_meta.get("version") or SURVEY_VERSION)

    fingerprint = survey_fingerprint(definition)
    question_index = build_question_index(definition)
    required_question_ids = sorted([qid for qid, meta in question_index.items() if bool(meta.get("is_required"))])

    return {
        "slug": slug,
        "version": version,
        "hash": str(fingerprint.get("hash") or ""),
        "definition": definition,
        "question_index": question_index,
        "required_question_ids": required_question_ids,
        "active_db_definition": active,
    }


def list_question_codes(survey_def: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for screen in survey_def.get("screens", []) if isinstance(survey_def, dict) else []:
        if not isinstance(screen, dict):
            continue
        for item in screen.get("items", []):
            if not isinstance(item, dict):
                continue
            q = item.get("question")
            if not isinstance(q, dict):
                continue
            code = str(q.get("code") or "").strip()
            if code:
                out.add(code)
    return out
