#!/usr/bin/env python3
"""
Seed dummy users and run weekly matching to produce a testable matched pair.

Usage:
    API_BASE_URL=https://cbs-match-api.onrender.com \
    ADMIN_EMAIL=admin@cbsmatch.local \
    ADMIN_PASSWORD=<your-admin-password> \
    python scripts/seed_and_match.py

Optional env vars:
    TENANT_SLUG     Tenant to seed (default: cbs)
    N_USERS         Number of dummy users to create (default: 20)
    QA_PASSWORD     Password for QA accounts (default: community12345)
    RESET           Set to "true" to wipe existing seed data first
"""
import json
import os
import sys

import requests

API_BASE = os.getenv("API_BASE_URL", "").rstrip("/")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
TENANT_SLUG = os.getenv("TENANT_SLUG", "cbs")
N_USERS = int(os.getenv("N_USERS", "20"))
QA_PASSWORD = os.getenv("QA_PASSWORD", "community12345")
RESET = os.getenv("RESET", "false").lower() == "true"
TIMEOUT = 120


def fail(msg: str) -> None:
    print(f"\n[FAIL] {msg}", file=sys.stderr)
    sys.exit(1)


def req(method: str, path: str, body=None, token: str | None = None):
    if not API_BASE:
        fail("API_BASE_URL is required")
    url = f"{API_BASE}{path}"
    hdrs = {"Content-Type": "application/json"}
    if token:
        hdrs["Authorization"] = f"Bearer {token}"
    try:
        resp = requests.request(method.upper(), url, json=body, headers=hdrs, timeout=TIMEOUT)
        try:
            data = resp.json()
        except Exception:
            data = {"raw": resp.text}
        return resp.status_code, data
    except Exception as e:
        fail(f"{method} {path} → network error: {e}")


def main():
    if not API_BASE:
        fail("API_BASE_URL is required")
    if not ADMIN_EMAIL or not ADMIN_PASSWORD:
        fail("ADMIN_EMAIL and ADMIN_PASSWORD are required")

    # 1. Health check
    print(f"Connecting to {API_BASE} ...")
    code, _ = req("GET", "/health")
    if code != 200:
        fail(f"Health check failed (HTTP {code})")
    print("  API is healthy")

    # 2. Admin login
    print(f"\nLogging in as {ADMIN_EMAIL} ...")
    code, body = req("POST", "/admin/auth/login", {"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    if code != 200:
        fail(f"Admin login failed (HTTP {code}): {body}")
    token = body.get("access_token")
    role = body.get("admin", {}).get("role", "?")
    print(f"  Logged in — role: {role}")

    # 3. Seed dummy users
    print(f"\nSeeding {N_USERS} dummy users for tenant '{TENANT_SLUG}' (reset={RESET}) ...")
    print("  This may take 30–90 seconds on a cold Render instance ...")
    code, body = req(
        "POST",
        "/admin/seed",
        {
            "tenant_slug": TENANT_SLUG,
            "n_users": N_USERS,
            "reset": RESET,
            "clustered": True,
            "include_qa_login": True,
            "qa_password": QA_PASSWORD,
            "seed": 42,
        },
        token=token,
    )
    if code != 200:
        fail(f"Seeding failed (HTTP {code}): {body}")

    users_created = body.get("users_created", "?")
    print(f"  Created {users_created} users")

    qa_creds = body.get("qa_credentials") or []
    if qa_creds:
        print(f"  QA account: {qa_creds[0].get('email')} / {qa_creds[0].get('password')}")

    # 4. Run weekly matching
    print(f"\nRunning weekly matching for tenant '{TENANT_SLUG}' ...")
    code, body = req(
        "POST",
        f"/admin/matches/run-weekly?tenant_slug={TENANT_SLUG}&force=true",
        token=token,
    )
    if code != 200:
        fail(f"Matching failed (HTTP {code}): {body}")

    eligible = body.get("eligible_users", "?")
    matched = body.get("matched_pairs", "?")
    no_match = body.get("no_match_count", "?")
    week = body.get("week_start_date", "?")
    print(f"  Week: {week}")
    print(f"  Eligible users: {eligible}")
    print(f"  Matched pairs:  {matched}")
    print(f"  No match:       {no_match}")

    # 5. Fetch week summary
    if week and week != "?":
        print(f"\nFetching week summary for {week} ...")
        code2, week_body = req("GET", f"/admin/matches/week/{week}?tenant_slug={TENANT_SLUG}", token=token)
        if code2 == 200:
            pairs = week_body.get("unique_pairs_current_week") or week_body.get("assignments_current_week", "?")
            print(f"  Week summary: {pairs} pairs on record")

    # 6. Summary
    print("\n" + "=" * 60)
    print("DONE — Credentials for happy-path demo:")
    print("=" * 60)
    print(f"  Tenant:       {TENANT_SLUG}")
    print(f"  Seed users:   {users_created} created")
    print(f"  Matches made: {matched} pairs for week {week}")
    print()
    if qa_creds:
        for cred in qa_creds:
            print(f"  QA Login:  {cred.get('email')}  /  {cred.get('password')}")
    else:
        print(f"  Seed user email format:  seed_{TENANT_SLUG}_42_<N>@<tenant-domain>")
        print(f"  Seed user password:      {QA_PASSWORD}")
    print()
    print("  To see both sides of a match, log in as two seed users who")
    print("  were matched together. Check the admin panel or DB for pairs.")
    print("=" * 60)


if __name__ == "__main__":
    main()
