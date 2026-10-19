import urllib.request
import json
import time
import concurrent.futures
from curl_cffi import requests

try:
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

def fetch_proxifly():
    url = "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/countries/US/data.txt"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=8) as r:
        return [l.strip() for l in r.read().decode("utf-8").splitlines() if l.strip()]

def test_proxy(p):
    t0 = time.time()
    try:
        r = requests.get(
            "http://ip-api.com/json",
            proxies={"http": p, "https": p},
            timeout=2.0
        )
        data = r.json()
        if data.get("countryCode") == "US":
            dur = time.time() - t0
            return {
                "proxy": p,
                "ip": data.get("query"),
                "city": data.get("city"),
                "region": data.get("regionName"),
                "isp": data.get("isp"),
                "ping": round(dur, 2)
            }
    except Exception:
        pass
    return None

def main():
    proxies = fetch_proxifly()
    print(f"Loaded {len(proxies)} US proxies from proxifly. Testing top 150 concurrently...")
    
    found = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=60) as ex:
        futures = {ex.submit(test_proxy, p): p for p in proxies[:150]}
        for f in concurrent.futures.as_completed(futures):
            res = f.result()
            if res:
                print(f"-> [FOUND LIVE US PROXY] {res['proxy']} | {res['city']}, {res['region']} | Ping: {res['ping']}s | ISP: {res['isp']}")
                found.append(res)
                if len(found) >= 3:
                    break
                    
    if found:
        with open("scripts/active_us_proxy.json", "w", encoding="utf-8") as out:
            json.dump(found[0], out, indent=2)
        print("Best proxy saved to scripts/active_us_proxy.json")
    else:
        print("No proxy responded under 2s in top 150.")

if __name__ == "__main__":
    main()
