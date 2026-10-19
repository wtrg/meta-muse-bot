import json
import asyncio
from playwright.async_api import async_playwright

with open("scripts/muse_accounts.json", "r", encoding="utf-8") as f:
    accs = json.load(f)

latest_acc = accs[0]
print("Testing account:", latest_acc.get("email"))
cookies = latest_acc.get("cookies", [])
print("Cookies count:", len(cookies))

async def test_acc():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            headless=True
        )
        context = await browser.new_context(locale="en-US", timezone_id="America/New_York")
        await context.add_cookies(cookies)
        page = await context.new_page()
        
        # Go to muse.ai/access
        await page.goto("https://muse.ai/access", timeout=30000)
        await asyncio.sleep(3)
        print("Final URL:", page.url)
        print("Page title:", await page.title())
        text = await page.inner_text("body")
        print("Body text snippet:\n", text[:400])
        
        # Test /access/invite
        await page.goto("https://muse.ai/access/invite", timeout=30000)
        await asyncio.sleep(2)
        print("\nURL after /access/invite:", page.url)
        print("Body text of /access/invite:\n", (await page.inner_text("body"))[:400])
        
        await browser.screenshot(path="scripts/test_invite_screen.png")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_acc())
