import concurrent.futures
import time
import urllib.request
from curl_cffi import requests
import json
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

def get_candidates():
    urls = [
        "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/countries/US/data.txt",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&country=us&protocol=http&proxy_format=protocolipport&format=text",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&country=us&protocol=socks5&proxy_format=protocolipport&format=text"
    ]
    proxies = []
    for u in urls:
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=6) as resp:
                text = resp.read().decode("utf-8", errors="ignore")
                for line in text.split("\n"):
                    line = line.strip()
                    if line and not line.startswith("#"):
                        if not (line.startswith("http://") or line.startswith("https://") or line.startswith("socks5://")):
                            line = f"http://{line}"
                        proxies.append(line)
        except Exception:
            pass
    return list(dict.fromkeys(proxies))

def test_proxy(p):
    start = time.time()
    try:
        r = requests.get(
            "https://muse.ai",
            proxies={"http": p, "https": p},
            verify=False,
            timeout=4.0,
            impersonate="chrome120"
        )
        if r.status_code == 200 and len(r.text) > 20000 and "Forbidden" not in r.text:
            dur = time.time() - start
            return p, dur
    except Exception:
        pass
    return None

def scan():
    candidates = get_candidates()
    print(f"Total US candidates gathered: {len(candidates)}")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as ex:
        futures = {ex.submit(test_proxy, p): p for p in candidates}
        for f in concurrent.futures.as_completed(futures):
            res = f.result()
            if res:
                p, dur = res
                print(f"\n>>> [FOUND WORKING US PROXY]: {p} in {dur:.2f}s! <<<")
                # Now check its IP
                try:
                    r_ip = requests.get("https://httpbin.org/ip", proxies={"http": p, "https": p}, timeout=3.0)
                    ip_info = r_ip.json().get("origin")
                    print(f"IP origin: {ip_info}")
                except Exception:
                    pass
                with open("scripts/working_us_proxy.json", "w", encoding="utf-8") as out:
                    json.dump({"proxy": p, "speed": dur}, out, indent=2)
                return p

if __name__ == "__main__":
    scan()
