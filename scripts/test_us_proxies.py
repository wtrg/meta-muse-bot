import urllib.request
import json
import time
import socket
import concurrent.futures

try:
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

def get_geonode_us_proxies():
    url = "https://proxylist.geonode.com/api/proxy-list?country=US&limit=50&page=1&sort_by=lastChecked&sort_type=desc"
    proxies = []
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())
            for item in data.get("data", []):
                proto = item["protocols"][0]
                ip = item["ip"]
                port = item["port"]
                proxies.append(f"{proto}://{ip}:{port}")
    except Exception as e:
        print("Geonode err:", e)
    return proxies

def get_proxyscrape_us():
    urls = [
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&country=us&protocol=http&proxy_format=protocolipport&format=text",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&country=us&protocol=socks5&proxy_format=protocolipport&format=text",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/us.txt"
    ]
    proxies = []
    for u in urls:
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as r:
                for line in r.read().decode("utf-8", errors="ignore").splitlines():
                    line = line.strip()
                    if line and not line.startswith("#"):
                        if not (line.startswith("http://") or line.startswith("socks5://")):
                            line = f"http://{line}"
                        proxies.append(line)
        except Exception:
            pass
    return proxies

def check_proxy_alive(p):
    # Test connection and real IP
    try:
        import urllib.request
        proto = "socks5" if "socks5" in p else "http"
        # Test against ipinfo.io or httpbin.org
        handler = urllib.request.ProxyHandler({'http': p, 'https': p})
        opener = urllib.request.build_opener(handler)
        req = urllib.request.Request("https://ipinfo.io/json", headers={"User-Agent": "curl/7.68.0"})
        t0 = time.time()
        with opener.open(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            lat = time.time() - t0
            country = data.get("country")
            if country == "US":
                return {
                    "proxy": p,
                    "ip": data.get("ip"),
                    "city": data.get("city"),
                    "region": data.get("region"),
                    "country": country,
                    "org": data.get("org"),
                    "latency": round(lat, 2)
                }
    except Exception:
        pass
    return None

def main():
    print("Gathering US proxy candidates...")
    all_proxies = get_geonode_us_proxies() + get_proxyscrape_us()
    all_proxies = list(dict.fromkeys(all_proxies))
    print(f"Total US proxies found: {len(all_proxies)}")
    
    working = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
        futures = {executor.submit(check_proxy_alive, p): p for p in all_proxies[:80]}
        for f in concurrent.futures.as_completed(futures):
            res = f.result()
            if res:
                print(f"[LIVE US PROXY] {res['proxy']} | {res['city']}, {res['region']}, US | Org: {res['org']} | Ping: {res['latency']}s")
                working.append(res)
                if len(working) >= 3:
                    break
                    
    with open("scripts/live_us_proxies.json", "w", encoding="utf-8") as f:
        json.dump(working, f, indent=2)
    print(f"Done! Found {len(working)} verified live US proxies.")

if __name__ == "__main__":
    main()
