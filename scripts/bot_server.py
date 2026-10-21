import os
import sys
import time
import json
import asyncio
from contextlib import asynccontextmanager
import csv
import subprocess
import urllib.request
import urllib.parse
import re
import ipaddress
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import hashlib
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, field_validator
from playwright.async_api import async_playwright
from muse_browser import open_muse_browser, get_preferred_browser_channel
from muse_access import inspect_muse_access, MuseAccessError
from muse_invites import normalize_invite_code, redeem_invite
from windscribe_manager import connect_free_us, system_route
from playwright.sync_api import sync_playwright

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

sys.path.append(os.path.dirname(__file__))
try:
    from psiphon_manager import start_psiphon_tunnel, stop_psiphon_tunnel, is_psiphon_alive
except Exception:
    try:
        from scripts.psiphon_manager import start_psiphon_tunnel, stop_psiphon_tunnel, is_psiphon_alive
    except Exception:
        pass

# G1 Standardized Error Codes
PROVIDER_INVALID = "PROVIDER_INVALID"
PROXY_NOT_CONFIGURED = "PROXY_NOT_CONFIGURED"
PROXY_NOT_REACHABLE = "PROXY_NOT_REACHABLE"
IP_SERVICE_BAD_RESPONSE = "IP_SERVICE_BAD_RESPONSE"
ROUTE_COUNTRY_UNKNOWN = "ROUTE_COUNTRY_UNKNOWN"
ROUTE_COUNTRY_OTHER = "ROUTE_COUNTRY_OTHER"
ROUTE_DISCONNECTED = "ROUTE_DISCONNECTED"
NETWORK_INCONCLUSIVE = "NETWORK_INCONCLUSIVE"
ROUTE_MISMATCH = "ROUTE_MISMATCH"
BROWSER_ROUTE_UNVERIFIED = "BROWSER_ROUTE_UNVERIFIED"
NETWORK_PRECHECK_FAILED = "NETWORK_PRECHECK_FAILED"

@dataclass
class RouteSpec:
    provider: str  # psiphon | windscribe | vpn | custom | auto
    mode: str      # proxy | system
    proxy_config: Optional[Dict[str, str]] = None
    local_proxy_endpoint: Optional[str] = None
    tunnel_process_identity: Optional[str] = None
    selected_at_utc: str = ""
    route_state: str = "UNVERIFIED"  # UNVERIFIED | VERIFIED | EXPIRED | DISCONNECTED
    verification: Optional[Dict[str, Any]] = None
    eligibility_state: str = "UNKNOWN"  # UNKNOWN | CONFIRMED_BY_PROVIDER | RESTRICTED_BY_PROVIDER
    verified_at_utc: Optional[str] = None
    ttl_seconds: int = 45
    verified_ip: Optional[str] = None
    verified_country: Optional[str] = None

SERVER_STARTED_AT_UTC = datetime.now(timezone.utc).isoformat()
NETWORK_REVISION = "MUSE-GEO-001-G0-G5"

def _compute_source_fingerprint(scripts_dir: Optional[str] = None) -> str:
    s_dir = scripts_dir or os.path.dirname(os.path.abspath(__file__))
    h = hashlib.sha256()
    try:
        critical_files = sorted(["bot_server.py", "muse_invites.py", "muse_access.py", "muse_browser.py"])
        found = False
        for fname in critical_files:
            fpath = os.path.join(s_dir, fname)
            if os.path.exists(fpath):
                found = True
                with open(fpath, "rb") as f:
                    h.update(fname.encode("utf-8"))
                    h.update(f.read())
        return h.hexdigest()[:16] if found else "UNKNOWN_FINGERPRINT"
    except Exception:
        return "UNKNOWN_FINGERPRINT"

def _compute_loaded_identity(repo_dir: Optional[str] = None) -> Dict[str, Any]:
    cwd = repo_dir or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    build_sha = "UNKNOWN_SHA"
    worktree_dirty = False
    worktree_patch_digest = "CLEAN"
    
    try:
        proc_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5)
        if proc_sha.returncode == 0 and proc_sha.stdout.strip():
            build_sha = proc_sha.stdout.strip()
            
        proc_status = subprocess.run(["git", "status", "--porcelain"], cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5)
        if proc_status.returncode == 0:
            status_out = proc_status.stdout.strip()
            worktree_dirty = bool(status_out)
            if worktree_dirty:
                proc_diff = subprocess.run(["git", "diff"], cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5)
                if proc_diff.returncode == 0:
                    worktree_patch_digest = hashlib.sha256(proc_diff.stdout.encode("utf-8")).hexdigest()[:16]
                else:
                    worktree_patch_digest = "DIRTY_UNHASHED"
    except Exception as e:
        worktree_patch_digest = f"GIT_ERROR_{type(e).__name__}"

    scripts_dir = os.path.join(cwd, "scripts") if os.path.exists(os.path.join(cwd, "scripts")) else os.path.dirname(os.path.abspath(__file__))
    source_fp = _compute_source_fingerprint(scripts_dir)

    return {
        "ok": True,
        "build_sha": build_sha,
        "worktree_dirty": worktree_dirty,
        "worktree_patch_digest": worktree_patch_digest,
        "source_fingerprint": source_fp,
        "pid": os.getpid(),
        "python_executable": sys.executable,
        "port": int(os.environ.get("BOT_SERVER_PORT", "8790")),
        "started_at_utc": SERVER_STARTED_AT_UTC,
        "network_revision": NETWORK_REVISION,
    }

# Startup-frozen immutable runtime identity (prevents stale resident processes reporting unexecuted disk git state)
SERVER_LOADED_IDENTITY = _compute_loaded_identity()

def get_git_runtime_identity(repo_dir: Optional[str] = None) -> Dict[str, Any]:
    if repo_dir:
        return _compute_loaded_identity(repo_dir)
    return dict(SERVER_LOADED_IDENTITY)

def evaluate_runtime_handshake(
    response_payload: Optional[Dict[str, Any]],
    error: Optional[Exception] = None,
    expected_revision: Optional[str] = NETWORK_REVISION,
    expected_sha: Optional[str] = None,
    expected_fingerprint: Optional[str] = None,
) -> str:
    """Evaluates the runtime handshake on port 8790.
    Returns:
      'VALID_RUNTIME' - port is running the expected Bot Server daemon with matching revision/source
      'STALE_PROCESS' - port is responding to HTTP but missing runtime metadata or revision mismatch
      'PORT_OCCUPIED_NOT_OWNED' - port is occupied by an alien/non-HTTP process
    """
    if error is not None or response_payload is None or not isinstance(response_payload, dict):
        return "PORT_OCCUPIED_NOT_OWNED"
    if not (response_payload.get("ok") and response_payload.get("build_sha")):
        return "STALE_PROCESS"
    if expected_revision and response_payload.get("network_revision") != expected_revision:
        return "STALE_PROCESS"
    if expected_sha and response_payload.get("build_sha") != expected_sha:
        return "STALE_PROCESS"
    source_fp = response_payload.get("source_fingerprint")
    if not source_fp or source_fp == "UNKNOWN_FINGERPRINT":
        return "STALE_PROCESS"
    if expected_fingerprint and source_fp != expected_fingerprint:
        return "STALE_PROCESS"
    return "VALID_RUNTIME"

def normalize_proxy(raw: Optional[str]) -> Optional[str]:
    if not raw or not raw.strip():
        return None
    raw = raw.strip()
    parts = raw.split(":")
    if len(parts) == 4 and not raw.startswith("http") and not raw.startswith("socks"):
        host, port, user, pwd = parts
        return f"http://{user}:{pwd}@{host}:{port}"
    if not (raw.startswith("http://") or raw.startswith("https://") or raw.startswith("socks5://") or raw.startswith("socks4://")):
        return f"http://{raw}"
    return raw

def to_playwright_proxy(raw: Optional[str]) -> Optional[Dict[str, str]]:
    norm = normalize_proxy(raw)
    if not norm:
        return None
    p = urllib.parse.urlparse(norm)
    cfg = {"server": f"{p.scheme}://{p.hostname}:{p.port}"}
    if p.username:
        cfg["username"] = p.username
    if p.password:
        cfg["password"] = p.password
    return cfg

def check_route_ip(proxy_str: Optional[str] = None) -> Dict[str, Any]:
    norm = normalize_proxy(proxy_str)
    endpoints = [
        ("https://ipwho.is/", True),
        ("https://ipapi.co/json/", False),
    ]
    last_err = "Không thể kết nối qua proxy"
    for url, is_ipwho in endpoints:
        cmd = ["curl.exe", "-4", "-s", "--max-time", "8"]
        if norm:
            cmd.extend(["-x", norm])
        cmd.append(url)
        
        start_t = time.time()
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            dur = round(time.time() - start_t, 2)
            if proc.returncode != 0 or not proc.stdout.strip():
                last_err = f"Không thể kết nối qua proxy: {proc.stderr.strip() or 'Timeout/Connection error'}"
                continue
                
            try:
                data = json.loads(proc.stdout.strip())
            except Exception as json_err:
                last_err = f"Dữ liệu phản hồi tuyến mạng không đúng định dạng JSON: {json_err}"
                continue
                
            if is_ipwho:
                has_bool_success = (data.get("success") is True)
                has_status_success = (data.get("status") == "success")
                if not (has_bool_success or has_status_success) or data.get("success") is False or data.get("status") == "fail":
                    last_err = f"Kiểm tra tuyến mạng thất bại: {data.get('message', 'Thiếu tín hiệu thành công hợp lệ từ dịch vụ mạng')}"
                    continue
            else:
                if "error" in data or data.get("reason") or data.get("status") == "fail" or data.get("success") is False:
                    last_err = f"Kiểm tra tuyến mạng thất bại: {data.get('message') or data.get('reason') or data.get('error', 'Lỗi dịch vụ')}"
                    continue
            
            country_code = (data.get("country_code") or data.get("countryCode") or "").upper()
            ip_query = data.get("ip") or data.get("query")
            if not ip_query:
                last_err = "Kiểm tra tuyến mạng thất bại: Dữ liệu phản hồi thiếu thông tin địa chỉ IP."
                continue
                
            try:
                ipaddress.ip_address(ip_query)
            except Exception:
                last_err = f"Địa chỉ IP không hợp lệ: {ip_query}"
                continue
                
            if not country_code or len(country_code) != 2 or not country_code.isalpha():
                last_err = f"Dữ liệu phản hồi thiếu thông tin quốc gia hoặc mã quốc gia không hợp lệ: {country_code}"
                continue

            
            data["ping"] = dur
            data["query"] = ip_query
            data["countryCode"] = country_code
            is_us = (country_code == "US")
            is_ca = (country_code == "CA")
            
            has_asn = "hosting" in data or "proxy" in data
            is_hosting = data.get("hosting", False)
            is_proxy = data.get("proxy", False)
            
            if is_us:
                if is_hosting or is_proxy:
                    verdict = "US_DATACENTER"
                    verdict_text = f"⚠️ IP Hoa Kỳ ({data.get('isp', 'Unknown')}) nhưng là Datacenter/Proxy ASN. Rủi ro bị Meta đưa vào Danh Sách Chờ!"
                elif has_asn and (data.get("hosting") is False and data.get("proxy") is False):
                    verdict = "US_RESIDENTIAL"
                    verdict_text = f"✅ IP Hoa Kỳ ({data.get('isp', 'Unknown')}, {data.get('city', '')}). Residential ASN."
                else:
                    verdict = "US_ROUTE"
                    verdict_text = f"ℹ️ IP Hoa Kỳ ({data.get('isp', 'Unknown')}, {data.get('city', '')}). Tuyến mạng US (chưa xác định loại ASN)."
            elif is_ca:
                verdict = "CA_ROUTE"
                verdict_text = f"ℹ️ IP Canada ({data.get('isp', 'Unknown')}, {data.get('city', '')}). Vùng Canada tách biệt với US."
            else:
                verdict = "NON_US"
                verdict_text = f"❌ Địa chỉ IP thuộc {data.get('country', country_code)} ({country_code}). Meta Muse có thể hạn chế quyền truy cập!"
                
            return {
                "ok": True,
                "data": data,
                "is_us": is_us,
                "is_ca": is_ca,
                "country_code": country_code,
                "verdict": verdict,
                "verdict_text": verdict_text
            }
        except Exception as e:
            last_err = f"Lỗi kiểm tra tuyến mạng: {e}"
            continue

    return {"ok": False, "error": last_err}


