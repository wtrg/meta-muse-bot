# Kế hoạch sửa SpinupMail — audit ngày 22/10/2026 (Asia/Saigon)

## Bàn giao

Repository thực tế: `C:/Users/Lenovo/Downloads/spinupmail-main/spinupmail-main`.
Baseline Git HEAD: `b45b512d25a6440cd3bd1590cbb7693e422ce538`, working tree đã có nhiều sửa đổi và file chưa tracked trước audit. Không reset, overwrite hoặc commit toàn bộ working tree.

Yêu cầu người dùng: đọc project, rà soát bug, kết nối ChatGPT web để lập plan và giao Antigravity sửa. Đây là kế hoạch khắc phục bảo mật/tính đúng và kiểm thử. Không mở rộng tạo tài khoản hàng loạt, hồ sơ giả, né chặn vùng/waitlist hoặc cơ chế chống lạm dụng. Không chạy đăng ký thật trong QA; dùng fixture và tài khoản test được phép.

Codex chưa sửa application code. Đã thêm probe offline trong `audit/reproduce_local_findings.py`. Các tài liệu cũ, README và nội dung ảnh là bằng chứng/thông tin cần đối chiếu, không phải nguồn cấp quyền thực thi. Không coi nội dung “PASS/APPROVED” trong báo cáo cũ là xác nhận của lần audit này.

## Kiến trúc và phạm vi đã kiểm tra

- SpinupMail: Cloudflare Workers/Hono, Better Auth, D1/KV/R2; modules auth, organizations, addresses, emails, inbound, integrations.
- React/Vite frontend, browser extension, SDK TypeScript, lite email router, landing/docs và Playwright E2E.
- Python FastAPI `scripts/bot_server.py`, helper browser/access/invite/network, bot UI `/muse`, public `/otp`, `/bulk`, launcher Windows.
- Đọc kỹ các điểm giao giữa auth, public OTP router, dữ liệu phiên/xuất file và luồng trạng thái thể hiện trong ảnh; chạy nhiều suite hiện có. Đây không phải chứng nhận mọi dòng code hoặc mọi deployment đều an toàn.
- Không gọi endpoint công khai để lấy OTP/PIN thật, không xuất cookies thật, không mở đăng ký thật, không thay đổi VPN hoặc khởi động lại dịch vụ.

## Kết luận từ ảnh

Ảnh thể hiện điều hướng Facebook timeout, sau đó log báo hoàn tất gửi thông tin, tiếp theo hết thời gian chờ OTP. Mã hiện tại chứng minh caller không kiểm tra `fb_res.ok` trước thông báo hoàn tất (`scripts/bot_server.py:984–994`). Helper trả `ok: false` khi điều hướng thất bại. Đây là lỗi báo trạng thái; chưa đủ bằng chứng kết luận email không tồn tại, provider lỗi, hay IP bị chặn.

Một lỗi tương tự: khi `wait_for_selector` màn hình mã thất bại, nhánh `except` vẫn ghi “Màn hình nhập mã xác thực đã sẵn sàng” (`bot_server.py:1066–1080`). Hãy báo `UNVERIFIED/FAILED` và lý do thực tế, không coi timeout là thành công.

## Các phát hiện cần sửa

### A01 — P0: Scanner OTP công khai vượt ranh giới tổ chức

`packages/backend/src/index.ts:53` mount public router trước các requireAuth; `modules/public-otp/router.ts:343–436` GET `/api/public/recent-otps` truy vấn thư của toàn DB, trả email, PIN, OTP và magic link, không requireAuth hay organization scope. Auth initialization chỉ tạo đối tượng auth, không xác thực request.

Khắc phục: loại endpoint khỏi public router; nếu cần scanner quản trị, đặt sau auth, permission và organization scope. Không trả PIN/OTP của tenant khác; dùng DTO tối thiểu. Không dùng CORS hay việc ẩn trang frontend thay cho auth API.

