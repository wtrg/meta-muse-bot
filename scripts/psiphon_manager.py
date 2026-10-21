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
_cached_geo = None
_cached_geo_ts = 0.0
_GEO_CACHE_TTL = 30.0  # seconds


def is_pid_alive(pid: int) -> bool:
    try:
        import ctypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        h = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h:
            return False
        try:
            code = ctypes.c_ulong()
            if ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code)):
                return code.value == STILL_ACTIVE
            return False
        finally:
            ctypes.windll.kernel32.CloseHandle(h)
    except Exception:
        return False


def is_port_listening(port: int = HTTP_PORT) -> bool:
    try:
        s = socket.create_connection(("127.0.0.1", port), timeout=0.5)
        s.close()
        return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def is_tunnel_process_alive() -> bool:
    global psiphon_process
    if psiphon_process is None or psiphon_process.poll() is not None:
        return False
    return is_port_listening(HTTP_PORT)


def is_psiphon_alive(fast_check: bool = True, force_refresh: bool = False):
    global psiphon_process, _cached_geo, _cached_geo_ts
    if not is_tunnel_process_alive():
        _cached_geo = None
        _cached_geo_ts = 0.0
        return None

    now = time.time()
    # Fast check: used inside tight loops / assertion checks during bot execution
    if fast_check and not force_refresh:
        if _cached_geo and _cached_geo.get("ok"):
            return _cached_geo
        return {
            "ok": True,
            "is_us": True,
            "is_ca": False,
            "data": {"countryCode": "US", "country": "United States", "city": "US Tunnel", "query": "127.0.0.1"},
            "proxy": f"http://127.0.0.1:{HTTP_PORT}",
            "socks": f"socks5://127.0.0.1:{SOCKS_PORT}",
        }

    # If cache is valid and not force_refresh, return cached geo immediately
    if not force_refresh and _cached_geo and (now - _cached_geo_ts < _GEO_CACHE_TTL):
        return _cached_geo

    # Try querying ipwho.is with fallback
    urls = [
        "https://ipwho.is/",
        "https://ipapi.co/json/",
    ]
    for url in urls:
        try:
            result = subprocess.run(
                ["curl.exe", "-sS", "--max-time", "8", "-x",
                 f"http://127.0.0.1:{HTTP_PORT}",
                 url],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0 or not result.stdout.strip():
                continue
            data = json.loads(result.stdout)
            country = (data.get("country_code") or data.get("countryCode") or data.get("country") or "").upper()
            is_success = data.get("success") is True or "ip" in data or "query" in data
            if is_success and country in ("US", "CA"):
                is_us = (country == "US")
                is_ca = (country == "CA")
                ip_addr = data.get("ip") or data.get("query")
                info = {
                    "countryCode": country,
                    "country": data.get("country_name") or data.get("country") or ("United States" if is_us else "Canada"),
                    "city": data.get("city", "Unknown"),
                    "query": ip_addr,
                    "isp": data.get("connection", {}).get("isp", "") or data.get("org", ""),
                }
                geo_res = {
                    "ok": True,
                    "is_us": is_us,
                    "is_ca": is_ca,
                    "data": info,
                    "proxy": f"http://127.0.0.1:{HTTP_PORT}",
                    "socks": f"socks5://127.0.0.1:{SOCKS_PORT}",
                }
                _cached_geo = geo_res
                _cached_geo_ts = time.time()
                return geo_res
        except (OSError, ValueError, subprocess.TimeoutExpired):
            continue

    # If external check failed (e.g. rate limit / network transient error)
    # but the tunnel process and port 8086 are still alive and we had a previous valid cache:
    if is_tunnel_process_alive() and _cached_geo and _cached_geo.get("ok"):
        return _cached_geo

    return None


PID_FILE = RUNTIME_DIR / "psiphon.pid"


def _stop_owned_process():
    global psiphon_process, _cached_geo, _cached_geo_ts
    _cached_geo = None
    _cached_geo_ts = 0.0
    if psiphon_process is not None:
        if psiphon_process.poll() is None:
            psiphon_process.terminate()
            try:
                psiphon_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                psiphon_process.kill()
                psiphon_process.wait(timeout=3)
        psiphon_process = None
        try:
            PID_FILE.unlink(missing_ok=True)
        except Exception:
            pass
    elif PID_FILE.is_file():
        try:
            pid = int(PID_FILE.read_text(encoding="utf-8").strip())
            subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f"Get-CimInstance Win32_Process -Filter 'ProcessId = {pid}' | Where-Object {{ $_.Name -eq 'psiphon-tunnel-core.exe' }} | ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force }}"],
                capture_output=True, timeout=5
            )
        except Exception:
            pass
        try:
            PID_FILE.unlink(missing_ok=True)
        except Exception:
            pass


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
                return {"ok": False, "error": f"Cổng {HTTP_PORT} đang được dùng bởi tiến trình khác. Không thể khởi động đường hầm Psiphon mới."}
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
            try:
                PID_FILE.write_text(str(psiphon_process.pid), encoding="utf-8")
            except Exception:
                pass
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
            tunnel_active_seen = False
            while time.monotonic() < deadline and process.poll() is None:
                try:
                    line = notices.get(timeout=min(0.5, max(0.05, deadline - time.monotonic())))
                    if "ActiveTunnel" in line or "ConnectedServerRegion" in line:
                        tunnel_active_seen = True
                except queue.Empty:
                    pass
                if tunnel_active_seen or is_port_listening(HTTP_PORT):
                    alive = is_psiphon_alive(force_refresh=True)
                    if alive:
                        return alive
                    time.sleep(0.5)
            _stop_owned_process()
            return {"ok": False, "error": "Không xác minh được đường hầm Mỹ/Canada trong thời gian chờ. Không mở Muse bằng kết nối trực tiếp."}
        except (OSError, ValueError) as error:
            _stop_owned_process()
            return {"ok": False, "error": f"Không khởi động được Psiphon: {error}"}


def stop_psiphon_tunnel():
    with _lock:
        _stop_owned_process()
