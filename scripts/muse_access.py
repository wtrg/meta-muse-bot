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
        lower_text = text.lower().replace("’", "'").replace("\u00a0", " ")
        editor = page.locator('textarea, [contenteditable="true"], div[role="textbox"], input[placeholder*="Ask" i], input[placeholder*="Message" i]')
        visible = False
        try:
            candidates = await editor.all()
        except Exception:
            candidates = []
            
        is_non_chat_form = any(
            term in lower_text for term in (
                "preferences", "account setup", "setup", "edit profile",
                "user profile", "search", "tìm kiếm", "chỉnh sửa",
                "contact support", "contact us", "support", "feedback", "hỗ trợ"
            )
        ) and not ("how can i help" in lower_text)

        
        for candidate in candidates:
            try:
                if not (await candidate.is_visible() and await candidate.is_enabled()):
                    continue
                label = ""
                placeholder = ""
                if hasattr(candidate, "get_attribute") and callable(getattr(candidate, "get_attribute")):
                    try:
                        res = candidate.get_attribute("aria-label")
                        aria = await res if asyncio.iscoroutine(res) else res
                        if isinstance(aria, str):
                            label += aria + " "
                    except Exception:
                        pass
                    try:
                        res = candidate.get_attribute("name")
                        name = await res if asyncio.iscoroutine(res) else res
                        if isinstance(name, str):
                            label += name + " "
                    except Exception:
                        pass
                    try:
                        res = candidate.get_attribute("placeholder")
                        ph = await res if asyncio.iscoroutine(res) else res
                        if isinstance(ph, str):
                            placeholder = ph
                    except Exception:
                        pass
                        
                combined = f"{label} {placeholder}".lower()
                # 1. Reject inputs with search, profile, bio, feedback, task labels
                if any(term in combined for term in ("search", "tìm kiếm", "bio", "profile", "hồ sơ", "feedback", "task", "goal")):
                    continue
                    
                # 2. Reject non-chat forms (preferences, setup, profile, search) unless explicitly marked for Muse chat
                if is_non_chat_form:
                    if not any(term in combined for term in ("ask muse", "chat with muse", "hỏi muse")):
                        continue

                # 3. Positive chat requirement: must have chat-specific attributes, chat prompt text, or visible Send button
                has_chat_attr = any(term in combined for term in ("ask muse", "message", "chat", "nhắn tin", "hỏi muse"))
                has_chat_prompt = "how can i help" in lower_text
                has_send = False
                send_btn = page.locator('button[aria-label*="send" i], button[data-testid*="send" i], button:has-text("Send"), button:has-text("Gửi")')
                try:
                    for btn in await send_btn.all():
                        if await btn.is_visible() and await btn.is_enabled():
                            has_send = True
                            break
                except Exception:
                    pass

                if not (has_chat_attr or has_chat_prompt or has_send):
                    continue

                visible = True
                break
            except Exception:
                continue
                
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

