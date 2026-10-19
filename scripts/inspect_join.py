import asyncio
from playwright.async_api import async_playwright

async def inspect_join():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            headless=True
        )
        page = await browser.new_page(locale="en-US", timezone_id="America/New_York")
        await page.goto("https://muse.ai/join", timeout=30000)
        await asyncio.sleep(2)
        print("URL:", page.url)
        print("Title:", await page.title())
        print("Body text snippet:\n", (await page.inner_text("body"))[:600])
        await page.screenshot(path=r"C:\Users\Lenovo\.gemini\antigravity\brain\f255b251-14c8-43b0-af0e-b9c0788ab043\muse_join_page.png")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(inspect_join())
