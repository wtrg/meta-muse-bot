Independent static review request R08. Exact target SHA d7e5dbe6d70cb6e29767b232897817fe1eae9037, branch review/audit-fix-2026-10-22. Review only selected source below; no live E2E claim. Codex independently passed 86 Python fixture tests with all runtime env paths redirected before import and R06/R07 probes now pass their exact original cases. Do not re-review old snapshot bec3f31. Output CHANGES REQUIRED or no findings, max 5 actionable findings with file:line, trigger, consequence, smallest sound fix and acceptance test; mark unknowns. Please keep response under 650 words. No network/signup/VPN/FB work. Source contains no real user credentials or runtime data.

Two NEW offline AST/tempfile reproductions on this SHA:
1. Generation A exists. Generation B writes all formats, then os.remove(.pending) raises PermissionError. Writer raises and both endpoints409, but old_csv_preserved=false and recoverable_backup_count=0. Backups were deleted before clearing the gate, and rollback then tries nonexistent backups.
2. An old .failed marker exists. On otherwise successful Generation B, os.remove(.failed) raises PermissionError. Writer returns normally (success), both download endpoints409. This violates writer/download readiness contract.
Please independently validate these from source, and identify any other important defect in commit/rollback ordering. Prefer a coherent publication boundary rather than another narrow exception patch. Known limitation: gate creation currently uses plain open/write without fsync; distinguish process restart from OS/power crash claims.


## scripts/bot_server.py:560-600
```python
560:         redact_fn = globals().get("redact_sensitive")
561:         safe_err = redact_fn(str(e)) if redact_fn else str(e)
562:         add_log(f"Đăng nhập chat thành công nhưng lưu file tài khoản thất bại: {safe_err}", "error", 100)
563:         raise
564: 
565: def save_session_csv_and_excel(session_accounts: List[Dict[str, Any]], session_id: str):
566:     if not session_id:
567:         session_id = time.strftime("%Y%m%d_%H%M%S")
568:     tunnel_url = get_effective_portal_url()
569:     
570:     headers = ["STT", "Email", "Mã PIN", "Trang Web Lấy OTP Đăng Nhập"]
571:     rows = []
572:     for idx, acc in enumerate(session_accounts, 1):
573:         email = acc.get("email", "")
574:         pin = acc.get("pin", "") or ""
575:         otp_link = f"{tunnel_url}/otp?email={urllib.parse.quote(email)}"
576:         rows.append([idx, email, pin, otp_link])
577:         
578:     csv_filename = f"muse_session_{session_id}.csv"
579:     excel_filename = f"muse_session_{session_id}.xlsx"
580:     
581:     os.makedirs(EXPORTS_DIR, exist_ok=True)
582:     session_csv_path = os.path.join(EXPORTS_DIR, csv_filename)
583:     session_excel_path = os.path.join(EXPORTS_DIR, excel_filename)
584:     
585:     latest_csv_path = os.path.join(EXPORTS_DIR, "muse_session_latest.csv")
586:     latest_excel_path = os.path.join(EXPORTS_DIR, "muse_session_latest.xlsx")
587:     
588:     root_latest_csv = globals().get("ROOT_LATEST_CSV_PATH", os.path.join(os.path.dirname(os.path.dirname(__file__)), "muse_session_latest.csv"))
589:     root_latest_excel = globals().get("ROOT_LATEST_EXCEL_PATH", os.path.join(os.path.dirname(os.path.dirname(__file__)), "muse_session_latest.xlsx"))
590:     
591:     pending_marker = os.path.join(EXPORTS_DIR, f"muse_session_{session_id}.pending")
592:     failure_marker = os.path.join(EXPORTS_DIR, f"muse_session_{session_id}.failed")
593:     targets = [
594:         session_csv_path,
595:         session_excel_path,
596:         latest_csv_path,
597:         root_latest_csv,
598:         latest_excel_path,
599:         root_latest_excel
600:     ]
```

