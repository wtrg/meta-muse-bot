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
        
        for url in ["https://muse.ai/join?code=QKPLQ6", "https://muse.ai/join#QKPLQ6", "https://muse.ai/peer/accept#QKPLQ6"]:
            print(f"=== Testing {url} ===")
            await page.goto(url, timeout=30000)
            await asyncio.sleep(3)
            print("Current URL:", page.url)
            txt = await page.inner_text("body")
            print("Body snippet:", txt.replace("\n", " ")[:200])
            
        await browser.close()

asyncio.run(run())
