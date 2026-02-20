- [x] WS-A deterministic vibe card backend and UI
- [x] WS-B funnel events and KPI metrics
- [x] WS-C notifications outbox and worker processing
- [x] WS-D router migration audit and cleanup
- [x] WS-E tests and validation runs
- [x] WS-F rollout summary and verification artifacts
- [x] Run relevant test/lint/typecheck commands and fix regressions

Validation snapshots:
- `python -m py_compile api/app/main.py api/app/repo.py api/app/routes/admin.py api/app/routes/events.py api/app/routes/profile.py api/app/routes/__init__.py` ✅
- `npm --prefix /Users/thomascline/Desktop/cbs-match --workspace cbs-match-web run lint` ✅ (warnings only; no new blocking errors)
- `npm --prefix /Users/thomascline/Desktop/cbs-match --workspace cbs-match-mobile exec tsc --noEmit` ✅
- `npm --prefix /Users/thomascline/Desktop/cbs-match run shared:test` ✅
- `python -m pytest -q api/tests/test_auth_api.py api/tests/test_events.py api/tests/test_matching.py api/tests/test_trust_safety.py` ✅
- `cd /Users/thomascline/Desktop/cbs-match/api && pytest -q` ✅
- `cd /Users/thomascline/Desktop/cbs-match/api && pytest -q tests/test_route_migration_guards.py` ✅
- `cd /Users/thomascline/Desktop/cbs-match/api && pytest -q tests/test_router_contract_baseline.py` ✅
- `npm --prefix /Users/thomascline/Desktop/cbs-match/web run lint` ✅
- `npm --prefix /Users/thomascline/Desktop/cbs-match/web run build` ✅
- `cd /Users/thomascline/Desktop/cbs-match/web && npx jest --config jest.config.ts --runInBand` ✅
- `npm --prefix /Users/thomascline/Desktop/cbs-match run shared:test` ✅
- `cd /Users/thomascline/Desktop/cbs-match/mobile && npx tsc --noEmit` ✅

- [x] Summarize changes and verification results

System scope documentation note:
- `docs/SYSTEM_SCOPE.md`
- `docs/SYSTEM_INDEX.md`
- Documented current product behavior and tenant model with only code-backed statements.
- Indexed FastAPI endpoints, Next.js page routes, DB tables, and shared exports for quick lookup.
- Mapped required critical flows with explicit web/API/DB/service wiring and invariants.
- Called out concrete, testable gaps (manual outbox processing, dual outbox schemas, verification bypass behavior, process-local rate limits, chat UI absence).
- Included runbook commands that match repo scripts, startup migration behavior, seeding, weekly run, and validation battery.

---

## Admin Portal hardening (tenant reliability + diagnostics + selector regression checks)

### What changed
- Fixed a critical admin router regression in `api/app/routes/admin.py` where undefined variables (`tenant_id`, `open_reports_rows`) were referenced in the wrong handlers, causing admin instability. `open_reports_rows` is now computed in dashboard only.
- Hardened `/admin/tenants` route behavior to keep compatibility with existing tests/mocks while still supporting `include_disabled=true`.
- Confirmed startup tenant sync path (`api/app/main.py` + `api/app/services/tenancy.py`) remains active and idempotent, including pre/post sync logging.
- Added web proxy support for admin diagnostics and tenant resync:
  - `web/app/api/admin/diagnostics/route.ts`
  - `web/app/api/admin/tenants/resync-from-shared/route.ts`
- Updated admin tenants proxy to forward query params correctly:
  - `web/app/api/admin/tenants/route.ts`
- Improved dashboard UX by wiring in diagnostics data (`/api/admin/diagnostics`) with per-tenant cards and current-week visibility.
- Improved users admin UX significantly:
  - tenant scope filter (all + per-tenant)
  - onboarding filter
  - search
  - eligible/paused filters
  - count + offset pagination controls
  - user detail panel (traits version, last match week, blocks count, etc.)
- Improved tenants admin UX with explicit **Sync from shared config** action.
- Added web regression test for tenant selector loading from `/api/admin/tenants`:
  - `web/__tests__/admin-tenant-selector.test.ts`

### How to run
- API contract checks:
  - `cd /Users/thomascline/Desktop/cbs-match && python -m py_compile api/app/routes/admin.py api/app/services/tenancy.py api/app/main.py`
  - `cd /Users/thomascline/Desktop/cbs-match/api && pytest -q tests/test_admin_portal_contracts.py`
