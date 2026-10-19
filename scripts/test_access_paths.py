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
        
        for p_name in ["/access/invite", "/access/welcome", "/access/waitlist", "/request-early-access"]:
            url = f"https://muse.ai{p_name}"
            print(f"=== Testing {url} ===")
            await page.goto(url, wait_until="load", timeout=30000)
            await asyncio.sleep(3)
            print("Current URL:", page.url)
            print("Title:", await page.title())
            txt = await page.inner_text("body")
            print("Body:", txt[:300].replace("\n", " "))
            
        await browser.close()

asyncio.run(run())
