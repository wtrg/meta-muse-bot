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
        
        print("Navigating to https://muse.ai/invite/QKPLQ6...")
        await page.goto("https://muse.ai/invite/QKPLQ6", wait_until="load", timeout=30000)
        await asyncio.sleep(4)
        
        print("URL after load:", page.url)
        print("Title:", await page.title())
        content = await page.inner_text("body")
        print("Body preview:", content[:500].replace("\n", " "))
        
        inputs = await page.query_selector_all("input")
        print("Inputs count:", len(inputs))
        for i, inp in enumerate(inputs):
            print(f"Input {i}: placeholder={await inp.get_attribute('placeholder')}")
            
        buttons = await page.query_selector_all("button, a")
        print("Buttons/Links count:", len(buttons))
        for i, b in enumerate(buttons[:10]):
            print(f"Button {i}: text={await b.inner_text()}, href={await b.get_attribute('href')}")
            
        await page.screenshot(path="scripts/test_invite_route.png")
        await browser.close()

asyncio.run(run())
