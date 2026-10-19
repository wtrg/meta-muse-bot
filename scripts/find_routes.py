import urllib.request
import re

# Search chunks for route definitions
with open('scripts/muse_page_dump.html', 'r', encoding='utf-8') as f:
    c = f.read()

scripts = re.findall(r'<script[^>]*src="([^"]+)"', c)

routes = set()
for s in scripts:
    s_url = "https://muse.ai" + s if not s.startswith("http") else s
    try:
        content = urllib.request.urlopen(urllib.request.Request(s_url, headers={"User-Agent": "Mozilla/5.0"}), timeout=5).read().decode("utf-8")
        # Find paths starting with "/"
        matches = re.findall(r'\"(/[a-zA-Z0-9_\-\/]+)\"', content)
        for m in matches:
            if any(k in m for k in ["chat", "app", "dashboard", "home", "prompt", "session", "access", "thread", "conversation", "idea"]):
                routes.add(m)
    except Exception:
        pass

print("Routes found:")
for r in sorted(routes):
    print(" -", r)
