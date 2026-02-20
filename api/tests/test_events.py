from datetime import date

from app.services.events import log_match_event


class FakeDB:
    def __init__(self):
        self.calls = []

    def execute(self, stmt, params):
        self.calls.append((str(stmt), params))


def test_log_match_event_inserts_expected_payload_shape():
    db = FakeDB()
    log_match_event(
        db=db,
        user_id="00000000-0000-0000-0000-000000000123",
        week_start_date=date(2026, 2, 9),
        event_type="match_viewed",
        payload={"status": "revealed"},
    )
    assert len(db.calls) == 1
    sql, params = db.calls[0]
    assert "INSERT INTO match_event" in sql
    assert params["event_type"] == "match_viewed"
    assert params["user_id"] == "00000000-0000-0000-0000-000000000123"
