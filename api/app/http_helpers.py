import json
import re
import uuid
from pathlib import Path
from typing import Any

from fastapi import HTTPException, Request, UploadFile


UPLOADS_DIR = Path(__file__).resolve().parents[1] / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def normalize_username(username: str) -> str:
    return username.strip().lower()


def validate_username(username: str) -> str:
    u = normalize_username(username)
    if not re.fullmatch(r"[a-z0-9_]{3,24}", u):
        raise HTTPException(status_code=400, detail="username must be 3-24 chars, lowercase letters/numbers/underscore")
    return u


def validate_registration_input(email: str, password: str) -> tuple[str, str]:
    e = normalize_email(email)
    if not e.endswith("@gsb.columbia.edu"):
        raise HTTPException(status_code=400, detail="Email must be @gsb.columbia.edu")
    if not re.match(r"^[a-zA-Z0-9._%+-]+@gsb\.columbia\.edu$", e):
        raise HTTPException(status_code=400, detail="Invalid email format")
    if len(e) > 254:
        raise HTTPException(status_code=400, detail="Email too long")
    if len(password) < 10:
        raise HTTPException(status_code=400, detail="Password must be at least 10 characters")
    return e, password


def public_upload_url(request: Request, filename: str) -> str:
    return f"{str(request.base_url).rstrip('/')}/uploads/{filename}"


async def store_uploaded_photo(file: UploadFile, owner_user_id: str, request: Request) -> str:
    content_type = (file.content_type or "").lower()
    if content_type not in {"image/jpeg", "image/jpg", "image/png", "image/webp"}:
        raise HTTPException(status_code=400, detail="Only JPG, PNG, and WEBP images are allowed")

    ext = ".jpg"
    if content_type == "image/png":
        ext = ".png"
    elif content_type == "image/webp":
        ext = ".webp"

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded image is empty")
    if len(data) > 8 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Each image must be <= 8MB")

    fname = f"{owner_user_id}_{uuid.uuid4().hex}{ext}"
    path = UPLOADS_DIR / fname
    path.write_bytes(data)
    return public_upload_url(request, fname)


def sanitize_profile_payload(payload: dict[str, Any], require_https_photo_urls: bool = False) -> tuple[str | None, str | None, str | None, str | None, str | None, list[str], str | None, list[str]]:
    raw_name = payload.get("display_name")
    display_name: str | None
    if raw_name is None:
        display_name = None
    else:
        display_name = str(raw_name).strip() or None
        if display_name and len(display_name) > 80:
            raise HTTPException(status_code=400, detail="display_name must be 80 characters or fewer")

    raw_year = payload.get("cbs_year")
    cbs_year: str | None
    if raw_year is None:
        cbs_year = None
    else:
        cbs_year = str(raw_year).strip() or None
        if cbs_year is not None and cbs_year not in {"26", "27"}:
            raise HTTPException(status_code=400, detail="cbs_year must be one of: 26, 27")

    raw_hometown = payload.get("hometown")
    hometown: str | None
    if raw_hometown is None:
        hometown = None
    else:
        hometown = str(raw_hometown).strip() or None
        if hometown and len(hometown) > 120:
            raise HTTPException(status_code=400, detail="hometown must be 120 characters or fewer")

    raw_phone_number = payload.get("phone_number")
    phone_number: str | None
    if raw_phone_number is None:
        phone_number = None
    else:
        phone_number = str(raw_phone_number).strip() or None
        if phone_number and len(phone_number) > 32:
            raise HTTPException(status_code=400, detail="phone_number must be 32 characters or fewer")

    raw_instagram = payload.get("instagram_handle")
    instagram_handle: str | None
    if raw_instagram is None:
        instagram_handle = None
    else:
        ig = str(raw_instagram).strip().lstrip("@")
        instagram_handle = ig or None
        if instagram_handle and len(instagram_handle) > 50:
            raise HTTPException(status_code=400, detail="instagram_handle must be 50 characters or fewer")

    raw_photo_urls = payload.get("photo_urls", [])
    if raw_photo_urls is None:
        raw_photo_urls = []
    if not isinstance(raw_photo_urls, list):
        raise HTTPException(status_code=400, detail="photo_urls must be an array")
    if len(raw_photo_urls) > 3:
        raise HTTPException(status_code=400, detail="You can provide up to 3 photo URLs")

    photo_urls: list[str] = []
    for value in raw_photo_urls:
        url = str(value or "").strip()
        if not url:
            continue
        if len(url) > 500:
            raise HTTPException(status_code=400, detail="Each photo URL must be 500 characters or fewer")
        if require_https_photo_urls:
            if not url.startswith("https://"):
                raise HTTPException(status_code=400, detail="Photo URLs must start with https://")
        else:
            if not (url.startswith("http://") or url.startswith("https://")):
                raise HTTPException(status_code=400, detail="Photo URLs must start with http:// or https://")
        photo_urls.append(url)

    allowed_genders = {"man", "woman", "nonbinary", "other"}
    raw_gender = payload.get("gender_identity")
    gender_identity: str | None
    if raw_gender is None:
        gender_identity = None
    else:
        gender_identity = str(raw_gender).strip().lower() or None
        if gender_identity is not None and gender_identity not in allowed_genders:
            raise HTTPException(status_code=400, detail="gender_identity must be one of: man, woman, nonbinary, other")

    raw_seeking = payload.get("seeking_genders", [])
    if raw_seeking is None:
        raw_seeking = []
    if not isinstance(raw_seeking, list):
        raise HTTPException(status_code=400, detail="seeking_genders must be an array")
    seeking_genders: list[str] = []
    for value in raw_seeking:
        item = str(value or "").strip().lower()
        if not item:
            continue
        if item not in allowed_genders:
            raise HTTPException(status_code=400, detail="seeking_genders may only include: man, woman, nonbinary, other")
        if item not in seeking_genders:
            seeking_genders.append(item)

    return display_name, cbs_year, hometown, phone_number, instagram_handle, photo_urls, gender_identity, seeking_genders
