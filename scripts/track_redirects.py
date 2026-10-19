import curl_cffi.requests as requests
try:
    r = requests.get("https://muse.ai", impersonate="chrome120")
    print("Status:", r.status_code)
    print("Final URL:", r.url)
    print("History:", [h.url for h in r.history])
except Exception:
    import subprocess
    cmd = ["curl.exe", "-I", "-L", "-s", "https://muse.ai"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    print(res.stdout)
