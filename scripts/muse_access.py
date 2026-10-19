"""Classify rendered Muse screens; bundled JavaScript is not account evidence."""
import asyncio
from urllib.parse import urlparse


class MuseAccessError(RuntimeError):
    def __init__(self, status, message):
        self.status = status
        super().__init__(message)


def classify_access(url, text, chat_visible=False):
    text = text.lower().replace("’", "'").replace("\u00a0", " ")
    path = urlparse(url).path
    if any(term in text for term in (
        "isn't available in your country", "not available in your country",
        "not available in your region", "chưa có ở quốc gia", "chưa hỗ trợ quốc gia",
    )):
        return "WAITLISTED_GEOGATED", "Muse thông báo chưa hỗ trợ quốc gia/khu vực của tài khoản."
    if any(term in text for term in ("join the waitlist", "join waitlist", "on the waitlist", "danh sách chờ")):
        return "WAITLISTED", "Muse đang hiển thị danh sách chờ; chưa xác định nguyên nhân."
    if any(term in text for term in (
        "log in or create an account", "use another account", "enter your code",
        "finish creating your account",
    )) or path.startswith(("/login", "/aymh", "/auth")):
        return "LOGIN_REQUIRED", "Chưa hoàn tất đăng nhập Muse; không có bằng chứng bị chặn vùng."
    if path.startswith("/access"):
        return "ACCESS_PENDING", "Muse chưa cấp quyền truy cập chat; chưa xác định nguyên nhân."
    if chat_visible:
        return "SUCCESS_CHAT_READY", "Đã thấy ô chat hoạt động trong Muse."
    return "ACCESS_UNVERIFIED", "Chưa xác minh được màn hình chat; không kết luận là chặn vùng."


async def inspect_muse_access(page, continue_saved_login=False, attempts=8):
    continued = False
    for attempt in range(attempts):
        text = await page.inner_text("body")
        editor = page.locator('textarea, [contenteditable="true"], input[placeholder*="Ask" i], input[placeholder*="goal" i], input[placeholder*="task" i], div[role="textbox"]')
        visible = False
        for candidate in await editor.all():
            if await candidate.is_visible() and await candidate.is_enabled():
                visible = True
                break
        status, message = classify_access(page.url, text, visible)
        if status in ("WAITLISTED_GEOGATED", "WAITLISTED", "SUCCESS_CHAT_READY"):
            return {"status": status, "message": message}
        # The rendered account chooser contains a saved-account tile, not chat.
        if continue_saved_login and not continued and status == "LOGIN_REQUIRED":
            tile = page.get_by_text("Meta Account", exact=True)
            if await tile.count() == 1 and await tile.is_visible():
                await tile.click(timeout=5000)
                continued = True
        if attempt + 1 < attempts:
            await asyncio.sleep(2)
    return {"status": status, "message": message}
