from __future__ import annotations

import hashlib
from typing import Any


_TITLE_RULES = [
    ("The Connector", lambda d: d.get("extraversion", 0.5) >= 0.68 and d.get("agreeableness", 0.5) >= 0.62),
    ("The Grounded Operator", lambda d: d.get("conscientiousness", 0.5) >= 0.66 and d.get("stability", 0.5) >= 0.58),
    ("The Curious Builder", lambda d: d.get("worldview_alignment", 0.5) >= 0.62 and d.get("openness", 0.5) >= 0.63),
    ("The Calm Strategist", lambda d: d.get("structure", 0.5) >= 0.62 and d.get("escalation", 0.5) <= 0.42),
]

_SAFE_BULLETS = {
    "openness": "You bring curiosity that keeps first conversations engaging.",
    "conscientiousness": "You show up reliably, which builds trust quickly.",
    "extraversion": "Your social energy helps create momentum early.",
    "agreeableness": "You make people feel heard and respected.",
    "stability": "You tend to keep interactions steady even when weeks get busy.",
    "repair_belief": "You are oriented toward repairing tension rather than letting it drag.",
    "structure": "You communicate in a clear, practical way that reduces confusion.",
}

_WATCHOUTS = [
    ("When your schedule gets overloaded, you may default to efficiency over warmth.", lambda d: d.get("conscientiousness", 0.5) >= 0.7),
    ("When stressed, you may over-index on reading signals too quickly.", lambda d: d.get("text_sensitivity", 0.5) >= 0.68),
    ("In high-pressure weeks, you may need more reset time than you initially say.", lambda d: d.get("withdrawal", 0.5) >= 0.62),
]

_DATE_ENERGY = [
    ("cocktail_bar", "Confident social setting with room for banter"),
    ("coffee_walk", "Low-pressure walk-and-talk with real conversation"),
    ("museum_activity", "Shared curiosity date with built-in talking points"),
    ("cozy_lounge", "Quiet, intentional setting that favors depth"),
]

_OPENER_STYLES = {
    "direct": "Direct opener: “You seem intentional—what kind of week are you hoping for from this match?”",
    "playful": "Playful opener: “Serious question: coffee walk, museum, or wildcard option?”",
    "thoughtful": "Thoughtful opener: “What’s one thing people usually miss about your energy?”",
}


def _safe_float(value: Any, default: float = 0.5) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _dims(traits: dict[str, Any]) -> dict[str, float]:
    dimensions = (traits or {}).get("dimensions") or {}
    big_five = (traits or {}).get("big_five") or {}
    conflict = (traits or {}).get("conflict") or {}
    return {
        "openness": _safe_float(big_five.get("openness"), _safe_float(dimensions.get("openness"), 0.5)),
        "conscientiousness": _safe_float(big_five.get("conscientiousness"), _safe_float(dimensions.get("conscientiousness"), 0.5)),
        "extraversion": _safe_float(big_five.get("extraversion"), _safe_float(dimensions.get("extraversion"), 0.5)),
        "agreeableness": _safe_float(big_five.get("agreeableness"), 0.5),
        "stability": _safe_float(dimensions.get("stability"), 0.5),
        "worldview_alignment": _safe_float(dimensions.get("worldview_alignment"), 0.5),
        "repair_belief": _safe_float(dimensions.get("repair_belief"), _safe_float(conflict.get("repair_belief"), 0.5)),
        "structure": _safe_float(dimensions.get("structure"), _safe_float(conflict.get("structure"), 0.5)),
        "escalation": _safe_float(dimensions.get("escalation"), _safe_float(conflict.get("escalation"), 0.5)),
        "withdrawal": _safe_float(dimensions.get("withdrawal"), _safe_float(conflict.get("withdrawal"), 0.5)),
        "text_sensitivity": _safe_float(dimensions.get("text_sensitivity"), 0.5),
        "independence_need": _safe_float(dimensions.get("independence_need"), 0.5),
    }