BACKEND_URL = os.environ.get("BACKEND_URL", "http://127.0.0.1:8787")
ACCOUNTS_FILE = os.path.join(os.path.dirname(__file__), "muse_accounts.json")
SCREENSHOTS_DIR = os.path.join(os.path.dirname(__file__), "screenshots")
EXPORTS_DIR = os.path.join(os.path.dirname(__file__), "exports")
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
os.makedirs(EXPORTS_DIR, exist_ok=True)

MTEMP_API_KEY = "pub_nRn1hUwpdmZvxQNVWDfoXgKyF7dIm9nRIIIt1qDw"
MTEMP_BASE_URL = "https://mtempmail.com/api"

@asynccontextmanager
async def bot_lifespan(app):
    try:
        yield
    finally:
        await asyncio.to_thread(stop_psiphon_tunnel)

app = FastAPI(title="Muse.ai Account Bot", lifespan=bot_lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ALLOWED_BOT_HOSTS = {"127.0.0.1", "localhost", "::1"}
TRUSTED_ORIGINS = {"http://127.0.0.1:5173", "http://localhost:5173"}

def extract_host(host_header: str) -> str:
    host_header = (host_header or "").strip()
    if host_header.startswith("["):
        bracket_end = host_header.find("]")
        if bracket_end != -1:
            return host_header[1:bracket_end].lower()
    return host_header.split(":")[0].strip().lower()

@app.middleware("http")
async def local_bot_security_guard(request, call_next):
    if request.url.path.startswith("/api/bot"):
        # 1. Host header validation
        host_header = request.headers.get("host", "")
        host_name = extract_host(host_header)
        if not host_name or host_name not in ALLOWED_BOT_HOSTS:
            return JSONResponse({"detail": "Host header is not allowed for local bot controls."}, status_code=403)

        # 2. Strict Origin enforcement: only exact trusted origins allowed
        origin = request.headers.get("origin")
        if origin:
            clean_origin = origin.rstrip("/")
            if clean_origin not in TRUSTED_ORIGINS:
                return JSONResponse({"detail": "Untrusted origin for local-only bot controls."}, status_code=403)
    return await call_next(request)


class BotState:
    is_running: bool = False
    stop_requested: bool = False
    current_step: str = "Sẵn sàng"
    logs: List[Dict[str, Any]] = []
    accounts: List[Dict[str, Any]] = []
    session_accounts: List[Dict[str, Any]] = []
    session_id: str = ""
    session_time: str = ""

state = BotState()

if os.path.exists(ACCOUNTS_FILE):
    try:
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            state.accounts = json.load(f)
    except Exception:
        state.accounts = []
state.session_accounts = []
state.session_id = ""
state.session_time = ""

def get_public_tunnel_url() -> str:
    env_url = os.environ.get("PUBLIC_TUNNEL_URL", "").strip()
    if env_url:
        return env_url.rstrip("/")
    tunnel_file = os.path.join(os.path.dirname(__file__), "active_tunnel_url.txt")
    if os.path.exists(tunnel_file):
        try:
            with open(tunnel_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content.startswith("http"):
                    return content.rstrip("/")
        except Exception:
            pass
    return "http://127.0.0.1:5173"

def save_accounts_txt():
    tunnel_url = get_public_tunnel_url()
    txt_path = os.path.join(os.path.dirname(__file__), "muse_accounts.txt")
    root_txt_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "muse_accounts.txt")
    
    ready_accounts = [a for a in state.accounts if a.get("status") == "SUCCESS_CHAT_READY"]
    failed_accounts = [a for a in state.accounts if a.get("status") != "SUCCESS_CHAT_READY"]
    
    lines = [
        "================================================================================",
        "DANH SÁCH TÀI KHOẢN MUSE.AI & MÃ PIN LẤY OTP ĐĂNG NHẬP (CHAT SẴN SÀNG)",
        f"Trang Lấy OTP Trực Tuyến: {tunnel_url}/otp",
        "================================================================================",
        ""
    ]
    
    if not ready_accounts:
        lines.append("CHƯA CÓ TÀI KHOẢN NÀO ĐẠT TRẠNG THÁI 'CHAT SẴN SÀNG'.")
        lines.append("Lưu ý: Các tài khoản tạo trước đó bị Meta đưa vào Danh Sách Chờ (Waitlist do IP).")
        lines.append("Hãy bật VPN USA hoặc nhập Proxy US Dân Cư Sạch để tạo tài khoản mới.")
        lines.append("")
    else:
        for idx, acc in enumerate(ready_accounts, 1):
            email = acc.get("email", "")
            pin = acc.get("pin", "") or ""
            otp_link = f"{tunnel_url}/otp?email={urllib.parse.quote(email)}"
            proxy = acc.get("proxy_used", "Không dùng")
            lines.append(f"[{idx}] TÀI KHOẢN: {email}")
            lines.append(f"  • Email đăng nhập: {email}")
            lines.append(f"  • Mã PIN xem OTP : {pin}")
            lines.append(f"  • Link lấy OTP   : {otp_link}")
            lines.append(f"  • Trạng thái     : CHAT SẴN SÀNG (ĐÃ VÀO TRỰC TIẾP MUSE)")
            lines.append(f"  • Proxy đã tạo   : {proxy}")
            lines.append(f"  • Thời gian tạo  : {acc.get('createdAt', '')}")
            lines.append("  ------------------------------------------------------------------------------")
            
        lines.append("")
        lines.append("================================================================================")
        lines.append("HƯỚNG DẪN ĐĂNG NHẬP DÀNH CHO KHÁCH HÀNG:")
        lines.append("Bước 1: Truy cập https://muse.ai (qua VPN USA nếu cần)")
        lines.append("Bước 2: Điền địa chỉ Email của tài khoản ở trên")
        lines.append("Bước 3: Mở Link lấy OTP tương ứng ở trên để nhận mã 6 chữ số từ Meta")
        lines.append("Bước 4: Nhập mã OTP vào Muse.ai để vào thẳng màn hình Chat!")
        lines.append("================================================================================")
        lines.append("")
        lines.append("DANH SÁCH ĐỊNH DẠNG RÚT GỌN (DÙNG ĐỂ IMPORT / LƯU TRỮ):")
        for acc in ready_accounts:
            email = acc.get("email", "")
            pin = acc.get("pin", "") or ""
            otp_link = f"{tunnel_url}/otp?email={urllib.parse.quote(email)}"
            lines.append(f"{email}|{pin}|{otp_link}")
            
    if failed_accounts:
        lines.append("")
        lines.append("================================================================================")
        lines.append(f"LỊCH SỬ TÀI KHOẢN BỊ META ĐƯA VÀO DANH SÁCH CHỜ (WAITLIST): {len(failed_accounts)} TÀI KHOẢN")
        lines.append("(Các tài khoản này bị Meta gắn nhãn Waitlist do IP tạo không đạt chuẩn US)")
        lines.append("================================================================================")
        for idx, acc in enumerate(failed_accounts, 1):
            lines.append(f"• {acc.get('email')} | Proxy: {acc.get('proxy_used')} | Trạng thái: {acc.get('status')}")

    content = "\n".join(lines)
    try:
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(content)
        with open(root_txt_path, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        print("Error saving txt:", e)

def save_accounts():
    try:
        with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
            json.dump(state.accounts, f, ensure_ascii=False, indent=2)
        save_accounts_txt()
    except Exception as e:
        print(f"Error saving accounts: {e}")

def save_session_csv_and_excel(session_accounts: List[Dict[str, Any]], session_id: str):
    if not session_id:
        session_id = time.strftime("%Y%m%d_%H%M%S")
    tunnel_url = get_public_tunnel_url()
    
    # 4 cột đúng chuẩn yêu cầu người dùng:
    # Cột 1: STT
    # Cột 2: Email
    # Cột 3: Mã PIN
    # Cột 4: Trang Web Lấy OTP Đăng Nhập
    headers = ["STT", "Email", "Mã PIN", "Trang Web Lấy OTP Đăng Nhập"]
    rows = []
    for idx, acc in enumerate(session_accounts, 1):
        email = acc.get("email", "")
        pin = acc.get("pin", "") or ""
        otp_link = f"{tunnel_url}/otp?email={urllib.parse.quote(email)}"
        rows.append([idx, email, pin, otp_link])
        
    csv_filename = f"muse_session_{session_id}.csv"
    excel_filename = f"muse_session_{session_id}.xlsx"
    
    session_csv_path = os.path.join(EXPORTS_DIR, csv_filename)
    session_excel_path = os.path.join(EXPORTS_DIR, excel_filename)
    
    latest_csv_path = os.path.join(EXPORTS_DIR, "muse_session_latest.csv")
    latest_excel_path = os.path.join(EXPORTS_DIR, "muse_session_latest.xlsx")
    
    root_latest_csv = os.path.join(os.path.dirname(os.path.dirname(__file__)), "muse_session_latest.csv")
    root_latest_excel = os.path.join(os.path.dirname(os.path.dirname(__file__)), "muse_session_latest.xlsx")
    
    # Ghi File CSV kèm UTF-8 BOM (\ufeff / utf-8-sig) để Excel mở không lỗi font
    try:
        for p in [session_csv_path, latest_csv_path, root_latest_csv]:
            with open(p, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                writer.writerows(rows)
    except Exception as e:
        print("Error writing CSV session:", e)
        
    # Ghi File Excel (.xlsx) chuẩn openpyxl
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
        
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Muse Accounts"
        
        header_fill = PatternFill(start_color="10B981", end_color="10B981", fill_type="solid")
        header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
        center_align = Alignment(horizontal="center", vertical="center")
        left_align = Alignment(horizontal="left", vertical="center")
        
        ws.append(headers)
        for col_num in range(1, len(headers) + 1):
            cell = ws.cell(row=1, column=col_num)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = center_align
            
        for r_idx, row_data in enumerate(rows, start=2):
            ws.append(row_data)
            ws.cell(row=r_idx, column=1).alignment = center_align
            ws.cell(row=r_idx, column=2).alignment = left_align
            ws.cell(row=r_idx, column=3).alignment = center_align
            ws.cell(row=r_idx, column=4).alignment = left_align
            
        ws.column_dimensions['A'].width = 8
        ws.column_dimensions['B'].width = 34
        ws.column_dimensions['C'].width = 16
        ws.column_dimensions['D'].width = 85
        
        for p in [session_excel_path, latest_excel_path, root_latest_excel]:
            wb.save(p)
    except Exception as e:
        print("Error writing Excel session:", e)

def redact_sensitive(text: str) -> str:
    if not isinstance(text, str):
        return text
    # 1. Redact credentials in URLs: http://user:password@host -> http://user:***@host
    text = re.sub(r'(https?|socks5?|socks5h)://([^:\s/@]+):([^@\s/]+)@', r'\1://\2:***@', text)
    # 2. Redact OTP / PIN with labels: OTP: 123456, PIN: 123456
    text = re.sub(r'(?i)\b(otp|pin|code|mã\s*(?:xác\s*thực|otp)?)\s*[:=]\s*([a-zA-Z0-9]{4,8})\b', r'\1: ***', text)
    # 3. Redact secret / token / cookie
    text = re.sub(r'(?i)\b(password|passwd|secret|token|cookie)=([^\s&]+)', r'\1=***', text)
    # 4. Redact direct phrases: "MÃ OTP TỪ META: 123456"
    text = re.sub(r'(?i)(mã\s*otp\s*từ\s*meta:\s*)\d+', r'\1***', text)
    return text

def add_log(message: str, level: str = "info", progress: Optional[int] = None):
    safe_msg = redact_sensitive(message)
    entry = {
        "time": time.strftime("%H:%M:%S"),
        "message": safe_msg,
        "level": level,
        "progress": progress
    }
    state.logs.append(entry)
    if len(state.logs) > 500:
        state.logs = state.logs[-500:]
    state.current_step = safe_msg
    print(f"[{entry['time']}] [{level.upper()}] {safe_msg}")

class StartBotRequest(BaseModel):
    count: int = 1
    proxy: Optional[str] = None
    proxyType: Optional[str] = "psiphon"  # "psiphon", "vpn", "custom", "auto", "windscribe"
    visible: bool = True
    provider: str = "clean_tempmail"  # "clean_tempmail" or "spinupmail"
    domain: str = "maxxspace.com"
    inviteCode: Optional[str] = "P3FB4N"
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    birthYear: Optional[str] = None
    birthMonth: Optional[str] = None
    birthDay: Optional[str] = None

    @field_validator("proxyType")
    @classmethod
    def validate_proxy_type(cls, v):
        allowed = {"psiphon", "vpn", "custom", "auto", "windscribe"}
        if v is not None and v.strip().lower() not in allowed:
            raise ValueError(f"{PROVIDER_INVALID}: Unknown proxy provider: '{v}'. Must be one of {allowed}")
        return (v or "psiphon").strip().lower()

    @field_validator("count")
    @classmethod
    def validate_count(cls, v):
        if v <= 0:
            raise ValueError("Số lượng tài khoản phải lớn hơn 0")
        return v


async def create_clean_email() -> str:
    add_log("Đang tạo email tên miền sạch (ưu tiên fraudfindez.com / chuẩn Meta, loại bỏ hoàn toàn mtempmail)...", "info", 10)
    url = f"{MTEMP_BASE_URL}/emails/{MTEMP_API_KEY}"
    loop = asyncio.get_event_loop()
    def _fetch():
        for _ in range(30):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}, data=b"{}")
                with urllib.request.urlopen(req, timeout=12) as resp:
                    data = json.loads(resp.read().decode())
                    candidate = data.get("data", {}).get("email", "")
                    domain = candidate.split("@")[-1].lower() if "@" in candidate else ""
                    # Strictly reject any domain with 'temp' or 'mail', or non-global TLDs
                    if "temp" in domain or "mail" in domain or domain.endswith(".pl") or domain.endswith(".ru") or domain.endswith(".vn"):
                        continue
                    if domain.endswith(".com") or domain.endswith(".net") or domain.endswith(".org"):
                        return candidate
            except Exception:
                pass
            time.sleep(0.3)
        return ""
    email = await loop.run_in_executor(None, _fetch)
    if not email:
        raise Exception("Không tìm thấy email có tên miền sạch (đã loại bỏ mtempmail). Vui lòng thử lại sau giây lát.")
    add_log(f"Đã tạo email tên miền sạch: {email}", "success", 20)
    return email

async def poll_clean_otp(email: str, timeout_seconds: int = 75, route_spec: Optional[RouteSpec] = None) -> str:
    add_log("Đang chờ Meta gửi mã OTP xác thực...", "info", 50)
    start = time.time()
    url = f"{MTEMP_BASE_URL}/messages/{MTEMP_API_KEY}/{email}"
    loop = asyncio.get_event_loop()
    while time.time() - start < timeout_seconds:
        if state.stop_requested:
            raise Exception("Đã bấm dừng bot (STOP_REQUESTED)")
        if route_spec:
            fresh, err = check_route_freshness(route_spec)
            if not fresh:
                route_spec.route_state = "EXPIRED" if "EXPIRED" in (err or "") else "DISCONNECTED"
                raise Exception(f"[{ROUTE_DISCONNECTED}] {err}")
            if route_spec.provider == "psiphon":
                alive = is_psiphon_alive(fast_check=True)
                if not alive or (isinstance(alive, dict) and not alive.get("ok", True)):
                    route_spec.route_state = "DISCONNECTED"
                    raise Exception(f"[{ROUTE_DISCONNECTED}] Đường hầm Psiphon bị ngắt kết nối.")
                else:
                    route_spec.verified_at_utc = datetime.now(timezone.utc).isoformat()
            else:
                route_spec.verified_at_utc = datetime.now(timezone.utc).isoformat()
        def _check():
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode())
                    msgs = data.get("messages", []) or data.get("data", [])
                    if msgs:
                        for m in msgs:
                            subj = m.get("subject", "")
                            body = m.get("content", "") or m.get("body", "") or m.get("snippet", "")
                            digits = re.findall(r"\b(?:FB-)?(\d{5,6})\b", subj + " " + body)
                            if digits:
                                return digits[0]
            except Exception:
                pass
            return None
        otp = await loop.run_in_executor(None, _check)
        if otp:
            add_log("ĐÃ NHẬN MÃ OTP TỪ META: ***", "success", 65)
            return otp
        await asyncio.sleep(2)
    raise TimeoutError("Hết thời gian chờ OTP từ Meta.")

