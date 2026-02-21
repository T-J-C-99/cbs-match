from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, UploadFile
from sqlalchemy import text

from .. import repo as auth_repo
from ..auth.deps import SESSION_COOKIE_NAME, get_current_user
from ..auth.security import (
    create_access_token_with_tenant,
    create_one_time_token,
    create_refresh_token,
    create_verification_code,
    hash_password,
    hash_refresh_token,
    hash_verification_code,
    verify_password,
    verify_verification_code,
)
from ..config import (
    ACCESS_TOKEN_TTL_MINUTES,
    DEV_MODE,
    REFRESH_TOKEN_TTL_DAYS,
    RL_AUTH_LOGIN_LIMIT,
    RL_AUTH_REFRESH_LIMIT,
    RL_AUTH_REGISTER_LIMIT,
    RL_AUTH_VERIFY_EMAIL_LIMIT,
    RL_WINDOW_SECONDS,
    VERIFICATION_TOKEN_TTL_HOURS,
)
from ..database import SessionLocal
from ..http_helpers import sanitize_profile_payload, store_uploaded_photo, validate_registration_input, validate_username, normalize_email
from ..services.events import log_product_event
from ..services.rate_limit import rate_limit_dependency
from ..services.tenancy import (
    ensure_email_allowed_for_tenant,
    get_shared_tenant_definitions,
    get_tenant_by_slug,
    resolve_tenant_for_email,
)

router = APIRouter()
scaffold_router = APIRouter()

RL_AUTH_REGISTER = rate_limit_dependency("auth_register", RL_AUTH_REGISTER_LIMIT, RL_WINDOW_SECONDS)
RL_AUTH_LOGIN = rate_limit_dependency("auth_login", RL_AUTH_LOGIN_LIMIT, RL_WINDOW_SECONDS)
RL_AUTH_VERIFY_EMAIL = rate_limit_dependency("auth_verify_email", RL_AUTH_VERIFY_EMAIL_LIMIT, RL_WINDOW_SECONDS)
RL_AUTH_REFRESH = rate_limit_dependency("auth_refresh", RL_AUTH_REFRESH_LIMIT, RL_WINDOW_SECONDS)


def create_access_token(**kwargs: Any) -> str:
    """Backward-compatible token factory used by tests and legacy callsites."""
    return create_access_token_with_tenant(**kwargs)


def _repo_get_user_by_email(email: str, tenant_id: str | None = None) -> dict[str, Any] | None:
    try:
        return auth_repo.get_user_by_email(email, tenant_id=tenant_id)
    except TypeError:
        return auth_repo.get_user_by_email(email)


def _repo_get_user_by_username(username: str, tenant_id: str | None = None) -> dict[str, Any] | None:
    try:
        return auth_repo.get_user_by_username(username, tenant_id=tenant_id)
    except TypeError:
        return auth_repo.get_user_by_username(username)


def _repo_is_username_available(username: str, tenant_id: str | None = None) -> bool:
    try:
        return auth_repo.is_username_available(username, tenant_id=tenant_id)
    except TypeError:
        return auth_repo.is_username_available(username)


def _issue_tokens_compat(user: dict[str, Any], *, tenant_slug: str | None = None) -> dict[str, Any]:
    try:
        return _issue_tokens(user, tenant_slug=tenant_slug)
    except TypeError:
        return _issue_tokens(user)


def _issue_tokens(user: dict[str, Any], *, tenant_slug: str | None = None) -> dict[str, Any]:
    """Issue access and refresh tokens for a user."""
    import logging
    logger = logging.getLogger(__name__)
    
    user_id = str(user["id"])
    user_email = str(user["email"])
    user_tenant_id = str(user.get("tenant_id")) if user.get("tenant_id") else None
    
    logger.info(f"[_issue_tokens] Creating tokens for user_id={user_id}, email={user_email}, tenant_id={user_tenant_id}, tenant_slug={tenant_slug}")
    
    access_token = create_access_token(
        user_id=user_id,
        email=user_email,
        is_email_verified=bool(user["is_email_verified"]),
        tenant_id=user_tenant_id,
        tenant_slug=tenant_slug,
        ttl_minutes=ACCESS_TOKEN_TTL_MINUTES,
    )
    
    logger.info(f"[_issue_tokens] Token created: {access_token[:20]}... for tenant_slug={tenant_slug}")
    
    refresh_token = create_refresh_token()
    refresh_token_hash = hash_refresh_token(refresh_token)
    expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_TTL_DAYS)
    auth_repo.create_refresh_token_row(str(user["id"]), refresh_token_hash, expires_at)
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_TTL_MINUTES * 60,
    }


