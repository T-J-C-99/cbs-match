from app.traits import compute_traits


def _survey_def() -> dict:
    return {
        "screens": [
            {
                "key": "big_five",
                "items": [
                    {"question": {"code": "BF_O_05", "response_type": "likert_1_5", "reverse_coded": True}},
                    {"question": {"code": "BF_N_04", "response_type": "likert_1_5", "reverse_coded": True}},
                    {"question": {"code": "BF_C_01", "response_type": "likert_1_5", "reverse_coded": False}},
                ],
            },
            {
                "key": "conflict",
                "items": [
                    {"question": {"code": "CR_03", "response_type": "likert_1_5"}},
                    {"question": {"code": "CR_06", "response_type": "likert_1_5"}},
                    {"question": {"code": "CR_10", "response_type": "likert_1_5"}},
                    {"question": {"code": "CR_13", "response_type": "likert_1_5"}},
                ],
            },
            {
                "key": "life",
                "items": [
                    {"question": {"code": "LA_KIDS_01", "response_type": "single_select"}},
                    {"question": {"code": "MOD_KIDS_IMPORTANCE", "response_type": "likert_1_5"}},
                    {"question": {"code": "MOD_KIDS_FLEXIBILITY", "response_type": "likert_1_5"}},
                    {"question": {"code": "LA_MARRIAGE_01", "response_type": "likert_1_5"}},
                ],
            },
        ]
    }


def test_reverse_coding_exact_values():
    answers = {
        "BF_O_05": 1,
        "BF_N_04": 2,
        "BF_C_01": 5,
        "CR_03": 4,
        "CR_06": 1,
        "CR_10": 5,
        "CR_13": 2,
        "LA_KIDS_01": "yes",
        "MOD_KIDS_IMPORTANCE": 5,
        "MOD_KIDS_FLEXIBILITY": 2,
        "LA_MARRIAGE_01": 4,
    }
    traits = compute_traits(_survey_def(), answers)

    assert traits["traits_version"] == 2
    # BF_O_05 reverse from 1 to 5, normalized to 1.0
    assert traits["big5"]["openness"] == 1.0
    # BF_N_04 reverse from 2 to 4, normalized to 0.75
    assert traits["big5"]["neuroticism"] == 0.75
    # BF_C_01 direct from 5 normalized to 1.0
    assert traits["big5"]["conscientiousness"] == 1.0

    assert traits["life_constraints"]["kids_preference"] == "yes"
    assert traits["modifiers"]["kids"]["importance"] == 1.0
    assert traits["modifiers"]["kids"]["flexibility"] == 0.25