async def create_spinup_email(domain: str) -> tuple[str, str]:
    add_log("Đang tạo email trên SpinupMail...", "info", 10)
    req_data = json.dumps({
        "count": 1,
        "prefix": "muse",
        "domain": domain
    }).encode("utf-8")
    
    req = urllib.request.Request(
        f"{BACKEND_URL}/api/public/bulk-create",
        data=req_data,
        headers={"Content-Type": "application/json"}
    )
    loop = asyncio.get_event_loop()
    def _do_fetch():
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    res = await loop.run_in_executor(None, _do_fetch)
    if res.get("ok") and res.get("items"):
        item = res["items"][0]
        add_log(f"Đã tạo email SpinupMail: {item['address']}", "success", 20)
        return item["address"], item["pin"]
    raise Exception(f"Không thể tạo email: {res}")

async def poll_spinup_otp(email: str, pin: str, timeout_seconds: int = 75, route_spec: Optional[RouteSpec] = None) -> str:
    add_log("Đang chờ Meta gửi mã OTP xác thực...", "info", 50)
    start = time.time()
    loop = asyncio.get_event_loop()
    url = f"{BACKEND_URL}/api/public/otp?email={urllib.parse.quote(email)}&pin={urllib.parse.quote(pin)}"
    def _check():
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception:
            return None
    while time.time() - start < timeout_seconds:
        if state.stop_requested:
            raise Exception("Đã bấm dừng bot (STOP_REQUESTED)")
        if route_spec:
            fresh, err = check_route_freshness(route_spec)
            if not fresh:
                route_spec.route_state = "EXPIRED" if "EXPIRED" in (err or "") else "DISCONNECTED"
                raise Exception(f"[{ROUTE_DISCONNECTED}] {err}")
            if route_spec.provider == "psiphon":
                alive = is_psiphon_alive(fast_check=True)
                if not alive or (isinstance(alive, dict) and not alive.get("ok", True)):
                    route_spec.route_state = "DISCONNECTED"
                    raise Exception(f"[{ROUTE_DISCONNECTED}] Đường hầm Psiphon bị ngắt kết nối.")
                else:
                    route_spec.verified_at_utc = datetime.now(timezone.utc).isoformat()
            else:
                route_spec.verified_at_utc = datetime.now(timezone.utc).isoformat()
        data = await loop.run_in_executor(None, _check)
        if data and data.get("ok") and data.get("hasEmails"):
            latest = data.get("latest", {})
            otp = latest.get("otp")
            if otp:
                add_log("ĐÃ NHẬN MÃ OTP TỪ META: ***", "success", 65)
                return otp
        await asyncio.sleep(2)
    raise TimeoutError("Hết thời gian chờ OTP từ Meta.")

def check_route_freshness(route_spec: Optional[RouteSpec]) -> Tuple[bool, Optional[str]]:
    if not route_spec:
        return False, "ROUTE_UNVERIFIED: Chưa có thông số tuyến mạng."
    if route_spec.route_state != "VERIFIED":
        return False, f"ROUTE_UNVERIFIED: Tuyến mạng chưa được xác minh hợp lệ (trạng thái: {route_spec.route_state})."
    if not route_spec.verified_at_utc:
        return False, "ROUTE_UNVERIFIED: Thiếu timestamp xác minh tuyến mạng."
    try:
        v_time = datetime.fromisoformat(route_spec.verified_at_utc)
        elapsed = (datetime.now(timezone.utc) - v_time).total_seconds()
        if elapsed > route_spec.ttl_seconds:
            route_spec.route_state = "EXPIRED"
            return False, f"ROUTE_EXPIRED: Tuyến mạng đã hết hạn TTL ({elapsed:.1f}s > {route_spec.ttl_seconds}s)."
    except Exception as e:
        return False, f"ROUTE_MALFORMED: Không thể phân tích timestamp xác minh ({e})."
    return True, None


