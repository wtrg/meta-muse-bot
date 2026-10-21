"""Redeem the supplied referral code through the authenticated settings UI."""
import asyncio
import json
import os
import re
import time
from urllib.parse import urlparse

import sqlite3
from typing import Dict, Any, Optional

RESERVATIONS_FILE = os.path.join(os.path.dirname(__file__), "invite_reservations.json")

_RESERVATIONS_LOCK = asyncio.Lock()
_IN_FLIGHT_KEYS = set()


def _get_db(db_path: str) -> sqlite3.Connection:
    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=15.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reservations (
                res_key TEXT PRIMARY KEY,
                account_id TEXT,
                code TEXT,
                status TEXT,
                timestamp REAL
            )
        """)
        return conn
    except Exception:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        raise


def _try_migrate_legacy_json(file_path: str):
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        return
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return
    except Exception:
        return

    # Transactional migration: build replacement DB in temporary file first
    temp_db = file_path + ".migration.tmp"
    if os.path.exists(temp_db):
        try:
            os.remove(temp_db)
        except Exception:
            pass

    conn = None
    try:
        conn = _get_db(temp_db)
        with conn:
            for k, v in data.items():
                if isinstance(v, dict):
                    conn.execute(
                        "INSERT OR REPLACE INTO reservations (res_key, account_id, code, status, timestamp) VALUES (?, ?, ?, ?, ?)",
                        (k, v.get("account_id", ""), v.get("code", ""), v.get("status", "SUBMITTED"), v.get("timestamp", time.time()))
                    )
                else:
                    conn.execute(
                        "INSERT OR REPLACE INTO reservations (res_key, account_id, code, status, timestamp) VALUES (?, ?, ?, ?, ?)",
                        (k, "", "", str(v), time.time())
                    )
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass

    # Fully built replacement DB; safely backup legacy JSON and atomically swap
    backup_path = file_path + ".legacy.json"
    try:
        import shutil
        shutil.copy2(file_path, backup_path)
    except Exception:
        pass
    os.replace(temp_db, file_path)


def _load_reservations() -> Dict[str, Dict[str, Any]]:
    backup_path = RESERVATIONS_FILE + ".legacy.json"
    if not os.path.exists(RESERVATIONS_FILE):
        if os.path.exists(backup_path):
            try:
                import shutil
                shutil.copy2(backup_path, RESERVATIONS_FILE)
            except Exception:
                raise RuntimeError(f"INTERRUPTED_MIGRATION: Backup {backup_path} exists but cannot restore {RESERVATIONS_FILE}")
        else:
            return {}
    if os.path.getsize(RESERVATIONS_FILE) == 0:
        return {}

    _try_migrate_legacy_json(RESERVATIONS_FILE)

    conn = None
    try:
        conn = _get_db(RESERVATIONS_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT res_key, status, code, timestamp, account_id FROM reservations")
        rows = cursor.fetchall()
        return {r[0]: {"status": r[1], "code": r[2], "timestamp": r[3], "account_id": r[4]} for r in rows}
    except Exception as e:
        raise RuntimeError(f"CORRUPT_STORAGE: Cannot load reservations from {RESERVATIONS_FILE}: {e}")
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def _save_reservation(res_key: str, status: str, code: str, account_id: Optional[str] = None) -> bool:
    if os.path.exists(RESERVATIONS_FILE) and os.path.getsize(RESERVATIONS_FILE) > 0:
        _try_migrate_legacy_json(RESERVATIONS_FILE)
    conn = None
    try:
        conn = _get_db(RESERVATIONS_FILE)
        with conn:
            conn.execute(
                "INSERT OR REPLACE INTO reservations (res_key, account_id, code, status, timestamp) VALUES (?, ?, ?, ?, ?)",
                (res_key, account_id or "", code, status, time.time())
            )
        return True
    except Exception:
        return False
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def _save_reservations(data: Dict[str, Any]) -> bool:
    ok = True
    for k, v in data.items():
        if isinstance(v, dict):
            if not _save_reservation(k, v.get("status", "SUBMITTED"), v.get("code", ""), v.get("account_id")):
                ok = False
        else:
            if not _save_reservation(k, str(v), ""):
                ok = False
    return ok



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
    if re.search(r"(code|invite|token).{0,80}(successfully redeemed|redeemed successfully)|successfully redeemed|redeemed successfully|mã.{0,60}(thành công|đã được quy đổi)", text):
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
    
    # 1. Check durable persistent reservations and avoid simultaneous in-flight submissions
    res_key = f"{account_id or idempotency_key or 'default'}:{code}"
    async with _RESERVATIONS_LOCK:
        if res_key in _IN_FLIGHT_KEYS:
            return {"code": code, "status": "REVIEW_REQUIRED", "message": "Đang có tiến trình đổi mã mời song song cho tài khoản này; ngăn chặn gửi trùng lặp."}
        _IN_FLIGHT_KEYS.add(res_key)

    try:
        try:
            reservations = _load_reservations()
        except Exception as err:
            return {"code": code, "status": "REVIEW_REQUIRED", "message": f"Dữ liệu đặt trước mã mời không thể đọc an toàn hoặc bị lỗi ({err}). Dừng để tránh gửi lại."}
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
        
        # 2. Record durable reservation BEFORE click; fail closed if write fails
        if not _save_reservation(res_key, "SUBMITTED", code, account_id):
            return {"code": code, "status": "REVIEW_REQUIRED", "message": "Không thể ghi nhận trạng thái đặt trước mã mời bền vững vào bộ nhớ lưu trữ."}
        
        # Capture pre-submit state to prevent stale alert false-positives
        pre_submit_body = (await page.inner_text("body")).lower()
        pre_alerts = set()
        alerts_pre = page.locator('[role="alert"], dialog [role="alert"], dialog, .alert, [class*="error"], [class*="toast"]')
        try:
            for item in await alerts_pre.all():
                if await item.is_visible():
                    txt = (await item.inner_text()).strip().lower()
                    if txt:
                        pre_alerts.add(txt)
        except Exception:
            pass

        await submit.click()
        
        # 3. Fresh specific post-submit outcome check
        for _ in range(12):
            # A. Check alerts, toasts, dialogs for immediate feedback
            alerts = page.locator('[role="alert"], dialog [role="alert"], dialog, .alert, [class*="error"], [class*="toast"]')
            try:
                alert_items = await alerts.all()
            except Exception:
                alert_items = []
                
            for item in alert_items:
                try:
                    if not await item.is_visible():
                        continue
                    txt = (await item.inner_text()).strip()
                    if not txt:
                        continue
                    lower_txt = txt.lower()
                    if lower_txt in pre_alerts:
                        continue
                    
                    outcome = redemption_outcome(lower_txt)
                    if outcome == "REJECTED":
                        _save_reservation(res_key, "REJECTED", code, account_id)
                        return {"code": code, "status": "REJECTED", "message": "Muse từ chối mã mời hoặc mã không hợp lệ; kiểm tra thông báo trong cửa sổ."}
                    elif outcome == "REDEEMED":
                        _save_reservation(res_key, "REDEEMED", code, account_id)
                        return {"code": code, "status": "REDEEMED", "message": "Muse xác nhận đổi mã mời thành công."}
                except Exception:
                    continue

            # B. Check body only if newly changed from pre-submit
            current_body = (await page.inner_text("body")).lower()
            if current_body != pre_submit_body:
                body_outcome = redemption_outcome(current_body)
                pre_body_outcome = redemption_outcome(pre_submit_body)
                if body_outcome == "REJECTED" and pre_body_outcome != "REJECTED":
                    _save_reservation(res_key, "REJECTED", code, account_id)
                    return {"code": code, "status": "REJECTED", "message": "Muse từ chối mã mời; thông báo lỗi xuất hiện trên màn hình."}
                if body_outcome == "REDEEMED" and pre_body_outcome != "REDEEMED":
                    _save_reservation(res_key, "REDEEMED", code, account_id)
                    return {"code": code, "status": "REDEEMED", "message": "Muse xác nhận đổi mã mời thành công."}
                
            await asyncio.sleep(1)
            
        _save_reservation(res_key, "REVIEW_REQUIRED", code, account_id)
        return {"code": code, "status": "REVIEW_REQUIRED", "message": "Đã gửi mã mời nhưng chưa nhận diện được thông báo xác nhận từ Muse. Cần kiểm tra thủ công, không tự động gửi lại."}
    finally:
        async with _RESERVATIONS_LOCK:
            _IN_FLIGHT_KEYS.discard(res_key)

