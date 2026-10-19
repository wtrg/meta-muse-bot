import urllib.request
import json
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

urls = json.load(open('scripts/audit_js_urls.json'))
print(f"Searching {len(urls)} JS chunks...")

for u in urls:
    if not u.endswith(".js") and ".js?" not in u: continue
    try:
        req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            text = resp.read().decode("utf-8", errors="ignore")
            if "registrationBlocked" in text or "register-completion" in text or "Something went wrong" in text:
                print(f"\n[FOUND MATCH in {u.split('/')[-1]}]:")
                for line in text.split(";"):
                    if "registrationBlocked" in line or "register-completion" in line:
                        print("  ->", line[:300])
    except Exception as e:
        pass
