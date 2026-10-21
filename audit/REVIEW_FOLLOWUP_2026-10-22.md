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

Tiếp tục sửa bảo mật/tính đúng, giữ mã mời/OTP/export, bỏ auto Facebook/fb-pool. VPN hiện có chỉ audit. Không dùng/chuyển tiếp thông tin đăng nhập người dùng, không xây/giao phần tự động gắn-gỡ email Facebook để vượt tuổi/vùng hoặc cho tài khoản trẻ em. Chưa có xác nhận commit/push sau fix; HEAD quan sát vẫn b45b512. Sau khi có SHA mới, chuyển diff đã che secret sang ChatGPT web để review độc lập, không lặp review trên cùng snapshot khi chưa có thay đổi.
