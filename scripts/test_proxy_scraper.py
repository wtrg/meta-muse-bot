import urllib.request
import json
import concurrent.futures
import time

def fetch_us_proxies():
    urls = [
        "https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&proxy_format=protocolipport&format=text&country=us",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/socks5/data.txt",
        "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/socks5.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/all.txt"
    ]
    proxies = set()
    for u in urls:
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
            lines = urllib.request.urlopen(req, timeout=8).read().decode("utf-8", errors="ignore").splitlines()
            for line in lines:
                l = line.strip()
                if l and not l.startswith("#"):
                    if not l.startswith("http") and not l.startswith("socks"):
                        l = f"socks5://{l}"
                    proxies.add(l)
        except Exception as e:
            pass
    return list(proxies)

def test_proxy(p):
    import subprocess
    cmd = ["curl.exe", "-s", "--max-time", "4", "-x", p, "http://ip-api.com/json/?fields=status,country,countryCode,isp,org,hosting,query"]
    try:
        t0 = time.time()
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if res.returncode == 0 and res.stdout.strip():
            data = json.loads(res.stdout.strip())
            if data.get("countryCode") == "US":
                is_hosting = data.get("hosting", True)
                dur = round(time.time() - t0, 2)
                return {
                    "proxy": p,
                    "ip": data.get("query"),
                    "isp": data.get("isp"),
                    "hosting": is_hosting,
                    "ping": dur
                }
    except Exception:
        pass
    return None

if __name__ == "__main__":
    print("Fetching proxy list...")
    all_proxies = fetch_us_proxies()
    print(f"Total raw proxies fetched: {len(all_proxies)}")
    
    # Test top 50 in parallel
    tested = 0
    residential_found = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as ex:
        futures = [ex.submit(test_proxy, p) for p in all_proxies[:100]]
        for f in concurrent.futures.as_completed(futures):
            res = f.result()
            if res:
                print(f"WORKING US PROXY: {res['proxy']} | IP: {res['ip']} | ISP: {res['isp']} | Hosting: {res['hosting']} | Ping: {res['ping']}s")
                if not res['hosting']:
                    residential_found.append(res)
                    print(f"🔥 FOUND RESIDENTIAL US PROXY: {res}")
                    
    print(f"Residential found in first 100: {len(residential_found)}")