## scripts/bot_server.py:632-795
```python
632:     ws.column_dimensions['D'].width = 85
633: 
634:     # Identify existing published targets before publication begins
635:     existed_targets = set()
636:     for target in targets:
637:         target_abs = os.path.abspath(target)
638:         if os.path.exists(target_abs):
639:             existed_targets.add(target_abs)
640: 
641:     # Establish durable in-progress gate BEFORE mutating any published data
642:     try:
643:         with open(pending_marker, "w", encoding="utf-8") as pm:
644:             json.dump({
645:                 "session_id": session_id,
646:                 "state": "pending",
647:                 "started_at": time.strftime("%Y-%m-%d %H:%M:%S")
648:             }, pm, ensure_ascii=False)
649:     except Exception as gate_err:
650:         raise OSError(f"Cannot establish publication gate for session '{session_id}': {gate_err}") from gate_err
651: 
652:     # Mandatory backup of all pre-existing targets; if ANY fails, abort before mutation
653:     import shutil
654:     batch_token = f"{session_id}_{os.getpid()}_{int(time.time() * 1000)}"
655:     existing_backups = {}
656:     for target_abs in existed_targets:
657:         target_dir = os.path.dirname(target_abs)
658:         os.makedirs(target_dir, exist_ok=True)
659:         bak_path = target_abs + f".bak_{batch_token}"
660:         try:
661:             shutil.copy2(target_abs, bak_path)
662:             existing_backups[target_abs] = bak_path
663:         except Exception as bak_exc:
664:             # Clean up partial backups created in this batch
665:             for created_bak in list(existing_backups.values()):
666:                 if os.path.exists(created_bak):
667:                     try:
668:                         os.remove(created_bak)
669:                     except OSError:
670:                         pass
671:             # Mark failure so endpoints reject incomplete attempts
672:             try:
673:                 with open(failure_marker, "w", encoding="utf-8") as fm:
674:                     json.dump({
675:                         "session_id": session_id,
676:                         "failed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
677:                         "error": f"Required backup failed: {bak_exc}"
678:                     }, fm, ensure_ascii=False)
679:             except Exception:
680:                 pass
681:             raise OSError(f"Required backup failed for {target_abs}, aborting export before mutation: {bak_exc}") from bak_exc
682: 
683:     written_files = []
684:     try:
685:         # 1. Ghi File CSV của phiên
686:         atomic_write_csv(session_csv_path, headers, rows)
687:         written_files.append(os.path.abspath(session_csv_path))
688: 
689:         # 2. Ghi File Excel của phiên
690:         atomic_write_excel(session_excel_path, wb)
691:         written_files.append(os.path.abspath(session_excel_path))
692: 
693:         # 3. Cập nhật latest files sau khi các file phiên đã hoàn tất
694:         atomic_write_csv(latest_csv_path, headers, rows)
695:         written_files.append(os.path.abspath(latest_csv_path))
696: 
697:         atomic_write_csv(root_latest_csv, headers, rows)
698:         written_files.append(os.path.abspath(root_latest_csv))
699: 
700:         atomic_write_excel(latest_excel_path, wb)
701:         written_files.append(os.path.abspath(latest_excel_path))
702: 
703:         atomic_write_excel(root_latest_excel, wb)
704:         written_files.append(os.path.abspath(root_latest_excel))
705: 
706:         # Xóa backup sau khi toàn bộ batch hoàn tất thành công
707:         for bak in list(existing_backups.values()):
708:             if os.path.exists(bak):
709:                 try:
710:                     os.remove(bak)
711:                 except OSError:
712:                     pass
713: 
714:         # Xóa failure marker nếu có từ lần chạy lỗi trước
715:         if os.path.exists(failure_marker):
716:             try:
717:                 os.remove(failure_marker)
718:             except OSError:
719:                 pass
720: 
721:         # Xóa pending marker (durable gate); writer must agree with download readiness
722:         if os.path.exists(pending_marker):
723:             try:
724:                 os.remove(pending_marker)
725:             except Exception as clear_err:
726:                 raise OSError(f"Could not clear pending marker: {clear_err}") from clear_err
727:     except Exception as exc:
728:         cleanup_errors = []
729:         failed_restore_backups = set()
730:         successful_restore_backups = set()
731: 
732:         # 1. Tạo failure marker để các download endpoints từ chối với status 409
733:         try:
734:             with open(failure_marker, "w", encoding="utf-8") as fm:
735:                 json.dump({
736:                     "session_id": session_id,
737:                     "failed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
738:                     "error": str(exc)
739:                 }, fm, ensure_ascii=False)
740:         except Exception as mark_err:
741:             cleanup_errors.append(f"Failed to write failure marker: {mark_err}")
742: 
743:         # 2. Khôi phục các file đã ghi về trạng thái ban đầu
744:         for p in reversed(written_files):
745:             if p in existing_backups:
746:                 bak = existing_backups[p]
747:                 try:
748:                     os.replace(bak, p)
749:                     successful_restore_backups.add(bak)
750:                 except Exception as restore_err:
751:                     cleanup_errors.append(f"Failed to restore {p} from backup: {restore_err}")
752:                     failed_restore_backups.add(bak)
753:             else:
754:                 try:
755:                     if os.path.exists(p):
756:                         os.remove(p)
757:                 except Exception as del_err:
758:                     cleanup_errors.append(f"Failed to remove newly written file {p}: {del_err}")
759: 
760:         # 3. Dọn dẹp backup: TUYỆT ĐỐI KHÔNG xóa các backup phục hồi thất bại
761:         for p, bak in list(existing_backups.items()):
762:             if bak in failed_restore_backups:
763:                 continue  # BẢO TỒN BACKUP PHỤC VỤ RECOVERY!
764:             if p in written_files and bak not in successful_restore_backups:
765:                 continue  # BẢO TỒN NẾU CHƯA RESTORE THÀNH CÔNG
766:             try:
767:                 if os.path.exists(bak):
768:                     os.remove(bak)
769:             except Exception as bak_err:
770:                 cleanup_errors.append(f"Failed to remove backup {bak}: {bak_err}")
771: 
772:         # 4. Ghi nhận lỗi cleanup và danh sách backup phục hồi vào failure marker nếu có
773:         if os.path.exists(failure_marker):
774:             try:
775:                 with open(failure_marker, "r+", encoding="utf-8") as fm:
776:                     data = json.load(fm)
777:                     if cleanup_errors:
778:                         data["cleanup_errors"] = cleanup_errors
779:                     if failed_restore_backups:
780:                         data["recovery_backups"] = list(failed_restore_backups)
781:                     fm.seek(0)
782:                     json.dump(data, fm, ensure_ascii=False)
783:                     fm.truncate()
784:             except Exception:
785:                 pass
786: 
787:         raise
788: 
789: def redact_sensitive(text: str) -> str:
790:     if not isinstance(text, str):
791:         return text
792:     # 1. Redact credentials in URLs: http://user:password@host -> http://user:***@host (including URL-encoded)
793:     text = re.sub(
794:         r'(?i)\b((?:https?|socks5?h?|ftp)://)([^:\s/@]+):([^@\s/]+)@',
795:         r'\1\2:***@',
```

