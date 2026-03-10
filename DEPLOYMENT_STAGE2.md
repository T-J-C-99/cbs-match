# CBS Match Stage 2: Staging infrastructure + deploy scripts

This stage establishes a repeatable staging deployment flow for API + web and a smoke test that validates auth and survey start.

## 1) Staging topology

- API: Railway/Render/Fly container deploy from `api/`
- DB: managed Postgres (separate staging instance)
- Web: Vercel project connected to `web/`
- Mobile: points to staging API via `EXPO_PUBLIC_API_BASE_URL`

## 2) Required staging environment variables

### API (staging)
- `APP_ENV=staging`
- `DEV_MODE=false`
- `DATABASE_URL=<staging_postgres_url>`
- `JWT_SECRET=<32+ char random>`
- `ADMIN_TOKEN=<24+ char random>`
- `CORS_ALLOWED_ORIGINS=https://staging.<your-web-domain>`
- `QUESTIONS_PATH=/app/questions.json` (or platform path)

### Web (staging)
- `NEXT_PUBLIC_API_BASE_URL=https://api-staging.<your-domain>`
- `API_BASE_URL=https://api-staging.<your-domain>`
- `ADMIN_TOKEN=<same staging admin token or server-side admin token>`

### Mobile (staging)
- `EXPO_PUBLIC_API_BASE_URL=https://api-staging.<your-domain>`

## 3) Deploy order

1. Deploy API to staging
2. Confirm API startup + migrations complete
3. Deploy web to staging
4. Run smoke test against staging API

## 4) Smoke test command

From repository root:

```bash
API_BASE_URL=https://api-staging.example.com ADMIN_TOKEN=<staging-admin-token> SMOKE_TENANT_SLUG=cbs python scripts/smoke_staging.py
```

What it validates:
- `/health`
- register/login token flow (`X-Auth-Mode: bearer`)
- `/auth/me`
- `/sessions` (survey start)
- `/sessions/{id}`
- optional admin match run (`/admin/matches/run-weekly`) when `ADMIN_TOKEN` is set
- `/matches/current`

## 5) Rollback basics

- API rollback: redeploy prior image/release in platform
- Web rollback: Vercel “Promote previous deployment”
- DB rollback: forward-fix preferred; restore snapshot only for critical incidents

## 6) Stage 2 exit criteria

- [x] Staging deploy runbook documented
- [x] Staging smoke script committed and runnable
- [x] Helper script for staging preflight checks committed
- [x] Commands documented for operator handoff
