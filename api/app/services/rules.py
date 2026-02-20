from typing import Any


def evaluate_show_if(operator: str, actual: Any, trigger_value: Any) -> bool:
    if operator == "eq":
        return actual == trigger_value
    if operator == "neq":
        return actual != trigger_value
    if operator == "in":
        return isinstance(trigger_value, list) and actual in trigger_value
    if operator == "not_in":
        return isinstance(trigger_value, list) and actual not in trigger_value
    return False


def item_is_visible(rules: list[dict[str, Any]], answers: dict[str, Any]) -> bool:
    if not rules:
        return True
    for rule in rules:
        if rule.get("type") != "show_if":
            continue
        code = rule.get("trigger_question_code")
        actual = answers.get(code)
        if not evaluate_show_if(rule.get("operator", ""), actual, rule.get("trigger_value")):
            return False
    return True
