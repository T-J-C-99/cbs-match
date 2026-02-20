from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import text

from ..config import DEV_MODE


DEFAULT_TENANT_SLUG = "cbs"
logger = logging.getLogger(__name__)

FALLBACK_TENANTS: list[dict[str, Any]] = [
    {"slug": "cbs", "name": "Columbia (CBS)", "tagline": "NYC ambition meets intentional dating.", "emailDomains": ["gsb.columbia.edu"], "theme": {"primary": "#1D3557", "secondary": "#0F2742", "accent": "#B9D9EB", "bg": "#EAF4FA", "text": "#0F172A", "muted": "#5C6B7A"}},
    {"slug": "hbs", "name": "Harvard (HBS)", "tagline": "Bold ideas, grounded connection.", "emailDomains": ["hbs.edu", "mba.hbs.edu"], "theme": {"primary": "#A51C30", "secondary": "#7A1524", "accent": "#D9C6A5", "bg": "#F8F3F1", "text": "#1F2937", "muted": "#6B7280"}},
    {"slug": "gsb", "name": "Stanford (GSB)", "tagline": "Heart-led builders, Bay Area energy.", "emailDomains": ["stanford.edu", "gsb.stanford.edu"], "theme": {"primary": "#8C1515", "secondary": "#2E2D29", "accent": "#B1040E", "bg": "#F8F5F0", "text": "#111827", "muted": "#6B7280"}},
    {"slug": "wharton", "name": "Wharton", "tagline": "Analytical minds, real chemistry.", "emailDomains": ["wharton.upenn.edu", "upenn.edu"], "theme": {"primary": "#011F5B", "secondary": "#003E7E", "accent": "#82AFD3", "bg": "#F3F8FC", "text": "#0F172A", "muted": "#64748B"}},
    {"slug": "kellogg", "name": "Kellogg", "tagline": "High EQ, high standards.", "emailDomains": ["kellogg.northwestern.edu", "northwestern.edu"], "theme": {"primary": "#4E2A84", "secondary": "#3D1F66", "accent": "#836EAA", "bg": "#F6F3FB", "text": "#1F2937", "muted": "#6B7280"}},
    {"slug": "booth", "name": "Booth", "tagline": "Data-smart, people-first.", "emailDomains": ["chicagobooth.edu", "uchicago.edu"], "theme": {"primary": "#800000", "secondary": "#5B0000", "accent": "#C79D6D", "bg": "#F9F3F1", "text": "#1F2937", "muted": "#6B7280"}},
    {"slug": "sloan", "name": "MIT Sloan", "tagline": "Inventive, curious, and intentional.", "emailDomains": ["mitsloan.mit.edu", "mit.edu"], "theme": {"primary": "#A31F34", "secondary": "#750E21", "accent": "#8A8B8C", "bg": "#F8F2F3", "text": "#111827", "muted": "#6B7280"}},
]


def resolve_repo_root_from_file(file_path: str) -> Path:
    current = Path(file_path).resolve()
    for parent in [current, *current.parents]:
        candidate = parent / "packages" / "shared" / "src" / "tenants.json"
        if candidate.exists():
            return parent
    # Deterministic fallback for this repo layout: api/app/services/tenancy.py -> repo root.
    return current.parents[3]


def _shared_tenants_path() -> Path:
    return resolve_repo_root_from_file(__file__) / "packages" / "shared" / "src" / "tenants.json"


def get_shared_tenant_definitions() -> list[dict[str, Any]]:
    path = _shared_tenants_path()
    raw: Any = None
    fallback_used = False

    if DEV_MODE:
        logger.warning("[TENANCY][DEV] Shared tenants path resolved: %s (exists=%s)", str(path), path.exists())

    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.warning("Failed to parse tenants config JSON at %s. Falling back to in-code defaults.", str(path))
            raw = None
    else:
        logger.warning("Shared tenants config file not found at %s. Falling back to in-code defaults.", str(path))

    if raw is None:
        raw = FALLBACK_TENANTS
        fallback_used = True

    if not isinstance(raw, list):
        logger.warning("Invalid tenants config format at %s; expected list. Falling back to in-code defaults.", str(path))
        return FALLBACK_TENANTS

    out: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        slug = str(item.get("slug") or "").strip().lower()
        if not slug:
            continue
        domains = [str(d).strip().lower() for d in (item.get("emailDomains") or []) if str(d).strip()]
        timezone_value = item.get("timezone")
        timezone_text = str(timezone_value).strip() if timezone_value is not None else ""
        out.append(
            {
                "slug": slug,
                "name": str(item.get("name") or slug.upper()),
                "tagline": str(item.get("tagline") or ""),
                "email_domains": domains,
                "theme": item.get("theme") if isinstance(item.get("theme"), dict) else {},
                "timezone": timezone_text or None,
            }
        )

    if DEV_MODE:
        logger.warning(
            "[TENANCY][DEV] Loaded tenant definitions: count=%s fallback_used=%s path=%s",
            len(out),
            fallback_used,
            str(path),
        )

    return out


