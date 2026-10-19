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


import tempfile

def _run_cli(args, timeout=15):
    with tempfile.TemporaryFile(mode="w+t", encoding="utf-8", errors="replace") as f:
        try:
            p = subprocess.run(args, stdout=f, stderr=f, timeout=timeout)
            f.seek(0)
            return p.returncode, f.read()
        except subprocess.TimeoutExpired:
            return -1, "TimeoutExpired"
        except Exception as e:
            return -1, str(e)


def connect_free_us():
    cli = cli_path()
    if not cli:
        return {"ok": False, "error": "Chưa tìm thấy ứng dụng Windscribe chính thức trên máy."}
    with _lock:
        try:
            code, out = _run_cli([cli, "status"], timeout=10)
            text = out.lower()
            if "unknown error" in text or "lỗi không xác định" in text:
                return {"ok": False, "error": "Ứng dụng Windscribe trên máy đang báo lỗi API hoặc chưa đăng nhập. Vui lòng mở Windscribe đăng nhập hoặc dùng Psiphon."}
            if "logged out" in text or "đăng xuất" in text or "chưa đăng nhập" in text:
                return {"ok": False, "error": "Windscribe chưa đăng nhập. Cần đăng nhập tài khoản Free một lần trên ứng dụng Windows trước khi tool tự kết nối."}
            # A normal US location uses the current account plan. No subscription,
            # upgrade, static-IP, purchase, or Pro-only rotation command is issued.
            code, connect_out = _run_cli([cli, "connect", "US"], timeout=30)
            connect_text = connect_out.lower()
            if code != 0 or "chưa đăng nhập" in connect_text or "logged out" in connect_text:
                return {"ok": False, "error": "Windscribe chưa kết nối được máy chủ US của gói hiện tại (chưa đăng nhập hoặc vị trí bận). Vui lòng kiểm tra app Windscribe hoặc dùng Psiphon."}
            code, verified_out = _run_cli([cli, "status"], timeout=10)
            status_text = verified_out.lower()
            if not any(term in status_text for term in ("connect state: connected", "trạng thái kết nối: đã kết nối", "trạng thái kết nối: kết nối")):
                return {"ok": False, "error": "Windscribe chưa xác nhận đã kết nối; không dùng mã thoát CLI để suy ra thành công."}
            route = system_route()
            country_code = (route.get("countryCode") or "").upper() if route else ""
            if not route or country_code not in ("US", "CA"):
                return {"ok": False, "error": "Chưa xác minh được IP Mỹ/Canada qua Windscribe; không tiếp tục đăng ký."}
            is_us = (country_code == "US")
            is_ca = (country_code == "CA")
            return {"ok": True, "is_us": is_us, "is_ca": is_ca, "data": route, "proxy": None, "provider": "windscribe", "networkMode": "system"}
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "Windscribe quá thời gian kết nối. Chưa đăng ký thêm tài khoản."}
        except OSError:
            return {"ok": False, "error": "Không gọi được Windscribe CLI chính thức."}
