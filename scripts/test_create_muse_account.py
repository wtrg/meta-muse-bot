import time
import json
import sys
import urllib.request
import urllib.parse
from playwright.sync_api import sync_playwright

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass


BACKEND_URL = "http://127.0.0.1:8787"

def create_mail():
    print("[1] Generating email on backend...")
    req_data = json.dumps({
        "count": 1,
        "prefix": "muse_pro",
        "domain": "maxxspace.com"
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{BACKEND_URL}/api/public/bulk-create",
        data=req_data,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        item = res["items"][0]
        print(f" -> Created email: {item['address']} (PIN: {item['pin']})")
        return item["address"], item["pin"]

def poll_otp(email, pin, timeout=90):
    print(f"[3] Polling for OTP from Meta for {email}...")
    start = time.time()
    while time.time() - start < timeout:
        url = f"{BACKEND_URL}/api/public/otp?email={urllib.parse.quote(email)}&pin={urllib.parse.quote(pin)}"
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("ok") and data.get("hasEmails"):
                    otp = data.get("latest", {}).get("otp")
                    if otp:
                        print(f" -> RECEIVED OTP FROM META: {otp}!")
                        return otp
        except Exception:
            pass
        time.sleep(2)
        print("    ...waiting for Meta email...")
    raise TimeoutError("OTP timeout")

def run_test():
    email, pin = create_mail()
    
    with sync_playwright() as p:
        print("[2] Launching Chrome Stealth...")
        browser = p.chromium.launch(
            executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            headless=False, # visible so we can watch
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
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            ignore_https_errors=True
        )
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
        """)
        page = context.new_page()
        
        print(" -> Opening https://muse.ai...")
        page.goto("https://muse.ai", timeout=35000)
        time.sleep(2)
        
        print(f" -> Typing email: {email}...")
        email_inp = page.wait_for_selector('input[type="text"], input[type="email"], input[placeholder*="email" i]', timeout=15000)
        email_inp.fill(email)
        time.sleep(1)
        
        btn = page.query_selector('button:has-text("Continue"), button[type="submit"]')
        if btn:
            btn.click()
        else:
            page.keyboard.press("Enter")
            
        print(" -> Waiting for 'Enter your code' screen...")
        page.wait_for_selector('text="Enter your code"', timeout=25000)
        print(" -> Code screen is visible!")
        
        otp = poll_otp(email, pin)
        
        print(f"[4] Entering OTP {otp} into Muse...")
        otp_inp = page.wait_for_selector('input[aria-label*="code" i], input[maxlength="6"]', timeout=10000)
        try:
            otp_inp.focus()
        except Exception:
            otp_inp.click(force=True)
            
        time.sleep(0.5)
        page.keyboard.type(str(otp), delay=150)
        time.sleep(1.5)
        
        confirm_btn = page.query_selector('button:has-text("Confirm"), button[type="submit"]')
        if confirm_btn:
            try:
                confirm_btn.click(force=True)
            except Exception:
                page.keyboard.press("Enter")
        else:
            page.keyboard.press("Enter")
            
        print("[5] Waiting for post-OTP response...")
        time.sleep(5)
        
        page.screenshot(path="scripts/muse_after_otp.png")
        print(" -> Screenshot after OTP saved to scripts/muse_after_otp.png")
        
        body = page.inner_text("body")
        print("Page URL:", page.url)
        print("Body preview:\n", body[:600])
        
        def handle_response(resp):
            if "graphql" in resp.url or "register" in resp.url or "account" in resp.url:
                try:
                    text = resp.text()
                    if "error" in text.lower() or "wrong" in text.lower() or "success" in text.lower():
                        print(f"[NETWORK {resp.status}] {resp.url[:80]}\n{text[:400]}")
                except Exception:
                    pass
        page.on("response", handle_response)

        # Check if Finish account / birthday screen
        if "finish creating your account" in body.lower() or "birthday" in body.lower() or "ngày sinh" in body.lower():
            print(" -> Detected 'Finish creating your account' screen! Filling names & date...")
            # 1. Print and fill First name & Last name
            all_inps = page.query_selector_all("input")
            print(f"Total inputs on Finish screen: {len(all_inps)}")
            text_inps = []
            for idx, inp in enumerate(all_inps):
                itype = inp.get_attribute("type") or "text"
                iph = inp.get_attribute("placeholder") or ""
                iaria = inp.get_attribute("aria-label") or ""
                iname = inp.get_attribute("name") or ""
                print(f"Input #{idx}: type={itype}, ph='{iph}', aria='{iaria}', name='{iname}'")
                if itype not in ["hidden", "checkbox", "radio"]:
                    text_inps.append(inp)
            
            if len(text_inps) >= 2:
                print(" -> Typing First name: Alex with keyboard...")
                text_inps[0].click()
                time.sleep(0.2)
                page.keyboard.press("Control+A")
                page.keyboard.press("Backspace")
                page.keyboard.type("Alex", delay=80)
                time.sleep(0.3)
                
                print(" -> Typing Last name: Miller with keyboard...")
                text_inps[1].click()
                time.sleep(0.2)
                page.keyboard.press("Control+A")
                page.keyboard.press("Backspace")
                page.keyboard.type("Miller", delay=80)
                time.sleep(0.3)

            # 2. Selects for Month, Day, Year using locator to avoid stale elements
            try:
                page.locator('select').nth(0).select_option(index=8) # August
                time.sleep(0.5)
            except Exception as e:
                print("Month select:", e)
                
            try:
                page.locator('select').nth(1).select_option(label="15")
                time.sleep(0.5)
            except Exception as e:
                print("Day select:", e)

            try:
                page.locator('select').nth(2).select_option(label="1996")
                time.sleep(0.5)
            except Exception as e:
                print("Year select:", e)

            time.sleep(1)
            page.screenshot(path="scripts/muse_before_confirm.png")
            print(" -> Screenshot before Confirm saved to scripts/muse_before_confirm.png")

            # 3. Click Confirm button
            finish = page.locator('button:has-text("Confirm"), button:has-text("Xác nhận"), button:has-text("Save"), button:has-text("Continue")').first
            if finish.count() > 0:
                print(" -> Clicking Confirm button...")
                finish.click()
            else:
                page.keyboard.press("Enter")
                
            print(" -> Waiting for dashboard/app redirect...")
            time.sleep(12)

            page.screenshot(path="scripts/muse_final.png")
            print(" -> Screenshot after birthday saved to scripts/muse_final.png")
            print("Final URL:", page.url)
            print("Final body preview:\n", page.inner_text("body")[:600])
            
        cookies = context.cookies()
        with open("scripts/muse_cookies.json", "w") as f:
            json.dump(cookies, f, indent=2)
            
        print("\nAll done! Browser staying open for 15s...")
        time.sleep(15)
        browser.close()

if __name__ == "__main__":
    run_test()
