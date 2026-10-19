import asyncio
import re
import json
from playwright.async_api import async_playwright

async def check_muse_geogate():
    async with async_playwright() as p:
        # Test without proxy (or whatever proxy is active)
        browser = await p.chromium.launch(
            executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            headless=True
        )
        page = await browser.new_page(locale="en-US")
        
        # Intercept network responses to find hatch / geogate payload
        async def on_response(response):
            try:
                url = response.url
                if "muse.ai" in url and ("rsc" in url or "access" in url or response.request.resource_type == "document"):
                    text = await response.text()
                    if "isGeoGated" in text or "waitlist" in text or "hasHatchAccess" in text:
                        print(f"\n--- FOUND IN {url} ---")
                        for line in text.split("\n"):
                            if "isGeoGated" in line or "hasHatchAccess" in line or "waitlistStatus" in line:
                                print(line[:300])
            except Exception:
                pass
                
        page.on("response", on_response)
        print("Navigating to https://muse.ai...")
        await page.goto("https://muse.ai", timeout=30000)
        await asyncio.sleep(3)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(check_muse_geogate())
