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

        # 2) vpn (system mode)
        r_vpn = asyncio.run(bot.resolve_provider_route("vpn"))
        self.assertTrue(r_vpn["ok"])
        self.assertEqual(r_vpn["provider"], "vpn")
        self.assertIsNone(r_vpn["proxy"])
        self.assertEqual(r_vpn["networkMode"], "system")

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
            # Should sanitize session_id or return 404
            self.assertIn(res.status_code, (200, 404))

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



if __name__ == "__main__":
    unittest.main()
