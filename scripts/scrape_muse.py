import urllib.request
import re

url = "https://muse.ai"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"})
html = urllib.request.urlopen(req).read().decode("utf-8")
print("HTML length:", len(html))

# Find script tags
scripts = re.findall(r'<script[^>]*src="([^"]+)"', html)
print("Scripts found:", len(scripts))
for s in scripts[:10]:
    print("Script:", s)
