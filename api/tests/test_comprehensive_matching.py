"""
Comprehensive Matching Algorithm Tests
Independent evaluator test suite - identifies matching algorithm issues
"""
import pytest
import uuid
from datetime import date, datetime, timezone, timedelta

pytest.importorskip("fastapi")

from app.services.matching import (
    build_candidate_pairs,
    compute_compatibility,
    greedy_one_to_one_match,
    get_week_start_date,
    canonical_pair,
    _vector_similarity,
    _kids_compatible,
    _gender_preference_compatible,
    _modifier_penalty,
)


def _user(
    user_id: str,
    kids: str = "yes",
    openness: float = 0.5,
    conscientiousness: float = 0.5,
    extraversion: float = 0.5,
    agreeableness: float = 0.5,
    neuroticism: float = 0.5,
    repair_willingness: float = 0.5,
    escalation: float = 0.5,
    cooldown_need: float = 0.5,
    grudge_tendency: float = 0.5,
    gender_identity: str | None = None,
    seeking_genders: list[str] | None = None,
    marriage_pref: float = 0.5,
    nyc_pref: float = 0.5,
    career_pref: float = 0.5,
    faith_pref: float = 0.5,
    lifestyle_pref: float = 0.5,
    marriage_importance: float = 0.5,
    marriage_flexibility: float = 0.5,
):
    """Factory for creating user objects with traits"""
    return {
        "user_id": user_id,
        "gender_identity": gender_identity,
        "seeking_genders": seeking_genders or [],
        "traits": {
            "big5": {
                "openness": openness,
                "conscientiousness": conscientiousness,
                "extraversion": extraversion,
                "agreeableness": agreeableness,
                "neuroticism": neuroticism,
            },
            "conflict_repair": {
                "repair_willingness": repair_willingness,
                "escalation": escalation,
                "cooldown_need": cooldown_need,
                "grudge_tendency": grudge_tendency,
            },
            "life_constraints": {"kids_preference": kids},
            "life_preferences": {
                "LA_MARRIAGE_01": marriage_pref,
                "LA_LOC_01": nyc_pref,
                "LA_CAREER_01": career_pref,
                "LA_FAITH_01": faith_pref,
                "LA_LIFESTYLE_01": lifestyle_pref,
            },
            "modifiers": {
                "marriage": {"importance": marriage_importance, "flexibility": marriage_flexibility},
                "nyc": {"importance": 0.5, "flexibility": 0.5},
                "career_intensity": {"importance": 0.5, "flexibility": 0.5},
                "faith": {"importance": 0.5, "flexibility": 0.5},
                "social_lifestyle": {"importance": 0.5, "flexibility": 0.5},
            },
        },
    }


