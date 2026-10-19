import urllib.request
import re
import json

with open('scripts/muse_accounts.json', 'r', encoding='utf-8') as f:
    accs = json.load(f)

cookies = accs[0]['cookies']
cookie_str = '; '.join([f"{c['name']}={c['value']}" for c in cookies])

req = urllib.request.Request('https://muse.ai/access', headers={
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
    'Cookie': cookie_str
})
html = urllib.request.urlopen(req).read().decode('utf-8', errors='ignore')

# Unescape
clean = html.replace('\\"', '"')
paths = re.findall(r'"pagePath":"([^"]+)"', clean)
print('Page paths:', set(paths))

# Search for any string starting with / in clean
app_routes = re.findall(r'"/(c/[^"]+|chat[^"]*|app[^"]*|workspace[^"]*|threads?[^"]*|onboarding[^"]*|settings[^"]*)"', clean)
print('App routes:', set(app_routes))
