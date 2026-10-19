"""Redeem the supplied referral code through the authenticated settings UI."""
import asyncio
import json
import os
import re
import time
from urllib.parse import urlparse

RESERVATIONS_FILE = os.path.join(os.path.dirname(__file__), "invite_reservations.json")


def _load_reservations():
    if os.path.exists(RESERVATIONS_FILE):
        try:
            with open(RESERVATIONS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_reservations(data):
    try:
        temp_file = RESERVATIONS_FILE + ".tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(temp_file, RESERVATIONS_FILE)
    except Exception:
        pass


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
    if re.search(r"invalid (invite )?code|code.{0,40}(expired|already used)|mã.{0,40}(không hợp lệ|hết hạn|đã sử dụng)", text):
        return "REJECTED"
    if re.search(r"(code|invite|token).{0,80}(successfully redeemed|redeemed successfully)|successfully redeemed|mã.{0,60}(thành công|đã được quy đổi)", text):
        return "REJECTED" if "invalid" in text else "REDEEMED"
    return "UNVERIFIED"


async def _visible(locator):
    for item in await locator.all():
        if await item.is_visible() and await item.is_enabled():
            return item
    return None


async def redeem_invite(page, supplied_code, idempotency_key=None, account_id=None):
    code = normalize_invite_code(supplied_code)
    if not code:
        return {"code": None, "status": "NOT_REQUESTED", "message": "Không yêu cầu đổi mã mời."}
    
    # 1. Check durable persistent reservations
    res_key = f"{account_id or idempotency_key or 'default'}:{code}"
    reservations = _load_reservations()
    if res_key in reservations:
        prior = reservations[res_key]
        prior_status = prior.get("status")
        if prior_status == "REDEEMED":
            return {"code": code, "status": "REDEEMED", "message": "Mã mời đã được quy đổi thành công trước đó."}
        if prior_status == "REJECTED":
            return {"code": code, "status": "REJECTED", "message": "Mã mời đã bị từ chối trước đó; không gửi lại."}
        # If previously SUBMITTED, PENDING, or REVIEW_REQUIRED, do not resubmit across restart/new page
        return {"code": code, "status": "REVIEW_REQUIRED", "message": "Đã có yêu cầu gửi mã mời trước đó; sau restart/crash không tự động gửi lại. Cần kiểm tra thủ công."}
        
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
    
    # 2. Record durable reservation BEFORE click
    reservations[res_key] = {"status": "SUBMITTED", "code": code, "timestamp": time.time()}
    _save_reservations(reservations)
    
    pre_submit_body = (await page.inner_text("body")).lower()
    await submit.click()
    
    # 3. Fresh specific post-submit outcome check
    for _ in range(12):
        # A. Check alerts, toasts, dialogs for immediate feedback
        alerts = page.locator('[role="alert"], dialog [role="alert"], dialog, .alert, [class*="error"], [class*="toast"]')
        alert_text = ""
        try:
            for item in await alerts.all():
                if await item.is_visible():
                    alert_text += " " + (await item.inner_text())
        except Exception:
            pass
        alert_lower = alert_text.lower()
        
        # B. Check for rejection signals (prioritized)
        if redemption_outcome(alert_lower) == "REJECTED":
            reservations[res_key] = {"status": "REJECTED", "code": code, "timestamp": time.time()}
            _save_reservations(reservations)
            return {"code": code, "status": "REJECTED", "message": "Muse từ chối mã mời hoặc mã không hợp lệ; kiểm tra thông báo trong cửa sổ."}
            
        current_body = (await page.inner_text("body")).lower()
        if redemption_outcome(current_body) == "REJECTED":
            reservations[res_key] = {"status": "REJECTED", "code": code, "timestamp": time.time()}
            _save_reservations(reservations)
            return {"code": code, "status": "REJECTED", "message": "Muse từ chối mã mời; thông báo lỗi xuất hiện trên màn hình."}
            
        # C. Check for success ONLY if it is newly appeared or in alert
        if redemption_outcome(alert_lower) == "REDEEMED":
            reservations[res_key] = {"status": "REDEEMED", "code": code, "timestamp": time.time()}
            _save_reservations(reservations)
            return {"code": code, "status": "REDEEMED", "message": "Muse xác nhận đổi mã mời thành công."}
            
        if redemption_outcome(current_body) == "REDEEMED" and ("successfully redeemed" not in pre_submit_body):
            reservations[res_key] = {"status": "REDEEMED", "code": code, "timestamp": time.time()}
            _save_reservations(reservations)
            return {"code": code, "status": "REDEEMED", "message": "Muse xác nhận đổi mã mời thành công."}
            
        await asyncio.sleep(1)
        
    reservations[res_key] = {"status": "REVIEW_REQUIRED", "code": code, "timestamp": time.time()}
    _save_reservations(reservations)
    return {"code": code, "status": "REVIEW_REQUIRED", "message": "Đã gửi mã mời nhưng chưa nhận diện được thông báo xác nhận từ Muse. Cần kiểm tra thủ công, không tự động gửi lại."}