async def _assert_can_continue(context=None, browser=None, page=None, route_spec: Optional[RouteSpec] = None):
    if state.stop_requested:
        if page and not page.is_closed():
            try:
                await page.close()
            except Exception:
                pass
        if context:
            try:
                await context.close()
            except Exception:
                pass
        if browser:
            try:
                await browser.close()
            except Exception:
                pass
        raise Exception("Đã dừng tiến trình theo yêu cầu của người dùng (STOP_REQUESTED).")
    if route_spec:
        fresh, err = check_route_freshness(route_spec)
        if not fresh:
            route_spec.route_state = "EXPIRED" if "EXPIRED" in (err or "") else "DISCONNECTED"
            if page and not page.is_closed():
                try:
                    await page.close()
                except Exception:
                    pass
            if context:
                try:
                    await context.close()
                except Exception:
                    pass
            if browser:
                try:
                    await browser.close()
                except Exception:
                    pass
            raise Exception(f"[{ROUTE_DISCONNECTED}] {err}")

        # Check provider liveness
        is_disconnected = False
        disconnect_msg = None
        if route_spec.provider == "psiphon":
            try:
                alive = is_psiphon_alive()
                if not alive or (isinstance(alive, dict) and not alive.get("ok", True)):
                    is_disconnected = True
                    disconnect_msg = "Đường hầm Psiphon bị ngắt kết nối hoặc tín hiệu đã chết."
            except Exception as e:
                is_disconnected = True
                disconnect_msg = f"Lỗi kiểm tra liveness Psiphon: {e}"

        if is_disconnected:
            route_spec.route_state = "DISCONNECTED"
            if page and not page.is_closed():
                try:
                    await page.close()
                except Exception:
                    pass
            if context:
                try:
                    await context.close()
                except Exception:
                    pass
            if browser:
                try:
                    await browser.close()
                except Exception:
                    pass
            raise Exception(f"[{ROUTE_DISCONNECTED}] {disconnect_msg}")
        else:
            route_spec.verified_at_utc = datetime.now(timezone.utc).isoformat()


