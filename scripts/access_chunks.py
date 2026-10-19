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
        page = await browser.new_page()
        
        chunks = []
        page.on("request", lambda req: chunks.append(req.url) if req.resource_type == "script" and "chunk" in req.url else None)
        
        await page.goto("https://muse.ai/access", timeout=30000)
        await asyncio.sleep(4)
        
        print(f"Loaded {len(chunks)} chunks on /access:")
        for c in chunks:
            print(c)
            
        await browser.close()

asyncio.run(run())
