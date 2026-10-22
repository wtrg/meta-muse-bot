# Audit R05 — bec3f317ac7bbdbfa515b4f5e5ccbef78428d0cb

Origin review/audit-fix-2026-10-22 đã được Codex đối chiếu cùng SHA. Đọc diff 44521e7..bec3f31 và tự chạy 3 suite OTP/router/service: PASS 48/48, 3 files, exit 0. Chỉ chứng minh phạm vi các test đó; không có live account/provider/VPN test.

## Đã kiểm chứng và đính chính

- R04: create response hiện trả PIN của chính request sau insert thành công, DTO list/detail vẫn bỏ pin, POST no-store. Top-level generatePin đã khai báo boolean.
- Nhận định Codex trước đây rằng top-level generatePin bị Zod strip là sai: schema cũ có `.passthrough()`. ChatGPT đã chỉ ra; đã sửa ghi chú R04. Thiếu khai báo type/validation là vấn đề thực, không phải route chắc chắn strip field.
- Test mang tên `Contract end-to-end: create address...` trong public-otp-router.test.ts KHÔNG gọi createEmailAddress hay POST create; chỉ đặt generatedPin='481516' vào DB mock rồi GET OTP. Test router POST cũng mock service hoàn toàn; test GET không leak chỉ trả fixture vốn không có secret. Đây không phải toàn chuỗi tạo→nhận secret→đọc/tenant thật. Sửa tên/báo cáo hoặc thêm fixture contract thực dùng cùng storage và code tạo/DTO; không gọi provider thật.

## Các phần kế hoạch cũ chưa xong — không phải yêu cầu mở rộng

### P1 / A08: TXT và error DTO vẫn chứa credential

Probe AST cô lập trích save_accounts_txt, sanitize_proxy_display, get_accounts từ source SHA này; namespace có state giả, __file__ trong TemporaryDirectory/scripts, ACCOUNTS_FILE không tồn tại. Không import bot hoặc load accounts thật. Kết quả:

- TXT_EXPORT_PROXY_SECRET: secret_present=true. save_accounts_txt dùng raw proxy_used cho cả danh sách ready/failed; user/pass từ proxy URL xuất nguyên văn vào TXT.
- ACCOUNT_ERROR_SECRET: secret_present=true. get_accounts sanitize proxy_used nhưng trả raw a.error, fixture error chứa proxy URL có password vẫn đi ra API.

Đề nghị dùng route summary không credential cho TXT và scrub diagnostic error trước API/log/export; PIN hộp thư cấp hợp lệ được giữ theo contract, không đánh đồng PIN cần xuất với proxy password/token cần xóa. Test secret scan fixture bao phủ TXT, API error, nested error, URL-encoded credentials, không chỉ proxy_used/cookies.

### P1 / A02: PIN vẫn đi trong URL

public-otp-page.tsx đọc searchParams.pin, fetch GET /api/public/otp?email=...&pin=..., và quảng bá link chia sẻ có &pin=. bot poll_spinup_otp cũng truyền query. Query secret có thể vào history/referrer/log/telemetry tùy triển khai. Kế hoạch cũ đã yêu cầu không PIN trong URL. Đổi kênh mang credential sang body/header qua transport an toàn cho mailbox được phép; link chia sẻ chỉ mang địa chỉ hoặc cơ chế capability được thiết kế rõ. Không bỏ PIN/auth/rate-limit, không tự mở public endpoint rộng hơn. Test contract client/server và xác nhận URL/error/log không có fixture PIN.

### P1 / A07: export chưa atomic, nuốt lỗi ghi

save_accounts_txt, save_session_csv_and_excel vẫn ghi trực tiếp nhiều đường dẫn rồi catch/print error, không truyền thất bại cho caller. Khi disk/full/dependency lỗi có thể trả file cũ hoặc file dở dưới ID hợp lệ. Cần atomic replace trong cùng thư mục, trạng thái lỗi rõ và không báo export thành công nếu chưa hoàn tất; tests giả lập disk/dependency lỗi, không chạm exports thật. Đừng chỉ dựa probe đọc phiên để nói đã hoàn tất write integrity.

### P2 / A12–A14: giới hạn runtime và báo cáo

- Launcher có thêm probe 8787 nhưng dùng /api/public/domains (có provider fetch); nhánh BOT_CHECK_CODE=2 vẫn tiếp tục start/readiness và có thể báo ready khi runtime stale. Dùng health/identity local phù hợp, fail rõ với stale/alien process, không kill/restart service của người dùng.
- Fingerprint đã thêm muse_browser.py (điểm này đã tiến triển); manifest các module cần thiết vẫn chưa có evidence hoàn tất. Phần VPN liveness/TTL chỉ audit theo scope.
- Tunnel URL env được trả thẳng; file chỉ startswith('http'), fallback loopback. Chưa có validation hostname/scheme hoặc health/current deployment. Phải phân biệt local URL với public sharing, unavailable khi không có public URL hợp lệ; không tự khởi động tunnel.

## Bàn giao

Antigravity sửa phần bảo mật/dữ liệu trên hoặc ghi rõ blocker chưa hoàn tất trong checklist A01–A15 trước khi xin nghiệm thu. Không nối lại tự tạo tài khoản/FB, không mở rộng VPN, không đọc credential/OTP thật. Không tuyên bố toàn bộ A01–A15 resolved theo title commit. Tiếp tục push source chọn lọc, không merge/deploy. ChatGPT review trước chỉ áp dụng SHA cũ; cần source diff mới trước khi đánh giá phiên này.
