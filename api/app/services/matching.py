from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import text


@dataclass
class MatchCandidate:
    user_id: str
    matched_user_id: str
    score_total: float
    score_breakdown: dict[str, Any]


def get_week_start_date(now: datetime, tz: str = "America/New_York") -> date:
    local_now = now.astimezone(ZoneInfo(tz))
    return local_now.date() - timedelta(days=local_now.weekday())


def canonical_pair(user_a: str, user_b: str) -> tuple[str, str]:
    return tuple(sorted((user_a, user_b)))


def _to_float(value: Any, default: float = 0.5) -> float:
    try:
        if value is None:
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _normalize_gender(value: Any) -> str | None:
    if value is None:
        return None
    v = str(value).strip().lower()
    return v or None


def _parse_seeking(values: Any) -> set[str]:
    if not isinstance(values, list):
        return set()
    out: set[str] = set()
    for item in values:
        g = _normalize_gender(item)
        if g:
            out.add(g)
    return out


def _gender_preference_compatible(u: dict[str, Any], v: dict[str, Any]) -> bool:
    u_gender = _normalize_gender(u.get("gender_identity"))
    v_gender = _normalize_gender(v.get("gender_identity"))
    u_seeking = _parse_seeking(u.get("seeking_genders"))
    v_seeking = _parse_seeking(v.get("seeking_genders"))
    if not u_gender or not v_gender or not u_seeking or not v_seeking:
        return False
    return (v_gender in u_seeking) and (u_gender in v_seeking)


def _kids_hard_mismatch(k1: str | None, k2: str | None) -> bool:
    if not k1 or not k2:
        return False
    if k1 == "unsure" or k2 == "unsure":
        return False
    hard_yes = {"yes", "probably"}
    hard_no = {"no", "probably_not"}
    return (k1 in hard_yes and k2 in hard_no) or (k2 in hard_yes and k1 in hard_no)


def _sim(a: float, b: float) -> float:
    return max(0.0, 1.0 - abs(a - b))


def _comp(a: float, b: float, target_sum: float = 1.0, extreme_penalty_threshold: float = 0.75) -> float:
    base = max(0.0, 1.0 - abs((a + b) - target_sum))
    if abs(a - b) > extreme_penalty_threshold:
        base *= 0.75
    return base


def _harmonic_mean(a: float, b: float) -> float:
    if a <= 0 or b <= 0:
        return 0.0
    return 2.0 * a * b / (a + b)


def _dim(traits: dict[str, Any], key: str, default: float = 0.5) -> float:
    dims = (traits or {}).get("dimensions") or {}
    return _to_float(dims.get(key), default)


def _life(traits: dict[str, Any], key: str, default: Any = None) -> Any:
    life = ((traits or {}).get("life") or {})
    if key in life:
        return life.get(key)
    legacy = ((traits or {}).get("life_constraints") or {})
    if key == "kids_intent":
        return legacy.get("kids_preference", default)
    if key == "kids_timeline":
        return legacy.get("kids_timeline", default)
    return default


# Legacy-compatible helpers used by existing tests
def _vector_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    sq = sum((x - y) ** 2 for x, y in zip(a, b))
    max_dist = len(a) ** 0.5
    return max(0.0, 1.0 - (sq ** 0.5) / max_dist)


def _kids_compatible(k1: str | None, k2: str | None) -> bool:
    return not _kids_hard_mismatch(k1, k2)


