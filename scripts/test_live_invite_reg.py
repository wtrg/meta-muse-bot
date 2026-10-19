import asyncio
import os
import sys
import time
import json
import re
import urllib.request
from playwright.async_api import async_playwright

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

MTEMP_API_KEY = "pub_nRn1hUwpdmZvxQNVWDfoXgKyF7dIm9nRIIIt1qDw"
MTEMP_BASE_URL = "https://mtempmail.com/api"

INVITE_CODE = "QKPLQ6"
PROXY_SERVER = "http://127.0.0.1:8085"

def log(msg):
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

async def create_email():
    url = f"{MTEMP_BASE_URL}/emails/{MTEMP_API_KEY}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}, data=b"{}")
    loop = asyncio.get_event_loop()
    def _fetch():
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode())
            return data["data"]["email"]
    return await loop.run_in_executor(None, _fetch)

async def poll_otp(email, timeout=75):
    start = time.time()
    url = f"{MTEMP_BASE_URL}/messages/{MTEMP_API_KEY}/{email}"
    loop = asyncio.get_event_loop()
    while time.time() - start < timeout:
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
            return otp
        await asyncio.sleep(2)
    raise TimeoutError("Hết thời gian chờ OTP từ Meta.")

async def main():
    log(f"=== BẮT ĐẦU TEST FLOW MÃ MỜI TỪ /invite/{INVITE_CODE} ===")
    
    email = await create_email()
    log(f"1. Tạo email sạch MX: {email}")
    
    async with async_playwright() as p:
        log("2. Khởi động Playwright Chrome qua Psiphon US...")
        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--lang=en-US,en",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-infobars",
            "--disable-webrtc",
            "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
            "--enforce-webrtc-ip-permission-check",
            "--ignore-certificate-errors",
            "--ignore-ssl-errors",
            "--allow-running-insecure-content"
        ]
        
        browser = await p.chromium.launch(
            executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            headless=True,
            proxy={"server": PROXY_SERVER},
            args=launch_args
        )
        
        context = await browser.new_context(
            locale="en-US",
            timezone_id="America/New_York",
            viewport={"width": 1280, "height": 800},
            ignore_https_errors=True,
            geolocation={"latitude": 40.7128, "longitude": -74.0060},
            permissions=["geolocation"]
        )
        
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            window.chrome = { runtime: {} };
        """)
        
        page = await context.new_page()
        
        # Intercept and log auth / hatch API calls
        async def on_res(res):
            if any(k in res.url for k in ["auth", "check", "invite", "hatch", "peer", "access"]):
                try:
                    txt = await res.text()
                    log(f"   [API {res.status}] {res.url[:70]}: {txt[:160]}")
                except Exception:
                    pass
        page.on("response", on_res)
        
        start_url = f"https://muse.ai/invite/{INVITE_CODE}"
        log(f"3. Truy cập khởi đầu: {start_url}...")
        await page.goto(start_url, wait_until="load", timeout=35000)
        await asyncio.sleep(4)
        log(f"   Trang landing: {page.url} - {await page.title()}")
        await page.screenshot(path="scripts/invite_flow_step1.png")
        
        # 1. Fill email
        log(f"4. Điền email: {email}")
        email_inp = await page.wait_for_selector('input[type="text"], input[type="email"], input[placeholder*="email" i], input', timeout=15000)
        await email_inp.fill(email)
        await asyncio.sleep(1)
        
        btn = await page.wait_for_selector('button:has-text("Continue"), button[type="submit"]')
        await btn.click()
        log("5. Đã bấm Continue, chờ màn hình OTP...")
        
        await page.wait_for_selector('text="Enter your code"', timeout=25000)
        log("6. Màn hình nhập mã xác thực đã sẵn sàng!")
        
        # 2. Poll OTP
        log("7. Chờ mã OTP 6 số từ Meta...")
        otp = await poll_otp(email)
        log(f"8. ĐÃ NHẬN MÃ OTP: {otp}!")
        
        # 3. Enter OTP
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
            
        log("9. Đã gửi OTP, chờ màn hình ngày sinh / hồ sơ...")
        await asyncio.sleep(5)
        
        # 4. Birthday & Name if present
        body_text = await page.inner_text("body")
        if "finish creating your account" in body_text.lower() or "birthday" in body_text.lower() or "first name" in body_text.lower():
            log("10. Điền Họ tên & Ngày sinh theo chuẩn Meta...")
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
                
            log("11. Đã gửi xác nhận hoàn tất tài khoản! Chờ Meta điều hướng...")
            await asyncio.sleep(6)
            
        log(f"12. URL sau khi hoàn tất đăng ký: {page.url}")
        await page.screenshot(path="scripts/invite_flow_step2_post_register.png")
        
        # 5. Check if it returned to /invite/{INVITE_CODE} or if we need to navigate there
        if f"/invite/{INVITE_CODE}" not in page.url and "/thread" not in page.url:
            log(f"13. Điều hướng chủ động đến: https://muse.ai/invite/{INVITE_CODE}...")
            try:
                await page.goto(f"https://muse.ai/invite/{INVITE_CODE}", wait_until="domcontentloaded", timeout=25000)
                await asyncio.sleep(5)
            except Exception as e:
                log(f"Lỗi khi điều hướng: {e}")
                
        await page.screenshot(path="scripts/invite_flow_step3_invite_page.png")
        log(f"14. URL hiện tại: {page.url} - {await page.title()}")
        body_invite = await page.inner_text("body")
        log(f"    Nội dung: {body_invite[:300].replace(chr(10), ' ')}")
        
        # Check buttons
        accept_btn = page.locator('button:has-text("Accept"), button:has-text("Join"), button:has-text("Continue"), button:has-text("Get started"), button:has-text("Claim")').first
        if await accept_btn.count() > 0:
            log(f"15. Tìm thấy nút: '{await accept_btn.inner_text()}', đang bấm...")
            await accept_btn.click()
            await asyncio.sleep(5)
            await page.screenshot(path="scripts/invite_flow_step4_after_btn.png")
            log(f"    URL sau khi bấm: {page.url}")
            
        # 6. Check final status
        log("16. Kiểm tra trang chính https://muse.ai...")
        try:
            await page.goto("https://muse.ai", wait_until="domcontentloaded", timeout=25000)
            await asyncio.sleep(5)
        except Exception:
            pass
            
        final_url = page.url
        final_body = await page.inner_text("body")
        await page.screenshot(path="scripts/invite_flow_step5_final.png")
        
        chat_el = await page.query_selector('textarea, [contenteditable="true"], input[placeholder*="Ask" i], input[placeholder*="goal" i], input[placeholder*="task" i]')
        is_waitlist = "waitlist" in final_body.lower() or "/access" in final_url or "isn't available" in final_body.lower()
        
        log(f"17. KẾT QUẢ: Final URL={final_url}")
        log(f"    Chat input tìm thấy: {chat_el is not None}")
        log(f"    Bị Waitlist: {is_waitlist}")
        
        if chat_el is not None and not is_waitlist:
            log("🎉🎉🎉 THÀNH CÔNG VÀO MÀN HÌNH CHAT! CHAT SẴN SÀNG! 🎉🎉🎉")
        else:
            log("    Chi tiết trạng thái xem trong ảnh invite_flow_step5_final.png")
            
        cookies = await context.cookies()
        with open("scripts/invite_flow_account.json", "w", encoding="utf-8") as f:
            json.dump({
                "email": email,
                "otp": otp,
                "url": final_url,
                "is_chat": chat_el is not None and not is_waitlist,
                "cookies": cookies
            }, f, indent=2)
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
