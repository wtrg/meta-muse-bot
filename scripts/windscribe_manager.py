"""Use the official Windows CLI with the account's existing free plan."""
import json
import os
import subprocess
import threading
from pathlib import Path

_lock = threading.Lock()


def cli_path():
    for folder in (os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")):
        path = Path(folder) / "Windscribe" / "windscribe-cli.exe"
        if path.is_file():
            return str(path)
    return None


def system_route():
    try:
        response = subprocess.run(
            ["curl.exe", "-fsS", "--max-time", "8", "--noproxy", "*", "https://ipwho.is/"],
            capture_output=True, text=True, timeout=10,
        )
        info = json.loads(response.stdout)
        if response.returncode or info.get("success") is not True:
            return None
        return {"countryCode": info.get("country_code"), "country": info.get("country"),
                "city": info.get("city"), "query": info.get("ip"),
                "isp": info.get("connection", {}).get("isp", "")}
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


def connect_free_us():
    cli = cli_path()
    if not cli:
        return {"ok": False, "error": "Chưa tìm thấy ứng dụng Windscribe chính thức trên máy."}
    with _lock:
        try:
            state = subprocess.run([cli, "status"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15)
            text = state.stdout.lower()
            if "unknown error" in text or "lỗi không xác định" in text:
                return {"ok": False, "error": "Ứng dụng Windscribe đang báo lỗi API/đăng nhập. Chưa tiếp tục đăng ký Muse."}
            if "logged out" in text or "đăng xuất" in text:
                return {"ok": False, "error": "Windscribe chưa đăng nhập. Cần đăng nhập tài khoản Free một lần trước khi tool tự kết nối."}
            # A normal US location uses the current account plan. No subscription,
            # upgrade, static-IP, purchase, or Pro-only rotation command is issued.
            result = subprocess.run([cli, "connect", "US"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
            if result.returncode:
                return {"ok": False, "error": "Windscribe chưa kết nối được máy chủ US của gói hiện tại. Không tự nâng cấp hay thanh toán."}
            verified = subprocess.run([cli, "status"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15)
            status_text = verified.stdout.lower()
            if not any(term in status_text for term in ("connect state: connected", "trạng thái kết nối: đã kết nối", "trạng thái kết nối: kết nối")):
                return {"ok": False, "error": "Windscribe chưa xác nhận đã kết nối; không dùng mã thoát CLI để suy ra thành công."}
            route = system_route()
            if not route or route.get("countryCode") not in ("US", "CA"):
                return {"ok": False, "error": "Chưa xác minh được IP Mỹ/Canada qua Windscribe; không tiếp tục đăng ký."}
            return {"ok": True, "is_us": True, "data": route, "proxy": None, "provider": "windscribe", "networkMode": "system"}
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "Windscribe quá thời gian kết nối. Chưa đăng ký thêm tài khoản."}
        except OSError:
            return {"ok": False, "error": "Không gọi được Windscribe CLI chính thức."}