def _modifier_penalty(u_traits: dict[str, Any], v_traits: dict[str, Any], cfg: dict[str, float]) -> tuple[float, dict[str, float]]:
    life_u = (u_traits or {}).get("life_preferences") or {}
    life_v = (v_traits or {}).get("life_preferences") or {}
    mods_u = (u_traits or {}).get("modifiers") or {}
    mods_v = (v_traits or {}).get("modifiers") or {}

    mapping = {
        "marriage": "LA_MARRIAGE_01",
        "nyc": "LA_LOC_01",
        "career_intensity": "LA_CAREER_01",
        "faith": "LA_FAITH_01",
        "social_lifestyle": "LA_LIFESTYLE_01",
    }

    scale = float(cfg.get("modifier_penalty_scale", 0.35))
    cap = float(cfg.get("modifier_penalty_cap", 0.6))
    penalties: dict[str, float] = {}
    multiplier = 1.0

    for mod_key, life_key in mapping.items():
        u_pref = _to_float(life_u.get(life_key), 0.5)
        v_pref = _to_float(life_v.get(life_key), 0.5)
        mismatch = abs(u_pref - v_pref)

        u_mod = mods_u.get(mod_key) or {}
        v_mod = mods_v.get(mod_key) or {}
        importance = (_to_float(u_mod.get("importance"), 0.5) + _to_float(v_mod.get("importance"), 0.5)) / 2.0
        flexibility = (_to_float(u_mod.get("flexibility"), 0.5) + _to_float(v_mod.get("flexibility"), 0.5)) / 2.0

        penalty = mismatch * importance * (1.0 - flexibility) * scale
        penalty = min(cap, max(0.0, penalty))
        multiplier *= max(0.0, 1.0 - penalty)
        penalties[mod_key] = round(max(0.0, 1.0 - penalty), 6)

    return round(max(0.0, min(1.0, multiplier)), 6), penalties


