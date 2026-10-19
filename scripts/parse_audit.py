import json
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

data = json.load(open('scripts/audit_network_dump.json', encoding='utf-8'))
print(f"Total network calls: {len(data)}")

for idx, d in enumerate(data):
    url = d.get('url', '')
    req_type = d.get('type')
    status = d.get('status', d.get('method', ''))
    print(f"\n#{idx} [{req_type}] {status} {url}")
    if req_type == 'REQUEST' and d.get('post_data'):
        print(f"  POST DATA: {d.get('post_data')[:400]}")
    if req_type == 'RESPONSE' and d.get('body'):
        print(f"  BODY: {d.get('body')[:400]}")
