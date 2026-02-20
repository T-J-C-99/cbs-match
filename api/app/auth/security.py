import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from fastapi import HTTPException
from passlib.context import CryptContext

from app.config import ACCESS_TOKEN_TTL_MINUTES, JWT_SECRET

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_access_token(
    user_id: str,
    email: str,
    is_email_verified: bool,
    ttl_minutes: int | None = None,
    tenant_id: str | None = None,
    tenant_slug: str | None = None,
) -> str:
    if not JWT_SECRET:
        raise HTTPException(status_code=500, detail="JWT secret not configured")
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=ttl_minutes or ACCESS_TOKEN_TTL_MINUTES)
    payload: dict[str, Any] = {
        "sub": user_id,
        "email": email,
        "verified": is_email_verified,
        "tenant_id": tenant_id,
        "tenant_slug": tenant_slug,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)


def create_access_token_with_tenant(
    user_id: str,
    email: str,
    is_email_verified: bool,
    tenant_id: str | None,
    tenant_slug: str | None,
    ttl_minutes: int | None = None,
) -> str:
    if not JWT_SECRET:
        raise HTTPException(status_code=500, detail="JWT secret not configured")
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=ttl_minutes or ACCESS_TOKEN_TTL_MINUTES)
    payload: dict[str, Any] = {
        "sub": user_id,
        "email": email,
        "verified": is_email_verified,
        "tenant_id": tenant_id,
        "tenant_slug": tenant_slug,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    if not JWT_SECRET:
        raise HTTPException(status_code=500, detail="JWT secret not configured")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        if not isinstance(payload, dict):
            raise HTTPException(status_code=401, detail="Invalid token")
        return payload
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="Token expired") from exc
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc


def create_admin_access_token(
    *,
    admin_id: str,
    email: str,
    role: str,
    ttl_minutes: int = 60,
    session_id: str | None = None,
) -> str:
    if not JWT_SECRET:
        raise HTTPException(status_code=500, detail="JWT secret not configured")
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=max(5, int(ttl_minutes)))
    payload: dict[str, Any] = {
        "sub": admin_id,
        "email": email,
        "role": role,
        "scope": "admin",
        "session_id": session_id,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)


def decode_admin_access_token(token: str) -> dict[str, Any]:
    payload = decode_access_token(token)
    if payload.get("scope") != "admin":
        raise HTTPException(status_code=401, detail="Invalid admin token")
    return payload


def create_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(refresh_token: str) -> str:
    if not JWT_SECRET:
        raise HTTPException(status_code=500, detail="JWT secret not configured")
    return hashlib.sha256(f"{JWT_SECRET}:{refresh_token}".encode("utf-8")).hexdigest()


def verify_refresh_token_hash(refresh_token: str, token_hash: str) -> bool:
    candidate = hash_refresh_token(refresh_token)
    return hmac.compare_digest(candidate, token_hash)


def create_one_time_token() -> str:
    return secrets.token_urlsafe(32)


def create_verification_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_verification_code(code: str) -> str:
    if not JWT_SECRET:
        raise HTTPException(status_code=500, detail="JWT secret not configured")
    return hashlib.sha256(f"verify-code:{JWT_SECRET}:{code}".encode("utf-8")).hexdigest()


def verify_verification_code(code: str, code_hash: str) -> bool:
    candidate = hash_verification_code(code)
    return hmac.compare_digest(candidate, code_hash)
