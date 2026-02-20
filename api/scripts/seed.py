import argparse
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.config import SURVEY_SLUG, SURVEY_VERSION
from app.database import SessionLocal
from app.services.seeding import seed_all_tenants_dummy_data, seed_dummy_data
from app.survey_loader import get_survey_definition


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed dummy CBS Match users")
    parser.add_argument("--n-users", type=int, default=100)
    parser.add_argument("--survey-slug", type=str, default=SURVEY_SLUG)
    parser.add_argument("--survey-version", type=int, default=SURVEY_VERSION)
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--clustered", action="store_true")
    parser.add_argument("--all-tenants", action="store_true")
    parser.add_argument("--tenant-slug", type=str, default="")
    parser.add_argument("--include-qa-login", action="store_true")
    parser.add_argument("--qa-password", type=str, default="community123")
    args = parser.parse_args()

    survey = get_survey_definition()
    with SessionLocal() as db:
        if args.all_tenants:
            summary = seed_all_tenants_dummy_data(
                db=db,
                survey_def=survey,
                survey_slug=args.survey_slug,
                survey_version=args.survey_version,
                n_users_per_tenant=args.n_users,
                reset=args.reset,
                seed=args.seed,
                clustered=args.clustered,
                include_qa_login=args.include_qa_login,
                qa_password=args.qa_password,
            )
        else:
            summary = seed_dummy_data(
                db=db,
                survey_def=survey,
                survey_slug=args.survey_slug,
                survey_version=args.survey_version,
                n_users=args.n_users,
                reset=args.reset,
                seed=args.seed,
                clustered=args.clustered,
                tenant_slug=args.tenant_slug.strip().lower() or None,
                include_qa_login=args.include_qa_login,
                qa_password=args.qa_password,
            )

    print("Seed completed")
    for k, v in summary.items():
        print(f"- {k}: {v}")


if __name__ == "__main__":
    main()