def sync_tenants_from_shared_config(db) -> dict[str, Any]:
    rows = get_shared_tenant_definitions()
    if not rows:
        return {"loaded": 0, "upserted": 0}

    pre_total = db.execute(text("SELECT COUNT(1) FROM tenant")).scalar() or 0

    upserted = 0
    synced_slugs: list[str] = []
    for row in rows:
        db.execute(
            text(
                """
                INSERT INTO tenant (id, slug, name, email_domains, theme, timezone)
                VALUES (
                  CAST(:id AS uuid),
                  :slug,
                  :name,
                  CAST(:email_domains AS jsonb),
                  CAST(:theme AS jsonb),
                  :timezone
                )
                ON CONFLICT (slug)
                DO UPDATE SET
                  name = EXCLUDED.name,
                  email_domains = EXCLUDED.email_domains,
                  theme = EXCLUDED.theme,
                  timezone = EXCLUDED.timezone
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "slug": row["slug"],
                "name": row["name"],
                "email_domains": json.dumps(row["email_domains"]),
                "theme": json.dumps(row["theme"]),
                "timezone": str(row.get("timezone") or "America/New_York"),
            },
        )
        upserted += 1
        synced_slugs.append(str(row["slug"]))

    post_total = db.execute(text("SELECT COUNT(1) FROM tenant")).scalar() or 0
    logger.info(
        "[TENANCY] sync complete loaded=%s upserted=%s pre_total=%s post_total=%s",
        len(rows),
        upserted,
        int(pre_total),
        int(post_total),
    )
    if DEV_MODE:
        logger.debug("[TENANCY][DEV] sync slugs=%s", sorted(synced_slugs))

    return {
        "loaded": len(rows),
        "upserted": upserted,
        "pre_total": int(pre_total),
        "post_total": int(post_total),
        "slugs": sorted(synced_slugs),
    }


def get_tenant_by_slug(db, slug: str) -> dict[str, Any] | None:
    row = db.execute(
        text("SELECT id, slug, name, email_domains, theme, timezone FROM tenant WHERE slug=:slug LIMIT 1"),
        {"slug": slug},
    ).mappings().first()
    return dict(row) if row else None


def get_default_tenant(db) -> dict[str, Any]:
    sync_tenants_from_shared_config(db)
    tenant = get_tenant_by_slug(db, DEFAULT_TENANT_SLUG)
    if tenant:
        return tenant

    # Defensive fallback if migration didn't run yet.
    db.execute(
        text(
            """
            INSERT INTO tenant (id, slug, name, email_domains, theme, timezone)
            VALUES (CAST(:id AS uuid), :slug, :name, CAST(:email_domains AS jsonb), CAST(:theme AS jsonb), :timezone)
            ON CONFLICT (slug) DO NOTHING
            """
        ),
        {
            "id": str(uuid.uuid4()),
            "slug": DEFAULT_TENANT_SLUG,
            "name": "Columbia Business School",
            "email_domains": '["gsb.columbia.edu"]',
            "theme": '{"primary":"#1D3557","secondary":"#0F2742","accent":"#B9D9EB","bg":"#EAF4FA","text":"#0F172A","muted":"#5C6B7A"}',
            "timezone": "America/New_York",
        },
    )
    row = get_tenant_by_slug(db, DEFAULT_TENANT_SLUG)
    if not row:
        raise RuntimeError("Unable to initialize default tenant")
    return row


def resolve_tenant_for_email(db, email: str, tenant_slug: str | None = None) -> dict[str, Any]:
    sync_tenants_from_shared_config(db)
    if tenant_slug:
        explicit = get_tenant_by_slug(db, tenant_slug.strip().lower())
        if not explicit:
            raise ValueError("Tenant not found")
        return explicit

    email_norm = str(email or "").strip().lower()
    domain = email_norm.split("@")[-1] if "@" in email_norm else ""
    rows = db.execute(
        text("SELECT id, slug, name, email_domains, theme, timezone FROM tenant ORDER BY created_at ASC")
    ).mappings().all()

    matches: list[dict[str, Any]] = []
    for row in rows:
        domains = row.get("email_domains") if isinstance(row.get("email_domains"), list) else []
        if domain and domain in {str(d).strip().lower() for d in domains}:
            matches.append(dict(row))

    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ValueError("Email domain matches multiple tenants")

    return get_default_tenant(db)


def ensure_email_allowed_for_tenant(email: str, tenant: dict[str, Any]) -> bool:
    email_norm = str(email or "").strip().lower()
    domain = email_norm.split("@")[-1] if "@" in email_norm else ""
    allowed = {str(d).strip().lower() for d in (tenant.get("email_domains") or []) if str(d).strip()}
    if not allowed:
        # Backward-compatible fallback for mocked tenants in tests.
        return bool(domain)
    return bool(domain) and domain in allowed
