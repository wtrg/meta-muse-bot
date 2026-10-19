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
try:
    html = urllib.request.urlopen(req).read().decode('utf-8', errors='ignore')
except Exception as e:
    print('Error loading html:', e)
    exit(1)

chunks = re.findall(r'/_next/static/chunks/[a-zA-Z0-9_\-\.]+\.js', html)
print('Total chunk matches:', len(chunks))

for c in set(chunks):
    url = 'https://muse.ai' + c
    try:
        data = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=5).read().decode('utf-8', errors='ignore')
        if 'hasHatchAccess' in data:
            print('MATCH IN:', c)
            for match in re.finditer(r'hasHatchAccess', data):
                start = max(0, match.start() - 100)
                end = min(len(data), match.end() + 200)
                print('Snippet:', data[start:end])
                print('---')
    except Exception as e:
        pass
