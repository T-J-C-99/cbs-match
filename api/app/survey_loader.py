import json
from functools import lru_cache
from typing import Any
from .config import QUESTIONS_PATH, SURVEY_SLUG
from . import survey_admin_repo


DEFAULT_SURVEY_DEFINITION: dict[str, Any] = {
    "survey": {
        "slug": SURVEY_SLUG,
        "version": 1,
        "name": "CBS Match Onboarding",
        "status": "active",
        "estimated_minutes": 5,
    },
    "option_sets": {
        "consent_yes_no": [
            {"value": "yes", "label": "Yes"},
            {"value": "no", "label": "No"},
        ],
        "likert_agree": [
            {"value": 1, "label": "Strongly disagree"},
            {"value": 2, "label": "Disagree"},
            {"value": 3, "label": "Neutral"},
            {"value": 4, "label": "Agree"},
            {"value": 5, "label": "Strongly agree"},
        ],
        "energy_pair": [
            {"value": "A", "label": "I recharge by being around people"},
            {"value": "B", "label": "I recharge by spending time alone"},
        ],
    },
    "screens": [
        {
            "key": "consent",
            "ordinal": 1,
            "title": "Let’s get you set up",
            "subtitle": "Complete this short survey to create your matching profile.",
            "items": [
                {
                    "question": {
                        "code": "CONSENT",
                        "text": "Do you want to participate in matching?",
                        "response_type": "single_select",
                        "is_required": True,
                        "allow_skip": False,
                        "region_tag": "GLOBAL",
                        "usage": "COPY_ONLY",
                    },
                    "options": "consent_yes_no",
                    "rules": [],
                }
            ],
        },
        {
            "key": "personality",
            "ordinal": 2,
            "title": "Your style",
            "items": [
                {
                    "question": {
                        "code": "OPENNESS",
                        "text": "I enjoy trying new things and ideas.",
                        "response_type": "single_select",
                        "is_required": True,
                        "allow_skip": False,
                        "region_tag": "GLOBAL",
                        "usage": "SCORING",
                    },
                    "options": "likert_agree",
                    "rules": [
                        {
                            "type": "show_if",
                            "trigger_question_code": "CONSENT",
                            "operator": "eq",
                            "trigger_value": "yes",
                        }
                    ],
                },
                {
                    "question": {
                        "code": "CONSCIENTIOUSNESS",
                        "text": "I like to stay organized and follow through.",
                        "response_type": "single_select",
                        "is_required": True,
                        "allow_skip": False,
                        "region_tag": "GLOBAL",
                        "usage": "SCORING",
                    },
                    "options": "likert_agree",
                    "rules": [
                        {
                            "type": "show_if",
                            "trigger_question_code": "CONSENT",
                            "operator": "eq",
                            "trigger_value": "yes",
                        }
                    ],
                },
                {
                    "question": {
                        "code": "EXTRAVERSION_PAIR",
                        "text": "Which sounds more like you?",
                        "response_type": "forced_choice_pair",
                        "is_required": True,
                        "allow_skip": False,
                        "region_tag": "GLOBAL",
                        "usage": "SCORING",
                    },
                    "options": "energy_pair",
                    "rules": [
                        {
                            "type": "show_if",
                            "trigger_question_code": "CONSENT",
                            "operator": "eq",
                            "trigger_value": "yes",
                        }
                    ],
                },
            ],
        },
    ],
}


def is_placeholder_survey_definition(definition: Any) -> bool:
    if not isinstance(definition, dict):
        return True
    screens = definition.get("screens")
    if isinstance(screens, list) and len(screens) > 0:
        return False
    questions = definition.get("questions")
    if isinstance(questions, list) and len(questions) == 0:
        return True
    return not isinstance(screens, list) or len(screens) == 0


def _normalize_loaded_definition(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return DEFAULT_SURVEY_DEFINITION.copy()
    if isinstance(raw.get("screens"), list):
        return raw if raw.get("screens") else DEFAULT_SURVEY_DEFINITION.copy()
    # Backward compatibility for placeholder/legacy code survey files that only
    # expose a top-level `questions` array. Treat them as an empty valid survey
    # definition for admin flows/tests until a full screen-based schema is loaded.
    if isinstance(raw.get("questions"), list):
        return DEFAULT_SURVEY_DEFINITION.copy() if len(raw.get("questions") or []) == 0 else {**raw, "screens": []}
    return DEFAULT_SURVEY_DEFINITION.copy()


@lru_cache(maxsize=1)
def get_file_survey_definition() -> dict[str, Any]:
    with QUESTIONS_PATH.open("r", encoding="utf-8") as f:
        return _normalize_loaded_definition(json.load(f))


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
    if active and isinstance(active.get("definition_json"), dict) and not is_placeholder_survey_definition(active.get("definition_json")):
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
