# CHATGPT REVIEW PACKET — R05 HARDENING & SECRET BOUNDARY FIXES

**Target Branch:** `review/audit-fix-2026-10-22`  
**Base Commit:** `bec3f317ac7bbdbfa515b4f5e5ccbef78428d0cb`  
**Scope:** Resolving P1/A08 (Proxy Credential Redaction in TXT & Error DTO), P1/A02 (PIN Transport via Header/Body & URL Query Scrubbing), P1/A07 (Atomic File Exports with Error Propagation), Contract Test Accuracy, and P2/A12–A14 (Launcher Local Health Probe & Stale Daemon Guard, Tunnel URL Validation).

---

## 1. PHẠM VI VÀ CÁC THAY ĐỔI ĐÃ THỰC HIỆN

### (A) P1 / A08: Khử rò rỉ Credential trong TXT Export và Error DTO
- **Vấn đề trước sửa:** `save_accounts_txt()` xuất nguyên văn `proxy_used` chứa `user:pass@host:port`. `get_accounts()` trả raw `a.error` chứa proxy password hoặc token khi có lỗi mạng.
- **Giải pháp:**
  - `save_accounts_txt()` áp dụng `sanitize_proxy_display()` cho cả danh sách tài khoản thành công và danh sách thất bại/waitlist. Mật khẩu proxy bị loại bỏ hoàn toàn khỏi file TXT.
  - Mã PIN hộp thư hợp lệ được bảo lưu theo hợp đồng phục vụ người dùng lấy OTP.
  - `get_accounts()` và log hệ thống áp dụng `redact_sensitive()` khử toàn bộ username/password proxy, token, chuỗi password URL-encoded.
  - Fixed-width regex regex compile trong Python 3.11: sửa lookbehind variable-width `(?<=[^a-zA-Z0-9_-]|^)` thành `(^|[^a-zA-Z0-9_-])` tránh runtime `re.error`.
- **Bằng chứng kiểm thử:**
  - `test_t25_save_accounts_txt_strips_proxy_credentials_and_redacts_errors` PASS.
  - `test_t26_get_accounts_redacts_proxy_passwords_in_error_dto` PASS.
  - Probe `audit/reproduce_local_findings.py`: `ACCOUNT_DTO_CREDENTIAL_LEAK: resolved=True`.

### (B) P1 / A02: Chuyển kênh mang PIN ra khỏi URL Query (Header/Body Transport)
- **Vấn đề trước sửa:** `public-otp-page.tsx` và `bot_server.py:poll_spinup_otp` truyền `?pin=...` qua query param trong URL. Giao diện chia sẻ link tự động gắn `&pin=...`.
- **Giải pháp:**
  - `packages/backend/src/modules/public-otp/router.ts`:
    - Hỗ trợ trích xuất PIN từ HTTP Header `X-Mailbox-Pin` (và header `pin`).
    - Hỗ trợ method `POST /api/public/otp` với JSON body `{ email, pin }`.
    - Duy trì fallback query param cho tính tương thích ngược nhưng không còn khuyến khích.
  - `packages/frontend/src/pages/public-otp-page.tsx`:
    - `fetchOtp` gửi PIN qua header `"X-Mailbox-Pin": targetPin`.
    - Ngay khi mount với `?pin=...`, component lưu PIN vào state và gọi `window.history.replaceState` để xóa sạch `?pin=` khỏi thanh địa chỉ trình duyệt (chống rò rỉ qua Browser History, Referrer, Telemetry).
    - Hộp tip chia sẻ link đổi thành link hòm thư an toàn không kèm PIN: `{origin}/otp?mail={email}`.
  - `scripts/bot_server.py:poll_spinup_otp`:
    - Gửi request đến `/api/public/otp?email=...` kèm header `"X-Mailbox-Pin": pin.strip()`.
- **Bằng chứng kiểm thử:**
  - `packages/backend/tests/unit/public-otp-router.test.ts`:
    - Test `P1/A02: supports X-Mailbox-Pin header on GET /otp and POST /otp body, avoiding secret in URL query` PASS.
    - Test `Multi-step contract: provisioned secret from storage is accepted via X-Mailbox-Pin header and rejects wrong tenant secret` PASS.
    - 24/24 tests trong suite PASS.
  - `test_t29_poll_spinup_otp_transports_pin_via_header` PASS.

### (C) P1 / A07: Ghi File Export Nguyên Tử (Atomic) và Lan Truyền Lỗi
- **Vấn đề trước sửa:** `save_accounts_txt()` và `save_session_csv_and_excel()` ghi trực tiếp vào file đích rồi nuốt lỗi bằng `except: pass/print`, có thể để lại file rác hoặc trả file của phiên cũ khi disk lỗi.
- **Giải pháp:**
  - Xây dựng 3 hàm: `atomic_write_text()`, `atomic_write_csv()`, `atomic_write_excel()`.
  - Tạo file tạm bằng `tempfile.mkstemp` ngay trong thư mục đích (`dir=target_dir` để đảm bảo cùng phân vùng ổ đĩa trên Windows), flush + fsync dữ liệu, sau đó thực hiện `os.replace` nguyên tử.
  - Khối `except` tự động dọn dẹp file tạm và `raise` ngoại lệ ra caller thay vì nuốt lỗi.
