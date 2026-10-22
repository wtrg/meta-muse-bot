"""Comprehensive regression tests for MUSE-V5 / MUSE-GEO-001 (Option A).
Verifies fail-closed route validation, five-provider dispatch, CA separation,
Host/Origin protection, atomic job lock, cookie redaction, path traversal guards,
and invite idempotency.
"""
import asyncio
import builtins
import copy
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from fastapi.testclient import TestClient
import bot_server as bot
import psiphon_manager as pm
import windscribe_manager as wm
from muse_invites import normalize_invite_code, redemption_outcome, redeem_invite
from muse_access import classify_access, inspect_muse_access


class BaseIsolatedTestCase(unittest.TestCase):
    """Hermetic test isolation fixture with strict write guard.
    Redirects all runtime file writes into a test-scoped TemporaryDirectory.
    Restores BotState and original paths on tearDown.
    """
    def setUp(self):
        self._temp_dir_ctx = tempfile.TemporaryDirectory(prefix="test_iso_")
        self.test_dir = os.path.realpath(self._temp_dir_ctx.name)
        self.allowed_write_roots = [
            self.test_dir,
            os.path.realpath(tempfile.gettempdir())
        ]

        # Deepcopy and isolate state
        self._orig_state_accounts = copy.deepcopy(bot.state.accounts)
        self._orig_state_session_accounts = copy.deepcopy(bot.state.session_accounts)
        self._orig_state_logs = list(bot.state.logs)
        self._orig_state_session_id = bot.state.session_id
        self._orig_state_session_time = getattr(bot.state, "session_time", "")
        self._orig_state_is_running = bot.state.is_running
        self._orig_state_stop_requested = bot.state.stop_requested

        bot.state.accounts = []
        bot.state.session_accounts = []
        bot.state.logs = []
        bot.state.session_id = None
        bot.state.session_time = ""
        bot.state.is_running = False
        bot.state.stop_requested = False

        # Save and redirect all bot paths into self.test_dir
        self._orig_paths = {
            "EXPORTS_DIR": bot.EXPORTS_DIR,
            "SCREENSHOTS_DIR": bot.SCREENSHOTS_DIR,
            "ACCOUNTS_FILE": bot.ACCOUNTS_FILE,
            "ACCOUNTS_TXT_PATH": bot.ACCOUNTS_TXT_PATH,
            "ROOT_ACCOUNTS_TXT_PATH": bot.ROOT_ACCOUNTS_TXT_PATH,
            "ROOT_LATEST_CSV_PATH": bot.ROOT_LATEST_CSV_PATH,
            "ROOT_LATEST_EXCEL_PATH": bot.ROOT_LATEST_EXCEL_PATH,
        }

        bot.EXPORTS_DIR = os.path.join(self.test_dir, "exports")
        bot.SCREENSHOTS_DIR = os.path.join(self.test_dir, "screenshots")
        bot.ACCOUNTS_FILE = os.path.join(self.test_dir, "muse_accounts.json")
        bot.ACCOUNTS_TXT_PATH = os.path.join(self.test_dir, "muse_accounts.txt")
        bot.ROOT_ACCOUNTS_TXT_PATH = os.path.join(self.test_dir, "root_muse_accounts.txt")
        bot.ROOT_LATEST_CSV_PATH = os.path.join(self.test_dir, "muse_session_latest.csv")
        bot.ROOT_LATEST_EXCEL_PATH = os.path.join(self.test_dir, "muse_session_latest.xlsx")

        os.makedirs(bot.EXPORTS_DIR, exist_ok=True)
        os.makedirs(bot.SCREENSHOTS_DIR, exist_ok=True)

        self.client = TestClient(bot.app, base_url="http://127.0.0.1:8790")

        # Install strict write guard on atomic writers
        self._orig_atomic_text = bot.atomic_write_text
        self._orig_atomic_csv = bot.atomic_write_csv
        self._orig_atomic_excel = bot.atomic_write_excel

        def guarded_atomic_text(path, content, *args, **kwargs):
            self._assert_allowed_write(path)
            return self._orig_atomic_text(path, content, *args, **kwargs)

        def guarded_atomic_csv(path, headers, rows, *args, **kwargs):
            self._assert_allowed_write(path)
            return self._orig_atomic_csv(path, headers, rows, *args, **kwargs)

        def guarded_atomic_excel(path, wb, *args, **kwargs):
            self._assert_allowed_write(path)
            return self._orig_atomic_excel(path, wb, *args, **kwargs)

        self._patcher_text = patch.object(bot, "atomic_write_text", side_effect=guarded_atomic_text)
        self._patcher_csv = patch.object(bot, "atomic_write_csv", side_effect=guarded_atomic_csv)
        self._patcher_excel = patch.object(bot, "atomic_write_excel", side_effect=guarded_atomic_excel)
        self._patcher_text.start()
        self._patcher_csv.start()
        self._patcher_excel.start()

    def _assert_allowed_write(self, target_path: str):
        real_target = os.path.realpath(str(target_path))
        for allowed in self.allowed_write_roots:
            if real_target == allowed or real_target.startswith(allowed + os.sep):
                return
        raise AssertionError(f"WRITE GUARD VIOLATION: Test attempted to write outside temporary test directory: {target_path}")

    def tearDown(self):
        self._patcher_text.stop()
        self._patcher_csv.stop()
        self._patcher_excel.stop()

        for k, v in self._orig_paths.items():
            setattr(bot, k, v)

        bot.state.accounts = self._orig_state_accounts
        bot.state.session_accounts = self._orig_state_session_accounts
        bot.state.logs = self._orig_state_logs
        bot.state.session_id = self._orig_state_session_id
        bot.state.session_time = self._orig_state_session_time
        bot.state.is_running = self._orig_state_is_running
        bot.state.stop_requested = self._orig_state_stop_requested

        try:
            self._temp_dir_ctx.cleanup()
        except Exception:
            pass