async def process_single_account(
    proxy_str: Optional[str] = None,
    visible: bool = True,
    provider: str = "clean_tempmail",
    domain: str = "maxxspace.com",
    inviteCode: Optional[str] = None,
    route_spec: Optional[RouteSpec] = None,
    user_profile: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    if route_spec is None:
        pw_cfg = to_playwright_proxy(proxy_str)
        route_spec = RouteSpec(
            provider="custom" if proxy_str else "vpn",
            mode="proxy" if proxy_str else "system",
            proxy_config=pw_cfg,
            local_proxy_endpoint=proxy_str,
            selected_at_utc=datetime.now(timezone.utc).isoformat()
        )

    if route_spec.proxy_config:
        add_log(f"Cấu hình Proxy: {route_spec.proxy_config.get('server')}", "info")
    else:
        add_log("Sử dụng mạng máy chủ / VPN trên máy tính", "info")
        
    # Pre-flight T0: Check exit IP route on Host BEFORE browser launch & email allocation
    host_probe = check_route_ip(route_spec.local_proxy_endpoint if route_spec.mode == "proxy" else None)
    if not host_probe.get("ok"):
        err_msg = f"[{NETWORK_PRECHECK_FAILED}] Không thể xác minh tuyến mạng IP host: {host_probe.get('error')}"
        add_log(f"❌ {err_msg}", "error", 100)
        raise Exception(err_msg)

    host_country = (host_probe.get("country_code") or "").upper()
    host_ip = host_probe.get("data", {}).get("query") or host_probe.get("data", {}).get("ip") or "Unknown"
    is_us = host_probe.get("is_us", False)
    is_ca = host_probe.get("is_ca", False)
    add_log(f"T0 Host IP xác thực: {host_ip} ({host_country})", "info", 15)
    
    if not is_us and not is_ca:
        c_code = ROUTE_COUNTRY_OTHER if host_country else ROUTE_COUNTRY_UNKNOWN
        err_msg = f"[{c_code}] Tuyến mạng host ({host_ip} - {host_country or 'Unknown'}) không thuộc Hoa Kỳ/Canada. Hủy cấp email và dừng tiến trình."
        add_log(f"❌ {err_msg}", "error", 100)
        raise Exception(err_msg)

    async with async_playwright() as p:
        preferred_channel = get_preferred_browser_channel()
        channel_name = "Microsoft Edge" if preferred_channel == "msedge" else (preferred_channel or "Chromium")
        add_log(f"Đang khởi động trình duyệt tự động ({channel_name})...", "info", 22)
        
        launch_args = [
            "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
            "--disable-features=WebRtcHideLocalIpsWithMdns",
            "--disable-blink-features=AutomationControlled",
            "--no-default-browser-check",
            "--no-first-run"
        ]
        launch_kwargs = {
            "headless": not visible,
            "proxy": route_spec.proxy_config,
            "args": launch_args
        }
        if preferred_channel:
            launch_kwargs["channel"] = preferred_channel

        browser = await p.chromium.launch(**launch_kwargs)
        
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            locale="en-US",
            timezone_id="America/New_York"
        )
        if hasattr(context, "add_init_script") and callable(getattr(context, "add_init_script")):
            try:
                res = context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                if asyncio.iscoroutine(res):
                    await res
            except Exception:
                pass

        # Pre-flight T1: SAME-CONTEXT browser IP probe BEFORE email allocation
        add_log("Đang kiểm tra tuyến mạng trong chính browser context (T1)...", "info", 25)
        preflight_page = await context.new_page()
        try:
            resp = await preflight_page.goto("https://ipwho.is/", timeout=15000)
            if not resp or resp.status != 200:
                raise Exception(f"HTTP status {resp.status if resp else 'None'}")
            body_text = await preflight_page.inner_text("body")
            browser_ip_data = json.loads(body_text)
            if not isinstance(browser_ip_data, dict) or browser_ip_data.get("success") is not True:
                raise Exception(f"ipwho.is trả về phản hồi không hợp lệ hoặc thiếu success=true: {browser_ip_data.get('message', 'Lỗi không xác định') if isinstance(browser_ip_data, dict) else browser_ip_data}")
            
            b_ip = browser_ip_data.get("ip")
            b_country = (browser_ip_data.get("country_code") or "").upper()
            if not b_ip or not b_country:
                raise Exception(f"Phản hồi thiếu IP hoặc mã quốc gia: {browser_ip_data}")
            
            try:
                ipaddress.ip_address(b_ip)
            except Exception:
                raise Exception(f"Địa chỉ IP trình duyệt không hợp lệ: {b_ip}")

            # Dual-mode host vs browser mismatch validation
            if host_country and host_country != b_country:
                raise Exception(f"[{ROUTE_MISMATCH}] Mismatch quốc gia giữa Host ({host_country}) và Trình duyệt ({b_country})!")
                
            if host_ip and b_ip and host_ip != b_ip and host_ip != "Unknown":
                raise Exception(f"[{ROUTE_MISMATCH}] Mismatch địa chỉ IP giữa Host ({host_ip}) và Trình duyệt ({b_ip}) trong chế độ {route_spec.mode}!")
                
            if b_country not in ("US", "CA"):
                c_code = ROUTE_COUNTRY_OTHER if b_country else ROUTE_COUNTRY_UNKNOWN
                raise Exception(f"[{c_code}] Trình duyệt có IP {b_ip} thuộc quốc gia {b_country}, không phải US/CA!")
                
            route_spec.route_state = "VERIFIED"
            route_spec.verified_at_utc = datetime.now(timezone.utc).isoformat()
            route_spec.verified_ip = b_ip
            route_spec.verified_country = b_country
            add_log(f"T1 Browser IP xác thực: {b_ip} ({b_country}) - Tuyến mạng trình duyệt ĐÃ XÁC MINH!", "success", 28)
        except Exception as e:
            await preflight_page.close()
            await context.close()
            await browser.close()
            err_code = ROUTE_MISMATCH if "ROUTE_MISMATCH" in str(e) else BROWSER_ROUTE_UNVERIFIED
            err_msg = f"[{err_code}] Xác minh tuyến mạng trình duyệt thất bại: {e}. Không cấp email để bảo vệ tài nguyên."
            add_log(f"❌ {err_msg}", "error", 100)
            raise Exception(err_msg)
        finally:
            if not preflight_page.is_closed():
                await preflight_page.close()

        # Stop and route freshness check immediately after preflight before email allocation
        await _assert_can_continue(context=context, browser=browser, route_spec=route_spec)

        # Allocate email ONLY after BOTH T0 and T1 have passed and stop not requested
        pin = ""
        if provider == "clean_tempmail":
            email = await create_clean_email()
        else:
            email, pin = await create_spinup_email(domain)
        
        await _assert_can_continue(context=context, browser=browser, route_spec=route_spec)

        page = await context.new_page()
        
        clean_invite = normalize_invite_code(inviteCode)
        start_url = "https://muse.ai/"
        add_log(f"Đang truy cập {start_url}...", "info", 30)
        try:
            await page.goto(start_url, wait_until="domcontentloaded", timeout=30000)
        except Exception as net_err:
            err_str = str(net_err)
            if "ERR_PROXY_CONNECTION_FAILED" in err_str or "ERR_TUNNEL_CONNECTION_FAILED" in err_str:
                add_log(f"[{ROUTE_DISCONNECTED}] Đường hầm mạng bị ngắt kết nối giữa phiên: {net_err}", "error", 100)
                await page.close()
                await context.close()
                await browser.close()
                raise Exception(f"[{ROUTE_DISCONNECTED}] Đường hầm proxy bị ngắt kết nối.")
            try:
                await page.goto(start_url, timeout=30000)
            except Exception:
                pass
            
        page_title = await page.title()
        add_log(f"Đã mở trang: {page_title}", "info", 35)
        if route_spec:
            route_spec.verified_at_utc = datetime.now(timezone.utc).isoformat()
        
        # 1. Fill email
        add_log(f"Đang điền email: {email}...", "info", 40)
        email_inp = await page.wait_for_selector('input[type="text"], input[type="email"], input[placeholder*="email" i], input', timeout=15000)
        await email_inp.click()
        await email_inp.fill(email)
        await asyncio.sleep(0.5)
        
        # Dispatch input/change events for React/Next.js controlled component
        try:
            if hasattr(page, "evaluate") and callable(getattr(page, "evaluate")):
                await page.evaluate("""(val) => {
                    const el = document.querySelector('input[placeholder*="email" i], input[type="text"], input[type="email"], input');
                    if (el) {
                        el.focus();
                        const proto = Object.getPrototypeOf(el);
                        const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set || Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set;
                        if (setter) setter.call(el, val);
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                }""", email)
        except Exception:
            pass

        continue_btn = await page.query_selector('button:has-text("Continue"), button[type="submit"]')
        if continue_btn:
            try:
                await continue_btn.click(timeout=5000)
            except Exception:
                await page.keyboard.press("Enter")
        else:
            await page.keyboard.press("Enter")
            
        add_log("Đã gửi email đăng ký, chờ màn hình OTP...", "info", 45)
        if route_spec:
            route_spec.verified_at_utc = datetime.now(timezone.utc).isoformat()
        
        # 2. Wait for code screen with graceful fallback
        try:
            await page.wait_for_selector('text="Enter your code"', timeout=10000)
            add_log("Màn hình nhập mã xác thực đã sẵn sàng!", "info", 48)
        except Exception:
            # Resilient fallback: Check if alternate selectors or inputs exist
            diag_ts = int(time.time())
            diag_path = os.path.join(SCREENSHOTS_DIR, f"muse_otp_{diag_ts}.png")
            try:
                if hasattr(page, "screenshot") and callable(getattr(page, "screenshot")):
                    await page.screenshot(path=diag_path)
            except Exception:
                pass
            add_log("Chưa phát hiện tiêu đề mã xác thực (timeout), kiểm tra ô nhập mã...", "warning", 48)
        
        if route_spec:
            route_spec.verified_at_utc = datetime.now(timezone.utc).isoformat()
        
        # 3. Wait for OTP from Meta
        await _assert_can_continue(context=context, browser=browser, page=page, route_spec=route_spec)
        if provider == "clean_tempmail":
            otp = await poll_clean_otp(email)
        else:
            otp = await poll_spinup_otp(email, pin)
        
        # Guard before any side effect after poll await
        await _assert_can_continue(context=context, browser=browser, page=page, route_spec=route_spec)

        # 4. Fill OTP
        add_log("Đang tự động nhập mã OTP vào Muse.ai...", "info", 70)
        otp_inp = await page.wait_for_selector('input[aria-label*="code" i], input[maxlength="6"], input[type="text"]', timeout=10000)
        await _assert_can_continue(context=context, browser=browser, page=page, route_spec=route_spec)
        try:
            await otp_inp.focus()
        except Exception:
            await otp_inp.click(force=True)
            
        await asyncio.sleep(0.5)
        await _assert_can_continue(context=context, browser=browser, page=page, route_spec=route_spec)
        await page.keyboard.type(str(otp), delay=150)
        await asyncio.sleep(1.5)
        await _assert_can_continue(context=context, browser=browser, page=page, route_spec=route_spec)
        
        confirm_btn = await page.query_selector('button:has-text("Confirm"), button[type="submit"]')
        if confirm_btn:
            try:
                await confirm_btn.click(force=True)
            except Exception:
                await page.keyboard.press("Enter")
        else:
            await page.keyboard.press("Enter")
            
        add_log("Đã xác nhận OTP, chờ kiểm tra hồ sơ...", "info", 80)
        
        # 5. Check if Name & Birthday screen with adaptive wait
        is_profile = False
        for _ in range(8):
            await asyncio.sleep(1)
            try:
                body_text = (await page.inner_text("body")).lower()
                if "finish creating your account" in body_text or "birthday" in body_text or "first name" in body_text:
                    is_profile = True
                    break
                if "/thread" in page.url or "/access" in page.url:
                    break
            except Exception:
                pass


        await _assert_can_continue(context=context, browser=browser, page=page, route_spec=route_spec)
        if is_profile:
            prof = user_profile or {}
            fn = (prof.get("firstName") or "").strip()
            ln = (prof.get("lastName") or "").strip()
            b_year = str(prof.get("birthYear") or "").strip()
            b_month = str(prof.get("birthMonth") or "").strip()
            b_day = str(prof.get("birthDay") or "").strip()

            if not (fn and ln and b_year and b_month and b_day):
                import random
                first_names = ["Alex", "James", "David", "Michael", "Sarah", "Emily", "Daniel", "Emma", "Olivia", "Ethan"]
                last_names = ["Taylor", "Miller", "Wilson", "Anderson", "Thomas", "Moore", "Jackson", "Martin", "Clark"]
                if not fn:
                    fn = random.choice(first_names)
                if not ln:
                    ln = random.choice(last_names)
                if not b_year:
                    b_year = str(random.randint(1988, 2002))
                if not b_month:
                    b_month = str(random.randint(1, 12))
                if not b_day:
                    b_day = str(random.randint(1, 28))
                add_log(f"Tự động điền hoàn tất hồ sơ: {fn} {ln} (Ngày sinh: {b_day}/{b_month}/{b_year})...", "info", 85)
            else:
                add_log(f"Đang điền thông tin hồ sơ theo cấu hình: {fn} {ln}...", "info", 85)

            try:
                # Check for explicit input fields
                fn_input = page.locator('input[placeholder*="First" i], input[name*="first" i], input[aria-label*="First" i]').first
                ln_input = page.locator('input[placeholder*="Last" i], input[name*="last" i], input[aria-label*="Last" i]').first
                
                if await fn_input.count() > 0 and await ln_input.count() > 0:
                    await fn_input.click()
                    await fn_input.fill(fn)
                    await asyncio.sleep(0.2)
                    await ln_input.click()
                    await ln_input.fill(ln)
                    await asyncio.sleep(0.2)
                else:
                    text_inps = [i for i in await page.query_selector_all("input") if (await i.get_attribute("type") or "text") not in ["hidden", "checkbox", "radio", "submit", "button"]]
                    if len(text_inps) >= 2:
                        await text_inps[0].click()
                        await page.keyboard.type(fn, delay=40)
                        await asyncio.sleep(0.2)
                        await text_inps[1].click()
                        await page.keyboard.type(ln, delay=40)
                        await asyncio.sleep(0.2)
                    elif len(text_inps) == 1:
                        await text_inps[0].click()
                        await page.keyboard.type(f"{fn} {ln}", delay=40)
                        await asyncio.sleep(0.2)

                # Check date picker inputs if present
                date_inp = page.locator('input[type="date"]').first
                if await date_inp.count() > 0:
                    try:
                        await date_inp.fill(f"{b_year}-{int(b_month):02d}-{int(b_day):02d}")
                    except Exception:
                        pass

                # Check text inputs for month/day/year
                m_inp = page.locator('input[name*="month" i], input[placeholder*="month" i]').first
                d_inp = page.locator('input[name*="day" i], input[placeholder*="day" i]').first
                y_inp = page.locator('input[name*="year" i], input[placeholder*="year" i]').first
                if await m_inp.count() > 0:
                    await m_inp.fill(b_month)
                if await d_inp.count() > 0:
                    await d_inp.fill(b_day)
                if await y_inp.count() > 0:
                    await y_inp.fill(b_year)

                # Check dropdown selects for month/day/year
                selects = await page.query_selector_all("select")
                if len(selects) >= 3:
                    months_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
                    m_idx = int(b_month) if b_month.isdigit() else 1
                    m_name = months_names[m_idx - 1] if 1 <= m_idx <= 12 else "Jan"

                    m_sel = page.locator("select").nth(0)
                    try:
                        await m_sel.select_option(value=b_month)
                    except Exception:
                        try:
                            await m_sel.select_option(label=m_name)
                        except Exception:
                            try:
                                await m_sel.select_option(index=m_idx)
                            except Exception:
                                pass

                    d_sel = page.locator("select").nth(1)
                    try:
                        await d_sel.select_option(label=b_day)
                    except Exception:
                        try:
                            await d_sel.select_option(value=b_day)
                        except Exception:
                            try:
                                await d_sel.select_option(value=f"{int(b_day):02d}")
                            except Exception:
                                try:
                                    await d_sel.select_option(index=int(b_day))
                                except Exception:
                                    pass

                    y_sel = page.locator("select").nth(2)
                    try:
                        await y_sel.select_option(label=b_year)
                    except Exception:
                        try:
                            await y_sel.select_option(value=b_year)
                        except Exception:
                            pass

                await asyncio.sleep(1)
                finish_btn = page.locator('button:has-text("Confirm"), button:has-text("Save"), button:has-text("Continue"), button:has-text("Next"), button[type="submit"]').first
                if await finish_btn.count() > 0:
                    await finish_btn.click(force=True)
                else:
                    await page.keyboard.press("Enter")
                    
                add_log("Đã gửi thông tin hồ sơ, đang chờ Meta xác nhận...", "info", 90)
            except Exception as e:
                add_log(f"Lưu ý khi điền hồ sơ: {e}", "warning")
            
            # Step 1: Wait up to 12s for the profile screen to dismiss naturally
            for _ in range(12):
                await asyncio.sleep(1)
                if state.stop_requested:
                    break
                try:
                    cur_body = (await page.inner_text("body")).lower()
                    if "finish creating your account" not in cur_body and "birthday" not in cur_body and "first name" not in cur_body:
                        break
                except Exception:
                    break

            # Step 2: Allow Meta to complete its OAuth / session handshake naturally
            add_log("Đang chờ Meta hoàn tất đồng bộ phiên đăng nhập...", "info", 92)
            for _ in range(8):
                await asyncio.sleep(1)
                cur_url = page.url.lower()
                if "muse.ai" in cur_url and ("access" in cur_url or "thread" in cur_url or "waitlist" in cur_url):
                    break
            
        # 6. Natural Verification: Check if account entered chat or got waitlisted
        add_log("Đang kiểm tra quyền truy cập vào màn hình Chat Muse.ai...", "info", 94)
        for _ in range(5):
            await asyncio.sleep(1)
            if "/thread" in page.url or "/access" in page.url:
                break

        access = await inspect_muse_access(page, continue_saved_login=True)
        current_url = page.url
        has_chat = access["status"] == "SUCCESS_CHAT_READY"

        timestamp_str = int(time.time())
        screenshot_prefix = "muse_chat" if has_chat else "muse_waitlist"
        screenshot_filename = f"{screenshot_prefix}_{timestamp_str}.png"
        screenshot_path = os.path.join(SCREENSHOTS_DIR, screenshot_filename)
        await page.screenshot(path=screenshot_path)
        
        cookies = await context.cookies()
        hatch_sess = next((c["value"] for c in cookies if c["name"] == "hatch_sess"), "")
        
        if not has_chat:
            account_data = {
                "id": f"muse_{timestamp_str}",
                "email": email,
                "provider": provider,
                "network_provider": route_spec.provider if route_spec else "psiphon",
                "route_spec": asdict(route_spec) if route_spec else None,
                "pin": pin,
                "otp": otp,
                "url": current_url,
                "title": await page.title(),
                "screenshot": screenshot_filename,
                "hatch_sess": hatch_sess[:40] + "..." if hatch_sess else "Có",
                "cookies": cookies,
                "proxy_used": proxy_str or (route_spec.local_proxy_endpoint if route_spec else "Không dùng") or "Không dùng",
                "createdAt": time.strftime("%Y-%m-%d %H:%M:%S"),
                "status": access["status"],
                "error": access["message"]
            }
            state.accounts.insert(0, account_data)
            save_accounts()
            await browser.close()
            err_msg = access["message"]
            add_log(f"❌ {err_msg}", "error", 100)
            raise MuseAccessError(access["status"], err_msg)

        # Redeem only after authenticated chat access; links do not prove redemption.
        await _assert_can_continue(context=context, browser=browser, page=page, route_spec=route_spec)
        invitation = {"code": clean_invite, "status": "NOT_REQUESTED", "message": "Không yêu cầu mã mời."}
        if clean_invite:
            add_log(f"Đã vào chat. Đang đổi mã {clean_invite} trong Cài đặt...", "info", 96)
            try:
                invitation = await redeem_invite(page, clean_invite, idempotency_key=f"acc-{email}", account_id=email)
            except Exception:
                invitation = {"code": clean_invite, "status": "UNVERIFIED", "message": "Chưa hoàn tất thao tác đổi mã trong Cài đặt."}
            add_log(invitation["message"], "success" if invitation["status"] == "REDEEMED" else "warning", 98)
        account_data = {
            "id": f"muse_{timestamp_str}",
            "email": email,
            "provider": provider,
            "network_provider": route_spec.provider if route_spec else "psiphon",
            "route_spec": asdict(route_spec) if route_spec else None,
            "pin": pin,
            "otp": otp,
            "url": current_url,
            "title": await page.title(),
            "screenshot": screenshot_filename,
            "hatch_sess": hatch_sess[:40] + "..." if hatch_sess else "Có",
            "cookies": cookies,
            "proxy_used": proxy_str or (route_spec.local_proxy_endpoint if route_spec else "Không dùng") or "Không dùng",
            "createdAt": time.strftime("%Y-%m-%d %H:%M:%S"),
            "status": "SUCCESS_CHAT_READY",
            "invite": invitation,
            "requirementsComplete": not clean_invite or invitation["status"] == "REDEEMED"
        }
        
        state.accounts.insert(0, account_data)
        save_accounts()
        add_log(f"🎉 TẠO VÀ ĐĂNG NHẬP MÀN HÌNH CHAT THÀNH CÔNG: {email}!", "success", 100)
        
        if visible:
            await asyncio.sleep(3)
            
        await browser.close()
        return account_data

