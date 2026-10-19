import urllib.request
import json
import time
from playwright.sync_api import sync_playwright

def get_cox_and_residential():
    lines = urllib.request.urlopen(
        'https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/countries/US/data.txt',
        timeout=10
    ).read().decode().strip().split('\n')
    
    candidates = []
    print(f"Scanning first 60 proxies from {len(lines)} total...")
    for p in lines[:60]:
        if not p.strip(): continue
        candidates.append(p.strip())
    return candidates

def test_single_proxy(proxy_str):
    print(f"Testing {proxy_str}...")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                headless=True,
                proxy={"server": proxy_str},
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--lang=en-US,en",
                    "--no-sandbox",
                    "--ignore-certificate-errors"
                ]
            )
            context = browser.new_context(
                locale="en-US",
                timezone_id="America/New_York",
                ignore_https_errors=True
            )
            page = context.new_page()
            start = time.time()
            resp = page.goto("https://muse.ai", timeout=12000, wait_until="commit")
            elapsed = time.time() - start
            url = page.url
            title = page.title()
            browser.close()
            print(f"  -> SUCCESS! {proxy_str} connected in {elapsed:.1f}s | Title: {title} | URL: {url}")
            return proxy_str, elapsed, title
    except Exception as e:
        err_msg = str(e).split("\n")[0]
        print(f"  -> Failed: {err_msg[:60]}")
        return None

if __name__ == "__main__":
    candidates = get_cox_and_residential()
    working = []
    for c in candidates:
        res = test_single_proxy(c)
        if res:
            working.append(res)
            print(f"\n*** FOUND WORKING RESIDENTIAL PROXY: {res[0]} ***\n")
            break
            
    if not working:
        print("No proxy connected in this batch.")
