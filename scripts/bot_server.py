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
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from playwright.async_api import async_playwright
from muse_browser import open_muse_browser
from muse_access import inspect_muse_access, MuseAccessError
from muse_invites import normalize_invite_code, redeem_invite
from windscribe_manager import connect_free_us
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
    cmd = ["curl.exe", "-s", "--max-time", "8"]
    if norm:
        cmd.extend(["-x", norm])
    cmd.append("http://ip-api.com/json/?fields=status,message,country,countryCode,regionName,city,zip,isp,org,as,mobile,proxy,hosting,query")
    
    start_t = time.time()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        dur = round(time.time() - start_t, 2)
        if proc.returncode == 0 and proc.stdout.strip():
            data = json.loads(proc.stdout.strip())
            data["ping"] = dur
            country_code = data.get("countryCode", "").upper()
            is_us = country_code in ["US", "CA"]
            is_hosting = data.get("hosting", False)
            is_proxy = data.get("proxy", False)
            
            if not is_us:
                verdict = "NON_US"
                verdict_text = f"❌ Địa chỉ IP thuộc {data.get('country')} ({country_code}). Meta Muse CHẶN VÙNG VÀ BẮT BUỘC WAITLIST!"
            elif is_hosting or is_proxy:
                verdict = "US_DATACENTER"
                verdict_text = f"⚠️ IP Hoa Kỳ ({data.get('isp')}) nhưng là Datacenter/Proxy ASN. Rủi ro bị Meta đưa vào Danh Sách Chờ!"
            else:
                verdict = "US_RESIDENTIAL"
                verdict_text = f"✅ IP Mỹ/Canada ({data.get('isp')}, {data.get('city')}). Chưa xác minh quyền truy cập Muse."
                
            return {
                "ok": True,
                "data": data,
                "is_us": is_us,
                "verdict": verdict,
                "verdict_text": verdict_text
            }
        else:
            return {"ok": False, "error": f"Không thể kết nối qua proxy: {proc.stderr or 'Timeout/Connection error'}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


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

@app.middleware("http")
async def local_bot_origin_guard(request, call_next):
    if request.url.path.startswith("/api/bot"):
        origin = request.headers.get("origin")
        if origin and urllib.parse.urlparse(origin).hostname not in ("127.0.0.1", "localhost", "::1"):
            return JSONResponse({"detail": "Bot controls are local-only."}, status_code=403)
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
            # Only put SUCCESS_CHAT_READY accounts into session_accounts
            ready = [a for a in state.accounts if a.get("status") == "SUCCESS_CHAT_READY"]
            if ready:
                state.session_accounts = ready[:min(len(ready), 4)]
                state.session_id = time.strftime("%Y%m%d_%H%M%S")
                state.session_time = time.strftime("%Y-%m-%d %H:%M:%S")
            else:
                state.session_accounts = []
    except Exception:
        state.accounts = []

def get_public_tunnel_url() -> str:
    tasks_dir = r"C:\Users\Lenovo\.gemini\antigravity\brain\f255b251-14c8-43b0-af0e-b9c0788ab043\.system_generated\tasks"
    if os.path.exists(tasks_dir):
        try:
            files = sorted(
                [os.path.join(tasks_dir, f) for f in os.listdir(tasks_dir) if f.endswith(".log")],
                key=os.path.getmtime,
                reverse=True
            )
            for fpath in files:
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        matches = re.findall(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", f.read())
                        if matches:
                            return matches[0]
                except Exception:
                    pass
        except Exception:
            pass
    return "https://genome-theater-voip-benz.trycloudflare.com"

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
            pin = acc.get("otp", "") or acc.get("pin", "")
            otp_link = f"{tunnel_url}/otp?email={urllib.parse.quote(email)}&pin={urllib.parse.quote(pin)}"
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
            pin = acc.get("otp", "") or acc.get("pin", "")
            otp_link = f"{tunnel_url}/otp?email={urllib.parse.quote(email)}&pin={urllib.parse.quote(pin)}"
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
        pin = acc.get("otp", "") or acc.get("pin", "")
        otp_link = f"{tunnel_url}/otp?email={urllib.parse.quote(email)}&pin={urllib.parse.quote(pin)}"
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

def add_log(message: str, level: str = "info", progress: Optional[int] = None):
    entry = {
        "time": time.strftime("%H:%M:%S"),
        "message": message,
        "level": level,
        "progress": progress
    }
    state.logs.append(entry)
    if len(state.logs) > 500:
        state.logs = state.logs[-500:]
    state.current_step = message
    print(f"[{entry['time']}] [{level.upper()}] {message}")

class StartBotRequest(BaseModel):
    count: int = 1
    proxy: Optional[str] = None
    proxyType: Optional[str] = "psiphon"  # "psiphon", "vpn", "custom", "auto"
    visible: bool = True
    provider: str = "clean_tempmail"  # "clean_tempmail" or "spinupmail"
    domain: str = "maxxspace.com"
    inviteCode: Optional[str] = "QKPLQ6"

async def create_clean_email() -> str:
    add_log("Đang tạo email từ Clean TempMail Engine (vượt kiểm duyệt MX của Meta)...", "info", 10)
    url = f"{MTEMP_BASE_URL}/emails/{MTEMP_API_KEY}"
    loop = asyncio.get_event_loop()
    def _fetch():
        em = ""
        for _ in range(15):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}, data=b"{}")
                with urllib.request.urlopen(req, timeout=12) as resp:
                    data = json.loads(resp.read().decode())
                    candidate = data.get("data", {}).get("email", "")
                    domain = candidate.split("@")[-1].lower() if "@" in candidate else ""
                    # Enforce global TLD (.com, .net, .org) and reject country-code TLDs (.pl, .vn, .ru, etc.)
                    if (domain.endswith(".com") or domain.endswith(".net") or domain.endswith(".org")) and not (domain.endswith(".pl") or domain.endswith(".vn") or domain.endswith(".ru")):
                        return candidate
            except Exception:
                pass
            time.sleep(0.5)
        return em
    email = await loop.run_in_executor(None, _fetch)
    add_log(f"Đã tạo Clean TempMail (Global Domain): {email}", "success", 20)
    return email

