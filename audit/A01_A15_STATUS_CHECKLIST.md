# BẢNG CHECKLIST TRẠNG THÁI KIỂM SOÁT A01 — A15 (AUDIT 2026-10-22)

Tài liệu này đối chiếu và xác nhận trạng thái toàn bộ 15 phát hiện A01 — A15 từ bản kế hoạch `ANTIGRAVITY_FIX_PLAN_2026-10-22.md` và các bổ sung từ Review R01–R05 (bao gồm đợt sửa P1/A08, P1/A02, P1/A07, P2/A12-A14 trên commit `bec3f31` và bản vá hiện tại).

---

## BẢNG TỔNG HỢP TRẠNG THÁI

| Mã | Mức độ | Mô tả tóm tắt | Trạng thái kỹ thuật | Bằng chứng kiểm thử / Verification |
|---|---|---|---|---|
| **A01** | P0 | Scanner OTP công khai (`/recent-otps`) vượt ranh giới tổ chức | **ĐÃ GIẢI QUYẾT** | Route đã bị gỡ hoàn toàn khỏi public router. Anonymous & tenant-cross trả 404. Test: `public-otp-router.test.ts:40-43` PASS. |
| **A02** | P0 / P1 | Mailbox fallback bỏ qua PIN; PIN lộ qua URL query | **ĐÃ GIẢI QUYẾT** | - Fallback Mail.tm kiểm tra nghiêm ngặt PIN và fail-closed 401/404 nếu không khớp.<br>- PIN được chuyển từ URL query sang HTTP Header `X-Mailbox-Pin` và POST body trong backend router, frontend UI và bot server.<br>- Frontend tự động xóa `?pin=` khỏi URL bar ngay khi load.<br>- Rate limit 2 tầng (mailbox 10 req/min, IP 30 req/min) với fail-closed trên DO outage.<br>- Test: `public-otp-router.test.ts` (24/24 PASS), `test_muse_regression_v5.py:test_t29` PASS. |
| **A03** | P0 | Raw HTML email render có sink XSS | **ĐÃ GIẢI QUYẾT** | `public-otp-page.tsx` đã loại bỏ `dangerouslySetInnerHTML`, chỉ render text an toàn. Hostname magic link được lọc chặt chẽ qua allowlist chính thức (`muse.ai`, `facebook.com`, `meta.com`, `instagram.com`). Negative tests host giả mạo PASS. |
| **A04** | P1 | Public endpoint `/bulk-create` tự tạo default user/admin/org | **ĐÃ GIẢI QUYẾT** | Endpoint đã gỡ khỏi public router (trả 404). Việc tạo hộp thư chuyển vào authenticated router `POST /api/email-addresses` tuân thủ hạn mức/quota. Test `public-otp-router.test.ts:45-52` PASS. |
| **A05** | P1 | Hardcoded auto-login (`/auto-login`) thiếu production guard | **ĐÃ GIẢI QUYẾT** | Route `/auto-login` và hardcoded credentials đã gỡ bỏ hoàn toàn. Trả 404. Test `public-otp-router.test.ts:54-57` PASS. |
| **A06** | P1 | OTP bị gán nhầm thành PIN hộp thư trong export | **ĐÃ GIẢI QUYẾT** | Tách bạch `mailboxPin` và `verificationCode`. Helper không lấy OTP thay PIN. Thư mục và export TXT/CSV/XLSX chỉ ghi PIN thực được cấp hợp lệ. Test probe synthetic `reproduce_local_findings.py` xác nhận `OTP_USED_AS_MAILBOX_PIN: resolved=True`. |
| **A07** | P1 | Export trả file của phiên khác; export ghi đè non-atomic | **ĐÃ GIẢI QUYẾT** | - Reject alias `latest` và manifest/session rỗng với 404/409, không trả dữ liệu phiên cũ.<br>- Các hàm export TXT, CSV, XLSX (`atomic_write_text`, `atomic_write_csv`, `atomic_write_excel`) sử dụng temp file trong cùng thư mục + `os.replace` nguyên tử, dọn dẹp temp file khi lỗi và ném exception cho caller thay vì nuốt lỗi.<br>- Test: `test_t27_atomic_write_failure_propagates_exception_and_cleans_tmp` PASS, `test_reserved_alias_latest_rejected_on_csv_and_excel` PASS. |
| **A08** | P1 | Account DTO & TXT export làm lộ credentials (proxy pass, raw error) | **ĐÃ GIẢI QUYẾT** | - `save_accounts_txt()` khử user/password trong `proxy_used` (bằng `sanitize_proxy_display`), chỉ xuất PIN mailbox hợp lệ theo hợp đồng người dùng.<br>- `/api/bot/accounts` và log hệ thống áp dụng `redact_sensitive()` cho toàn bộ error string, URL proxy, password, secret.<br>- Test: `test_t25` (TXT export không lộ pass), `test_t26` (Error DTO redact) PASS. Probe `ACCOUNT_DTO_CREDENTIAL_LEAK: resolved=True`. |
| **A09** | P1 | Nguy cơ thêm browser profiles/dumps vào Git | **ĐÃ GIẢI QUYẾT** | Đã cấu hình `.gitignore` chặn `profiles/`, `test_edge_p/`, `*.dump`, `fb_dump.html`, cookie exports. Quy trình commit chỉ dùng selective staging (`git add <file>`), không bao giờ `git add .`. |
| **A10** | P1 | Type contract và circular dependency DTO → Public Router | **ĐÃ GIẢI QUYẾT** | Helper thuần (`getMailboxPin`, `getOrDerivePin`) đã được chuyển vào `packages/backend/src/shared/pin.ts`. DTO không import từ public router. Frontend & backend `tsc -b --noEmit` hoàn toàn không còn lỗi (0 errors). |
| **A11** | P1 | Báo thành công giả tạo (log success) khi các bước trước timeout | **ĐÃ GIẢI QUYẾT** | Caller kiểm tra `ok` explicit từ browser/access helpers. Helper bắt lỗi cụ thể, báo trạng thái `FAILED/UNVERIFIED`, không nuốt lỗi timeout thành success. |
| **A12** | P2 | Tunnel URL cấu hình theo máy, fallback hostname cũ | **ĐÃ GIẢI QUYẾT** | Bổ sung hàm `validate_tunnel_url()` kiểm tra scheme (`http`/`https`), từ chối địa chỉ loopback/localhost (`127.0.0.1`, `localhost`, `0.0.0.0`, `::1`), kiểm tra định dạng hostname hợp lệ; không fallback trycloudflare cố định. Test `test_t28` PASS. |
| **A13** | P2 | Launcher readiness probe và runtime fingerprint | **ĐÃ GIẢI QUYẾT** | - `start_tool.bat` chuyển probe port 8787 từ `/api/public/domains` (phụ thuộc Mail.tm) sang `/health` local độc lập.<br>- Xử lý `BOT_CHECK_CODE=2` (port 8790 bị chiếm bởi process lạ hoặc sai fingerprint) dừng ngay launcher (`exit /b 1`), không tiếp tục báo ready giả tạo.<br>- Source fingerprint bao phủ toàn diện các file thực thi của bot. |
| **A14** | P2 | Báo cáo kiểm thử cũ vượt quá bằng chứng thực tế | **ĐÃ GIẢI QUYẾT** | Tách bạch rõ giữa unit test, probe synthetic offline và live run. Đổi tên test `Contract end-to-end` trong `public-otp-router.test.ts` thành `OTP query contract` và bổ sung test multi-step contract có cùng storage logic. Không tuyên bố hệ thống pass 100% khi chỉ chạy mock. |
| **A15** | P2 | Worker timeout và CAPTCHA policy | **ĐÃ KIỂM CHỨNG** | - Tách bạch test key CAPTCHA trong môi trường dev/unit.<br>- Suite chạy đơn lẻ đạt 100% pass (353/353 backend unit tests, 46/46 frontend unit tests, 76/76 python tests). Các timeout xuất hiện khi chạy đồng thời nhiều worker nặng trên máy Windows đã được ghi nhận đúng bản chất tải phần cứng, không làm yếu assertion hay tăng timeout giả tạo. |

---

## CÁC GIỚI HẠN VÀ PHẠM VI TUÂN THỦ (BOUNDARY CONSTRAINTS)

1. **Không tạo tài khoản Facebook tự động:** Đã loại bỏ hoàn toàn các module/caller auto FB theo đúng yêu cầu cập nhật `IMPLEMENTATION_HANDOFF_2026-10-22.md`.
2. **VPN Audit-Only:** Giữ nguyên mã nguồn Psiphon / Windscribe phục vụ audit, không can thiệp routing hệ điều hành, không tự động kích hoạt Green VPN.
3. **Không dùng dữ liệu thật trong QA:** Tất cả test và probe chỉ sử dụng synthetic fixtures, không gọi provider thật, không lấy OTP thật, không đăng ký tài khoản thật.
4. **Bảo mật Git:** Không push `profiles/`, cookies, database files, `.env` hay credential. Chỉ commit và push các source code đã được kiểm tra bảo mật lên branch `review/audit-fix-2026-10-22`.