def _is_bearer_mode(request: Request) -> bool:
    """Check if client requested bearer token mode (for mobile clients)."""
    auth_mode = str(request.headers.get("X-Auth-Mode") or "").strip().lower()
    return auth_mode == "bearer"


def _set_session_cookie(response: Response, access_token: str) -> None:
    """Set the httpOnly session cookie with the access token."""
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=access_token,
        httponly=True,
        secure=False,  # Set to True in production with HTTPS
        samesite="lax",
        path="/",
        max_age=ACCESS_TOKEN_TTL_MINUTES * 60,
    )


def _clear_session_cookie(response: Response) -> None:
    """Clear the httpOnly session cookie."""
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
    )


def _issue_email_verification_code(user_id: str, email: str) -> dict[str, Any]:
    verification_token = create_one_time_token()
    verification_code = "123456" if DEV_MODE else create_verification_code()
    verification_code_hash = hash_verification_code(verification_code)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=VERIFICATION_TOKEN_TTL_HOURS)

    auth_repo.invalidate_active_verification_tokens(user_id)
    auth_repo.create_email_verification_token(
        user_id=user_id,
        token=verification_token,
        expires_at=expires_at,
        code_hash=verification_code_hash,
    )

    print(f"[auth] verification code for {email}: {verification_code}")
    print(
        "[auth] verify curl: "
        "curl -s -X POST http://localhost:8000/auth/verify-email "
        "-H 'Content-Type: application/json' "
        f"-d '{{\"email\":\"{email}\",\"code\":\"{verification_code}\"}}'"
    )

    response: dict[str, Any] = {
        "message": "Verification code sent. Enter the 6-digit code to verify your email.",
    }
    if DEV_MODE:
        response["dev_only"] = {"verification_code": verification_code}
    return response


@scaffold_router.get("/health")
def auth_scaffold_health() -> dict[str, str]:
    return {"status": "ok", "module": "auth"}