async def poll_clean_otp(email: str, timeout_seconds: int = 75) -> str:
    add_log("Đang chờ Meta gửi mã OTP xác thực...", "info", 50)
    start = time.time()
    url = f"{MTEMP_BASE_URL}/messages/{MTEMP_API_KEY}/{email}"
    loop = asyncio.get_event_loop()
    while time.time() - start < timeout_seconds:
        if state.stop_requested:
            raise Exception("Đã bấm dừng bot")
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
                            digits = re.findall(r"\b\d{6}\b", subj + " " + body)
                            if digits:
                                return digits[0]
            except Exception:
                pass
            return None
        otp = await loop.run_in_executor(None, _check)
        if otp:
            add_log(f"ĐÃ NHẬN MÃ OTP TỪ META: {otp}!", "success", 65)
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

async def poll_spinup_otp(email: str, pin: str, timeout_seconds: int = 75) -> str:
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
            raise Exception("Đã bấm dừng bot")
        data = await loop.run_in_executor(None, _check)
        if data and data.get("ok") and data.get("hasEmails"):
            latest = data.get("latest", {})
            otp = latest.get("otp")
            if otp:
                add_log(f"ĐÃ NHẬN MÃ OTP TỪ META: {otp}!", "success", 65)
                return otp
        await asyncio.sleep(2)
    raise TimeoutError("Hết thời gian chờ OTP từ Meta.")