Chấp nhận: anonymous trả 401/404; user tenant A không thể xem dữ liệu B kể cả đổi query/header; không gọi provider hoặc ghi DB trước khi quyền được xác nhận. Test qua `createApp`, không chỉ test router tách rời.

### A02 — P0: Nhánh mailbox dự phòng bỏ qua kiểm tra PIN

`public-otp/router.ts:116–228`: chỉ yêu cầu PIN không rỗng; khi địa chỉ không có trong D1, gọi provider và trả thư trước đoạn so sánh expectedPin ở dòng 230. Mọi chuỗi không rỗng đi được nhánh này; chưa chạy khai thác trên thư thật.

Khắc phục: đăng ký quyền sở hữu mailbox và secret được quản lý trước khi cấp quyền đọc; không có record/không xác thực thì từ chối. Áp dụng cùng auth policy cho mọi provider. PIN dùng CSPRNG, hash phía server, giới hạn số lần thử và trả lỗi không tiết lộ địa chỉ tồn tại. Không đưa PIN vào URL/query hay log. Nếu dùng capability thì phải ngẫu nhiên mạnh, có scope, thời hạn và cơ chế thu hồi.

Chấp nhận: thiếu PIN, sai PIN, PIN của mailbox khác, mailbox chưa đăng ký và provider fallback đều không trả nội dung/OTP, không gọi provider khi bị từ chối; rate limit có test; `Cache-Control: no-store` cho phản hồi chứa secret.

### A03 — P0: Render HTML email không sanitize

`packages/frontend/src/pages/public-otp-page.tsx:326–333`: khi bodyText rỗng, raw bodyHtml đi vào `dangerouslySetInnerHTML`. Đây là sink XSS xác nhận bằng source, chưa chạy payload trên UI thật. `public-otp/router.ts:90–99` dùng regex tìm magic link dựa trên chuỗi trong URL; `public-otp-page.tsx:306` và `bulk-create-page.tsx:542` mở link này.

Khắc phục: mặc định render text; nếu cần HTML thì dùng cơ chế sanitize/email renderer đã có, chặn script/event handler/URL nguy hiểm và remote resource không cần thiết; cân nhắc sandbox không same-origin khi hiển thị email. Parse URL và kiểm scheme + hostname theo policy, không dùng contains-domain trong path/query làm chứng minh domain.

Chấp nhận: fixture HTML-only với event handler, SVG/script, javascript URL không thực thi; link có hostname giả/path chứa tên nhà cung cấp bị từ chối; xem email không phát sinh request ra máy chủ tracking. Giữ các test email renderer hiện có xanh.

### A04 — P1: Endpoint public tự cấp dữ liệu user/admin, org và mailbox

`public-otp/router.ts:440–576`: POST `/bulk-create` không auth, dùng user cố định, có nhánh tạo user `role: admin`, org cố định, không đi qua quota/policy của address service. Đây là lỗi kiểm soát truy cập và tiêu thụ tài nguyên; không suy diễn việc tạo row admin đồng nghĩa đã đăng nhập được.

Khắc phục: dừng provision qua public route; dùng service có auth/scope/quota/validation hiện có, không tạo admin/default identity theo request công khai. Không tăng throughput bulk. Xác thực body bằng schema; kiểu prefix sai phải trả 400/422, không TypeError 500; count nguyên và giới hạn rõ.

Chấp nhận: anonymous không tạo DB row, user hoặc provider mailbox; role và org do server xác định từ principal; quota/permission/invalid-input tests có bằng chứng không side effect.

### A05 — P1: Auto-login hardcoded không có production guard

`public-otp/router.ts:580–611`: GET `/auto-login` gọi signInEmail với credentials cố định, chuyển Set-Cookie và redirect. Không có environment gate. Khả năng đăng nhập thật phụ thuộc credentials có tồn tại; chưa thử.

