from app.services.explanations import build_safe_explanation


def test_explanations_are_safe_and_no_sensitive_terms():
    score_breakdown = {
        "big5_similarity": 0.81,
        "conflict_similarity": 0.74,
        "kids_hard_check": True,
        "faith_alignment": 0.9,
    }
    user_traits = {"fun_answers": {"FUN_TRAVEL": "beach"}}
    matched_traits = {"fun_answers": {"FUN_TRAVEL": "mountains"}}

    out = build_safe_explanation(score_breakdown, user_traits, matched_traits)

    assert len(out["bullets"]) == 3
    text = " ".join(out["bullets"]).lower()
    assert "kids" not in text
    assert "faith" not in text
    assert len(out["icebreakers"]) == 2