async def process_single_account(proxy_str: Optional[str], visible: bool, provider: str, domain: str, inviteCode: Optional[str] = "QKPLQ6") -> Dict[str, Any]:
    pin = ""
    if provider == "clean_tempmail":
        email = await create_clean_email()
    else:
        email, pin = await create_spinup_email(domain)
    
    proxy_config = to_playwright_proxy(proxy_str)
    if proxy_config:
        add_log(f"Cấu hình Proxy: {proxy_config['server']}", "info")
    else:
        add_log("Sử dụng mạng máy chủ / VPN trên máy tính", "info")
        
    # Pre-flight check exit IP route
    route_res = check_route_ip(proxy_str)
    if route_res.get("ok"):
        ip_info = route_res.get("data", {})
        ip_addr = ip_info.get("query", "Unknown")
        country = ip_info.get("country", "")
        country_code = ip_info.get("countryCode", "")
        isp_name = ip_info.get("isp", "")
        is_us = route_res.get("is_us", False)
        add_log(f"Kiểm tra IP kết nối: {ip_addr} ({country} - {isp_name})", "info", 15)
        
        if not is_us:
            err_msg = f"CHẶN VÙNG: IP kết nối là {ip_addr} ({country} - {isp_name}), không thuộc Hoa Kỳ/Canada! Meta Muse sẽ lập tức đưa tài khoản vào Waitlist. Hủy tạo để bảo vệ email."
            add_log(f"❌ {err_msg}", "error", 100)
            raise Exception(err_msg)
    else:
        add_log(f"Cảnh báo kiểm tra IP: {route_res.get('error')}", "warning", 15)

    async with async_playwright() as p:
        add_log("Đang khởi động trình duyệt tự động...", "info", 25)
        
        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--lang=en-US,en",
            "--disable-dev-shm-usage",
            "--disable-infobars",
            "--disable-webrtc",
            "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
            "--enforce-webrtc-ip-permission-check",
        ]
        
        browser = await p.chromium.launch(
            executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            headless=not visible,
            proxy=proxy_config,
            args=launch_args
        )
        
        context = await browser.new_context(
            locale="en-US",
            timezone_id="America/New_York",
            viewport={"width": 1280, "height": 800},
            geolocation={"latitude": 40.7128, "longitude": -74.0060},
            permissions=["geolocation"]
        )
        
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            window.chrome = { runtime: {} };
        """)
        
        page = await context.new_page()
        
        clean_invite = normalize_invite_code(inviteCode)
        start_url = "https://muse.ai/"
        add_log(f"Đang truy cập {start_url}...", "info", 30)
        try:
            await page.goto(start_url, wait_until="load", timeout=30000)
        except Exception:
            await page.goto(start_url, timeout=30000)
            
        page_title = await page.title()
        add_log(f"Đã mở trang: {page_title}", "info", 35)
        
        # 1. Fill email
        add_log(f"Đang điền email: {email}...", "info", 40)
        email_inp = await page.wait_for_selector('input[type="text"], input[type="email"], input[placeholder*="email" i], input', timeout=15000)
        await email_inp.fill(email)
        await asyncio.sleep(0.5)
        
        continue_btn = await page.query_selector('button:has-text("Continue"), button[type="submit"]')
        if continue_btn:
            await continue_btn.click()
        else:
            await page.keyboard.press("Enter")
            
        add_log("Đã gửi email đăng ký, chờ màn hình OTP...", "info", 45)
        
        # 2. Wait for code screen
        await page.wait_for_selector('text="Enter your code"', timeout=20000)
        add_log("Màn hình nhập mã xác thực đã sẵn sàng!", "info", 48)
        
        # 3. Wait for OTP from Meta
        if provider == "clean_tempmail":
            otp = await poll_clean_otp(email)
        else:
            otp = await poll_spinup_otp(email, pin)
        
        # 4. Fill OTP
        add_log(f"Đang tự động nhập mã OTP: {otp} vào Muse.ai...", "info", 70)
        otp_inp = await page.wait_for_selector('input[aria-label*="code" i], input[maxlength="6"], input[type="text"]', timeout=10000)
        try:
            await otp_inp.focus()
        except Exception:
            await otp_inp.click(force=True)
            
        await asyncio.sleep(0.5)
        await page.keyboard.type(str(otp), delay=150)
        await asyncio.sleep(1.5)
        
        confirm_btn = await page.query_selector('button:has-text("Confirm"), button[type="submit"]')
        if confirm_btn:
            try:
                await confirm_btn.click(force=True)
            except Exception:
                await page.keyboard.press("Enter")
        else:
            await page.keyboard.press("Enter")
            
        add_log("Đã xác nhận OTP, chờ kiểm tra hồ sơ...", "info", 80)
        await asyncio.sleep(4)
        
        # 5. Check if Name & Birthday screen
        body_text = await page.inner_text("body")
        if "finish creating your account" in body_text.lower() or "birthday" in body_text.lower() or "first name" in body_text.lower():
            add_log("Đang tự động điền Họ tên và Ngày sinh theo chuẩn Meta...", "info", 85)
            text_inps = [i for i in await page.query_selector_all("input") if (await i.get_attribute("type") or "text") not in ["hidden", "checkbox", "radio"]]
            if len(text_inps) >= 2:
                await text_inps[0].click()
                await page.keyboard.type("Alex", delay=50)
                await asyncio.sleep(0.2)
                await text_inps[1].click()
                await page.keyboard.type("Miller", delay=50)
                await asyncio.sleep(0.2)
                
            try:
                await page.locator("select").nth(0).select_option(index=8)
                await page.locator("select").nth(1).select_option(label="15")
                await page.locator("select").nth(2).select_option(label="1996")
            except Exception:
                pass
                
            await asyncio.sleep(1)
            finish_btn = page.locator('button:has-text("Confirm"), button:has-text("Save"), button:has-text("Continue")').first
            if await finish_btn.count() > 0:
                await finish_btn.click()
            else:
                await page.keyboard.press("Enter")
                
            add_log("Đang chờ Meta hoàn tất đăng ký tài khoản...", "info", 90)
            await asyncio.sleep(6)
            
        # 7. Strict Verification: Check if account entered chat or got waitlisted
        add_log("Đang kiểm tra quyền truy cập vào màn hình Chat Muse.ai...", "info", 94)
        try:
            if "/thread" not in page.url:
                await page.goto("https://muse.ai/thread/new", wait_until="domcontentloaded", timeout=25000)
                await asyncio.sleep(4)
        except Exception:
            pass

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
                "pin": pin,
                "otp": otp,
                "url": current_url,
                "title": await page.title(),
                "screenshot": screenshot_filename,
                "hatch_sess": hatch_sess[:40] + "..." if hatch_sess else "Có",
                "cookies": cookies,
                "proxy_used": proxy_str or "Không dùng",
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
        invitation = {"code": clean_invite, "status": "NOT_REQUESTED", "message": "Không yêu cầu mã mời."}
        if clean_invite:
            add_log(f"Đã vào chat. Đang đổi mã {clean_invite} trong Cài đặt...", "info", 96)
            try:
                invitation = await redeem_invite(page, clean_invite)
            except Exception:
                invitation = {"code": clean_invite, "status": "UNVERIFIED", "message": "Chưa hoàn tất thao tác đổi mã trong Cài đặt."}
            add_log(invitation["message"], "success" if invitation["status"] == "REDEEMED" else "warning", 98)
        account_data = {
            "id": f"muse_{timestamp_str}",
            "email": email,
            "provider": provider,
            "pin": pin,
            "otp": otp,
            "url": current_url,
            "title": await page.title(),
            "screenshot": screenshot_filename,
            "hatch_sess": hatch_sess[:40] + "..." if hatch_sess else "Có",
            "cookies": cookies,
            "proxy_used": proxy_str or "Không dùng",
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
    state.stop_requested = False
    state.session_accounts = []
    state.session_id = time.strftime("%Y%m%d_%H%M%S")
    state.session_time = time.strftime("%Y-%m-%d %H:%M:%S")
    add_log(f"Bắt đầu phiên tạo {req.count} tài khoản Muse.ai ({req.provider})...", "info", 0)
    
    # Tự động bật đường hầm Psiphon US ngầm nếu chọn Psiphon (hoặc mặc định)
    if req.proxyType == "windscribe":
        add_log("Đang kết nối Windscribe bằng CLI chính thức (gói hiện có, không nâng cấp)...", "info", 3)
        vpn_result = await asyncio.to_thread(connect_free_us)
        if not vpn_result.get("ok"):
            add_log(vpn_result.get("error", "Chưa kết nối được Windscribe"), "error", 100)
            state.is_running = False
            return
        req.proxy = None
        add_log("Đã xác minh kết nối Windscribe Mỹ/Canada.", "info", 8)
    elif req.proxyType == "psiphon" or (not req.proxy and req.proxyType not in ["vpn", "custom", "windscribe"]):
        add_log("🚀 Tự động kích hoạt đường hầm Psiphon US ngầm trên máy...", "info", 3)
        loop = asyncio.get_event_loop()
        psi_res = await loop.run_in_executor(None, start_psiphon_tunnel, 25)
        if not psi_res or not psi_res.get("ok") or not psi_res.get("is_us"):
            err_msg = (psi_res or {}).get("error", "Không thể khởi động đường hầm Psiphon US")
            add_log(f"❌ {err_msg}", "error", 100)
            state.is_running = False
            return
        req.proxy = psi_res.get("proxy", "http://127.0.0.1:8085")
        psi_info = psi_res.get("data", {})
        add_log(f"✅ Đường hầm Psiphon US đã sẵn sàng! IP: {psi_info.get('query')} ({psi_info.get('city')}, US - {psi_info.get('isp')})", "success", 8)
    elif req.proxyType == "auto" and not req.proxy:
        req.proxy = "socks5://193.25.215.182:22222"
        
    success_count = 0
    for i in range(req.count):
        if state.stop_requested:
            add_log("Đã dừng quy trình theo yêu cầu.", "warning")
            break
            
        add_log(f"--- Đang tạo tài khoản {i + 1}/{req.count} ---", "info")
        try:
            acc = await process_single_account(req.proxy, req.visible, req.provider, req.domain, req.inviteCode)
            if acc and acc.get("status") == "SUCCESS_CHAT_READY" and acc.get("requirementsComplete", False):
                state.session_accounts.append(acc)
                success_count += 1
                save_session_csv_and_excel(state.session_accounts, state.session_id)
            elif acc and acc.get("status") == "SUCCESS_CHAT_READY":
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
        
    state.is_running = False
    add_log(f"Kết thúc phiên: {success_count}/{req.count} tài khoản hoàn tất yêu cầu chat và mã mời.", "success" if success_count == req.count else "warning" if success_count else "error", 100)

@app.post("/api/bot/start")
async def start_bot(req: StartBotRequest, bg_tasks: BackgroundTasks):
    if state.is_running:
        raise HTTPException(status_code=400, detail="Bot đang chạy, vui lòng chờ hoặc bấm dừng.")
    try:
        normalize_invite_code(req.inviteCode)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
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

@app.get("/api/bot/accounts")
async def get_accounts():
    if os.path.exists(ACCOUNTS_FILE):
        try:
            with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                state.accounts = json.load(f)
        except Exception:
            pass
    return {
        "ok": True,
        "count": len(state.accounts),
        "accounts": state.accounts
    }

@app.delete("/api/bot/accounts")
async def clear_accounts():
    state.accounts = []
    save_accounts()
    return {"ok": True, "message": "Đã xóa lịch sử tài khoản"}

@app.get("/api/bot/screenshot/{filename}")
async def get_screenshot(filename: str):
    path = os.path.join(SCREENSHOTS_DIR, filename)
    if os.path.exists(path):
        return FileResponse(path, media_type="image/png")
    fallback = os.path.join(os.path.dirname(__file__), filename)
    if os.path.exists(fallback):
        return FileResponse(fallback, media_type="image/png")
    raise HTTPException(status_code=404, detail="Screenshot not found")

async def ensure_free_tunnel():
    result = await asyncio.get_running_loop().run_in_executor(None, start_psiphon_tunnel, 25)
    if not result or not result.get("ok") or not result.get("is_us"):
        raise HTTPException(status_code=503, detail=(result or {}).get("error", "Chưa xác minh được kết nối Mỹ/Canada."))
    return result


@app.post("/api/bot/open-muse")
async def open_muse():
    result = await ensure_free_tunnel()
    try:
        url = await open_muse_browser(to_playwright_proxy(result["proxy"]))
    except Exception:
        raise HTTPException(status_code=502, detail="Không mở được Muse qua đường hầm. Kiểm tra kết nối hoặc Chrome rồi thử lại.")
    return {"ok": True, "url": url, "message": "Đã mở Muse qua Psiphon miễn phí. Bạn có thể đăng nhập tài khoản của mình; quyền truy cập do Muse quyết định."}


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
    if proxy_val and any(port in proxy_val for port in ("127.0.0.1:8085", "127.0.0.1:1085", "127.0.0.1:8086", "127.0.0.1:1086")):
        result = await ensure_free_tunnel()
        proxy_val = result["proxy"]
    if proxy_val in ("Không dùng", "", None):
        proxy_val = None
    try:
        url = await open_muse_browser(to_playwright_proxy(proxy_val), acc.get("cookies", []))
    except Exception:
        raise HTTPException(status_code=502, detail="Không mở được phiên Muse. Kiểm tra kết nối hoặc Chrome rồi thử lại.")
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
    tunnel = await ensure_free_tunnel()
    try:
        result = await open_muse_browser(to_playwright_proxy(tunnel["proxy"]), acc.get("cookies", []), verify_access=True)
    except Exception:
        raise HTTPException(status_code=502, detail="Không tải được Muse để kiểm tra. Chưa thay đổi kết quả tài khoản.")
    acc.update(status=result["status"], error=result["message"], url=result["url"],
               cookies=result["cookies"], proxy_used=tunnel["proxy"])
    save_accounts()
    return {"ok": True, "status": result["status"], "message": result["message"]}


class CheckProxyRequest(BaseModel):
    proxy: Optional[str] = None
    proxyType: Optional[str] = "psiphon"

@app.post("/api/bot/check-proxy-health")
async def check_proxy_health(req: CheckProxyRequest):
    p_str = req.proxy
    if req.proxyType == "psiphon":
        alive = await asyncio.to_thread(is_psiphon_alive)
        if not alive:
            loop = asyncio.get_event_loop()
            alive = await loop.run_in_executor(None, start_psiphon_tunnel, 25)
        if alive and alive.get("ok"):
            p_str = alive.get("proxy", "http://127.0.0.1:8085")
        else:
            return {"ok": False, "error": alive.get("error", "Không thể khởi động Psiphon Tunnel")}
    elif req.proxyType == "vpn":
        p_str = None
    elif req.proxyType == "auto" and not p_str:
        active_path = os.path.join(os.path.dirname(__file__), "active_us_proxy.json")
        if os.path.exists(active_path):
            try:
                with open(active_path, "r", encoding="utf-8") as f:
                    p_str = json.load(f).get("proxy")
            except Exception:
                pass
        if not p_str:
            p_str = "socks5://193.25.215.182:22222"
            
    res = await asyncio.to_thread(check_route_ip, p_str)
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
    try:
        if os.path.exists(active_path):
            with open(active_path, "r", encoding="utf-8") as f:
                data = json.load(f)
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
        "ok": True,
        "proxy": "socks5://193.25.215.182:22222",
        "ip": "193.25.215.182",
        "isp": "ReadyDedis, LLC",
        "region": "Los Angeles, California, US",
        "ping": 0.91
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
        pin = acc.get("otp", "") or acc.get("pin", "")
        formatted.append({
            "stt": idx,
            "id": acc.get("id"),
            "email": email,
            "pin": pin,
            "otpLink": f"{tunnel_url}/otp?email={urllib.parse.quote(email)}&pin={urllib.parse.quote(pin)}",
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

@app.get("/api/bot/export-session-csv")
async def export_session_csv(session_id: Optional[str] = None):
    target_id = session_id or state.session_id
    file_path = None
    if target_id:
        file_path = os.path.join(EXPORTS_DIR, f"muse_session_{target_id}.csv")
    if not file_path or not os.path.exists(file_path):
        file_path = os.path.join(EXPORTS_DIR, "muse_session_latest.csv")
    if not os.path.exists(file_path):
        save_session_csv_and_excel(state.session_accounts, state.session_id)
        file_path = os.path.join(EXPORTS_DIR, "muse_session_latest.csv")
        
    if os.path.exists(file_path):
        fname = f"muse_session_{state.session_id or 'latest'}.csv"
        return FileResponse(
            file_path,
            media_type="text/csv; charset=utf-8",
            filename=fname
        )
    raise HTTPException(status_code=404, detail="Chưa có file CSV phiên này.")

@app.get("/api/bot/export-session-excel")
async def export_session_excel(session_id: Optional[str] = None):
    target_id = session_id or state.session_id
    file_path = None
    if target_id:
        file_path = os.path.join(EXPORTS_DIR, f"muse_session_{target_id}.xlsx")
    if not file_path or not os.path.exists(file_path):
        file_path = os.path.join(EXPORTS_DIR, "muse_session_latest.xlsx")
    if not os.path.exists(file_path):
        save_session_csv_and_excel(state.session_accounts, state.session_id)
        file_path = os.path.join(EXPORTS_DIR, "muse_session_latest.xlsx")
        
    if os.path.exists(file_path):
        fname = f"muse_session_{state.session_id or 'latest'}.xlsx"
        return FileResponse(
            file_path,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=fname
        )
    raise HTTPException(status_code=404, detail="Chưa có file Excel phiên này.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("BOT_SERVER_PORT", "8790")))
