import urllib.request
import re

url = 'https://muse.ai/_next/static/chunks/3z8tbqkzsxq-c.js'
data = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=10).read().decode('utf-8', errors='ignore')

# Search for what happens with hasHatchAccess
matches = re.finditer(r'hasHatchAccess', data)
for m in matches:
    print(data[max(0, m.start() - 200): min(len(data), m.end() + 300)])
    print('='*60)
