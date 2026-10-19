import asyncio
from playwright.async_api import async_playwright

async def test_code():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            headless=True
        )
        context = await browser.new_context(locale="en-US", timezone_id="America/New_York")
        page = await context.new_page()
        
        # 1. Test /peer/accept#QKPLQ6
        url = "https://muse.ai/peer/accept#QKPLQ6"
        print(f"Navigating to {url}...")
        await page.goto(url, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(3)
        print("Final URL:", page.url)
        print("Title:", await page.title())
        body_text = (await page.inner_text("body"))[:600].replace("\n", " ")
        print("Body text snippet:\n", body_text)
        await page.screenshot(path=r"C:\Users\Lenovo\.gemini\antigravity\brain\f255b251-14c8-43b0-af0e-b9c0788ab043\muse_peer_accept_qkplq6.png")
        
        # 2. Test /join
        url_join = "https://muse.ai/join"
        print(f"\nNavigating to {url_join}...")
        await page.goto(url_join, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(2)
        print("Join Final URL:", page.url)
        print("Join Title:", await page.title())
        join_body = (await page.inner_text("body"))[:600].replace("\n", " ")
        print("Join Body snippet:\n", join_body)
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_code())
