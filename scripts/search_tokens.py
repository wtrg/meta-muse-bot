import urllib.request
import re

url = 'https://muse.ai/_next/static/chunks/3z8tbqkzsxq-c.js'
data = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=10).read().decode('utf-8', errors='ignore')

matches = re.findall(r'"([a-zA-Z0-9_]{3,30})"', data)
relevant = [m for m in matches if any(k in m.lower() for k in ['waitlist', 'destination', 'activation', 'chat', 'hatch', 'geogated'])]
print('Relevant tokens:', set(relevant))