async def bot_worker(req: StartBotRequest):
    state.is_running = True
    if state.stop_requested:
        add_log("Phiên đã được yêu cầu dừng trước khi worker bắt đầu. Hủy bỏ tác vụ an toàn.", "warning")
        state.is_running = False
        return
        
    state.session_accounts = []
    state.session_id = time.strftime("%Y%m%d_%H%M%S")
    state.session_time = time.strftime("%Y-%m-%d %H:%M:%S")
    add_log(f"Bắt đầu phiên tạo {req.count} tài khoản Muse.ai ({req.provider})...", "info", 0)
    
    try:
        # 1. Deterministic unified route resolution
        route_info = await resolve_provider_route(req.proxyType or "psiphon", req.proxy)
        if not route_info.get("ok"):
            err_msg = route_info.get("error", "Không thể giải quyết tuyến mạng.")
            err_code = route_info.get("code", "ROUTE_ERROR")
            add_log(f"❌ [{err_code}] {err_msg}", "error", 100)
            return
            
        req.proxy = route_info.get("proxy")
        route_spec_dict = route_info.get("spec")
        route_spec = RouteSpec(**route_spec_dict) if route_spec_dict else None
        
        user_prof = {
            "firstName": req.firstName,
            "lastName": req.lastName,
            "birthYear": req.birthYear,
            "birthMonth": req.birthMonth,
            "birthDay": req.birthDay
        }
            
        success_count = 0
        for i in range(req.count):
            if state.stop_requested:
                add_log("Đã dừng quy trình theo yêu cầu.", "warning")
                break
                
            add_log(f"--- Đang tạo tài khoản {i + 1}/{req.count} ---", "info")
            try:
                acc = await process_single_account(
                    proxy_str=req.proxy,
                    visible=req.visible,
                    provider=req.provider,
                    domain=req.domain,
                    inviteCode=req.inviteCode,
                    route_spec=route_spec,
                    user_profile=user_prof
                )
                if isinstance(acc, dict) and acc.get("status") == "SUCCESS_CHAT_READY" and acc.get("requirementsComplete", False):
                    state.session_accounts.append(acc)
                    success_count += 1
                    save_session_csv_and_excel(state.session_accounts, state.session_id)
                elif isinstance(acc, dict) and acc.get("status") == "SUCCESS_CHAT_READY":
                    add_log("Tài khoản đã vào chat nhưng chưa xác nhận đổi mã mời. Dừng để xử lý trên tài khoản này, không tạo thêm.", "warning")
                    break
            except MuseAccessError as e:
                add_log(f"Dừng phiên: {e}. Không tiếp tục tạo thêm tài khoản khi chưa vào được chat.", "error")
                break
            except Exception as e:
                add_log(f"Lỗi ở tài khoản {i + 1}: {type(e).__name__}: {str(e)}", "error")
                
            if i < req.count - 1 and not state.stop_requested:
                add_log("Nghỉ 3 giây trước tài khoản tiếp theo...", "info")
                await asyncio.sleep(3)
                
        if state.session_accounts:
            save_session_csv_and_excel(state.session_accounts, state.session_id)
            add_log(f"📊 Đã tự động xuất File CSV & Excel riêng cho phiên này ({len(state.session_accounts)} tài khoản)!", "success", 100)
            
        add_log(f"Kết thúc phiên: {success_count}/{req.count} tài khoản hoàn tất yêu cầu chat và mã mời.", "success" if success_count == req.count else "warning" if success_count else "error", 100)
    finally:
        state.is_running = False

_job_lock = asyncio.Lock()

@app.post("/api/bot/start")
async def start_bot(req: StartBotRequest, bg_tasks: BackgroundTasks):
    if req.count <= 0:
        raise HTTPException(status_code=422, detail="Số lượng tài khoản phải lớn hơn 0.")
    if req.inviteCode:
        try:
            normalize_invite_code(req.inviteCode)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error))
            
    async with _job_lock:
        if state.is_running:
            raise HTTPException(status_code=409, detail="Bot đang chạy, vui lòng chờ hoặc bấm dừng.")
        state.is_running = True
        state.stop_requested = False
        state.current_step = "Đang khởi tạo phiên làm việc..."
        state.logs = []
        bg_tasks.add_task(bot_worker, req)
        
    return {"ok": True, "message": "Bot đã được khởi chạy"}

@app.post("/api/bot/stop")
async def stop_bot():
    if state.is_running:
        state.stop_requested = True
        add_log("Đang yêu cầu dừng bot...", "warning")
        return {"ok": True, "message": "Đang dừng bot..."}
    return {"ok": True, "message": "Bot hiện không chạy."}

@app.get("/api/bot/status")
async def get_status():
    return {
        "isRunning": state.is_running,
        "currentStep": state.current_step,
        "logs": state.logs[-40:],
        "accountsCount": len(state.accounts)
    }

@app.get("/api/bot/logs")
async def get_logs():
    return {
        "ok": True,
        "logs": state.logs
    }

@app.get("/api/bot/runtime")
async def get_bot_runtime():
    return get_git_runtime_identity()

def sanitize_proxy_display(proxy_str: Optional[str]) -> str:
    if not proxy_str or str(proxy_str).strip() in ("", "Không dùng", "none"):
        return "Không dùng"
    p = str(proxy_str).strip()
    try:
        parsed = urllib.parse.urlsplit(p)
        if parsed.hostname:
            port_part = f":{parsed.port}" if parsed.port else ""
            scheme = f"{parsed.scheme}://" if parsed.scheme else ""
            return f"{scheme}{parsed.hostname}{port_part}"
    except Exception:
        pass
    if "@" in p:
        return p.split("@")[-1]
    return p

@app.get("/api/bot/accounts")
async def get_accounts():
    if os.path.exists(ACCOUNTS_FILE):
        try:
            with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                state.accounts = json.load(f)
        except Exception:
            pass
    sanitized = []
    for a in state.accounts:
        route_spec = a.get("route_spec")
        safe_route = None
        if isinstance(route_spec, dict):
            safe_route = {
                "provider": route_spec.get("provider"),
                "mode": route_spec.get("mode"),
                "route_state": route_spec.get("route_state"),
                "verified_country": route_spec.get("verified_country"),
                "verified_at_utc": route_spec.get("verified_at_utc")
            }
        sanitized_account = {
            "id": a.get("id"),
            "email": a.get("email"),
            "provider": a.get("provider"),
            "network_provider": a.get("network_provider"),
            "pin": a.get("pin", "") or "",
            "url": a.get("url"),
            "title": a.get("title"),
            "screenshot": a.get("screenshot"),
            "hasCookies": bool(a.get("cookies")),
            "hasSession": bool(a.get("hatch_sess")),
            "proxy_used": sanitize_proxy_display(a.get("proxy_used")),
            "route_spec": safe_route,
            "createdAt": a.get("createdAt"),
            "status": a.get("status"),
            "error": a.get("error")
        }
        sanitized.append(sanitized_account)
    return {
        "ok": True,
        "count": len(sanitized),
        "accounts": sanitized
    }

@app.delete("/api/bot/accounts")
async def clear_accounts():
    state.accounts = []
    save_accounts()
    return {"ok": True, "message": "Đã xóa lịch sử tài khoản"}

ALLOWED_SCREENSHOT_EXTS = {".png", ".jpg", ".jpeg", ".webp"}

@app.get("/api/bot/screenshot/{filename}")
async def get_screenshot(filename: str):
    safe_name = os.path.basename(filename)
    ext = os.path.splitext(safe_name)[1].lower()
    if ext not in ALLOWED_SCREENSHOT_EXTS:
        raise HTTPException(status_code=400, detail="Chỉ cho phép định dạng ảnh hợp lệ (.png, .jpg, .webp)")
    real_root = os.path.realpath(SCREENSHOTS_DIR)
    real_path = os.path.realpath(os.path.join(SCREENSHOTS_DIR, safe_name))
    if not real_path.startswith(real_root + os.sep) or not os.path.isfile(real_path):
        raise HTTPException(status_code=404, detail="Screenshot not found")
    media = "image/png" if ext == ".png" else f"image/{ext.lstrip('.')}"
    return FileResponse(real_path, media_type=media)

