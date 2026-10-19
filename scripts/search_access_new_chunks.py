import urllib.request
import re

new_chunks = [
    "078xt26s0yyq3.js", "0ss2eqiws_lbt.js", "1g8ttzk162o8g.js", "1j5tnav_z-sin.js",
    "2zzdp6s-pl-x4.js", "0tn9ih25xpq84.js", "17jqbibawqr8i.js", "21e_q67qq8rwz.js",
    "1393-4-xn6nzl.js", "2vfrqtbhlm3sv.js", "1s0sjy-6uizwo.js", "2iqc1is9flbxt.js",
    "15tcg-f4bm08k.js", "00jz7fqmldi2t.js"
]

base = "https://muse.ai/_next/static/chunks/"

for c in new_chunks:
    url = f"{base}{c}?dpl=dpl_13w2XhxKwKs7oW6RrPKNJxMESSbw"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            code = r.read().decode('utf-8', errors='ignore')
        matches = re.findall(r".{0,100}(?:invite|waitlist|voucher|claim|code).{0,100}", code, flags=re.IGNORECASE)
        if matches:
            print(f"=== FOUND {len(matches)} MATCHES IN {c} ===")
            for m in matches[:6]:
                print("   ", m.strip())
    except Exception as e:
        pass
