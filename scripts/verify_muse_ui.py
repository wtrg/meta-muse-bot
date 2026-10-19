import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            headless=True
        )
        page = await browser.new_page(viewport={"width": 1400, "height": 900})
        await page.goto("http://127.0.0.1:5173/muse", wait_until="networkidle")
        await asyncio.sleep(2)
        await page.screenshot(path=r"C:\Users\Lenovo\.gemini\antigravity\brain\f255b251-14c8-43b0-af0e-b9c0788ab043\muse_psiphon_ui.png", full_page=True)
        await browser.close()
        print("Screenshot saved to muse_psiphon_ui.png")

if __name__ == "__main__":
    asyncio.run(run())
