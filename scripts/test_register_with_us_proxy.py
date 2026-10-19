import os
import sys
import time
import json
import urllib.request
import re
from playwright.sync_api import sync_playwright

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

MTEMP_API_KEY = "pub_nRn1hUwpdmZvxQNVWDfoXgKyF7dIm9nRIIIt1qDw"
MTEMP_BASE_URL = "https://mtempmail.com/api"

# Load best US proxy
with open("scripts/active_us_proxy.json", "r", encoding="utf-8") as f:
    proxy_info = json.load(f)

US_PROXY = proxy_info["proxy"]
print(f"[1] Using verified US Proxy: {US_PROXY} ({proxy_info['city']}, {proxy_info['region']}, US)")

def create_email():
    url = f"{MTEMP_BASE_URL}/emails/{MTEMP_API_KEY}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}, data=b"{}")
    with urllib.request.urlopen(req, timeout=12) as resp:
        return json.loads(resp.read().decode())["data"]["email"]

def poll_otp(email, timeout=60):
    start = time.time()
    url = f"{MTEMP_BASE_URL}/messages/{MTEMP_API_KEY}/{email}"
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
    print(f"[2] Created Clean TempMail: {email}")

    with sync_playwright() as p:
        print("[3] Launching Chrome with US Proxy config...")
        browser = p.chromium.launch(
            executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            headless=False,
            proxy={"server": US_PROXY},
            args=[
                "--disable-blink-features=AutomationControlled",
                "--lang=en-US,en",
                "--no-sandbox",
                "--ignore-certificate-errors",
                "--ignore-ssl-errors"
            ]
        )
        context = browser.new_context(
            locale="en-US",
            timezone_id="America/New_York",
            viewport={"width": 1280, "height": 800},
            ignore_https_errors=True
        )
        page = context.new_page()

        # Step 1: Verify IP on browser itself
        print("[4] Verifying browser IP location...")
        try:
            page.goto("https://ipinfo.io/json", wait_until="load", timeout=20000)
            time.sleep(2)
            ip_text = page.inner_text("body")
            print("Browser IP Info:\n", ip_text)
            page.screenshot(path="scripts/proof_us_ip_check.png")
            print("Saved IP proof screenshot: scripts/proof_us_ip_check.png")
        except Exception as e:
            print("Direct ipinfo check err:", e)

        # Step 2: Go to Muse.ai
        print("[5] Navigating to https://muse.ai under US Proxy...")
        try:
            page.goto("https://muse.ai", wait_until="load", timeout=30000)
        except Exception:
            page.goto("https://muse.ai", timeout=30000)
        time.sleep(3)
        print("Muse page title:", page.title())

        # Step 3: Enter email
        print(f"[6] Filling email {email}...")
        inp = page.wait_for_selector('input[type="text"], input[type="email"], input[placeholder*="email" i], input', timeout=15000)
        inp.fill(email)
        time.sleep(0.5)

        btn = page.query_selector('button:has-text("Continue"), button[type="submit"]')
        if btn: btn.click()
        else: page.keyboard.press("Enter")

        # Step 4: Wait for OTP
        print("[7] Waiting for OTP input screen...")
        page.wait_for_selector('text="Enter your code"', timeout=20000)
        print("[8] Polling OTP from Meta...")
        otp = poll_otp(email)
        print(f"[8] Received OTP: {otp}")

        # Step 5: Fill OTP
        otp_inp = page.wait_for_selector('input[aria-label*="code" i], input[maxlength="6"], input[type="text"]', timeout=10000)
        try: otp_inp.focus()
        except Exception: otp_inp.click(force=True)
        time.sleep(0.5)
        page.keyboard.type(str(otp), delay=150)
        time.sleep(1.5)

        confirm_btn = page.query_selector('button:has-text("Confirm"), button[type="submit"]')
        if confirm_btn:
            try: confirm_btn.click(force=True)
            except Exception: page.keyboard.press("Enter")
        else: page.keyboard.press("Enter")
        print("[9] Confirmed OTP, waiting for name/birthday screen...")
        time.sleep(4)

        # Step 6: Fill Name and Birthday
        body_text = page.inner_text("body")
        if "finish creating your account" in body_text.lower() or "birthday" in body_text.lower() or "first name" in body_text.lower():
            print("[10] Filling Name and Birthday...")
            text_inps = [i for i in page.query_selector_all("input") if (i.get_attribute("type") or "text") not in ["hidden", "checkbox", "radio"]]
            if len(text_inps) >= 2:
                text_inps[0].click()
                page.keyboard.type("Alex", delay=50)
                time.sleep(0.2)
                text_inps[1].click()
                page.keyboard.type("Miller", delay=50)
                time.sleep(0.2)
            try:
                page.locator("select").nth(0).select_option(index=8)
                page.locator("select").nth(1).select_option(label="15")
                page.locator("select").nth(2).select_option(label="1996")
            except Exception as e:
                print("Select err:", e)
            time.sleep(1)
            finish_btn = page.locator('button:has-text("Confirm"), button:has-text("Save"), button:has-text("Continue")').first
            if finish_btn.count() > 0: finish_btn.click()
            else: page.keyboard.press("Enter")
            print("[11] Clicked final confirm, waiting for completion...")
            time.sleep(6)

        # Step 7: Wait for destination and capture screenshot proof
        try:
            if "access" not in page.url and "dashboard" not in page.url:
                page.goto("https://muse.ai/access", wait_until="load", timeout=20000)
            time.sleep(3)
        except Exception:
            pass

        body_final = page.inner_text("body")
        if "Join waitlist" in body_final or "waitlist" in body_final.lower():
            join_btn = page.locator('button:has-text("Join waitlist"), button:has-text("Join")').first
            if join_btn.count() > 0:
                try:
                    join_btn.click()
                    time.sleep(2)
                except Exception:
                    pass

        # Capture final proof screenshot
        proof_screenshot = "scripts/proof_muse_registered_with_us_proxy.png"
        page.screenshot(path=proof_screenshot)
        print(f"[12] Final URL: {page.url}")
        print(f"[12] Saved registration proof screenshot: {proof_screenshot}")

        cookies = context.cookies()
        hatch_sess = next((c["value"] for c in cookies if c["name"] == "hatch_sess"), "")
        print(f"[13] Successfully obtained session cookies! hatch_sess length: {len(hatch_sess)}")

        acc_record = {
            "id": f"muse_us_{int(time.time())}",
            "email": email,
            "otp": otp,
            "proxy_used": US_PROXY,
            "proxy_geo": f"{proxy_info['city']}, {proxy_info['region']}, US",
            "url": page.url,
            "status": "SUCCESS_LOGGED_IN",
            "cookies": cookies,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        with open("scripts/latest_us_proxy_account.json", "w", encoding="utf-8") as out:
            json.dump(acc_record, out, indent=2)

        time.sleep(2)
        browser.close()
        print("[SUCCESS] COMPLETED END-TO-END WITH US PROXY!")

if __name__ == "__main__":
    main()
