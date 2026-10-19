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

chunks = re.findall(r'/_next/static/chunks/[a-zA-Z0-9_\-\.]+\.js', html)

for c in set(chunks):
    if c == '/_next/static/chunks/3z8tbqkzsxq-c.js':
        continue
    url = 'https://muse.ai' + c
    try:
        data = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=5).read().decode('utf-8', errors='ignore')
        if 'resolvedDestination' in data or 'hasHatchAccess' in data:
            print('MATCH IN:', c)
            for match in re.finditer(r'(?:resolvedDestination|hasHatchAccess)', data):
                print(data[max(0, match.start() - 150): min(len(data), match.end() + 250)])
                print('---')
    except Exception as e:
        pass