def compute_compatibility(u_traits: dict[str, Any], v_traits: dict[str, Any], cfg: dict[str, float] | None = None) -> dict[str, Any]:
    cfg = cfg or {}

    gates_triggered: list[str] = []
    penalties_applied: list[dict[str, float]] = []

    kids_u = str(_life(u_traits, "kids_intent", "unsure"))
    kids_v = str(_life(v_traits, "kids_intent", "unsure"))
    if _kids_hard_mismatch(kids_u, kids_v):
        gates_triggered.append("kids_hard_conflict")
        return {
            "score_total": 0.0,
            "score_breakdown": {
                "kids_hard_check": False,
                "gates": gates_triggered,
                "categories": {},
                "components": {},
                "penalties": penalties_applied,
            },
        }

    escalation_u = _dim(u_traits, "escalation")
    escalation_v = _dim(v_traits, "escalation")
    if escalation_u > float(cfg.get("ESCALATION_GATE", 0.95)) and escalation_v > float(cfg.get("ESCALATION_GATE", 0.95)):
        gates_triggered.append("safety_escalation_gate")
        return {
            "score_total": 0.0,
            "score_breakdown": {
                "kids_hard_check": True,
                "gates": gates_triggered,
                "categories": {},
                "components": {},
                "penalties": penalties_applied,
            },
        }

    # Legacy v1/v2 trait compatibility path for old tests/fixtures.
    if "dimensions" not in (u_traits or {}) and "dimensions" not in (v_traits or {}):
        u_big5 = (u_traits or {}).get("big5") or {}
        v_big5 = (v_traits or {}).get("big5") or {}
        u_conf = (u_traits or {}).get("conflict_repair") or {}
        v_conf = (v_traits or {}).get("conflict_repair") or {}

        big5_vec_u = [
            _to_float(u_big5.get("openness"), 0.5),
            _to_float(u_big5.get("conscientiousness"), 0.5),
            _to_float(u_big5.get("extraversion"), 0.5),
            _to_float(u_big5.get("agreeableness"), 0.5),
            _to_float(u_big5.get("neuroticism"), 0.5),
        ]
        big5_vec_v = [
            _to_float(v_big5.get("openness"), 0.5),
            _to_float(v_big5.get("conscientiousness"), 0.5),
            _to_float(v_big5.get("extraversion"), 0.5),
            _to_float(v_big5.get("agreeableness"), 0.5),
            _to_float(v_big5.get("neuroticism"), 0.5),
        ]
        conflict_vec_u = [
            _to_float(u_conf.get("repair_willingness"), 0.5),
            _to_float(u_conf.get("escalation"), 0.5),
            _to_float(u_conf.get("cooldown_need"), 0.5),
            _to_float(u_conf.get("grudge_tendency"), 0.5),
        ]
        conflict_vec_v = [
            _to_float(v_conf.get("repair_willingness"), 0.5),
            _to_float(v_conf.get("escalation"), 0.5),
            _to_float(v_conf.get("cooldown_need"), 0.5),
            _to_float(v_conf.get("grudge_tendency"), 0.5),
        ]

        big5_similarity = _vector_similarity(big5_vec_u, big5_vec_v)
        conflict_similarity = _vector_similarity(conflict_vec_u, conflict_vec_v)
        modifier_multiplier, _ = _modifier_penalty(u_traits, v_traits, cfg)

        base_score = (
            float(cfg.get("big5_weight", 0.7)) * big5_similarity
            + float(cfg.get("conflict_weight", 0.3)) * conflict_similarity
        )
        total = max(0.0, min(1.0, base_score * modifier_multiplier))

        return {
            "score_total": round(total, 6),
            "score_breakdown": {
                "kids_hard_check": True,
                "big5_similarity": round(big5_similarity, 6),
                "conflict_similarity": round(conflict_similarity, 6),
                "modifier_multiplier": round(modifier_multiplier, 6),
                "base_score": round(base_score, 6),
                "gates": gates_triggered,
                "categories": {},
                "components": {},
                "penalties": penalties_applied,
            },
        }

    # Component scores
    values_similarity = _sim(_dim(u_traits, "worldview_alignment"), _dim(v_traits, "worldview_alignment"))
    emo_similarity = _sim(_dim(u_traits, "stability"), _dim(v_traits, "stability"))

    reassurance_vs_independence = (
        _comp(_dim(u_traits, "reassurance_need"), _dim(v_traits, "independence_need"))
        + _comp(_dim(v_traits, "reassurance_need"), _dim(u_traits, "independence_need"))
    ) / 2.0
    text_similarity = _sim(_dim(u_traits, "text_sensitivity"), _dim(v_traits, "text_sensitivity"))
    drama_similarity = _sim(_dim(u_traits, "drama_avoidance"), _dim(v_traits, "drama_avoidance"))
    testing_similarity = _sim(_dim(u_traits, "testing_behavior"), _dim(v_traits, "testing_behavior"))

    approach_withdrawal = (
        _comp(_dim(u_traits, "approach"), _dim(v_traits, "withdrawal"))
        + _comp(_dim(v_traits, "approach"), _dim(u_traits, "withdrawal"))
    ) / 2.0
    escalation_risk = 1.0 - max(escalation_u, escalation_v)
    repair_similarity = _sim(_dim(u_traits, "repair_belief"), _dim(v_traits, "repair_belief"))
    structure_similarity = _sim(_dim(u_traits, "structure"), _dim(v_traits, "structure"))

    extraversion_comp = _comp(_dim(u_traits, "extraversion"), _dim(v_traits, "extraversion"))
    conscientiousness_comp = _comp(_dim(u_traits, "conscientiousness"), _dim(v_traits, "conscientiousness"))

    relocation_similarity = _sim(_dim(u_traits, "relocation_openness"), _dim(v_traits, "relocation_openness"))
    career_similarity = _sim(_dim(u_traits, "career_intensity"), _dim(v_traits, "career_intensity"))
    intentions_similarity = _sim(_dim(u_traits, "define_intentions_early"), _dim(v_traits, "define_intentions_early"))

    kids_timeline_score = 0.5
    if kids_u in {"yes", "probably"} and kids_v in {"yes", "probably"}:
        kids_timeline_score = _sim(_dim(u_traits, "kids_timeline_value"), _dim(v_traits, "kids_timeline_value"))

    values_bucket = values_similarity
    attachment_bucket = (
        0.10 * reassurance_vs_independence
        + 0.06 * text_similarity
        + 0.03 * drama_similarity
        + 0.03 * testing_similarity
    ) / 0.22
    conflict_bucket = (
        0.08 * approach_withdrawal
        + 0.08 * escalation_risk
        + 0.04 * repair_similarity
        + 0.04 * structure_similarity
    ) / 0.24
    personality_bucket = (0.06 * extraversion_comp + 0.06 * conscientiousness_comp) / 0.12
    life_bucket = (0.03 * relocation_similarity + 0.03 * career_similarity + 0.02 * intentions_similarity) / 0.08

    total = (
        0.22 * values_similarity
        + 0.12 * emo_similarity
        + 0.10 * reassurance_vs_independence
        + 0.06 * text_similarity
        + 0.03 * drama_similarity
        + 0.03 * testing_similarity
        + 0.08 * approach_withdrawal
        + 0.08 * escalation_risk
        + 0.04 * repair_similarity
        + 0.04 * structure_similarity
        + 0.06 * extraversion_comp
        + 0.06 * conscientiousness_comp
        + 0.03 * relocation_similarity
        + 0.03 * career_similarity
        + 0.02 * intentions_similarity
    )

    if escalation_u > float(cfg.get("ESCALATION_PENALTY_THRESHOLD", 0.7)) and escalation_v > float(cfg.get("ESCALATION_PENALTY_THRESHOLD", 0.7)):
        total *= float(cfg.get("ESCALATION_PENALTY_MULTIPLIER", 0.75))
        penalties_applied.append({"two_escalators": float(cfg.get("ESCALATION_PENALTY_MULTIPLIER", 0.75))})

    withdrawal_u = _dim(u_traits, "withdrawal")
    withdrawal_v = _dim(v_traits, "withdrawal")
    if withdrawal_u > float(cfg.get("WITHDRAWAL_PENALTY_THRESHOLD", 0.7)) and withdrawal_v > float(cfg.get("WITHDRAWAL_PENALTY_THRESHOLD", 0.7)):
        total *= float(cfg.get("WITHDRAWAL_PENALTY_MULTIPLIER", 0.85))
        penalties_applied.append({"two_withdrawers": float(cfg.get("WITHDRAWAL_PENALTY_MULTIPLIER", 0.85))})

    if _dim(u_traits, "reassurance_need") > 0.8 and _dim(v_traits, "independence_need") > 0.8:
        total *= float(cfg.get("MISMATCH_PENALTY_MULTIPLIER", 0.8))
        penalties_applied.append({"reassurance_independence_u_to_v": float(cfg.get("MISMATCH_PENALTY_MULTIPLIER", 0.8))})
    if _dim(v_traits, "reassurance_need") > 0.8 and _dim(u_traits, "independence_need") > 0.8:
        total *= float(cfg.get("MISMATCH_PENALTY_MULTIPLIER", 0.8))
        penalties_applied.append({"reassurance_independence_v_to_u": float(cfg.get("MISMATCH_PENALTY_MULTIPLIER", 0.8))})

    total = max(0.0, min(1.0, total))

    return {
        "score_total": round(total, 6),
        "score_breakdown": {
            "kids_hard_check": True,
            "gates": gates_triggered,
            "categories": {
                "values_similarity": round(values_bucket, 6),
                "attachment_fit": round(attachment_bucket, 6),
                "conflict_fit": round(conflict_bucket, 6),
                "personality_fit": round(personality_bucket, 6),
                "life_fit": round(life_bucket, 6),
                "emotional_similarity": round(emo_similarity, 6),
                "kids_timeline_similarity": round(kids_timeline_score, 6),
            },
            "components": {
                "values_similarity": round(values_similarity, 6),
                "reassurance_vs_independence": round(reassurance_vs_independence, 6),
                "text_sensitivity_similarity": round(text_similarity, 6),
                "drama_avoidance_similarity": round(drama_similarity, 6),
                "testing_behavior_similarity": round(testing_similarity, 6),
                "approach_withdrawal_complement": round(approach_withdrawal, 6),
                "escalation_risk": round(escalation_risk, 6),
                "repair_similarity": round(repair_similarity, 6),
                "structure_similarity": round(structure_similarity, 6),
                "extraversion_complement": round(extraversion_comp, 6),
                "conscientiousness_complement": round(conscientiousness_comp, 6),
                "relocation_similarity": round(relocation_similarity, 6),
                "career_similarity": round(career_similarity, 6),
                "intentions_similarity": round(intentions_similarity, 6),
            },
            "penalties": penalties_applied,
            "base_score": round(total, 6),
        },
    }


