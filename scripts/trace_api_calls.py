import json
import asyncio
from playwright.async_api import async_playwright

with open("scripts/muse_accounts.json", "r", encoding="utf-8") as f:
    accs = json.load(f)

latest_acc = accs[0]
cookies = latest_acc.get("cookies", [])

async def trace_api_calls():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            headless=True
        )
        context = await browser.new_context(locale="en-US", timezone_id="America/New_York")
        await context.add_cookies(cookies)
        page = await context.new_page()
        
        async def on_response(res):
            if "api" in res.url or "graphql" in res.url or "rsc" in res.url or "access" in res.url:
                try:
                    text = await res.text()
                    if any(k in text for k in ["hatch", "waitlist", "isGeoGated", "user", "access"]):
                        print(f"\nAPI URL: {res.url}")
                        print("Body:", text[:350])
                except Exception:
                    pass
                    
        page.on("response", on_response)
        await page.goto("https://muse.ai/access", timeout=20000)
        await asyncio.sleep(4)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(trace_api_calls())
