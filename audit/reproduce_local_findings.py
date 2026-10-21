"""Offline audit probes. Synthetic data only; no browser or provider requests.

Run from repository root: python audit/reproduce_local_findings.py
These probes document current defects, rather than asserting desired behavior.
"""
import asyncio
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import bot_server as bot


async def main():
    with tempfile.TemporaryDirectory(prefix="spinupmail-audit-") as temp:
        latest = Path(temp) / "muse_session_latest.csv"
        latest.write_text("old-session-synthetic-data", encoding="utf-8")
        with patch.object(bot, "EXPORTS_DIR", temp), patch.object(bot.state, "session_id", "new-empty-session"):
            try:
                response = await bot.export_session_csv()
                print(json.dumps({"finding": "EXPORT_CROSS_SESSION", "requested": "new-empty-session", "returned": Path(response.path).name, "confirmed": Path(response.path) == latest, "resolved": False}))
            except bot.HTTPException as e:
                print(json.dumps({"finding": "EXPORT_CROSS_SESSION", "requested": "new-empty-session", "status_code": e.status_code, "confirmed": False, "resolved": e.status_code == 404}))

    fake = {"id": "synthetic", "email": "example@example.invalid", "pin": "222222", "otp": "111111"}
    with patch.object(bot.state, "session_accounts", [fake]), patch.object(bot, "get_public_tunnel_url", return_value="https://example.invalid"):
        result = await bot.get_session_info()
        print(json.dumps({"finding": "OTP_USED_AS_MAILBOX_PIN", "confirmed": result["accounts"][0]["pin"] == fake["otp"], "pin_is_real_pin": result["accounts"][0]["pin"] == fake["pin"], "resolved": result["accounts"][0]["pin"] == fake["pin"]}))

    fake["cookies"] = [{"name": "dummy", "value": "dummy-cookie"}]
    fake["route_spec"] = {"proxy_config": {"password": "synthetic-secret"}}
    fake["proxy_used"] = "http://dummy:synthetic-secret@127.0.0.1:9999"
    with patch.object(bot.state, "accounts", [fake]), patch.object(bot.os.path, "exists", return_value=False):
        result = await bot.get_accounts()
        serialized = json.dumps(result)
        print(json.dumps({"finding": "ACCOUNT_DTO_CREDENTIAL_LEAK", "cookies_removed": "dummy-cookie" not in serialized, "proxy_secret_still_present": "synthetic-secret" in serialized, "resolved": ("dummy-cookie" not in serialized and "synthetic-secret" not in serialized)}))


if __name__ == "__main__":
    asyncio.run(main())
