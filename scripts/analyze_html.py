import re

with open('scripts/muse_page_dump.html', 'r', encoding='utf-8') as f:
    c = f.read()

print("HTML size:", len(c))
print("Matches for isGeoGated:", len(re.findall(r'isGeoGated', c)))
print("Matches for waitlist:", len(re.findall(r'waitlist', c)))
print("Matches for Hatch/hatch:", len(re.findall(r'hatch', c, re.I)))

scripts = re.findall(r'<script[^>]*src="([^"]+)"', c)
print(f"Scripts count: {len(scripts)}")
for s in scripts:
    print("Script:", s)

# Print lines containing isGeoGated or waitlist
for line in c.split("\n"):
    if any(k in line for k in ["isGeoGated", "waitlist", "resolvedDestination", "hasHatchAccess"]):
        print("LINE:", line[:300])
