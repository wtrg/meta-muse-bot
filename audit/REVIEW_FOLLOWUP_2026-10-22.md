# Follow-up audit hiện tại

Codex kiểm tra source đang thay đổi; đây chưa phải nghiệm thu commit cuối. Antigravity đang có tool activity thực trong đúng chat Reading And Using Repository; không dispatch lại việc đang chạy. Lịch heartbeat đã bật 15 phút cho audit bảo mật/tính đúng, không cho các phần né xác minh hoặc dùng credential đã gửi trong chat.

## Kết quả tự chạy

`pnpm -C packages/backend exec vitest run --config vitest.unit.config.ts tests/unit/public-otp-router.test.ts --maxWorkers=1`: PASS 8/8, exit 0. Suite mount router riêng trong Hono, không chứng minh toàn bộ createApp/middleware/tenant hoặc production/E2E. Test chưa có rate-limit, tenant A/B, PIN từ mailbox khác, URL giả host hoặc PIN thiếu meta.

## Các điểm còn cần sửa trước nghiệm thu

1. `scripts/bot_server.py:export_session_csv/export_session_excel`: khi state.session_id rỗng và request không có ID, vẫn đọc muse_session_latest. Phiên không tồn tại sau restart còn tải được dữ liệu cũ. Yêu cầu 404/409 khi không có phiên, không fallback dữ liệu phiên cũ; validate ID thay vì xóa ký tự làm hai ID khác nhau trùng nhau. Probe AST chỉ trích hai function vào namespace synthetic với TemporaryDirectory, không import bot, provider, state hay profile thật; cả CSV và XLSX đều trả latest cũ khi session_id rỗng.

2. `packages/backend/src/shared/pin.ts`: thiếu PIN lại suy ra 6 số từ hash addressId, nhận cả PIN kiểu number. Đây vẫn là fallback secret dự đoán được. Mailbox chưa có secret hợp lệ phải bị từ chối; không suy secret từ ID. Cần kế hoạch migration/cấp PIN CSPRNG được xác thực, rate limit cho endpoint OTP và negative tests. Không chỉ chuyển helper ra file mới rồi coi A02 hoàn tất. Kiểm tra thêm DTO trả raw parsedMeta có chứa secret hay không.

3. `packages/backend/src/modules/public-otp/router.ts:extractOtpAndLinks`: chỉ thêm check http(s), vẫn không kiểm hostname thực. Chuỗi domain trong path/query trên host khác vẫn được chọn làm magic link. Dùng scheme/hostname allowlist được định nghĩa rõ, test evil-host chứa domain trong query/path và subdomain lookalike; không nhấp link thật.

4. `create-auth.test.ts` đổi timeout lên 30000 và sửa production captcha config: tách lý do, chứng cứ import chậm và correctness của captcha. Không coi tăng timeout là sửa production bug. Không bỏ assertion làm xanh.

## Phạm vi phối hợp

### Probe bổ sung sau bản sửa export đầu tiên

Source working tree mới đã trả 404 khi không có phiên, 400 cho ID có dấu chấm, 404 cho ID không có file, và 200 cho session-a synthetic hợp lệ, cả CSV/XLSX: 8/8 ca này đạt. Tuy nhiên `session_id=latest` vẫn trả 200 từ artifact latest cũ khi không có phiên hiện tại (2/2 định dạng). ID thực được tạo bằng timestamp, không có session record tên latest; cần chặn alias reserved hoặc map qua manifest session được phép. Đây là probe source bằng AST namespace synthetic, không phải test middleware/auth HTTP hoặc kết luận khai thác từ xa. Chưa nghiệm thu export hoàn toàn.

Tiếp tục sửa bảo mật/tính đúng, giữ mã mời/OTP/export, bỏ auto Facebook/fb-pool. VPN hiện có chỉ audit. Không dùng/chuyển tiếp thông tin đăng nhập người dùng, không xây/giao phần tự động gắn-gỡ email Facebook để vượt tuổi/vùng hoặc cho tài khoản trẻ em. Tại audit ban đầu HEAD là b45b512; lần kiểm tra sau đã xác nhận commit 73db799 trên origin nhánh review/audit-fix-2026-10-22 và gửi source trích đúng SHA cho ChatGPT. Kết quả quan sát CHANGES REQUIRED được ghi ở CHATGPT_R02_REVIEW_SUMMARY.md; sửa export đang ở working tree, chưa có commit mới được kiểm chứng. Chỉ gửi review tiếp khi có diff mới có ý nghĩa.
