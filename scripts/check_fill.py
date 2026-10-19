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
        
        await page.goto("https://muse.ai", wait_until="load", timeout=30000)
        await asyncio.sleep(4)
        
        print("Page URL:", page.url)
        print("Frames count:", len(page.frames))
        for idx, f in enumerate(page.frames):
            print(f"Frame {idx}: {f.url}")
            inputs = await f.query_selector_all("input")
            print(f"   Inputs in frame {idx}: {len(inputs)}")
            for i, inp in enumerate(inputs):
                print(f"     Input {i}: placeholder={await inp.get_attribute('placeholder')}, type={await inp.get_attribute('type')}")
                
        # Now fill email using fill()
        email = "checktest99@mtempmail.com"
        email_inp = await page.wait_for_selector('input[type="text"], input[type="email"], input[placeholder*="email" i], input', timeout=15000)
        await email_inp.fill(email)
        await asyncio.sleep(1)
        val = await email_inp.input_value()
        print("Filled value:", val)
        
        btn = await page.query_selector('button:has-text("Continue"), button[type="submit"]')
        if btn:
            print("Button disabled?", await btn.is_disabled())
            await btn.click()
            await asyncio.sleep(3)
            print("After click URL:", page.url)
            print("Body snippet:", (await page.inner_text("body"))[:300].replace("\n", " "))
        await browser.close()

asyncio.run(run())
