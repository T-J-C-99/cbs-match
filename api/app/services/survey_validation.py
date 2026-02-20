from __future__ import annotations

from typing import Any

VALID_OPERATORS = {"eq", "neq", "in", "not_in"}
VALID_RESPONSE_TYPES = {"likert_1_5", "single_select", "forced_choice_pair"}
VALID_REGION_TAGS = {"GLOBAL", "CBS_NYC"}
VALID_USAGES = {"SCORING", "COPY_ONLY"}


def _is_scalar(value: Any) -> bool:
    return isinstance(value, (str, int, float, bool)) or value is None


def validate_survey_definition(definition: dict[str, Any]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []

    screens = definition.get("screens")
    if not isinstance(screens, list):
        return [{"code": "invalid_schema", "path": "screens", "message": "screens must be an array"}]

    option_sets = definition.get("option_sets") or {}
    if not isinstance(option_sets, dict):
        errors.append({"code": "invalid_schema", "path": "option_sets", "message": "option_sets must be an object"})
        option_sets = {}

    seen_screen_keys: set[str] = set()
    seen_question_codes: set[str] = set()
    question_options: dict[str, set[Any] | None] = {}
    all_items: list[tuple[int, int, dict[str, Any]]] = []

    for s_idx, screen in enumerate(screens):
        key = screen.get("key")
        screen_path = f"screens[{s_idx}]"
        if not isinstance(key, str) or not key.strip():
            errors.append({"code": "missing_screen_key", "path": f"{screen_path}.key", "message": "screen key is required"})
        elif key in seen_screen_keys:
            errors.append({"code": "duplicate_screen_key", "path": f"{screen_path}.key", "message": f"duplicate screen key '{key}'"})
        else:
            seen_screen_keys.add(key)

        items = screen.get("items")
        if not isinstance(items, list):
            errors.append({"code": "invalid_screen_items", "path": f"{screen_path}.items", "message": "items must be an array"})
            continue

        for i_idx, item in enumerate(items):
            item_path = f"{screen_path}.items[{i_idx}]"
            question = item.get("question") or {}
            code = question.get("code")
            if not isinstance(code, str) or not code.strip():
                errors.append({"code": "missing_question_code", "path": f"{item_path}.question.code", "message": "question code is required"})
                continue

            if code in seen_question_codes:
                errors.append({"code": "duplicate_question_code", "path": f"{item_path}.question.code", "message": f"duplicate question code '{code}'"})
            else:
                seen_question_codes.add(code)

            # Validate response_type
            response_type = question.get("response_type")
            if response_type and response_type not in VALID_RESPONSE_TYPES:
                errors.append({
                    "code": "invalid_response_type",
                    "path": f"{item_path}.question.response_type",
                    "message": f"response_type '{response_type}' must be one of {sorted(VALID_RESPONSE_TYPES)}",
                })

            region_tag = question.get("region_tag")
            if region_tag not in VALID_REGION_TAGS:
                errors.append(
                    {
                        "code": "invalid_region_tag",
                        "path": f"{item_path}.question.region_tag",
                        "message": f"region_tag must be one of {sorted(VALID_REGION_TAGS)}",
                    }
                )

            usage = question.get("usage")
            if usage not in VALID_USAGES:
                errors.append(
                    {
                        "code": "invalid_usage",
                        "path": f"{item_path}.question.usage",
                        "message": f"usage must be one of {sorted(VALID_USAGES)}",
                    }
                )

            opts = item.get("options")
            if isinstance(opts, str):
                if opts not in option_sets:
                    errors.append({
                        "code": "missing_option_set",
                        "path": f"{item_path}.options",
                        "message": f"option_set '{opts}' not found",
                    })
                    question_options[code] = None
                else:
                    values = set()
                    for opt in option_sets.get(opts) or []:
                        if isinstance(opt, dict) and "value" in opt:
                            values.add(opt["value"])
                    question_options[code] = values if values else None
            elif isinstance(opts, list):
                values = set()
                for opt in opts:
                    if isinstance(opt, dict) and "value" in opt:
                        values.add(opt["value"])
                question_options[code] = values if values else None
            else:
                question_options[code] = None

            if response_type == "forced_choice_pair":
                forced_opts = None
                if isinstance(opts, list):
                    forced_opts = opts
                elif isinstance(opts, str):
                    forced_opts = option_sets.get(opts)

                if not isinstance(forced_opts, list) or len(forced_opts) != 2:
                    errors.append(
                        {
                            "code": "invalid_forced_choice_options",
                            "path": f"{item_path}.options",
                            "message": "forced_choice_pair must define exactly 2 options",
                        }
                    )
                else:
                    values = [opt.get("value") for opt in forced_opts if isinstance(opt, dict)]
                    labels = [str(opt.get("label", "")).strip() for opt in forced_opts if isinstance(opt, dict)]
                    if set(values) != {"A", "B"}:
                        errors.append(
                            {
                                "code": "invalid_forced_choice_values",
                                "path": f"{item_path}.options",
                                "message": "forced_choice_pair option values must be exactly 'A' and 'B'",
                            }
                        )
                    if any(not label for label in labels):
                        errors.append(
                            {
                                "code": "invalid_forced_choice_labels",
                                "path": f"{item_path}.options",
                                "message": "forced_choice_pair labels must be non-empty",
                            }
                        )

            all_items.append((s_idx, i_idx, item))

    for s_idx, i_idx, item in all_items:
        item_path = f"screens[{s_idx}].items[{i_idx}]"
        rules = item.get("rules") or []
        if not isinstance(rules, list):
            errors.append({"code": "invalid_rules", "path": f"{item_path}.rules", "message": "rules must be an array"})
            continue

        for r_idx, rule in enumerate(rules):
            rule_path = f"{item_path}.rules[{r_idx}]"
            if not isinstance(rule, dict):
                errors.append({"code": "invalid_rule", "path": rule_path, "message": "rule must be an object"})
                continue

            if rule.get("type") != "show_if":
                continue

            trigger_code = rule.get("trigger_question_code")
            operator = rule.get("operator")
            trigger_value = rule.get("trigger_value")

            if trigger_code not in seen_question_codes:
                errors.append({
                    "code": "unknown_trigger_question_code",
                    "path": f"{rule_path}.trigger_question_code",
                    "message": f"trigger question code '{trigger_code}' not found",
                })

            if operator not in VALID_OPERATORS:
                errors.append({
                    "code": "invalid_operator",
                    "path": f"{rule_path}.operator",
                    "message": f"operator must be one of {sorted(VALID_OPERATORS)}",
                })
                continue

            if operator in {"eq", "neq"}:
                if not _is_scalar(trigger_value):
                    errors.append({
                        "code": "invalid_trigger_value_shape",
                        "path": f"{rule_path}.trigger_value",
                        "message": "trigger_value must be a scalar for eq/neq",
                    })
                    continue
            elif operator in {"in", "not_in"}:
                if not isinstance(trigger_value, list):
                    errors.append({
                        "code": "invalid_trigger_value_shape",
                        "path": f"{rule_path}.trigger_value",
                        "message": "trigger_value must be an array for in/not_in",
                    })
                    continue

            allowed_values = question_options.get(trigger_code)
            if not allowed_values:
                continue

            if operator in {"eq", "neq"}:
                if trigger_value not in allowed_values:
                    errors.append({
                        "code": "invalid_trigger_value",
                        "path": f"{rule_path}.trigger_value",
                        "message": f"trigger_value '{trigger_value}' is not a valid option for '{trigger_code}'",
                    })
            else:
                bad = [v for v in trigger_value if v not in allowed_values]
                if bad:
                    errors.append({
                        "code": "invalid_trigger_values",
                        "path": f"{rule_path}.trigger_value",
                        "message": f"trigger values {bad} are not valid options for '{trigger_code}'",
                    })

    return errors
