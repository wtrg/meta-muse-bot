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
        
        # Click "Kiểm Tra IP Ngay"
        check_btn = page.locator('button:has-text("Kiểm Tra IP Ngay")')
        await check_btn.click()
        await asyncio.sleep(5)
        
        await page.screenshot(path=r"C:\Users\Lenovo\.gemini\antigravity\brain\f255b251-14c8-43b0-af0e-b9c0788ab043\muse_psiphon_health_tested.png", full_page=True)
        await browser.close()
        print("Done!")

if __name__ == "__main__":
    asyncio.run(run())
