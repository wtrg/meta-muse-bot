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
        
        await page.goto("https://muse.ai/join?code=QKPLQ6", wait_until="load", timeout=30000)
        await asyncio.sleep(3)
        
        email = "testbot1234@mtempmail.com"
        email_inp = await page.wait_for_selector('input[type="text"], input[type="email"], input[placeholder*="email" i], input', timeout=15000)
        await email_inp.click()
        await page.keyboard.type(email, delay=50)
        await asyncio.sleep(1)
        
        await page.screenshot(path="scripts/debug_typed.png")
        
        btn = await page.wait_for_selector('button:has-text("Continue")', timeout=5000)
        is_disabled = await btn.is_disabled()
        print("Button disabled before click?", is_disabled)
        
        await btn.click()
        await asyncio.sleep(3)
        await page.screenshot(path="scripts/debug_after_click.png")
        print("URL after click:", page.url)
        print("Body text after click:", (await page.inner_text("body"))[:300].replace("\n", " "))
        await browser.close()

asyncio.run(run())