class TestCompatibilityScoring:
    """Tests for the compatibility scoring algorithm"""

    def test_identical_users_high_similarity(self):
        """ISSUE: Identical users should have very high compatibility"""
        u = _user("u1", gender_identity="man", seeking_genders=["woman"])
        v = _user("v1", gender_identity="woman", seeking_genders=["man"])
        
        # Make traits identical
        for key in ["openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"]:
            v["traits"]["big5"][key] = u["traits"]["big5"][key]
        for key in ["repair_willingness", "escalation", "cooldown_need", "grudge_tendency"]:
            v["traits"]["conflict_repair"][key] = u["traits"]["conflict_repair"][key]
        
        comp = compute_compatibility(u["traits"], v["traits"])
        assert comp["score_total"] > 0.9, f"Expected high score, got {comp['score_total']}"

    def test_opposite_users_lower_similarity(self):
        """ISSUE: Very different users should have lower compatibility"""
        u = _user("u1", openness=0.9, conscientiousness=0.9, extraversion=0.9, 
                  agreeableness=0.9, neuroticism=0.1, gender_identity="man", seeking_genders=["woman"])
        v = _user("v1", openness=0.1, conscientiousness=0.1, extraversion=0.1, 
                  agreeableness=0.1, neuroticism=0.9, gender_identity="woman", seeking_genders=["man"])
        
        comp = compute_compatibility(u["traits"], v["traits"])
        assert comp["score_total"] < 0.7, f"Expected lower score for opposite users, got {comp['score_total']}"

    def test_kids_hard_constraint_yes_vs_no(self):
        """ISSUE: yes vs no on kids should zero the score"""
        u = _user("u1", kids="yes")
        v = _user("v1", kids="no")
        
        comp = compute_compatibility(u["traits"], v["traits"])
        assert comp["score_total"] == 0.0, "Kids incompatibility should zero score"
        assert comp["score_breakdown"]["kids_hard_check"] is False

    def test_kids_hard_constraint_yes_vs_probably_not(self):
        """ISSUE: yes vs probably_not should zero the score"""
        u = _user("u1", kids="yes")
        v = _user("v1", kids="probably_not")
        
        comp = compute_compatibility(u["traits"], v["traits"])
        assert comp["score_total"] == 0.0

    def test_kids_hard_constraint_no_vs_probably(self):
        """ISSUE: no vs probably should zero the score"""
        u = _user("u1", kids="no")
        v = _user("v1", kids="probably")
        
        comp = compute_compatibility(u["traits"], v["traits"])
        assert comp["score_total"] == 0.0

    def test_kids_compatible_yes_vs_probably(self):
        """ISSUE: yes vs probably should be compatible"""
        u = _user("u1", kids="yes")
        v = _user("v1", kids="probably")
        
        comp = compute_compatibility(u["traits"], v["traits"])
        assert comp["score_breakdown"]["kids_hard_check"] is True
        assert comp["score_total"] > 0.0

    def test_kids_compatible_no_vs_probably_not(self):
        """ISSUE: no vs probably_not should be compatible"""
        u = _user("u1", kids="no")
        v = _user("v1", kids="probably_not")
        
        comp = compute_compatibility(u["traits"], v["traits"])
        assert comp["score_breakdown"]["kids_hard_check"] is True
        assert comp["score_total"] > 0.0

    def test_score_never_exceeds_1(self):
        """ISSUE: Score should be capped at 1.0"""
        u = _user("u1")
        v = _user("v1")
        
        # Even with perfect match
        for key in u["traits"]["big5"]:
            u["traits"]["big5"][key] = 0.5
            v["traits"]["big5"][key] = 0.5
        
        comp = compute_compatibility(u["traits"], v["traits"])
        assert comp["score_total"] <= 1.0

    def test_score_never_below_0(self):
        """ISSUE: Score should never be negative"""
        u = _user("u1")
        v = _user("v1")
        
        comp = compute_compatibility(u["traits"], v["traits"])
        assert comp["score_total"] >= 0.0

    def test_modifier_penalty_applied(self):
        """ISSUE: Large preference mismatch should reduce score"""
        u = _user("u1", marriage_pref=0.9, marriage_importance=0.9, marriage_flexibility=0.1)
        v = _user("v1", marriage_pref=0.1, marriage_importance=0.9, marriage_flexibility=0.1)
        
        comp = compute_compatibility(u["traits"], v["traits"])
        assert comp["score_breakdown"]["modifier_multiplier"] < 1.0