@router.post("/register", status_code=201)
async def auth_register(request: Request, response: Response, _: None = RL_AUTH_REGISTER) -> dict[str, Any]:
    """Register endpoint that sets httpOnly session cookie."""
    content_type = request.headers.get("content-type", "")
    payload: dict[str, Any]
    upload_files: list[UploadFile] = []
    if "multipart/form-data" in content_type:
        form = await request.form()
        payload = {
            "email": str(form.get("email") or ""),
            "password": str(form.get("password") or ""),
            "username": str(form.get("username") or "").strip() or None,
            "display_name": str(form.get("display_name") or "").strip() or None,
            "cbs_year": str(form.get("cbs_year") or "").strip() or None,
            "hometown": str(form.get("hometown") or "").strip() or None,
            "gender_identity": str(form.get("gender_identity") or "").strip() or None,
            "seeking_genders": form.getlist("seeking_genders"),
        }
        upload_files = [f for f in form.getlist("photos") if isinstance(f, UploadFile)]
    else:
        payload = await request.json()

    email, password = validate_registration_input(str(payload.get("email", "")), str(payload.get("password", "")))
    tenant_slug_header = str(request.headers.get("X-Tenant-Slug") or "").strip().lower() or None
    tenant_id: str | None = None
    tenant_slug: str | None = None
    with SessionLocal() as db:
        try:
            if tenant_slug_header:
                tenant = get_tenant_by_slug(db, tenant_slug_header)
                if not tenant:
                    raise ValueError("Tenant not found")
            else:
                tenant = resolve_tenant_for_email(db, email)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not ensure_email_allowed_for_tenant(email, tenant):
            raise HTTPException(
                status_code=400,
                detail=f"That email domain is not valid for {tenant.get('name')}. Try your school email.",
            )
        tenant_id = str(tenant.get("id")) if tenant.get("id") else None
        tenant_slug = str(tenant.get("slug") or "") or None

    with SessionLocal() as db:
        log_product_event(
            db,
            event_name="register_started",
            tenant_id=tenant_id,
            properties={"platform": "api"},
        )
        db.commit()

    existing_user = _repo_get_user_by_email(email, tenant_id=tenant_id)
    if existing_user:
        raise HTTPException(status_code=409, detail="Email already registered")

    raw_username = payload.get("username")
    username = validate_username(str(raw_username)) if raw_username is not None and str(raw_username).strip() else None
    if username and not _repo_is_username_available(username, tenant_id=tenant_id):
        raise HTTPException(status_code=409, detail="Username is already taken")

    if username is None:
        created = auth_repo.create_user(email=email, password_hash=hash_password(password), tenant_id=tenant_id)
    else:
        created = auth_repo.create_user(email=email, password_hash=hash_password(password), username=username, tenant_id=tenant_id)
    if not created:
        raise HTTPException(status_code=409, detail="Email already registered")

    auth_repo.set_user_verified(str(created["id"]))
    created["is_email_verified"] = True

    display_name, cbs_year, hometown, phone_number, instagram_handle, existing_photo_urls, gender_identity, seeking_genders = sanitize_profile_payload(payload)
    photo_urls = existing_photo_urls
    if upload_files:
        if len(upload_files) > 3:
            raise HTTPException(status_code=400, detail="You can upload up to 3 photos")
        photo_urls = [await store_uploaded_photo(f, str(created["id"]), request) for f in upload_files]

    auth_repo.update_user_profile(
        user_id=str(created["id"]),
        display_name=display_name,
        cbs_year=cbs_year,
        hometown=hometown,
        phone_number=phone_number,
        instagram_handle=instagram_handle,
        photo_urls=photo_urls,
        gender_identity=gender_identity,
        seeking_genders=seeking_genders,
    )
    with SessionLocal() as db:
        log_product_event(
            db,
            event_name="register_completed",
            user_id=str(created["id"]),
            tenant_id=tenant_id,
            properties={"method": "password", "platform": "api"},
        )
        log_product_event(
            db,
            event_name="auth_registered",
            user_id=str(created["id"]),
            tenant_id=tenant_id,
            properties={"method": "password", "platform": "api"},
        )
        db.commit()
    created["tenant_id"] = tenant_id
    
    tokens = _issue_tokens_compat(created, tenant_slug=tenant_slug)
    
    # Set httpOnly session cookie (harmless for mobile, required for web)
    _set_session_cookie(response, tokens["access_token"])
    
    # If client requested bearer mode (mobile), return tokens in body
    if _is_bearer_mode(request):
        return tokens
    
    # Return user info (no tokens in body - they're in cookie)
    return {
        "id": str(created["id"]),
        "email": str(created["email"]),
        "username": created.get("username"),
        "is_email_verified": bool(created["is_email_verified"]),
        "tenant_slug": tenant_slug,
    }


