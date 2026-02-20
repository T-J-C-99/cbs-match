import json
import uuid
from typing import Any

from sqlalchemy import text


def log_match_event(
    db,
    user_id: str,
    week_start_date,
    event_type: str,
    payload: dict[str, Any] | None = None,
    tenant_id: str | None = None,
) -> None:
    payload = payload or {}
    db.execute(
        text(
            """
            INSERT INTO match_event (id, user_id, tenant_id, week_start_date, event_type, payload)
            VALUES (:id, CAST(:user_id AS uuid), CAST(NULLIF(:tenant_id, '') AS uuid), :week_start_date, :event_type, CAST(:payload AS jsonb))
            """
        ),
        {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "tenant_id": tenant_id or "",
            "week_start_date": week_start_date,
            "event_type": event_type,
            "payload": json.dumps(payload),
        },
    )


def log_profile_event(
    db,
    user_id: str,
    event_type: str,
    payload: dict[str, Any] | None = None,
    tenant_id: str | None = None,
) -> None:
    payload = payload or {}
    db.execute(
        text(
            """
            INSERT INTO user_profile_event (id, user_id, tenant_id, event_type, payload)
            VALUES (:id, CAST(:user_id AS uuid), CAST(NULLIF(:tenant_id, '') AS uuid), :event_type, CAST(:payload AS jsonb))
            """
        ),
        {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "tenant_id": tenant_id or "",
            "event_type": event_type,
            "payload": json.dumps(payload),
        },
    )


def log_product_event(
    db,
    *,
    event_name: str,
    user_id: str | None = None,
    tenant_id: str | None = None,
    session_id: str | None = None,
    properties: dict[str, Any] | None = None,
) -> None:
    properties = properties or {}
    db.execute(
        text(
            """
            INSERT INTO product_event (id, user_id, tenant_id, session_id, event_name, properties)
            VALUES (
              :id,
              CAST(NULLIF(:user_id, '') AS uuid),
              CAST(NULLIF(:tenant_id, '') AS uuid),
              CAST(NULLIF(:session_id, '') AS uuid),
              :event_name,
              CAST(:properties AS jsonb)
            )
            """
        ),
        {
            "id": str(uuid.uuid4()),
            "user_id": user_id or "",
            "tenant_id": tenant_id or "",
            "session_id": session_id or "",
            "event_name": event_name,
            "properties": json.dumps(properties),
        },
    )


def log_analytics_event(
    db,
    *,
    event_name: str,
    tenant_id: str | None,
    user_id: str | None = None,
    properties: dict[str, Any] | None = None,
    week_start_date: str | None = None,
    source: str = "api",
) -> None:
    properties = properties or {}
    db.execute(
        text(
            """
            INSERT INTO analytics_event (id, tenant_id, user_id, event_name, properties_json, week_start_date, source)
            VALUES (
              :id,
              CAST(NULLIF(:tenant_id, '') AS uuid),
              CAST(NULLIF(:user_id, '') AS uuid),
              :event_name,
              CAST(:properties_json AS jsonb),
              :week_start_date,
              :source
            )
            """
        ),
        {
            "id": str(uuid.uuid4()),
            "tenant_id": tenant_id or "",
            "user_id": user_id or "",
            "event_name": event_name,
            "properties_json": json.dumps(properties),
            "week_start_date": week_start_date,
            "source": source,
        },
    )
