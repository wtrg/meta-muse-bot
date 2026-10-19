import json
import time
import sys
from playwright.sync_api import sync_playwright

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

with open("scripts/latest_registered_account.json", "r", encoding="utf-8") as f:
    acc_data = json.load(f)

cookies = acc_data["cookies"]

with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        headless=False,
        args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
    )
    context = browser.new_context(
        locale="en-US",
        timezone_id="America/New_York",
        viewport={"width": 1280, "height": 800}
    )
    context.add_cookies(cookies)
    page = context.new_page()

    page.on("console", lambda msg: print(f"[Console {msg.type}] {msg.text}"))
    page.on("response", lambda r: print(f"[Resp {r.status}] {r.url[:70]}") if any(k in r.url for k in ["api", "user", "me", "access", "auth"]) else None)

    print("Navigating to https://muse.ai/...")
    page.goto("https://muse.ai/", wait_until="load", timeout=30000)
    time.sleep(5)
    print("Page URL:", page.url)
    print("Page Title:", page.title())
    print("Body text preview:\n", page.inner_text("body")[:500])
    page.screenshot(path="scripts/muse_logged_in_root.png")

    if "access" in page.url or page.url.endswith("/access"):
        print("We are on /access!")
    else:
        print("Navigating to https://muse.ai/access...")
        page.goto("https://muse.ai/access", wait_until="load", timeout=30000)
        time.sleep(5)
        print("Access Page URL:", page.url)
        print("Access Page Title:", page.title())
        print("Access Page text preview:\n", page.inner_text("body")[:500])
        page.screenshot(path="scripts/muse_access_page_loaded.png")

    time.sleep(3)
    browser.close()
    print("Done inspection!")
