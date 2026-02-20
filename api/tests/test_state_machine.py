from datetime import datetime, timedelta, timezone

from app.services.state_machine import transition_status


def test_state_machine_idempotent_accept_decline():
    now = datetime.now(timezone.utc)
    expires = now + timedelta(hours=2)

    assert transition_status("revealed", "accept", now, expires) == "accepted"
    assert transition_status("accepted", "accept", now, expires) == "accepted"

    assert transition_status("revealed", "decline", now, expires) == "declined"
    assert transition_status("declined", "decline", now, expires) == "declined"


def test_state_machine_proposed_to_revealed_and_expired():
    now = datetime.now(timezone.utc)
    expires = now + timedelta(hours=2)
    past = now - timedelta(hours=1)

    assert transition_status("proposed", "view", now, expires) == "revealed"
    assert transition_status("revealed", "view", now, expires) == "revealed"
    assert transition_status("proposed", "view", now, past) == "expired"
    assert transition_status("revealed", "accept", now, past) == "expired"


def test_no_match_terminal():
    now = datetime.now(timezone.utc)
    expires = now + timedelta(hours=2)
    assert transition_status("no_match", "view", now, expires) == "no_match"
    assert transition_status("no_match", "accept", now, expires) == "no_match"
