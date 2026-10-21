# Security Review Packet — R03 Audit Fixes

Branch: `review/audit-fix-2026-10-22`  
Remote: `https://github.com/wtrg/meta-muse-bot.git`  
Target: Verification of R03 audit resolution (`audit/REVIEW_R03_5d4948a.md`).

---

## 1. Summary of Changes

### Finding 1: Dead Callers of Removed Endpoints Neutralized (P1)
- **`scripts/bot_server.py`**:
  - `create_spinup_email` explicitly raises `NotImplementedError` explaining deprecation of unauthenticated `/api/public/bulk-create`.
  - `StartBotRequest` now validates `provider`: rejects `provider="spinupmail"` with a 422 HTTP validation error guiding users to Clean TempMail or authenticated mailbox management.
- **`packages/frontend/src/pages/bulk-create-page.tsx`**:
  - Completely purged all background polling and dead fetch calls to `/api/public/recent-otps`, `/api/public/bulk-create`, and `/api/public/auto-login`.
  - Replaced with security guidance cards directing users to authenticated `/addresses` and verified `/otp`.
- **Scripts cleanup (`audit_muse_flow.py`, `test_create_muse_account.py`, `test_complete_flow.py`)**:
  - Replaced dead calls to `/api/public/bulk-create` with `NotImplementedError` explanations.

### Finding 2: Reserved Alias `latest` Rejected on Session Exports (P1)
- **`scripts/bot_server.py`**:
  - Defined `RESERVED_SESSION_ALIASES = frozenset({"latest", "current", "default", "all", "null", "undefined"})`.
  - Both `/api/bot/export-session-csv` and `/api/bot/export-session-excel` reject requests where `session_id` matches any reserved alias with HTTP 400.
  - Prevents retrieving old `muse_session_latest.csv` / `muse_session_latest.xlsx` artifacts via parameter spoofing.
  - Unit tests added in `scripts/tests/test_muse_regression_v5.py`.

### Finding 3: Rate Limiting Fail-Closed on Shared Store Outage & Dual-Budget Protection (P1)
- **`packages/backend/src/modules/public-otp/router.ts`**:
  - When `env.FIXED_WINDOW_RATE_LIMITERS` is provided and fails/throws (Durable Object outage, timeout, or partition), `checkOtpRateLimit` **fails closed** (`return { allowed: false, retryAfterSeconds: 60 }`), preventing silent fallback to a fresh memory budget per isolate.
  - Implemented **Dual-Budget Rate Limiting** on `/api/public/otp`:
    1. **Mailbox budget** (`mail:${email}`, 10 req/min): protects target mailbox from distributed brute force attacks across rotating IPs.
    2. **Client IP budget** (`ip:${clientIp}`, 30 req/min): protects against wide credential stuffing / address enumeration across many mailboxes.
  - In-memory fallback (`memoryRateLimits`) is now strictly bounded (`MAX_MEMORY_RATE_LIMIT_ENTRIES = 10000`) with proactive cleanup of expired entries (`cleanupMemoryRateLimits`) and LRU/FIFO eviction on overflow.
  - Vitest unit tests added covering DO outage fail-closed, multi-IP distributed attack on single mailbox, single-IP scanning across multiple mailboxes, and memory cleanup.

### Finding 4: Removed Insecure `Math.random` Fallback & Safe PIN Provisioning (P2)
- **`packages/backend/src/shared/pin.ts`**:
  - Removed `Math.random()` fallback from `generateSecurePin()`. Throws `Error("CSPRNG_UNAVAILABLE: ...")` if CSPRNG is unavailable.
- **`packages/backend/src/modules/email-addresses/service.ts`**:
  - Integrated `generateSecurePin()` into address creation workflow when `generatePin: true` or `meta.pin = "auto"` is requested.
  - Validates explicitly provided PINs: rejects malformed or weak PINs (< 4 characters or non-string) with HTTP 400.
  - Unit tests added in `email-addresses-service.test.ts` and `public-otp-router.test.ts`.

---

## 2. Test Execution & Verification

| Test Suite | Command | Result |
| :--- | :--- | :--- |
| Backend Unit Tests | `pnpm -C packages/backend test:unit` | **47/47 files passed (346/346 tests PASS)**, exit code 0 |
| Backend Integration | `pnpm -C packages/backend test:integration` | **3/3 files passed (11/11 tests PASS)**, exit code 0 |
| Frontend Unit Tests | `pnpm -C packages/frontend test:unit` | **13/13 files passed (46/46 tests PASS)**, exit code 0 |
| Extension Unit Tests | `pnpm -C packages/extension test:unit` | **3/3 files passed (8/8 tests PASS)**, exit code 0 |
| Lite-Router Tests | `pnpm --filter @spinupmail/lite-router test` | **2/2 files passed (18/18 tests PASS)**, exit code 0 |
| Python Regression | `python -m unittest discover -s scripts/tests -v` | **71/71 tests PASS**, exit code 0 |
| Offline Probe | `python audit/reproduce_local_findings.py` | **4/4 findings resolved**, exit code 0 |
| Frontend Typecheck | `pnpm -C packages/frontend typecheck` | **0 errors (PASS)**, exit code 0 |
| SDK Typecheck | `pnpm -C packages/sdk typecheck` | **0 errors (PASS)**, exit code 0 |
| Backend Typecheck | `pnpm -C packages/backend typecheck` | **0 errors (PASS)**, exit code 0 |