def build_candidate_pairs(
    users: list[dict[str, Any]],
    cfg: dict[str, float] | None = None,
    recent_pairs: set[tuple[str, str]] | None = None,
    blocked_pairs: set[tuple[str, str]] | None = None,
) -> list[MatchCandidate]:
    cfg = cfg or {}
    recent_pairs = recent_pairs or set()
    blocked_pairs = blocked_pairs or set()
    candidates: list[MatchCandidate] = []

    for i in range(len(users)):
        for j in range(i + 1, len(users)):
            u = users[i]
            v = users[j]
            pair_key = canonical_pair(u["user_id"], v["user_id"])
            if pair_key in recent_pairs:
                continue
            if pair_key in blocked_pairs:
                continue
            if not _gender_preference_compatible(u, v):
                continue

            comp = compute_compatibility(u.get("traits", {}), v.get("traits", {}), cfg=cfg)
            candidates.append(
                MatchCandidate(
                    user_id=u["user_id"],
                    matched_user_id=v["user_id"],
                    score_total=float(comp["score_total"]),
                    score_breakdown=comp["score_breakdown"],
                )
            )
    return candidates


def _stable_hash_eps(a: str, b: str, week_start: date | None) -> float:
    payload = f"{min(a,b)}|{max(a,b)}|{week_start.isoformat() if week_start else ''}"
    h = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    x = int(h[:12], 16) / float(16**12)
    return x * 1e-6


