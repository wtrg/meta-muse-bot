import time
from playwright.sync_api import sync_playwright

def test_meta():
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
        time.sleep(3)
        
        print("AFTER CLICK URL:", page.url)
        print("AFTER CLICK TEXT:\n", page.inner_text("body")[:600])
        
        inputs = page.query_selector_all("input")
        print(f"Inputs count: {len(inputs)}")
        for idx, inp in enumerate(inputs):
            print(f"Input {idx}: type={inp.get_attribute('type')}, placeholder={inp.get_attribute('placeholder')}")
            
        browser.close()

if __name__ == "__main__":
    test_meta()
