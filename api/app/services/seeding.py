import json
import random
import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text

from app.auth.security import hash_password
from app.services.matching import build_candidate_pairs
from app.services.rules import item_is_visible
from app.services.tenancy import sync_tenants_from_shared_config
from app.traits import compute_traits


CLUSTERS = {
    "grounded": {
        "weight": 0.35,
        "big5": {"O": 3.0, "C": 4.2, "E": 2.8, "A": 3.8, "N": 2.2},
        "conflict": 3.6,
        "kids_pref": {"yes": 3.0, "probably": 2.0, "unsure": 1.1, "probably_not": 0.8, "no": 0.7},
    },
    "social": {
        "weight": 0.35,
        "big5": {"O": 3.9, "C": 3.3, "E": 4.2, "A": 3.6, "N": 2.9},
        "conflict": 3.3,
        "kids_pref": {"yes": 1.8, "probably": 2.5, "unsure": 1.5, "probably_not": 1.2, "no": 1.0},
    },
    "intense": {
        "weight": 0.30,
        "big5": {"O": 4.0, "C": 3.9, "E": 3.3, "A": 2.9, "N": 3.8},
        "conflict": 2.8,
        "kids_pref": {"yes": 1.5, "probably": 2.2, "unsure": 1.6, "probably_not": 1.6, "no": 1.4},
    },
}

GENDER_OPTIONS = ["man", "woman", "nonbinary", "other"]
SEEKING_PROFILES: dict[str, list[list[str]]] = {
    "man": [["woman"], ["man"], ["woman", "man"], ["woman", "man", "nonbinary"]],
    "woman": [["man"], ["woman"], ["man", "woman"], ["man", "woman", "nonbinary"]],
    "nonbinary": [["man"], ["woman"], ["nonbinary"], ["man", "woman", "nonbinary"]],
    "other": [["man"], ["woman"], ["nonbinary"], ["man", "woman", "nonbinary", "other"]],
}


def _pick_cluster(rng: random.Random) -> str:
    names = list(CLUSTERS.keys())
    weights = [CLUSTERS[n]["weight"] for n in names]
    return rng.choices(names, weights=weights, k=1)[0]


def _bounded_likert(v: float) -> int:
    return max(1, min(5, int(round(v))))


def _option_list(item: dict[str, Any], option_sets: dict[str, Any]) -> list[dict[str, Any]]:
    opts = item.get("options")
    if isinstance(opts, str):
        return option_sets.get(opts, [])
    if isinstance(opts, list):
        return opts
    return []


def _weighted_choice(rng: random.Random, options: list[dict[str, Any]], weight_map: dict[Any, float] | None = None):
    if not options:
        return None
    if not weight_map:
        return rng.choice(options)["value"]
    values = [opt["value"] for opt in options]
    weights = [float(weight_map.get(v, 1.0)) for v in values]
    return rng.choices(values, weights=weights, k=1)[0]


def _cluster_likert_mean(code: str, cluster_name: str) -> float:
    c = CLUSTERS[cluster_name]
    if code.startswith("BF_O_"):
        return c["big5"]["O"]
    if code.startswith("BF_C_"):
        return c["big5"]["C"]
    if code.startswith("BF_E_"):
        return c["big5"]["E"]
    if code.startswith("BF_A_"):
        return c["big5"]["A"]
    if code.startswith("BF_N_"):
        return c["big5"]["N"]
    if code.startswith("CR_"):
        return c["conflict"]
    if code.endswith("_IMPORTANCE"):
        return 3.8
    if code.endswith("_FLEXIBILITY"):
        return 3.0
    return 3.2


def _generate_gender_preferences(rng: random.Random) -> tuple[str, list[str]]:
    gender = rng.choices(GENDER_OPTIONS, weights=[0.42, 0.42, 0.12, 0.04], k=1)[0]
    options = SEEKING_PROFILES.get(gender) or [["man", "woman"]]
    seeking = rng.choice(options)
    return gender, seeking


def _generate_seed_matchable_gender_preferences(index: int, rng: random.Random) -> tuple[str, list[str]]:
    """
    Keep seeded data broadly matchable across every tenant.
    Most rows are reciprocal man<->woman preference pairs, with a minority
    sampled from the broader distribution for realism.
    """
    if index % 5 != 0:
        if index % 2 == 0:
            return "man", ["woman"]
        return "woman", ["man"]
    return _generate_gender_preferences(rng)


