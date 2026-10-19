import urllib.request
import re

with open('scripts/muse_page_dump.html', 'r', encoding='utf-8') as f:
    c = f.read()

scripts = re.findall(r'<script[^>]*src="([^"]+)"', c)

for s in scripts:
    s_url = "https://muse.ai" + s if not s.startswith("http") else s
    try:
        content = urllib.request.urlopen(urllib.request.Request(s_url, headers={"User-Agent": "Mozilla/5.0"}), timeout=5).read().decode("utf-8")
        if "isPeerInviteLandingPathname" in content:
            idx = content.find("isPeerInviteLandingPathname")
            print(f"\n--- {s} ---")
            print(content[max(0, idx-50):min(len(content), idx+300)])
    except Exception:
        pass
