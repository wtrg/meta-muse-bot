import asyncio
import json
from playwright.async_api import async_playwright

async def inspect_browser():
    async with async_playwright() as p:
        proxy_config = {"server": "http://127.0.0.1:8085"}
        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--lang=en-US,en",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-infobars",
            "--disable-webrtc",
            "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
            "--enforce-webrtc-ip-permission-check"
        ]
        browser = await p.chromium.launch(
            executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            headless=True,
            proxy=proxy_config,
            args=launch_args
        )
        context = await browser.new_context(
            locale="en-US",
            timezone_id="America/New_York",
            viewport={"width": 1280, "height": 800}
        )
        page = await context.new_page()
        
        # 1. Test IP seen by web page
        await page.goto("http://ip-api.com/json/?fields=query,country,city,isp,org,as,hosting,proxy", timeout=20000)
        ip_info = await page.inner_text("pre")
        print("IP Info in browser:", ip_info)
        
        # 2. Check navigator properties
        nav_info = await page.evaluate("""() => ({
            userAgent: navigator.userAgent,
            webdriver: navigator.webdriver,
            languages: navigator.languages,
            timezone: Intl.DateTimeFormat().resolvedOptions().timeZone
        })""")
        print("Navigator Info:", json.dumps(nav_info, indent=2))
        
        # 3. Check muse.ai access status directly
        resp = await page.goto("https://muse.ai", wait_until="domcontentloaded", timeout=25000)
        print("Muse.ai status:", resp.status if resp else "None")
        print("Muse.ai title:", await page.title())
        print("Muse.ai URL:", page.url)
        content = await page.content()
        print("isGeoGated in content:", "isGeoGated" in content)
        if "isGeoGated" in content:
            idx = content.find("isGeoGated")
            print("Snippet:", content[max(0, idx - 80):min(len(content), idx + 120)])
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(inspect_browser())
