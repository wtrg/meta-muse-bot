import concurrent.futures
import time
from curl_cffi import requests
import urllib.request

def get_candidates():
    urls = [
        "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/countries/US/data.txt",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&country=us&protocol=http&proxy_format=protocolipport&format=text"
    ]
    proxies = []
    for u in urls:
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                text = resp.read().decode("utf-8")
                lines = [l.strip() for l in text.split("\n") if l.strip()]
                proxies.extend(lines)
        except Exception:
            pass
    return list(dict.fromkeys(proxies))

def test_single_proxy(p):
    start = time.time()
    try:
        r = requests.get(
            "https://httpbin.org/ip",
            proxies={"http": p, "https": p},
            verify=False,
            timeout=3.0
        )
        if r.status_code == 200:
            dur = time.time() - start
            return p, dur, r.json().get("origin")
    except Exception:
        pass
    return None

def find_fastest_us_proxies(count=3):
    candidates = get_candidates()
    print(f"Scanning {len(candidates)} candidates...")
    
    # Try in batches of 50
    working = []
    for batch_start in range(0, min(len(candidates), 300), 50):
        batch = candidates[batch_start:batch_start + 50]
        print(f"Testing batch {batch_start} to {batch_start + len(batch)}...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=30) as ex:
            results = ex.map(test_single_proxy, batch)
            for res in results:
                if res:
                    p, dur, ip = res
                    print(f" -> FOUND LIVE FAST PROXY: {p} ({dur:.2f}s) [IP: {ip}]")
                    working.append((p, dur, ip))
                    if len(working) >= count:
                        return working
    return working

if __name__ == "__main__":
    fast = find_fastest_us_proxies(5)
    print("Top fast proxies:", fast)
