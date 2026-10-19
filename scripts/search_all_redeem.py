import urllib.request
import re

chunks = [
    "1-gj2rmtigpe9.js", "0d9a236stbk__.js", "3b6-ppe_7z9s2.js", "0blqw8ajecl7o.js",
    "0s75stlmk8kbp.js", "18vfigcodde__.js", "2vc8ai3vban9r.js", "1ti4-18rkngba.js",
    "1o54q-v3qwf0s.js", "3qboj8_74hu5g.js", "turbopack-1x-0r2hybyb69.js", "1d7k5o86hwm28.js",
    "1276qxj07m6r7.js", "1xvfk-xwuym87.js", "2o12axoangi7u.js", "1gk24dyk_v5nw.js",
    "1npkdi7ysab-6.js", "2ce1vys900qg4.js", "0-2-yc0_v7hbv.js", "0cotgbnihlt8v.js",
    "3nqwlj4ftg9ca.js", "285igq3ps2k29.js", "3cfv2xt2lyyd0.js", "0hkqb4740qxzc.js",
    "1wk1sqzy19q-x.js", "403gedalid7b0.js", "22y-c9s_pqt6i.js", "0-h-pu3acjn68.js",
    "3bac_x841c6en.js", "3y40cubq0knvw.js"
]

base = "https://muse.ai/_next/static/chunks/"

for c in chunks:
    url = f"{base}{c}?dpl=dpl_13w2XhxKwKs7oW6RrPKNJxMESSbw"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            code = r.read().decode('utf-8', errors='ignore')
        if "invite_redeem" in code:
            print(f"=== MATCH IN {c} ===")
            idx = code.find("invite_redeem")
            while idx != -1:
                print(code[max(0, idx-100):min(len(code), idx+300)])
                idx = code.find("invite_redeem", idx + 1)
    except Exception as e:
        pass