class TestGenderPreferences:
    """Tests for gender preference matching"""

    def test_mutual_gender_preference_required(self):
        """ISSUE: Both users must match each other's gender preferences"""
        users = [
            _user("man1", gender_identity="man", seeking_genders=["woman"]),
            _user("woman1", gender_identity="woman", seeking_genders=["man"]),
        ]
        
        pairs = build_candidate_pairs(users)
        assert len(pairs) == 1

    def test_non_mutual_gender_preference_excluded(self):
        """ISSUE: Non-mutual preferences should be excluded"""
        users = [
            _user("man1", gender_identity="man", seeking_genders=["woman"]),
            _user("man2", gender_identity="man", seeking_genders=["woman"]),
        ]
        
        pairs = build_candidate_pairs(users)
        assert len(pairs) == 0, "Two men both seeking women should not be paired"

    def test_missing_gender_identity_excluded(self):
        """ISSUE: Missing gender identity should exclude from matching"""
        users = [
            _user("user1", gender_identity=None, seeking_genders=["woman"]),
            _user("woman1", gender_identity="woman", seeking_genders=["man"]),
        ]
        
        pairs = build_candidate_pairs(users)
        assert len(pairs) == 0

    def test_missing_seeking_genders_excluded(self):
        """ISSUE: Missing seeking_genders should exclude from matching"""
        users = [
            _user("man1", gender_identity="man", seeking_genders=[]),
            _user("woman1", gender_identity="woman", seeking_genders=["man"]),
        ]
        
        pairs = build_candidate_pairs(users)
        assert len(pairs) == 0

    def test_nonbinary_preference_supported(self):
        """ISSUE: Nonbinary preferences should work"""
        users = [
            _user("nb1", gender_identity="nonbinary", seeking_genders=["woman", "nonbinary"]),
            _user("woman1", gender_identity="woman", seeking_genders=["nonbinary"]),
        ]
        
        pairs = build_candidate_pairs(users)
        assert len(pairs) == 1

    def test_multiple_seeking_genders_supported(self):
        """ISSUE: Users can seek multiple genders"""
        users = [
            _user("bi1", gender_identity="woman", seeking_genders=["man", "woman", "nonbinary"]),
            _user("man1", gender_identity="man", seeking_genders=["woman"]),
        ]
        
        pairs = build_candidate_pairs(users)
        assert len(pairs) == 1


class TestMatchingConstraints:
    """Tests for matching constraints and exclusions"""

    def test_recent_pairs_excluded(self):
        """ISSUE: Recently matched pairs should not be rematched"""
        users = [
            _user("a", gender_identity="man", seeking_genders=["woman"]),
            _user("b", gender_identity="woman", seeking_genders=["man"]),
            _user("c", gender_identity="woman", seeking_genders=["man"]),
        ]
        
        # a and b were recently matched
        recent_pairs = {canonical_pair("a", "b")}
        pairs = build_candidate_pairs(users, recent_pairs=recent_pairs)
        
        # a should only pair with c
        pair_users = {frozenset((p.user_id, p.matched_user_id)) for p in pairs}
        assert frozenset(("a", "b")) not in pair_users
        assert frozenset(("a", "c")) in pair_users

    def test_blocked_pairs_excluded(self):
        """ISSUE: Blocked pairs should not be matched"""
        users = [
            _user("a", gender_identity="man", seeking_genders=["woman"]),
            _user("b", gender_identity="woman", seeking_genders=["man"]),
            _user("c", gender_identity="woman", seeking_genders=["man"]),
        ]
        
        blocked_pairs = {canonical_pair("a", "b")}
        pairs = build_candidate_pairs(users, blocked_pairs=blocked_pairs)
        
        pair_users = {frozenset((p.user_id, p.matched_user_id)) for p in pairs}
        assert frozenset(("a", "b")) not in pair_users

    def test_both_recent_and_blocked_excluded(self):
        """ISSUE: Both constraints should be applied"""
        users = [
            _user("a", gender_identity="man", seeking_genders=["woman"]),
            _user("b", gender_identity="woman", seeking_genders=["man"]),
            _user("c", gender_identity="woman", seeking_genders=["man"]),
            _user("d", gender_identity="woman", seeking_genders=["man"]),
        ]
        
        recent_pairs = {canonical_pair("a", "b")}
        blocked_pairs = {canonical_pair("a", "c")}
        pairs = build_candidate_pairs(users, recent_pairs=recent_pairs, blocked_pairs=blocked_pairs)
        
        pair_users = {frozenset((p.user_id, p.matched_user_id)) for p in pairs}
        assert frozenset(("a", "b")) not in pair_users  # Recent
        assert frozenset(("a", "c")) not in pair_users  # Blocked
        assert frozenset(("a", "d")) in pair_users      # Available


