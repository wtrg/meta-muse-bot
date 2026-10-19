import concurrent.futures
import time
from curl_cffi import requests
import urllib.request
import json
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

def get_us_candidates():
    urls = [
        "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/countries/US/data.txt",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&country=us&protocol=http&proxy_format=protocolipport&format=text",
        "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/socks5.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/all.txt"
    ]
    proxies = []
    for u in urls:
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                text = resp.read().decode("utf-8", errors="ignore")
                lines = [l.strip() for l in text.split("\n") if l.strip() and not l.startswith("#")]
                proxies.extend(lines)
        except Exception:
            pass
    clean = []
    for p in set(proxies):
        if not (p.startswith("http://") or p.startswith("https://") or p.startswith("socks5://")):
            clean.append(f"http://{p}")
        else:
            clean.append(p)
    return clean

def test_proxy_on_muse(p):
    start = time.time()
    try:
        r = requests.get(
            "https://muse.ai",
            proxies={"http": p, "https": p},
            verify=False,
            timeout=4.0,
            impersonate="chrome120"
        )
        if r.status_code in [200, 301, 302, 403]:
            # Also test geolocation
            r_ip = requests.get(
                "http://ip-api.com/json/",
                proxies={"http": p, "https": p},
                timeout=3.0
            )
            data = r_ip.json()
            if data.get("countryCode") == "US":
                dur = time.time() - start
                return p, dur, data.get("query"), data.get("isp"), data.get("regionName")
    except Exception:
        pass
    return None

RESIDENTIAL_ISPS = [
    "comcast", "charter", "spectrum", "at&t", "verizon", "cox", 
    "frontier", "century", "windstream", "fuse", "optimum", "suddenlink", "cable"
]

def find_working(target_count=3):
    candidates = get_us_candidates()
    print(f"Total candidates: {len(candidates)}")
    found = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=60) as ex:
        futures = {ex.submit(test_proxy_on_muse, p): p for p in candidates[:600]}
        for f in concurrent.futures.as_completed(futures):
            res = f.result()
            if res:
                p, dur, ip, isp, region = res
                is_res = any(kw in (isp or "").lower() for kw in RESIDENTIAL_ISPS)
                tag = "RESIDENTIAL" if is_res else "DATACENTER"
                print(f"[{tag}] {p} | Speed: {dur:.2f}s | IP: {ip} | ISP: {isp} ({region})")
                found.append({"proxy": p, "speed": dur, "ip": ip, "isp": isp, "region": region, "residential": is_res})
                if is_res and len(found) >= target_count:
                    break
    # Sort residential first, then by speed
    found.sort(key=lambda x: (not x["residential"], x["speed"]))
    return found

if __name__ == "__main__":
    results = find_working(3)
    print("\n--- TOP WORKING PROXIES ---")
    for r in results:
        print(r)

