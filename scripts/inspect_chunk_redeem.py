import urllib.request

url = "https://muse.ai/_next/static/chunks/3cfv2xt2lyyd0.js?dpl=dpl_13w2XhxKwKs7oW6RrPKNJxMESSbw"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=10) as r:
    code = r.read().decode('utf-8', errors='ignore')

idx = code.find("INVITE_REDEEM_SUBMIT_CLICK")
if idx != -1:
    print(code[max(0, idx-500):min(len(code), idx+1000)])
else:
    print("Not found")
