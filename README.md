# CBS Match v1.5

Pilot-ready questionnaire and weekly matching app.

## Stack

- Web: Next.js App Router + TypeScript + Tailwind
- API: FastAPI + SQLAlchemy
- DB: Postgres
- Local runtime: Docker Compose

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
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 NEXT_PUBLIC_ADMIN_TOKEN=dev-admin-token npm run dev
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