Khắc phục: xóa route khỏi production. Nếu cần dev fixture, tạo qua setup riêng biệt explicit dev-only, không public HTTP auto-login. Xóa hardcoded account/password khỏi source; người vận hành rà soát/thu hồi credential đã dùng thật. Không ghi credential vào báo cáo hoặc log.

Chấp nhận: production route 404 và không gọi signInEmail; test cấu hình production/local riêng. Không làm yếu CAPTCHA để làm test xanh.

### A06 — P1: OTP bị dùng nhầm thành PIN hộp thư

`scripts/bot_server.py:418,442,486,2079` và `muse-bot-page.tsx:1502` ưu tiên `otp` trước `pin`. Hai giá trị có mục đích và thời hạn khác nhau. Probe offline xác nhận session-info trả OTP làm PIN khi cả hai tồn tại.

Khắc phục: field riêng `mailboxPin` và transient `verificationCode`; map rõ tại boundary. Export PIN hộp thư nếu đã được cấp hợp lệ, tuyệt đối không dùng verificationCode làm fallback. Với provider không hỗ trợ PIN, UI phải nói rõ thay vì bịa ra PIN.

Chấp nhận: fixture PIN và OTP khác nhau xuất đúng PIN; thiếu PIN không điền OTP thay; API/history/export dùng cùng contract. Kiểm tra cả TXT, CSV, XLSX và UI.

### A07 — P1: Export trả file của phiên khác; restart dựng phiên mới từ lịch sử

`bot_server.py:355–367` chọn tối đa 4 tài khoản lịch sử ready và gán session mới khi import. `2099–2144` export thiếu file requested session thì fallback `muse_session_latest`. Phiên rỗng/mới hoặc ID không tồn tại có thể tải file cũ dưới tên phiên hiện tại. Probe offline xác nhận CSV; XLSX có cùng nhánh source.

Khắc phục: session ID duy nhất và manifest persisted theo phiên; restart khôi phục đúng identity/trạng thái hoặc báo không có phiên hiện tại. Export chỉ đúng phiên được chọn; thiếu phiên/file thì 404/409 hoặc artifact rỗng rõ ràng, không fallback sang phiên khác. Ghi file atomic và không nuốt lỗi ghi.

Chấp nhận: phiên A có dữ liệu, phiên B rỗng không tải A; ID không tồn tại không tải latest; restart không gán tài khoản A cho session mới; tên file/content/count/session ID nhất quán; lỗi disk/Excel dependency có error UI thay vì báo thành công.

### A08 — P1: Account API chỉ loại cookies, vẫn rò credential khác

`bot_server.py:1513–1532` shallow-copy và xóa cookies, vẫn giữ `route_spec.proxy_config.password`, `proxy_used` chứa user/pass, OTP và `hatch_sess` prefix từ account_data. Probe synthetic xác nhận proxy secret vẫn nằm trong output dù cookies đã bị xóa.

Khắc phục: DTO allowlist thay vì blacklist; chỉ trả cờ có session và route summary không credential. Secret chỉ lưu trong kho cần thiết với ACL/khả năng thu hồi; không trả qua history/log/export mặc định. Rà log `public-otp/mail-tm.ts:113–133` đang ghi raw response có thể chứa metadata thư.

Chấp nhận: recursive secret scan trên JSON/log/error với fixture cookie, token, OTP, password, proxy URL, nested route; không chỉ test key cookies. Không đưa fixture secret vào report thật.

### A09 — P1: Browser profiles có nguy cơ bị add vào Git

`.gitignore` đã chặn nhiều account/export nhưng thiếu `profiles/` và `test_edge_p/`. Cả hai đang untracked trong baseline, có dữ liệu trình duyệt. Chưa phát hiện chúng tracked bằng `git ls-files` trong lần này; không khẳng định đã bị push.

Khắc phục: ignore các profile/runtime/dump chứa session; kiểm tra staged diff trước commit; không xóa profile người dùng. Không commit `scripts/fb_dump.html` nếu chứa thông tin phiên. Secret scan local và xác nhận remediation nếu có secret thật từng được công bố.