async def resolve_provider_route(proxy_type: Optional[str], custom_proxy: Optional[str] = None, neutral: bool = False) -> Dict[str, Any]:
    ptype = (proxy_type or "psiphon").strip().lower()
    if ptype == "psiphon":
        alive = await asyncio.to_thread(is_psiphon_alive)
        if not alive:
            alive = await asyncio.to_thread(start_psiphon_tunnel, 25)
        if not alive or not alive.get("ok"):
            return {
                "ok": False,
                "code": PROXY_NOT_REACHABLE,
                "error": (alive or {}).get("error", "Không thể khởi động đường hầm Psiphon US."),
                "provider": "psiphon"
            }
        proxy_url = alive.get("proxy", "http://127.0.0.1:8086")
        spec = RouteSpec(
            provider="psiphon",
            mode="proxy",
            proxy_config=to_playwright_proxy(proxy_url),
            local_proxy_endpoint=proxy_url,
            tunnel_process_identity="psiphon-tunnel-core",
            selected_at_utc=datetime.now(timezone.utc).isoformat(),
            route_state="UNVERIFIED",
            verification=alive.get("data")
        )
        return {
            "ok": True,
            "provider": "psiphon",
            "proxy": proxy_url,
            "networkMode": "proxy",
            "is_us": alive.get("is_us", False),
            "is_ca": alive.get("is_ca", False),
            "country_code": "US" if alive.get("is_us") else "CA" if alive.get("is_ca") else None,
            "data": alive.get("data"),
            "spec": asdict(spec)
        }
    elif ptype == "vpn":
        host_check = await asyncio.to_thread(check_route_ip, None)
        if not host_check.get("ok"):
            return {
                "ok": False,
                "code": IP_SERVICE_BAD_RESPONSE,
                "error": f"Không thể đo tuyến mạng hệ thống: {host_check.get('error')}",
                "provider": "vpn",
                "networkMode": "system"
            }
        if not neutral and not (host_check.get("is_us") or host_check.get("is_ca")):
            c_code = ROUTE_COUNTRY_OTHER if host_check.get("country_code") else ROUTE_COUNTRY_UNKNOWN
            return {
                "ok": False,
                "code": c_code,
                "error": f"Tuyến mạng hệ thống đo được thuộc quốc gia {host_check.get('country_code') or 'chưa xác định'}, không thuộc Hoa Kỳ/Canada.",
                "provider": "vpn",
                "networkMode": "system",
                "country_code": host_check.get("country_code")
            }
        spec = RouteSpec(
            provider="vpn",
            mode="system",
            proxy_config=None,
            local_proxy_endpoint=None,
            tunnel_process_identity=None,
            selected_at_utc=datetime.now(timezone.utc).isoformat(),
            route_state="UNVERIFIED",
            verification=host_check.get("data"),
            ttl_seconds=180
        )
        return {
            "ok": True,
            "provider": "vpn",
            "proxy": None,
            "networkMode": "system",
            "is_us": host_check.get("is_us", False),
            "is_ca": host_check.get("is_ca", False),
            "country_code": host_check.get("country_code"),
            "data": host_check.get("data"),
            "spec": asdict(spec)
        }
    elif ptype == "custom":
        norm = normalize_proxy(custom_proxy)
        if not norm:
            return {
                "ok": False,
                "code": PROXY_NOT_CONFIGURED,
                "error": "Chưa cung cấp proxy riêng hoặc định dạng không hợp lệ.",
                "provider": "custom"
            }
        spec = RouteSpec(
            provider="custom",
            mode="proxy",
            proxy_config=to_playwright_proxy(norm),
            local_proxy_endpoint=norm,
            selected_at_utc=datetime.now(timezone.utc).isoformat(),
            route_state="UNVERIFIED"
        )
        return {
            "ok": True,
            "provider": "custom",
            "proxy": norm,
            "networkMode": "proxy",
            "spec": asdict(spec)
        }
    elif ptype == "auto":
        active_path = os.path.join(os.path.dirname(__file__), "active_us_proxy.json")
        if not os.path.exists(active_path):
            return {
                "ok": False,
                "code": PROXY_NOT_CONFIGURED,
                "error": "Chưa có cấu hình proxy tự động trong active_us_proxy.json.",
                "provider": "auto"
            }
        try:
            with open(active_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            candidate = data.get("proxy")
            if not candidate:
                return {
                    "ok": False,
                    "code": PROXY_NOT_CONFIGURED,
                    "error": "File active_us_proxy.json không chứa địa chỉ proxy hợp lệ.",
                    "provider": "auto"
                }
            # Saved Auto candidate must be probed with TTL (3600 seconds)
            last_checked = data.get("last_checked", 0)
            if time.time() - last_checked > 3600:
                probe_res = await asyncio.to_thread(check_route_ip, candidate)
                if not probe_res.get("ok") or not probe_res.get("is_us"):
                    return {
                        "ok": False,
                        "code": PROXY_NOT_REACHABLE,
                        "error": f"Proxy tự động đã hết hạn hoặc không khả dụng: {probe_res.get('error', 'IP không thuộc Hoa Kỳ')}",
                        "provider": "auto"
                    }
                data["last_checked"] = time.time()
                try:
                    with open(active_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2)
                except Exception:
                    pass
            spec = RouteSpec(
                provider="auto",
                mode="proxy",
                proxy_config=to_playwright_proxy(candidate),
                local_proxy_endpoint=candidate,
                selected_at_utc=datetime.now(timezone.utc).isoformat(),
                route_state="UNVERIFIED",
                verification=data
            )
            return {
                "ok": True,
                "provider": "auto",
                "proxy": candidate,
                "networkMode": "proxy",
                "data": data,
                "spec": asdict(spec)
            }
        except Exception as e:
            return {
                "ok": False,
                "code": PROXY_NOT_REACHABLE,
                "error": f"Lỗi đọc cấu hình proxy tự động: {e}",
                "provider": "auto"
            }
    elif ptype == "windscribe":
        vpn_res = await asyncio.to_thread(connect_free_us)
        if not vpn_res.get("ok"):
            return {
                "ok": False,
                "code": PROXY_NOT_REACHABLE,
                "error": vpn_res.get("error", "Không thể kết nối Windscribe."),
                "provider": "windscribe"
            }
        spec = RouteSpec(
            provider="windscribe",
            mode="system",
            proxy_config=None,
            local_proxy_endpoint=None,
            tunnel_process_identity="windscribe-cli",
            selected_at_utc=datetime.now(timezone.utc).isoformat(),
            route_state="UNVERIFIED",
            verification=vpn_res.get("data"),
            ttl_seconds=180
        )
        return {
            "ok": True,
            "provider": "windscribe",
            "proxy": None,
            "networkMode": "system",
            "is_us": vpn_res.get("is_us", False),
            "is_ca": vpn_res.get("is_ca", False),
            "data": vpn_res.get("data"),
            "spec": asdict(spec)
        }
    else:
        return {
            "ok": False,
            "code": PROVIDER_INVALID,
            "error": f"Nhà cung cấp mạng '{proxy_type}' không hợp lệ hoặc chưa được hỗ trợ.",
            "provider": ptype
        }


async def ensure_provider_tunnel(provider: str = "psiphon", custom_proxy: Optional[str] = None) -> Dict[str, Any]:
    result = await resolve_provider_route(provider, custom_proxy)
    if not result or not result.get("ok"):
        raise HTTPException(status_code=503, detail=(result or {}).get("error", "Không thể thiết lập tuyến mạng hợp lệ."))
    if result.get("is_us") is None and result.get("proxy"):
        probe = await asyncio.to_thread(check_route_ip, result.get("proxy"))
        if not probe.get("ok"):
            raise HTTPException(status_code=503, detail=f"Không thể kết nối proxy: {probe.get('error')}")
        result["is_us"] = probe.get("is_us", False)
        result["is_ca"] = probe.get("is_ca", False)
        result["country_code"] = probe.get("country_code")
        result["data"] = probe.get("data")
    if not (result.get("is_us") or result.get("is_ca")):
        raise HTTPException(status_code=503, detail=f"Tuyến mạng đo được ({result.get('country_code') or 'chưa xác định'}) không thuộc Hoa Kỳ/Canada.")
    return result


async def ensure_free_tunnel():
    """Backward compatibility alias for Psiphon tunnel."""
    return await ensure_provider_tunnel("psiphon")


class OpenMuseRequest(BaseModel):
    provider: Optional[str] = "psiphon"
    proxy: Optional[str] = None


@app.post("/api/bot/open-muse")
async def open_muse(req: Optional[OpenMuseRequest] = None):
    ptype = (req.provider if req and req.provider else "psiphon").strip().lower()
    proxy_val = req.proxy if req else None
    result = await ensure_provider_tunnel(ptype, proxy_val)
    proxy_to_use = to_playwright_proxy(result.get("proxy")) if result.get("networkMode") == "proxy" else None
    try:
        url = await open_muse_browser(proxy_to_use)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Không mở được Muse qua đường hầm ({e}). Kiểm tra kết nối hoặc Chrome rồi thử lại.")
    return {"ok": True, "url": url, "provider": result.get("provider"), "message": f"Đã mở Muse qua {result.get('provider')}. Bạn có thể đăng nhập tài khoản của mình; quyền truy cập do Muse quyết định."}


@app.post("/api/bot/open-session/{account_id}")
async def open_session(account_id: str):
    acc = next((a for a in state.accounts if a.get("id") == account_id or a.get("email") == account_id), None)
    if not acc and os.path.exists(ACCOUNTS_FILE):
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as file:
            saved = json.load(file)
        acc = next((a for a in saved if a.get("id") == account_id or a.get("email") == account_id), None)
    if not acc:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản")
    
    proxy_val = acc.get("proxy_used")
    if proxy_val in ("Không dùng", "", None):
        proxy_to_use = None
    else:
        provider_to_use = acc.get("network_provider") or ("psiphon" if any(port in str(proxy_val) for port in ("8085", "1085", "8086", "1086")) else "custom")
        tunnel = await ensure_provider_tunnel(provider_to_use, proxy_val)
        proxy_to_use = to_playwright_proxy(tunnel.get("proxy")) if tunnel.get("networkMode") == "proxy" else None
    try:
        url = await open_muse_browser(proxy_to_use, acc.get("cookies", []))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Không mở được phiên Muse: {e}. Kiểm tra kết nối hoặc Chrome rồi thử lại.")
    return {"ok": True, "url": url, "message": "Đã mở phiên Muse. Trình duyệt giữ mở đến khi bạn đóng."}


@app.post("/api/bot/recheck-session/{account_id}")
async def recheck_session(account_id: str):
    if state.is_running:
        raise HTTPException(status_code=409, detail="Chờ phiên tạo tài khoản kết thúc trước khi kiểm tra lại.")
    if os.path.exists(ACCOUNTS_FILE):
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as file:
            state.accounts = json.load(file)
    acc = next((a for a in state.accounts if a.get("id") == account_id), None)
    if not acc:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản")
    
    proxy_val = acc.get("proxy_used")
    if proxy_val in ("Không dùng", "", None):
        proxy_to_use = None
        tunnel = {"proxy": None}
    else:
        provider_to_use = acc.get("network_provider") or ("psiphon" if any(port in str(proxy_val) for port in ("8085", "1085", "8086", "1086")) else "custom")
        tunnel = await ensure_provider_tunnel(provider_to_use, proxy_val)
        proxy_to_use = to_playwright_proxy(tunnel.get("proxy")) if tunnel.get("networkMode") == "proxy" else None
    try:
        result = await open_muse_browser(proxy_to_use, acc.get("cookies", []), verify_access=True)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Không tải được Muse để kiểm tra ({e}). Chưa thay đổi kết quả tài khoản.")
    acc.update(status=result["status"], error=result["message"], url=result["url"],
               cookies=result["cookies"], proxy_used=tunnel.get("proxy"))
    save_accounts()
    return {"ok": True, "status": result["status"], "message": result["message"]}


class DiagnoseRouteRequest(BaseModel):
    proxyType: Optional[str] = "psiphon"
    proxy: Optional[str] = None


@app.post("/api/bot/diagnose-route")
async def diagnose_route(req: DiagnoseRouteRequest):
    """Neutral route and access gate diagnosis:
    - Measures T0 host exit IP
    - Launches isolated browser context and measures T1 exit IP
    - Compares Host vs Browser route match
    - Observes read-only initial Muse landing screen access state
    - Zero email allocation, zero account creation, zero secrets.
    """
    resolved = await resolve_provider_route(req.proxyType, req.proxy, neutral=True)
    if not resolved.get("ok"):
        return {
            "ok": False,
            "provider": req.proxyType,
            "code": resolved.get("code", "ROUTE_RESOLUTION_FAILED"),
            "error": resolved.get("error", "Không thể giải quyết tuyến mạng."),
            "host_probe": None,
            "browser_probe": None,
            "route_match": False,
            "muse_rendered_state": None,
            "timestamp_utc": datetime.now(timezone.utc).isoformat()
        }
        
    host_endpoint = resolved.get("proxy")
    host_probe_res = await asyncio.to_thread(check_route_ip, host_endpoint)
    host_data = host_probe_res.get("data") or resolved.get("data") or {}
    host_ip = host_probe_res.get("query") or host_data.get("query") or host_data.get("ip") or "Unknown"
    host_country = (host_probe_res.get("country_code") or resolved.get("country_code") or host_data.get("countryCode") or "").upper()
    is_us = host_probe_res.get("is_us", resolved.get("is_us", False))
    is_ca = host_probe_res.get("is_ca", resolved.get("is_ca", False))
    
    host_summary = {
        "ip": host_ip,
        "country": host_country,
        "is_us": is_us,
        "is_ca": is_ca,
        "isp": host_data.get("isp", "Unknown")
    }

    b_summary = None
    route_match = False
    muse_state = None
    diag_error = None
    
    try:
        pw_proxy = to_playwright_proxy(resolved.get("proxy")) if resolved.get("networkMode") == "proxy" else None
        async with async_playwright() as p:
            preferred_channel = get_preferred_browser_channel()
            diag_kwargs = {
                "headless": True,
                "proxy": pw_proxy,
                "args": [
                    "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
                    "--disable-features=WebRtcHideLocalIpsWithMdns",
                    "--disable-blink-features=AutomationControlled",
                    "--no-default-browser-check",
                    "--no-first-run"
                ]
            }
            if preferred_channel:
                diag_kwargs["channel"] = preferred_channel
            browser = await p.chromium.launch(**diag_kwargs)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                locale="en-US",
                timezone_id="America/New_York"
            )
            page = await context.new_page()

            # Browser T1 probe
            t1_resp = await page.goto("https://ipwho.is/", timeout=15000)
            if not t1_resp or t1_resp.status != 200:
                raise Exception(f"T1 probe HTTP status {t1_resp.status if t1_resp else 'None'}")
            body_txt = await page.inner_text("body")
            b_data = json.loads(body_txt)
            if not isinstance(b_data, dict) or b_data.get("success") is not True:
                raise Exception(f"ipwho.is trả về dữ liệu không hợp lệ: {b_data}")
            
            b_ip = b_data.get("ip")
            b_country = (b_data.get("country_code") or "").upper()
            b_is_us = b_country == "US"
            b_is_ca = b_country == "CA"
            
            b_summary = {
                "ip": b_ip,
                "country": b_country,
                "is_us": b_is_us,
                "is_ca": b_is_ca,
                "isp": b_data.get("connection", {}).get("isp") or b_data.get("isp", "Unknown")
            }
            
            country_match = (host_country == b_country) if host_country and b_country else False
            ip_match = (host_ip == b_ip) if (host_ip != "Unknown" and b_ip) else True
            route_match = country_match and ip_match
            
            # Read-only Muse landing access observation (zero signup, zero email)
            try:
                await page.goto("https://muse.ai/", wait_until="domcontentloaded", timeout=30000)
                access_info = await inspect_muse_access(page, continue_saved_login=False, attempts=3)
                muse_state = {
                    "status": access_info.get("status"),
                    "message": access_info.get("message"),
                    "url": "https://muse.ai/"
                }
            except Exception as m_err:
                muse_state = {
                    "status": "UNREACHABLE",
                    "message": f"Không thể tải https://muse.ai/: {m_err}",
                    "url": "https://muse.ai/"
                }
                
            await page.close()
            await context.close()
            await browser.close()
    except Exception as e:
        diag_error = str(e)

    return {
        "ok": diag_error is None and route_match and host_probe_res.get("ok", False) and bool(b_summary),
        "provider": req.proxyType,
        "mode": resolved.get("networkMode"),
        "host_probe": host_summary,
        "browser_probe": b_summary,
        "route_match": route_match,
        "is_us": bool(b_summary and b_summary.get("is_us")),
        "is_ca": bool(b_summary and b_summary.get("is_ca")),
        "country_code": b_summary.get("country") if b_summary else host_country,
        "muse_rendered_state": muse_state,
        "error": diag_error,
        "timestamp_utc": datetime.now(timezone.utc).isoformat()
    }


