"""Manage the bundled free Psiphon tunnel without changing system VPN settings."""
import json
import os
import queue
import socket
import subprocess
import threading
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CORE_EXE = BASE_DIR / "bin" / "psiphon-tunnel-core.exe"
SOURCE_DIR = Path(os.environ.get("LOCALAPPDATA", "")) / "Psiphon3"
RUNTIME_DIR = BASE_DIR / "bin" / "psiphon-runtime-8086"
HTTP_PORT = 8086
SOCKS_PORT = 1086
psiphon_process = None
_lock = threading.Lock()


def is_psiphon_alive():
    try:
        result = subprocess.run(
            ["curl.exe", "-sS", "--max-time", "4", "-x",
             f"http://127.0.0.1:{HTTP_PORT}",
             "https://ipwho.is/"],
            capture_output=True, text=True, timeout=5,
        )
        data = json.loads(result.stdout)
        country = data.get("country_code", "")
        if result.returncode == 0 and data.get("success") is True and country in ("US", "CA"):
            info = {"countryCode": country, "country": data.get("country"),
                    "city": data.get("city"), "query": data.get("ip"),
                    "isp": data.get("connection", {}).get("isp", "")}
            return {"ok": True, "is_us": True, "data": info,
                    "proxy": f"http://127.0.0.1:{HTTP_PORT}",
                    "socks": f"socks5://127.0.0.1:{SOCKS_PORT}"}
    except (OSError, ValueError, subprocess.TimeoutExpired):
        pass
    return None


def _stop_owned_process():
    global psiphon_process
    if psiphon_process is not None:
        if psiphon_process.poll() is None:
            psiphon_process.terminate()
            try:
                psiphon_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                psiphon_process.kill()
                psiphon_process.wait(timeout=3)
        psiphon_process = None


def start_psiphon_tunnel(timeout=25):
    global psiphon_process
    with _lock:
        alive = is_psiphon_alive()
        if alive:
            return alive
        _stop_owned_process()
        with socket.socket() as probe:
            probe.settimeout(0.5)
            if probe.connect_ex(("127.0.0.1", HTTP_PORT)) == 0:
                return {"ok": False, "error": "Cổng 8086 đang được dùng nhưng chưa xác minh được IP Mỹ/Canada. Hãy kiểm tra đường hầm hiện có."}
        source_config = SOURCE_DIR / "psiphon.config"
        server_list = SOURCE_DIR / "server_list.dat"
        if not CORE_EXE.is_file() or not source_config.is_file() or not server_list.is_file():
            return {"ok": False, "error": "Thiếu Psiphon Core, psiphon.config hoặc server_list.dat. Chưa thể tự kết nối."}
        try:
            config = json.loads(source_config.read_text(encoding="utf-8-sig"))
            config = {key: value for key, value in config.items() if not key.startswith("Migrate")}
            config.update(DataRootDirectory=str(RUNTIME_DIR), EgressRegion="US", LocalHttpProxyPort=HTTP_PORT,
                          LocalSocksProxyPort=SOCKS_PORT)
            RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
            config_path = RUNTIME_DIR / "psiphon.config"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            psiphon_process = subprocess.Popen(
                [str(CORE_EXE), "-config", str(config_path), "-serverList", str(server_list),
                 "-dataRootDirectory", str(RUNTIME_DIR), "-formatNotices"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            process = psiphon_process
            notices = queue.Queue(maxsize=128)

            def drain():
                for line in process.stdout:
                    try:
                        notices.put_nowait(line)
                    except queue.Full:
                        pass
                process.stdout.close()

            threading.Thread(target=drain, daemon=True).start()
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline and process.poll() is None:
                try:
                    line = notices.get(timeout=min(0.25, max(0.01, deadline-time.monotonic())))
                except queue.Empty:
                    continue
                if "ActiveTunnel" in line or "ConnectedServerRegion" in line:
                    alive = is_psiphon_alive()
                    if alive:
                        return alive
            _stop_owned_process()
            return {"ok": False, "error": "Không xác minh được đường hầm Mỹ/Canada trong thời gian chờ. Không mở Muse bằng kết nối trực tiếp."}
        except (OSError, ValueError) as error:
            _stop_owned_process()
            return {"ok": False, "error": f"Không khởi động được Psiphon: {error}"}


def stop_psiphon_tunnel():
    with _lock:
        _stop_owned_process()
