import urllib.request
import json
import time
import concurrent.futures

try:
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

def fetch_proxies():
    urls = [
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/us.txt",
        "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/socks5.txt",
        "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&country=us&protocol=http,socks5&proxy_format=protocolipport&format=text"
    ]
    candidates = []
    for u in urls:
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=6) as r:
                for line in r.read().decode("utf-8", errors="ignore").splitlines():
                    line = line.strip()
                    if line and not line.startswith("#"):
                        if "socks5.txt" in u:
                            candidates.append(f"socks5://{line}")
                        elif line.startswith("socks5://") or line.startswith("http://"):
                            candidates.append(line)
                        else:
                            candidates.append(f"http://{line}")
        except Exception:
            pass
    return list(dict.fromkeys(candidates))

def test_p(p):
    try:
        handler = urllib.request.ProxyHandler({'http': p, 'https': p})
        opener = urllib.request.build_opener(handler)
        req = urllib.request.Request("http://ip-api.com/json", headers={"User-Agent": "curl/7.68.0"})
        t0 = time.time()
        with opener.open(req, timeout=3.5) as resp:
            data = json.loads(resp.read().decode())
            dur = time.time() - t0
            if data.get("countryCode") == "US":
                return {
                    "proxy": p,
                    "ip": data.get("query"),
                    "city": data.get("city"),
                    "region": data.get("regionName"),
                    "country": "United States",
                    "isp": data.get("isp"),
                    "ping": round(dur, 2)
                }
    except Exception:
        pass
    return None

def main():
    proxies = fetch_proxies()
    print(f"Scraping completed: {len(proxies)} candidates.")
    
    live_us = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as ex:
        futures = {ex.submit(test_p, p): p for p in proxies[:200]}
        for f in concurrent.futures.as_completed(futures):
            res = f.result()
            if res:
                print(f"[FOUND US PROXY] {res['proxy']} | {res['city']}, {res['region']} | Ping: {res['ping']}s | ISP: {res['isp']}")
                live_us.append(res)
                if len(live_us) >= 5:
                    break
                    
    with open("scripts/fast_us_proxies.json", "w", encoding="utf-8") as f:
        json.dump(live_us, f, indent=2)
    print(f"Saved {len(live_us)} verified US proxies to scripts/fast_us_proxies.json")

if __name__ == "__main__":
    main()
