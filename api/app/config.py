import json
import os
from pathlib import Path
from typing import Any

SURVEY_SLUG = "match-core-v3"
SURVEY_VERSION = 1
_default_questions = Path(__file__).resolve().parents[2] / "questions.json"
QUESTIONS_PATH = Path(os.getenv("QUESTIONS_PATH", str(_default_questions)))
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
ADMIN_BOOTSTRAP_EMAIL = os.getenv("ADMIN_BOOTSTRAP_EMAIL", "admin@cbsmatch.local").strip().lower()
ADMIN_BOOTSTRAP_PASSWORD = os.getenv("ADMIN_BOOTSTRAP_PASSWORD", "community123")
ADMIN_SESSION_TTL_MINUTES = int(os.getenv("ADMIN_SESSION_TTL_MINUTES", "480"))
MATCH_EXPIRY_HOURS = int(os.getenv("MATCH_EXPIRY_HOURS", "72"))
MATCH_TIMEZONE = os.getenv("MATCH_TIMEZONE", "America/New_York")
LOOKBACK_WEEKS = int(os.getenv("LOOKBACK_WEEKS", "6"))
MIN_SCORE = float(os.getenv("MIN_SCORE", "0.60"))
MATCH_TOP_K = int(os.getenv("MATCH_TOP_K", "60"))
MATCH_ALGO_MODE = os.getenv("MATCH_ALGO_MODE", "stable_bipartite_if_possible")

DEFAULT_MATCHING_CONFIG: dict[str, Any] = {
    "VALUES_W": float(os.getenv("VALUES_W", "0.22")),
    "EMO_STAB_W": float(os.getenv("EMO_STAB_W", "0.12")),
    "ATTACH_W": float(os.getenv("ATTACH_W", "0.22")),
    "CONFLICT_W": float(os.getenv("CONFLICT_W", "0.24")),
    "PERSONALITY_W": float(os.getenv("PERSONALITY_W", "0.12")),
    "LIFE_W": float(os.getenv("LIFE_W", "0.08")),
    "ESCALATION_GATE": float(os.getenv("ESCALATION_GATE", "0.95")),
    "ESCALATION_PENALTY_THRESHOLD": float(os.getenv("ESCALATION_PENALTY_THRESHOLD", "0.70")),
    "ESCALATION_PENALTY_MULTIPLIER": float(os.getenv("ESCALATION_PENALTY_MULTIPLIER", "0.75")),
    "WITHDRAWAL_PENALTY_THRESHOLD": float(os.getenv("WITHDRAWAL_PENALTY_THRESHOLD", "0.70")),
    "WITHDRAWAL_PENALTY_MULTIPLIER": float(os.getenv("WITHDRAWAL_PENALTY_MULTIPLIER", "0.85")),
    "MISMATCH_PENALTY_MULTIPLIER": float(os.getenv("MISMATCH_PENALTY_MULTIPLIER", "0.80")),
}

if os.getenv("MATCHING_CONFIG_JSON"):
    try:
        DEFAULT_MATCHING_CONFIG.update(json.loads(os.getenv("MATCHING_CONFIG_JSON", "{}")))
    except json.JSONDecodeError:
        pass

JWT_SECRET = os.getenv("JWT_SECRET", "")
ACCESS_TOKEN_TTL_MINUTES = int(os.getenv("ACCESS_TOKEN_TTL_MINUTES", "15"))
REFRESH_TOKEN_TTL_DAYS = int(os.getenv("REFRESH_TOKEN_TTL_DAYS", "30"))
VERIFICATION_TOKEN_TTL_HOURS = int(os.getenv("VERIFICATION_TOKEN_TTL_HOURS", "24"))
DEV_MODE = os.getenv("DEV_MODE", "false").lower() == "true"


RL_AUTH_REGISTER_LIMIT = int(os.getenv("RL_AUTH_REGISTER_LIMIT", "100"))
RL_AUTH_LOGIN_LIMIT = int(os.getenv("RL_AUTH_LOGIN_LIMIT", "100"))
RL_AUTH_VERIFY_EMAIL_LIMIT = int(os.getenv("RL_AUTH_VERIFY_EMAIL_LIMIT", "100"))
RL_AUTH_REFRESH_LIMIT = int(os.getenv("RL_AUTH_REFRESH_LIMIT", "120"))
RL_SESSION_ANSWERS_LIMIT = int(os.getenv("RL_SESSION_ANSWERS_LIMIT", "120"))
RL_MATCH_ACCEPT_LIMIT = int(os.getenv("RL_MATCH_ACCEPT_LIMIT", "100"))
RL_MATCH_DECLINE_LIMIT = int(os.getenv("RL_MATCH_DECLINE_LIMIT", "100"))
RL_MATCH_FEEDBACK_LIMIT = int(os.getenv("RL_MATCH_FEEDBACK_LIMIT", "100"))
RL_WINDOW_SECONDS = int(os.getenv("RL_WINDOW_SECONDS", "60"))
