import urllib.request
import concurrent.futures
import time
import socket

def get_proxy_candidates():
    urls = [
        "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/countries/US/data.txt",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&country=us&protocol=http,socks5&proxy_format=protocolipport&format=text"
    ]
    proxies = []
    for u in urls:
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=6) as resp:
                text = resp.read().decode("utf-8")
                lines = [l.strip() for l in text.split("\n") if l.strip()]
                proxies.extend(lines)
        except Exception as e:
            pass
    return list(dict.fromkeys(proxies))

def quick_test_proxy(p):
    # Quick socket test first
    try:
        clean = p.replace("socks5://", "").replace("http://", "").replace("https://", "")
        host, port = clean.split(":")
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2.0)
        s.connect((host, int(port)))
        s.close()
        return p
    except Exception:
        return None

def find_working_proxies(max_to_test=100, concurrency=30):
    candidates = get_proxy_candidates()
    print(f"Total candidates: {len(candidates)}. Fast-probing top {max_to_test}...")
    
    live_sockets = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        results = executor.map(quick_test_proxy, candidates[:max_to_test])
        for r in results:
            if r:
                live_sockets.append(r)
                
    print(f"Live socket responders: {len(live_sockets)}")
    return live_sockets

if __name__ == "__main__":
    live = find_working_proxies(150, 40)
    print("Live proxies:", live[:10])