def _seed(user_id: str, survey_slug: str, survey_version: int) -> int:
    digest = hashlib.sha256(f"{user_id}:{survey_slug}:{survey_version}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def _pick_title(dimensions: dict[str, float]) -> str:
    for label, fn in _TITLE_RULES:
        if fn(dimensions):
            return label
    return "The Intentional Spark"


def _top_strength_keys(dimensions: dict[str, float]) -> list[str]:
    ranked = sorted(_SAFE_BULLETS.keys(), key=lambda k: dimensions.get(k, 0.5), reverse=True)
    return ranked[:3]


def _watchout(dimensions: dict[str, float]) -> str:
    for text, fn in _WATCHOUTS:
        if fn(dimensions):
            return text
    return "When your week gets packed, explicit plans usually help you stay connected."


def _date_energy(dimensions: dict[str, float], seed: int) -> dict[str, str]:
    if dimensions.get("extraversion", 0.5) >= 0.67:
        return {"key": _DATE_ENERGY[0][0], "label": _DATE_ENERGY[0][1]}
    if dimensions.get("openness", 0.5) >= 0.64:
        return {"key": _DATE_ENERGY[2][0], "label": _DATE_ENERGY[2][1]}
    idx = 1 if seed % 2 == 0 else 3
    return {"key": _DATE_ENERGY[idx][0], "label": _DATE_ENERGY[idx][1]}


def _opener_style(dimensions: dict[str, float]) -> tuple[str, str]:
    if dimensions.get("structure", 0.5) >= 0.62:
        return "direct", _OPENER_STYLES["direct"]
    if dimensions.get("extraversion", 0.5) >= 0.66:
        return "playful", _OPENER_STYLES["playful"]
    return "thoughtful", _OPENER_STYLES["thoughtful"]


def _motto(dimensions: dict[str, float]) -> str:
    if dimensions.get("repair_belief", 0.5) >= 0.62 and dimensions.get("escalation", 0.5) <= 0.45:
        return "You tend to do best with people who are clear, warm, and willing to repair quickly."
    if dimensions.get("independence_need", 0.5) >= 0.65:
        return "Your best fits usually pair chemistry with enough room to keep life momentum."
    return "Your best matches usually combine emotional steadiness with genuine curiosity."


def generate_vibe_card(
    *,
    user_id: str,
    survey_slug: str,
    survey_version: int,
    traits: dict[str, Any] | None,
    copy_only: dict[str, Any] | None,
    tenant_ctx: dict[str, Any] | None,
    safety_flags: dict[str, Any] | None,
) -> dict[str, Any]:
    dimensions = _dims(traits or {})
    deterministic_seed = _seed(user_id, survey_slug, survey_version)
    top_keys = _top_strength_keys(dimensions)
    date_energy = _date_energy(dimensions, deterministic_seed)
    opener_key, opener_template = _opener_style(dimensions)

    hooks: list[str] = []
    school = ((copy_only or {}).get("school") or {}) if isinstance(copy_only, dict) else {}
    for code in sorted(school.keys())[:2]:
        value = str(school.get(code) or "").strip()
        if value:
            hooks.append(f"CBS hook: {code.replace('_', ' ').title()} → {value}.")

    title = _pick_title(dimensions)
    strengths = [_SAFE_BULLETS[k] for k in top_keys][:2]
    watchouts = [_watchout(dimensions), "Clarity around expectations early usually makes this dynamic shine."]
    best_dates = [
        date_energy["label"],
        "Low-pressure coffee walk near campus",
        "One intentional plan with room for spontaneity",
    ]
    starters = [
        opener_template,
        "What does a great week look like for you right now?",
        "What kind of pace feels best to you when getting to know someone?",
    ]

    school_tag = None
    if hooks:
        school_tag = hooks[0].replace("CBS hook: ", "")

    card = {
        "title": title,
        "subtitle": _motto(dimensions),
        "archetype": title,
        "traits": [
            {"label": "Openness", "value": f"{round(dimensions.get('openness', 0.5) * 100)}"},
            {"label": "Conscientiousness", "value": f"{round(dimensions.get('conscientiousness', 0.5) * 100)}"},
            {"label": "Extraversion", "value": f"{round(dimensions.get('extraversion', 0.5) * 100)}"},
        ],
        "strengths": strengths,
        "watchouts": watchouts,
        "best_dates": best_dates,
        "conversation_starters": starters,
    }
    if school_tag:
        card["school_tag"] = school_tag

    # Backward-compatible fields for current web/mobile renderers.
    card["three_bullets"] = [_SAFE_BULLETS[k] for k in top_keys]
    card["one_watchout"] = watchouts[0]
    card["best_date_energy"] = date_energy
    card["opener_style"] = {"key": opener_key, "template": opener_template}
    card["compatibility_motto"] = card["subtitle"]
    card["school_module_hooks"] = hooks
    card["meta"] = {
        "version": "vibe-card-2026-02-18",
        "deterministic_seed": deterministic_seed,
        "tenant_slug": (tenant_ctx or {}).get("slug") or "cbs",
        "safe_mode": not bool((safety_flags or {}).get("allow_sensitive")),
    }
    return card
