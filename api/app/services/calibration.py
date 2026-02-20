from datetime import date
from typing import Any

from sqlalchemy import text

from app.services.matching import build_candidate_pairs, fetch_eligible_users, fetch_recent_pairs


def _percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    vals = sorted(values)
    if len(vals) == 1:
        return round(vals[0], 6)
    pos = (len(vals) - 1) * p
    lo = int(pos)
    hi = min(lo + 1, len(vals) - 1)
    frac = pos - lo
    v = vals[lo] * (1 - frac) + vals[hi] * frac
    return round(v, 6)


def percentile_summary(values: list[float]) -> dict[str, float | None]:
    return {
        "p10": _percentile(values, 0.10),
        "p25": _percentile(values, 0.25),
        "p50": _percentile(values, 0.50),
        "p75": _percentile(values, 0.75),
        "p90": _percentile(values, 0.90),
    }


def compute_calibration_report(
    db,
    *,
    survey_slug: str,
    survey_version: int,
    week_start_date: date,
    cfg: dict[str, float],
    lookback_weeks: int,
) -> dict[str, Any]:
    users = fetch_eligible_users(db, survey_slug, survey_version)
    recent_pairs = fetch_recent_pairs(db, week_start_date, lookback_weeks)
    pairs = build_candidate_pairs(users, cfg=cfg, recent_pairs=recent_pairs)

    pair_scores = [float(p.score_total) for p in pairs]

    best_by_user: dict[str, float] = {}
    for p in pairs:
        best_by_user[p.user_id] = max(best_by_user.get(p.user_id, 0.0), float(p.score_total))
        best_by_user[p.matched_user_id] = max(best_by_user.get(p.matched_user_id, 0.0), float(p.score_total))
    best_scores = list(best_by_user.values())
    stability_proxy = {
        "best_score_p50": _percentile(best_scores, 0.50),
        "best_score_iqr": None,
        "best_score_std_approx": None,
    }
    p25 = _percentile(best_scores, 0.25)
    p75 = _percentile(best_scores, 0.75)
    if p25 is not None and p75 is not None:
        stability_proxy["best_score_iqr"] = round(p75 - p25, 6)
        # Robust std approximation from IQR under near-normal assumption.
        stability_proxy["best_score_std_approx"] = round((p75 - p25) / 1.349, 6)

    assigned_rows = db.execute(
        text(
            """
            SELECT score_total, status
            FROM weekly_match_assignment
            WHERE week_start_date = :week_start_date
            """
        ),
        {"week_start_date": week_start_date},
    ).mappings().all()

    assigned_scores = [float(r['score_total']) for r in assigned_rows if r['score_total'] is not None]
    total_assignments = len(assigned_rows)
    no_match_count = sum(1 for r in assigned_rows if r['status'] == 'no_match')
    no_match_rate = round((no_match_count / total_assignments), 6) if total_assignments else 0.0

    return {
        "week_start_date": str(week_start_date),
        "eligible_users": len(users),
        "candidate_pair_count": len(pairs),
        "pair_score_distribution": {
            "count": len(pair_scores),
            "percentiles": percentile_summary(pair_scores),
        },
        "per_user_best_distribution": {
            "count": len(best_scores),
            "percentiles": percentile_summary(best_scores),
        },
        "assigned_distribution": {
            "count": len(assigned_scores),
            "percentiles": percentile_summary(assigned_scores),
        },
        "assignment_counts": {
            "total_assignments": total_assignments,
            "no_match_count": no_match_count,
            "no_match_rate": no_match_rate,
        },
        "stability_proxy": stability_proxy,
    }
