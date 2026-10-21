# Audit R03 — 5d4948aa7c03972a00846c6afa07c753f7a09887

Codex xác nhận HEAD và origin nhánh review/audit-fix-2026-10-22 cùng SHA trên. Đây là audit tiếp theo, không nghiệm thu production/E2E. Antigravity vẫn có phiên Working sau push. Phần VPN chỉ audit; không đăng nhập Facebook/đăng ký thật hoặc dùng credential trong chat.

## Kết quả tự chạy

`pnpm -C packages/backend exec vitest run --config vitest.unit.config.ts tests/unit/public-otp-router.test.ts --maxWorkers=1`: PASS 15/15, exit 0. Suite mới có kiểm PIN thiếu/sai, lookalike hostname, rate-limit cùng key và một số request qua createApp. Không chứng minh mọi caller đã chuyển contract, shared-store failure hoặc quyền tải export.

## Phát hiện còn mở

Python regression: `python -m unittest discover -s scripts/tests -q` PASS 68/68, exit 0. Probe cô lập helper rate-limit bằng TypeScript transpile/VM và shared store mock luôn throw trả `allowed: true`; không gọi mạng/provider. Đây là bằng chứng nhánh degradation, không phải khai thác production.

1. **P1 — caller của route bị gỡ còn tồn tại.** `scripts/bot_server.py:create_spinup_email` POST `/api/public/bulk-create`, trong khi route đã bị gỡ. `packages/frontend/src/pages/bulk-create-page.tsx` còn gọi recent-otps, bulk-create và auto-login đã bị gỡ. Source phía caller + test 404 chứng minh contract không còn khớp; không được tuyên bố luồng email hiện tại đã nghiệm thu. Không mở lại các public route thiếu auth, không nối lại tự tạo tài khoản. Loại caller chết hoặc báo rõ chức năng hiện chưa được hỗ trợ; nếu giữ UI mailbox độc lập thì dùng service có auth/quota/ownership đã có. Test caller qua HTTP app với fixture, không chỉ chứng minh endpoint cũ 404. Không tăng throughput hoặc triển khai né kiểm soát đăng ký.

2. **P1 — alias latest vẫn là session ID được chấp nhận.** Regex `[a-zA-Z0-9_-]{1,64}` nhận `latest`, file `muse_session_latest.csv/xlsx` vẫn tồn tại và được write bởi exporter. Dù nhánh thiếu session đã trả 404, request chỉ định `session_id=latest` vẫn lấy artifact phiên cũ khi không có session record tương ứng. Probe source synthetic trước đó đã xác nhận hai định dạng; hàm trong commit này giữ cùng nhánh. Chặn reserved alias hoặc dùng manifest kiểm chứng session-to-artifact. Thêm test có latest cũ và state.session_id rỗng, requested latest phải bị từ chối, cả hai định dạng. Không quy kết remote exploit khi chưa có evidence quyền route.

3. **P1 — shared rate-limit có fallback im lặng.** `checkOtpRateLimit` bắt mọi lỗi Durable Object rồi chuyển sang Map riêng từng isolate, tạo budget mới. Khi store lỗi, không bảo toàn giới hạn toàn cục. Khóa `${clientIp}:${email}` cũng chỉ giới hạn từng cặp; chưa có budget độc lập theo mailbox và nguồn. Map fallback không có cleanup/cap cho các key hết hạn không được truy cập lại. Test mới chỉ cùng một key ở memory path. Cần production fail-closed hoặc policy degradation được duyệt rõ; test shared-store outage không cho thêm thử PIN, multi-client/mailbox và cleanup bounded. Đừng tuyên bố có bảo vệ phân tán chỉ dựa vào test memory.

4. **P2 — helper generateSecurePin vẫn Math.random fallback và chưa được caller sử dụng.** Không khẳng định đây là secret đang cấp thật. Xóa fallback không bảo mật hoặc throw khi CSPRNG unavailable; chứng minh đường cấp PIN thật dùng helper an toàn, không chỉ tạo helper không được gọi. Schema meta vẫn nhận unknown; xem lại việc tự cung cấp PIN yếu và cấp quyền qua các service đang có.

## Hành động phối hợp

Yêu cầu Antigravity sửa/ghi rõ blocker trước nghiệm thu; giữ mã mời/OTP/export. ChatGPT R02 chỉ review snapshot 73db799 nên không được gán approval cho 5d4948a. Chỉ gửi R03/diff mới khi có gói source cần kiểm tra, không lặp cùng snapshot. Không merge/deploy hoặc nói luồng giữ lại đã chạy end-to-end nếu chưa kiểm caller/fixture.