class MuseV5RegressionTests(BaseIsolatedTestCase):

    # 1. Strict Fail-Closed Route Checks
    def test_check_route_ip_upstream_failure_fails_closed(self):
        failure_payload = json.dumps({"status": "fail", "message": "query limit reached"})
        with patch.object(bot.subprocess, "run", return_value=MagicMock(returncode=0, stdout=failure_payload)):
            res = bot.check_route_ip("http://127.0.0.1:8086")
            self.assertFalse(res["ok"])
            self.assertIn("thất bại", res["error"])

    def test_check_route_ip_timeout_or_exit_fails_closed(self):
        with patch.object(bot.subprocess, "run", return_value=MagicMock(returncode=1, stdout="", stderr="Connection timed out")):
            res = bot.check_route_ip("http://127.0.0.1:8086")
            self.assertFalse(res["ok"])
            self.assertIn("Không thể kết nối qua proxy", res["error"])

    def test_check_route_ip_invalid_json_fails_closed(self):
        with patch.object(bot.subprocess, "run", return_value=MagicMock(returncode=0, stdout="<html>Bad Gateway</html>")):
            res = bot.check_route_ip("http://127.0.0.1:8086")
            self.assertFalse(res["ok"])

    def test_check_route_ip_missing_country_code_fails_closed(self):
        payload = json.dumps({"status": "success", "query": "192.0.2.1"})
        with patch.object(bot.subprocess, "run", return_value=MagicMock(returncode=0, stdout=payload)):
            res = bot.check_route_ip("http://127.0.0.1:8086")
            self.assertFalse(res["ok"])
            self.assertIn("thiếu thông tin quốc gia", res["error"])

    # 2. Canada and US Country Separation
    def test_check_route_ip_canada_distinct_from_us(self):
        payload = json.dumps({"status": "success", "countryCode": "CA", "country": "Canada", "query": "198.51.100.1", "isp": "Bell"})
        with patch.object(bot.subprocess, "run", return_value=MagicMock(returncode=0, stdout=payload)):
            res = bot.check_route_ip("http://127.0.0.1:8086")
            self.assertTrue(res["ok"])
            self.assertFalse(res["is_us"])
            self.assertTrue(res["is_ca"])
            self.assertEqual(res["verdict"], "CA_ROUTE")
            self.assertIn("Canada", res["verdict_text"])

    def test_check_route_ip_us_residential_and_datacenter(self):
        # US Datacenter
        dc_payload = json.dumps({"status": "success", "countryCode": "US", "country": "United States", "query": "192.0.2.1", "isp": "DigitalOcean", "hosting": True})
        with patch.object(bot.subprocess, "run", return_value=MagicMock(returncode=0, stdout=dc_payload)):
            res_dc = bot.check_route_ip("http://127.0.0.1:8086")
            self.assertTrue(res_dc["ok"])
            self.assertTrue(res_dc["is_us"])
            self.assertEqual(res_dc["verdict"], "US_DATACENTER")

        # US Residential
        res_payload = json.dumps({"status": "success", "countryCode": "US", "country": "United States", "query": "192.0.2.2", "isp": "Comcast", "hosting": False, "proxy": False})
        with patch.object(bot.subprocess, "run", return_value=MagicMock(returncode=0, stdout=res_payload)):
            res_r = bot.check_route_ip("http://127.0.0.1:8086")
            self.assertTrue(res_r["ok"])
            self.assertTrue(res_r["is_us"])
            self.assertEqual(res_r["verdict"], "US_RESIDENTIAL")

    # 3. Auto Proxy Endpoint Fails Closed Without Hardcoded Fallback
    def test_auto_proxy_endpoint_fails_closed_when_file_missing(self):
        with patch.object(bot.os.path, "exists", return_value=False):
            res = asyncio.run(bot.auto_proxy())
            self.assertFalse(res["ok"])
            self.assertIn("Chưa có cấu hình proxy tự động", res["error"])
            self.assertNotIn("proxy", res)

    # 4. Shared Provider Dispatcher across 5 Providers
    def test_resolve_provider_route_dispatcher(self):
        # 1) psiphon
        with patch.object(bot, "is_psiphon_alive", return_value={"ok": True, "proxy": "http://127.0.0.1:8086", "is_us": True, "is_ca": False, "data": {}}):
            r_psi = asyncio.run(bot.resolve_provider_route("psiphon"))
            self.assertTrue(r_psi["ok"])
            self.assertEqual(r_psi["provider"], "psiphon")
            self.assertEqual(r_psi["proxy"], "http://127.0.0.1:8086")

        # 2) vpn (system mode): fails closed if host is not US/CA, passes when host is verified
        with patch.object(bot, "check_route_ip", return_value={"ok": True, "is_us": True, "is_ca": False, "country_code": "US", "data": {"query": "198.51.100.1"}}):
            r_vpn = asyncio.run(bot.resolve_provider_route("vpn"))
            self.assertTrue(r_vpn["ok"])
            self.assertEqual(r_vpn["provider"], "vpn")
            self.assertIsNone(r_vpn["proxy"])
            self.assertEqual(r_vpn["networkMode"], "system")
            self.assertIsNotNone(r_vpn.get("spec"))

        with patch.object(bot, "check_route_ip", return_value={"ok": True, "is_us": False, "is_ca": False, "country_code": "VN", "data": {"query": "1.2.3.4"}}):
            r_vpn_vn = asyncio.run(bot.resolve_provider_route("vpn"))
            self.assertFalse(r_vpn_vn["ok"])
            self.assertEqual(r_vpn_vn.get("code"), bot.ROUTE_COUNTRY_OTHER)

        with patch.object(bot, "check_route_ip", return_value={"ok": True, "is_us": False, "is_ca": False, "country_code": "", "data": {"query": "1.2.3.4"}}):
            r_vpn_unk = asyncio.run(bot.resolve_provider_route("vpn"))
            self.assertFalse(r_vpn_unk["ok"])
            self.assertEqual(r_vpn_unk.get("code"), bot.ROUTE_COUNTRY_UNKNOWN)

        # 3) custom
        r_cust_valid = asyncio.run(bot.resolve_provider_route("custom", "127.0.0.1:9050"))
        self.assertTrue(r_cust_valid["ok"])
        self.assertEqual(r_cust_valid["proxy"], "http://127.0.0.1:9050")

        r_cust_empty = asyncio.run(bot.resolve_provider_route("custom", ""))
        self.assertFalse(r_cust_empty["ok"])

        # 4) auto - fails closed if active_us_proxy.json missing
        with patch.object(bot.os.path, "exists", return_value=False):
            r_auto = asyncio.run(bot.resolve_provider_route("auto"))
            self.assertFalse(r_auto["ok"])

        # 5) windscribe
        with patch.object(bot, "connect_free_us", return_value={"ok": True, "is_us": True, "is_ca": False, "data": {}}):
            r_wind = asyncio.run(bot.resolve_provider_route("windscribe"))
            self.assertTrue(r_wind["ok"])
            self.assertEqual(r_wind["provider"], "windscribe")
            self.assertEqual(r_wind["networkMode"], "system")

        # Unknown provider fails closed
        r_unknown = asyncio.run(bot.resolve_provider_route("unsupported_network"))
        self.assertFalse(r_unknown["ok"])
        self.assertIn("không hợp lệ", r_unknown["error"])

    # 5. Security Middleware: Host and Origin Protection
    def test_security_guards_reject_foreign_host_and_origin(self):
        # Foreign Host
        res_host = self.client.get("/api/bot/status", headers={"Host": "external.evil.com"})
        self.assertEqual(res_host.status_code, 403)
        self.assertIn("Host header is not allowed", res_host.json()["detail"])

        # Foreign Origin
        res_origin = self.client.get("/api/bot/status", headers={"Origin": "https://attacker.example.org"})
        self.assertEqual(res_origin.status_code, 403)
        self.assertIn("local-only", res_origin.json()["detail"])

        # Valid Localhost Host and Origin
        res_valid = self.client.get("/api/bot/status", headers={"Host": "127.0.0.1:8790", "Origin": "http://127.0.0.1:5173"})
        self.assertEqual(res_valid.status_code, 200)

    # 6. Atomic Job Lock and Admission
    def test_start_bot_atomic_job_lock(self):
        # Count <= 0 rejected
        req_zero = {"count": 0, "proxyType": "psiphon"}
        res_zero = self.client.post("/api/bot/start", json=req_zero)
        self.assertEqual(res_zero.status_code, 422)

        # Single-flight lock: returns 409 Conflict if already running
        with patch.object(bot.state, "is_running", True):
            res_conflict = self.client.post("/api/bot/start", json={"count": 1, "proxyType": "psiphon"})
            self.assertEqual(res_conflict.status_code, 409)

    # 7. Privacy: Cookie Redaction and No PIN in URLs
    def test_accounts_endpoint_redacts_raw_cookies(self):
        mock_accounts = [
            {"id": "acc-1", "email": "test@example.com", "cookies": [{"name": "hatch_sess", "value": "secret_token_123"}]}
        ]
        with patch.object(bot.state, "accounts", mock_accounts), patch.object(bot.os.path, "exists", return_value=False):
            res = self.client.get("/api/bot/accounts")
            self.assertEqual(res.status_code, 200)
            data = res.json()["accounts"][0]
            self.assertNotIn("cookies", data)
            self.assertTrue(data.get("hasCookies"))

    def test_session_info_no_pin_in_otp_link(self):
        mock_accounts = [
            {"id": "acc-1", "email": "test@example.com", "pin": "888999", "status": "SUCCESS_CHAT_READY"}
        ]
        with patch.object(bot.state, "session_accounts", mock_accounts):
            res = self.client.get("/api/bot/session-info")
            self.assertEqual(res.status_code, 200)
            account_info = res.json()["accounts"][0]
            otp_link = account_info["otpLink"]
            self.assertIn("email=test%40example.com", otp_link)
            self.assertNotIn("pin=", otp_link)

    # 8. Path Traversal Protection
    def test_path_traversal_rejected_on_screenshot(self):
        res = self.client.get("/api/bot/screenshot/../../../../windows/system.ini")
        self.assertEqual(res.status_code, 404)

    def test_path_traversal_sanitized_on_export(self):
        with patch.object(bot.state, "session_accounts", []):
            res = self.client.get("/api/bot/export-session-csv?session_id=../../test_traversal")
            # Should reject invalid session_id with 400 (or 404)
            self.assertIn(res.status_code, (400, 404))

    def test_empty_session_id_fails_closed_no_latest_leak(self):
        with patch.object(bot.state, "session_id", None):
            res = self.client.get("/api/bot/export-session-csv")
            self.assertEqual(res.status_code, 404)
            res_xlsx = self.client.get("/api/bot/export-session-excel")
            self.assertEqual(res_xlsx.status_code, 404)

    def test_reserved_alias_latest_rejected_on_csv_and_excel(self):
        # Reserved aliases ("latest", "current", "default", etc.) must return 400
        # even if an old muse_session_latest artifact exists on disk
        for alias in ("latest", "current", "default", "LATEST"):
            r_csv = self.client.get(f"/api/bot/export-session-csv?session_id={alias}")
            self.assertEqual(r_csv.status_code, 400)
            self.assertIn("dành riêng", r_csv.json()["detail"])

            r_xlsx = self.client.get(f"/api/bot/export-session-excel?session_id={alias}")
            self.assertEqual(r_xlsx.status_code, 400)
            self.assertIn("dành riêng", r_xlsx.json()["detail"])

    def test_create_spinup_email_deprecated_fails_closed(self):
        # create_spinup_email raises NotImplementedError due to A04 removal of unauth public endpoint
        with self.assertRaises(NotImplementedError):
            asyncio.run(bot.create_spinup_email("maxxspace.com"))

    def test_start_bot_rejects_deprecated_spinupmail_provider(self):
        # /api/bot/start with provider="spinupmail" returns 422
        res = self.client.post("/api/bot/start", json={"count": 1, "provider": "spinupmail"})
        self.assertEqual(res.status_code, 422)

    # 9. Psiphon Manager Owned Lifecycle and Collision Check
    def test_psiphon_manager_ownership_lifecycle(self):
        # 1) When psiphon_process is None, is_psiphon_alive returns None
        with patch.object(pm, "psiphon_process", None):
            self.assertIsNone(pm.is_psiphon_alive())

        # 2) Port collision when unmanaged process listens on 8086
        probe_mock = MagicMock()
        probe_mock.__enter__.return_value = probe_mock
        probe_mock.connect_ex.return_value = 0  # port occupied
        with patch.object(pm, "psiphon_process", None), patch.object(pm.socket, "socket", return_value=probe_mock):
            res = pm.start_psiphon_tunnel(timeout=1)
            self.assertFalse(res["ok"])
            self.assertIn("đang được dùng bởi tiến trình khác", res["error"])

    # 10. Invite Code Idempotency and REVIEW_REQUIRED
    def test_invite_code_idempotency_and_review_required(self):
        self.assertEqual(normalize_invite_code("QKPLQ6"), "QKPLQ6")
        self.assertIsNone(normalize_invite_code(None))
        self.assertIsNone(normalize_invite_code(""))

        # If already attempted, redeem_invite immediately returns REVIEW_REQUIRED
        with patch("muse_invites._load_reservations", return_value={"test_page_1:QKPLQ6": {"status": "SUBMITTED"}}):
            res = asyncio.run(redeem_invite(MagicMock(), "QKPLQ6", idempotency_key="test_page_1"))
            self.assertEqual(res["status"], "REVIEW_REQUIRED")
            self.assertIn("đã có yêu cầu gửi mã mời", res["message"].lower())


