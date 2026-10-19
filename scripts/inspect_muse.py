import json
from playwright.sync_api import sync_playwright

def inspect():
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
        
        print("CURRENT URL:", page.url)
        print("PAGE TITLE:", page.title())
        
        # Check text
        body_text = page.inner_text("body")
        print("\n--- BODY TEXT (first 800 chars) ---")
        print(body_text[:800])
        
        # Check buttons and inputs
        elements = page.query_selector_all("button, a, input")
        print(f"\n--- INTERACTIVE ELEMENTS (found {len(elements)}) ---")
        for el in elements[:25]:
            tag = el.evaluate("e => e.tagName.toLowerCase()")
            text = el.evaluate("e => (e.innerText || e.value || e.placeholder || e.getAttribute('aria-label') || '').trim()")
            href = el.evaluate("e => e.getAttribute('href') || ''")
            print(f"[{tag}] text='{text}' href='{href}'")
            
        page.screenshot(path="scripts/muse_home.png")
        print("\nScreenshot saved to scripts/muse_home.png")
        browser.close()

if __name__ == "__main__":
    inspect()