- **Bằng chứng kiểm thử:**
  - `test_t27_atomic_write_failure_propagates_exception_and_cleans_tmp` PASS.
  - `test_reserved_alias_latest_rejected_on_csv_and_excel` PASS.

### (D) Đính chính và chuẩn hóa Contract Test
- **Vấn đề trước sửa:** Test mang tên `Contract end-to-end` trong `public-otp-router.test.ts` chỉ mock DB rồi gọi GET OTP, không thực sự tạo address.
- **Giải pháp:**
  - Đổi tên test thành `OTP query contract: allows OTP query with valid secret, denies wrong/tenant PIN`.
  - Bổ sung test multi-step contract tích hợp storage logic chung giữa secret được cấp và quy trình xác thực OTP qua Header/Body.

### (E) P2 / A12–A14: Launcher Readiness & Tunnel URL Validation
- **start_tool.bat:**
  - Nhánh `BOT_CHECK_CODE=2` (cổng 8790 bị chiếm bởi tiến trình lạ hoặc sai fingerprint/revision) được xử lý dừng ngay launcher (`exit /b 1`), ngăn chặn việc báo ready giả mạo.
  - Readiness probe port 8787 chuyển sang kiểm tra endpoint local `/health` thay vì `/api/public/domains` (vốn phụ thuộc kết nối bên ngoài Mail.tm).
- **scripts/bot_server.py:**
  - `validate_tunnel_url()` xác thực scheme (`http`/`https`), loại bỏ loopback IP (`127.0.0.1`, `localhost`, `0.0.0.0`, `::1`), kiểm tra hostname hợp lệ; không fallback trycloudflare cố định.
- **Bằng chứng kiểm thử:**
  - `test_t28_validate_tunnel_url_enforces_public_domain_and_scheme` PASS.
  - `packages/backend/src/index.ts:80` `/health` đã được kiểm chứng trả `{ status: "ok" }`.

---

## 2. TỔNG HỢP KẾT QUẢ KIỂM THỬ THỰC TẾ

1. **Python Regression & Unit Test Suite (`scripts/tests`):**
   - Command: `python -m unittest discover -s spinupmail-main/scripts/tests -v`
   - Kết quả: **76/76 tests PASS** (Exit Code: 0).
2. **Synthetic Local Findings Probes (`audit/reproduce_local_findings.py`):**
   - `EXPORT_CROSS_SESSION`: **resolved** (status 404).
   - `EMPTY_SESSION_FALLBACK_LATEST`: **resolved** (status 404).
   - `OTP_USED_AS_MAILBOX_PIN`: **resolved** (`pin_is_real_pin=True`).
   - `ACCOUNT_DTO_CREDENTIAL_LEAK`: **resolved** (`proxy_secret_still_present=False`).
3. **Backend Public OTP & Security Unit Tests:**
   - Command: `pnpm -C packages/backend test:unit tests/unit/public-otp-router.test.ts`
   - Kết quả: **24/24 tests PASS** (Duration: 34.91s).
4. **Toàn bộ Backend Unit Tests:**
   - 48 test files, **353/353 unit tests PASS** (chạy độc lập đạt 100% xanh; không sửa assertion, không tăng timeout).
5. **Frontend Unit Tests & Typecheck:**
   - Command: `pnpm -C packages/frontend test:unit` -> **46/46 tests PASS** (13 test files).
   - Command: `pnpm -C packages/frontend typecheck` -> **0 errors** (tsc -b --noEmit clean).
6. **Backend Typecheck:**
   - Command: `pnpm -C packages/backend typecheck` -> **0 errors** (tsc -b --noEmit clean).

---

## 3. DANH MỤC FILE THAY ĐỔI
- `packages/backend/src/modules/public-otp/router.ts`: Hỗ trợ `X-Mailbox-Pin` header & `POST /otp` body.
- `packages/backend/tests/unit/public-otp-router.test.ts`: Đổi tên contract test, thêm negative/positive tests cho header & body.
- `packages/frontend/src/pages/public-otp-page.tsx`: Gửi PIN qua header, xóa `?pin=` khỏi thanh địa chỉ, cập nhật template tip.
- `scripts/bot_server.py`: Khử proxy user/pass trong TXT export, redact error DTO, atomic file writes, validate tunnel URL, poll OTP qua header.
- `scripts/tests/test_muse_regression_v5.py`: Thêm T25–T29 bao phủ toàn bộ các nội dung sửa.
- `start_tool.bat`: Chặn stale process (BOT_CHECK_CODE=2), probe local `/health`.
- `audit/A01_A15_STATUS_CHECKLIST.md`: Bảng checklist chi tiết 15 mục A01–A15.
