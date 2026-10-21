"""Classify rendered Muse screens; bundled JavaScript is not account evidence."""
import asyncio
from urllib.parse import urlparse


class MuseAccessError(RuntimeError):
    def __init__(self, status, message):
        self.status = status
        super().__init__(message)


def classify_access(url, text, chat_visible=False, gate_text=None):
    text = text.lower().replace("’", "'").replace("\u00a0", " ")
    check_text = (gate_text if gate_text is not None else text).lower().replace("’", "'").replace("\u00a0", " ")
    parsed = urlparse(url)
    path = parsed.path
    hostname = (parsed.hostname or "").lower()
    is_muse_origin = hostname == "muse.ai" or hostname.endswith(".muse.ai")

    if not is_muse_origin:
        return "ACCESS_UNVERIFIED", "Trang không thuộc domain Muse hợp lệ."

    # Active country geogate or waitlist outside transcript takes strict precedence over any generic input
    if any(term in check_text for term in (
        "isn't available in your country", "not available in your country",
        "not available in your region", "chưa có ở quốc gia", "chưa hỗ trợ quốc gia",
    )):
        return "WAITLISTED_GEOGATED", "Muse thông báo chưa hỗ trợ quốc gia/khu vực của tài khoản."
    if any(term in check_text for term in ("join the waitlist", "join waitlist", "on the waitlist", "danh sách chờ")):
        return "WAITLISTED", "Muse đang hiển thị danh sách chờ; chưa xác định nguyên nhân."

    # Auth and login screens outside transcript cannot be overridden by generic inputs
    if path.startswith(("/login", "/aymh", "/auth")) or "log in or create an account" in check_text or "finish creating your account" in check_text:
        return "LOGIN_REQUIRED", "Chưa hoàn tất đăng nhập Muse; không có bằng chứng bị chặn vùng."

    # Access gate screen cannot be overridden by generic inputs
    if path.startswith("/access"):
        return "ACCESS_PENDING", "Muse chưa cấp quyền truy cập chat; chưa xác định nguyên nhân."

    # Active authenticated chat composer on Muse origin
    if chat_visible:
        return "SUCCESS_CHAT_READY", "Đã thấy ô chat hoạt động trong Muse."

    if any(term in check_text for term in ("use another account", "enter your code")):
        return "LOGIN_REQUIRED", "Chưa hoàn tất đăng nhập Muse; không có bằng chứng bị chặn vùng."

    return "ACCESS_UNVERIFIED", "Chưa xác minh được màn hình chat; không kết luận là chặn vùng."


async def inspect_muse_access(page, continue_saved_login=False, attempts=8):
    continued = False
    for attempt in range(attempts):
        text = await page.inner_text("body")
        lower_text = text.lower().replace("’", "'").replace("\u00a0", " ")
        
        # Extract text outside message logs/transcript containers so quotes/history do not trigger false gates
        log_locator = page.locator('[role="log"]')
        gate_text = lower_text
        try:
            if await log_locator.count() > 0:
                for el in await log_locator.all():
                    if await el.is_visible():
                        log_t = (await el.inner_text()).lower().replace("’", "'").replace("\u00a0", " ")
                        gate_text = gate_text.replace(log_t, "")
        except Exception:
            pass

        editor = page.locator('textarea, [contenteditable="true"], div[role="textbox"], input[placeholder*="Ask" i], input[placeholder*="Message" i]')
        visible = False
        try:
            candidates = await editor.all()
        except Exception:
            candidates = []
            
        # Scope form rejection to profile/setup pages, NOT global sidebar search
        is_non_chat_form = any(
            term in lower_text for term in (
                "preferences", "account setup", "setup", "edit profile",
                "user profile", "chỉnh sửa",
                "contact support", "contact us", "feedback"
            )
        ) and not ("how can i help" in lower_text)

        for candidate in candidates:
            try:
                if not (await candidate.is_visible() and await candidate.is_enabled()):
                    continue
                label = ""
                placeholder = ""
                input_type = ""
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
                    try:
                        res = candidate.get_attribute("type")
                        t_val = await res if asyncio.iscoroutine(res) else res
                        if isinstance(t_val, str):
                            input_type = t_val.lower()
                    except Exception:
                        pass
                        
                if input_type == "search":
                    continue

                combined = f"{label} {placeholder}".lower()
                # 1. Reject inputs with search, profile, bio, feedback, task labels
                if any(term in combined for term in ("search", "tìm kiếm", "bio", "profile", "hồ sơ", "feedback", "task", "goal")):
                    continue
                    
                # 2. Reject non-chat forms (preferences, setup, profile) unless explicitly marked for Muse chat
                if is_non_chat_form:
                    if not any(term in combined for term in ("ask muse", "chat with muse", "hỏi muse", "ask anything")):
                        continue

                # 3. Positive chat requirement: must have chat-specific attributes, chat prompt text, or visible Send button
                has_chat_attr = any(term in combined for term in ("ask muse", "message", "chat", "nhắn tin", "hỏi muse", "ask anything"))
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
                
        status, message = classify_access(page.url, text, visible, gate_text=gate_text)
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