- Web selector regression check:
  - `cd /Users/thomascline/Desktop/cbs-match/web && npx jest --config jest.config.ts --runInBand __tests__/admin-tenant-selector.test.ts`

### Verification results
- `py_compile` for admin/tenancy/main: ✅
- `pytest -q tests/test_admin_portal_contracts.py`: ✅ (`3 passed`)
- `jest` tenant selector test: ✅ (`1 passed`)

---

## Admin portal world-class hardening pass (tenant reliability + data surfaces + UX + regression checks)

### Key fixes delivered
- **Tenant reliability root-cause hardening**
  - Startup sync remains enforced and idempotent (`api/app/main.py` + `api/app/services/tenancy.py`).
  - `/admin/tenants` now defensively re-syncs shared tenant config before listing, preventing “only CBS appears” drift when startup paths are skipped.
  - Added/confirmed tenant summary + diagnostics plumbing to reduce silent zero-data states.

- **Backend admin capability expansion**
  - `repo_week_summary` now supports tenant filtering.
  - Added admin routes for audit feed and survey initialization from code.
  - Extended diagnostics payload with per-tenant `eligible_users`, `unique_pairs_current_week`, `accepts_current_week`, `feedback_count_current_week`.
  - Week summary route now forwards query string tenant filters.

- **Web admin UX upgrades**
  - Matching page now includes status table, week summary cards, force rerun confirmations, CSV export, and run result visibility.
  - Safety page now includes filters, paginated table, detail panel, resolve flow, and export JSON action.
  - Notifications page now includes filters, pending-by-tenant summary, process action, retry action, details panel, and pagination.
  - Survey admin client now supports initialize-from-code, draft lifecycle actions, overview/editor/diff/preview tabs, validation and rollback flows.
  - Metrics and calibration pages now render card/table dashboards instead of raw JSON-only output.

- **Regression tests and test-runtime hardening**
  - Added tenant sync unit coverage (`api/tests/test_tenant_sync.py`).
  - Updated admin portal contract test to account for defensive tenant re-sync behavior.
  - Added web smoke coverage for matching/safety/notifications/metrics/calibration/survey admin surfaces (`web/__tests__/admin-pages-smoke.test.tsx`).
  - Added Jest TextEncoder/TextDecoder polyfill in `web/jest.setup.ts` for stable CI-like execution.

### Verification commands (this pass)
- `python3 -m pytest /Users/thomascline/Desktop/cbs-match/api/tests/test_tenant_sync.py /Users/thomascline/Desktop/cbs-match/api/tests/test_admin_portal_contracts.py -q` ✅ (`4 passed`)
- `cd /Users/thomascline/Desktop/cbs-match/web && npx jest --config jest.config.ts --runInBand __tests__/admin-tenant-selector.test.ts __tests__/admin-pages-smoke.test.tsx` ✅ (`2 suites passed, 7 tests passed`)
- `npm --prefix /Users/thomascline/Desktop/cbs-match/web run lint` ✅ (warnings only, no blocking errors)

### Manual smoke checklist still recommended
- Fresh DB startup: confirm `/admin/tenants` shows all 7 shared tenants.
- `/admin/seed` with `reset=true`: confirm tenants persist.
- Matching run(s): confirm diagnostics/status tables update and outbox rows appear.
- Survey initialize/publish/rollback flows in UI with tenant preview.

---

## 2026-02-19: Root-cause fix for “only CBS tenant appears” + admin reliability hardening

### Root cause found
- **Primary regression path:** all-tenant seed reset only deleted `seed_<tenant>_*` users per tenant, leaving historical tenant users (especially CBS) in place. This made diagnostics/dashboard look “CBS-only” and created misleading zeroes elsewhere.
- **Secondary reliability gap:** admin tenant scope state could retain stale/non-canonical values (e.g., “all” / invalid slug) causing inconsistent query behavior across pages.
- **Hardening concern:** needed explicit proof that `/admin/tenants` is never tenant-header scoped and always returns the full registry.

### What changed
- **Seed reset fixed (platform-safe):** `api/app/services/seeding.py`
  - tenant-scoped reset now removes all users for target tenant (plus dependent records), not only seed-pattern users.
  - keeps tenant registry untouched, so `/admin/seed reset=true` no longer causes cross-tenant drift.
