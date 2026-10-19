import urllib.request

url = "https://muse.ai/_next/static/chunks/0-2-yc0_v7hbv.js?dpl=dpl_13w2XhxKwKs7oW6RrPKNJxMESSbw"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=10) as r:
    code = r.read().decode('utf-8', errors='ignore')

idx = code.find("ONBOARDING_INVITE_CODE_IMPRESSION")
if idx != -1:
    print(code[max(0, idx-500):min(len(code), idx+1500)])
else:
    print("Not found")