@router.post("/verify-email")
def auth_verify_email(payload: dict[str, Any], _: None = RL_AUTH_VERIFY_EMAIL) -> dict[str, Any]:
    email = normalize_email(str(payload.get("email", "")))
    code = str(payload.get("code", "")).strip()
    if not email:
        raise HTTPException(status_code=400, detail="Email required")
    if not code or len(code) != 6 or not code.isdigit():
        raise HTTPException(status_code=400, detail="6-digit verification code required")

    user = _repo_get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid email or code")

    if bool(user.get("is_email_verified")):
        return {"message": "Email already verified"}

    row = auth_repo.get_latest_active_verification_for_user(str(user["id"]))
    if not row:
        raise HTTPException(status_code=400, detail="Verification code not found. Request a new code.")

    if row.get("expires_at") is None or row["expires_at"] < datetime.now(timezone.utc):
        auth_repo.mark_token_used(str(row["id"]))
        raise HTTPException(status_code=400, detail="Verification code expired. Request a new code.")

    if int(row.get("failed_attempts") or 0) >= 8:
        auth_repo.mark_token_used(str(row["id"]))
        raise HTTPException(status_code=400, detail="Too many attempts. Request a new code.")

    code_hash = row.get("code_hash")
    if DEV_MODE and code == "123456":
        auth_repo.set_user_verified(str(user["id"]))
        auth_repo.mark_token_used(str(row["id"]))
        return {"message": "Email verified"}

    if not code_hash or not verify_verification_code(code, str(code_hash)):
        auth_repo.increment_verification_failed_attempts(str(row["id"]))
        raise HTTPException(status_code=400, detail="Invalid email or code")

    auth_repo.set_user_verified(str(user["id"]))
    auth_repo.mark_token_used(str(row["id"]))
    return {"message": "Email verified"}


@router.post("/verify-email/resend")
def auth_verify_email_resend(payload: dict[str, Any], _: None = RL_AUTH_VERIFY_EMAIL) -> dict[str, Any]:
    email = normalize_email(str(payload.get("email", "")))
    if not email:
        raise HTTPException(status_code=400, detail="Email required")

    user = _repo_get_user_by_email(email)
    if not user:
        return {"message": "If the account exists, a new verification code was sent."}

    if bool(user.get("is_email_verified")):
        return {"message": "Email already verified"}

    return _issue_email_verification_code(str(user["id"]), email)


@router.post("/login")
def auth_login(payload: dict[str, Any], request: Request, response: Response, _: None = RL_AUTH_LOGIN) -> dict[str, Any]:
    """Login endpoint that sets httpOnly session cookie."""
    login_id = str(payload.get("identifier") or payload.get("email") or payload.get("username") or "").strip()
    password = str(payload.get("password", ""))
    tenant_slug_header = str(request.headers.get("X-Tenant-Slug") or payload.get("tenant_slug") or "").strip().lower() or None
    if not login_id:
        raise HTTPException(status_code=400, detail="email or username required")

    resolved_tenant: dict[str, Any] | None = None
    if tenant_slug_header:
        with SessionLocal() as db:
            resolved_tenant = get_tenant_by_slug(db, tenant_slug_header)
        if not resolved_tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
    elif "@" in login_id:
        with SessionLocal() as db:
            try:
                resolved_tenant = resolve_tenant_for_email(db, normalize_email(login_id))
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

    tenant_id = str((resolved_tenant or {}).get("id")) if resolved_tenant and resolved_tenant.get("id") else None
    if "@" in login_id:
        user = _repo_get_user_by_email(normalize_email(login_id), tenant_id=tenant_id)
    else:
        user = _repo_get_user_by_username(validate_username(login_id), tenant_id=tenant_id)
    if not user or not verify_password(password, str(user["password_hash"])):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if user.get("disabled_at"):
        raise HTTPException(status_code=403, detail="Account disabled")

    user_tenant_id = str(user.get("tenant_id")) if user.get("tenant_id") else None
    user_tenant_slug: str | None = None
    with SessionLocal() as db:
        if user_tenant_id:
            row = db.execute(
                text("SELECT slug FROM tenant WHERE id=CAST(:id AS uuid)"),
                {"id": user_tenant_id},
            ).mappings().first()
            if row:
                user_tenant_slug = str(row.get("slug") or "") or None
    if tenant_slug_header and user_tenant_slug and tenant_slug_header != user_tenant_slug:
        raise HTTPException(status_code=403, detail="You can only log into the tenant your account belongs to.")

    if not bool(user.get("is_email_verified")):
        auth_repo.set_user_verified(str(user["id"]))
        user["is_email_verified"] = True

    auth_repo.update_last_login(str(user["id"]))
    with SessionLocal() as db:
        log_product_event(
            db,
            event_name="login_success",
            user_id=str(user["id"]),
            tenant_id=str(user.get("tenant_id")) if user.get("tenant_id") else None,
            properties={"identifier_type": "email" if "@" in login_id else "username"},
        )
        log_product_event(
            db,
            event_name="auth_logged_in",
            user_id=str(user["id"]),
            tenant_id=str(user.get("tenant_id")) if user.get("tenant_id") else None,
            properties={"identifier_type": "email" if "@" in login_id else "username"},
        )
        db.commit()
    
    tokens = _issue_tokens_compat(user, tenant_slug=user_tenant_slug)
    
    # Set httpOnly session cookie (harmless for mobile, required for web)
    _set_session_cookie(response, tokens["access_token"])
    
    # If client requested bearer mode (mobile), return tokens in body
    if _is_bearer_mode(request):
        return tokens
    
    # Return user info (no tokens in body - they're in cookie)
    return {
        "id": str(user["id"]),
        "email": str(user["email"]),
        "username": user.get("username"),
        "is_email_verified": bool(user["is_email_verified"]),
        "tenant_slug": user_tenant_slug,
    }