- **Tenant scope normalization (web):**
  - added `web/lib/admin-tenant-scope.ts`.
  - `AdminPortalProvider` now normalizes/persists admin tenant selection to canonical `"" | valid slug`.
  - updated dashboard/users/matching/safety/notifications/metrics pages to use normalized scope and omit `tenant_slug` when “All tenants” is selected.
- **Admin header cleanup:**
  - `web/components/tenant/TenantHeaderActions.tsx` now hides end-user community switch on `/admin/*`.
- **Diagnostics/dashboard polish:**
  - `web/app/admin/page.tsx` now shows aggregate totals, anomaly warning hints, percent formatting, and a one-click “Seed all tenants” remediation action.
  - `api/app/routes/admin.py` diagnostics now returns `overall` totals aggregate.
- **API hardening confirmation:**
  - `/admin/tenants` behavior verified header-independent and still returns full tenant list.

### Regression tests added/updated
- **API:** `api/tests/test_admin_portal_contracts.py`
  - `/admin/tenants` unaffected by `X-Tenant-Slug` header.
  - all-tenant seed fanout covers every shared tenant slug.
  - dashboard global call uses `tenant_slug=None` when unscoped.
- **Web:** `web/__tests__/admin-dashboard-scope.test.tsx`
  - dashboard omits tenant query for “All tenants”.
  - includes `tenant_slug` for scoped tenant.

### Verification run (this pass)
- `python3 -m py_compile api/app/main.py api/app/routes/admin.py api/app/services/tenancy.py api/app/services/seeding.py` ✅
- `cd /Users/thomascline/Desktop/cbs-match/api && pytest -q tests/test_admin_portal_contracts.py` ✅ (`6 passed`)
- `cd /Users/thomascline/Desktop/cbs-match/web && npx jest --config jest.config.ts --runInBand __tests__/admin-tenant-selector.test.ts __tests__/admin-dashboard-scope.test.tsx __tests__/admin-pages-smoke.test.tsx` ✅ (`3 suites, 9 tests passed`)
- `cd /Users/thomascline/Desktop/cbs-match/web && npm run lint` ✅ (warnings only, no blocking errors)
- Manual API checks:
  - `/admin/tenants` returns `7` slugs ✅
  - `/admin/tenants` with `X-Tenant-Slug: cbs` still returns `7` slugs ✅
  - `/admin/seed {all_tenants:true, reset:true}` then `/admin/tenants` still returns `7` ✅

### Live reseed + QA login alignment (requested)
- Executed:
  - `POST /admin/seed` with `{ "all_tenants": true, "n_users_per_tenant": 60, "reset": true, "include_qa_login": true, "qa_password": "community123" }`
- Verified returned QA accounts include:
  - `qa_cbs@gsb.columbia.edu`
  - `qa_hbs@hbs.edu`
  - `qa_gsb@stanford.edu`
  - `qa_wharton@wharton.upenn.edu`
  - `qa_kellogg@kellogg.northwestern.edu`
  - `qa_booth@chicagobooth.edu`
  - `qa_sloan@mitsloan.mit.edu`
- Observed CBS had extra legacy users from prior runs, then cleaned non-seed/non-QA CBS users via admin delete endpoint.
- Post-clean verification from `/admin/diagnostics`:
  - `cbs 61`, `hbs 61`, `gsb 61`, `wharton 61`, `kellogg 61`, `booth 61`, `sloan 61` ✅

---

## 2026-02-19: Survey admin end-to-end repair (Active none / drafts none)

### Root cause
- Startup bootstrap gate used `count_definitions()==0` globally. If **any** survey rows existed for other slugs, `SURVEY_SLUG` could still have no active row, causing `/admin/survey/active` to return all null.
- Initialize endpoint behavior was not truly idempotent and could route through draft+publish flow unnecessarily.

### Fixes implemented
- **Slug-scoped startup bootstrap** (`api/app/main.py`):
  - now checks `get_active_definition(SURVEY_SLUG)` instead of global count before bootstrap.
- **Robust initialize-from-code repository API** (`api/app/survey_admin_repo.py`):
  - added `initialize_active_from_code(slug, definition_json, actor_user_id, force=False)`.
  - idempotent no-op if active exists and `force=false`.
  - atomic active handoff when initializing/forcing (deactivate prior active, insert new published active).
  - writes survey change log entry.
- **Admin initialize endpoint hardened** (`api/app/routes/admin.py`):
  - accepts optional payload with `force`.
  - loads the same runtime code definition source (`get_file_survey_definition`).
  - validates with `validate_survey_definition` before persistence.
  - writes admin audit event `survey_initialize_from_code`.
  - returns active + latest draft + published versions.
