from __future__ import annotations

from statistics import mean
from typing import Any


TRAITS_VERSION = 3


def _coerce_likert(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        v = float(value)
    elif isinstance(value, str) and value.strip().isdigit():
        v = float(value.strip())
    else:
        return None
    if 1.0 <= v <= 5.0:
        return v
    return None


def _normalize_likert(value: Any, reverse: bool = False) -> float | None:
    v = _coerce_likert(value)
    if v is None:
        return None
    out = (v - 1.0) / 4.0
    return round(1.0 - out if reverse else out, 6)


def _forced_choice_value(value: Any) -> float | None:
    if value == "A":
        return 0.0
    if value == "B":
        return 1.0
    return None


def _mean(values: list[float], *, default: float | None = None) -> float | None:
    if not values:
        return default
    return round(float(mean(values)), 6)


def _weighted_mean(values: list[tuple[float, float]], *, default: float | None = None) -> float | None:
    if not values:
        return default
    total_w = sum(w for _, w in values)
    if total_w <= 0:
        return default
    return round(sum(v * w for v, w in values) / total_w, 6)


def _answer_scalar(answer_value: Any) -> Any:
    if isinstance(answer_value, dict) and "value" in answer_value:
        return answer_value.get("value")
    return answer_value


def _build_question_meta(survey_def: dict[str, Any]) -> dict[str, dict[str, Any]]:
    meta: dict[str, dict[str, Any]] = {}
    for screen in survey_def.get("screens", []):
        for item in screen.get("items", []):
            question = item.get("question") or {}
            code = question.get("code")
            if not code:
                continue
            meta[str(code)] = {
                "reverse_coded": bool(question.get("reverse_coded", False)),
                "response_type": question.get("response_type"),
                "usage": question.get("usage"),
                "region_tag": question.get("region_tag"),
                "allow_skip": bool(question.get("allow_skip", False)),
                "is_required": bool(question.get("is_required", False)),
            }
    return meta


def _required_missing_codes(survey_def: dict[str, Any], answers: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for screen in survey_def.get("screens", []):
        for item in screen.get("items", []):
            q = item.get("question") or {}
            code = q.get("code")
            if not code:
                continue
            if not bool(q.get("is_required", False)):
                continue
            if bool(q.get("allow_skip", False)):
                continue
            if code == "KIDS_02":
                kids_intent = _answer_scalar(answers.get("KIDS_01"))
                if kids_intent not in {"yes", "probably"}:
                    continue
            value = answers.get(code)
            scalar = _answer_scalar(value)
            if scalar is None or scalar == "":
                missing.append(str(code))
    return sorted(set(missing))


def _compute_traits_legacy_v1(survey_def: dict[str, Any], answers: dict[str, Any]) -> dict[str, Any]:
    # Backward-compatible fallback for existing v1 sessions.
    qmeta = _build_question_meta(survey_def)
    big5_map = {
        "O": "openness",
        "C": "conscientiousness",
        "E": "extraversion",
        "A": "agreeableness",
        "N": "neuroticism",
    }
    big5_vals: dict[str, list[float]] = {k: [] for k in big5_map}

    for code, raw in answers.items():
        meta = qmeta.get(code)
        if not meta or meta.get("response_type") != "likert_1_5":
            continue
        scalar = _answer_scalar(raw)
        v = _normalize_likert(scalar, reverse=bool(meta.get("reverse_coded")))
        if v is None:
            continue
        if str(code).startswith("BF_"):
            parts = str(code).split("_")
            if len(parts) >= 2 and parts[1] in big5_vals:
                big5_vals[parts[1]].append(v)

    big5 = {
        big5_map[k]: _mean(vals, default=0.5)
        for k, vals in big5_vals.items()
    }

    life_constraints = {
        "kids_preference": _answer_scalar(answers.get("LA_KIDS_01")),
    }
    modifiers = {
        "kids": {
            "importance": _normalize_likert(_answer_scalar(answers.get("MOD_KIDS_IMPORTANCE"))) or 0.5,
            "flexibility": _normalize_likert(_answer_scalar(answers.get("MOD_KIDS_FLEXIBILITY"))) or 0.5,
        }
    }

    return {
        "traits_version": 2,
        "survey_slug": (survey_def.get("survey") or {}).get("slug"),
        "survey_version": (survey_def.get("survey") or {}).get("version"),
        "big5": big5,
        "life_constraints": life_constraints,
        "modifiers": modifiers,
        "copy_only": {"vibe": {}, "school": {}},
    }


def compute_traits_match_core_v3(survey_def: dict[str, Any], answers: dict[str, Any]) -> dict[str, Any]:
    qmeta = _build_question_meta(survey_def)
    missing = _required_missing_codes(survey_def, answers)
    if missing:
        raise ValueError(f"missing required answers: {', '.join(missing)}")

    scoring_answers: dict[str, Any] = {}
    copy_vibe: dict[str, str] = {}
    copy_school: dict[str, str] = {}

    for code, raw in answers.items():
        meta = qmeta.get(code, {})
        scalar = _answer_scalar(raw)
        usage = str(meta.get("usage") or "")
        region = str(meta.get("region_tag") or "")
        if usage == "COPY_ONLY":
            if code.startswith("VIBE_"):
                copy_vibe[code] = "" if scalar is None else str(scalar)
            elif region == "CBS_NYC" or code.startswith("CBS_"):
                copy_school[code] = "" if scalar is None else str(scalar)
            continue
        if usage == "SCORING" and region == "GLOBAL":
            scoring_answers[code] = scalar

    def likert(code: str) -> float | None:
        reverse = bool((qmeta.get(code) or {}).get("reverse_coded", False))
        return _normalize_likert(scoring_answers.get(code), reverse=reverse)

    def fc(code: str) -> float | None:
        return _forced_choice_value(scoring_answers.get(code))

    def mean_codes(codes: list[str]) -> float | None:
        vals = [likert(c) for c in codes]
        return _mean([v for v in vals if v is not None], default=0.5)

    big_five = {
        "openness": mean_codes(["OPN_01", "OPN_02", "OPN_03"]),
        "conscientiousness": mean_codes(["CON_01", "CON_02", "CON_03"]),
        "extraversion": mean_codes(["EXT_01", "EXT_02", "EXT_03"]),
        "agreeableness": mean_codes(["AGR_01", "AGR_02", "AGR_03"]),
    }

    emotional_stability = mean_codes(["ER_01", "ER_02", "ER_03"])

    conflict = {
        "approach": likert("REP_01") or 0.5,
        "withdrawal": _mean([v for v in [likert("REP_02"), likert("REP_05")] if v is not None], default=0.5),
        "escalation": _mean([v for v in [likert("REP_04"), likert("REP_10")] if v is not None], default=0.5),
        "structure": likert("REP_11") or 0.5,
        "repair_belief": _mean([v for v in [likert("REP_07"), likert("REP_12")] if v is not None], default=0.5),
        "accountability_need": likert("REP_08") or 0.5,
    }

    attachment = {
        "reassurance_need": likert("ATT_02") or 0.5,
        "text_sensitivity": likert("ATT_03") or 0.5,
        "independence_need": likert("ATT_04") or 0.5,
        "trust_baseline": likert("ATT_05") or 0.5,
        "alone_time_need": likert("ATT_07") or 0.5,
        "drama_avoidance": likert("ATT_08") or 0.5,
        "testing_behavior": likert("ATT_09") or 0.5,
    }

    kids_intent = scoring_answers.get("KIDS_01")
    kids_timeline = scoring_answers.get("KIDS_02")
    if scoring_answers.get("KIDS_01") not in {"yes", "probably"}:
        kids_timeline = None

    val2 = likert("VAL_02")
    if val2 is None:
        val2 = 0.5
    val_parts = [likert("VAL_01"), likert("VAL_03")]
    val_available = [v for v in val_parts if v is not None]
    worldview_alignment = _mean(val_available, default=0.5)

    life = {
        "kids_intent": kids_intent if isinstance(kids_intent, str) else "unsure",
        "kids_timeline": kids_timeline if isinstance(kids_timeline, str) else None,
        "relocation_openness": likert("LOC_01") or 0.5,
        "career_intensity": likert("CAR_01") or 0.5,
        "partner_achievement_preference": likert("CAR_02") or 0.5,
        "marriage_intent": likert("MAR_01") or 0.5,
        "define_intentions_early": _mean([v for v in [likert("MAR_02"), likert("MAR_03")] if v is not None], default=0.5),
        "worldview_alignment_importance": val2,
        "worldview_alignment": worldview_alignment,
    }

    tradeoffs = {
        "stability_vs_novelty": fc("FC_01") if fc("FC_01") is not None else 0.5,
        "intimate_vs_group": fc("FC_02") if fc("FC_02") is not None else 0.5,
        "steady_vs_highs": fc("FC_03") if fc("FC_03") is not None else 0.5,
        "direct_vs_gradual": fc("FC_04") if fc("FC_04") is not None else 0.5,
        "define_early_vs_unfold": fc("FC_05") if fc("FC_05") is not None else 0.5,
        "frequent_comm_vs_space": fc("FC_06") if fc("FC_06") is not None else 0.5,
        "career_vs_relationship": fc("FC_07") if fc("FC_07") is not None else 0.5,
        "save_vs_spend": fc("FC_08") if fc("FC_08") is not None else 0.5,
    }

    # Additional dimensions used directly in matching score components.
    dims: dict[str, float] = {
        "worldview_alignment": float(life["worldview_alignment"]),
        "stability": float(emotional_stability if emotional_stability is not None else 0.5),
        "reassurance_need": float(attachment["reassurance_need"]),
        "independence_need": float(attachment["independence_need"]),
        "text_sensitivity": float(attachment["text_sensitivity"]),
        "drama_avoidance": float(attachment["drama_avoidance"]),
        "testing_behavior": float(attachment["testing_behavior"]),
        "approach": float(conflict["approach"]),
        "withdrawal": float(conflict["withdrawal"]),
        "escalation": float(conflict["escalation"]),
        "repair_belief": float(conflict["repair_belief"]),
        "structure": float(conflict["structure"]),
        "extraversion": float(big_five["extraversion"] if big_five["extraversion"] is not None else 0.5),
        "conscientiousness": float(big_five["conscientiousness"] if big_five["conscientiousness"] is not None else 0.5),
        "relocation_openness": float(life["relocation_openness"]),
        "career_intensity": float(life["career_intensity"]),
        "define_intentions_early": float(life["define_intentions_early"]),
        "kids_timeline_value": {
            "0_3_years": 1.0,
            "3_7_years": 0.66,
            "later": 0.33,
            "open": 0.5,
        }.get(str(life["kids_timeline"]), 0.5),
    }

    return {
        "traits_version": TRAITS_VERSION,
        "survey_slug": "match-core-v3",
        "survey_version": 1,
        "big_five": big_five,
        "emotional_regulation": {"stability": emotional_stability if emotional_stability is not None else 0.5},
        "conflict": conflict,
        "attachment": attachment,
        "life": life,
        "tradeoffs": tradeoffs,
        "dimensions": dims,
        "copy_only": {
            "vibe": copy_vibe,
            "school": copy_school,
        },
    }


def compute_traits(survey_def: dict[str, Any], answers: dict[str, Any]) -> dict[str, Any]:
    survey = survey_def.get("survey") or {}
    slug = survey.get("slug")
    version = survey.get("version")
    if slug == "match-core-v3" and int(version or 0) == 1:
        return compute_traits_match_core_v3(survey_def, answers)
    return _compute_traits_legacy_v1(survey_def, answers)
