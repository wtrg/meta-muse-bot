Frontend mailbox/OTP implementation handoff
Base HEAD: b330f7529b27923f075db9b09ff7656c2bf4ea98 (unchanged; working tree changes only)

Owned files changed:
packages/frontend/src/pages/public-otp-page.tsx
packages/frontend/src/pages/tests/public-otp-page.test.tsx (new/untracked; include explicitly when staging)
packages/frontend/src/features/addresses/components/create-address-form.tsx
packages/frontend/src/features/addresses/components/tests/create-address-form.test.tsx
packages/frontend/src/features/addresses/hooks/use-addresses.ts
packages/frontend/src/features/addresses/hooks/tests/use-addresses.test.tsx
packages/frontend/src/lib/api.ts
packages/frontend/src/lib/tests/api.test.ts

Behavior:
- Poll every 8 seconds at most using one shared manual/automatic cooldown and one in-flight request. Rate limits backend unchanged. 429 accepts Retry-After seconds/date and defaults to 60s if absent/invalid. Network/API errors back off exponentially to 60s. Credential changes preserve cooldown.
- Mailbox/PIN changes abort prior request and clear display; sequence + current credential key rejects late responses, including mocks ignoring abort. Unmount aborts; network failures clear result and show visible error. URL navigation resets URL-derived state before committing stale display.
- Signed-in single mailbox form offers optional Generate a mailbox PIN (default false); create request generatePin and response pin typed separately from EmailAddress GET DTO. PIN visible only in transient post-create panel with copy/dismiss, cleared on next valid submission or unmount. Mutation reset + gcTime 0 discard cached creation secret. No localStorage/URL/log writes for generated PIN and no PIN added to GET types/cache.

Acceptance evidence (synthetic only):
9 OTP tests cover two minutes under budgets (16 requests, no self429), header PIN/no-store, Retry-After seconds/date, manual cooldown, non-overlap, deferred A/B and changed PIN responses, clear on credential change, network failure/backoff, unmount.
8 form tests include opt-in generation, top-level secret display/copy/dismiss/remount absence, missing PIN message, metadata PIN rejection plus existing form behavior.
4 hook tests include mutation cache removal after reset.
11 API tests include authenticated organization-scoped single POST, generatePin body, no secret URL.

Commands (cwd packages/frontend unless otherwise noted):
1) pnpm exec vitest run --config vitest.component.config.ts src/pages/tests/public-otp-page.test.tsx src/features/addresses/components/tests/create-address-form.test.tsx src/features/addresses/hooks/tests/use-addresses.test.tsx --maxWorkers=1
Initial exit1: 17passed/3failed (two new test harness expectations, one 5s form timeout). Corrected fake-clock act flushing and spinner name matching, no timeout increase. Final rerun after lifecycle/lint fixes: exit0; 3files/21tests PASS; duration20.91s.
2) pnpm exec vitest run --config vitest.component.config.ts src/pages/tests/public-otp-page.test.tsx --maxWorkers=1
Intermediate exit0;9PASS.
3) pnpm exec vitest run --config vitest.component.config.ts src/features/addresses/components/tests/create-address-form.test.tsx src/features/addresses/hooks/tests/use-addresses.test.tsx --maxWorkers=1
Intermediate exit0;11PASS (before adding the cache-removal test).
4) pnpm exec vitest run --config vitest.unit.config.ts src/lib/tests/api.test.ts --maxWorkers=1
Exit0;11PASS.
5) pnpm exec tsc -b --noEmit
Exit0, no diagnostics (standalone before final lifecycle refactor; also repeated together with #6 after final source change with no diagnostics).
6) pnpm exec tsc -p tsconfig.test.json --noEmit
Exit0, no diagnostics. Last shell ran #5 followed by #6; combined exit0, both silent.
7) From repo root:
pnpm exec eslint packages/frontend/src/pages/public-otp-page.tsx packages/frontend/src/pages/tests/public-otp-page.test.tsx packages/frontend/src/features/addresses/components/create-address-form.tsx packages/frontend/src/features/addresses/components/tests/create-address-form.test.tsx packages/frontend/src/features/addresses/hooks/use-addresses.ts packages/frontend/src/features/addresses/hooks/tests/use-addresses.test.tsx packages/frontend/src/lib/api.ts packages/frontend/src/lib/tests/api.test.ts
Final exit0, no warnings/errors. Earlier lint before lifecycle correction returned exit1 (refs during render/state in effect/no-empty); fixed without suppressions.
8) From repo root: git diff --check -- packages/frontend
Exit0; only Git CRLF advisory messages.
Prettier run only on owned frontend files, exit0.

No edits to backend, bot_server, root audit files. Concurrent Antigravity backend provider error changes and coordinator audit files preserved. No stage, commit, push, server/start/restart, browser, signup, VPN, live provider, real credential/account access. No full suite/build/deployed session/provider proof. Same-IP traffic from other tabs/clients can still trigger backend429; this client honors backoff rather than changing limits. Existing backend legacy query PIN compatibility remains outside scope.
