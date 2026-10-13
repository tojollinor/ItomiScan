"""Persisted PIN auth, user permissions, timeouts and recovery, no GUI."""
import json
import tempfile
import unittest
from pathlib import Path

from itomiscan.storage.config import ConfigStore
from itomiscan.storage.users import PinError, UserStore


class FakeClock:
    def __init__(self):
        self.now = 10000

    def __call__(self):
        return self.now


class UserSecurityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "itomiscan.db"
        self.clock = FakeClock()
        self.users = UserStore(self.path, clock=self.clock)

    def make_user(self, name="Anna", pin="123456", allowed=None, profiles=None,
                  default="Dokument"):
        return self.users.save_user(
            name=name, pin=pin, permissions=allowed if allowed is not None else ["scan"],
            assigned_profiles=profiles if profiles is not None else ["Dokument"],
            default_profile=default, active=True)

    def test_disabled_by_default_and_cannot_enable_without_account(self):
        self.assertFalse(self.users.settings()["enabled"])
        self.assertTrue(self.users.authorized(None, "scan"))
        with self.assertRaises(PinError):
            self.users.configure(enabled=True)

    def test_unique_pins_and_secret_not_rendered_or_backed_up(self):
        uid = self.make_user()
        with self.assertRaisesRegex(PinError, "bereits"):
            self.make_user("Berta", "123456")
        other = self.make_user("Berta", "9876", allowed=["paperless","copy"],
                               profiles=["Foto"], default="Foto")
        self.users.configure(enabled=True)
        self.assertEqual(self.users.verify_pin("123456")["id"], uid)
        self.assertEqual(self.users.verify_pin("9876")["id"], other)
        self.assertTrue(self.users.authorized(uid, "scan"))
        self.assertFalse(self.users.authorized(uid, "copy"))
        self.assertTrue(self.users.authorized(other, "copy"))
        self.assertFalse(self.users.authorized(None, "scan"))
        self.assertNotIn("123456", json.dumps(self.users.list_users()))
        backup = json.dumps(ConfigStore(self.path).backup())
        self.assertNotIn("pin_users", backup)
        self.assertNotIn("salt", backup)
        self.assertNotIn("123456", backup)

    def test_lockout_persists_across_instance_restart(self):
        self.make_user()
        self.users.configure(enabled=True, timeout_minutes=2)
        for _ in range(5):
            self.assertIsNone(self.users.verify_pin("9999"))
        self.assertGreater(self.users.settings()["locked_seconds"], 0)
        reopened = UserStore(self.path, clock=self.clock)
        self.assertIsNone(reopened.verify_pin("123456"))
        self.clock.now += 181
        self.assertEqual(reopened.verify_pin("123456")["name"], "Anna")
        self.assertEqual(reopened.settings()["locked_seconds"], 0)

    def test_can_not_delete_or_disable_last_active_user(self):
        uid = self.make_user()
        self.users.configure(enabled=True)
        with self.assertRaises(PinError):
            self.users.delete_user(uid)
        with self.assertRaises(PinError):
            self.users.save_user(user_id=uid, name="Anna", pin=None,
                                 permissions=["scan"],
                                 assigned_profiles=["Dokument"],
                                 default_profile="Dokument", active=False)
        self.users.configure(enabled=False)
        self.users.delete_user(uid)
        self.assertEqual(self.users.list_users(), [])
        self.assertTrue(self.users.authorized(None, "copy"))

    def test_account_modifications_revoke_permissions(self):
        uid = self.make_user(allowed=["scan","copy"],
                             profiles=["Dokument","Foto"])
        self.users.configure(enabled=True)
        self.assertTrue(self.users.authorized(uid, "copy"))
        self.users.save_user(user_id=uid, name="Anna", pin=None,
                             permissions=["scan"], assigned_profiles=["Foto"],
                             default_profile="Foto", active=True)
        self.assertFalse(self.users.authorized(uid, "copy"))
        self.assertEqual(self.users.get_user(uid)["default_profile"], "Foto")

    def test_profile_assignment_rejects_unknown_and_duplicates(self):
        with self.assertRaises(PinError):
            self.make_user(profiles=["DoesNotExist"])
        with self.assertRaises(PinError):
            self.make_user(profiles=["Dokument","Dokument"])
        with self.assertRaises(PinError):
            self.make_user(profiles=["Foto"], default="Dokument")
        with self.assertRaises(PinError):
            self.users.configure(timeout_minutes=0)

    def test_bad_pin_format_rejected(self):
        for pin in ("123", "1234567", "123a", "１２３４"):
            with self.subTest(pin=pin), self.assertRaises(PinError):
                self.make_user(pin=pin)

    def test_preserves_user_hashes_across_regular_config_restore(self):
        uid = self.make_user()
        self.users.configure(enabled=True)
        backup = ConfigStore(self.path).backup()
        ConfigStore(self.path).restore(backup)
        self.assertTrue(self.users.authorized(uid, "scan"))
        self.assertEqual(self.users.verify_pin("123456")["id"], uid)


if __name__ == "__main__":
    unittest.main()
