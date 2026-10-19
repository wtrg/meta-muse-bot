import os
from playwright.sync_api import sync_playwright

ext_path = r"C:\Users\Lenovo\AppData\Local\Google\Chrome\User Data\Default\Extensions\bnlofglpdlboacepdieejiecfbfpmhlb\2.0.4_0"

def test_extension():
    print("Testing Chrome launch with Turbo VPN extension...")
    with sync_playwright() as p:
        user_data = os.path.join(os.path.dirname(__file__), "chrome_test_profile")
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=user_data,
            executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            headless=False,
            args=[
                f"--disable-extensions-except={ext_path}",
                f"--load-extension={ext_path}",
                "--lang=en-US,en"
            ]
        )
        page = ctx.new_page()
        page.goto("http://ip-api.com/json")
        print("Page text:", page.inner_text("body")[:300])
        page.wait_for_timeout(3000)
        ctx.close()

if __name__ == "__main__":
    test_extension()
