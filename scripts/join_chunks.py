import urllib.request
import re

url = "https://muse.ai/join"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
try:
    with urllib.request.urlopen(req, timeout=10) as r:
        html = r.read().decode('utf-8', errors='ignore')
    chunks = re.findall(r'src="([^"]+\.js)"', html)
    print("Chunks loaded specifically on /join:")
    for c in chunks:
        print(c)
except Exception as e:
    print("Error:", e)