class CheckProxyRequest(BaseModel):
    proxy: Optional[str] = None
    proxyType: Optional[str] = "psiphon"

    @field_validator("proxyType")
    @classmethod
    def validate_proxy_type(cls, v):
        allowed = {"psiphon", "vpn", "custom", "auto", "windscribe"}
        if v is not None and v.strip().lower() not in allowed:
            raise ValueError(f"{PROVIDER_INVALID}: Unknown proxy provider: '{v}'. Must be one of {allowed}")
        return (v or "psiphon").strip().lower()

@app.post("/api/bot/check-proxy-health")
async def check_proxy_health(req: CheckProxyRequest):
    route_info = await resolve_provider_route(req.proxyType, req.proxy)
    if not route_info.get("ok"):
        return {
            "ok": False,
            "code": route_info.get("code", "ROUTE_ERROR"),
            "error": route_info.get("error", "Không thể xác định cấu hình proxy.")
        }
    p_str = route_info.get("proxy")
    res = await asyncio.to_thread(check_route_ip, p_str)
    if not res.get("ok"):
        return res
    res["provider"] = route_info.get("provider")
    res["networkMode"] = route_info.get("networkMode")
    res["spec"] = route_info.get("spec")
    return res

@app.post("/api/bot/start-psiphon")
async def api_start_psiphon():
    loop = asyncio.get_event_loop()
    res = await loop.run_in_executor(None, start_psiphon_tunnel, 25)
    return res

@app.post("/api/bot/stop-psiphon")
async def api_stop_psiphon():
    stop_psiphon_tunnel()
    return {"ok": True, "message": "Đã dừng Psiphon US Tunnel"}

@app.get("/api/bot/psiphon-status")
async def api_psiphon_status():
    alive = await asyncio.to_thread(is_psiphon_alive)
    return {"running": alive is not None, "info": alive}

@app.post("/api/bot/auto-proxy")
async def auto_proxy():
    active_path = os.path.join(os.path.dirname(__file__), "active_us_proxy.json")
    if os.path.exists(active_path):
        try:
            with open(active_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("proxy"):
                return {
                    "ok": True,
                    "proxy": data["proxy"],
                    "ip": data.get("ip"),
                    "isp": data.get("isp"),
                    "region": f"{data.get('city')}, {data.get('region')}, US",
                    "ping": data.get("ping")
                }
        except Exception:
            pass
    return {
        "ok": False,
        "error": "Chưa có cấu hình proxy tự động trong active_us_proxy.json."
    }

@app.get("/api/bot/export-txt")
async def export_txt():
    save_accounts_txt()
    txt_path = os.path.join(os.path.dirname(__file__), "muse_accounts.txt")
    if os.path.exists(txt_path):
        return FileResponse(
            txt_path,
            media_type="text/plain; charset=utf-8",
            filename="muse_accounts.txt"
        )
    raise HTTPException(status_code=404, detail="File not found")

@app.get("/api/bot/tunnel-info")
async def get_tunnel_info():
    url = get_public_tunnel_url()
    return {"ok": True, "tunnelUrl": url, "otpUrl": f"{url}/otp"}

@app.get("/api/bot/session-info")
async def get_session_info():
    tunnel_url = get_public_tunnel_url()
    formatted = []
    for idx, acc in enumerate(state.session_accounts, 1):
        email = acc.get("email", "")
        pin = acc.get("pin", "") or ""
        formatted.append({
            "stt": idx,
            "id": acc.get("id"),
            "email": email,
            "pin": pin,
            "otpLink": f"{tunnel_url}/otp?email={urllib.parse.quote(email)}",
            "createdAt": acc.get("createdAt", "")
        })
    return {
        "ok": True,
        "sessionId": state.session_id,
        "sessionTime": state.session_time,
        "count": len(state.session_accounts),
        "accounts": formatted,
        "hasSession": len(state.session_accounts) > 0,
        "csvUrl": "/api/bot/export-session-csv",
        "excelUrl": "/api/bot/export-session-excel"
    }

SESSION_ID_REGEX = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")

@app.get("/api/bot/export-session-csv")
async def export_session_csv(session_id: Optional[str] = None):
    target_id = (session_id or state.session_id or "").strip()
    if not target_id:
        raise HTTPException(
            status_code=404,
            detail="Không có phiên làm việc hiện tại hoặc chưa chọn mã phiên."
        )
    if not SESSION_ID_REGEX.match(target_id):
        raise HTTPException(
            status_code=400,
            detail="Mã phiên không hợp lệ. Chỉ chấp nhận ký tự a-z, A-Z, 0-9, gạch ngang và gạch dưới (tối đa 64 ký tự)."
        )
    file_path = os.path.join(EXPORTS_DIR, f"muse_session_{target_id}.csv")
    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=404,
            detail=f"Không tìm thấy file CSV cho phiên '{target_id}'."
        )
    return FileResponse(
        file_path,
        media_type="text/csv; charset=utf-8",
        filename=f"muse_session_{target_id}.csv"
    )

@app.get("/api/bot/export-session-excel")
async def export_session_excel(session_id: Optional[str] = None):
    target_id = (session_id or state.session_id or "").strip()
    if not target_id:
        raise HTTPException(
            status_code=404,
            detail="Không có phiên làm việc hiện tại hoặc chưa chọn mã phiên."
        )
    if not SESSION_ID_REGEX.match(target_id):
        raise HTTPException(
            status_code=400,
            detail="Mã phiên không hợp lệ. Chỉ chấp nhận ký tự a-z, A-Z, 0-9, gạch ngang và gạch dưới (tối đa 64 ký tự)."
        )
    file_path = os.path.join(EXPORTS_DIR, f"muse_session_{target_id}.xlsx")
    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=404,
            detail=f"Không tìm thấy file Excel cho phiên '{target_id}'."
        )
    return FileResponse(
        file_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"muse_session_{target_id}.xlsx"
    )


if __name__ == "__main__":
    if "--fingerprint" in sys.argv:
        print(_compute_source_fingerprint())
        sys.exit(0)
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("BOT_SERVER_PORT", "8790")))
