# Bàn giao Antigravity: thu gọn SpinupMail, sửa bug, đẩy source để review

## Yêu cầu hiện tại và bối cảnh

Làm việc tại `C:/Users/Lenovo/Downloads/spinupmail-main/spinupmail-main`. Repo lồng trong thư mục tải xuống; đừng nhầm với thư mục cha hoặc project WORK-TEAM. Remote hiện tại: `https://github.com/wtrg/meta-muse-bot.git`. Đọc AGENTS.md nếu có, git status/diff và các sửa đổi đang tồn tại trước khi làm. Không reset hay ghi đè thay đổi người dùng/agent khác.

Người dùng muốn thu gọn tool giáo dục hiện tại, giữ phần email và hỗ trợ đăng ký Muse, sử dụng Edge. Người dùng đã có VPN chạy trên máy nhưng chưa kiểm thử đầy đủ; độ ổn định chưa được xác nhận. Người dùng từng đề cập tiện ích Green trên Edge như hướng tương lai. Giữ nguyên các chế độ VPN/proxy hiện có, chỉ audit và báo bug trong đợt này; không triển khai bật Green tự động, tối ưu giả vị trí hoặc thay đổi cấu hình VPN máy.

Video tham chiếu: https://www.facebook.com/share/v/18Ra7MPHH5/ (chuyển tới https://www.facebook.com/reel/1649276340314558), tiêu đề quan sát được: “Muse AI Unlimited Account Create | 100% Working Secret Trick”, chủ tài khoản hiển thị “Vectricx By Redwan”. Codex chỉ xem một số đoạn bằng cách tua, không nghe/xem toàn bộ; chưa xác minh danh tính tác giả. Không gán video cho kỹ sư Meta như một sự thật đã kiểm chứng độc lập. Người dùng cho biết Muse có yêu cầu tuổi/vùng và có thể dùng Facebook/Instagram liên kết để xác minh thay phương thức thẻ. Đây là thông tin người dùng cung cấp; nếu cần xác minh tài khoản, để người dùng thực hiện qua luồng chính thức. Ý tưởng xoay vòng email qua Facebook để tạo nhiều tài khoản đã được thảo luận nhưng không thuộc phần được giao triển khai: không xây lại tính năng vượt tuổi, vùng, waitlist, CAPTCHA hoặc chống lạm dụng.

## Giữ lại

1. Tạo và quản lý email/OTP trên nền tảng hiện có cho hộp thư người dùng có quyền sử dụng. Thể hiện rõ provider, lỗi cấp mail, lỗi nhận thư và thời gian chờ. Không cam kết mọi tên miền đều được Muse chấp nhận; không thêm cơ chế né danh sách chặn.
2. Luồng hỗ trợ đăng ký Muse theo quy trình chính thức, trạng thái từng bước chính xác. Khi cần tuổi/thẻ/Facebook/Instagram/CAPTCHA hoặc chờ xét duyệt, dừng ở trạng thái rõ ràng để người dùng hoàn tất. Không tự vượt hoặc coi bước chưa xác minh là thành công.
3. Edge làm trình duyệt ưu tiên. Xác nhận thực tế browser/channel đã mở; phân biệt phiên Playwright mới với profile Edge có sẵn. Không mặc định tiện ích Green của profile người dùng được nạp trong phiên mới.
4. Toàn bộ lựa chọn VPN/proxy hiện có: chỉ đọc/audit, không thay mã, cấu hình, bật/tắt dịch vụ hoặc sửa route trong đợt này. Ghi rõ giới hạn chưa live test.
5. Mã mời: giữ UI/API, normalize/validate, kết quả REDEEMED/FAILED/UNVERIFIED và idempotency. Chỉ dùng cơ chế đổi mã chính thức, không đổi mã thành cơ chế vượt waitlist. Không đồng nhất có mã mời với chat đã sẵn sàng.
6. Cổng OTP: giữ trải nghiệm truy cập mailbox hợp lệ nhưng phải sửa ranh giới quyền, PIN/capability, tenant, rate limit, no-store và an toàn render email. Giữ tính năng không có nghĩa giữ endpoint lộ OTP/PIN công khai.
7. Export TXT/CSV/XLSX: giữ, xuất đúng phiên, đúng mailbox PIN; không lấy OTP đăng nhập thay PIN. Không xuất cookie/token/mật khẩu proxy. Bảo vệ tải file và báo lỗi ghi file/dependency trung thực.
8. Start/stop, log, trạng thái tiến trình, lịch sử cần thiết, nút mở lại phiên, kiểm tra runtime và launcher để vận hành các phần trên. Stop phải dừng đúng job và không tiếp tục tác vụ sau await.

