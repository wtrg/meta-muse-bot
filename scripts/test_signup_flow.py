import time
from playwright.sync_api import sync_playwright

def test_flow():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            headless=True
        )
        context = browser.new_context(
            locale="en-US",
            timezone_id="America/New_York",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        page.goto("https://muse.ai", wait_until="networkidle", timeout=30000)
        
        print("Page loaded. Looking for email input...")
        email_input = page.query_selector('input[type="text"], input[type="email"], input[placeholder*="email" i], input[placeholder*="mobile" i]')
        if not email_input:
            inputs = page.query_selector_all("input")
            if inputs:
                email_input = inputs[0]
                
        if email_input:
            print("Found input! Entering test email...")
            email_input.fill("test_probe_muse@maxxspace.com")
            time.sleep(1)
            
            # Find continue button
            continue_btn = page.query_selector('button:has-text("Continue"), button[type="submit"]')
            if continue_btn:
                print("Clicking Continue...")
                continue_btn.click()
                time.sleep(5)
                
                print("AFTER CLICK URL:", page.url)
                print("AFTER CLICK TITLE:", page.title())
                print("AFTER CLICK TEXT:", page.inner_text("body")[:600])
                page.screenshot(path="scripts/muse_step2.png")
                print("Screenshot saved to scripts/muse_step2.png")
            else:
                print("Continue button not found!")
        else:
            print("Email input not found!")
            
        browser.close()

if __name__ == "__main__":
    test_flow()
