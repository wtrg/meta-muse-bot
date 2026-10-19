import json
import asyncio
from playwright.async_api import async_playwright

with open("scripts/muse_accounts.json", "r", encoding="utf-8") as f:
    accs = json.load(f)

latest_acc = accs[0]
cookies = latest_acc.get("cookies", [])

async def test_routes():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            headless=True
        )
        context = await browser.new_context(locale="en-US", timezone_id="America/New_York")
        await context.add_cookies(cookies)
        page = await context.new_page()
        
        target_routes = [
            "/thread/main",
            "/thread/new",
            "/ideas",
            "/access/welcome",
            "/access/disclosure",
            "/hatch/session/bootstrap/"
        ]
        
        for r in target_routes:
            url = f"https://muse.ai{r}"
            try:
                resp = await page.goto(url, timeout=15000)
                await asyncio.sleep(2)
                print(f"\nRoute: {r}")
                print(" -> Status:", resp.status if resp else "None")
                print(" -> Final URL:", page.url)
                print(" -> Title:", await page.title())
                body_sub = (await page.inner_text("body"))[:200].replace("\n", " ")
                print(" -> Text:", body_sub)
            except Exception as e:
                print(f"Route {r} error: {e}")
                
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_routes())