def _build_preference_lists(users: list[dict[str, Any]], pairs: list[MatchCandidate], min_score: float, top_k: int, week_start: date | None) -> dict[str, list[str]]:
    by_user: dict[str, list[tuple[str, float]]] = {u["user_id"]: [] for u in users}
    for p in pairs:
        if p.score_total < min_score:
            continue
        score = p.score_total + _stable_hash_eps(p.user_id, p.matched_user_id, week_start)
        by_user[p.user_id].append((p.matched_user_id, score))
        by_user[p.matched_user_id].append((p.user_id, score))

    prefs: dict[str, list[str]] = {}
    for uid, vals in by_user.items():
        vals.sort(key=lambda x: (-x[1], x[0]))
        prefs[uid] = [v for v, _ in vals[:top_k]]
    return prefs


def _is_bipartite_hetero_pool(users: list[dict[str, Any]]) -> bool:
    for u in users:
        g = _normalize_gender(u.get("gender_identity"))
        s = _parse_seeking(u.get("seeking_genders"))
        if g == "man" and s != {"woman"}:
            return False
        if g == "woman" and s != {"man"}:
            return False
        if g not in {"man", "woman"}:
            return False
    return True


def _stable_bipartite_match(users: list[dict[str, Any]], prefs: dict[str, list[str]]) -> list[tuple[str, str]]:
    men = [u["user_id"] for u in users if _normalize_gender(u.get("gender_identity")) == "man"]
    women = [u["user_id"] for u in users if _normalize_gender(u.get("gender_identity")) == "woman"]
    women_rank: dict[str, dict[str, int]] = {}
    for w in women:
        women_rank[w] = {m: i for i, m in enumerate(prefs.get(w, []))}

    free = men[:]
    next_idx = {m: 0 for m in men}
    engaged_to: dict[str, str] = {}  # woman -> man

    while free:
        m = free.pop(0)
        p = prefs.get(m, [])
        if next_idx[m] >= len(p):
            continue
        w = p[next_idx[m]]
        next_idx[m] += 1
        if w not in women_rank:
            free.append(m)
            continue
        current = engaged_to.get(w)
        if current is None:
            engaged_to[w] = m
            continue
        rank_map = women_rank[w]
        if rank_map.get(m, 10**9) < rank_map.get(current, 10**9):
            engaged_to[w] = m
            free.append(current)
        else:
            free.append(m)

    out: list[tuple[str, str]] = []
    for w, m in engaged_to.items():
        out.append((m, w))
    return out


