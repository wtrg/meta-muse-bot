import urllib.request
import time
from playwright.sync_api import sync_playwright
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

def get_candidates():
    url = "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/countries/US/data.txt"
    try:
        lines = urllib.request.urlopen(url, timeout=10).read().decode().splitlines()
        clean = [l.strip() for l in lines if l.strip() and not l.startswith("#")]
        return clean
    except Exception as e:
        print("Error fetching candidates:", e)
        return []

def test_proxies():
    candidates = get_candidates()
    print(f"Total candidates: {len(candidates)}")
    
    with sync_playwright() as p:
        for idx, proxy_url in enumerate(candidates[:30]):
            print(f"[{idx+1}/30] Testing proxy: {proxy_url}...")
            browser = None
            try:
                browser = p.chromium.launch(
                    executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                    headless=True,
                    proxy={"server": proxy_url},
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--ignore-certificate-errors",
                        "--disable-dev-shm-usage"
                    ]
                )
                context = browser.new_context(
                    locale="en-US",
                    timezone_id="America/New_York",
                    ignore_https_errors=True
                )
                page = context.new_page()
                start = time.time()
                resp = page.goto("https://muse.ai", timeout=8000)
                dur = time.time() - start
                title = page.title()
                body = page.inner_text("body")
                print(f"  -> SUCCESS! Duration: {dur:.2f}s | Title: {title} | Body len: {len(body)}")
                if "Forbidden" not in body and len(body) > 100:
                    print(f"*** FOUND WORKING CLEAN US PROXY FOR MUSE: {proxy_url} ***")
                    return proxy_url
            except Exception as e:
                err = str(e).splitlines()[0]
                print(f"  -> Failed: {err[:80]}")
            finally:
                if browser:
                    try: browser.close()
                    except: pass
    return None

if __name__ == "__main__":
    test_proxies()
