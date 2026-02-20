from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from .. import repo as auth_repo
from ..auth.deps import require_verified_user

router = APIRouter()
scaffold_router = APIRouter()


@scaffold_router.get("/health")
def chat_scaffold_health() -> dict[str, str]:
    return {"status": "ok", "module": "chat"}


@router.get("/chat/threads")
def list_chat_threads(current_user: dict[str, Any] = Depends(require_verified_user)) -> dict[str, Any]:
    tenant_id = str(current_user.get("tenant_id")) if current_user.get("tenant_id") else None
    rows = auth_repo.get_user_chat_threads(str(current_user["id"]), tenant_id=tenant_id)
    threads = []
    for r in rows:
        threads.append(
            {
                "id": str(r["id"]),
                "week_start_date": str(r["week_start_date"]),
                "other_profile": {
                    "id": str(r["other_user_id"]),
                    "display_name": r.get("other_display_name") or (str(r.get("other_email") or "").split("@")[0] if r.get("other_email") else "Match"),
                    "email": r.get("other_email"),
                    "cbs_year": r.get("other_cbs_year"),
                    "hometown": r.get("other_hometown"),
                    "photo_urls": r.get("other_photo_urls") if isinstance(r.get("other_photo_urls"), list) else [],
                },
                "latest_message": {
                    "body": r.get("latest_message_body"),
                    "created_at": r.get("latest_message_at"),
                },
            }
        )
    return {"threads": threads}


@router.get("/chat/threads/{thread_id}")
def get_chat_thread(thread_id: str, current_user: dict[str, Any] = Depends(require_verified_user)) -> dict[str, Any]:
    tenant_id = str(current_user.get("tenant_id")) if current_user.get("tenant_id") else None
    t = auth_repo.get_thread_by_id(thread_id, tenant_id=tenant_id)
    if not t:
        raise HTTPException(status_code=404, detail="Thread not found")
    uid = str(current_user["id"])
    a = str(t["participant_a_id"])
    b = str(t["participant_b_id"])
    if uid not in {a, b}:
        raise HTTPException(status_code=403, detail="Forbidden")
    other_id = b if uid == a else a
    other = auth_repo.get_user_public_profile(other_id)
    messages = auth_repo.get_thread_messages(thread_id, tenant_id=tenant_id)
    return {
        "thread": {
            "id": str(t["id"]),
            "week_start_date": str(t["week_start_date"]),
            "other_profile": {
                "id": str(other["id"]) if other else other_id,
                "display_name": (other or {}).get("display_name") or str((other or {}).get("email") or "Match").split("@")[0],
                "email": (other or {}).get("email"),
                "cbs_year": (other or {}).get("cbs_year"),
                "hometown": (other or {}).get("hometown"),
                "photo_urls": (other or {}).get("photo_urls") if isinstance((other or {}).get("photo_urls"), list) else [],
            },
            "messages": [
                {
                    "id": str(m["id"]),
                    "sender_user_id": str(m["sender_user_id"]),
                    "body": m["body"],
                    "created_at": m["created_at"],
                }
                for m in messages
            ],
        }
    }


@router.post("/chat/threads/{thread_id}/messages")
def send_chat_message(thread_id: str, payload: dict[str, Any], current_user: dict[str, Any] = Depends(require_verified_user)) -> dict[str, Any]:
    body = str(payload.get("body") or "").strip()
    if not body:
        raise HTTPException(status_code=400, detail="Message body required")
    if len(body) > 2000:
        raise HTTPException(status_code=400, detail="Message too long")

    tenant_id = str(current_user.get("tenant_id")) if current_user.get("tenant_id") else None
    t = auth_repo.get_thread_by_id(thread_id, tenant_id=tenant_id)
    if not t:
        raise HTTPException(status_code=404, detail="Thread not found")
    uid = str(current_user["id"])
    if uid not in {str(t["participant_a_id"]), str(t["participant_b_id"])}:
        raise HTTPException(status_code=403, detail="Forbidden")

    message = auth_repo.create_chat_message(thread_id=thread_id, sender_user_id=uid, body=body, tenant_id=tenant_id)
    return {
        "message": {
            "id": str(message["id"]),
            "thread_id": str(message["thread_id"]),
            "sender_user_id": str(message["sender_user_id"]),
            "body": message["body"],
            "created_at": message.get("created_at"),
        }
    }