def _stable_general_match(users: list[dict[str, Any]], prefs: dict[str, list[str]]) -> list[tuple[str, str]]:
    unmatched = {u["user_id"] for u in users}
    next_idx = {uid: 0 for uid in unmatched}
    held_by: dict[str, str] = {}  # accepter -> proposer

    def rank(of_user: str, candidate: str) -> int:
        pl = prefs.get(of_user, [])
        try:
            return pl.index(candidate)
        except ValueError:
            return 10**9

    active = True
    while active:
        active = False
        for proposer in sorted(list(unmatched)):
            pref = prefs.get(proposer, [])
            if next_idx[proposer] >= len(pref):
                continue
            active = True
            target = pref[next_idx[proposer]]
            next_idx[proposer] += 1
            current = held_by.get(target)
            if current is None:
                held_by[target] = proposer
                continue
            if rank(target, proposer) < rank(target, current):
                held_by[target] = proposer

    # Build mutual accepted pairs deterministically
    used: set[str] = set()
    pairs: list[tuple[str, str]] = []
    for target in sorted(held_by.keys()):
        proposer = held_by[target]
        if proposer in used or target in used:
            continue
        if held_by.get(proposer) == target or target in prefs.get(proposer, []):
            used.add(proposer)
            used.add(target)
            pairs.append(canonical_pair(proposer, target))
    uniq = sorted(set(pairs))
    return uniq


def stable_match(
    users: list[dict[str, Any]],
    pairs: list[MatchCandidate],
    *,
    min_score: float,
    top_k: int,
    mode: str,
    week_start_date: date | None,
) -> list[MatchCandidate]:
    pair_map = {canonical_pair(p.user_id, p.matched_user_id): p for p in pairs}
    prefs = _build_preference_lists(users, pairs, min_score=min_score, top_k=top_k, week_start=week_start_date)

    if mode == "stable_bipartite_if_possible" and _is_bipartite_hetero_pool(users):
        chosen = _stable_bipartite_match(users, prefs)
    else:
        chosen = _stable_general_match(users, prefs)

    assignments: list[MatchCandidate] = []
    for a, b in chosen:
        p = pair_map.get(canonical_pair(a, b))
        if not p or p.score_total < min_score:
            continue
        assignments.append(p)
    assignments.sort(key=lambda x: (-x.score_total, x.user_id, x.matched_user_id))
    return assignments


def greedy_one_to_one_match(pairs: list[MatchCandidate], min_score: float) -> list[MatchCandidate]:
    matched: set[str] = set()
    assignments: list[MatchCandidate] = []
    for pair in sorted(pairs, key=lambda p: (-p.score_total, p.user_id, p.matched_user_id)):
        if pair.score_total < min_score:
            continue
        if pair.user_id in matched or pair.matched_user_id in matched:
            continue
        matched.add(pair.user_id)
        matched.add(pair.matched_user_id)
        assignments.append(pair)
    return assignments


def fetch_eligible_users(db, survey_slug: str, survey_version: int, tenant_id: str | None = None) -> list[dict[str, Any]]:
    rows = db.execute(
        text(
            """
            SELECT DISTINCT
              us.user_id,
              ut.traits,
              COALESCE(NULLIF(TRIM(up.gender_identity), ''), NULLIF(TRIM(ua.gender_identity), '')) AS gender_identity,
              CASE
                WHEN up.seeking_genders IS NOT NULL
                     AND jsonb_typeof(up.seeking_genders) = 'array'
                     AND COALESCE(jsonb_array_length(up.seeking_genders), 0) > 0
                  THEN up.seeking_genders
                WHEN ua.seeking_genders IS NOT NULL
                     AND jsonb_typeof(ua.seeking_genders) = 'array'
                     AND COALESCE(jsonb_array_length(ua.seeking_genders), 0) > 0
                  THEN ua.seeking_genders
                ELSE '[]'::jsonb
              END AS seeking_genders
            FROM survey_session us
            JOIN user_traits ut
              ON ut.user_id = us.user_id
             AND ut.survey_slug = us.survey_slug
             AND ut.survey_version = us.survey_version
            JOIN user_account ua
              ON ua.id = CAST(us.user_id AS uuid)
            LEFT JOIN user_profile up
              ON up.user_id = ua.id
            LEFT JOIN user_preferences pref
              ON pref.user_id = CAST(us.user_id AS uuid)
            WHERE us.survey_slug = :survey_slug
              AND us.survey_version = :survey_version
              AND us.status = 'completed'
              AND COALESCE(pref.pause_matches, FALSE) = FALSE
              AND (:tenant_id IS NULL OR ua.tenant_id = CAST(:tenant_id AS uuid))
            """
        ),
        {"survey_slug": survey_slug, "survey_version": survey_version, "tenant_id": tenant_id},
    ).mappings().all()

    eligible = []
    for row in rows:
        raw_user_id = str(row["user_id"])
        try:
            uid = str(uuid.UUID(raw_user_id))
        except ValueError:
            continue

        # ut.survey_slug/ut.survey_version are already enforced in SQL join.
        # Do not require duplicated metadata keys inside traits JSON payload.
        traits = row["traits"] if isinstance(row.get("traits"), dict) else {}

        eligible.append(
            {
                "user_id": uid,
                "traits": traits,
                "gender_identity": row.get("gender_identity"),
                "seeking_genders": row.get("seeking_genders") if isinstance(row.get("seeking_genders"), list) else [],
            }
        )
    return eligible


