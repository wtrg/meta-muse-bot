import asyncio
import json
from playwright.async_api import async_playwright

async def run():
    with open("scripts/live_test_account.json", "r", encoding="utf-8") as f:
        acc = json.load(f)
    cookies = acc["cookies"]
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            headless=True,
            proxy={"server": "http://127.0.0.1:8085"},
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        ctx = await browser.new_context(locale="en-US", timezone_id="America/New_York")
        await ctx.add_cookies(cookies)
        page = await ctx.new_page()
        
        print("Opening https://muse.ai/access/invite with authenticated session...")
        await page.goto("https://muse.ai/access/invite", wait_until="load", timeout=30000)
        await asyncio.sleep(4)
        
        print("URL after load:", page.url)
        print("Title:", await page.title())
        content = await page.inner_text("body")
        print("Body preview:", content[:500].replace("\n", " "))
        
        inputs = await page.query_selector_all("input")
        print(f"Inputs count: {len(inputs)}")
        for i, inp in enumerate(inputs):
            print(f"  Input {i}: placeholder={await inp.get_attribute('placeholder')}, type={await inp.get_attribute('type')}")
            
        buttons = await page.query_selector_all("button, a")
        print(f"Buttons count: {len(buttons)}")
        for i, b in enumerate(buttons[:10]):
            print(f"  Btn {i}: {await b.inner_text()}")
            
        await page.screenshot(path="scripts/authenticated_access_invite.png")
        await browser.close()

asyncio.run(run())
