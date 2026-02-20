from fastapi import APIRouter, FastAPI

from .admin import router as admin_router, scaffold_router as admin_scaffold_router
from .auth import router as auth_router, scaffold_router as auth_scaffold_router
from .chat import router as chat_router, scaffold_router as chat_scaffold_router
from .events import router as events_router, scaffold_router as events_scaffold_router
from .match import router as match_router, scaffold_router as match_scaffold_router
from .profile import router as profile_router, scaffold_router as profile_scaffold_router
from .safety import router as safety_router, scaffold_router as safety_scaffold_router
from .survey import router as survey_router, scaffold_router as survey_scaffold_router


def include_modular_routers(app: FastAPI) -> None:
    app.include_router(auth_router, prefix="/auth", tags=["auth"])
    app.include_router(profile_router, tags=["users"])
    app.include_router(survey_router, tags=["survey"])
    app.include_router(chat_router, tags=["chat"])
    app.include_router(events_router, tags=["events"])
    app.include_router(safety_router, tags=["safety"])
    app.include_router(match_router, tags=["matches"])
    app.include_router(admin_router, tags=["admin"])

    app.include_router(auth_scaffold_router, prefix="/_scaffold/auth", tags=["scaffold-auth"])
    app.include_router(profile_scaffold_router, prefix="/_scaffold/profile", tags=["scaffold-profile"])
    app.include_router(survey_scaffold_router, prefix="/_scaffold/survey", tags=["scaffold-survey"])
    app.include_router(chat_scaffold_router, prefix="/_scaffold/chat", tags=["scaffold-chat"])
    app.include_router(events_scaffold_router, prefix="/_scaffold/events", tags=["scaffold-events"])
    app.include_router(safety_scaffold_router, prefix="/_scaffold/safety", tags=["scaffold-safety"])
    app.include_router(match_scaffold_router, prefix="/_scaffold/match", tags=["scaffold-match"])
    app.include_router(admin_scaffold_router, prefix="/_scaffold/admin", tags=["scaffold-admin"])


__all__ = ["include_modular_routers", "APIRouter"]
