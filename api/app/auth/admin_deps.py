from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import Depends, Header, HTTPException

from app import repo
from app.auth.security import decode_admin_access_token
from app import config


ROLE_ORDER = {"viewer": 1, "operator": 2, "admin": 3}


def _extract_bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        return None
    return parts[1].strip()


def get_current_admin(
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> dict[str, Any]:
    bearer = _extract_bearer(authorization)
    if bearer:
        payload = decode_admin_access_token(bearer)
        admin_id = str(payload.get("sub") or "").strip()
        role = str(payload.get("role") or "viewer").strip().lower()
        session_id = str(payload.get("session_id") or "").strip() or None
        if not admin_id or role not in ROLE_ORDER:
            raise HTTPException(status_code=401, detail="Invalid admin token")

        admin = repo.get_admin_user_by_id(admin_id)
        if not admin or not bool(admin.get("is_active")):
            raise HTTPException(status_code=401, detail="Admin account inactive")

        if session_id:
            sess = repo.get_admin_session(session_id)
            if not sess:
                raise HTTPException(status_code=401, detail="Admin session not found")
            if str(sess.get("admin_user_id")) != admin_id:
                raise HTTPException(status_code=401, detail="Invalid admin session")
            if sess.get("revoked_at") is not None:
                raise HTTPException(status_code=401, detail="Admin session revoked")
            expires_at = sess.get("expires_at")
            if not expires_at or expires_at < datetime.now(timezone.utc):
                raise HTTPException(status_code=401, detail="Admin session expired")

        return {
            "id": str(admin.get("id")),
            "email": str(admin.get("email") or ""),
            "role": str(admin.get("role") or role),
            "auth_mode": "session",
            "session_id": session_id,
        }

    # Dev fallback only.
    runtime_admin_token = str(getattr(config, "ADMIN_TOKEN", "") or "")
    if not runtime_admin_token:
        try:
            from app import main as app_main  # local import to avoid circular import at module load

            runtime_admin_token = str(getattr(app_main, "ADMIN_TOKEN", "") or "")
        except Exception:
            runtime_admin_token = ""

    if runtime_admin_token and x_admin_token and x_admin_token == runtime_admin_token:
        return {
            "id": None,
            "email": "dev-admin-token",
            "role": "admin",
            "auth_mode": "token",
            "session_id": None,
        }

    # Backwards-compatible local/dev token when no explicit ADMIN_TOKEN is configured.
    if not runtime_admin_token and x_admin_token and x_admin_token == "dev-admin-token":
        return {
            "id": None,
            "email": "dev-admin-token",
            "role": "admin",
            "auth_mode": "token",
            "session_id": None,
        }

    raise HTTPException(status_code=401, detail="Admin authentication required")


def require_admin_role(min_role: str):
    required = ROLE_ORDER.get(min_role)
    if required is None:
        raise ValueError(f"Unknown role: {min_role}")

    def _dep(admin_user: dict[str, Any] = Depends(get_current_admin)) -> dict[str, Any]:
        role = str(admin_user.get("role") or "viewer").lower()
        current = ROLE_ORDER.get(role, 0)
        if current < required:
            raise HTTPException(status_code=403, detail="Insufficient admin role")
        return admin_user

    return _dep
