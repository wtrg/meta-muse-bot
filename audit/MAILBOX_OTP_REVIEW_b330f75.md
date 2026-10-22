# Mailbox / OTP independent read-only audit

Reviewed HEAD: b330f7529b27923f075db9b09ff7656c2bf4ea98
Start: git status --short empty. End: same HEAD; only ?? audit/CHATGPT_REVIEW_PACKET_b330f75.md appeared from concurrent work. This audit did not edit source, start services, read env/profile/credentials/runtime account data, call real providers, or change Git state.

No applicable AGENTS.md found at workspace or ancestor paths checked.

## Commands and results

Backend cwd: C:/Users/Lenovo/Downloads/spinupmail-main/spinupmail-main/packages/backend

1. pnpm exec vitest run --config vitest.unit.config.ts tests/unit/public-otp-router.test.ts tests/unit/email-addresses-router.test.ts tests/unit/email-addresses-service.test.ts tests/unit/email-addresses-dto.test.ts tests/unit/email-addresses-schemas.test.ts tests/unit/email-addresses-repo.test.ts tests/unit/auth-middleware.test.ts --maxWorkers=1
   Exit 0; 7 files, 76 tests passed.
2. pnpm exec vitest run --config vitest.integration.config.ts tests/integration/app-auth.integration.test.ts tests/integration/require-organization-scope.integration.test.ts --maxWorkers=1
   Exit 0; 2 files, 10 tests passed. Auth factory is mocked; no live auth/storage proof.
3. pnpm exec vitest run --config C:/Users/Lenovo/AppData/Local/Temp/spinupmail-mailbox-audit-hwQGwg/config.mjs -t 'Independent audit' --maxWorkers=1
   Initial exit 1, no tests: temporary harness alias for hono incorrectly matched hono/cors. Corrected ONLY temporary config to use resolve.dedupe. Same command rerun: exit 0; 4 passed, 24 existing cases skipped by filter.
   a. createApp GET and POST /api/email-addresses plus GET /api/email-addresses/box-a all return 401 to anonymous before getDb.
   b. Same exact routes return 403 for verified session whose org lookup returns null, before getDb.
   c. Valid mailbox PIN plus mocked provider outage returns 200, ok:true, hasEmails:false (characterization of bug, not acceptance).
   d. 20 valid polls at 3-second intervals produce 10 HTTP 200 and 10 HTTP 429 in one minute (characterization of bug, not acceptance).

Frontend cwd: C:/Users/Lenovo/Downloads/spinupmail-main/spinupmail-main/packages/frontend

4. pnpm exec vitest run --config vitest.component.config.ts src/features/addresses/components/tests/create-address-form.test.tsx src/features/addresses/components/tests/address-list.test.tsx src/features/addresses/components/tests/edit-address-sheet.test.tsx src/features/addresses/hooks/tests/use-addresses.test.tsx src/pages/tests/address-management-page.test.tsx --maxWorkers=1
   Exit 0; 5 files, 29 tests passed; reported duration 101.18s. Final output arrived when cancellation/poll was attempted; tool returned completed exit 0. No test failure/cancelled claim.
5. pnpm exec vitest run --config vitest.unit.config.ts src/lib/tests/api.test.ts --maxWorkers=1
   Exit 0; 1 file, 10 tests passed.

All suites run sequentially with maxWorkers=1. No coverage, full-suite, server, deploy, signup, browser or provider live test.

## Source / fixture proof and limits

- POST /api/email-addresses: authenticated verified session + organization membership; acceptedRiskNotice true, configured allowed domain/localPart, organization quota; 200 on successful insert, no-store. generatePin true (top-level), meta.generatePin true or meta.pin auto generates secure PIN. Explicit meta.pin >=4 characters accepted. Pin returned top-level only at creation; DTO strips pin/liveToken/livePassword/password from meta. GET list/detail do not re-expose PIN; they use private,max-age=15. Existing generation tests and mocked router tests prove pieces, not a single POST-to-GET-to-OTP real storage flow.
- List/detail queries scope organization; authenticated UI uses /api/domains and /api/email-addresses list/detail/POST/PATCH/DELETE through apiFetch(credentials include, X-Org-Id, no-store). Component fixtures verify existing management behavior. create errors use toast.promise error; domain/list/detail errors rendered. PublicOtpPage has no dedicated browser test in this audit.
- Public OTP is intentionally PIN capability access independent of session. Missing PIN 400; wrong PIN 401; different mailbox PIN 401; unknown mailbox 404; denied paths don't call provider. Header X-Mailbox-Pin and POST JSON supported; all OTP responses set no-store. Query PIN still accepted and warning header does not prevent upstream URL logging. Initial page history cleanup cannot undo first request logs/referrer exposure.
- Removed recent-otps, bulk-create, auto-login return 404. Normal authenticated mailbox management remains, while scripts/bot_server.py:862 explicitly rejects SpinupMail as bot provisioning provider. No restoration/integration attempted.

## Findings and acceptance tests

1. P2: OTP polling exceeds its own budget. packages/frontend/src/pages/public-otp-page.tsx:131 uses 3000ms vs packages/backend/src/modules/public-otp/router.ts:239 permits 10/minute and counts successful requests. Probe above confirms 10 successes then 10 rate-limit errors per minute. Acceptance: simulate 2 minutes with fake clock and normal UI polling; no self-induced 429; genuine 429 respects Retry-After and pauses/backoffs.
2. P2: Provider errors represented as successful empty/stale inbox. packages/backend/src/modules/public-otp/router.ts:334 catches live sync errors then reaches 200 empty response at :357 (or existing cached rows). Probe above confirms. Acceptance: fetchLiveMailMessages rejection yields explicit provider error/degraded status distinct from successful empty mailbox; cached message status discloses freshness; UI shows corresponding state.
3. P2: Signed-in single-address form cannot provision usable public OTP PIN. packages/frontend/src/features/addresses/components/create-address-form.tsx:399 sends neither generatePin nor meta.pin; :421 only offers Copy address. api.ts:623 request/response types omit generatePin/pin. Backend default intentionally permits PIN-less inbox. Repro source + existing submission fixture: create via /addresses then visit /otp; no PIN issued, so public access fails closed. Authenticated inbox still works. Acceptance: offer explicit PIN provisioning for an owned mailbox, show/copy returned PIN once, no PIN on later list/detail. Do not add anonymous or bulk provisioning.
4. P2: OTP page retains old mailbox data on network failure / mailbox change. packages/frontend/src/pages/public-otp-page.tsx:107 catch only toasts, while :249 continues rendering previous data; email/PIN input changes do not clear data, and responses aren't bound to current credentials. Source proof only. Repro: load A success, change to B, cause fetch reject (or resolve delayed A after successful B); A's OTP can remain alongside B input. Acceptance: deferred-fetch component test covers A/B reordering and failure; clear or visibly mark stale results, accept only current mailbox/request response.

No live delivery, Cloudflare D1/DO deployment, actual session/org integration, browser history/referrer behavior or real provider availability verified. Unit/mock PASS does not close the findings above or imply whole-tool completion.