def _slug_seed(slug: str) -> int:
    return sum(ord(ch) for ch in slug) % 997


def _normalize_domain(domain: str) -> str:
    return str(domain or "").strip().lower()


def _primary_domain(email_domains: list[str] | None) -> str:
    domains = [_normalize_domain(d) for d in (email_domains or []) if _normalize_domain(d)]
    return domains[0] if domains else "example.edu"


def _seed_contact_info(rng: random.Random, idx: int) -> tuple[str, str]:
    area_code = rng.choice(["212", "646", "917", "347", "929", "617", "415", "650"])
    exchange = 200 + ((idx * 7 + rng.randint(0, 299)) % 800)
    subscriber = 1000 + ((idx * 37 + rng.randint(0, 4999)) % 9000)
    phone = f"+1{area_code}{exchange:03d}{subscriber:04d}"
    instagram = f"seed_{idx:06d}_{rng.randint(10, 99)}"
    return phone, instagram


def _generate_answer(
    code: str,
    response_type: str,
    options: list[dict[str, Any]],
    rng: random.Random,
    cluster_name: str,
    clustered: bool,
    slider_config: dict[str, Any] | None = None,
):
    if response_type == "likert_1_5":
        base = _cluster_likert_mean(code, cluster_name) if clustered else 3.2
        return _bounded_likert(rng.normalvariate(base, 0.85))

    if response_type == "single_select":
        if code == "LA_KIDS_01":
            wm = (
                CLUSTERS[cluster_name]["kids_pref"]
                if clustered
                else {"yes": 3.1, "probably": 2.3, "unsure": 1.5, "probably_not": 1.4, "no": 1.2}
            )
            return _weighted_choice(rng, options, wm)
        if code == "CBS_CLUSTER":
            return _weighted_choice(rng, options, {"uris": 2.0, "warren": 2.0, "second_year": 1.5, "jterm": 1.5, "emba": 0.5, "prefer_not": 0.3})
        if code == "CBS_POST_MBA":
            return _weighted_choice(rng, options, {"pe_vc": 2.0, "consulting": 2.5, "investment_banking": 2.0, "tech": 2.0, "entrepreneurship": 1.5, "healthcare": 1.0, "real_estate": 1.0, "other": 1.5})
        if code == "NYC_NEIGHBORHOOD":
            return _weighted_choice(rng, options, {"ues": 2.5, "uws": 2.0, "murray_hill": 2.5, "hells_kitchen": 2.0, "west_village": 1.5, "soho": 1.0, "brooklyn": 1.5, "other": 1.0})
        if code == "WARM_01_WEEKEND":
            return _weighted_choice(rng, options, {"early_gym": 1.5, "brunch": 2.5, "sleep_in": 2.0, "productivity": 1.5})
        return _weighted_choice(rng, options, None)

    if response_type == "slider":
        min_val = (slider_config or {}).get("min", 0)
        max_val = (slider_config or {}).get("max", 100)
        base = (min_val + max_val) / 2
        val = int(rng.normalvariate(base, (max_val - min_val) / 4))
        return max(min_val, min(max_val, val))

    if response_type == "multi_select":
        if not options:
            return []
        n = rng.randint(1, min(3, len(options)))
        return rng.sample([opt["value"] for opt in options], n)

    return None


def _fill_missing_required_answers(
    *,
    survey_def: dict[str, Any],
    answers: dict[str, Any],
    rng: random.Random,
) -> None:
    option_sets = survey_def.get("option_sets", {})
    for screen in survey_def.get("screens", []):
        for item in screen.get("items", []):
            q = item.get("question", {})
            code = str(q.get("code") or "").strip()
            if not code:
                continue
            if not bool(q.get("is_required", False)) or bool(q.get("allow_skip", False)):
                continue
            if code in answers and answers.get(code) not in (None, ""):
                continue

            # Conditional required in traits logic.
            if code == "KIDS_02" and str(answers.get("KIDS_01") or "") not in {"yes", "probably"}:
                continue

            response_type = str(q.get("response_type") or "")
            options = _option_list(item, option_sets)

            if response_type == "likert_1_5":
                answers[code] = rng.randint(2, 4)
            elif response_type == "single_select":
                values = [opt.get("value") for opt in options if opt.get("value") is not None]
                if code.startswith("FC_"):
                    answers[code] = rng.choice(["A", "B"])
                elif values:
                    answers[code] = rng.choice(values)
            elif response_type == "multi_select":
                values = [opt.get("value") for opt in options if opt.get("value") is not None]
                if values:
                    answers[code] = [rng.choice(values)]
            elif response_type == "slider":
                slider = q.get("slider_config") or {}
                min_val = int(slider.get("min", 0))
                max_val = int(slider.get("max", 100))
                answers[code] = int((min_val + max_val) / 2)

    # Defensive fallback for match-core forced choice if not encoded as required in JSON metadata.
    for idx in range(1, 9):
        code = f"FC_0{idx}"
        if code not in answers or answers.get(code) in (None, ""):
            answers[code] = rng.choice(["A", "B"])