## scripts/bot_server.py:2360-2425
```python
2360: async def export_session_csv(session_id: Optional[str] = None):
2361:     target_id = (session_id or state.session_id or "").strip()
2362:     if not target_id:
2363:         raise HTTPException(
2364:             status_code=404,
2365:             detail="Không có phiên làm việc hiện tại hoặc chưa chọn mã phiên."
2366:         )
2367:     if not SESSION_ID_REGEX.match(target_id) or target_id.lower() in RESERVED_SESSION_ALIASES:
2368:         raise HTTPException(
2369:             status_code=400,
2370:             detail=f"Mã phiên không hợp lệ hoặc thuộc từ khóa định danh phiên dành riêng ('{target_id}')."
2371:         )
2372:     failure_marker = os.path.join(EXPORTS_DIR, f"muse_session_{target_id}.failed")
2373:     pending_marker = os.path.join(EXPORTS_DIR, f"muse_session_{target_id}.pending")
2374:     if os.path.exists(failure_marker) or os.path.exists(pending_marker):
2375:         raise HTTPException(
2376:             status_code=409,
2377:             detail=f"Phiên '{target_id}' gặp lỗi hoặc đang trong quá trình xuất dữ liệu và không thể tải về artifact."
2378:         )
2379:     file_path = os.path.join(EXPORTS_DIR, f"muse_session_{target_id}.csv")
2380:     if not os.path.exists(file_path):
2381:         raise HTTPException(
2382:             status_code=404,
2383:             detail=f"Không tìm thấy file CSV cho phiên '{target_id}'."
2384:         )
2385:     return FileResponse(
2386:         file_path,
2387:         media_type="text/csv; charset=utf-8",
2388:         filename=f"muse_session_{target_id}.csv"
2389:     )
2390: 
2391: @app.get("/api/bot/export-session-excel")
2392: async def export_session_excel(session_id: Optional[str] = None):
2393:     target_id = (session_id or state.session_id or "").strip()
2394:     if not target_id:
2395:         raise HTTPException(
2396:             status_code=404,
2397:             detail="Không có phiên làm việc hiện tại hoặc chưa chọn mã phiên."
2398:         )
2399:     if not SESSION_ID_REGEX.match(target_id) or target_id.lower() in RESERVED_SESSION_ALIASES:
2400:         raise HTTPException(
2401:             status_code=400,
2402:             detail=f"Mã phiên không hợp lệ hoặc thuộc từ khóa định danh phiên dành riêng ('{target_id}')."
2403:         )
2404:     failure_marker = os.path.join(EXPORTS_DIR, f"muse_session_{target_id}.failed")
2405:     pending_marker = os.path.join(EXPORTS_DIR, f"muse_session_{target_id}.pending")
2406:     if os.path.exists(failure_marker) or os.path.exists(pending_marker):
2407:         raise HTTPException(
2408:             status_code=409,
2409:             detail=f"Phiên '{target_id}' gặp lỗi hoặc đang trong quá trình xuất dữ liệu và không thể tải về artifact."
2410:         )
2411:     file_path = os.path.join(EXPORTS_DIR, f"muse_session_{target_id}.xlsx")
2412:     if not os.path.exists(file_path):
2413:         raise HTTPException(
2414:             status_code=404,
2415:             detail=f"Không tìm thấy file Excel cho phiên '{target_id}'."
2416:         )
2417:     return FileResponse(
2418:         file_path,
2419:         media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
2420:         filename=f"muse_session_{target_id}.xlsx"
2421:     )
2422: 
2423: 
2424: if __name__ == "__main__":
2425:     if "--fingerprint" in sys.argv:
```
