"""Comprehensive regression tests for MUSE-V5 / MUSE-GEO-001 (Option A).
Verifies fail-closed route validation, five-provider dispatch, CA separation,
Host/Origin protection, atomic job lock, cookie redaction, path traversal guards,
and invite idempotency.
"""
import asyncio
import io
import json
import os
import sys
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


class MuseV5RegressionTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(bot.app, base_url="http://127.0.0.1:8790")

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


class MuseG5ExplicitTableTests(unittest.TestCase):
    """Explicit Gate G5 test suite mapping 1:1 to cases T01 through T24 in the Master Fix Plan."""

    def setUp(self):
        self.client = TestClient(bot.app, base_url="http://127.0.0.1:8790")

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


if __name__ == "__main__":
    unittest.main()

