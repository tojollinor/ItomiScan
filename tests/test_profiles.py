"""SQLite scan-profile roundtrip and safe migration, headless."""
import json
import os
import tempfile
import unittest
from pathlib import Path

from itomiscan.core.profiles import ProfileError, ProfileStore, validate_profile
from itomiscan.storage.config import ConfigStore, ConfigError, validate_target


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.path = Path(self.dir.name) / "config" / "itomiscan.db"

    def test_defaults_and_selection_across_processes(self):
        one = ProfileStore(self.path)
        self.assertEqual(one.selected, "Dokument")
        self.assertIn("Foto", one.names())
        one.select("Foto")
        self.assertEqual(ProfileStore(self.path).current()["output"], "Bild (PNG)")

    def test_profile_save_and_options(self):
        store = ProfileStore(self.path)
        record = store.current()
        record.update(name="Rechnungen", mode="Gray", resolution=300,
                      settings={"--brightness":"15","--mode":"Gray"})
        store.save(record)
        other = ProfileStore(self.path)
        self.assertEqual(other.current()["name"], "Rechnungen")
        self.assertEqual(other.current()["settings"]["--brightness"], "15")
        self.assertEqual(len(other.names()), 5)

    def test_unsafe_profile_inputs(self):
        item = ProfileStore(self.path).current()
        for key, val in (("resolution", -1), ("name", "a/b")):
            broken = dict(item, **{key: val})
            with self.assertRaises(ProfileError):
                validate_profile(broken)
        with self.assertRaises(ProfileError):
            validate_profile(dict(item, settings={"--mode;rm": "Color"}))

    def test_legacy_json_migrated_and_retained(self):
        old = self.path.parent / "profiles.json"
        old.parent.mkdir(parents=True)
        payload = {"version":1, "selected":"Foto", "profiles": [
            {**item, "settings":{}} for item in ProfileStore(
                Path(self.dir.name) / "elsewhere.db").profiles]}
        old.write_text(json.dumps(payload), encoding="utf-8")
        prior = old.read_bytes()
        store = ProfileStore(self.path)
        self.assertEqual(store.selected, "Foto")
        self.assertEqual(old.read_bytes(), prior)
        self.assertEqual(store.db.list_profiles()[1], "Foto")

    def test_corrupt_legacy_file_preserved(self):
        old = self.path.parent / "profiles.json"
        old.parent.mkdir(parents=True)
        old.write_text("{bad-json", encoding="utf-8")
        store = ProfileStore(self.path)
        self.assertTrue(store.warning)
        with self.assertRaises(ProfileError):
            store.select("Foto")
        self.assertEqual(old.read_text(), "{bad-json")

    def test_private_sqlite_file_and_configuration(self):
        db = ConfigStore(self.path)
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.path.parent.stat().st_mode & 0o777, 0o700)
        db.set_settings({"screensaver_minutes":10,"device_label":"Archiv"})
        self.assertEqual(db.get_settings()["screensaver_minutes"],10)
        with self.assertRaises(ConfigError):
            db.set_settings({"screensaver_minutes":0})

    def test_targets_validation_and_backup_restore(self):
        db = ConfigStore(self.path)
        db.save_target({"kind":"paperless","name":"DMS","address":"https://paperless.local"})
        db.save_target({"kind":"printer","name":"Laser","address":"ipp://10.1.2.3/ipp/print"})
        backup = db.backup()
        db.save_target({"kind":"network","name":"NAS","address":"smb://nas/share"})
        db.restore(backup)
        self.assertEqual(len(db.list_targets()),2)
        self.assertEqual(len(db.list_profiles()[0]),4)
        for invalid in ("http://user:pass@host/", "javascript://server"):
            with self.assertRaises(ConfigError):
                validate_target({"kind":"paperless","name":"X","address":invalid})

    def test_failed_restore_is_atomic_and_no_credentials(self):
        db = ConfigStore(self.path)
        db.set_password("SecureExamplePassphrase43")
        exported = db.backup()
        self.assertNotIn("SecureExamplePassphrase43", json.dumps(exported))
        original = db.list_profiles()[0]
        broken = dict(exported, profiles=[dict(original[0], resolution=9999)])
        with self.assertRaises((ConfigError, ProfileError)):
            db.restore(broken)
        self.assertEqual(db.list_profiles()[0], original)
        self.assertTrue(db.verify_password("SecureExamplePassphrase43"))
        self.assertFalse(db.verify_password("bad"))

if __name__ == "__main__":
    unittest.main()
