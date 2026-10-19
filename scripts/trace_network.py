import asyncio
import json
from playwright.async_api import async_playwright

async def trace_all_network():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            headless=True
        )
        page = await browser.new_page(
            locale="en-US",
            timezone_id="America/New_York",
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9"
            }
        )
        
        requests_log = []
        
        async def on_request(req):
            if any(k in req.url for k in ["muse.ai", "meta.com", "facebook.com", "instagram.com"]):
                requests_log.append({
                    "method": req.method,
                    "url": req.url,
                    "headers": req.headers,
                    "post_data": req.post_data[:200] if req.post_data else None
                })
                
        async def on_response(res):
            url = res.url
            if "muse.ai" in url and res.request.resource_type in ["document", "fetch", "xhr"]:
                try:
                    text = await res.text()
                    if any(k in text for k in ["geo", "Geo", "waitlist", "Hatch", "hatch", "country", "Region"]):
                        print(f"\n[RESPONSE {res.status}] {url}")
                        for line in text.split("\n"):
                            if any(k in line for k in ["isGeoGated", "hasHatchAccess", "waitlistStatus", "geo", "country"]):
                                print("MATCH:", line[:250])
                except Exception:
                    pass
                    
        page.on("request", on_request)
        page.on("response", on_response)
        
        print("Navigating to https://muse.ai...")
        await page.goto("https://muse.ai", wait_until="networkidle", timeout=30000)
        
        # Check Next.js build manifest and chunk files
        html = await page.content()
        with open("scripts/muse_page_dump.html", "w", encoding="utf-8") as f:
            f.write(html)
            
        print("Page dumped to scripts/muse_page_dump.html")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(trace_all_network())
