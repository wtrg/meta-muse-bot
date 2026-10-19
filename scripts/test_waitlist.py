import json
import time
from playwright.sync_api import sync_playwright

with open("scripts/latest_registered_account.json", "r", encoding="utf-8") as f:
    acc_data = json.load(f)

cookies = acc_data["cookies"]

with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        headless=False,
        args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
    )
    context = browser.new_context(locale="en-US", timezone_id="America/New_York")
    context.add_cookies(cookies)
    page = context.new_page()

    page.on("response", lambda r: print(f"[{r.status}] {r.url}") if "api" in r.url else None)

    print("Navigating to https://muse.ai/access...")
    page.goto("https://muse.ai/access", timeout=25000)
    time.sleep(3)

    # Look for buttons
    btns = page.query_selector_all("button")
    print(f"Found {len(btns)} buttons:")
    for b in btns:
        print(f"  Button: '{b.inner_text()}'")

    join_btn = page.query_selector('button:has-text("Join waitlist"), button:has-text("Join")')
    if join_btn:
        print("Clicking 'Join waitlist'...")
        join_btn.click()
        time.sleep(5)
        print("After click text:\n", page.inner_text("body"))
        page.screenshot(path="scripts/muse_after_waitlist.png")

    time.sleep(2)
    browser.close()