def _upsert_seed_user(
    db,
    *,
    tenant_id: str,
    user_id: str,
    email: str,
    username: str,
    password: str,
    display_name: str,
    cbs_year: str,
    hometown: str,
    phone_number: str,
    instagram_handle: str,
    photo_urls: list[str],
    gender_identity: str,
    seeking_genders: list[str],
) -> str:
    row = db.execute(
        text(
            """
            INSERT INTO user_account (
              id, tenant_id, email, username, password_hash, is_email_verified,
              display_name, cbs_year, hometown, phone_number, instagram_handle,
              photo_urls, gender_identity, seeking_genders
            )
            VALUES (
              CAST(:id AS uuid), CAST(:tenant_id AS uuid), :email, :username,
              :password_hash, TRUE, :display_name, :cbs_year, :hometown,
              :phone_number, :instagram_handle, CAST(:photo_urls AS jsonb),
              :gender_identity, CAST(:seeking_genders AS jsonb)
            )
            ON CONFLICT (tenant_id, lower(email))
            DO UPDATE SET
              username = EXCLUDED.username,
              password_hash = EXCLUDED.password_hash,
              display_name = EXCLUDED.display_name,
              cbs_year = EXCLUDED.cbs_year,
              hometown = EXCLUDED.hometown,
              phone_number = EXCLUDED.phone_number,
              instagram_handle = EXCLUDED.instagram_handle,
              photo_urls = EXCLUDED.photo_urls,
              gender_identity = EXCLUDED.gender_identity,
              seeking_genders = EXCLUDED.seeking_genders,
              is_email_verified = TRUE,
              disabled_at = NULL
            RETURNING id::text AS id
            """
        ),
        {
            "id": user_id,
            "tenant_id": tenant_id,
            "email": email,
            "username": username,
            "password_hash": hash_password(password),
            "display_name": display_name,
            "cbs_year": cbs_year,
            "hometown": hometown,
            "phone_number": phone_number,
            "instagram_handle": instagram_handle,
            "photo_urls": json.dumps(photo_urls),
            "gender_identity": gender_identity,
            "seeking_genders": json.dumps(seeking_genders),
        },
    ).mappings().first()

    resolved_user_id = str((row or {}).get("id") or user_id)

    db.execute(
        text(
            """
            INSERT INTO user_profile (
              user_id, tenant_id, display_name, cbs_year, hometown,
              phone_number, instagram_handle, photo_urls,
              gender_identity, seeking_genders, updated_at
            )
            VALUES (
              CAST(:user_id AS uuid), CAST(:tenant_id AS uuid), :display_name,
              :cbs_year, :hometown, :phone_number, :instagram_handle,
              CAST(:photo_urls AS jsonb), :gender_identity,
              CAST(:seeking_genders AS jsonb), NOW()
            )
            ON CONFLICT (user_id)
            DO UPDATE SET
              tenant_id = EXCLUDED.tenant_id,
              display_name = EXCLUDED.display_name,
              cbs_year = EXCLUDED.cbs_year,
              hometown = EXCLUDED.hometown,
              phone_number = EXCLUDED.phone_number,
              instagram_handle = EXCLUDED.instagram_handle,
              photo_urls = EXCLUDED.photo_urls,
              gender_identity = EXCLUDED.gender_identity,
              seeking_genders = EXCLUDED.seeking_genders,
              updated_at = NOW()
            """
        ),
        {
            "user_id": resolved_user_id,
            "tenant_id": tenant_id,
            "display_name": display_name,
            "cbs_year": cbs_year,
            "hometown": hometown,
            "phone_number": phone_number,
            "instagram_handle": instagram_handle,
            "photo_urls": json.dumps(photo_urls),
            "gender_identity": gender_identity,
            "seeking_genders": json.dumps(seeking_genders),
        },
    )

    db.execute(
        text(
            """
            INSERT INTO user_preferences (user_id, pause_matches, updated_at)
            VALUES (CAST(:user_id AS uuid), FALSE, NOW())
            ON CONFLICT (user_id)
            DO UPDATE SET pause_matches = FALSE, updated_at = NOW()
            """
        ),
        {"user_id": resolved_user_id},
    )

    return resolved_user_id


