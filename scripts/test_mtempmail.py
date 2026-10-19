import urllib.request
import json
import time
import sys
from playwright.sync_api import sync_playwright

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

API_KEY = "pub_nRn1hUwpdmZvxQNVWDfoXgKyF7dIm9nRIIIt1qDw"
BASE_URL = "https://mtempmail.com/api"

def create_mtemp_email():
    url = f"{BASE_URL}/emails/{API_KEY}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}, data=b"{}")
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode())
        email = data["data"]["email"]
        print(f"[MTEMP] Created Email: {email}")
        return email

def poll_mtemp_otp(email, timeout=60):
    print(f"[MTEMP] Polling messages for {email}...")
    start = time.time()
    url = f"{BASE_URL}/messages/{API_KEY}/{email}"
    while time.time() - start < timeout:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                msgs = data.get("messages", []) or data.get("data", [])
                if msgs:
                    print(f" -> Found {len(msgs)} messages!")
                    for m in msgs:
                        subj = m.get("subject", "")
                        body = m.get("content", "") or m.get("body", "") or m.get("snippet", "")
                        print(f"  Subject: {subj}")
                        import re
                        digits = re.findall(r"\b\d{6}\b", subj + " " + body)
                        if digits:
                            print(f"  >>> FOUND OTP: {digits[0]}")
                            return digits[0]
        except Exception as e:
            print("Poll err:", e)
        time.sleep(3)
    raise TimeoutError("MTempMail OTP timeout")

def test():
    email = create_mtemp_email()
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            headless=False,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        context = browser.new_context(
            locale="en-US",
            timezone_id="America/New_York"
        )
        page = context.new_page()
        page.goto("https://muse.ai", timeout=25000)
        time.sleep(2)
        
        inp = page.wait_for_selector('input[placeholder*="email" i], input', timeout=10000)
        inp.fill(email)
        time.sleep(0.5)
        
        btn = page.query_selector('button:has-text("Continue"), button[type="submit"]')
        if btn: btn.click()
        else: page.keyboard.press("Enter")
        
        # Check if Meta accepted email
        time.sleep(3)
        body = page.inner_text("body")
        print("Page state after email submit:")
        print(body[:300])
        
        if "Enter your code" in body:
            print("Meta ACCEPTED the email and sent OTP!")
            otp = poll_mtemp_otp(email)
            print(f"Entering OTP: {otp}")
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
            print("Post-OTP screen:")
            print(page.inner_text("body")[:300])
            
            # Fill Names and Birthday
            all_inps = page.query_selector_all("input")
            text_inps = [i for i in all_inps if (i.get_attribute("type") or "text") not in ["hidden", "checkbox", "radio"]]
            if len(text_inps) >= 2:
                text_inps[0].click()
                time.sleep(0.2)
                page.keyboard.press("Control+A")
                page.keyboard.type("Alex", delay=50)
                time.sleep(0.2)
                text_inps[1].click()
                time.sleep(0.2)
                page.keyboard.press("Control+A")
                page.keyboard.type("Miller", delay=50)
                time.sleep(0.2)
                
            try:
                page.locator('select').nth(0).select_option(index=8)
                page.locator('select').nth(1).select_option(label="15")
                page.locator('select').nth(2).select_option(label="1996")
            except Exception as e:
                print("Select err:", e)
                
            time.sleep(1)
            print("Clicking final Confirm...")
            fin = page.locator('button:has-text("Confirm"), button:has-text("Save"), button:has-text("Continue")').first
            if fin.count() > 0: fin.click()
            else: page.keyboard.press("Enter")
            
            time.sleep(8)
            page.screenshot(path="scripts/mtemp_final.png")
            print("Final URL:", page.url)
            print("Final body:\n", page.inner_text("body")[:400])
        else:
            print("Meta did not show code screen.")
            page.screenshot(path="scripts/mtemp_reject.png")
            
        browser.close()

if __name__ == "__main__":
    test()
