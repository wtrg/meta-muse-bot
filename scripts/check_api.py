import urllib.request
import json

with open("scripts/latest_registered_account.json", "r", encoding="utf-8") as f:
    acc = json.load(f)

cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in acc['cookies'] if 'muse.ai' in c['domain']])

req = urllib.request.Request(
    "https://muse.ai/api/auth/check",
    headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Cookie": cookie_str,
        "Accept": "application/json"
    }
)
try:
    with urllib.request.urlopen(req, timeout=10) as r:
        print("Status:", r.status)
        print("Body:", r.read().decode())
except urllib.error.HTTPError as e:
    print("HTTP Error:", e.code)
    print("Error Body:", e.read().decode())
