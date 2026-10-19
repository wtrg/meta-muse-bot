"""Redeem the supplied referral code through the authenticated settings UI."""
import asyncio
import re
from urllib.parse import urlparse


def normalize_invite_code(value):
    if not value or not value.strip():
        return None
    value = value.strip()
    if "://" in value:
        parsed = urlparse(value)
        if parsed.scheme != "https" or parsed.hostname != "muse.ai":
            raise ValueError("Link mời phải thuộc https://muse.ai")
        value = parsed.fragment or parsed.path.rstrip("/").split("/")[-1]
    if not re.fullmatch(r"[A-Za-z0-9]{6}", value):
        raise ValueError("Mã mời phải có đúng 6 chữ cái/chữ số.")
    return value


def redemption_outcome(text):
    text = text.lower()
    if re.search(r"(code|invite|token).{0,80}(successfully redeemed|redeemed successfully)|successfully redeemed|mã.{0,60}(thành công|đã được quy đổi)", text):
        return "REDEEMED"
    if re.search(r"invalid (invite )?code|code.{0,40}(expired|already used)|mã.{0,40}(không hợp lệ|hết hạn|đã sử dụng)", text):
        return "REJECTED"
    return "UNVERIFIED"


async def _visible(locator):
    for item in await locator.all():
        if await item.is_visible() and await item.is_enabled():
            return item
    return None


async def redeem_invite(page, supplied_code):
    code = normalize_invite_code(supplied_code)
    if not code:
        return {"code": None, "status": "NOT_REQUESTED", "message": "Không yêu cầu đổi mã mời."}
    settings = await _visible(page.get_by_role("button", name=re.compile(r"^(Settings|Cài đặt)$", re.I)))
    if not settings:
        return {"code": code, "status": "UNAVAILABLE", "message": "Chưa thấy nút Cài đặt trong tài khoản đã đăng nhập."}
    await settings.click()
    menuitem = await _visible(page.get_by_role("menuitem", name=re.compile(r"Settings|Cài đặt", re.I)))
    if menuitem:
        await menuitem.click()
    entry = None
    for _ in range(10):
        entry = await _visible(page.get_by_role("button", name=re.compile(r"redeem (invite code|token)|use invite code|quy đổi mã|đổi mã|sử dụng mã mời", re.I)))
        if entry:
            break
        await asyncio.sleep(1)
    if not entry:
        return {"code": code, "status": "UNAVAILABLE", "message": "Tài khoản chưa hiển thị mục đổi mã mời; chưa xác nhận đủ điều kiện."}
    await entry.click()
    dialogs = page.get_by_role("dialog")
    dialog = await _visible(dialogs)
    scope = dialog or page
    field = await _visible(scope.get_by_role("textbox", name=re.compile(r"code|mã", re.I)))
    if not field:
        field = await _visible(scope.locator('input[placeholder*="code" i], input[placeholder*="mã" i]'))
    if not field:
        return {"code": code, "status": "UNVERIFIED", "message": "Đã mở phần đổi mã nhưng chưa nhận diện được ô nhập."}
    await field.fill(code)
    submit = await _visible(scope.get_by_role("button", name=re.compile(r"^(Redeem|Redeem code|Redeem invite code|Confirm|Quy đổi|Đổi mã|Xác nhận)$", re.I)))
    if not submit:
        return {"code": code, "status": "UNVERIFIED", "message": "Đã nhập đúng mã nhưng chưa thấy nút xác nhận khả dụng."}
    await submit.click()
    for _ in range(12):
        message = (await page.inner_text("body")).lower()
        if redemption_outcome(message) == "REDEEMED":
            return {"code": code, "status": "REDEEMED", "message": "Muse xác nhận đổi mã mời thành công."}
        if redemption_outcome(message) == "REJECTED":
            return {"code": code, "status": "REJECTED", "message": "Muse từ chối mã mời hoặc tài khoản không đủ điều kiện; kiểm tra thông báo trong cửa sổ."}
        await asyncio.sleep(1)
    return {"code": code, "status": "UNVERIFIED", "message": "Đã gửi mã nhưng chưa nhận được xác nhận đổi mã thành công từ Muse."}
