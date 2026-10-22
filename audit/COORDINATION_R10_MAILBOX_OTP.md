# R10 — parallel mailbox/OTP correctness fixes

Base: b330f7529b27923f075db9b09ff7656c2bf4ea98. Source/fixture evidence: MAILBOX_OTP_REVIEW_b330f75.md. User requested parallel implementation to accelerate work. This is defensive mailbox/OTP correctness and single-mailbox management, not bot provisioning, signup throughput, Facebook email rotation, or age/region bypass.

## Ownership while sharing one checkout

- Antigravity chat Frontend Email And OTP Completion, cascade dc32557b-8273-4a50-8f43-d5796d18b0a4, owns frontend only: public-otp-page.tsx, authenticated create-address form and minimal associated API/types/schema/hooks and frontend tests. User explicitly corrected the destination to Antigravity on 2026-10-22; Codex chat 01a16327-9c4a-7a01-b2f3-26569b313454 is stopped, with no active tool. Its existing eight frontend source/test changes were preserved and handed off via FRONTEND_IMPLEMENTATION_R10_HANDOFF.md, not reset or redone.
- Antigravity cascade f255b251-14c8-43b0-af0e-b9c0788ab043 owns backend public-otp/router.ts and its backend tests only.
- Neither stages, commits, pushes, resets, restarts services, or edits the other side's files during concurrent work. Root reviews the combined diff before asking Antigravity to commit selected files.

## Acceptance

1. UI polling must fit existing backend budgets of 10/mailbox/minute and 30/IP/minute. No rate-limit increase. Avoid overlapping requests and honor Retry-After/backoff. Fake clock over two minutes must not cause normal first-party polling to rate-limit itself.
2. OTP display belongs to the current mailbox, PIN and request. Credential changes, network errors, unmount and deferred out-of-order A/B responses must not display A's OTP as B's. Clear or explicitly mark stale results; reject obsolete responses.
3. A signed-in user can explicitly request a PIN for one owned mailbox via the existing authenticated generatePin capability. Show/copy the one-time create response only. No PIN in later GET DTOs, URL, logs or localStorage. No anonymous/bulk path or connection to bot provisioning.
4. Backend provider sync failure must be distinct from a successful empty inbox. Minimum agreed shape: HTTP 502/503 with ok:false and generic existing-format error code/message; no raw provider details or credentials. Cached rows must not be represented as fresh after sync failure. Keep no-store, PIN validation, organization scope and existing budgets. Tests cover valid PIN + provider reject with/without cache, successful empty mailbox, and denied requests never calling provider.

Tests use synthetic fixtures only, sequential maxWorkers=1, no provider requests or runtime user data. Typecheck and targeted regressions must pass before handoff. Source/fixture success is not live E2E.

## Review state

Codex independently passed 89 Python tests and R08 export probes on b330f75. R08-01/02 on old d7e5dbe were confirmed by ChatGPT and then fixed by b330f75. R09 follow-up for b330f75 completed in the ChatGPT web UI with “This response couldn’t load”; no readable new verdict. Do not retry the same snapshot repeatedly or call that approval. Do not equate this rendering error with exhausted quota. R09 user message and packet CHATGPT_REVIEW_PACKET_b330f75.md remain evidence of submission only.
