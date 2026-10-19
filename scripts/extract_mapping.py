import urllib.request

url = "https://muse.ai/_next/static/chunks/0s75stlmk8kbp.js?dpl=dpl_13w2XhxKwKs7oW6RrPKNJxMESSbw"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=10) as r:
    code = r.read().decode('utf-8', errors='ignore')

idx = code.find("hatch.onboarding.access.invite")
if idx != -1:
    print(code[max(0, idx-300):min(len(code), idx+500)])
else:
    print("Not found")