@router.post("/refresh")
def auth_refresh(payload: dict[str, Any], _: None = RL_AUTH_REFRESH) -> dict[str, Any]:
    token = str(payload.get("refresh_token", "")).strip()
    if not token:
        raise HTTPException(status_code=400, detail="refresh_token required")

    token_hash = hash_refresh_token(token)
    row = auth_repo.get_refresh_token_row(token_hash)
    if not row or row.get("revoked_at") is not None:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    if row.get("expires_at") is None or row["expires_at"] < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Refresh token expired")

    user = auth_repo.get_user_by_id(str(row["user_id"]))
    if not user or user.get("disabled_at"):
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    new_refresh = create_refresh_token()
    new_hash = hash_refresh_token(new_refresh)
    new_exp = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_TTL_DAYS)
    auth_repo.rotate_refresh_token(token_hash, str(user["id"]), new_hash, new_exp)

    user_tenant_slug: str | None = None
    with SessionLocal() as db:
        if user.get("tenant_id"):
            row = db.execute(
                text("SELECT slug FROM tenant WHERE id=CAST(:id AS uuid)"),
                {"id": str(user.get("tenant_id"))},
            ).mappings().first()
            if row:
                user_tenant_slug = str(row.get("slug") or "") or None

    access_token = create_access_token(
        user_id=str(user["id"]),
        email=str(user["email"]),
        is_email_verified=bool(user["is_email_verified"]),
        tenant_id=str(user.get("tenant_id")) if user.get("tenant_id") else None,
        tenant_slug=user_tenant_slug,
        ttl_minutes=ACCESS_TOKEN_TTL_MINUTES,
    )
    return {
        "access_token": access_token,
        "refresh_token": new_refresh,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_TTL_MINUTES * 60,
    }


@router.post("/logout")
def auth_logout(response: Response, current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    """Logout endpoint that clears httpOnly session cookie."""
    # Revoke any refresh tokens (optional, for cleanup)
    # The session cookie is cleared regardless
    
    # Clear httpOnly session cookie
    _clear_session_cookie(response)
    
    return {"message": "Logged out"}


@router.get("/me")
def auth_me(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    return {
        "id": str(current_user["id"]),
        "email": str(current_user["email"]),
        "username": current_user.get("username"),
        "is_email_verified": bool(current_user["is_email_verified"]),
    }


@router.get("/username-availability")
def auth_username_availability(username: str, request: Request) -> dict[str, Any]:
    normalized = validate_username(username)
    tenant_slug_header = str(request.headers.get("X-Tenant-Slug") or "").strip().lower() or None
    tenant_id: str | None = None
    if tenant_slug_header:
        with SessionLocal() as db:
            tenant = get_tenant_by_slug(db, tenant_slug_header)
            if not tenant:
                raise HTTPException(status_code=404, detail="Tenant not found")
            tenant_id = str(tenant.get("id")) if tenant.get("id") else None
    return {"username": normalized, "available": _repo_is_username_available(normalized, tenant_id=tenant_id)}


@router.get("/public/tenants")
def public_tenants() -> dict[str, Any]:
    return {"tenants": get_shared_tenant_definitions()}
