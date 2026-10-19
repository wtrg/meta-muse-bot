import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            headless=True,
            proxy={"server": "http://127.0.0.1:8085"},
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        ctx = await browser.new_context(locale="en-US", timezone_id="America/New_York")
        page = await ctx.new_page()
        
        await page.goto("https://muse.ai/join?code=QKPLQ6", timeout=30000)
        await asyncio.sleep(3)
        
        storage = await page.evaluate("""() => {
            return {
                local: Object.entries(localStorage),
                session: Object.entries(sessionStorage),
                cookies: document.cookie
            };
        }""")
        print("Storage on /join?code=QKPLQ6:", storage)
        await browser.close()

asyncio.run(run())
