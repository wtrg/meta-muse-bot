import urllib.request
import re

with open('scripts/muse_page_dump.html', 'r', encoding='utf-8') as f:
    c = f.read()

scripts = re.findall(r'<script[^>]*src="([^"]+)"', c)

for s in scripts:
    s_url = "https://muse.ai" + s if not s.startswith("http") else s
    try:
        content = urllib.request.urlopen(urllib.request.Request(s_url, headers={"User-Agent": "Mozilla/5.0"}), timeout=5).read().decode("utf-8")
        if "/peer/accept" in content:
            print(f"\n--- MATCH IN {s} ---")
            for m in re.finditer(r'/peer/accept', content):
                start = max(0, m.start() - 100)
                end = min(len(content), m.end() + 300)
                print(content[start:end])
    except Exception:
        pass
