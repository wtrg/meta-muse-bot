# Kết quả kiểm tra tại máy — 22/10/2026, Asia/Saigon

Baseline `b45b512d25a6440cd3bd1590cbb7693e422ce538` với các sửa đổi có sẵn. Các lệnh dưới chạy từ `C:/Users/Lenovo/Downloads/spinupmail-main/spinupmail-main`, trừ khi dùng `pnpm -C` để đặt cwd package. Không sửa application code trong audit.

## Hoàn tất

- `python -m unittest discover -s scripts/tests -v`: **PASS, 67/67**, exit 0, 1.895s phần thực thi suite. Đây là mock/unit regression, không phải live registration/E2E. Starlette cảnh báo deprecation httpx.
- `python audit/reproduce_local_findings.py`: **3/3 lỗi tái hiện bằng dữ liệu giả**: export phiên mới trả latest phiên cũ; session-info ưu tiên OTP thay PIN; account DTO loại cookies nhưng còn proxy password. Không gọi provider/browser, file dùng TemporaryDirectory.
- `pnpm -C packages/backend test:unit`: **FAIL, 315 pass / 8 fail, 46 files**, 46.99s. Log `audit-backend-tests.log`.
- `pnpm -C packages/backend exec vitest run --config vitest.unit.config.ts tests/unit/create-auth.test.ts`: **FAIL, 7 pass / 3 fail**, 21.39s. Log `audit-auth-rerun.log`. Timeout import 5s, kế đó mock gọi 2 thay 1, captcha không có với test secret. Timeout có thể gây nhiễu test sau, không gọi đó là ba production bugs độc lập.
- `pnpm -C packages/frontend test:unit`: **PASS, 46/46, 13 files**, 13.84s. Log `audit-frontend-unit.log`.
- `pnpm -C packages/backend test:integration`: **PASS, 11/11, 3 files**, 58.25s. Log `audit-integration.log`. Không bao phủ public OTP router theo tìm kiếm test hiện tại.
- `pnpm -C packages/extension test:unit`: **PASS, 8/8, 3 files**, 33.45s. Log `audit-extension.log`.
- `pnpm -C packages/lite-router test`: **PASS, 18/18, 2 files**, 0.726s. Log `audit-lite.log`.
- `pnpm -C packages/frontend typecheck`: **PASS**, tsc -b --noEmit; command tiếp sau đã chạy, không có TypeScript diagnostics.
- `pnpm -C packages/backend build`: **PASS**, tsc --noEmit. Log `audit-backend-build.log`.
- `pnpm -C packages/sdk typecheck`: **FAIL**, TS2307 ở backend public-otp router import `@/db/email.schema` và `@/db/auth.schema`. Log `audit-sdk-typecheck.log`. DTO address đang import helper từ router, kéo module router/DB vào graph SDK integration.
- `pnpm -C packages/lite-router typecheck`: **PASS**, log `audit-lite-typecheck.log`.
- `pnpm -C packages/extension typecheck`: **PASS**, log `audit-extension-typecheck.log`.
- `pnpm -C packages/landing typecheck`: **PASS**, log `audit-landing-typecheck.log`; orchestration kết thúc exit 0.

## Các lượt không được coi là kết luận deterministic

- `pnpm -C packages/frontend test:component`: **FAIL / INCOMPLETE EXECUTION**, 54 pass / 1 timeout trong 55 test đã báo, 18 files pass / 1 file fail, **15 worker startup errors**. Chỉ 19 files được báo; không có nghĩa toàn bộ component suite đã chạy. Log `audit-frontend-component.log`. Test sign-in callback timeout 5s; cần rerun sau khi ổn tài nguyên.
- `pnpm -C packages/sdk test`: **FAIL**, 23 pass / 3 fail, 3 files; 2 backend integration timeout (15s/5s), 1 polling deadline 50ms. Log `audit-sdk.log`. Chưa tách hết ảnh hưởng RAM và deadline flaky.
- `pnpm -C packages/landing test`: **INTERRUPTED**, đã quan sát 1 timeout ở `agent-discovery.test.ts`, chưa có summary suite. Log `audit-landing.log`.
- `pnpm run lint`: **INTERRUPTED**, đã khởi động lint:root, chưa có exit hoàn tất; không ghi PASS. Log `audit-lint.log`.
- Thử lại component với `--maxWorkers=1` đã khởi động nhưng bị dừng khi tài nguyên máy gần cạn, chưa có summary. Log `audit-frontend-component-serial.log`. Các lệnh SDK/auth serial đặt sau đó **chưa chạy**, không có kết quả.
- Kiểm tra tài nguyên lúc quá tải: RAM khả dụng khoảng **173 MB / 16 GB**. Codex dừng các orchestration kiểm thử của chính audit bằng Ctrl+C, không kill service/user process. Bộ frontend build được chạy riêng sau đó.
- Một lệnh thử vitest backend từ repository root thay vì cwd package trả “No test files found”; **không tính** là kết quả suite. Đã chạy lại đúng bằng script package ở trên.

## Kiểm tra read-only runtime

8790 `/api/bot/runtime`, 8790 `/api/bot/status`, 8787 `/health`, 5173 `/` đều trả HTTP 200. Bot status `isRunning: false`; runtime SHA cùng baseline, PID 22860. Health không chứng minh public API an toàn hoặc luồng OTP thành công. Không gọi API scanner lấy OTP/PIN thật.

## Chưa chạy / còn phải nghiệm thu sau fix

Cloudflare worker-pool tests, Playwright E2E trên DB cách ly, package publication/packing checks, dependency advisory scan và live provider test chưa hoàn tất trong audit này. Không có tuyên bố deployment production đã được kiểm tra. Cần chạy sau khi sửa P0 và ổn tài nguyên, từng suite với giới hạn workers phù hợp. Không chạy live tạo tài khoản, thay VPN, tạo tunnel hay lấy email/OTP thật để làm test.

## Kênh bàn giao

Bridge WT `connection_status`: `fetch failed`. Browser extension create/select tab timeout. Windows UI đã gửi prompt tổng hợp đã che dữ liệu vào ChatGPT web “Tìm hiểu Muse AI”; phản hồi hiển thị **“This response couldn't load”**. Đã reload/thử retry; không có plan đọc được để nhận là phê duyệt. Kế hoạch tại `ANTIGRAVITY_FIX_PLAN_2026-10-22.md` được Codex soạn độc lập từ mã và probe, không gán tác giả/phê duyệt cho ChatGPT web.

Antigravity được giao đúng project qua UI; trạng thái xác nhận nhận việc ghi trong `HANDOFF_2026-10-22.md` sau khi có bằng chứng hiển thị.

## Frontend production build

Lượt chạy riêng: `pnpm -C packages/frontend build`: **PASS, exit 0**, log `audit-build.log`, Vite build 19.66s. Bundle JS chính 2,279.23 kB (gzip 668.66 kB), có cảnh báo chunk lớn hơn 500 kB và thời gian plugin. Đây là cảnh báo hiệu năng P2, không phải build failure. Dòng `AUDIT_EXIT_CODE=0` được ghi sau process. Không có production deploy.