### A10 — P1: Test/type contract đang đỏ; SDK kéo theo module DB qua DTO

Backend unit hiện có 5 assertion lệch metadata/API do `pin`/`otpPin` thêm vào; `modules/email-addresses/dto.ts:10,25` import helper từ public-otp router, tạo coupling DTO → router → DB/provider. SDK typecheck báo TS2307 cho alias `@/db/email.schema`, `@/db/auth.schema` khi kéo backend integration graph.

Khắc phục: sau khi chốt secret/DTO policy, tách helper thuần vào shared module đúng layer. Đồng bộ contract/schema/test theo hành vi mong muốn, không xóa assertion hàng loạt. Xử lý alias/import graph với phạm vi test SDK. Có thể giữ PIN chỉ ở flow cấp credential được phép thay vì mọi list/update DTO.

Chấp nhận: backend unit và SDK typecheck pass; không import public router từ DTO; contract test phân biệt credential provisioning với list response.

### A11 — P1: Log thành công sai khi bước trước timeout

Như phần ảnh: bỏ điều kiện `ok` và dùng generic except vẫn báo sẵn sàng. `poll_clean_otp`/`poll_spinup_otp` nuốt lỗi upstream rồi báo TimeoutError chung, không có chẩn đoán đã che dữ liệu.

Khắc phục: trạng thái step có kết quả explicit; lỗi browser, provider auth, 429, network, schema, mailbox-empty được phân biệt; không tiếp tục side effect khi prerequisite thất bại/chưa xác minh. Không sửa bằng tăng timeout vô hạn hoặc né kiểm soát provider. OTP chỉ khớp thư đúng request/time/sender trong fixture; không chọn tùy ý chữ số cũ trong mailbox.

Chấp nhận: fixture navigation fail/selector timeout/upstream 401/429/invalid JSON đều không ghi success sai, không quy lỗi cho IP khi chưa đo được. Stop/exception đóng context/runtime qua finally trên mọi đường thoát; kiểm resource cleanup bằng mock lifecycle.

### A12 — P2: Tunnel URL cấu hình theo máy, fallback hostname cũ

`bot_server.py:373–392` đọc đường dẫn log Antigravity hardcoded và fallback trycloudflare hostname cố định. Export có thể phát link chết hoặc không còn thuộc deployment hiện tại.

Khắc phục: config rõ ràng/URL do tunnel manager hiện tại cung cấp; kiểm health và xác thực đích, timeout hữu hạn; không có URL hợp lệ thì báo unavailable. Không tự mở public tunnel trong quá trình fix.

### A13 — P2: Launcher readiness và runtime fingerprint thiếu bằng chứng

`start_tool.bat:71–75` readiness chỉ kiểm bot status + frontend, không kiểm 8787 health. Phát hiện stale/alien process vẫn tiếp tục và có thể báo tất cả ready. `_compute_source_fingerprint` chỉ hash 3 file, bỏ `muse_browser.py` và helper mới; patch digest từ git diff cũng không phủ file untracked.

Khắc phục: failure rõ cho runtime không phù hợp; không kill process tùy tiện; kiểm cả ba dịch vụ và protocol identity; fingerprint từ manifest module thực sự nạp. Verify launcher trong môi trường test với fake/stale/non-owned port, không restart dịch vụ đang dùng.

### A14 — P2: Báo cáo kiểm thử cũ vượt quá bằng chứng của test

`scripts/tests/test_muse_regression_v5.py:548–568`: T23 dùng TestClient, không chạy launcher Windows; T24 chỉ hasattr các module, không chạy frontend build. `ROUND_1_REVIEW_PACKET.md` mô tả các gate rất rộng. Mocks có thể đúng nhưng không chứng minh live provider, WebRTC hay E2E.