- **Web proxy + UI reliability**:
  - `web/app/api/admin/survey/initialize-from-code/route.ts` forwards request JSON body.
  - `web/components/AdminSurveyClient.tsx` tightened UX labels and publish disabled state when no draft exists.

### Tests added
- **API**: `api/tests/test_admin_survey_lifecycle.py`
  - initialize-from-empty → create draft → save → validate → publish → rollback lifecycle coverage.
- **Web**: `web/__tests__/admin-survey-initialize.test.tsx`
  - verifies initialize flow transitions UI from `Active: none` to `Active: v1`.

### Verification
- `python3 -m py_compile api/app/main.py api/app/survey_admin_repo.py api/app/routes/admin.py` ✅
- `cd /Users/thomascline/Desktop/cbs-match/api && pytest -q tests/test_admin_survey_lifecycle.py tests/test_admin_portal_contracts.py` ✅ (`7 passed`)
- `cd /Users/thomascline/Desktop/cbs-match/web && npx jest --config jest.config.ts --runInBand __tests__/admin-survey-initialize.test.tsx __tests__/admin-pages-smoke.test.tsx` ✅ (`2 suites, 7 tests passed`)
- `cd /Users/thomascline/Desktop/cbs-match/web && npm run lint` ✅ (warnings only)

### Runbook updates
- Added survey initialize/version lifecycle section to `docs/ADMIN_PORTAL_RUNBOOK.md` with command examples and expected semantics.

---

## 2026-02-19: Surveys Admin debugging evidence + reliability fixes

### Evidence captured first (before final fixes)
- Direct API probe against currently running local server showed mismatch symptoms:
  - `GET /admin/diagnostics/tenant-coverage` returned `404` (route missing in running process)
  - `PUT /admin/survey/draft/latest` accepted string payload and returned `200` with `definition_json` string (invalid contract)
  - `GET /admin/survey/preview?tenant_slug=cbs` returned only `survey` + `tenant_slug` and no `source`/comparison fields
- This indicated the live process was stale relative to current code and explained UI behavior drift/silent failures.

### Fixes applied
- **Web surveys admin (`web/components/AdminSurveyClient.tsx`)**
  - Added request instrumentation and debug panel (`?debug=1`) with last 10 calls: method/url/status/trimmed req+res/error.
  - Added robust request error surfacing with status + message + request/trace id and inline validation error list.
  - Fixed save payload shape to always send `{ definition_json: ... }`.
  - Added invalid JSON diagnostics (line/col), and disabled Save/Validate/Publish when JSON invalid.
  - Prevented editing when no draft exists (shows active JSON read-only with guidance).
  - Added preview tenant selector and explicit source labels: Active (DB) vs Runtime (code).
- **Admin dashboard (`web/app/admin/page.tsx`)**
  - Wired tenant coverage diagnostics endpoint into UI and added coverage table.
- **API survey update endpoint (`api/app/routes/admin.py`)**
  - Made request body explicit with `Body(...)` for `/admin/survey/draft/latest` so JSON body is parsed and custom validation executes (instead of FastAPI 422 preemption path).
- **Regression tests**
  - `api/tests/test_admin_survey_lifecycle.py`: invalid draft JSON now asserted as structured `400` error with `trace_id`.
  - `api/tests/test_admin_portal_contracts.py`: added `/admin/diagnostics/tenant-coverage` shape contract test.
  - `web/__tests__/admin-survey-initialize.test.tsx`: added invalid-JSON save-blocking test and endpoint-call assertions.
  - `web/__tests__/admin-pages-smoke.test.tsx`: mock provider updated for new `tenants` dependency.

### Verification commands + results
- `pytest -q api/tests/test_admin_survey_lifecycle.py api/tests/test_admin_portal_contracts.py` ✅ (`10 passed`)
- `cd /Users/thomascline/Desktop/cbs-match/web && npx jest --config jest.config.ts --runInBand __tests__/admin-survey-initialize.test.tsx __tests__/admin-dashboard-scope.test.tsx __tests__/admin-pages-smoke.test.tsx` ✅ (`3 suites, 11 tests passed`)

### Operator note
- If your running API still returns 404 on `/admin/diagnostics/tenant-coverage` or old survey preview shape, restart the API process/container so the updated routes are loaded.