from app.services.matching import build_candidate_pairs, compute_compatibility, greedy_one_to_one_match


def _user(
    user_id: str,
    kids: str,
    o: float,
    c: float,
    e: float,
    a: float,
    n: float,
    gender_identity: str | None = None,
    seeking_genders: list[str] | None = None,
):
    return {
        "user_id": user_id,
        "gender_identity": gender_identity,
        "seeking_genders": seeking_genders or [],
        "traits": {
            "big5": {
                "openness": o,
                "conscientiousness": c,
                "extraversion": e,
                "agreeableness": a,
                "neuroticism": n,
            },
            "conflict_repair": {
                "repair_willingness": 0.7,
                "escalation": 0.2,
                "cooldown_need": 0.5,
                "grudge_tendency": 0.3,
            },
            "life_constraints": {"kids_preference": kids},
            "life_preferences": {
                "LA_MARRIAGE_01": 0.8,
                "LA_LOC_01": 0.4,
                "LA_CAREER_01": 0.7,
                "LA_FAITH_01": 0.3,
                "LA_LIFESTYLE_01": 0.6,
            },
            "modifiers": {
                "marriage": {"importance": 0.8, "flexibility": 0.4},
                "nyc": {"importance": 0.6, "flexibility": 0.5},
                "career_intensity": {"importance": 0.7, "flexibility": 0.5},
                "faith": {"importance": 0.5, "flexibility": 0.5},
                "social_lifestyle": {"importance": 0.5, "flexibility": 0.5},
            },
        },
    }


def test_kids_hard_constraint_zero_score():
    u = _user("u1", "yes", 0.5, 0.5, 0.5, 0.5, 0.5)
    v = _user("u2", "no", 0.5, 0.5, 0.5, 0.5, 0.5)
    comp = compute_compatibility(u["traits"], v["traits"])
    assert comp["score_total"] == 0.0
    assert comp["score_breakdown"]["kids_hard_check"] is False


def test_repeat_avoidance_excludes_recent_pair():
    users = [
        _user("a", "yes", 0.7, 0.7, 0.6, 0.6, 0.4),
        _user("b", "yes", 0.68, 0.7, 0.61, 0.59, 0.42),
        _user("c", "yes", 0.3, 0.4, 0.8, 0.4, 0.6),
    ]
    pairs = build_candidate_pairs(users, recent_pairs={tuple(sorted(("a", "b")))})
    ab_present = any(set((p.user_id, p.matched_user_id)) == {"a", "b"} for p in pairs)
    assert ab_present is False


def test_min_score_threshold_behavior():
    users = [
        _user("u1", "yes", 0.9, 0.9, 0.9, 0.9, 0.1),
        _user("u2", "yes", 0.9, 0.9, 0.85, 0.88, 0.12),
        _user("u3", "yes", 0.1, 0.2, 0.1, 0.2, 0.9),
        _user("u4", "yes", 0.1, 0.2, 0.15, 0.25, 0.88),
    ]
    pairs = build_candidate_pairs(users)
    strict = greedy_one_to_one_match(pairs, min_score=0.8)
    relaxed = greedy_one_to_one_match(pairs, min_score=0.2)
    assert len(strict) <= len(relaxed)
    assert all(p.score_total >= 0.8 for p in strict)



def test_block_list_excludes_candidate_pair():
    users = [
        _user("a", "yes", 0.7, 0.7, 0.6, 0.6, 0.4),
        _user("b", "yes", 0.68, 0.7, 0.61, 0.59, 0.42),
        _user("c", "yes", 0.67, 0.69, 0.62, 0.58, 0.43),
    ]
    blocked = {tuple(sorted(("a", "b")))}
    pairs = build_candidate_pairs(users, blocked_pairs=blocked)
    assert all(set((p.user_id, p.matched_user_id)) != {"a", "b"} for p in pairs)


def test_gender_preferences_require_mutual_compatibility():
    users = [
        _user("a", "yes", 0.7, 0.7, 0.6, 0.6, 0.4, gender_identity="man", seeking_genders=["woman"]),
        _user("b", "yes", 0.68, 0.7, 0.61, 0.59, 0.42, gender_identity="woman", seeking_genders=["man"]),
        _user("c", "yes", 0.67, 0.69, 0.62, 0.58, 0.43, gender_identity="man", seeking_genders=["man"]),
    ]

    pairs = build_candidate_pairs(users)
    pair_sets = {frozenset((p.user_id, p.matched_user_id)) for p in pairs}

    assert frozenset(("a", "b")) in pair_sets
    assert frozenset(("a", "c")) not in pair_sets
    assert frozenset(("b", "c")) not in pair_sets


def test_gender_preferences_missing_values_hard_fail_pairing():
    users = [
        _user("a", "yes", 0.7, 0.7, 0.6, 0.6, 0.4, gender_identity="man", seeking_genders=[]),
        _user("b", "yes", 0.68, 0.7, 0.61, 0.59, 0.42, gender_identity="woman", seeking_genders=["man"]),
    ]

    pairs = build_candidate_pairs(users)
    assert not any(set((p.user_id, p.matched_user_id)) == {"a", "b"} for p in pairs)
