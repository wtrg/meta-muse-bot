# Independent review R08 — d7e5dbe6d70cb6e29767b232897817fe1eae9037

Origin SHA verified. R06 original probe now returns 409/409 and TXT exception_propagated=true. R07 original probes preserve the original CSV on backup failure; restore failure preserves a recoverable backup and pending gates block mixed-generation downloads. These exact cases are verified resolved.

Codex independently ran Python unittest discovery with all seven runtime path environment variables redirected to a TemporaryDirectory before importing tests: 86/86 passed, exit 0. This is offline fixture verification, not live E2E. Existing suite write guard wraps only atomic writers and permits the entire system temp directory; do not characterize that guard as covering every filesystem write or only the per-test root.

## P1: backup cleanup precedes the final publication step

In save_session_csv_and_excel, backups are deleted before removing pending_marker. For an existing generation A, attempt generation B and inject PermissionError only on os.remove(.pending). The writer then enters rollback, but its backups no longer exist. Both endpoints return 409; original CSV bytes are lost and there are zero recoverable backups. T39 currently starts with no old generation and therefore does not verify preservation in this case.

Independent AST/tempfile output: `{"case":"pending_clear_existing_generation","writer_success":false,"statuses":{"csv":409,"excel":409},"old_csv_preserved":false,"recoverable_backup_count":0}`.

Acceptance: define an explicit commit point. Do not discard recovery backups before every fallible pre-commit step has succeeded. On an existing-generation pending-clear error, preserve original bytes or recoverable backup and consistently report failure. After commitment, cleanup failures must not trigger rollback using backups already deleted. Add that exact existing-generation regression fixture.

## P2: failure marker removal is swallowed, writer reports false readiness

When a .failed marker remains from an earlier attempt, inject PermissionError on os.remove(.failed) during an otherwise successful new export. The exception is ignored, pending_marker is removed, and the writer returns normally. Both download endpoints still reject with 409 due to .failed, while its caller can emit export success.

Independent output: `{"case":"failed_clear_writer_success","writer_success":true,"statuses":{"csv":409,"excel":409}}`.

Acceptance: failure marker removal must be a checked readiness step with a truthful return/exception contract. A successful writer result must mean both download endpoints can serve the committed generation. Include an existing failed marker, failed unlink, then recovery success. Do not simply remove the endpoint gate to satisfy readiness.

The new pending marker is written with plain open/json.dump without flush/fsync or a durable manifest. Scope any durability claims to evidence actually obtained; process restart tests do not prove power-loss durability.

Selected source and these independent observations were sent ONCE to ChatGPT web Tìm hiểu Muse AI for review of this exact SHA (packet audit/CHATGPT_REVIEW_PACKET_d7e5dbe.md). UI showed Pasted text(4).txt and ChatGPT is responding. No complete response has yet been read; do not attribute approval. No repeat submission for this same snapshot.