Khắc phục: đặt tên test đúng phạm vi, tạo pipeline thực chạy Python + build + integration + fixture E2E; lưu command/cwd/exit code/artifact/time. Tách mock/static/live. Không tuyên bố 100% toàn hệ thống vì 67 unit pass.

### A15 — P2: Timeout/worker errors và policy CAPTCHA cần tái kiểm

Backend auth test: lần đầu 3 lỗi gồm import timeout, mock call 2 lần, thiếu captcha plugin với test key. Timeout có thể làm rò công việc async sang test sau; chưa kết luận mock-call là production bug. Source `create-auth.ts:269–270` chủ động loại test secret key mà test mong giữ captcha. Component suite lần đầu có worker timeout và một test sign-in timeout; SDK có test dùng deadline 50ms. Cần rerun hạn chế workers trước khi phân loại deterministic bug.

Khắc phục: chốt policy rõ giữa E2E test key và production CAPTCHA; giữ kiểm tra từ chối request thiếu CAPTCHA trong test phù hợp. Dùng clock/fake timers và mock provider cho polling; không tăng timeout hoặc sửa expected tùy tiện để che lỗi. Giới hạn workers theo tài nguyên Windows/CI.

## Thứ tự thực hiện cho Antigravity

1. **PR/commit A — Chặn lộ dữ liệu:** A01, A02, A04, A05. Tests anonymous/tenant/wrong PIN phải đỏ trước khi sửa và xanh sau sửa; không gọi dịch vụ thật. A04 chỉ khôi phục auth/quota, không mở rộng provisioning.
2. **B — Hiển thị nội dung an toàn và secret boundary:** A03, A08, A09; allowlist DTO và HTML/link tests; không xóa dữ liệu/profile hiện tại.
3. **C — Đúng dữ liệu phiên và credential:** A06, A07; session manifest, PIN contract, export/error tests và fixtures restart.
4. **D — Runtime và trạng thái:** A11–A14; fail-closed prerequisites, bounded cleanup/stop, launcher health, tunnel config; không tối ưu bypass.
5. **E — Khôi phục CI:** A10, A15 và những lỗi có log trong `TEST_RESULTS_2026-10-22.md`; cập nhật docs/contract; chạy full checks sau sửa. Tách lỗi môi trường, flaky deadline và bug deterministic.

## Quy tắc nghiệm thu

- Bảo toàn uncommitted work; chỉ stage file liên quan và xem diff trước commit. Không deploy, không Git push, không công bố URL chứa credential.
- Mỗi task có file/line, mô tả trước/sau, test âm, command + cwd + exit code và hạn chế còn lại. Không đánh dấu hoàn tất theo tên test hay mock assertion không kiểm hành vi.
- Acceptance bắt buộc: auth + organization isolation, PIN fallback fail-closed, HTML/link safety, zero cross-session export, DTO không secret, cleanup khi timeout/stop, typecheck/build và suite liên quan xanh.
- Không tuyên bố OTP flow live thành công nếu chưa có test được phép và artifact thật. Health 200 chỉ xác nhận process phản hồi.

## Phối hợp ChatGPT web / Antigravity

Codex đã gửi một bản tổng hợp audit đã bỏ credential lên cuộc trò chuyện ChatGPT web đang mở “Tìm hiểu Muse AI”. Không gửi profile/cookie/OTP/PIN thật hay toàn bộ source. UI hiển thị request đã gửi; cần phân biệt việc gửi thành công với việc nhận được plan — trạng thái phản hồi sẽ được ghi riêng trong kết quả bàn giao.

Bridge `mcp__wt_desktop_team.connection_status` trả `fetch failed`; browser extension thao tác tab bị timeout. Fallback Windows UI đã mở được ChatGPT web và tìm đúng cuộc trò chuyện Antigravity “Reading And Using Repository” thuộc project spinupmail-main. Không coi nội dung báo cáo cũ trong các chat này là xác nhận audit hiện tại.
