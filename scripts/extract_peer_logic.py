import urllib.request

url = "https://muse.ai/_next/static/chunks/1wk1sqzy19q-x.js?dpl=dpl_13w2XhxKwKs7oW6RrPKNJxMESSbw"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=10) as r:
    code = r.read().decode('utf-8', errors='ignore')

idx = code.find("PEER_ACCEPT")
if idx != -1:
    start = max(0, idx - 1000)
    end = min(len(code), idx + 2500)
    print("=== PEER ACCEPT LOGIC ===")
    print(code[start:end])
else:
    print("Not found")
