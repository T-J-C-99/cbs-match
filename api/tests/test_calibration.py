from datetime import date

import app.services.calibration as c


class FakeDB:
    def execute(self, stmt, params):
        class R:
            def mappings(self_inner):
                class M:
                    def all(self_in):
                        return [
                            {"score_total": 0.9, "status": "accepted"},
                            {"score_total": 0.7, "status": "revealed"},
                            {"score_total": None, "status": "no_match"},
                        ]
                return M()
        return R()


def test_percentile_summary_deterministic():
    out = c.percentile_summary([0.1, 0.2, 0.3, 0.4, 0.5])
    assert out["p50"] == 0.3
    assert out["p90"] == 0.46


def test_compute_calibration_report_counts(monkeypatch):
    monkeypatch.setattr(c, "fetch_eligible_users", lambda *args, **kwargs: [{"user_id": "u1"}, {"user_id": "u2"}, {"user_id": "u3"}])
    monkeypatch.setattr(c, "fetch_recent_pairs", lambda *args, **kwargs: set())

    class P:
        def __init__(self, u, v, s):
            self.user_id = u
            self.matched_user_id = v
            self.score_total = s

    monkeypatch.setattr(c, "build_candidate_pairs", lambda *args, **kwargs: [P("u1", "u2", 0.8), P("u1", "u3", 0.6), P("u2", "u3", 0.4)])

    report = c.compute_calibration_report(
        FakeDB(),
        survey_slug="cbs-match-v1",
        survey_version=1,
        week_start_date=date(2026, 2, 9),
        cfg={},
        lookback_weeks=6,
    )

    assert report["eligible_users"] == 3
    assert report["candidate_pair_count"] == 3
    assert report["assignment_counts"]["no_match_count"] == 1
    assert report["assignment_counts"]["no_match_rate"] == 0.333333
    assert "stability_proxy" in report
    assert "best_score_p50" in report["stability_proxy"]