class TestGreedyMatching:
    """Tests for the greedy one-to-one matching algorithm"""

    def test_higher_scores_prioritized(self):
        """ISSUE: Higher compatibility scores should be prioritized"""
        users = [
            _user("a", openness=0.9, gender_identity="man", seeking_genders=["woman"]),
            _user("b", openness=0.9, gender_identity="woman", seeking_genders=["man"]),  # High match with a
            _user("c", openness=0.1, gender_identity="woman", seeking_genders=["man"]),  # Low match with a
        ]
        
        # Make a-b pair have highest score
        pairs = build_candidate_pairs(users)
        assignments = greedy_one_to_one_match(pairs, min_score=0.0)
        
        # Should match a with b (highest score)
        assert len(assignments) == 1
        assert {assignments[0].user_id, assignments[0].matched_user_id} == {"a", "b"}

    def test_one_to_one_constraint(self):
        """ISSUE: Each user can only be matched once"""
        users = [
            _user("a", gender_identity="man", seeking_genders=["woman"]),
            _user("b", gender_identity="woman", seeking_genders=["man"]),
            _user("c", gender_identity="woman", seeking_genders=["man"]),
        ]
        
        pairs = build_candidate_pairs(users)
        assignments = greedy_one_to_one_match(pairs, min_score=0.0)
        
        # Only one pair should be formed
        assert len(assignments) == 1

    def test_min_score_threshold(self):
        """ISSUE: Pairs below min_score should be excluded"""
        users = [
            _user("a", openness=0.1, neuroticism=0.9, gender_identity="man", seeking_genders=["woman"]),
            _user("b", openness=0.9, neuroticism=0.1, gender_identity="woman", seeking_genders=["man"]),
        ]
        
        pairs = build_candidate_pairs(users)
        assignments = greedy_one_to_one_match(pairs, min_score=0.99)  # Very high threshold
        
        assert len(assignments) == 0

    def test_no_users_no_pairs(self):
        """ISSUE: Empty user list should produce no pairs"""
        pairs = build_candidate_pairs([])
        assignments = greedy_one_to_one_match(pairs, min_score=0.0)
        
        assert len(assignments) == 0

    def test_odd_number_of_users(self):
        """ISSUE: Odd number of users should leave one unmatched"""
        users = [
            _user("a", gender_identity="man", seeking_genders=["woman"]),
            _user("b", gender_identity="woman", seeking_genders=["man"]),
            _user("c", gender_identity="woman", seeking_genders=["man"]),
        ]
        
        pairs = build_candidate_pairs(users)
        assignments = greedy_one_to_one_match(pairs, min_score=0.0)
        
        # One pair, one unmatched
        assert len(assignments) == 1


