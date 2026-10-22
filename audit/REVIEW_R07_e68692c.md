# Independent review R07 — e68692c58396655524db524f040075b70baaec48

CHANGES REQUIRED. Origin SHA verified. Original R06 probe now reports both formats 409 on session Excel failure and TXT exception_propagated=true (exit 0). This verifies those exact cases only.

New probe: `python audit/probe_r07_exports.py`, AST-extracted functions, synthetic content and TemporaryDirectory only, no import of bot_server and no live requests. Exit 0 with the following reproduced failures:

## P1: backup/rollback destroys the last good generation

scripts/bot_server.py:585-595 ignores backup copy errors and proceeds with replacements. Inject shutil.copy2 PermissionError, then session XLSX failure: the pre-existing good CSV is deleted, no backup remains. Both endpoints return 409, but the last good CSV is lost.

scripts/bot_server.py:683-699: if restoring a .bak fails, that same backup is subsequently deleted by the cleanup loop. Probe restore_failure leaves generation B CSV, generation A Excel, zero backups. An error entry in the marker is not preservation of the original data.

Acceptance: abort before mutation when a required backup cannot be made; track whether each target existed independently of backup success. Never delete a backup whose restoration failed. Keep recovery information and redact diagnostics. Add assertions for original bytes or an intact recoverable backup, not merely cleanup_errors length.

## P1: marker write failure reopens mixed-generation downloads

scripts/bot_server.py:666-677 creates the failure marker only after publication has begun and ignores marker-write failure. Inject session Excel failure, PermissionError for writing .failed, and PermissionError restoring .bak. Probe result: CSV 200, Excel 200, CSV contains generation B while Excel still contains generation A; no backup remains. This contradicts the fail-closed download contract.

Acceptance: establish an in-progress/unavailable state durably before mutating published targets, or publish immutable generation files through a validated committed manifest. If the gate/manifest cannot be persisted, do not modify published data. Download readers must reject uncommitted/inconsistent generations, including after process restart. Test marker creation failure, restore failure, and marker-clear failure; a successful writer result must agree with download readiness. Do not claim full transactional atomicity from a best-effort error marker.

Workbook initialization/import is also outside the write try block (597-624), so exceptions there leave backups and no new failure marker. Include the pre-publication dependency/build failure boundary in the chosen contract.

## P1: new tests write into real repository runtime data

scripts/tests/test_muse_regression_v5.py T31/T32 patch only EXPORTS_DIR, while save_session_csv_and_excel also writes root_latest_csv/root_latest_excel derived from real bot.__file__. Successful synthetic exports therefore overwrite repository-root muse_session_latest.csv/.xlsx. T34:891-893 calls real save_accounts while only save_accounts_txt is mocked to fail: atomic_write_text first overwrites real bot.ACCOUNTS_FILE (scripts/muse_accounts.json). Class setup creates a TestClient and does not globally redirect these paths or restore BotState.

Codex did NOT rerun the 81-test suite on this SHA because of these side effects. The previous 77/50 independent results are for 48178b4, not this commit. The agent's reported 81/81 is not independent proof and does not establish that user data was preserved. No actual user-data loss is claimed without before/after evidence.

Acceptance: isolate every runtime path (accounts JSON, scripts/root TXT, all aliases, exports, screenshots, tunnel config) and BotState in a common temporary fixture. Add a write guard that fails if tests attempt to write outside the fixture. T34 caller test currently copies the implementation into the test rather than invoking the actual caller; replace with a fixture through the real caller or a factored persistence boundary used by that caller. Do not repair repository runtime files using invented contents; preserve originals and report uncertainty.

Do not run another broad suite until test isolation is corrected. Keep source changes confined to persistence/export/test safety. Do not restart services, trigger signup/browser/VPN/FB, merge, deploy, or force-push. Preserve this audit and its probe. Push selected fixes only after relevant isolated acceptance tests pass. ChatGPT source review should target the next fixed SHA rather than repeat a known failing snapshot.
