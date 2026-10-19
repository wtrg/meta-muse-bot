import time
from playwright.sync_api import sync_playwright

def test_meta_submit():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--lang=en-US,en",
                "--no-sandbox"
            ]
        )
        context = browser.new_context(
            locale="en-US",
            timezone_id="America/New_York",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        page.goto("https://auth.meta.com", timeout=30000)
        
        btn = page.wait_for_selector('text="Use mobile number or email address"', timeout=10000)
        btn.click()
        time.sleep(2)
        
        inp = page.wait_for_selector('input[type="text"]')
        inp.fill("muse_meta_test_01@maxxspace.com")
        time.sleep(1)
        
        continue_btn = page.wait_for_selector('button:has-text("Continue")')
        continue_btn.click()
        time.sleep(5)
        
        print("AFTER SUBMIT URL:", page.url)
        print("AFTER SUBMIT TEXT:\n", page.inner_text("body")[:600])
        page.screenshot(path="scripts/meta_step2.png")
        print("Screenshot saved to scripts/meta_step2.png")
        
        browser.close()

if __name__ == "__main__":
    test_meta_submit()