def fetch_eligibility_debug_counts(db, survey_slug: str, survey_version: int, tenant_id: str | None = None) -> dict[str, int]:
    row = db.execute(
        text(
            """
            WITH users AS (
              SELECT
                ua.id AS user_id,
                ua.tenant_id,
                COALESCE(NULLIF(TRIM(up.gender_identity), ''), NULLIF(TRIM(ua.gender_identity), '')) AS gender_identity,
                CASE
                  WHEN up.seeking_genders IS NOT NULL
                       AND jsonb_typeof(up.seeking_genders) = 'array'
                       AND jsonb_array_length(up.seeking_genders) > 0
                    THEN up.seeking_genders
                  WHEN ua.seeking_genders IS NOT NULL
                       AND jsonb_typeof(ua.seeking_genders) = 'array'
                       AND jsonb_array_length(ua.seeking_genders) > 0
                    THEN ua.seeking_genders
                  ELSE '[]'::jsonb
                END AS seeking_genders,
                COALESCE(pref.pause_matches, FALSE) AS pause_matches,
                EXISTS (
                  SELECT 1
                  FROM survey_session ss
                  WHERE ss.user_id = CAST(ua.id AS text)
                    AND ss.survey_slug = :survey_slug
                    AND ss.survey_version = :survey_version
                    AND ss.status = 'completed'
                ) AS has_completed_session,
                EXISTS (
                  SELECT 1
                  FROM user_traits ut
                  WHERE ut.user_id = CAST(ua.id AS text)
                    AND ut.survey_slug = :survey_slug
                    AND ut.survey_version = :survey_version
                ) AS has_traits
              FROM user_account ua
              LEFT JOIN user_profile up ON up.user_id = ua.id
              LEFT JOIN user_preferences pref ON pref.user_id = ua.id
              WHERE ua.disabled_at IS NULL
                AND (:tenant_id IS NULL OR ua.tenant_id = CAST(:tenant_id AS uuid))
            )
            SELECT
              COUNT(1) AS total_active_users,
              SUM(CASE WHEN has_completed_session THEN 1 ELSE 0 END) AS users_with_completed_session,
              SUM(CASE WHEN has_traits THEN 1 ELSE 0 END) AS users_with_traits,
              SUM(CASE WHEN has_completed_session AND has_traits THEN 1 ELSE 0 END) AS users_with_completed_and_traits,
              SUM(CASE WHEN gender_identity IS NOT NULL THEN 1 ELSE 0 END) AS users_with_gender,
              SUM(CASE WHEN COALESCE(jsonb_array_length(seeking_genders), 0) > 0 THEN 1 ELSE 0 END) AS users_with_seeking,
              SUM(CASE WHEN pause_matches THEN 1 ELSE 0 END) AS users_paused,
              SUM(
                CASE
                  WHEN has_completed_session
                   AND has_traits
                   AND gender_identity IS NOT NULL
                   AND COALESCE(jsonb_array_length(seeking_genders), 0) > 0
                   AND NOT pause_matches
                  THEN 1
                  ELSE 0
                END
              ) AS users_eligible_pre_pairing
            FROM users
            """
        ),
        {
            "survey_slug": survey_slug,
            "survey_version": survey_version,
            "tenant_id": tenant_id,
        },
    ).mappings().first() or {}

    return {
        "total_active_users": int(row.get("total_active_users") or 0),
        "users_with_completed_session": int(row.get("users_with_completed_session") or 0),
        "users_with_traits": int(row.get("users_with_traits") or 0),
        "users_with_completed_and_traits": int(row.get("users_with_completed_and_traits") or 0),
        "users_with_gender": int(row.get("users_with_gender") or 0),
        "users_with_seeking": int(row.get("users_with_seeking") or 0),
        "users_paused": int(row.get("users_paused") or 0),
        "users_eligible_pre_pairing": int(row.get("users_eligible_pre_pairing") or 0),
    }


