# R11 independent verification

Base: ad21a4d0f6f4600c6213b1c5bdf1f0dbe1dd0489.

Codex read the three-file frontend diff and independently ran the three targeted component suites with maxWorkers=1: 27/27 tests passed, exit 0, duration 65.30s (22 October 2026, 19:43 Asia/Saigon). git diff --check exited 0. Agent reports API/typecheck/lint success; these were not all repeated by Codex in this round.

R11-02: confirmed in prior source. The form now blocks another submission while a one-time PIN remains visible, retaining it until explicit acknowledgement/dismissal. The regression checks no second mutation, PIN preservation, clipboard failure and subsequent submission after dismissal. No backend changes.

R11-01: not reproduced on existing production code. Email/PIN input handlers already clear loading/error and abort stale requests; URL navigation resets state during render. Added deferred email-change/navigation and 429 cooldown tests pass without changing public-otp-page.tsx. The new pending-input test explicitly changes email; PIN handler equivalence is source evidence, not an additional pending-PIN test.

Only create-address-form.tsx and its test plus public-otp-page.test.tsx changed. This is synthetic/component evidence, not live provider, browser or signup E2E acceptance. Bot SpinupMail provisioning remains disabled. No claim of complete original goal or fresh ChatGPT approval.
