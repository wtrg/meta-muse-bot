import urllib.request
import json
import time
import sys
import re
from playwright.sync_api import sync_playwright

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

API_KEY = "pub_nRn1hUwpdmZvxQNVWDfoXgKyF7dIm9nRIIIt1qDw"
BASE_URL = "https://mtempmail.com/api"

def create_email():
    url = f"{BASE_URL}/emails/{API_KEY}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}, data=b"{}")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())["data"]["email"]

def poll_otp(email, timeout=60):
    start = time.time()
    url = f"{BASE_URL}/messages/{API_KEY}/{email}"
    while time.time() - start < timeout:
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
        except Exception as e:
            print("Poll err:", e)
        time.sleep(2)
    raise TimeoutError("OTP timeout")

def main():
    email = create_email()
    print(f"[1] Created email: {email}")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            headless=False,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        context = browser.new_context(locale="en-US", timezone_id="America/New_York")
        page = context.new_page()
        
        # Track console and network
        page.on("console", lambda msg: print(f"[Browser Console {msg.type}] {msg.text}"))
        page.on("response", lambda res: print(f"[HTTP {res.status}] {res.url[:80]}") if "api" in res.url or "auth" in res.url or "access" in res.url else None)

        print("[2] Navigating to muse.ai...")
        page.goto("https://muse.ai", timeout=25000)
        time.sleep(2)
        
        inp = page.wait_for_selector('input[placeholder*="email" i], input', timeout=10000)
        inp.fill(email)
        time.sleep(0.5)
        
        btn = page.query_selector('button:has-text("Continue"), button[type="submit"]')
        if btn: btn.click()
        else: page.keyboard.press("Enter")
        time.sleep(3)
        
        print("[3] Waiting for OTP...")
        otp = poll_otp(email)
        print(f"[3] Got OTP: {otp}")
        
        otp_inp = page.wait_for_selector('input[aria-label*="code" i], input[maxlength="6"]', timeout=10000)
        try: otp_inp.focus()
        except: otp_inp.click(force=True)
        time.sleep(0.5)
        page.keyboard.type(str(otp), delay=150)
        time.sleep(1.5)
        
        confirm = page.query_selector('button:has-text("Confirm"), button[type="submit"]')
        if confirm: confirm.click(force=True)
        else: page.keyboard.press("Enter")
        time.sleep(4)
        
        print("[4] Filling name and birthday...")
        text_inps = [i for i in page.query_selector_all("input") if (i.get_attribute("type") or "text") not in ["hidden", "checkbox", "radio"]]
        if len(text_inps) >= 2:
            text_inps[0].click()
            page.keyboard.type("David", delay=50)
            time.sleep(0.2)
            text_inps[1].click()
            page.keyboard.type("Evans", delay=50)
            time.sleep(0.2)
            
        try:
            page.locator("select").nth(0).select_option(index=4)
            page.locator("select").nth(1).select_option(label="10")
            page.locator("select").nth(2).select_option(label="1995")
        except Exception as e:
            print("Select error:", e)
            
        time.sleep(1)
        print("[5] Clicking final Confirm button...")
        fin = page.locator('button:has-text("Confirm"), button:has-text("Save"), button:has-text("Continue")').first
        if fin.count() > 0: fin.click()
        else: page.keyboard.press("Enter")
        
        print("[6] Waiting after confirm...")
        for sec in range(1, 16):
            time.sleep(1)
            print(f"  Sec {sec}: URL={page.url} | Title='{page.title()}'")
            if page.url != "https://muse.ai" and "meta.com" not in page.url:
                # We transitioned!
                break
                
        time.sleep(5)
        print("\n================ FINAL STATUS ================")
        print(f"Final URL: {page.url}")
        print(f"Final Title: {page.title()}")
        print(f"Body inner_text: \n{page.inner_text('body')[:600]}")
        
        cookies = context.cookies()
        print(f"Total cookies: {len(cookies)}")
        for c in cookies:
            print(f"Cookie: {c['domain']} | {c['name']} = {c['value'][:25]}...")
            
        screenshot_path = "scripts/muse_access_page.png"
        page.screenshot(path=screenshot_path)
        print(f"Screenshot saved to {screenshot_path}")
        
        # Save account data
        acc_data = {
            "email": email,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "final_url": page.url,
            "title": page.title(),
            "cookies": cookies
        }
        with open("scripts/latest_registered_account.json", "w", encoding="utf-8") as f:
            json.dump(acc_data, f, ensure_ascii=False, indent=2)
            
        browser.close()

if __name__ == "__main__":
    main()
