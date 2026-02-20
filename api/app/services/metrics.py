from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import text


def _to_week(value: str) -> date:
    return date.fromisoformat(value)


def metrics_funnel_summary(db, *, date_from: date, date_to: date, tenant_id: str | None = None) -> dict[str, Any]:
    tenant_clause = "AND tenant_id = CAST(:tenant_id AS uuid)" if tenant_id else ""
    rows = db.execute(
        text(
            f"""
            SELECT event_name, COUNT(1) AS c
            FROM product_event
            WHERE created_at::date >= :date_from
              AND created_at::date <= :date_to
              {tenant_clause}
            GROUP BY event_name
            """
        ),
        {"date_from": date_from, "date_to": date_to, "tenant_id": tenant_id},
    ).mappings().all()
    counts = {str(r["event_name"]): int(r["c"]) for r in rows}

    def c(name: str) -> int:
        return counts.get(name, 0)

    def ratio(num: int, den: int) -> float:
        if den <= 0:
            return 0.0
        return round(num / den, 4)

    # Outcome-by-decile from weekly assignments.
    deciles = db.execute(
        text(
            f"""
            WITH scoped AS (
              SELECT wma.week_start_date, wma.user_id, wma.score_total
              FROM weekly_match_assignment wma
              WHERE wma.week_start_date >= :date_from
                AND wma.week_start_date <= :date_to
                AND wma.matched_user_id IS NOT NULL
                AND wma.score_total IS NOT NULL
                {"AND wma.tenant_id = CAST(:tenant_id AS uuid)" if tenant_id else ""}
            ),
            ranked AS (
              SELECT *, NTILE(10) OVER (ORDER BY score_total) AS decile
              FROM scoped
            )
            SELECT
              decile,
              COUNT(1) AS assignments,
              AVG(CASE WHEN status = 'accepted' THEN 1.0 ELSE 0.0 END) AS accept_rate
            FROM ranked r
            JOIN weekly_match_assignment w ON w.week_start_date = r.week_start_date AND w.user_id = r.user_id
            GROUP BY decile
            ORDER BY decile
            """
        ),
        {"date_from": date_from, "date_to": date_to, "tenant_id": tenant_id},
    ).mappings().all()

    return {
        "date_from": str(date_from),
        "date_to": str(date_to),
        "counts": counts,
        "kpis": {
            "registration_to_profile_complete": ratio(c("profile_completed"), c("auth_registered")),
            "profile_complete_to_survey_complete": ratio(c("survey_completed"), c("profile_completed")),
            "match_view_rate_24h": ratio(c("match_viewed"), c("match_created")),
            "accept_rate": ratio(c("match_accepted"), max(1, c("match_viewed"))),
            "decline_rate": ratio(c("match_declined"), max(1, c("match_viewed"))),
            "expiry_rate": ratio(c("match_expired"), max(1, c("match_created"))),
            "contact_click_rate_24h": ratio(c("contact_clicked_email") + c("contact_clicked_phone") + c("contact_clicked_ig"), max(1, c("match_viewed"))),
            "met_rate": ratio(c("met_self_reported"), max(1, c("match_viewed"))),
            "blocks_per_100_matches": round(100.0 * c("safety_block_created") / max(1, c("match_created")), 2),
            "reports_per_100_matches": round(100.0 * c("safety_report_created") / max(1, c("match_created")), 2),
        },
        "decile_outcomes": [
            {
                "decile": int(r["decile"]),
                "assignments": int(r["assignments"]),
                "accept_rate": round(float(r["accept_rate"] or 0.0), 4),
            }
            for r in deciles
        ],
    }


def metrics_weekly_funnel(db, *, week_start: date, tenant_id: str | None = None) -> dict[str, Any]:
    # Uses product_event snapshots inside week boundaries.
    week_end = week_start.fromordinal(week_start.toordinal() + 6)
    summary = metrics_funnel_summary(db, date_from=week_start, date_to=week_end, tenant_id=tenant_id)
    return {
        "week_start": str(week_start),
        "week_end": str(week_end),
        **summary,
    }
