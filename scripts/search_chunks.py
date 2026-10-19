import urllib.request
import re

chunks = [
    "0s75stlmk8kbp.js",
    "1ti4-18rkngba.js",
    "3cfv2xt2lyyd0.js",
    "3bac_x841c6en.js",
    "0d9a236stbk__.js",
    "3b6-ppe_7z9s2.js",
    "0blqw8ajecl7o.js",
    "18vfigcodde__.js",
    "2vc8ai3vban9r.js",
    "1o54q-v3qwf0s.js",
    "3qboj8_74hu5g.js",
    "1d7k5o86hwm28.js",
    "1276qxj07m6r7.js",
    "1xvfk-xwuym87.js",
    "2o12axoangi7u.js",
    "1gk24dyk_v5nw.js",
    "1npkdi7ysab-6.js",
    "2ce1vys900qg4.js",
    "0-2-yc0_v7hbv.js",
    "0cotgbnihlt8v.js",
    "3nqwlj4ftg9ca.js",
    "285igq3ps2k29.js",
    "0hkqb4740qxzc.js",
    "1wk1sqzy19q-x.js",
    "403gedalid7b0.js",
    "22y-c9s_pqt6i.js",
    "0-h-pu3acjn68.js",
    "3y40cubq0knvw.js"
]

base = "https://muse.ai/_next/static/chunks/"

for c in chunks:
    url = f"{base}{c}?dpl=dpl_13w2XhxKwKs7oW6RrPKNJxMESSbw"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            code = r.read().decode('utf-8', errors='ignore')
        if "peer/accept" in code or "accept#" in code or "Sign in to accept this invitation" in code:
            print(f"=== FOUND IN {c} ===")
            matches = re.findall(r".{0,150}(?:peer/accept|Sign in to accept|invitation).{0,150}", code)
            for m in matches[:10]:
                print("MATCH:", m)
    except Exception as e:
        pass
