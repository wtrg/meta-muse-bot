import urllib.request
import re

url = "https://muse.ai/_next/static/chunks/2vc8ai3vban9r.js?dpl=dpl_13w2XhxKwKs7oW6RrPKNJxMESSbw"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=10) as r:
    code = r.read().decode('utf-8', errors='ignore')

matches = re.findall(r'\{"path":"[^"]+"\}', code)
print(f"Found {len(matches)} paths in 2vc8ai3vban9r.js:")
for m in matches:
    print(m)
