import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from muse_invites import normalize_invite_code, redemption_outcome

class InvitationTests(unittest.TestCase):
    def test_user_code_is_preserved(self):
        self.assertEqual(normalize_invite_code("QKPLQ6"), "QKPLQ6")
    def test_full_link_is_normalized(self):
        self.assertEqual(normalize_invite_code("https://muse.ai/invite/QKPLQ6"), "QKPLQ6")
    def test_foreign_link_is_rejected(self):
        with self.assertRaises(ValueError):normalize_invite_code("https://example.com/invite/QKPLQ6")
    def test_invalid_input_does_not_silently_use_default(self):
        with self.assertRaises(ValueError):normalize_invite_code("join")
    def test_empty_code_is_not_requested(self):
        self.assertIsNone(normalize_invite_code(""))
    def test_opened_invite_is_not_redeemed(self):
        self.assertEqual(redemption_outcome("Invite friends. Redeem code in settings."),"UNVERIFIED")
    def test_failure_is_not_redeemed(self):
        self.assertEqual(redemption_outcome("Invalid invite code"),"REJECTED")
    def test_success_requires_confirmation(self):
        self.assertEqual(redemption_outcome("Invite code redeemed successfully"),"REDEEMED")
    def test_vietnamese_confirmation(self):
        self.assertEqual(redemption_outcome("Mã mời đã được quy đổi thành công"),"REDEEMED")

if __name__=="__main__":unittest.main()
