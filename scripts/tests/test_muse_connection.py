import sys, unittest, json, io
from unittest.mock import patch, AsyncMock, MagicMock
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
import bot_server as bot
import psiphon_manager as manager

class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.client=TestClient(bot.app, base_url='http://127.0.0.1:8790')
    def test_external_origin_cannot_read_bot_sessions(self):
        self.assertEqual(self.client.get('/api/bot/accounts', headers={'Origin':'https://external.example'}).status_code,403)
    def test_local_origin_can_use_tool(self):
        self.assertEqual(self.client.get('/api/bot/status', headers={'Origin':'http://127.0.0.1:5173'}).status_code,200)
    def test_no_browser_when_tunnel_fails(self):
        with patch.object(bot,'start_psiphon_tunnel',return_value={'ok':False,'error':'Unavailable'}), patch.object(bot,'open_muse_browser',new_callable=AsyncMock) as browser:
            r=self.client.post('/api/bot/open-muse')
            self.assertEqual(r.status_code,503)
            browser.assert_not_awaited()
    def test_no_browser_when_country_unverified(self):
        with patch.object(bot,'start_psiphon_tunnel',return_value={'ok':True,'is_us':False}), patch.object(bot,'open_muse_browser',new_callable=AsyncMock) as browser:
            self.assertEqual(self.client.post('/api/bot/open-muse').status_code,503)
            browser.assert_not_awaited()
    def test_one_click_passes_verified_proxy(self):
        with patch.object(bot,'start_psiphon_tunnel',return_value={'ok':True,'is_us':True,'proxy':'http://127.0.0.1:8085'}), patch.object(bot,'open_muse_browser',new_callable=AsyncMock,return_value='https://muse.ai/') as browser:
            self.assertEqual(self.client.post('/api/bot/open-muse').status_code,200)
            browser.assert_awaited_once_with({'server':'http://127.0.0.1:8085'})
    def test_session_reconnects_and_restores_cookies(self):
        acc={'id':'test-session','proxy_used':'http://127.0.0.1:8085','cookies':[]}
        with patch.object(bot.state,'accounts',[acc]), patch.object(bot,'start_psiphon_tunnel',return_value={'ok':True,'is_us':True,'proxy':'http://127.0.0.1:8085'}) as tunnel, patch.object(bot,'open_muse_browser',new_callable=AsyncMock,return_value='https://muse.ai/') as browser:
            self.assertEqual(self.client.post('/api/bot/open-session/test-session').status_code,200)
            tunnel.assert_called_once()
            browser.assert_awaited_once_with({'server':'http://127.0.0.1:8085'},[])
    def test_no_proxy_sentinel(self):
        with patch.object(bot.state,'accounts',[{'id':'test-direct','proxy_used':'Không dùng'}]), patch.object(bot,'open_muse_browser',new_callable=AsyncMock,return_value='https://muse.ai/') as browser:
            self.assertEqual(self.client.post('/api/bot/open-session/test-direct').status_code,200)
            browser.assert_awaited_once_with(None,[])
    def test_browser_error_reported(self):
        with patch.object(bot,'start_psiphon_tunnel',return_value={'ok':True,'is_us':True,'proxy':'http://127.0.0.1:8085'}), patch.object(bot,'open_muse_browser',new_callable=AsyncMock,side_effect=RuntimeError('test')):
            self.assertEqual(self.client.post('/api/bot/open-muse').status_code,502)
    def test_wrong_country_is_not_healthy(self):
        response=MagicMock(returncode=0,stdout=json.dumps({'success':True,'country_code':'VN'}))
        with patch.object(manager.subprocess,'run',return_value=response):
            self.assertIsNone(manager.is_psiphon_alive())
    def test_silent_tunnel_times_out(self):
        config=MagicMock(); config.is_file.return_value=True
        config.read_text.return_value='{}'; config.__truediv__.return_value=config
        process=MagicMock(); process.poll.return_value=None; process.stdout=io.StringIO('')
        probe=MagicMock(); probe.__enter__.return_value=probe; probe.connect_ex.return_value=1
        with patch.object(manager,'is_psiphon_alive',return_value=None), patch.object(manager,'CORE_EXE',config), patch.object(manager,'SOURCE_DIR',config), patch.object(manager,'RUNTIME_DIR',config), patch.object(manager.socket,'socket',return_value=probe), patch.object(manager.subprocess,'Popen',return_value=process):
            result=manager.start_psiphon_tunnel(timeout=0.05)
            self.assertFalse(result['ok'])
            process.terminate.assert_called_once()

if __name__ == "__main__":
    unittest.main()
