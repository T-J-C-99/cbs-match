from __future__ import annotations

import re
from typing import Any

from .copy_templates import (
    build_personalized_explanation as _build_personalized_explanation,
    generate_profile_insights as _generate_profile_insights,
)


_BANNED_TERMS = {
    "kids",
    "religion",
    "emotional regulation",
    "attachment",
    "cbs_nyc",
    "region_tag",
}


def _safe_num(v: Any, default: float = 0.5) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _clean_text(line: str) -> str:
    txt = " ".join(str(line or "").split())
    txt = re.sub(r"\b[A-Z]{2,}_[A-Z0-9_]+\b", "", txt)
    lowered = txt.lower()
    for term in _BANNED_TERMS:
        if term in lowered:
            return "Your profiles show meaningful compatibility potential."
    return txt.strip()


def _top_two(items: list[tuple[str, float]], reverse: bool = True) -> list[tuple[str, float]]:
    return sorted(items, key=lambda x: x[1], reverse=reverse)[:2]


def _choose_vibe_hook(user_traits: dict[str, Any], matched_traits: dict[str, Any]) -> str:
    u_vibe = ((user_traits or {}).get("copy_only") or {}).get("vibe") or {}
    m_vibe = ((matched_traits or {}).get("copy_only") or {}).get("vibe") or {}
    shared = [k for k in u_vibe.keys() if k in m_vibe]
    if shared:
        k = shared[0]
        return f"You both picked a similar vibe on {k.replace('_', ' ').title()}—easy chemistry starter."
    if u_vibe:
        k = sorted(u_vibe.keys())[0]
        return f"Your {k.replace('_', ' ').title()} pick gives you an easy first conversation opener."
    return "Your match has a playful spark that should make the first conversation easy."


def _icebreakers(user_traits: dict[str, Any], matched_traits: dict[str, Any]) -> list[str]:
    u_copy = (user_traits or {}).get("copy_only") or {}
    m_copy = (matched_traits or {}).get("copy_only") or {}
    u_vibe = u_copy.get("vibe") or {}
    m_vibe = m_copy.get("vibe") or {}
    u_school = u_copy.get("school") or {}
    m_school = m_copy.get("school") or {}

    prompts: list[str] = []
    for code in sorted(set(u_vibe.keys()) & set(m_vibe.keys()))[:2]:
        prompts.append(f"You both answered {code.replace('_', ' ').title()}—what story sits behind your choice?")
    for code in sorted(set(u_school.keys()) & set(m_school.keys()))[:2]:
        prompts.append(f"Quick warm-up: compare your takes on {code.replace('_', ' ').title()} and swap one surprising detail.")

    if not prompts:
        prompts = [
            "What’s your ideal pace for getting to know someone new?",
            "What kind of date setting makes you feel most like yourself?",
        ]
    return [_clean_text(p) for p in prompts[:2]]


def _component_values(score_breakdown: dict[str, Any]) -> dict[str, float]:
    cats = (score_breakdown or {}).get("categories") or {}
    comps = (score_breakdown or {}).get("components") or {}
    return {
        "values_alignment": _safe_num(cats.get("values_similarity"), 0.5),
        "conflict_fit": _safe_num(cats.get("conflict_fit"), 0.5),
        "communication_fit": _safe_num(comps.get("text_sensitivity_similarity"), 0.5),
        "attachment_fit": _safe_num(cats.get("attachment_fit"), 0.5),
        "personality_fit": _safe_num(cats.get("personality_fit"), 0.5),
        "life_fit": _safe_num(cats.get("life_fit"), 0.5),
        "escalation_risk": _safe_num(comps.get("escalation_risk"), 0.5),
    }


def build_safe_explanation(
    score_breakdown: dict[str, Any] | None,
    user_traits: dict[str, Any] | None,
    matched_traits: dict[str, Any] | None,
) -> dict[str, Any]:
    score_breakdown = score_breakdown or {}
    user_traits = user_traits or {}
    matched_traits = matched_traits or {}

    vals = _component_values(score_breakdown)
    positives = _top_two(
        [
            ("Values alignment", vals["values_alignment"]),
            ("How you resolve tension", vals["conflict_fit"]),
            ("Pace of communication", vals["communication_fit"]),
            ("Day-to-day rhythm", vals["life_fit"]),
        ]
    )
    risks = _top_two(
        [
            ("Communication pacing", 1 - vals["communication_fit"]),
            ("Conflict recovery style", 1 - vals["conflict_fit"]),
            ("Escalation risk", 1 - vals["escalation_risk"]),
            ("Lifestyle rhythm", 1 - vals["life_fit"]),
        ],
        reverse=True,
    )

    vibe_hook = _choose_vibe_hook(user_traits, matched_traits)
    overall = _clean_text(
        f"Strongest fit areas are values alignment and how you resolve tension. {vibe_hook}"
    )

    highlights = [_clean_text(f"{name} looks strong in this pairing.") for name, _ in positives]
    challenges = [_clean_text(f"{name} may need explicit check-ins.") for name, _ in risks]
    icebreakers = _icebreakers(user_traits, matched_traits)

    bullets = [
        _clean_text("You align well on core values and relationship direction."),
        _clean_text("Your fit on how quickly you like to talk things through looks promising."),
        _clean_text(vibe_hook),
    ]

    return {
        "bullets": bullets,
        "summary": [overall, *highlights[:1], *challenges[:1]],
        "icebreakers": icebreakers,
        "highlights": highlights,
        "potential_challenges": challenges,
        "uniqueness": [_clean_text(vibe_hook)],
        "option_bank": {
            "highlights": highlights,
            "potential_challenges": challenges,
            "uniqueness": [_clean_text(vibe_hook)],
            "icebreakers": icebreakers,
        },
    }


def build_safe_explanation_v2(
    score_breakdown: dict[str, Any] | None,
    user_traits: dict[str, Any] | None,
    matched_traits: dict[str, Any] | None,
) -> dict[str, Any]:
    # Prefer dynamic template-driven commentary (large copy corpus + data-driven placeholders).
    # Fall back to safe heuristic copy if template generation fails for any reason.
    try:
        dyn = _build_personalized_explanation(score_breakdown or {}, user_traits or {}, matched_traits or {})
        overall = _clean_text(str(dyn.get("overall") or ""))
        pros = [_clean_text(str(x)) for x in (dyn.get("pros") or []) if str(x).strip()]
        cons = [_clean_text(str(x)) for x in (dyn.get("cons") or []) if str(x).strip()]
        if overall and pros and cons:
            return {
                "overall": overall,
                "pros": pros[:2],
                "cons": cons[:2],
                "version": str(dyn.get("version") or "2026-02-18-v4"),
            }
    except Exception:
        pass

    base = build_safe_explanation(score_breakdown, user_traits, matched_traits)
    return {
        "overall": base["summary"][0],
        "pros": base["highlights"][:2],
        "cons": base["potential_challenges"][:2],
        "version": "2026-02-18-v4-fallback",
    }


def generate_profile_insights(user_traits: dict[str, Any] | None, profile_data: dict[str, Any] | None, count: int = 4) -> list[str]:
    return _generate_profile_insights(user_traits, profile_data, count=count)
