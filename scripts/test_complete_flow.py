import time
import json
import urllib.request
import urllib.parse
from playwright.sync_api import sync_playwright

BACKEND_URL = "http://127.0.0.1:8787"

def create_email():
    print("[1/5] Creating new live email on backend...")
    req_data = json.dumps({
        "count": 1,
        "prefix": "muse_auto",
        "domain": "maxxspace.com"
    }).encode("utf-8")
    
    req = urllib.request.Request(
        f"{BACKEND_URL}/api/public/bulk-create",
        data=req_data,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        if res.get("ok") and res.get("items"):
            item = res["items"][0]
            print(f" -> Created email: {item['address']}, PIN: {item['pin']}")
            return item["address"], item["pin"]
        else:
            raise Exception(f"Failed to create email: {res}")

def wait_for_otp(email, pin, timeout_seconds=60):
    print(f"[3/5] Polling for OTP from Meta for {email}...")
    start = time.time()
    while time.time() - start < timeout_seconds:
        url = f"{BACKEND_URL}/api/public/otp?email={urllib.parse.quote(email)}&pin={urllib.parse.quote(pin)}"
        try:
            with urllib.request.urlopen(url) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("ok") and data.get("hasEmails") and data.get("latest", {}).get("otp"):
                    otp = data["latest"]["otp"]
                    print(f" -> RECEIVED OTP FROM META: {otp}!")
                    return otp
        except Exception as e:
            pass
        time.sleep(2)
        print("    ...still waiting for Meta to send OTP...")
    raise TimeoutError("Timed out waiting for OTP from Meta.")

def run():
    email, pin = create_email()
    
    with sync_playwright() as p:
        print("[2/5] Launching stealth Chrome browser with US Geo-spoofing...")
        browser = p.chromium.launch(
            executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--lang=en-US,en",
                "--no-sandbox",
                "--disable-dev-shm-usage"
            ]
        )
        context = browser.new_context(
            locale="en-US",
            timezone_id="America/New_York",
            geolocation={"latitude": 40.7128, "longitude": -74.0060},
            permissions=["geolocation"],
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        )
        
        # Anti-detect script
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
        """)
        
        page = context.new_page()
        print(" -> Navigating to https://muse.ai...")
        page.goto("https://muse.ai", wait_until="networkidle", timeout=30000)
        
        print(f" -> Entering email: {email}...")
        email_inp = page.wait_for_selector('input[type="text"], input[type="email"], input[placeholder*="email" i]', timeout=10000)
        email_inp.fill(email)
        time.sleep(1)
        
        continue_btn = page.query_selector('button:has-text("Continue"), button[type="submit"]')
        continue_btn.click()
        
        print(" -> Waiting for 'Enter your code' screen...")
        page.wait_for_selector('text="Enter your code"', timeout=15000)
        print(" -> Code screen appeared!")
        
        # Wait for OTP from our live mail system
        otp = wait_for_otp(email, pin)
        
        print(f"[4/5] Typing OTP {otp} into Muse...")
        otp_inp = page.wait_for_selector('input[aria-label*="code" i], input[maxlength="6"]', timeout=10000)
        otp_inp.fill(otp)
        time.sleep(1)
        
        print(" -> Clicking Confirm...")
        confirm_btn = page.query_selector('button:has-text("Confirm")')
        confirm_btn.click()
        
        time.sleep(5)
        print(f"[5/5] After Confirm URL: {page.url}")
        print(f" -> Page title: {page.title()}")
        body_sample = page.inner_text("body")[:800]
        print(f" -> Body sample:\n{body_sample}")
        
        page.screenshot(path="scripts/after_confirm.png")
        print(" -> Saved screenshot to scripts/after_confirm.png")
        
        # Check if birthday or error or success
        if "Bạn hiện không thể tạo tài khoản" in body_sample or "You can't create an account right now" in body_sample:
            print("\n[RESULT] Blocked by Meta IP anti-fraud (Cần proxy US sạch)")
        elif "birth" in body_sample.lower() or "ngày sinh" in body_sample.lower() or "hoàn tất" in body_sample.lower():
            print("\n[RESULT] Reached Birthday / Completion Step!")
        else:
            print("\n[RESULT] Current state:", page.url)
            
        browser.close()

if __name__ == "__main__":
    run()
