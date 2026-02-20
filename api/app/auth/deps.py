"""
Authentication dependencies for FastAPI.

Supports two auth modes:
1. Cookie-based session (primary for web): httpOnly cookie contains access token
2. Bearer token (for admin/API): Authorization header with Bearer token

For user-facing routes, tenant is resolved from the user record.
For admin routes, X-Tenant-Slug header may still be used.
"""

import logging
import uuid
from typing import Any

from fastapi import Cookie, Depends, Header, HTTPException, Request
from pydantic import BaseModel

from app import repo
from app.auth.security import decode_access_token
from app.config import DEV_MODE

logger = logging.getLogger(__name__)

# Cookie name for session token
SESSION_COOKIE_NAME = "cbs_session"


class AuthErrorDetail(BaseModel):
    message: str = "unauthorized"
    reason: str
    trace_id: str


class AuthError(Exception):
    """Raised when authentication fails with detailed reason."""
    
    def __init__(self, reason: str, detail: str = "unauthorized"):
        self.reason = reason
        self.detail = detail
        self.trace_id = str(uuid.uuid4())
        super().__init__(detail)


def _log_auth_failure(
    reason: str,
    trace_id: str,
    token_prefix: str | None = None,
    auth_source: str | None = None,
    payload: dict[str, Any] | None = None,
    user_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """Log detailed auth failure for debugging."""
    log_data = {
        "trace_id": trace_id,
        "reason": reason,
        "auth_source": auth_source,
        "token_prefix": token_prefix,
        "token_user_id": payload.get("sub") if payload else None,
        "token_email": payload.get("email") if payload else None,
        "token_tenant_id": payload.get("tenant_id") if payload else None,
        "token_tenant_slug": payload.get("tenant_slug") if payload else None,
        "resolved_user_id": user_id,
        "extra": extra or {},
    }
    logger.warning(f"[AUTH_FAILURE] {log_data}")


def _extract_bearer(authorization: str | None) -> str:
    """Extract Bearer token from Authorization header."""
    if not authorization:
        raise AuthError(reason="missing_token", detail="Missing Authorization header")
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise AuthError(reason="malformed_token", detail="Invalid Authorization header")
    return parts[1].strip()


def _validate_token_and_get_user(
    token: str,
    trace_id: str,
    auth_source: str,
) -> dict[str, Any]:
    """
    Validate a JWT token and return the user dict.
    
    This is the core validation logic shared between cookie and bearer auth.
    Tenant is resolved from the user record, not from headers.
    """
    token_prefix = token[:8] + "..." if len(token) > 8 else token
    
    # Decode token
    try:
        payload = decode_access_token(token)
    except HTTPException as e:
        reason = "token_expired" if "expired" in str(e.detail).lower() else "signature_invalid"
        _log_auth_failure(reason, trace_id, token_prefix, auth_source)
        raise HTTPException(
            status_code=401,
            detail=AuthErrorDetail(message="unauthorized", reason=reason, trace_id=trace_id).model_dump() if DEV_MODE else {"message": "unauthorized", "trace_id": trace_id},
        )
    
    logger.debug(f"[auth] token valid, sub={payload.get('sub')} email={payload.get('email')}")
    
    # Validate subject
    user_id = str(payload.get("sub", ""))
    if not user_id:
        _log_auth_failure("token_missing_subject", trace_id, token_prefix, auth_source, payload)
        raise HTTPException(
            status_code=401,
            detail=AuthErrorDetail(message="unauthorized", reason="token_missing_subject", trace_id=trace_id).model_dump() if DEV_MODE else {"message": "unauthorized", "trace_id": trace_id},
        )
    
    # Look up user
    user = repo.get_user_by_id(user_id)
    if not user:
        _log_auth_failure("token_user_not_found", trace_id, token_prefix, auth_source, payload, user_id)
        raise HTTPException(
            status_code=401,
            detail=AuthErrorDetail(message="unauthorized", reason="token_user_not_found", trace_id=trace_id).model_dump() if DEV_MODE else {"message": "unauthorized", "trace_id": trace_id},
        )
    
    if user.get("disabled_at"):
        _log_auth_failure("account_disabled", trace_id, token_prefix, auth_source, payload, user_id)
        raise HTTPException(
            status_code=403,
            detail=AuthErrorDetail(message="Account disabled", reason="account_disabled", trace_id=trace_id).model_dump() if DEV_MODE else {"message": "Account disabled", "trace_id": trace_id},
        )
    
    # Get tenant info from user record (not from token or headers)
    user_tenant_id = str(user.get("tenant_id")) if user.get("tenant_id") else None
    token_tenant_slug = str(payload.get("tenant_slug") or "") or None
    
    logger.info(f"[auth] SUCCESS user_id={user_id} email={user.get('email')} tenant_id={user_tenant_id}")
    
    return {
        "id": str(user["id"]),
        "email": user["email"],
        "username": user.get("username"),
        "is_email_verified": bool(user["is_email_verified"]),
        "tenant_id": user_tenant_id,
        "tenant_slug": token_tenant_slug,
    }


def get_current_user(
    # Cookie-based session (primary for web)
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    # Bearer token (fallback for API clients)
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    """
    Get current user from cookie session or bearer token.
    
    Priority:
    1. Cookie session token (httpOnly cookie set by login/register)
    2. Bearer token in Authorization header
    
    Tenant is always resolved from the user record for user routes.
    """
    trace_id = str(uuid.uuid4())
    
    # Try cookie session first
    if session_token:
        logger.debug(f"[auth] Using cookie session, token_prefix={session_token[:8]}...")
        return _validate_token_and_get_user(session_token, trace_id, "cookie")
    
    # Fall back to bearer token
    if authorization:
        logger.debug("[auth] Using bearer token")
        try:
            token = _extract_bearer(authorization)
            return _validate_token_and_get_user(token, trace_id, "bearer")
        except AuthError as e:
            _log_auth_failure(e.reason, e.trace_id, auth_source="bearer")
            raise HTTPException(
                status_code=401,
                detail=AuthErrorDetail(message=e.detail, reason=e.reason, trace_id=e.trace_id).model_dump() if DEV_MODE else {"message": e.detail, "trace_id": e.trace_id},
            )
    
    # No auth provided
    _log_auth_failure("missing_token", trace_id, auth_source="none")
    raise HTTPException(
        status_code=401,
        detail=AuthErrorDetail(message="Authentication required", reason="missing_token", trace_id=trace_id).model_dump() if DEV_MODE else {"message": "Authentication required", "trace_id": trace_id},
    )


def get_current_user_for_admin(
    # Admin routes use bearer token only
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_tenant_slug: str | None = Header(default=None, alias="X-Tenant-Slug"),
) -> dict[str, Any]:
    """
    Get current user for admin routes.
    
    Uses bearer token only. Supports X-Tenant-Slug header for tenant selection.
    """
    trace_id = str(uuid.uuid4())
    
    if not authorization:
        _log_auth_failure("missing_token", trace_id, auth_source="admin")
        raise HTTPException(
            status_code=401,
            detail=AuthErrorDetail(message="Authentication required", reason="missing_token", trace_id=trace_id).model_dump() if DEV_MODE else {"message": "Authentication required", "trace_id": trace_id},
        )
    
    try:
        token = _extract_bearer(authorization)
        user = _validate_token_and_get_user(token, trace_id, "admin_bearer")
        # Add tenant slug from header for admin operations
        user["_admin_tenant_slug"] = x_tenant_slug
        return user
    except AuthError as e:
        _log_auth_failure(e.reason, e.trace_id, auth_source="admin")
        raise HTTPException(
            status_code=401,
            detail=AuthErrorDetail(message=e.detail, reason=e.reason, trace_id=e.trace_id).model_dump() if DEV_MODE else {"message": e.detail, "trace_id": e.trace_id},
        )


def require_verified_user(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    """Require email verification (currently deprecated for v1 UX)."""
    # Email verification has been deprecated for v1 product UX
    return current_user