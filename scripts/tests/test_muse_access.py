import sys
import asyncio
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from muse_access import classify_access, inspect_muse_access, MuseAccessError
import bot_server as bot

class AccessTests(unittest.TestCase):
    def test_account_chooser_is_not_country_block(self):
        self.assertEqual(classify_access("https://muse.ai/", "Log in or create an account Meta Account Use another account")[0], "LOGIN_REQUIRED")
    def test_explicit_country_message(self):
        self.assertEqual(classify_access("https://muse.ai/access", "Muse isn’t available in your country or region yet")[0], "WAITLISTED_GEOGATED")
    def test_waitlist_does_not_prove_country_block(self):
        self.assertEqual(classify_access("https://muse.ai/access", "Join the waitlist")[0], "WAITLISTED")
    def test_access_route_alone_is_not_country_block(self):
        self.assertEqual(classify_access("https://muse.ai/access", "Loading")[0], "ACCESS_PENDING")
    def test_missing_chat_is_unverified(self):
        self.assertEqual(classify_access("https://muse.ai/", "Loading")[0], "ACCESS_UNVERIFIED")
    def test_visible_chat(self):
        self.assertEqual(classify_access("https://muse.ai/thread/new", "How can I help?", True)[0], "SUCCESS_CHAT_READY")
    def test_account_chooser_is_continued_once(self):
        page=MagicMock(); page.url="https://muse.ai/"
        page.inner_text=AsyncMock(side_effect=["Log in or create an account Meta Account Use another account", "How can I help?"])
        editor=MagicMock(); editor.is_visible=AsyncMock(return_value=True); editor.is_enabled=AsyncMock(return_value=True)
        page.locator.return_value.all=AsyncMock(side_effect=[[],[editor]])
        tile=page.get_by_text.return_value
        tile.count=AsyncMock(return_value=1); tile.is_visible=AsyncMock(return_value=True); tile.click=AsyncMock()
        with patch("muse_access.asyncio.sleep",new_callable=AsyncMock):
            result=asyncio.run(inspect_muse_access(page,True,2))
        self.assertEqual(result["status"],"SUCCESS_CHAT_READY")
        tile.click.assert_awaited_once()
    def test_batch_stops_on_access_failure_and_zero_is_error(self):
        request=bot.StartBotRequest(count=3,proxyType="vpn")
        with patch.object(bot,"resolve_provider_route",return_value={"ok": True, "provider": "vpn", "proxy": None, "networkMode": "system"}), patch.object(bot,"process_single_account",new_callable=AsyncMock,side_effect=MuseAccessError("LOGIN_REQUIRED","Login incomplete")) as register, patch.object(bot,"add_log") as log, patch.object(bot,"save_session_csv_and_excel"):
            asyncio.run(bot.bot_worker(request))
            register.assert_awaited_once()
            self.assertEqual(log.call_args.args[1],"error")

if __name__=="__main__":unittest.main()
