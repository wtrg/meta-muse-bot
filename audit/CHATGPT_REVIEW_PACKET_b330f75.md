Review follow-up R09, exact new SHA b330f7529b27923f075db9b09ff7656c2bf4ea98 on review/audit-fix-2026-10-22. This is NEW SOURCE after your R08 review of d7e5dbe. Review only export persistence; no live E2E or merge approval for the whole project. Keep response under 400 words, actionable findings file:line; distinguish current blocking bugs from stated availability/durability limits or conditional concurrency.
Codex independently verified origin SHA; Python 89/89 pass with all 7 runtime environment paths redirected into TemporaryDirectory BEFORE import, exit0. AST/tempfile R08 probe verifies: pending-clear failure on existing A returns writer failure and409/409 while both A files preserved; failed-marker unlink failure returns writer failure and409/409; subsequent retry returns success/200/200; post-commit backup cleanup failure leaves committed B served200/200.
Patch moves backup deletion AFTER an explicit commit point, and checks failure marker removal before un-gating. Downloads still intentionally reject a failed attempt until a successful retry; this availability contract was accepted in the R06 criteria (409 for both formats), so R08-03 is a documented limitation rather than proof of data loss. R08-04 concurrency was conditional, not demonstrated: production writer is synchronous inside a single async worker and start is protected with _job_lock; do not assume multi-process writers without evidence. No power-loss durability claim; flush is not fsync. Based on the NEW diff below and your preceding full selected source, are R08-01/R08-02 resolved? Any remaining demonstrated blocker in commit/rollback flow? If prior context insufficient, state precisely what source is missing. Do not restate old source findings as current.

```diff
diff --git a/scripts/bot_server.py b/scripts/bot_server.py
index aaf6d69..06531ba 100644
--- a/scripts/bot_server.py
+++ b/scripts/bot_server.py
@@ -638,7 +638,7 @@ def save_session_csv_and_excel(session_accounts: List[Dict[str, Any]], session_i
         if os.path.exists(target_abs):
             existed_targets.add(target_abs)
 
-    # Establish durable in-progress gate BEFORE mutating any published data
+    # Establish in-progress publication gate BEFORE mutating any published data
     try:
         with open(pending_marker, "w", encoding="utf-8") as pm:
             json.dump({
@@ -646,6 +646,7 @@ def save_session_csv_and_excel(session_accounts: List[Dict[str, Any]], session_i
                 "state": "pending",
                 "started_at": time.strftime("%Y-%m-%d %H:%M:%S")
             }, pm, ensure_ascii=False)
+            pm.flush()
     except Exception as gate_err:
         raise OSError(f"Cannot establish publication gate for session '{session_id}': {gate_err}") from gate_err
 
@@ -703,27 +704,21 @@ def save_session_csv_and_excel(session_accounts: List[Dict[str, Any]], session_i
         atomic_write_excel(root_latest_excel, wb)
         written_files.append(os.path.abspath(root_latest_excel))
 
-        # Xóa backup sau khi toàn bộ batch hoàn tất thành công
-        for bak in list(existing_backups.values()):
-            if os.path.exists(bak):
-                try:
-                    os.remove(bak)
-                except OSError:
-                    pass
-
-        # Xóa failure marker nếu có từ lần chạy lỗi trước
+        # 4. Checked readiness step: xóa failure marker nếu có từ lần chạy lỗi trước
         if os.path.exists(failure_marker):
             try:
                 os.remove(failure_marker)
-            except OSError:
-                pass
+            except Exception as clear_fail_err:
+                raise OSError(f"Could not clear failure marker for session '{session_id}': {clear_fail_err}") from clear_fail_err
 
-        # Xóa pending marker (durable gate); writer must agree with download readiness
+        # 5. Xóa pending marker; un-gate phiên để download endpoints sẵn sàng phục vụ
         if os.path.exists(pending_marker):
             try:
                 os.remove(pending_marker)
             except Exception as clear_err:
-                raise OSError(f"Could not clear pending marker: {clear_err}") from clear_err
+                raise OSError(f"Could not clear pending marker for session '{session_id}': {clear_err}") from clear_err
+
+        # COMMIT POINT: Toàn bộ pre-commit steps thành công, phiên đã un-gate và sẵn sàng download!
     except Exception as exc:
         cleanup_errors = []
         failed_restore_backups = set()
@@ -737,6 +732,7 @@ def save_session_csv_and_excel(session_accounts: List[Dict[str, Any]], session_i
                     "failed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                     "error": str(exc)
                 }, fm, ensure_ascii=False)
+                fm.flush()
         except Exception as mark_err:
             cleanup_errors.append(f"Failed to write failure marker: {mark_err}")
 
@@ -786,6 +782,17 @@ def save_session_csv_and_excel(session_accounts: List[Dict[str, Any]], session_i
 
         raise
 
+    # POST-COMMIT CLEANUP:
+    # Điểm cam kết (commit point) đã qua thành công. Các file tải về đã sẵn sàng phục vụ.
+    # Dọn dẹp các bản sao lưu (.bak) tạm thời. Lỗi dọn dẹp ở giai đoạn này là non-fatal
+    # và TUYỆT ĐỐI KHÔNG kích hoạt rollback vì dữ liệu thế hệ mới đã được publish chính thức!
+    for bak in list(existing_backups.values()):
+        if os.path.exists(bak):
+            try:
+                os.remove(bak)
+            except OSError:
+                pass
+
 def redact_sensitive(text: str) -> str:
     if not isinstance(text, str):
         return text

```
