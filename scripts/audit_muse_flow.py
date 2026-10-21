import time
import json
import urllib.request
import urllib.parse
from playwright.sync_api import sync_playwright
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

BACKEND_URL = "http://127.0.0.1:8787"

def create_mail():
    raise NotImplementedError(
        "Cổng tạo email công khai ẩn danh (/api/public/bulk-create) đã bị gỡ bỏ theo khuyến nghị bảo mật A04. "
        "Vui lòng quản lý hộp thư qua giao diện có xác thực hoặc sử dụng Clean TempMail."
    )

def poll_otp(email, pin):
    start = time.time()
    while time.time() - start < 90:
        try:
            url = f"{BACKEND_URL}/api/public/otp?email={urllib.parse.quote(email)}&pin={urllib.parse.quote(pin)}"
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                if data.get("ok") and data.get("hasEmails"):
                    otp = data.get("latest", {}).get("otp")
                    if otp: return otp
        except Exception:
            pass
        time.sleep(2)
    raise TimeoutError("OTP timeout")

def audit():
    email, pin = create_mail()
    print(f"[AUDIT] Test email: {email}")

    network_logs = []
    js_urls = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--lang=en-US,en",
                "--no-sandbox"
            ]
        )
        context = browser.new_context(
            locale="en-US",
            timezone_id="America/New_York",
            geolocation={"latitude": 40.7128, "longitude": -74.0060},
            permissions=["geolocation"],
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        def on_request(req):
            if "api" in req.url or "auth" in req.url:
                try:
                    network_logs.append({
                        "type": "REQUEST",
                        "url": req.url,
                        "method": req.method,
                        "headers": req.headers,
                        "post_data": req.post_data
                    })
                except: pass

        def on_response(res):
            if ".js" in res.url:
                js_urls.append(res.url)
            if "api" in res.url or "auth" in res.url:
                try:
                    text = res.text()
                    network_logs.append({
                        "type": "RESPONSE",
                        "url": res.url,
                        "status": res.status,
                        "headers": res.headers,
                        "body": text
                    })
                except: pass

        page.on("request", on_request)
        page.on("response", on_response)

        page.goto("https://muse.ai", timeout=35000)
        time.sleep(2)

        email_inp = page.wait_for_selector('input[placeholder*="email" i], input', timeout=15000)
        email_inp.fill(email)
        time.sleep(1)
        btn = page.query_selector('button:has-text("Continue"), button[type="submit"]')
        if btn: btn.click()
        else: page.keyboard.press("Enter")

        page.wait_for_selector('text="Enter your code"', timeout=25000)
        otp = poll_otp(email, pin)
        print(f"[AUDIT] Received OTP: {otp}")

        otp_inp = page.wait_for_selector('input[aria-label*="code" i], input[maxlength="6"]', timeout=10000)
        try: otp_inp.focus()
        except: otp_inp.click(force=True)
        time.sleep(0.5)
        page.keyboard.type(str(otp), delay=150)
        time.sleep(1.5)

        confirm_btn = page.query_selector('button:has-text("Confirm"), button[type="submit"]')
        if confirm_btn: confirm_btn.click(force=True)
        else: page.keyboard.press("Enter")

        time.sleep(4)
        body = page.inner_text("body")
        print("[AUDIT] Post-OTP screen detected:")
        print(body[:300])

        all_inps = page.query_selector_all("input")
        text_inps = [i for i in all_inps if (i.get_attribute("type") or "text") not in ["hidden", "checkbox", "radio"]]
        if len(text_inps) >= 2:
            print(" -> Typing First name: Alex...")
            text_inps[0].click()
            time.sleep(0.2)
            page.keyboard.press("Control+A")
            page.keyboard.press("Backspace")
            page.keyboard.type("Alex", delay=80)
            time.sleep(0.3)

            print(" -> Typing Last name: Miller...")
            text_inps[1].click()
            time.sleep(0.2)
            page.keyboard.press("Control+A")
            page.keyboard.press("Backspace")
            page.keyboard.type("Miller", delay=80)
            time.sleep(0.3)

        try:
            page.locator('select').nth(0).select_option(index=8)
            time.sleep(0.5)
            page.locator('select').nth(1).select_option(label="15")
            time.sleep(0.5)
            page.locator('select').nth(2).select_option(label="1996")
            time.sleep(0.5)
        except Exception as e:
            print("Select error:", e)

        print("[AUDIT] Submitting confirmation...")
        finish = page.locator('button:has-text("Confirm"), button:has-text("Save"), button:has-text("Continue")').first
        if finish.count() > 0: finish.click()
        else: page.keyboard.press("Enter")

        time.sleep(8)

        # Dump network logs
        with open("scripts/audit_network_dump.json", "w", encoding="utf-8") as f:
            json.dump(network_logs, f, indent=2, ensure_ascii=False)

        with open("scripts/audit_js_urls.json", "w", encoding="utf-8") as f:
            json.dump(js_urls, f, indent=2)

        print(f"[AUDIT] Dumped {len(network_logs)} network calls to scripts/audit_network_dump.json")
        browser.close()

if __name__ == "__main__":
    audit()
