#!/usr/bin/env python3
"""
Creates 6 named demo accounts (Brad, Tom, Matt, Jennifer, Margot, Oprah),
completes their personality surveys, runs weekly matching, and prints the
matched pairs for use in demo / class submission.

Usage:
    API_BASE_URL=https://cbs-match-api.onrender.com python3 scripts/create_demo_users.py
"""
import json
import os
import sys

import requests

BASE = os.getenv("API_BASE_URL", "https://cbs-match-api.onrender.com").rstrip("/")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@cbsmatch.local")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "community123")
TENANT_SLUG = "cbs"
TIMEOUT = 60


def fail(msg):
    print(f"[FAIL] {msg}", file=sys.stderr)
    sys.exit(1)


def api(method, path, body=None, token=None, tenant=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if tenant:
        headers["X-Tenant-Slug"] = tenant
    r = requests.request(method.upper(), f"{BASE}{path}", json=body, headers=headers, timeout=TIMEOUT)
    try:
        data = r.json()
    except Exception:
        data = {"raw": r.text}
    return r.status_code, data


# ── Personality profiles ──────────────────────────────────────────────────────
# Each profile maps question_code → answer_value.
# Likert 1-5: higher = stronger agreement (note: some are reverse_coded but
# the API expects the raw 1-5 value; scoring handles reversal internally).
# FC_*: "A" or "B". Single-select: one of the enumerated option values.

def profile_brad():
    """Brad: social, stable, career-driven, direct, wants kids, saver."""
    return {
        # Big Five
        "OPN_01": 3, "OPN_02": 3, "OPN_03": 3,
        "CON_01": 5, "CON_02": 5, "CON_03": 5,
        "EXT_01": 5, "EXT_02": 5, "EXT_03": 5,
        "AGR_01": 4, "AGR_02": 4, "AGR_03": 4,
        "ER_01": 5, "ER_02": 5, "ER_03": 5,
        # Conflict & Repair
        "REP_01": 5, "REP_02": 5, "REP_03": 4, "REP_04": 5,
        "REP_05": 4, "REP_06": 4, "REP_07": 4, "REP_08": 5,
        "REP_09": 4, "REP_10": 4, "REP_11": 4, "REP_12": 4,
        # Attachment
        "ATT_01": 4, "ATT_02": 4, "ATT_03": 4, "ATT_04": 3,
        "ATT_05": 3, "ATT_06": 4, "ATT_07": 4, "ATT_08": 3, "ATT_09": 3,
        # Life
        "KIDS_01": "yes", "KIDS_02": "3_7_years", "KIDS_03": 4,
        "LOC_01": 4, "CAR_01": 5, "CAR_02": 4,
        "MAR_01": 4, "MAR_02": 4, "MAR_03": 3,
        "VAL_01": 4, "VAL_02": 4, "VAL_03": 3,
        # Lifestyle
        "SOC_01": 5, "SOC_02": 5, "SOC_03": 5,
        "STR_01": 3, "STR_02": 3,
        "HOME_01": 4, "HOME_02": 4, "HOME_03": 3,
        "FIN_01": 4, "FIN_02": 4, "FIN_03": 4, "FIN_04": 3, "FIN_05": 4,
        # Forced choice: stability, social energy, steady, direct, define early, communicate, career, save
        "FC_01": "A", "FC_02": "B", "FC_03": "A", "FC_04": "A",
        "FC_05": "A", "FC_06": "A", "FC_07": "A", "FC_08": "A",
        # Vibe
        "VIBE_01": "cocktail_bar", "VIBE_02": "social_dinner",
        "VIBE_03": "direct_clear", "VIBE_04": "late_reservation",
        "CBS_01": "kravis_lounge", "CBS_02": "dinner_with_friends",
    }


def profile_jennifer():
    """Jennifer: warm, social, relationship-focused, wants kids, security-minded."""
    return {
        "OPN_01": 3, "OPN_02": 3, "OPN_03": 3,
        "CON_01": 4, "CON_02": 4, "CON_03": 4,
        "EXT_01": 4, "EXT_02": 4, "EXT_03": 4,
        "AGR_01": 5, "AGR_02": 5, "AGR_03": 5,
        "ER_01": 4, "ER_02": 4, "ER_03": 4,
        "REP_01": 4, "REP_02": 4, "REP_03": 4, "REP_04": 4,
        "REP_05": 4, "REP_06": 4, "REP_07": 3, "REP_08": 4,
        "REP_09": 4, "REP_10": 3, "REP_11": 4, "REP_12": 3,
        "ATT_01": 4, "ATT_02": 4, "ATT_03": 4, "ATT_04": 4,
        "ATT_05": 3, "ATT_06": 4, "ATT_07": 4, "ATT_08": 3, "ATT_09": 3,
        "KIDS_01": "yes", "KIDS_02": "3_7_years", "KIDS_03": 4,
        "LOC_01": 4, "CAR_01": 4, "CAR_02": 3,
        "MAR_01": 5, "MAR_02": 5, "MAR_03": 4,
        "VAL_01": 5, "VAL_02": 4, "VAL_03": 4,
        "SOC_01": 4, "SOC_02": 4, "SOC_03": 4,
        "STR_01": 3, "STR_02": 3,
        "HOME_01": 4, "HOME_02": 4, "HOME_03": 4,
        "FIN_01": 4, "FIN_02": 4, "FIN_03": 4, "FIN_04": 3, "FIN_05": 4,
        "FC_01": "A", "FC_02": "A", "FC_03": "A", "FC_04": "A",
        "FC_05": "A", "FC_06": "A", "FC_07": "B", "FC_08": "A",
        "VIBE_01": "cocktail_bar", "VIBE_02": "social_dinner",
        "VIBE_03": "warm_checkins", "VIBE_04": "late_reservation",
        "CBS_01": "kravis_lounge", "CBS_02": "dinner_with_friends",
    }


def profile_tom():
    """Tom: intellectually curious, open, balanced, playful, adventurous."""
    return {
        "OPN_01": 5, "OPN_02": 5, "OPN_03": 5,
        "CON_01": 3, "CON_02": 3, "CON_03": 3,
        "EXT_01": 3, "EXT_02": 3, "EXT_03": 3,
        "AGR_01": 4, "AGR_02": 4, "AGR_03": 4,
        "ER_01": 3, "ER_02": 3, "ER_03": 3,
        "REP_01": 3, "REP_02": 3, "REP_03": 4, "REP_04": 3,
        "REP_05": 3, "REP_06": 3, "REP_07": 4, "REP_08": 3,
        "REP_09": 3, "REP_10": 4, "REP_11": 3, "REP_12": 4,
        "ATT_01": 3, "ATT_02": 3, "ATT_03": 4, "ATT_04": 3,
        "ATT_05": 4, "ATT_06": 3, "ATT_07": 3, "ATT_08": 4, "ATT_09": 4,
        "KIDS_01": "probably", "KIDS_02": "later", "KIDS_03": 3,
        "LOC_01": 3, "CAR_01": 3, "CAR_02": 3,
        "MAR_01": 3, "MAR_02": 3, "MAR_03": 3,
        "VAL_01": 4, "VAL_02": 3, "VAL_03": 3,
        "SOC_01": 3, "SOC_02": 3, "SOC_03": 3,
        "STR_01": 4, "STR_02": 4,
        "HOME_01": 3, "HOME_02": 3, "HOME_03": 3,
        "FIN_01": 3, "FIN_02": 3, "FIN_03": 3, "FIN_04": 4, "FIN_05": 3,
        "FC_01": "B", "FC_02": "A", "FC_03": "B", "FC_04": "B",
        "FC_05": "B", "FC_06": "B", "FC_07": "B", "FC_08": "B",
        "VIBE_01": "museum_activity", "VIBE_02": "quiet_recharge",
        "VIBE_03": "playful_banter", "VIBE_04": "last_minute_trip",
        "CBS_01": "manhattanville_walk", "CBS_02": "library_work",
    }


def profile_margot():
    """Margot: adventurous, open, spontaneous, playful, independent, unsure on kids."""
    return {
        "OPN_01": 5, "OPN_02": 5, "OPN_03": 5,
        "CON_01": 3, "CON_02": 3, "CON_03": 2,
        "EXT_01": 3, "EXT_02": 3, "EXT_03": 3,
        "AGR_01": 4, "AGR_02": 4, "AGR_03": 4,
        "ER_01": 3, "ER_02": 3, "ER_03": 3,
        "REP_01": 3, "REP_02": 3, "REP_03": 4, "REP_04": 3,
        "REP_05": 3, "REP_06": 3, "REP_07": 4, "REP_08": 3,
        "REP_09": 3, "REP_10": 4, "REP_11": 3, "REP_12": 4,
        "ATT_01": 3, "ATT_02": 3, "ATT_03": 4, "ATT_04": 3,
        "ATT_05": 4, "ATT_06": 3, "ATT_07": 3, "ATT_08": 4, "ATT_09": 4,
        "KIDS_01": "unsure", "KIDS_02": "open", "KIDS_03": 3,
        "LOC_01": 4, "CAR_01": 4, "CAR_02": 3,
        "MAR_01": 3, "MAR_02": 3, "MAR_03": 3,
        "VAL_01": 4, "VAL_02": 3, "VAL_03": 3,
        "SOC_01": 3, "SOC_02": 3, "SOC_03": 4,
        "STR_01": 4, "STR_02": 4,
        "HOME_01": 2, "HOME_02": 2, "HOME_03": 3,
        "FIN_01": 3, "FIN_02": 3, "FIN_03": 3, "FIN_04": 4, "FIN_05": 3,
        "FC_01": "B", "FC_02": "A", "FC_03": "B", "FC_04": "B",
        "FC_05": "B", "FC_06": "B", "FC_07": "B", "FC_08": "B",
        "VIBE_01": "museum_activity", "VIBE_02": "spontaneous_adventure",
        "VIBE_03": "playful_banter", "VIBE_04": "last_minute_trip",
        "CBS_01": "manhattanville_walk", "CBS_02": "early_night",
    }


def profile_matt():
    """Matt: conscientious, grounded, stable, direct, wants kids, disciplined."""
    return {
        "OPN_01": 2, "OPN_02": 2, "OPN_03": 2,
        "CON_01": 5, "CON_02": 5, "CON_03": 5,
        "EXT_01": 3, "EXT_02": 3, "EXT_03": 3,
        "AGR_01": 3, "AGR_02": 3, "AGR_03": 3,
        "ER_01": 5, "ER_02": 5, "ER_03": 5,
        "REP_01": 5, "REP_02": 5, "REP_03": 5, "REP_04": 5,
        "REP_05": 4, "REP_06": 5, "REP_07": 4, "REP_08": 5,
        "REP_09": 5, "REP_10": 4, "REP_11": 5, "REP_12": 4,
        "ATT_01": 4, "ATT_02": 4, "ATT_03": 3, "ATT_04": 5,
        "ATT_05": 2, "ATT_06": 5, "ATT_07": 4, "ATT_08": 2, "ATT_09": 2,
        "KIDS_01": "yes", "KIDS_02": "3_7_years", "KIDS_03": 5,
        "LOC_01": 3, "CAR_01": 5, "CAR_02": 5,
        "MAR_01": 4, "MAR_02": 4, "MAR_03": 2,
        "VAL_01": 3, "VAL_02": 3, "VAL_03": 2,
        "SOC_01": 3, "SOC_02": 3, "SOC_03": 2,
        "STR_01": 2, "STR_02": 2,
        "HOME_01": 5, "HOME_02": 5, "HOME_03": 4,
        "FIN_01": 5, "FIN_02": 5, "FIN_03": 5, "FIN_04": 2, "FIN_05": 5,
        "FC_01": "A", "FC_02": "A", "FC_03": "A", "FC_04": "A",
        "FC_05": "A", "FC_06": "A", "FC_07": "A", "FC_08": "A",
        "VIBE_01": "dinner_reservation", "VIBE_02": "workout_reset",
        "VIBE_03": "direct_clear", "VIBE_04": "low_key_detour",
        "CBS_01": "uris_steps", "CBS_02": "gym_reset",
    }


def profile_oprah():
    """Oprah: direct, conscientious, career-focused, emotionally steady, wants kids eventually."""
    return {
        "OPN_01": 2, "OPN_02": 2, "OPN_03": 2,
        "CON_01": 5, "CON_02": 5, "CON_03": 5,
        "EXT_01": 3, "EXT_02": 3, "EXT_03": 3,
        "AGR_01": 3, "AGR_02": 3, "AGR_03": 3,
        "ER_01": 5, "ER_02": 5, "ER_03": 5,
        "REP_01": 5, "REP_02": 5, "REP_03": 5, "REP_04": 5,
        "REP_05": 5, "REP_06": 5, "REP_07": 4, "REP_08": 5,
        "REP_09": 5, "REP_10": 4, "REP_11": 5, "REP_12": 4,
        "ATT_01": 4, "ATT_02": 4, "ATT_03": 3, "ATT_04": 5,
        "ATT_05": 2, "ATT_06": 5, "ATT_07": 4, "ATT_08": 2, "ATT_09": 2,
        "KIDS_01": "probably", "KIDS_02": "3_7_years", "KIDS_03": 4,
        "LOC_01": 3, "CAR_01": 5, "CAR_02": 5,
        "MAR_01": 4, "MAR_02": 4, "MAR_03": 2,
        "VAL_01": 3, "VAL_02": 3, "VAL_03": 2,
        "SOC_01": 3, "SOC_02": 3, "SOC_03": 2,
        "STR_01": 2, "STR_02": 2,
        "HOME_01": 5, "HOME_02": 5, "HOME_03": 4,
        "FIN_01": 5, "FIN_02": 5, "FIN_03": 5, "FIN_04": 2, "FIN_05": 5,
        "FC_01": "A", "FC_02": "A", "FC_03": "A", "FC_04": "A",
        "FC_05": "A", "FC_06": "A", "FC_07": "A", "FC_08": "A",
        "VIBE_01": "dinner_reservation", "VIBE_02": "workout_reset",
        "VIBE_03": "direct_clear", "VIBE_04": "low_key_detour",
        "CBS_01": "uris_steps", "CBS_02": "gym_reset",
    }


USERS = [
    {
        "name": "Brad",
        "email": "brad@gsb.columbia.edu",
        "username": "brad",
        "display_name": "Brad",
        "gender_identity": "man",
        "seeking_genders": ["woman"],
        "cbs_year": "26",
        "hometown": "Boston, MA",
        "profile": profile_brad,
    },
    {
        "name": "Tom",
        "email": "tom@gsb.columbia.edu",
        "username": "tom",
        "display_name": "Tom",
        "gender_identity": "man",
        "seeking_genders": ["woman"],
        "cbs_year": "26",
        "hometown": "Chicago, IL",
        "profile": profile_tom,
    },
    {
        "name": "Matt",
        "email": "matt@gsb.columbia.edu",
        "username": "matt",
        "display_name": "Matt",
        "gender_identity": "man",
        "seeking_genders": ["woman"],
        "cbs_year": "27",
        "hometown": "Dallas, TX",
        "profile": profile_matt,
    },
    {
        "name": "Jennifer",
        "email": "jennifer@gsb.columbia.edu",
        "username": "jennifer",
        "display_name": "Jennifer",
        "gender_identity": "woman",
        "seeking_genders": ["man"],
        "cbs_year": "26",
        "hometown": "New York, NY",
        "profile": profile_jennifer,
    },
    {
        "name": "Margot",
        "email": "margot@gsb.columbia.edu",
        "username": "margot",
        "display_name": "Margot",
        "gender_identity": "woman",
        "seeking_genders": ["man"],
        "cbs_year": "26",
        "hometown": "San Francisco, CA",
        "profile": profile_margot,
    },
    {
        "name": "Oprah",
        "email": "oprah@gsb.columbia.edu",
        "username": "oprah",
        "display_name": "Oprah",
        "gender_identity": "woman",
        "seeking_genders": ["man"],
        "cbs_year": "27",
        "hometown": "Atlanta, GA",
        "profile": profile_oprah,
    },
]


def register_user(u):
    """Register user and return bearer token."""
    payload = {
        "email": u["email"],
        "password": "community123",
        "username": u["username"],
        "display_name": u["display_name"],
        "gender_identity": u["gender_identity"],
        "seeking_genders": u["seeking_genders"],
        "cbs_year": u["cbs_year"],
        "hometown": u["hometown"],
    }
    code, body = api("POST", "/auth/register", payload,
                     tenant=TENANT_SLUG)
    # Bearer mode: set X-Auth-Mode header
    headers = {"Content-Type": "application/json", "X-Tenant-Slug": TENANT_SLUG, "X-Auth-Mode": "bearer"}
    r = requests.post(f"{BASE}/auth/register", json=payload, headers=headers, timeout=TIMEOUT)
    if r.status_code == 409:
        # Already exists — log in instead
        headers2 = {"Content-Type": "application/json", "X-Tenant-Slug": TENANT_SLUG, "X-Auth-Mode": "bearer"}
        r2 = requests.post(f"{BASE}/auth/login", json={"email": u["email"], "password": "community123"},
                           headers=headers2, timeout=TIMEOUT)
        if r2.status_code != 200:
            fail(f"Login failed for {u['name']}: {r2.text}")
        return r2.json().get("access_token")
    if r.status_code not in (200, 201):
        fail(f"Register failed for {u['name']} ({r.status_code}): {r.text[:300]}")
    return r.json().get("access_token")


def complete_survey(name, token):
    """Create session, submit all answers, complete."""
    # Get user from list
    u = next(x for x in USERS if x["name"] == name)
    answers = u["profile"]()

    # Create / resume session
    code, body = api("POST", "/sessions", token=token, tenant=TENANT_SLUG)
    if code not in (200, 201):
        fail(f"Create session failed for {name} ({code}): {body}")
    session_id = body.get("id") or body.get("session_id")
    if not session_id:
        fail(f"No session_id for {name}: {body}")

    # Submit answers
    answer_list = [{"question_code": k, "answer_value": v} for k, v in answers.items()]
    code, body = api("POST", f"/sessions/{session_id}/answers",
                     {"answers": answer_list}, token=token, tenant=TENANT_SLUG)
    if code not in (200, 201):
        fail(f"Submit answers failed for {name} ({code}): {body}")
    print(f"    Saved {body.get('saved_count', '?')} answers")

    # Complete session
    code, body = api("POST", f"/sessions/{session_id}/complete", token=token, tenant=TENANT_SLUG)
    if code not in (200, 201):
        fail(f"Complete session failed for {name} ({code}): {body}")
    print(f"    Session completed: {body.get('status', body)}")


def main():
    print(f"Target: {BASE}\n")

    # Health check
    code, _ = api("GET", "/health")
    if code != 200:
        fail(f"API unhealthy ({code})")
    print("API healthy ✓\n")

    # Admin login (for running matching)
    code, body = api("POST", "/admin/auth/login", {"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    if code != 200:
        fail(f"Admin login failed: {body}")
    admin_token = body["access_token"]
    print(f"Admin logged in ({body['admin']['role']}) ✓\n")

    # Register and complete surveys for each user
    user_tokens = {}
    for u in USERS:
        print(f"→ {u['name']} ({u['email']})")
        token = register_user(u)
        if not token:
            fail(f"No token returned for {u['name']}")
        user_tokens[u["name"]] = token
        print(f"    Registered / logged in ✓")
        complete_survey(u["name"], token)

    print("\nAll 6 users ready. Running matching...\n")

    # Run matching (force=true to re-run for this week)
    code, body = api("POST", f"/admin/matches/run-weekly?tenant_slug={TENANT_SLUG}&force=true",
                     token=admin_token)
    if code != 200:
        fail(f"Matching failed ({code}): {body}")

    week = body.get("week_start_date", "?")
    eligible = body.get("eligible_users", "?")
    matched = body.get("matched_pairs", "?")
    print(f"Week:           {week}")
    print(f"Eligible users: {eligible}")
    print(f"Matched pairs:  {matched}")

    if int(matched or 0) == 0:
        print("\n[WARN] 0 pairs — check eligibility. Trying to fetch week data anyway...")

    # Fetch match details for each user
    print("\n── Match Results ──────────────────────────────────────────")
    pairs = {}
    for u in USERS:
        token = user_tokens[u["name"]]
        code, body = api("GET", "/matches/current", token=token, tenant=TENANT_SLUG)
        if code == 200:
            match = body.get("match") or body
            matched_name = match.get("display_name") or match.get("username") or "(no match)"
            score = match.get("score_total") or match.get("score") or "?"
            print(f"  {u['name']:12} → matched with: {matched_name:12}  (score: {score})")
            pairs[u["name"]] = {"matched_with": matched_name, "score": score}
        elif code == 404:
            print(f"  {u['name']:12} → no match this week")
            pairs[u["name"]] = {"matched_with": None}
        else:
            print(f"  {u['name']:12} → error {code}: {body}")

    print("\n── Demo Credentials ────────────────────────────────────────")
    print(f"  Site:     https://cbs-match-web.vercel.app")
    print(f"  Password: community123  (all accounts)")
    print()
    for u in USERS:
        p = pairs.get(u["name"], {})
        print(f"  {u['name']:12}  {u['email']:35}  → {p.get('matched_with', 'none')}")

    print("\nDone.")

    # Write pairs to JSON for notebook use
    result = {
        "week": week,
        "eligible_users": eligible,
        "matched_pairs": matched,
        "users": [
            {
                "name": u["name"],
                "email": u["email"],
                "username": u["username"],
                "gender": u["gender_identity"],
                "matched_with": pairs.get(u["name"], {}).get("matched_with"),
                "score": pairs.get(u["name"], {}).get("score"),
            }
            for u in USERS
        ],
    }
    out_path = os.path.join(os.path.dirname(__file__), "demo_pairs.json")
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\nPairs saved to {out_path}")


if __name__ == "__main__":
    main()
