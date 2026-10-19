import time
from playwright.sync_api import sync_playwright

def inspect_otp_inputs():
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
        
        email_input = page.query_selector('input[type="text"], input[type="email"], input[placeholder*="email" i], input[placeholder*="mobile" i]')
        email_input.fill("test_probe_muse2@maxxspace.com")
        time.sleep(1)
        
        continue_btn = page.query_selector('button:has-text("Continue"), button[type="submit"]')
        continue_btn.click()
        
        # Wait for "Enter your code" text or inputs
        page.wait_for_selector('text="Enter your code"', timeout=15000)
        time.sleep(2)
        
        inputs = page.query_selector_all("input")
        print(f"Total inputs on OTP screen: {len(inputs)}")
        for idx, inp in enumerate(inputs):
            inp_type = inp.get_attribute("type") or ""
            inp_name = inp.get_attribute("name") or ""
            inp_id = inp.get_attribute("id") or ""
            inp_class = inp.get_attribute("class") or ""
            inp_maxlength = inp.get_attribute("maxlength") or ""
            inp_aria = inp.get_attribute("aria-label") or ""
            print(f"Input #{idx}: type={inp_type}, name={inp_name}, id={inp_id}, maxlength={inp_maxlength}, aria-label={inp_aria}")
            
        buttons = page.query_selector_all("button")
        print(f"Total buttons: {len(buttons)}")
        for b in buttons:
            print(f"Button: text='{b.inner_text().strip()}'")
            
        browser.close()

if __name__ == "__main__":
    inspect_otp_inputs()
