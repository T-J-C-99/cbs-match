# CBS Match Stage 1: Repo hardening + config templates

## Environment tiers

- local
- staging
- production

Use committed templates only:

- `api/.env.example`
- `web/.env.example`
- `mobile/.env.example`

## API required vars (staging/production)

- `APP_ENV` (`staging` or `production`)
- `DATABASE_URL`
- `JWT_SECRET` (32+ chars)
- `ADMIN_TOKEN` (24+ chars)
- `CORS_ALLOWED_ORIGINS` (explicit origins, comma-separated)

API startup fails fast in non-dev if required vars are missing/invalid.

## Web required vars

- `NEXT_PUBLIC_API_BASE_URL`
- `API_BASE_URL`
- `ADMIN_TOKEN` (server-only fallback)

Security note: do not use `NEXT_PUBLIC_ADMIN_TOKEN`.

## Mobile required vars

- `EXPO_PUBLIC_API_BASE_URL`

Use HTTPS API endpoints for staging/production iOS builds.

## Stage 1 exit criteria

- [x] `.env.example` templates for API/web/mobile
- [x] API startup env validation in non-dev
- [x] CORS configured via explicit allowlist env var
- [x] Required variables documented
- [x] No dev public admin token pattern in deployment docs
