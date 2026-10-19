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
        
        scripts = []
        async def on_req(req):
            if req.resource_type == "script" and "muse.ai" in req.url:
                scripts.append(req.url)
        page.on("request", on_req)

        await page.goto("https://muse.ai/peer/accept#QKPLQ6", timeout=30000)
        await asyncio.sleep(4)
        
        print(f"Loaded {len(scripts)} scripts:")
        for s in scripts:
            print("SCRIPT:", s)
            
        # Search page content
        html = await page.content()
        print("Page HTML length:", len(html))
        
        # Check window properties or Next.js state
        state = await page.evaluate("""() => {
            return {
                nextData: window.__NEXT_DATA__ || null,
                location: window.location.href,
                hash: window.location.hash
            };
        }""")
        print("State:", state)
        await browser.close()

asyncio.run(run())
