import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.config import DEFAULT_MATCHING_CONFIG, LOOKBACK_WEEKS, MATCH_TIMEZONE, SURVEY_SLUG, SURVEY_VERSION
from app.database import SessionLocal
from app.services.calibration import compute_calibration_report
from app.services.matching import get_week_start_date


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate current week calibration report")
    parser.add_argument("--lookback-weeks", type=int, default=LOOKBACK_WEEKS)
    args = parser.parse_args()

    now = datetime.now(timezone.utc)
    week_start = get_week_start_date(now, MATCH_TIMEZONE)

    with SessionLocal() as db:
        report = compute_calibration_report(
            db,
            survey_slug=SURVEY_SLUG,
            survey_version=SURVEY_VERSION,
            week_start_date=week_start,
            cfg=DEFAULT_MATCHING_CONFIG,
            lookback_weeks=args.lookback_weeks,
        )

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
