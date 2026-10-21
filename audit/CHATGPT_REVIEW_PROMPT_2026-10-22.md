# Prompt ChatGPT: review source SpinupMail sau khi Antigravity sửa

Hãy review độc lập source sau fix của `https://github.com/wtrg/meta-muse-bot`, bám đúng URL commit/PR và SHA mà Antigravity cung cấp. Nếu chưa có SHA/PR/source truy cập được, nói rõ đang chờ; không giả vờ đã đọc local file hoặc đã review code.

Yêu cầu sản phẩm: giữ email/OTP và hỗ trợ đăng ký Muse qua quy trình chính thức; Edge ưu tiên; giữ nguyên các lựa chọn VPN/proxy để audit (không triển khai/đổi VPN trong đợt này); GIỮ mã mời, cổng OTP và export TXT/CSV/XLSX cùng start/stop/log/lịch sử cần thiết. BỎ tạo Facebook tự động, `autoFbBypass`/`auto_fb_bypass`, Facebook pool, API `/api/bot/fb-pool/*`, module/caller/UI/launcher phụ thuộc. Không tích hợp ChatGPT/Antigravity vào sản phẩm; hai ứng dụng chỉ dùng để sửa và review.

Người dùng mô tả tool giáo dục, có VPN hệ thống chưa kiểm thử đủ và mong muốn Edge/Green trong tương lai. Đợt này Green chỉ là bối cảnh tương lai, không hạng mục triển khai. Người dùng cung cấp thông tin Facebook/Instagram có thể dùng trong bước xác minh Muse. Giữ bước xác minh chính thức cho người dùng tự hoàn tất; không triển khai tạo nhiều tài khoản bằng xoay vòng liên kết email, hoặc vượt tuổi/vùng/waitlist/CAPTCHA/chống lạm dụng. Video tham chiếu https://www.facebook.com/reel/1649276340314558 chỉ được Codex xem một số đoạn, chưa xác minh tác giả là kỹ sư Meta; đừng tự nâng thành sự thật đã kiểm chứng.

Nội dung đầy đủ để đối chiếu: file `audit/IMPLEMENTATION_HANDOFF_2026-10-22.md` trên đúng commit, cùng kế hoạch audit cũ và kết quả test nếu có. Nếu GitHub chưa có file này, yêu cầu người điều phối cung cấp nội dung, không suy diễn từ tên file. Đọc thay đổi thực và code liên quan, không chỉ README hoặc lời agent báo PASS.

Các lỗi đã xác nhận trước fix cần kiểm tra đã được khắc phục: export sai phiên/fallback latest; OTP bị dùng làm mailbox PIN ở API/UI/TXT/CSV/XLSX; account DTO bỏ cookies nhưng giữ proxy credentials; timeout OTP vẫn báo sẵn sàng; public recent-otps thiếu auth/tenant scope; provider fallback trước kiểm PIN; raw HTML email XSS; provisioning và auto-login hardcoded công khai; coupling DTO→router→DB khiến SDK typecheck lỗi. Không gọi provider/hộp thư thật để khai thác.

Các vấn đề VPN chỉ audit: Psiphon fast_check có thể báo US khi chỉ có cổng mở và không đo IP; verified_at_utc được cập nhật mà không có phép đo mới; system VPN và browser context có thể không đồng nhất; Edge launch/new_context không chứng minh nạp profile/Green sẵn có. Báo chính xác giới hạn; không tối ưu giả vị trí.

Hãy kiểm:
1. Scope giữ/bỏ đúng yêu cầu; không còn hidden route/caller/default bật Facebook hoặc client cũ kích hoạt lại. Không xóa profiles người dùng và không làm hỏng mã mời/OTP/export.
2. Authz tenant/mailbox, PIN/capability, rate limit, no-store, XSS/URL injection; request bị từ chối không gọi provider/ghi DB.
3. Trạng thái thực tế: registration/login/verification pending/invite redeemed/chat ready phân biệt; không quy mọi thất bại cho IP; không báo success khi timeout hoặc chưa xác minh.
4. Contract dữ liệu phiên/PIN/OTP; restart/empty/missing session; CSV/XLSX formula injection nếu có input không tin cậy; atomic write và lỗi disk/dependency; không rò cookie/token/proxy credential.
5. Concurrency/start-stop/cancellation/cleanup; không side effect sau stop; UI request/response và test mock phải phản ánh code thật.
6. Test regression có bắt lỗi thật: baseline Python 67/67 pass nhưng 3 probe synthetic vẫn tái hiện bug. Phân biệt unit/mock với live/E2E; ghi suite chưa chạy, test đỏ hoặc lỗi tài nguyên.
7. Git diff/commit không chứa profiles/, test_edge_p/, accounts/cookies, .env/.dev.vars, proxy credentials, dumps/logs/exports. Không trích giá trị secret vào review.

Trả findings theo P0/P1/P2, path:line trên đúng SHA, trigger cụ thể, impact, cách tái hiện bằng synthetic/fixture và hướng sửa. Đánh dấu lỗi còn tồn tại, đã sửa có bằng chứng, chưa đủ bằng chứng; không bịa PASS hay production verification. Kết thúc với checklist scope và blockers trước merge. Nếu không có actionable findings sau kiểm tra đủ, nói không tìm thấy và nêu test/rủi ro còn thiếu. Người điều phối sẽ chuyển findings cho Antigravity sửa và gửi SHA mới để review lại; không tự nhận đã nhắn hoặc đã sửa khi chưa thực hiện.