## Loại bỏ phần Facebook tự động

- Bỏ UI/state/request `autoFbBypass`, nhánh `auto_fb_bypass`, bước tạo Facebook và tự bấm liên kết để vượt tuổi trong `scripts/bot_server.py` và `packages/frontend/src/pages/muse-bot-page.tsx`.
- Gỡ toàn bộ route `/api/bot/fb-pool/*`, model/task/caller/import và UI liên quan. Client cũ không được kích hoạt lại qua field dư hoặc endpoint ẩn.
- Loại module `scripts/fb_account_creator.py`, `scripts/fb_pool.py` và launcher `mo_fb_profile_*.bat` khỏi ứng dụng/source bàn giao; cập nhật test, dependency và README liên quan. Nếu có file chứa dữ liệu người dùng, đừng đọc/copy/push/xóa dữ liệu đó để dọn source. Giữ nguyên thư mục profile thật trên máy và thêm ignore phù hợp.
- Phân biệt việc bỏ automation Facebook với liên kết/xác minh chính thức do người dùng thao tác: không tuyên bố Meta không hỗ trợ liên kết.
- Không thêm kết nối ChatGPT/Antigravity vào sản phẩm; đây chỉ là kênh phát triển/review bên ngoài. Không xóa integration SpinupMail khác hoặc package không liên quan chỉ vì gọi chung là “tính năng phụ”; chỉ xóa dependency chứng minh không còn dùng.

## Bằng chứng bug phải xử lý và kiểm chứng

Đọc `audit/ANTIGRAVITY_FIX_PLAN_2026-10-22.md`, `audit/TEST_RESULTS_2026-10-22.md`, `audit/HANDOFF_2026-10-22.md` và probe synthetic `audit/reproduce_local_findings.py`. Báo cáo cũ không phải xác nhận code hiện tại đã sửa.

Lần chạy gần nhất: `python -m unittest discover -s scripts/tests -q` PASS 67/67, nhưng probe vẫn tái hiện 3 lỗi: export phiên rỗng trả latest phiên cũ; session-info ưu tiên OTP thay PIN; account DTO xóa cookies nhưng còn secret proxy. Mock/unit pass không chứng minh live đăng ký thành công.

Ưu tiên bảo mật/tính đúng:

- P0: `/api/public/recent-otps` thiếu auth/scope; fallback provider mailbox đi trước so PIN; raw HTML email vào dangerouslySetInnerHTML. Phải chặn đọc thư/secret không có quyền, sanitize/text render và URL scheme/host validation. Test qua createApp, có negative tests tenant A/B, thiếu/sai PIN, mailbox không đăng ký, provider không được gọi khi từ chối.
- P1: public bulk provisioning/auto-login hardcoded; chuyển hoặc bỏ đường truy cập thiếu auth mà vẫn giữ cổng OTP hợp lệ; không tạo user/admin cố định từ anonymous request. Xóa hardcoded credentials, không in secret ra báo cáo.
- P1: tách OTP tạm thời và mailbox PIN ở API/history/TXT/CSV/XLSX/UI (`acc.otp || acc.pin` hiện sai); provider không có PIN phải thể hiện thiếu PIN, không tự bịa.
- P1: export đúng requested session, unknown/empty session không fallback latest; khôi phục session sau restart không gán tài khoản lịch sử cho session ID mới; tên file/content/count/ID nhất quán; atomic writes, không nuốt lỗi disk/openpyxl.
- P1: DTO allowlist cho account; loại cookie, token, OTP tạm thời, proxy username/password và credential URL/nested fields khỏi phản hồi/log/export không cần thiết. Dùng fixture secret giả để kiểm tra.
- P1: OTP selector timeout hiện vẫn log “sẵn sàng”; sửa thành chưa xác minh/thất bại, không tiếp tục coi thành công. Lỗi false success bước Facebook sẽ biến mất cùng code bị gỡ.
- P1: SDK typecheck từng lỗi TS2307 do DTO import helper từ public router kéo graph DB; tách helper vào tầng dùng chung, không làm yếu auth/CAPTCHA để test pass.