def fetch_recent_pairs(db, week_start_date: date, lookback_weeks: int) -> set[tuple[str, str]]:
    since = week_start_date - timedelta(days=7 * lookback_weeks)
    rows = db.execute(
        text(
            """
            SELECT user_id, matched_user_id
            FROM weekly_match_assignment
            WHERE week_start_date < :week_start_date
              AND week_start_date >= :since
              AND matched_user_id IS NOT NULL
              AND status <> 'no_match'
            """
        ),
        {"week_start_date": week_start_date, "since": since},
    ).mappings().all()
    return {canonical_pair(str(r["user_id"]), str(r["matched_user_id"])) for r in rows}


def fetch_recent_pairs_for_tenant(db, week_start_date: date, lookback_weeks: int, tenant_id: str | None) -> set[tuple[str, str]]:
    since = week_start_date - timedelta(days=7 * lookback_weeks)
    rows = db.execute(
        text(
            """
            SELECT user_id, matched_user_id
            FROM weekly_match_assignment
            WHERE week_start_date < :week_start_date
              AND week_start_date >= :since
              AND matched_user_id IS NOT NULL
              AND status <> 'no_match'
              AND (:tenant_id IS NULL OR tenant_id = CAST(:tenant_id AS uuid))
            """
        ),
        {"week_start_date": week_start_date, "since": since, "tenant_id": tenant_id},
    ).mappings().all()
    return {canonical_pair(str(r["user_id"]), str(r["matched_user_id"])) for r in rows}


def was_matched_recently(db, user_a: str, user_b: str, week_start_date: date, lookback_weeks: int) -> bool:
    return canonical_pair(user_a, user_b) in fetch_recent_pairs(db, week_start_date, lookback_weeks)


def create_weekly_assignments(
    db,
    week_start_date: date,
    expires_at: datetime,
    assignments: list[MatchCandidate],
    unmatched_user_ids: set[str],
    tenant_id: str | None = None,
) -> int:
    created = 0

    for pair in assignments:
        for user_id, matched_user_id in [(pair.user_id, pair.matched_user_id), (pair.matched_user_id, pair.user_id)]:
            db.execute(
                text(
                    """
                    INSERT INTO weekly_match_assignment
                    (id, week_start_date, user_id, matched_user_id, score_total, score_breakdown, status, expires_at, tenant_id)
                    VALUES (:id, :week_start_date, CAST(:user_id AS uuid), CAST(:matched_user_id AS uuid), :score_total, CAST(:score_breakdown AS jsonb), 'proposed', :expires_at, CAST(NULLIF(:tenant_id, '') AS uuid))
                    ON CONFLICT (week_start_date, user_id)
                    DO NOTHING
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "week_start_date": week_start_date,
                    "user_id": user_id,
                    "matched_user_id": matched_user_id,
                    "score_total": pair.score_total,
                    "score_breakdown": json.dumps(pair.score_breakdown),
                    "expires_at": expires_at,
                    "tenant_id": tenant_id or "",
                },
            )
            created += 1

    for user_id in unmatched_user_ids:
        db.execute(
            text(
                """
                INSERT INTO weekly_match_assignment
                (id, week_start_date, user_id, matched_user_id, score_total, score_breakdown, status, expires_at, tenant_id)
                VALUES (:id, :week_start_date, CAST(:user_id AS uuid), NULL, NULL, CAST(:score_breakdown AS jsonb), 'no_match', :expires_at, CAST(NULLIF(:tenant_id, '') AS uuid))
                ON CONFLICT (week_start_date, user_id)
                DO NOTHING
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "week_start_date": week_start_date,
                "user_id": user_id,
                "score_breakdown": json.dumps({"reason": "below_min_score_or_no_candidate"}),
                "expires_at": expires_at,
                "tenant_id": tenant_id or "",
            },
        )
        created += 1

    return created
