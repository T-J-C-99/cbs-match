from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ..auth.deps import get_current_user
from ..database import SessionLocal
from ..services.events import log_analytics_event

router = APIRouter()
scaffold_router = APIRouter()


@scaffold_router.get("/health")
def events_scaffold_health() -> dict[str, str]:
    return {"status": "ok", "module": "events"}


@router.post("/events/track")
def track_event(payload: dict[str, Any], current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    event_name = str(payload.get("event_name") or "").strip()
    if not event_name:
        raise HTTPException(status_code=400, detail="event_name is required")
    if len(event_name) > 120:
        raise HTTPException(status_code=400, detail="event_name too long")

    properties = payload.get("properties") if isinstance(payload.get("properties"), dict) else {}
    week_start_date = str(payload.get("week_start_date") or "").strip() or None

    with SessionLocal() as db:
        log_analytics_event(
            db,
            event_name=event_name,
            user_id=str(current_user["id"]),
            tenant_id=str(current_user.get("tenant_id")) if current_user.get("tenant_id") else None,
            properties=properties,
            week_start_date=week_start_date,
            source="client",
        )
        db.commit()
    return {"status": "ok", "event_name": event_name}