Các phát hiện VPN chỉ audit, không sửa trong đợt này:

- `scripts/psiphon_manager.py:is_psiphon_alive` mặc định fast_check, cổng còn mở/cache trống trả ok=true,is_us=true với IP 127.0.0.1 mà không gọi đo IP; đã xác nhận bằng patch is_tunnel_process_alive=True, _cached_geo=None, mock subprocess.run: network_measurement_called=False.
- `scripts/bot_server.py:_assert_can_continue` cập nhật verified_at_utc khi kiểm tra liveness xong mà không đo lại IP, kể cả system VPN; TTL không đảm bảo độ mới của kết quả đo. Nhiều chỗ khác cũng tự cập nhật timestamp khi chuyển bước.
- Edge mới dùng launch/new_context, không chứng minh extension có trong profile người dùng được nạp. Không tuyên bố Green đã hoạt động.
- Chưa đo live độ ổn định VPN, chưa chứng minh đăng ký thật; mọi kết luận phải có phạm vi và evidence rõ.

## Test và GitHub

Làm theo từng giai đoạn: thu gọn Facebook, fix P0/P1 không thay VPN, chạy test phù hợp, typecheck/build, kiểm tra UI. Chỉ dùng synthetic/mock và fixture được phép, không đọc OTP/cookie thật hoặc tạo tài khoản thật để test. Máy từng gần cạn RAM: chạy suite tuần tự, giới hạn worker. Backend unit, SDK, component từng đỏ hoặc timeout; phân biệt bug với lỗi tài nguyên, không công bố full pass khi chưa chạy đủ. Test phải bắt các lỗi dữ liệu và access-control bên trên, không chỉ mirror implementation.

Người dùng đã yêu cầu Antigravity đẩy source lên GitHub để ChatGPT review. Sau khi sửa, kiểm tra remote/quyền truy cập, tạo branch review phù hợp, stage CHỌN FILE, kiểm tra diff và secret trước commit; tuyệt đối không git add . trên repo hiện tại. Không force-push, không đổi visibility, không merge/deploy. Không push profiles/, test_edge_p/, cookies, account store, .env/.dev.vars, exports, raw dumps/screenshots/log chứa thông tin, token, proxy config có credential. Bổ sung .gitignore cho runtime/profile/dump nhưng không xóa dữ liệu thật. Nếu source lịch sử có credential thật, báo blocker đã che giá trị; không phát tán thêm.

Tạo PR nếu có quyền, mô tả scope giữ/bỏ, test thực chạy, VPN chỉ audit, hạn chế và commit SHA. Trả URL repo/branch/PR và SHA cùng danh sách thay đổi/test/pass/fail/blocked. Chưa push được thì ghi CHƯA PUSH và lý do; không nói đã hoàn tất theo ý định.

Đầu ra bắt buộc: checklist mọi yêu cầu ở trên (giữ/bỏ/fix/audit-only), kết quả từng lệnh kiểm thử, các lỗi còn mở, reference source/line và URL commit/PR. ChatGPT review phải đọc đúng SHA sau fix, không review mặc định branch cũ; chỉ vòng review sau khi có source thật. Không đợi nhận định ChatGPT để che lỗi đã biết, và không coi “đã gửi prompt” là “đã review xong”.
