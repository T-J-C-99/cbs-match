from datetime import datetime


def transition_status(current: str, action: str, now: datetime, expires_at: datetime) -> str:
    if current == "no_match":
        return "no_match"

    if current in {"proposed", "revealed"} and now >= expires_at:
        return "expired"

    if action == "view":
        if current == "proposed":
            return "revealed"
        return current

    if action == "accept":
        if current == "revealed":
            return "accepted"
        if current == "accepted":
            return "accepted"
        return current

    if action == "decline":
        if current == "revealed":
            return "declined"
        if current == "declined":
            return "declined"
        return current

    if action == "expire":
        if current in {"proposed", "revealed"}:
            return "expired"
        return current

    return current
