import json
from functools import lru_cache
from typing import Any
from .config import QUESTIONS_PATH, SURVEY_SLUG
from . import survey_admin_repo


@lru_cache(maxsize=1)
def get_file_survey_definition() -> dict[str, Any]:
    with QUESTIONS_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def _filter_items_for_tenant(items: list[dict[str, Any]], tenant_slug: str | None) -> list[dict[str, Any]]:
    slug = (tenant_slug or "cbs").strip().lower()
    out: list[dict[str, Any]] = []
    for item in items:
        q = item.get("question") if isinstance(item, dict) else None
        if not isinstance(q, dict):
            continue
        region_tag = str(q.get("region_tag") or "GLOBAL").strip().upper()
        tenant_tags = q.get("tenant_tags")
        tags = [str(t).strip().lower() for t in (tenant_tags or []) if str(t).strip()] if isinstance(tenant_tags, list) else []
        if region_tag == "GLOBAL":
            out.append(item)
            continue
        if region_tag == "SCHOOL_SPECIFIC" and slug in tags:
            out.append(item)
            continue
        # Backward compatibility for pre-M7 CBS_NYC tagging.
        if region_tag == "CBS_NYC" and slug == "cbs":
            out.append(item)
            continue
    return out


def filter_survey_for_tenant(survey: dict[str, Any], tenant_slug: str | None) -> dict[str, Any]:
    screens = survey.get("screens") if isinstance(survey.get("screens"), list) else []
    filtered_screens: list[dict[str, Any]] = []
    for screen in screens:
        if not isinstance(screen, dict):
            continue
        items = screen.get("items") if isinstance(screen.get("items"), list) else []
        filtered_items = _filter_items_for_tenant(items, tenant_slug)
        if not filtered_items:
            continue
        filtered_screens.append({**screen, "items": filtered_items})
    return {**survey, "screens": filtered_screens}


def get_survey_definition(tenant_slug: str | None = None) -> dict[str, Any]:
    try:
        active = survey_admin_repo.get_active_definition(SURVEY_SLUG)
    except Exception:
        active = None
    if active and isinstance(active.get("definition_json"), dict):
        return filter_survey_for_tenant(active["definition_json"], tenant_slug)
    return filter_survey_for_tenant(get_file_survey_definition(), tenant_slug)


def get_runtime_code_definition(tenant_slug: str | None = None) -> dict[str, Any]:
    return filter_survey_for_tenant(get_file_survey_definition(), tenant_slug)


def get_question_map() -> dict[str, dict[str, Any]]:
    survey = get_survey_definition()
    out: dict[str, dict[str, Any]] = {}
    for screen in survey.get("screens", []):
        for item in screen.get("items", []):
            q = item.get("question", {})
            code = q.get("code")
            if code:
                out[code] = {
                    "question": q,
                    "screen_key": screen.get("key"),
                    "screen_ordinal": screen.get("ordinal"),
                }
    return out