def _seed_survey_for_user(
    db,
    *,
    user_id: str,
    tenant_id: str,
    survey_def: dict[str, Any],
    survey_slug: str,
    survey_version: int,
    rng: random.Random,
    clustered: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    screens = sorted(survey_def.get("screens", []), key=lambda s: s.get("ordinal", 0))
    option_sets = survey_def.get("option_sets", {})
    answers: dict[str, Any] = {}
    cluster_name = _pick_cluster(rng) if clustered else "uniform"

    for screen in screens:
        for item in screen.get("items", []):
            if not item_is_visible(item.get("rules", []), answers):
                continue
            q = item.get("question", {})
            code = q.get("code")
            response_type = q.get("response_type")
            if not code or not response_type:
                continue
            val = _generate_answer(
                code,
                response_type,
                _option_list(item, option_sets),
                rng,
                cluster_name,
                clustered,
                q.get("slider_config"),
            )
            if val is None:
                continue
            if q.get("allow_skip") and rng.random() < 0.08:
                continue
            answers[code] = val

    _fill_missing_required_answers(survey_def=survey_def, answers=answers, rng=rng)

    traits = compute_traits(survey_def, answers)
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    db.execute(
        text(
            """
            INSERT INTO survey_session (id, user_id, survey_slug, survey_version, status, started_at, completed_at, tenant_id)
            VALUES (:id, :user_id, :survey_slug, :survey_version, 'completed', :started_at, :completed_at, CAST(:tenant_id AS uuid))
            """
        ),
        {
            "id": session_id,
            "user_id": user_id,
            "survey_slug": survey_slug,
            "survey_version": survey_version,
            "started_at": now,
            "completed_at": now,
            "tenant_id": tenant_id,
        },
    )

    for code, val in answers.items():
        db.execute(
            text(
                """
                INSERT INTO survey_answer (id, session_id, question_code, answer_value)
                VALUES (:id, :session_id, :question_code, CAST(:answer_value AS jsonb))
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "session_id": session_id,
                "question_code": code,
                "answer_value": json.dumps(val),
            },
        )

    db.execute(
        text(
            """
            INSERT INTO user_traits (id, user_id, survey_slug, survey_version, traits, tenant_id)
            VALUES (:id, :user_id, :survey_slug, :survey_version, CAST(:traits AS jsonb), CAST(:tenant_id AS uuid))
            ON CONFLICT (user_id, survey_slug, survey_version)
            DO UPDATE SET traits = EXCLUDED.traits, computed_at = NOW(), tenant_id = EXCLUDED.tenant_id
            """
        ),
        {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "survey_slug": survey_slug,
            "survey_version": survey_version,
            "traits": json.dumps(traits),
            "tenant_id": tenant_id,
        },
    )

    return answers, traits


def seed_dummy_data(
    db,
    survey_def: dict[str, Any],
    survey_slug: str,
    survey_version: int,
    n_users: int = 100,
    reset: bool = False,
    seed: int = 42,
    clustered: bool = False,
    tenant_slug: str | None = None,
    include_qa_login: bool = False,
    qa_password: str = "community123",
) -> dict[str, Any]:
    rng = random.Random(seed)

    tenant = db.execute(
        text(
            """
            SELECT id::text AS id, slug, name, email_domains
            FROM tenant
            WHERE (:tenant_slug IS NULL OR slug = :tenant_slug)
            ORDER BY CASE WHEN slug = 'cbs' THEN 0 ELSE 1 END, created_at ASC
            LIMIT 1
            """
        ),
        {"tenant_slug": tenant_slug},
    ).mappings().first()
    if not tenant:
        raise ValueError("No tenant found for seeding")

    tenant_id = str(tenant["id"])
    tenant_slug_out = str(tenant.get("slug") or "cbs")
    tenant_seed_offset = _slug_seed(tenant_slug_out)
    tenant_domain = _primary_domain(tenant.get("email_domains") if isinstance(tenant.get("email_domains"), list) else [])

    if reset:
        seeded_user_rows = db.execute(
            text(
                """
                SELECT id::text AS id
                FROM user_account
                WHERE tenant_id = CAST(:tenant_id AS uuid)
                """
            ),
            {
                "tenant_id": tenant_id,
            },
        ).mappings().all()
        seeded_user_ids = [str(r["id"]) for r in seeded_user_rows]

        db.execute(text("DELETE FROM chat_message WHERE tenant_id = CAST(:tenant_id AS uuid)"), {"tenant_id": tenant_id})
        db.execute(text("DELETE FROM chat_thread WHERE tenant_id = CAST(:tenant_id AS uuid)"), {"tenant_id": tenant_id})
        db.execute(text("DELETE FROM match_event WHERE tenant_id = CAST(:tenant_id AS uuid)"), {"tenant_id": tenant_id})
        db.execute(text("DELETE FROM match_feedback WHERE tenant_id = CAST(:tenant_id AS uuid)"), {"tenant_id": tenant_id})
        db.execute(text("DELETE FROM match_report WHERE tenant_id = CAST(:tenant_id AS uuid)"), {"tenant_id": tenant_id})
        db.execute(text("DELETE FROM weekly_match_assignment WHERE tenant_id = CAST(:tenant_id AS uuid)"), {"tenant_id": tenant_id})

        if seeded_user_ids:
            db.execute(
                text(
                    """
                    DELETE FROM survey_answer
                    WHERE session_id IN (
                      SELECT id FROM survey_session WHERE user_id::text = ANY(CAST(:seeded_user_ids AS text[]))
                    )
                    """
                ),
                {"seeded_user_ids": seeded_user_ids},
            )
            db.execute(text("DELETE FROM survey_session WHERE user_id::text = ANY(CAST(:seeded_user_ids AS text[]))"), {"seeded_user_ids": seeded_user_ids})
            db.execute(text("DELETE FROM user_traits WHERE user_id::text = ANY(CAST(:seeded_user_ids AS text[]))"), {"seeded_user_ids": seeded_user_ids})
            db.execute(text("DELETE FROM user_profile WHERE user_id::text = ANY(CAST(:seeded_user_ids AS text[]))"), {"seeded_user_ids": seeded_user_ids})
            db.execute(text("DELETE FROM user_preferences WHERE user_id::text = ANY(CAST(:seeded_user_ids AS text[]))"), {"seeded_user_ids": seeded_user_ids})
            db.execute(text("DELETE FROM notification_preference WHERE user_id::text = ANY(CAST(:seeded_user_ids AS text[]))"), {"seeded_user_ids": seeded_user_ids})
            db.execute(text("DELETE FROM user_account WHERE id::text = ANY(CAST(:seeded_user_ids AS text[]))"), {"seeded_user_ids": seeded_user_ids})

        db.commit()

    all_users_for_pairs: list[dict[str, Any]] = []
    all_users_traits: list[dict[str, Any]] = []
    kids_counter: Counter[str] = Counter()
    cluster_counter: Counter[str] = Counter()

    for i in range(n_users):
        user_id = str(uuid.uuid4())
        global_idx = tenant_seed_offset * 10000 + i + 1
        gender_identity, seeking_genders = _generate_seed_matchable_gender_preferences(i, rng)
        cbs_year = rng.choice(["26", "27"])
        hometown = rng.choice(["New York, NY", "Boston, MA", "Chicago, IL", "San Francisco, CA", "Austin, TX", "Seattle, WA"])
        display_name = f"{tenant_slug_out.upper()} Seed {i + 1}"
        email = f"seed_{tenant_slug_out}_{seed}_{i + 1}@{tenant_domain}"
        username = f"seed_{tenant_slug_out}_{i + 1}"
        phone_number, instagram_handle = _seed_contact_info(rng, global_idx)
        photo_urls = [
            f"https://picsum.photos/seed/{tenant_slug_out}-{seed}-{i + 1}-1/600/800",
            f"https://picsum.photos/seed/{tenant_slug_out}-{seed}-{i + 1}-2/600/800",
            f"https://picsum.photos/seed/{tenant_slug_out}-{seed}-{i + 1}-3/600/800",
        ]

        resolved_user_id = _upsert_seed_user(
            db,
            tenant_id=tenant_id,
            user_id=user_id,
            email=email,
            username=username,
            password="password123",
            display_name=display_name,
            cbs_year=cbs_year,
            hometown=hometown,
            phone_number=phone_number,
            instagram_handle=instagram_handle,
            photo_urls=photo_urls,
            gender_identity=gender_identity,
            seeking_genders=seeking_genders,
        )

        _, traits = _seed_survey_for_user(
            db,
            user_id=resolved_user_id,
            tenant_id=tenant_id,
            survey_def=survey_def,
            survey_slug=survey_slug,
            survey_version=survey_version,
            rng=rng,
            clustered=clustered,
        )

        kids_pref = str((traits.get("life_constraints") or {}).get("kids_preference", "unsure"))
        kids_counter[kids_pref] += 1
        cluster_counter[_pick_cluster(rng) if clustered else "uniform"] += 1

        all_users_traits.append({"user_id": resolved_user_id, "traits": traits})
        all_users_for_pairs.append(
            {
                "user_id": resolved_user_id,
                "traits": traits,
                "gender_identity": gender_identity,
                "seeking_genders": seeking_genders,
            }
        )

    qa_credentials: list[dict[str, str]] = []
    if include_qa_login:
        qa_gender, qa_seeking = _generate_seed_matchable_gender_preferences(n_users + 1, rng)
        qa_phone, qa_instagram = _seed_contact_info(rng, tenant_seed_offset * 10000 + 9999)
        qa_user_id = _upsert_seed_user(
            db,
            tenant_id=tenant_id,
            user_id=str(uuid.uuid4()),
            email=f"qa_{tenant_slug_out}@{tenant_domain}",
            username=f"qa_{tenant_slug_out}",
            password=qa_password,
            display_name=f"{tenant_slug_out.upper()} QA",
            cbs_year=rng.choice(["26", "27"]),
            hometown=rng.choice(["New York, NY", "Boston, MA", "Chicago, IL", "San Francisco, CA", "Austin, TX", "Seattle, WA"]),
            phone_number=qa_phone,
            instagram_handle=qa_instagram,
            photo_urls=[
                f"https://picsum.photos/seed/{tenant_slug_out}-qa-1/600/800",
                f"https://picsum.photos/seed/{tenant_slug_out}-qa-2/600/800",
                f"https://picsum.photos/seed/{tenant_slug_out}-qa-3/600/800",
            ],
            gender_identity=qa_gender,
            seeking_genders=qa_seeking,
        )
        _, qa_traits = _seed_survey_for_user(
            db,
            user_id=qa_user_id,
            tenant_id=tenant_id,
            survey_def=survey_def,
            survey_slug=survey_slug,
            survey_version=survey_version,
            rng=rng,
            clustered=clustered,
        )
        all_users_for_pairs.append(
            {
                "user_id": qa_user_id,
                "traits": qa_traits,
                "gender_identity": qa_gender,
                "seeking_genders": qa_seeking,
            }
        )
        qa_credentials.append(
            {
                "tenant_slug": tenant_slug_out,
                "email": f"qa_{tenant_slug_out}@{tenant_domain}",
                "username": f"qa_{tenant_slug_out}",
                "password": qa_password,
            }
        )

    db.commit()

    pairs = build_candidate_pairs(all_users_for_pairs)
    viable = sum(1 for p in pairs if p.score_total > 0)

    big5_avgs: dict[str, float] = {}
    if all_users_traits:
        keys = ["openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"]
        for key in keys:
            vals = [float((u["traits"].get("big5") or {}).get(key, 0.5)) for u in all_users_traits]
            big5_avgs[key] = round(sum(vals) / len(vals), 4)

    return {
        "tenant_slug": tenant_slug_out,
        "users_created": n_users,
        "completed_sessions": n_users,
        "big5_distribution": big5_avgs,
        "kids_preference_distribution": dict(kids_counter),
        "cluster_distribution": dict(cluster_counter),
        "viable_pairs": viable,
        "clustered": clustered,
        "qa_credentials": qa_credentials,
    }


def seed_all_tenants_dummy_data(
    db,
    survey_def: dict[str, Any],
    survey_slug: str,
    survey_version: int,
    n_users_per_tenant: int = 60,
    reset: bool = False,
    seed: int = 42,
    clustered: bool = True,
    include_qa_login: bool = False,
    qa_password: str = "community123",
) -> dict[str, Any]:
    sync_tenants_from_shared_config(db)
    tenants = db.execute(text("SELECT slug FROM tenant ORDER BY created_at ASC")).mappings().all()

    summaries: list[dict[str, Any]] = []
    all_credentials: list[dict[str, str]] = []

    for idx, row in enumerate(tenants):
        slug = str(row.get("slug") or "").strip()
        if not slug:
            continue
        summary = seed_dummy_data(
            db=db,
            survey_def=survey_def,
            survey_slug=survey_slug,
            survey_version=survey_version,
            n_users=n_users_per_tenant,
            reset=reset,
            seed=seed + idx,
            clustered=clustered,
            tenant_slug=slug,
            include_qa_login=include_qa_login,
            qa_password=qa_password,
        )
        summaries.append(summary)
        all_credentials.extend(summary.get("qa_credentials") or [])

    return {
        "tenants_seeded": len(summaries),
        "n_users_per_tenant": n_users_per_tenant,
        "summaries": summaries,
        "qa_credentials": all_credentials,
    }


def backfill_existing_users_survey_data(
    db,
    *,
    survey_slug: str,
    survey_version: int,
    tenant_slug: str | None = None,
    all_tenants: bool = False,
    seed: int = 42,
    clustered: bool = False,
    force_reseed: bool = False,
) -> dict[str, Any]:
    from app.survey_loader import get_survey_definition

    params: dict[str, Any] = {}
    where = ["ua.disabled_at IS NULL"]
    if tenant_slug and not all_tenants:
        where.append("t.slug = :tenant_slug")
        params["tenant_slug"] = tenant_slug

    users = db.execute(
        text(
            f"""
            SELECT
              ua.id::text AS user_id,
              ua.tenant_id::text AS tenant_id,
              COALESCE(t.slug, 'cbs') AS tenant_slug,
              COALESCE(up.gender_identity, ua.gender_identity) AS gender_identity,
              COALESCE(up.seeking_genders, ua.seeking_genders, '[]'::jsonb) AS seeking_genders
            FROM user_account ua
            LEFT JOIN tenant t ON t.id = ua.tenant_id
            LEFT JOIN user_profile up ON up.user_id = ua.id
            WHERE {' AND '.join(where)}
            ORDER BY ua.created_at ASC
            """
        ),
        params,
    ).mappings().all()

    survey_def_cache: dict[str, dict[str, Any]] = {}
    seeded_count = 0
    skipped_existing = 0
    reseeded_count = 0
    profile_defaults_applied = 0

    for idx, row in enumerate(users):
        user_id = str(row.get("user_id") or "")
        user_tenant_id = str(row.get("tenant_id") or "")
        user_tenant_slug = str(row.get("tenant_slug") or "cbs")
        if not user_id or not user_tenant_id:
            continue

        current_gender = str(row.get("gender_identity") or "").strip().lower()
        current_seeking = row.get("seeking_genders") if isinstance(row.get("seeking_genders"), list) else []
        if not current_gender or not current_seeking:
            fallback_gender = "man" if idx % 2 == 0 else "woman"
            fallback_seeking = ["woman"] if fallback_gender == "man" else ["man"]
            db.execute(
                text(
                    """
                    UPDATE user_account
                    SET gender_identity = COALESCE(NULLIF(gender_identity, ''), :gender_identity),
                        seeking_genders = CASE
                          WHEN seeking_genders IS NULL OR jsonb_typeof(seeking_genders) <> 'array' OR jsonb_array_length(seeking_genders) = 0
                          THEN CAST(:seeking_genders AS jsonb)
                          ELSE seeking_genders
                        END
                    WHERE id = CAST(:user_id AS uuid)
                    """
                ),
                {
                    "user_id": user_id,
                    "gender_identity": fallback_gender,
                    "seeking_genders": json.dumps(fallback_seeking),
                },
            )
            db.execute(
                text(
                    """
                    INSERT INTO user_profile (user_id, tenant_id, gender_identity, seeking_genders, updated_at)
                    VALUES (CAST(:user_id AS uuid), CAST(:tenant_id AS uuid), :gender_identity, CAST(:seeking_genders AS jsonb), NOW())
                    ON CONFLICT (user_id)
                    DO UPDATE SET
                      gender_identity = COALESCE(NULLIF(user_profile.gender_identity, ''), EXCLUDED.gender_identity),
                      seeking_genders = CASE
                        WHEN user_profile.seeking_genders IS NULL OR jsonb_typeof(user_profile.seeking_genders) <> 'array' OR jsonb_array_length(user_profile.seeking_genders) = 0
                        THEN EXCLUDED.seeking_genders
                        ELSE user_profile.seeking_genders
                      END,
                      updated_at = NOW()
                    """
                ),
                {
                    "user_id": user_id,
                    "tenant_id": user_tenant_id,
                    "gender_identity": fallback_gender,
                    "seeking_genders": json.dumps(fallback_seeking),
                },
            )
            profile_defaults_applied += 1

        has_completed_session = db.execute(
            text(
                """
                SELECT 1
                FROM survey_session
                WHERE user_id = CAST(:user_id AS uuid)
                  AND survey_slug = :survey_slug
                  AND survey_version = :survey_version
                  AND status = 'completed'
                LIMIT 1
                """
            ),
            {
                "user_id": user_id,
                "survey_slug": survey_slug,
                "survey_version": survey_version,
            },
        ).first() is not None

        has_current_traits = db.execute(
            text(
                """
                SELECT 1
                FROM user_traits
                WHERE user_id = CAST(:user_id AS uuid)
                  AND survey_slug = :survey_slug
                  AND survey_version = :survey_version
                LIMIT 1
                """
            ),
            {
                "user_id": user_id,
                "survey_slug": survey_slug,
                "survey_version": survey_version,
            },
        ).first() is not None

        if has_current_traits and has_completed_session and not force_reseed:
            skipped_existing += 1
            continue

        if force_reseed:
            db.execute(
                text(
                    """
                    DELETE FROM survey_answer
                    WHERE session_id IN (
                      SELECT id
                      FROM survey_session
                      WHERE user_id = CAST(:user_id AS uuid)
                        AND survey_slug = :survey_slug
                        AND survey_version = :survey_version
                    )
                    """
                ),
                {"user_id": user_id, "survey_slug": survey_slug, "survey_version": survey_version},
            )
            db.execute(
                text(
                    """
                    DELETE FROM survey_session
                    WHERE user_id = CAST(:user_id AS uuid)
                      AND survey_slug = :survey_slug
                      AND survey_version = :survey_version
                    """
                ),
                {"user_id": user_id, "survey_slug": survey_slug, "survey_version": survey_version},
            )
            db.execute(
                text(
                    """
                    DELETE FROM user_traits
                    WHERE user_id = CAST(:user_id AS uuid)
                      AND survey_slug = :survey_slug
                      AND survey_version = :survey_version
                    """
                ),
                {"user_id": user_id, "survey_slug": survey_slug, "survey_version": survey_version},
            )
            reseeded_count += 1

        survey_def = survey_def_cache.get(user_tenant_slug)
        if survey_def is None:
            survey_def = get_survey_definition(user_tenant_slug)
            survey_def_cache[user_tenant_slug] = survey_def

        rng = random.Random(seed + idx)
        _seed_survey_for_user(
            db,
            user_id=user_id,
            tenant_id=user_tenant_id,
            survey_def=survey_def,
            survey_slug=survey_slug,
            survey_version=survey_version,
            rng=rng,
            clustered=clustered,
        )
        seeded_count += 1

    db.commit()

    return {
        "mode": "backfill_existing_users",
        "survey_slug": survey_slug,
        "survey_version": survey_version,
        "tenant_slug": tenant_slug,
        "all_tenants": all_tenants,
        "total_users_considered": len(users),
        "users_seeded": seeded_count,
        "users_skipped_existing": skipped_existing,
        "users_reseeded": reseeded_count,
        "users_profile_defaults_applied": profile_defaults_applied,
        "force_reseed": force_reseed,
    }
