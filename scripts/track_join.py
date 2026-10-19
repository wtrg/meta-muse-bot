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
        
        page.on("framenavigated", lambda frame: print("FRAME NAVIGATED:", frame.url))
        
        print("Navigating...")
        await page.goto("https://muse.ai/join?code=QKPLQ6", wait_until="load", timeout=30000)
        await asyncio.sleep(5)
        
        print("Final URL:", page.url)
        print("Title:", await page.title())
        await browser.close()

asyncio.run(run())
