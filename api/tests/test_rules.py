from app.services.rules import evaluate_show_if, item_is_visible


def test_show_if_eq_and_not_in():
    answers = {"CONSENT_FLIRTY_01": "ok", "LA_KIDS_01": "yes"}
    assert evaluate_show_if("eq", answers["CONSENT_FLIRTY_01"], "ok") is True
    assert evaluate_show_if("not_in", answers["LA_KIDS_01"], ["no", "probably_not"]) is True


def test_item_visibility_with_rules():
    rules = [
        {"type": "show_if", "trigger_question_code": "CONSENT_FLIRTY_01", "operator": "eq", "trigger_value": "ok"},
        {"type": "show_if", "trigger_question_code": "LA_KIDS_01", "operator": "not_in", "trigger_value": ["no"]},
    ]
    assert item_is_visible(rules, {"CONSENT_FLIRTY_01": "ok", "LA_KIDS_01": "yes"}) is True
    assert item_is_visible(rules, {"CONSENT_FLIRTY_01": "skip", "LA_KIDS_01": "yes"}) is False