class TestWeekStartDate:
    """Tests for week start date calculation"""

    def test_week_start_is_monday(self):
        """ISSUE: Week start should always be a Monday"""
        # Test various dates
        test_dates = [
            datetime(2026, 2, 17, tzinfo=timezone.utc),  # Tuesday
            datetime(2026, 2, 18, tzinfo=timezone.utc),  # Wednesday
            datetime(2026, 2, 21, tzinfo=timezone.utc),  # Saturday
            datetime(2026, 2, 22, tzinfo=timezone.utc),  # Sunday
            datetime(2026, 2, 16, tzinfo=timezone.utc),  # Monday
        ]
        
        for dt in test_dates:
            week_start = get_week_start_date(dt)
            # Python weekday: Monday = 0
            assert week_start.weekday() == 0, f"Week start for {dt} should be Monday, got {week_start}"

    def test_week_start_same_week(self):
        """ISSUE: All days in same week should have same week_start"""
        # Note: get_week_start_date uses America/New_York timezone
        # UTC times that fall on different calendar days in NY may have different week starts
        # Test with times that are all mid-day in NY to avoid DST boundary issues
        dates_in_week_utc = [
            datetime(2026, 2, 16, hour=12, tzinfo=timezone.utc),  # Monday midday UTC = early Monday NY
            datetime(2026, 2, 17, hour=12, tzinfo=timezone.utc),  # Tuesday midday UTC
            datetime(2026, 2, 18, hour=12, tzinfo=timezone.utc),  # Wednesday midday UTC
            datetime(2026, 2, 19, hour=12, tzinfo=timezone.utc),  # Thursday midday UTC
            datetime(2026, 2, 20, hour=12, tzinfo=timezone.utc),  # Friday midday UTC
            datetime(2026, 2, 21, hour=12, tzinfo=timezone.utc),  # Saturday midday UTC
            datetime(2026, 2, 22, hour=12, tzinfo=timezone.utc),  # Sunday midday UTC
        ]
        
        week_starts = [get_week_start_date(dt) for dt in dates_in_week_utc]
        # All dates in the same week should map to the same Monday
        assert len(set(week_starts)) == 1, f"All days in same week should have same week_start, got {week_starts}"


class TestVectorSimilarity:
    """Tests for the vector similarity calculation"""

    def test_identical_vectors_similarity_one(self):
        """ISSUE: Identical vectors should have similarity 1.0"""
        vec = [0.5, 0.5, 0.5, 0.5, 0.5]
        sim = _vector_similarity(vec, vec)
        assert sim == 1.0

    def test_max_different_vectors_low_similarity(self):
        """ISSUE: Maximally different vectors should have low similarity"""
        vec1 = [0.0, 0.0, 0.0, 0.0, 0.0]
        vec2 = [1.0, 1.0, 1.0, 1.0, 1.0]
        sim = _vector_similarity(vec1, vec2)
        assert sim == 0.0

    def test_empty_vectors_zero_similarity(self):
        """ISSUE: Empty vectors should return 0"""
        assert _vector_similarity([], []) == 0.0

    def test_different_length_vectors_zero_similarity(self):
        """ISSUE: Different length vectors should return 0"""
        assert _vector_similarity([0.5, 0.5], [0.5, 0.5, 0.5]) == 0.0


class TestEdgeCases:
    """Edge case tests for the matching system"""

    def test_single_user_no_match(self):
        """ISSUE: Single user should produce no pairs"""
        users = [_user("a", gender_identity="man", seeking_genders=["woman"])]
        pairs = build_candidate_pairs(users)
        assert len(pairs) == 0

    def test_all_users_blocked(self):
        """ISSUE: When all potential matches are blocked, no pairs form"""
        users = [
            _user("a", gender_identity="man", seeking_genders=["woman"]),
            _user("b", gender_identity="woman", seeking_genders=["man"]),
        ]
        
        blocked_pairs = {canonical_pair("a", "b")}
        pairs = build_candidate_pairs(users, blocked_pairs=blocked_pairs)
        assert len(pairs) == 0

    def test_all_users_recently_matched(self):
        """ISSUE: When all potential matches are recent, no pairs form"""
        users = [
            _user("a", gender_identity="man", seeking_genders=["woman"]),
            _user("b", gender_identity="woman", seeking_genders=["man"]),
        ]
        
        recent_pairs = {canonical_pair("a", "b")}
        pairs = build_candidate_pairs(users, recent_pairs=recent_pairs)
        assert len(pairs) == 0

    def test_missing_traits_handled(self):
        """ISSUE: Missing traits should not crash"""
        u = {"user_id": "a", "gender_identity": "man", "seeking_genders": ["woman"], "traits": {}}
        v = {"user_id": "b", "gender_identity": "woman", "seeking_genders": ["man"], "traits": {}}
        
        # Should not raise
        comp = compute_compatibility(u["traits"], v["traits"])
        assert "score_total" in comp