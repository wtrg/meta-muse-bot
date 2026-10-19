import urllib.request
import json
import re

with open('scripts/muse_accounts.json', 'r', encoding='utf-8') as f:
    accs = json.load(f)

cookies = accs[0]['cookies']
cookie_str = '; '.join([f"{c['name']}={c['value']}" for c in cookies])

req = urllib.request.Request('https://muse.ai/access', headers={
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
    'Cookie': cookie_str
})
html = urllib.request.urlopen(req).read().decode('utf-8', errors='ignore')

pos = html.find('waitlistStatus')
while pos != -1:
    print('Found at', pos)
    print(html[pos-100:pos+400])
    print('='*50)
    pos = html.find('waitlistStatus', pos + 1)
