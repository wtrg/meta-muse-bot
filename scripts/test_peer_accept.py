import json
import asyncio
from playwright.async_api import async_playwright

with open("scripts/muse_accounts.json", "r", encoding="utf-8") as f:
    accs = json.load(f)

latest_acc = accs[0]
cookies = latest_acc.get("cookies", [])

async def test_peer_accept():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            headless=True
        )
        context = await browser.new_context(locale="en-US", timezone_id="America/New_York")
        await context.add_cookies(cookies)
        page = await context.new_page()
        
        # Test code V8V7FY or 6O2TUC
        url = "https://muse.ai/peer/accept#V8V7FY"
        print(f"Navigating to {url}...")
        resp = await page.goto(url, timeout=25000)
        await asyncio.sleep(4)
        print("Final URL:", page.url)
        print("Page title:", await page.title())
        body_sub = await page.inner_text("body")
        print("Body text:\n", body_sub[:500])
        await page.screenshot(path="scripts/test_peer_accept_screen.png")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_peer_accept())
