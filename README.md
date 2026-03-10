# CBS Match v1.5

Pilot-ready questionnaire and weekly matching app.

## Stack

## Stage 1 deployment hardening

Stage 1 deployment setup (env templates, API startup validation, and required variable checklist) is documented in:

- `DEPLOYMENT_STAGE1.md`


- Web: Next.js App Router + TypeScript + Tailwind
- API: FastAPI + SQLAlchemy
- DB: Postgres
- Local runtime: Docker Compose

## GitHub CI

Automated checks run on every push and PR to `main`:

- **API**: Python 3.11 + pip install + pytest
- **Web**: Node 20 + npm install + lint + jest
- **Shared**: Node 20 + npm install + vitest

View status: Check the "CI" workflow in the Actions tab on GitHub.

### How to verify build locally

Run the same checks CI runs:

```bash
# API tests
cd api && pip install -r requirements.txt && pytest -q

# Web lint and tests
cd web && npm install && npm run lint && npx jest --config jest.config.ts --runInBand

# Shared package tests
cd packages/shared && npm install && npm test
```

## Smoke Test (Docker Compose)

Verify the full stack boots and responds:

```bash
./scripts/smoke_compose.sh
```

This will:
1. Create a placeholder `questions.json` if missing
2. Run `docker compose up -d --build`
3. Wait up to 120s for API at `http://localhost:8000/health`
4. Wait up to 120s for Web at `http://localhost:3000`
5. Report success or show logs on failure

Cleanup after testing:

```bash
./scripts/smoke_compose.sh cleanup
# or
docker compose down
```

## Test It Yourself (local, no Docker)

Start API + web + mobile with one command:

```bash
cd /Users/thomascline/Desktop/cbs-match
npm run dev:up
```

Notes for `dev:up` and `dev:down`:

- `dev:up` now checks `http://127.0.0.1:8000/survey/active` first. If it returns 200, it reuses the existing API process and continues.
- If port 8000 is occupied but not healthy, `dev:up` exits with a clear conflict message by default.
- Set `DEV_UP_KILL_EXISTING_API=true` to let `dev:up` kill the current listener on 8000 and start API itself.
- `dev:down` only stops processes started by `dev:up` by default.
- Set `DEV_DOWN_KILL_8000=true` to also kill any current listener on port 8000.

Examples:

```bash
# Reuse healthy existing API
cd /Users/thomascline/Desktop/cbs-match
npm run dev:up

# Force replace whatever is listening on 8000
cd /Users/thomascline/Desktop/cbs-match
DEV_UP_KILL_EXISTING_API=true npm run dev:up

# Stop script-started services only
cd /Users/thomascline/Desktop/cbs-match
npm run dev:down

# Also clear any process on 8000
cd /Users/thomascline/Desktop/cbs-match
DEV_DOWN_KILL_8000=true npm run dev:down
```

Start only web + mobile (API already running):

```bash
cd /Users/thomascline/Desktop/cbs-match
npm run dev:wm
```

Stop background services started by the scripts:

```bash
cd /Users/thomascline/Desktop/cbs-match
npm run dev:down
```

Open web:

- http://localhost:3000

Mobile quick flow:

- In Expo terminal press `i` for iOS simulator or `a` for Android emulator.
- Register, verify, and login in the mobile app.
- With `DEV_MODE=true`, register returns `dev_only.verification_token` and API also prints a verify curl line in logs.
- Use that token in the Verify screen or call `/auth/verify-email`.

API base URL guidance for mobile:

- iOS simulator: `http://localhost:8000`
- Android emulator: `http://10.0.2.2:8000`
- Physical device on same WiFi: `http://<LAN_IP>:8000`

For physical devices, set the value in the mobile Settings screen API base URL override.

## New in v1.5

- Deterministic weekly one-to-one matching pipeline
- Match assignment persistence with auditable score breakdown JSON
- /match user flow with accept and decline actions
- /admin flow for weekly run and seed actions
- Dummy data seeding for 50 to 200+ users
- Trait schema upgraded for matching inputs
- Automated tests for rules, traits, persistence flow, and matching invariants

## Docker run

```bash
cd /Users/thomascline/Desktop/cbs-match
docker compose up --build
```

Open:
- Web: http://localhost:3000/start
- Match: http://localhost:3000/match
- Admin: http://localhost:3000/admin
- API docs: http://localhost:8000/docs

## Non-docker run

1) Start local Postgres and set DATABASE_URL.
2) API:
```bash
cd /Users/thomascline/Desktop/cbs-match/api
pip install -r requirements.txt
export DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/cbs_match
export QUESTIONS_PATH=/Users/thomascline/Desktop/cbs-match/questions.json
uvicorn app.main:app --reload --port 8000
```
3) Web:
```bash
cd /Users/thomascline/Desktop/cbs-match/web
npm install
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 ADMIN_TOKEN=dev-admin-token npm run dev
```

## Seed dummy data

CLI:
```bash
cd /Users/thomascline/Desktop/cbs-match
python api/scripts/seed.py --n-users 120 --reset
```

