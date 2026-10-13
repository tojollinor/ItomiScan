"""Scan profile persistence and validation; headless tests."""
import json
import tempfile
import unittest
from pathlib import Path

from itomiscan.core.profiles import ProfileError, ProfileStore, validate_profile


class ScanProfilesTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.path = Path(self.dir.name) / "config" / "profiles.json"

    def test_defaults_without_existing_file(self):
        store = ProfileStore(self.path)
        self.assertEqual(store.selected, "Dokument")
        self.assertIn("Foto", store.names())
        self.assertFalse(self.path.exists())

    def test_selection_survives_restart(self):
        store = ProfileStore(self.path)
        store.select("Foto")
        self.assertEqual(ProfileStore(self.path).current()["output"], "Bild (PNG)")

    def test_new_profile_survives_restart(self):
        store = ProfileStore(self.path)
        new = store.current()
        new.update(name="Rechnungen", mode="Gray", resolution=300)
        store.save(new)
        self.assertEqual(ProfileStore(self.path).current()["name"], "Rechnungen")
        self.assertEqual(len(ProfileStore(self.path).names()), 4)

    def test_bad_profile_rejected(self):
        store = ProfileStore(self.path)
        wrong = store.current()
        wrong["resolution"] = -1
        with self.assertRaises(ProfileError):
            store.save(wrong)
        with self.assertRaises(ProfileError):
            validate_profile({**store.current(), "name": "a/b"})

    def test_corrupt_data_preserved(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text("{not-json", encoding="utf-8")
        store = ProfileStore(self.path)
        self.assertTrue(store.warning)
        with self.assertRaises(ProfileError):
            store.select("Foto")
        self.assertEqual(self.path.read_text(), "{not-json")

    def test_permissions_and_atomic_json(self):
        store = ProfileStore(self.path)
        store.select("Text")
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(json.loads(self.path.read_text())["selected"], "Text")


if __name__ == "__main__":
    unittest.main()