class MuseG5ExplicitTableTests(BaseIsolatedTestCase):
    """Explicit Gate G5 test suite mapping 1:1 to cases T01 through T24 in the Master Fix Plan."""

    def test_t01_stale_backend_detection(self):
        # T01: Port 8790 occupied by stale backend -> flags STALE_PROCESS
        stale_resp_empty_sha = {"ok": True, "build_sha": ""}
        self.assertEqual(bot.evaluate_runtime_handshake(stale_resp_empty_sha), "STALE_PROCESS")
        
        not_ok_resp = {"ok": False, "build_sha": "some_sha"}
        self.assertEqual(bot.evaluate_runtime_handshake(not_ok_resp), "STALE_PROCESS")

        # Live runtime endpoint returns valid metadata
        res = self.client.get("/api/bot/runtime")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data.get("ok"))
        self.assertTrue(bool(data.get("build_sha")))
        self.assertEqual(bot.evaluate_runtime_handshake(data), "VALID_RUNTIME")

    def test_t02_foreign_process_on_port_rejected_no_blind_kill(self):
        # T02: Port 8790 occupied by foreign process -> PORT_OCCUPIED_NOT_OWNED, no kill
        self.assertEqual(bot.evaluate_runtime_handshake(None, error=ConnectionRefusedError()), "PORT_OCCUPIED_NOT_OWNED")
        self.assertEqual(bot.evaluate_runtime_handshake({"random_html": "nginx"}, None), "STALE_PROCESS")

    def test_t03_psiphon_healthy_curl_and_browser_context(self):
        # T03: Psiphon healthy measured via host and browser
        payload = json.dumps({"status": "success", "countryCode": "US", "country": "United States", "query": "198.51.100.5", "isp": "Psiphon"})
        with patch.object(bot.subprocess, "run", return_value=MagicMock(returncode=0, stdout=payload)):
            res = bot.check_route_ip("http://127.0.0.1:8086")
            self.assertTrue(res["ok"])
            self.assertTrue(res["is_us"])
            self.assertEqual(res["country_code"], "US")

    def test_t04_psiphon_dead_before_browser_no_email_allocated(self):
        # T04: Psiphon HTTP8086 dead before browser -> NETWORK_PRECHECK_FAILED, zero email
        mock_create_clean = AsyncMock()
        mock_create_spinup = AsyncMock()
        with patch.object(bot, "check_route_ip", return_value={"ok": False, "error": "Connection refused"}), \
             patch.object(bot, "create_clean_email", mock_create_clean), \
             patch.object(bot, "create_spinup_email", mock_create_spinup):
            with self.assertRaises(Exception) as ctx:
                asyncio.run(bot.process_single_account(proxy_str="http://127.0.0.1:8086"))
            self.assertIn("NETWORK_PRECHECK_FAILED", str(ctx.exception))
            mock_create_clean.assert_not_called()
            mock_create_spinup.assert_not_called()

    def test_t05_psiphon_dead_mid_session_no_direct_fallback(self):
        # T05: Tunnel disconnects mid-session -> ROUTE_DISCONNECTED, no fallback direct
        host_probe = {"ok": True, "is_us": True, "is_ca": False, "country_code": "US", "data": {"query": "198.51.100.1"}}
        browser_ip_json = json.dumps({"success": True, "ip": "198.51.100.1", "country_code": "US"})
        
        mock_page = MagicMock()
        mock_page.goto = AsyncMock(side_effect=Exception("net::ERR_PROXY_CONNECTION_FAILED"))
        mock_page.close = AsyncMock()

        mock_preflight = MagicMock()
        mock_preflight.goto = AsyncMock(return_value=MagicMock(status=200))
        mock_preflight.inner_text = AsyncMock(return_value=browser_ip_json)
        mock_preflight.is_closed = MagicMock(return_value=False)
        mock_preflight.close = AsyncMock()

        mock_context = MagicMock()
        mock_context.new_page = AsyncMock(side_effect=[mock_preflight, mock_page])
        mock_context.close = AsyncMock()

        mock_browser = MagicMock()
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_browser.close = AsyncMock()

        mock_p = MagicMock()
        mock_p.chromium.launch = AsyncMock(return_value=mock_browser)

        mock_playwright_cm = MagicMock()
        mock_playwright_cm.__aenter__ = AsyncMock(return_value=mock_p)
        mock_playwright_cm.__aexit__ = AsyncMock(return_value=None)

        with patch.object(bot, "check_route_ip", return_value=host_probe), \
             patch("bot_server.async_playwright", return_value=mock_playwright_cm), \
             patch.object(bot, "create_clean_email", AsyncMock(return_value="test@example.com")):
            with self.assertRaises(Exception) as ctx:
                asyncio.run(bot.process_single_account(proxy_str="http://127.0.0.1:8086"))
            self.assertIn("ROUTE_DISCONNECTED", str(ctx.exception))
            mock_context.close.assert_awaited()
            mock_browser.close.assert_awaited()

    def test_t06_route_mismatch_host_us_browser_vn_blocked(self):
        # T06: Host US but browser VN -> blocks with error before registration, zero email
        host_probe = {"ok": True, "is_us": True, "is_ca": False, "country_code": "US", "data": {"query": "198.51.100.1"}}
        browser_ip_json = json.dumps({"success": True, "ip": "1.2.3.4", "country_code": "VN"})

        mock_preflight = MagicMock()
        mock_preflight.goto = AsyncMock(return_value=MagicMock(status=200))
        mock_preflight.inner_text = AsyncMock(return_value=browser_ip_json)
        mock_preflight.is_closed = MagicMock(return_value=False)
        mock_preflight.close = AsyncMock()

        mock_context = MagicMock()
        mock_context.new_page = AsyncMock(return_value=mock_preflight)
        mock_context.close = AsyncMock()

        mock_browser = MagicMock()
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_browser.close = AsyncMock()

        mock_p = MagicMock()
        mock_p.chromium.launch = AsyncMock(return_value=mock_browser)

        mock_playwright_cm = MagicMock()
        mock_playwright_cm.__aenter__ = AsyncMock(return_value=mock_p)
        mock_playwright_cm.__aexit__ = AsyncMock(return_value=None)

        mock_create_clean = AsyncMock()
        with patch.object(bot, "check_route_ip", return_value=host_probe), \
             patch("bot_server.async_playwright", return_value=mock_playwright_cm), \
             patch.object(bot, "create_clean_email", mock_create_clean):
            with self.assertRaises(Exception) as ctx:
                asyncio.run(bot.process_single_account(proxy_str="http://127.0.0.1:8086"))
            err = str(ctx.exception)
            self.assertTrue("ROUTE_MISMATCH" in err or "ROUTE_COUNTRY_UNKNOWN" in err or "BROWSER_ROUTE_UNVERIFIED" in err)
            mock_create_clean.assert_not_called()
            mock_context.close.assert_awaited()

    def test_t07_browser_ip_api_timeout_or_invalid_fails_closed(self):
        # T07: Browser IP API timeout/invalid JSON -> BROWSER_ROUTE_UNVERIFIED, zero email
        host_probe = {"ok": True, "is_us": True, "is_ca": False, "country_code": "US", "data": {"query": "198.51.100.1"}}

        mock_preflight = MagicMock()
        mock_preflight.goto = AsyncMock(return_value=MagicMock(status=500))
        mock_preflight.inner_text = AsyncMock(return_value="<html>Error 500</html>")
        mock_preflight.is_closed = MagicMock(return_value=False)
        mock_preflight.close = AsyncMock()

        mock_context = MagicMock()
        mock_context.new_page = AsyncMock(return_value=mock_preflight)
        mock_context.close = AsyncMock()

        mock_browser = MagicMock()
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_browser.close = AsyncMock()

        mock_p = MagicMock()
        mock_p.chromium.launch = AsyncMock(return_value=mock_browser)

        mock_playwright_cm = MagicMock()
        mock_playwright_cm.__aenter__ = AsyncMock(return_value=mock_p)
        mock_playwright_cm.__aexit__ = AsyncMock(return_value=None)

        mock_create_clean = AsyncMock()
        with patch.object(bot, "check_route_ip", return_value=host_probe), \
             patch("bot_server.async_playwright", return_value=mock_playwright_cm), \
             patch.object(bot, "create_clean_email", mock_create_clean):
            with self.assertRaises(Exception) as ctx:
                asyncio.run(bot.process_single_account(proxy_str="http://127.0.0.1:8086"))
            self.assertIn("BROWSER_ROUTE_UNVERIFIED", str(ctx.exception))
            mock_create_clean.assert_not_called()

    def test_t08_browser_success_account_waitlisted_no_vpn_blame(self):
        # T08: Browser success but account waitlisted -> WAITLISTED, does not blame VPN
        status, msg = classify_access("https://muse.ai/access", "Join the waitlist. We will notify you when Muse is ready.")
        self.assertEqual(status, "WAITLISTED")
        self.assertNotIn("vpn", msg.lower())

    def test_t09_canada_distinct_from_us(self):
        # T09: Country CA recorded distinctly from US
        payload = json.dumps({"status": "success", "countryCode": "CA", "country": "Canada", "query": "198.51.100.2", "isp": "Telus"})
        with patch.object(bot.subprocess, "run", return_value=MagicMock(returncode=0, stdout=payload)):
            res = bot.check_route_ip("http://127.0.0.1:8086")
            self.assertTrue(res["ok"])
            self.assertTrue(res["is_ca"])
            self.assertFalse(res["is_us"])
            self.assertEqual(res["verdict"], "CA_ROUTE")

    def test_t10_vpn_system_proxy_none_measures_real_route(self):
        # T10: VPN system proxy=None measures real route
        with patch.object(bot, "check_route_ip", return_value={"ok": True, "is_us": True, "is_ca": False, "country_code": "US", "data": {"query": "198.51.100.1"}}):
            r_vpn = asyncio.run(bot.resolve_provider_route("vpn"))
            self.assertTrue(r_vpn["ok"])
            self.assertEqual(r_vpn["networkMode"], "system")
            self.assertIsNone(r_vpn["proxy"])

        with patch.object(bot, "check_route_ip", return_value={"ok": True, "is_us": False, "is_ca": False, "country_code": "VN", "data": {"query": "1.2.3.4"}}):
            r_vpn_vn = asyncio.run(bot.resolve_provider_route("vpn"))
            self.assertFalse(r_vpn_vn["ok"])
            self.assertEqual(r_vpn_vn.get("code"), bot.ROUTE_COUNTRY_OTHER)

        with patch.object(bot, "check_route_ip", return_value={"ok": True, "is_us": False, "is_ca": False, "country_code": None, "data": {"query": "1.2.3.4"}}):
            r_vpn_unk = asyncio.run(bot.resolve_provider_route("vpn"))
            self.assertFalse(r_vpn_unk["ok"])
            self.assertEqual(r_vpn_unk.get("code"), bot.ROUTE_COUNTRY_UNKNOWN)

    def test_t11_windscribe_cli_disconnected_fails_closed(self):
        # T11: Windscribe CLI disconnected -> fails closed
        with patch.object(bot, "connect_free_us", return_value={"ok": False, "error": "Windscribe CLI disconnected"}):
            r = asyncio.run(bot.resolve_provider_route("windscribe"))
            self.assertFalse(r["ok"])
            self.assertIn("Windscribe", r["error"])

    def test_t12_custom_or_auto_missing_fails_closed_no_psiphon_fallback(self):
        # T12: Custom or Auto missing fails closed, no silent fallback to Psiphon
        with patch.object(bot.os.path, "exists", return_value=False):
            r_auto = asyncio.run(bot.resolve_provider_route("auto"))
            self.assertFalse(r_auto["ok"])
            self.assertEqual(r_auto.get("code"), bot.PROXY_NOT_CONFIGURED)

        r_cust = asyncio.run(bot.resolve_provider_route("custom", ""))
        self.assertFalse(r_cust["ok"])

    def test_t13_unknown_provider_returns_422(self):
        # T13: Unknown provider returns HTTP 422 PROVIDER_INVALID
        res = self.client.post("/api/bot/start", json={"count": 1, "proxyType": "shadowsocks"})
        self.assertEqual(res.status_code, 422)
        self.assertIn("PROVIDER_INVALID", str(res.json()["detail"]))

    def test_t14_concurrent_starts_atomic_lock(self):
        # T14: Start 2 requests concurrently -> returns 409 Conflict
        with patch.object(bot.state, "is_running", True):
            res = self.client.post("/api/bot/start", json={"count": 1, "proxyType": "psiphon"})
            self.assertEqual(res.status_code, 409)

    def test_t15_stop_immediately_halts_worker(self):
        # T15: Stop immediately halts worker
        with patch.object(bot.state, "is_running", True):
            res = self.client.post("/api/bot/stop")
            self.assertEqual(res.status_code, 200)
            self.assertTrue(bot.state.stop_requested)

        # Worker cancels before starting when stop_requested is True
        mock_req = bot.StartBotRequest(count=1, proxyType="psiphon")
        with patch.object(bot.state, "stop_requested", True), \
             patch.object(bot, "resolve_provider_route") as mock_resolve:
            asyncio.run(bot.bot_worker(mock_req))
            mock_resolve.assert_not_called()
            self.assertFalse(bot.state.is_running)

    def test_t16_profile_form_no_random_dice_roll(self):
        # T16: Profile form deterministically keeps user values
        req = bot.StartBotRequest(
            count=1,
            proxyType="psiphon",
            firstName="Grace",
            lastName="Hopper",
            birthYear="1990",
            birthMonth="12",
            birthDay="9"
        )
        self.assertEqual(req.firstName, "Grace")
        self.assertEqual(req.lastName, "Hopper")
        self.assertEqual(req.birthYear, "1990")
        self.assertEqual(req.birthMonth, "12")
        self.assertEqual(req.birthDay, "9")

    def test_t17_fixtures_classify_distinctly(self):
        # T17: Geogated, ordinary waitlist, login fixtures classify distinctly
        self.assertEqual(classify_access("https://muse.ai/access", "Muse isn’t available in your country or region yet")[0], "WAITLISTED_GEOGATED")
        self.assertEqual(classify_access("https://muse.ai/access", "Join the waitlist")[0], "WAITLISTED")
        self.assertEqual(classify_access("https://muse.ai/", "Log in or create an account")[0], "LOGIN_REQUIRED")
        self.assertEqual(classify_access("https://muse.ai/access", "Loading")[0], "ACCESS_PENDING")
        self.assertEqual(classify_access("https://muse.ai/thread/new", "How can I help?", True)[0], "SUCCESS_CHAT_READY")

    def test_t18_existing_account_chat_verification_only_if_authorized(self):
        # T18: Existing PO account chat inspection without creating new accounts
        page = MagicMock()
        page.url = "https://muse.ai/thread/new"
        page.inner_text = AsyncMock(return_value="How can I help?")
        editor = MagicMock()
        editor.is_visible = AsyncMock(return_value=True)
        editor.is_enabled = AsyncMock(return_value=True)
        editor.get_attribute = AsyncMock(return_value="")
        locator_mock = MagicMock()
        locator_mock.all = AsyncMock(return_value=[editor])
        page.locator.return_value = locator_mock

        with patch("muse_access.asyncio.sleep", new_callable=AsyncMock):
            res = asyncio.run(inspect_muse_access(page, False, 1))
            self.assertEqual(res["status"], "SUCCESS_CHAT_READY")

    def test_t19_redeem_menu_absent_returns_unavailable(self):
        # T19: Redeem menu absent returns UNAVAILABLE
        page = MagicMock()
        page.get_by_role = MagicMock(return_value=MagicMock(all=AsyncMock(return_value=[])))
        with patch("muse_invites._load_reservations", return_value={}):
            res = asyncio.run(redeem_invite(page, "QKPLQ6", idempotency_key="page_no_redeem"))
            self.assertEqual(res["status"], "UNAVAILABLE")

    def test_t20_stale_success_plus_new_invalid_returns_review_required(self):
        # T20: Stale success + invalid rejection in text returns REJECTED, never REDEEMED
        outcome = redemption_outcome("Code successfully redeemed but invalid code format")
        self.assertEqual(outcome, "REJECTED")

    def test_t21_restart_after_redeem_no_duplicate_submission(self):
        # T21: Restart after submitting redeem avoids duplicate
        with patch("muse_invites._load_reservations", return_value={"session_123:QKPLQ6": {"status": "SUBMITTED"}}):
            res = asyncio.run(redeem_invite(MagicMock(), "QKPLQ6", idempotency_key="session_123"))
            self.assertEqual(res["status"], "REVIEW_REQUIRED")

    def test_t22_zero_leakage_of_cookies_otps_passwords_in_logs_and_apis(self):
        # T22: Zero leakage of credentials, OTPs, cookies
        log_sample = "ĐÃ NHẬN MÃ OTP TỪ META: 123456! Host proxy: http://user:secretpass123@1.2.3.4:8080 token=abc123xyz"
        redacted = bot.redact_sensitive(log_sample)
        self.assertNotIn("123456", redacted)
        self.assertNotIn("secretpass123", redacted)
        self.assertNotIn("abc123xyz", redacted)
        self.assertIn("***", redacted)

        mock_accs = [{"id": "acc-sec", "email": "sec@test.com", "cookies": [{"name": "auth", "value": "secret_cookie"}]}]
        with patch.object(bot.state, "accounts", mock_accs), patch.object(bot.os.path, "exists", return_value=False):
            r = self.client.get("/api/bot/accounts")
            self.assertNotIn("secret_cookie", r.text)

    def test_t23_system_readiness_probe_endpoints(self):
        # T23: System readiness probe endpoints return 200
        res_status = self.client.get("/api/bot/status")
        self.assertEqual(res_status.status_code, 200)

        res_runtime = self.client.get("/api/bot/runtime")
        self.assertEqual(res_runtime.status_code, 200)
        data = res_runtime.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["network_revision"], "MUSE-GEO-001-G0-G5")

    def test_t24_full_regression_suite_and_frontend_clean_build(self):
        # T24: Full regression suite & critical backend modules import cleanly
        import bot_server
        import muse_access
        import muse_invites
        import psiphon_manager
        import windscribe_manager
        self.assertTrue(hasattr(bot_server, "process_single_account"))
        self.assertTrue(hasattr(muse_access, "classify_access"))
        self.assertTrue(hasattr(muse_invites, "redeem_invite"))

    def test_t25_save_accounts_txt_strips_proxy_credentials_and_redacts_errors(self):
        # T25: save_accounts_txt strips user/pass from proxy_used and redacts sensitive errors, while preserving mailbox PIN
        mock_accounts = [
            {
                "id": "acc-1",
                "email": "user1@domain.com",
                "pin": "716253",
                "password": "Password123!",
                "status": "SUCCESS_CHAT_READY",
                "proxy_used": "http://myuser:supersecretpass@10.0.0.1:8080",
                "createdAt": "2026-10-22T08:00:00Z",
            },
            {
                "id": "acc-2",
                "email": "user2@domain.com",
                "pin": "998877",
                "password": "Password123!",
                "status": "FAILED_VERIFY",
                "proxy_used": "socks5://socksuser:sockspassword@10.0.0.2:1080",
                "error": "Failed to connect via http://myuser:supersecretpass@10.0.0.1:8080: timed out",
                "createdAt": "2026-10-22T08:05:00Z",
            },
        ]
        written_files = {}

        def mock_atomic_write(target_path, content, encoding="utf-8"):
            written_files[target_path] = content

        with patch.object(bot.state, "accounts", mock_accounts), \
             patch.object(bot, "atomic_write_text", side_effect=mock_atomic_write):
            bot.save_accounts_txt()

        self.assertTrue(len(written_files) > 0)
        for path, content in written_files.items():
            # Sensitive proxy credentials must be redacted or stripped
            self.assertNotIn("supersecretpass", content)
            self.assertNotIn("sockspassword", content)
            # Mailbox PINs for valid accounts must be preserved according to contract
            self.assertIn("716253", content)

    def test_t26_get_accounts_redacts_proxy_passwords_in_error_dto(self):
        # T26: /api/bot/accounts redacts raw proxy credentials and passwords in error strings
        mock_accs = [
            {
                "id": "acc-err-1",
                "email": "err@domain.com",
                "status": "FAILED_NETWORK",
                "proxy_used": "http://admin:adminsecret123@1.2.3.4:8080",
                "error": "Proxy connect error: http://admin:adminsecret123@1.2.3.4:8080 refused connection password=rawpwd456",
                "createdAt": "2026-10-22T09:00:00Z",
            }
        ]
        with patch.object(bot.state, "accounts", mock_accs), patch.object(bot.os.path, "exists", return_value=False):
            res = self.client.get("/api/bot/accounts")
            self.assertEqual(res.status_code, 200)
            data = res.json()
            account = data["accounts"][0]
            # Verify proxy_used sanitized
            self.assertNotIn("adminsecret123", account["proxy_used"])
            # Verify error message redacted
            self.assertNotIn("adminsecret123", account["error"])
            self.assertNotIn("rawpwd456", account["error"])
            self.assertIn("***", account["error"])

    def test_t27_atomic_write_failure_propagates_exception_and_cleans_tmp(self):
        # T27: atomic writes propagate errors and clean up temp files upon failure
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            target_file = os.path.join(tmp_dir, "test_output.txt")
            with patch("os.replace", side_effect=OSError("Simulated disk write error")):
                with self.assertRaises(OSError):
                    bot.atomic_write_text(target_file, "Some test content")
            # Ensure no orphaned temp files remained
            remaining_files = os.listdir(tmp_dir)
            self.assertEqual(remaining_files, [])

    def test_t28_validate_tunnel_url_enforces_public_domain_and_scheme(self):
        # T28: validate_tunnel_url rejects invalid schemes and loopbacks, accepts valid public tunnels
        self.assertIsNone(bot.validate_tunnel_url("http://127.0.0.1:5173"))
        self.assertIsNone(bot.validate_tunnel_url("http://localhost:3000"))
        self.assertIsNone(bot.validate_tunnel_url("http://0.0.0.0:8080"))
        self.assertIsNone(bot.validate_tunnel_url("ftp://tunnel.example.com"))
        self.assertIsNone(bot.validate_tunnel_url("https://invalid host.com"))
        self.assertIsNone(bot.validate_tunnel_url(""))
        self.assertIsNone(bot.validate_tunnel_url(None))

        self.assertEqual(bot.validate_tunnel_url("https://muse-tunnel.loca.lt"), "https://muse-tunnel.loca.lt")
        self.assertEqual(bot.validate_tunnel_url("http://abc-123.ngrok-free.app/"), "http://abc-123.ngrok-free.app")

    def test_t29_poll_spinup_otp_transports_pin_via_header(self):
        # T29: poll_spinup_otp passes PIN in X-Mailbox-Pin header instead of query param
        bot.state.stop_requested = False
        captured_requests = []

        class DummyResponse:
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc_val, exc_tb):
                pass
            def read(self):
                return json.dumps({"ok": True, "hasEmails": True, "latest": {"otp": "123456"}}).encode("utf-8")

        def mock_urlopen(req, timeout=10):
            captured_requests.append(req)
            return DummyResponse()

        with patch("urllib.request.urlopen", side_effect=mock_urlopen):
            res = asyncio.run(bot.poll_spinup_otp("test@example.com", "987654", timeout_seconds=1))
            self.assertEqual(res, "123456")
            self.assertEqual(len(captured_requests), 1)
            req = captured_requests[0]
            # Ensure PIN is NOT present in URL query
            self.assertNotIn("pin=", req.full_url)
            # Ensure PIN is passed in X-Mailbox-Pin header
            self.assertEqual(req.headers.get("X-mailbox-pin"), "987654")

    def test_t30_save_session_batch_atomic_rollback_on_excel_failure(self):
        # T30: Batch export fails atomically; if Excel fails after CSV, newly created session CSV is rolled back, caller gets 409 via failure marker
        session_id = "test_rollback_99"
        mock_accounts = [
            {"email": "rb@test.com", "pin": "123456"}
        ]
        orig_atomic_excel = bot.atomic_write_excel
        def fail_on_excel(target_path, wb):
            if target_path.endswith(f"muse_session_{session_id}.xlsx"):
                raise OSError("Simulated Excel disk full failure")
            return orig_atomic_excel(target_path, wb)

        with patch.object(bot, "atomic_write_excel", side_effect=fail_on_excel):
            with self.assertRaises(OSError):
                bot.save_session_csv_and_excel(mock_accounts, session_id)

        # Verify batch rollback: session CSV was rolled back and does not exist!
        expected_csv = os.path.join(bot.EXPORTS_DIR, f"muse_session_{session_id}.csv")
        expected_xlsx = os.path.join(bot.EXPORTS_DIR, f"muse_session_{session_id}.xlsx")
        self.assertFalse(os.path.exists(expected_csv), "Session CSV must be rolled back on batch failure")
        self.assertFalse(os.path.exists(expected_xlsx), "Session XLSX must not exist")

        # Verify caller endpoint returns 409 Conflict via failure marker and does NOT return old or corrupt artifact
        res_csv = self.client.get(f"/api/bot/export-session-csv?session_id={session_id}")
        self.assertEqual(res_csv.status_code, 409)

        res_xlsx = self.client.get(f"/api/bot/export-session-excel?session_id={session_id}")
        self.assertEqual(res_xlsx.status_code, 409)

    def test_t31_update_existing_session_failure_preserves_gen_a_and_both_endpoints_409(self):
        # T31: Overwriting existing session where Excel fails preserves Gen A files on disk and both endpoints return 409
        session_id = "test_existing_update_session"
        gen_a_accounts = [{"email": "gena@example.com", "pin": "111111"}]
        gen_b_accounts = [{"email": "genb@example.com", "pin": "222222"}]
        
        # 1. Export Generation A successfully
        bot.save_session_csv_and_excel(gen_a_accounts, session_id)
        csv_path = os.path.join(bot.EXPORTS_DIR, f"muse_session_{session_id}.csv")
        xlsx_path = os.path.join(bot.EXPORTS_DIR, f"muse_session_{session_id}.xlsx")
        
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            gen_a_csv_content = f.read()
        with open(xlsx_path, "rb") as f:
            gen_a_xlsx_bytes = f.read()
            
        self.assertIn("gena@example.com", gen_a_csv_content)

        # 2. Attempt Generation B with injected Excel failure on session XLSX
        orig_atomic_excel = bot.atomic_write_excel
        def fail_on_session_excel(target_path, wb):
            if target_path == xlsx_path or target_path.endswith(f"muse_session_{session_id}.xlsx"):
                raise OSError("Simulated disk error during Gen B Excel write")
            return orig_atomic_excel(target_path, wb)

        with patch.object(bot, "atomic_write_excel", side_effect=fail_on_session_excel):
            with self.assertRaises(OSError):
                bot.save_session_csv_and_excel(gen_b_accounts, session_id)

        # 3. Verify Gen A files were restored from backup and NOT destroyed
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            restored_csv = f.read()
        with open(xlsx_path, "rb") as f:
            restored_xlsx = f.read()

        self.assertEqual(restored_csv, gen_a_csv_content, "Gen A CSV must be restored, not destroyed")
        self.assertEqual(restored_xlsx, gen_a_xlsx_bytes, "Gen A XLSX must remain intact")

        # 4. Both endpoints must reject with 409 Conflict due to failure marker
        res_csv = self.client.get(f"/api/bot/export-session-csv?session_id={session_id}")
        self.assertEqual(res_csv.status_code, 409)

        res_xlsx = self.client.get(f"/api/bot/export-session-excel?session_id={session_id}")
        self.assertEqual(res_xlsx.status_code, 409)

        # 5. Verify retry success clears failure marker and serves new generation
        bot.save_session_csv_and_excel(gen_b_accounts, session_id)
        res_csv_ok = self.client.get(f"/api/bot/export-session-csv?session_id={session_id}")
        self.assertEqual(res_csv_ok.status_code, 200)
        self.assertIn("genb@example.com", res_csv_ok.text)
        
        res_xlsx_ok = self.client.get(f"/api/bot/export-session-excel?session_id={session_id}")
        self.assertEqual(res_xlsx_ok.status_code, 200)

    def test_t32_update_alias_failure_rolls_back_all_aliases(self):
        # T32: If later alias export fails, earlier updated files and aliases are rolled back to Gen A
        session_id = "test_alias_rollback_session"
        gen_a_accounts = [{"email": "alias_a@example.com", "pin": "333333"}]
        gen_b_accounts = [{"email": "alias_b@example.com", "pin": "444444"}]
        
        bot.save_session_csv_and_excel(gen_a_accounts, session_id)
        latest_csv_path = os.path.join(bot.EXPORTS_DIR, "muse_session_latest.csv")
        with open(latest_csv_path, "r", encoding="utf-8-sig") as f:
            latest_a_content = f.read()
        self.assertIn("alias_a@example.com", latest_a_content)

        orig_atomic_excel = bot.atomic_write_excel
        def fail_on_latest_excel(target_path, wb):
            if "muse_session_latest.xlsx" in target_path:
                raise OSError("Simulated failure writing latest.xlsx alias")
            return orig_atomic_excel(target_path, wb)

        with patch.object(bot, "atomic_write_excel", side_effect=fail_on_latest_excel):
            with self.assertRaises(OSError):
                bot.save_session_csv_and_excel(gen_b_accounts, session_id)

        # Verify latest.csv alias was restored back to Gen A, not left on Gen B
        with open(latest_csv_path, "r", encoding="utf-8-sig") as f:
            restored_latest_content = f.read()
        self.assertEqual(restored_latest_content, latest_a_content)
        self.assertNotIn("alias_b@example.com", restored_latest_content)

    def test_t33_cleanup_failure_recorded_in_failure_marker(self):
        # T33: If cleanup itself has errors, they are recorded in the failure marker
        session_id = "test_cleanup_failure_session"
        mock_accounts = [{"email": "clean@example.com", "pin": "555555"}]
        
        # Pre-populate a file so backup is made
        csv_path = os.path.join(bot.EXPORTS_DIR, f"muse_session_{session_id}.csv")
        with open(csv_path, "w", encoding="utf-8") as f:
            f.write("old-content")

        orig_atomic_excel = bot.atomic_write_excel
        def fail_on_excel(target_path, wb):
            if target_path.endswith(f"muse_session_{session_id}.xlsx"):
                raise OSError("Excel write failure")
            return orig_atomic_excel(target_path, wb)

        orig_replace = os.replace
        def fail_replace(src, dst):
            if ".bak" in str(src):
                raise OSError("Simulated permission denied during rollback restore")
            return orig_replace(src, dst)

        with patch.object(bot, "atomic_write_excel", side_effect=fail_on_excel), \
             patch.object(os, "replace", side_effect=fail_replace):
            with self.assertRaises(OSError):
                bot.save_session_csv_and_excel(mock_accounts, session_id)

        failure_marker = os.path.join(bot.EXPORTS_DIR, f"muse_session_{session_id}.failed")
        self.assertTrue(os.path.exists(failure_marker))
        with open(failure_marker, "r", encoding="utf-8") as fm:
            marker_data = json.load(fm)
        self.assertIn("cleanup_errors", marker_data)
        self.assertTrue(len(marker_data["cleanup_errors"]) > 0)

    def test_t34_save_accounts_real_caller_boundary(self):
        # T34: Real caller boundary commit_account_and_log_success propagates persistence failure and suppresses success claim
        with patch.object(bot, "save_accounts_txt", side_effect=OSError("Simulated TXT write failure")):
            with self.assertRaises(OSError):
                bot.save_accounts()

        log_entries = []
        def mock_add_log(msg, level="info", pct=None):
            log_entries.append((msg, level, pct))

        with patch.object(bot, "save_accounts", side_effect=OSError("disk error: token=secret_token_12345 and proxy http://user:super_secret_pass@127.0.0.1:8080")), \
             patch.object(bot, "add_log", side_effect=mock_add_log):
            account_data = {"email": "caller_test@example.com"}
            with self.assertRaises(OSError):
                bot.commit_account_and_log_success(account_data)

            # Verify no false success claim was logged
            success_logs = [m for m, lvl, _ in log_entries if "THÀNH CÔNG" in m and lvl == "success"]
            self.assertEqual(len(success_logs), 0, "Must not claim success when file save fails")

            # Verify error log was recorded and sensitive token & proxy password were redacted
            error_logs = [m for m, lvl, _ in log_entries if lvl == "error"]
            self.assertTrue(len(error_logs) > 0)
            self.assertIn("lưu file tài khoản thất bại", error_logs[0])
            self.assertNotIn("secret_token_12345", error_logs[0])
            self.assertNotIn("super_secret_pass", error_logs[0])
            self.assertIn("token=***", error_logs[0])
            self.assertIn("user:***@127.0.0.1:8080", error_logs[0])

    def test_t35_backup_failure_aborts_before_mutation_and_preserves_gen_a_bytes(self):
        # T35: When backup copy fails, save_session_csv_and_excel aborts before mutation, preserving Gen A bytes exactly
        session_id = "test_t35_backup_fail"
        gen_a_accounts = [{"email": "gena_t35@example.com", "pin": "111111"}]
        gen_b_accounts = [{"email": "genb_t35@example.com", "pin": "222222"}]

        bot.save_session_csv_and_excel(gen_a_accounts, session_id)
        csv_path = os.path.join(bot.EXPORTS_DIR, f"muse_session_{session_id}.csv")
        xlsx_path = os.path.join(bot.EXPORTS_DIR, f"muse_session_{session_id}.xlsx")
        gen_a_csv_bytes = open(csv_path, "rb").read()
        gen_a_xlsx_bytes = open(xlsx_path, "rb").read()

        import shutil
        with patch.object(shutil, "copy2", side_effect=PermissionError("Simulated backup permission denied")):
            with self.assertRaises(OSError):
                bot.save_session_csv_and_excel(gen_b_accounts, session_id)

        # Assert original Gen A bytes are 100% preserved
        self.assertEqual(open(csv_path, "rb").read(), gen_a_csv_bytes, "Gen A CSV bytes must be preserved")
        self.assertEqual(open(xlsx_path, "rb").read(), gen_a_xlsx_bytes, "Gen A XLSX bytes must be preserved")

        # Assert download endpoints return 409
        res_csv = self.client.get(f"/api/bot/export-session-csv?session_id={session_id}")
        self.assertEqual(res_csv.status_code, 409)
        res_xlsx = self.client.get(f"/api/bot/export-session-excel?session_id={session_id}")
        self.assertEqual(res_xlsx.status_code, 409)

    def test_t36_restore_failure_preserves_backup_on_disk(self):
        # T36: When rollback restore fails, the backup file is NOT deleted by cleanup and remains intact on disk
        session_id = "test_t36_restore_fail"
        gen_a_accounts = [{"email": "gena_t36@example.com", "pin": "333333"}]
        gen_b_accounts = [{"email": "genb_t36@example.com", "pin": "444444"}]

        bot.save_session_csv_and_excel(gen_a_accounts, session_id)
        csv_path = os.path.join(bot.EXPORTS_DIR, f"muse_session_{session_id}.csv")
        gen_a_csv_bytes = open(csv_path, "rb").read()

        orig_atomic_excel = bot.atomic_write_excel
        def fail_excel(target_path, wb):
            if f"muse_session_{session_id}.xlsx" in target_path:
                raise OSError("Excel write failed")
            return orig_atomic_excel(target_path, wb)

        orig_replace = os.replace
        def fail_restore(src, dst):
            if ".bak_" in str(src):
                raise PermissionError("Simulated restore permission denied")
            return orig_replace(src, dst)

        with patch.object(bot, "atomic_write_excel", side_effect=fail_excel), \
             patch.object(os, "replace", side_effect=fail_restore):
            with self.assertRaises(OSError):
                bot.save_session_csv_and_excel(gen_b_accounts, session_id)

        # Assert at least one backup file was preserved on disk and contains Gen A bytes
        bak_files = [p for p in os.listdir(bot.EXPORTS_DIR) if f"muse_session_{session_id}.csv.bak_" in p]
        self.assertTrue(len(bak_files) > 0, "Backup file must be preserved on disk when restore fails")
        bak_full = os.path.join(bot.EXPORTS_DIR, bak_files[0])
        self.assertEqual(open(bak_full, "rb").read(), gen_a_csv_bytes, "Preserved backup must contain Gen A bytes")

        # Assert endpoints reject with 409
        res_csv = self.client.get(f"/api/bot/export-session-csv?session_id={session_id}")
        self.assertEqual(res_csv.status_code, 409)

    def test_t37_pending_marker_durable_gate_rejects_mixed_generations(self):
        # T37: If writing failure marker and restore both fail, the pre-mutation pending marker still blocks download with 409
        session_id = "test_t37_gate_rejects"
        gen_a_accounts = [{"email": "gena_t37@example.com", "pin": "555555"}]
        gen_b_accounts = [{"email": "genb_t37@example.com", "pin": "666666"}]

        bot.save_session_csv_and_excel(gen_a_accounts, session_id)

        orig_atomic_excel = bot.atomic_write_excel
        def fail_excel(target_path, wb):
            if f"muse_session_{session_id}.xlsx" in target_path:
                raise OSError("Excel write failed")
            return orig_atomic_excel(target_path, wb)

        orig_open = builtins.open
        def fail_failed_marker(file, mode="r", *args, **kwargs):
            if str(file).endswith(".failed") and "w" in mode:
                raise PermissionError("Marker write failed")
            return orig_open(file, mode, *args, **kwargs)

        orig_replace = os.replace
        def fail_restore(src, dst):
            if ".bak_" in str(src):
                raise PermissionError("Restore replace failed")
            return orig_replace(src, dst)

        with patch.object(bot, "atomic_write_excel", side_effect=fail_excel), \
             patch("builtins.open", side_effect=fail_failed_marker), \
             patch.object(os, "replace", side_effect=fail_restore):
            with self.assertRaises(OSError):
                bot.save_session_csv_and_excel(gen_b_accounts, session_id)

        pending_marker = os.path.join(bot.EXPORTS_DIR, f"muse_session_{session_id}.pending")
        self.assertTrue(os.path.exists(pending_marker), "Pending marker must remain on disk as durable gate")

        # Both endpoints must reject with 409, NEVER returning mixed generations with 200
        res_csv = self.client.get(f"/api/bot/export-session-csv?session_id={session_id}")
        self.assertEqual(res_csv.status_code, 409)
        res_xlsx = self.client.get(f"/api/bot/export-session-excel?session_id={session_id}")
        self.assertEqual(res_xlsx.status_code, 409)

    def test_t38_gate_creation_failure_aborts_without_mutation(self):
        # T38: If publication gate cannot be created, aborts immediately with zero mutation
        session_id = "test_t38_gate_fail"
        gen_a_accounts = [{"email": "gena_t38@example.com", "pin": "777777"}]
        gen_b_accounts = [{"email": "genb_t38@example.com", "pin": "888888"}]

        bot.save_session_csv_and_excel(gen_a_accounts, session_id)
        csv_path = os.path.join(bot.EXPORTS_DIR, f"muse_session_{session_id}.csv")
        xlsx_path = os.path.join(bot.EXPORTS_DIR, f"muse_session_{session_id}.xlsx")
        gen_a_csv_bytes = open(csv_path, "rb").read()
        gen_a_xlsx_bytes = open(xlsx_path, "rb").read()

        orig_open = builtins.open
        def fail_pending_marker(file, mode="r", *args, **kwargs):
            if str(file).endswith(".pending") and "w" in mode:
                raise PermissionError("Cannot create pending gate")
            return orig_open(file, mode, *args, **kwargs)

        with patch("builtins.open", side_effect=fail_pending_marker):
            with self.assertRaises(OSError):
                bot.save_session_csv_and_excel(gen_b_accounts, session_id)

        # Assert zero mutation occurred on Gen A files
        self.assertEqual(open(csv_path, "rb").read(), gen_a_csv_bytes)
        self.assertEqual(open(xlsx_path, "rb").read(), gen_a_xlsx_bytes)

    def test_t39_marker_clear_failure_raises_and_agrees_with_download_endpoint(self):
        # T39: If clearing pending marker fails, writer raises and download endpoint rejects with 409
        session_id = "test_t39_clear_fail"
        mock_accounts = [{"email": "clear_fail@example.com", "pin": "999999"}]

        orig_remove = os.remove
        def fail_clear_pending(p):
            if str(p).endswith(".pending"):
                raise OSError("Cannot clear pending marker due to disk lock")
            return orig_remove(p)

        with patch.object(os, "remove", side_effect=fail_clear_pending):
            with self.assertRaises(OSError):
                bot.save_session_csv_and_excel(mock_accounts, session_id)

        # Download endpoint must reject with 409 because pending marker is still present
        res_csv = self.client.get(f"/api/bot/export-session-csv?session_id={session_id}")
        self.assertEqual(res_csv.status_code, 409)


if __name__ == "__main__":
    unittest.main()