Admin endpoint:
- `POST /admin/seed` with `X-Admin-Token`

## Weekly matching APIs

- `GET /matches/current` using `X-User-Id`
- `POST /matches/current/accept`
- `POST /matches/current/decline`
- `POST /admin/matches/run-weekly` using `X-Admin-Token`
- `GET /admin/matches/week/{week_start_date}` using `X-Admin-Token`

## Make targets

```bash
make up
make down
make seed N=120
make test
make match
```

## Tests

```bash
cd /Users/thomascline/Desktop/cbs-match/api
pytest -q
```

## Pilot smoke harness

Run this end-to-end check against a running API. It validates:

- auth register, verify, login
- survey completion and traits computation
- weekly match run and current match retrieval
- accept flow
- report and block basics

Important:

- start API with `DEV_MODE=true` so `/auth/register` returns `dev_only.verification_token`
- set `ADMIN_TOKEN` so admin endpoints are callable

Example local run:

```bash
cd /Users/thomascline/Desktop/cbs-match/api
export DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/cbs_match
export QUESTIONS_PATH=/Users/thomascline/Desktop/cbs-match/questions.json
export JWT_SECRET=dev-jwt-secret
export DEV_MODE=true
export ADMIN_TOKEN=dev-admin-token
uvicorn app.main:app --reload --port 8000
```

In another terminal:

```bash
cd /Users/thomascline/Desktop/cbs-match
API_BASE_URL=http://localhost:8000 ADMIN_TOKEN=dev-admin-token python scripts/smoke_pilot.py
```

Expected result:

- script prints `[PASS]` steps through the full flow
- exits `0` on success, nonzero on failure


## v2.5 pilot additions

- Calibration report endpoint: `GET /admin/calibration/current-week`
- Safe match explanations and icebreakers in `GET /matches/current`
- Outcome feedback endpoint: `POST /matches/current/feedback`
- Calibration CLI: `python api/scripts/calibration_report.py`

### Suggested run sequence

```bash
cd /Users/thomascline/Desktop/cbs-match
docker compose up --build
python api/scripts/seed.py --n-users 120 --reset --clustered
curl -s -X POST http://localhost:8000/admin/matches/run-weekly -H "X-Admin-Token: dev-admin-token"
curl -s http://localhost:8000/admin/calibration/current-week -H "X-Admin-Token: dev-admin-token"
cd /Users/thomascline/Desktop/cbs-match/api && pytest -q
```


## Mobile app with Expo

A new React Native app is available in `/mobile` and shared questionnaire logic is in `/packages/shared`.

### Install and run

```bash
cd /Users/thomascline/Desktop/cbs-match
npm install
npm run mobile
```

From Expo CLI:
- Press `i` for iOS simulator
- Press `a` for Android emulator

### Useful commands

```bash
npm run shared:test
cd /Users/thomascline/Desktop/cbs-match/mobile && npm run ios
cd /Users/thomascline/Desktop/cbs-match/mobile && npm run android
```

### API base URL notes

- iOS simulator: `http://localhost:8000`
- Android emulator: `http://10.0.2.2:8000`
- Physical device: use your machine LAN IP like `http://192.168.x.x:8000`

You can change the API base URL from mobile Settings or by setting:

```bash
EXPO_PUBLIC_API_BASE_URL=http://localhost:8000
```

The app stores `user_id` in SecureStore and sends it in `X-User-Id` headers for development auth.


## Stage 2 staging deployment

Use the Stage 2 runbook and smoke scripts:

- `DEPLOYMENT_STAGE2.md`
- `scripts/staging_preflight.sh`
- `scripts/smoke_staging.py`

Example:

```bash
cd /Users/thomascline/Desktop/cbs-match
API_BASE_URL=https://api-staging.example.com \
ADMIN_TOKEN=<staging-admin-token> \
SMOKE_TENANT_SLUG=cbs \
./scripts/staging_preflight.sh
```

## Render backend deployment

The repo now includes `render.yaml` for publishing the FastAPI backend and Postgres on Render.

### What Render will create

- `cbs-match-api` web service from `api/Dockerfile`
- `cbs-match-db` managed Postgres database

### Before first production use

After creating the Blueprint in Render, set these values in the Render web service:

- `CORS_ALLOWED_ORIGINS` = your Vercel frontend URL(s), comma-separated
  - example: `https://your-vercel-app.vercel.app,https://www.yourdomain.com`
- `ADMIN_BOOTSTRAP_EMAIL` = admin login email you want to use
- `ADMIN_BOOTSTRAP_PASSWORD` = strong admin password (replace the default)

Render will generate `JWT_SECRET` and `ADMIN_TOKEN` automatically from `render.yaml`.

### After backend is live

Copy the Render backend URL and add this in Vercel:

- `API_BASE_URL=https://your-render-api.onrender.com`

If any browser-side code must call the API directly, also add:

- `NEXT_PUBLIC_API_BASE_URL=https://your-render-api.onrender.com`

Then redeploy the Vercel frontend.
