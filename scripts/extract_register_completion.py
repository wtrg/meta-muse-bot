import urllib.request
import re

url = 'https://muse.ai/_next/static/chunks/1s0sjy-6uizwo.js?dpl=dpl_13w2XhxKwKs7oW6RrPKNJxMESSbw'
text = urllib.request.urlopen(url).read().decode('utf-8', errors='ignore')

matches = list(re.finditer(r'register-completion[^\"]*', text))
print(f"Total occurrences: {len(matches)}")
for m in matches:
    print("Match:", m.group())
    start = max(0, m.start() - 100)
    end = min(len(text), m.end() + 300)
    print(text[start:end])
    print("-" * 50)
