# Auth + Survey Rebuild Focus Chain

## Non-negotiable Design
1. Web auth uses ONLY httpOnly cookie session. No bearer tokens in localStorage.
2. User-facing endpoints resolve tenant from authenticated user record (no X-Tenant-Slug for user routes).
3. All web fetches use single apiClient with `credentials: "include"`.
4. Survey versioning with proper missing question detection.

## Tasks Progress

### A) Delete/disable old web token storage + refresh flow
- [ ] Remove localStorage token persistence from AuthProvider.tsx
- [ ] Ensure login/register only sets cookie session and calls /me
- [ ] Ensure logout clears cookie session

### B) Implement web apiClient
- [ ] Create web/lib/apiClient.ts with credentials: "include"
- [ ] Create web/lib/formatError.ts for typed errors
- [ ] Update AuthProvider to use apiClient
- [ ] Update all survey runtime calls to use apiClient

### C) API: make cookie session authoritative
- [ ] Ensure login sets httpOnly cookie
- [ ] Ensure get_current_user reads session cookie
- [ ] Add structured 401 errors with reason + trace_id

### D) API: unify tenant resolution for user runtime
- [ ] User routes get tenant from user record
- [ ] Admin routes keep tenant selector logic

### E) Survey versioning + migration
- [ ] Define stable survey schema
- [ ] Implement GET /me with onboarding state
- [ ] Implement GET /survey/active
- [ ] Implement GET /survey/response
- [ ] Implement POST /survey/response
- [ ] Implement GET /survey/missing
- [ ] Update scoring to error on missing answers

### F) Web: rebuild survey start flow
- [ ] On app load: call /me, route appropriately
- [ ] Survey missing questions flow
- [ ] Complete -> dashboard routing

### G) Tests and verification
- [ ] API tests for auth flow
- [ ] API tests for survey flow
- [ ] Web tests for apiClient
- [ ] End-to-end verification

## Commands Log