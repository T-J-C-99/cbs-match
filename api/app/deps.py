import uuid
from typing import Any

from fastapi import HTTPException
from sqlalchemy import text


def validate_admin_token(token: str | None, admin_token: str | None) -> None:
    if not admin_token or not token or token != admin_token:
        raise HTTPException(status_code=401, detail="Invalid admin token")


def tenant_id_from_user(user: dict[str, Any]) -> str | None:
    value = user.get("tenant_id")
    return str(value) if value else None


def tenant_context_from_user(db, user: dict[str, Any], *, get_default_tenant) -> dict[str, Any]:
    tenant_id = tenant_id_from_user(user)
    if tenant_id:
        row = db.execute(
            text("SELECT id, slug, name, email_domains, timezone FROM tenant WHERE id=CAST(:id AS uuid)"),
            {"id": tenant_id},
        ).mappings().first()
        if row:
            return dict(row)
    return get_default_tenant(db)


def parse_actor_user_id(raw_actor_user_id: str | None) -> str | None:
    if not raw_actor_user_id:
        return None
    value = raw_actor_user_id.strip()
    if not value:
        return None
    try:
        return str(uuid.UUID(value))
    except ValueError:
        raise HTTPException(status_code=400, detail="X-Actor-User-Id must be a valid UUID")
