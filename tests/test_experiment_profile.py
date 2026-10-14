"""Regression checks for the opt-in all-options scan preset."""
import tempfile
import unittest
from pathlib import Path

from itomiscan.core.profiles import DEFAULT_PROFILES, validate_profile
from itomiscan.storage.config import ConfigStore


class ExperimentProfileTests(unittest.TestCase):
    def test_default_is_valid_and_not_selected(self):
        preset = next(p for p in DEFAULT_PROFILES if p["name"] == "Test / Alle Optionen")
        self.assertEqual(validate_profile(preset)["name"], "Test / Alle Optionen")

    def test_existing_database_receives_preset_without_selection_change(self):
        with tempfile.TemporaryDirectory() as folder:
            db_path = Path(folder) / "itomiscan.db"
            db = ConfigStore(db_path)
            db.select_profile("Text")
            # Emulate an older installation missing the new optional preset.
            with db._connection(write=True) as conn:
                conn.execute("DELETE FROM profiles WHERE name=?", ("Test / Alle Optionen",))
            upgraded = ConfigStore(db_path)
            profiles, selected = upgraded.list_profiles()
            self.assertIn("Test / Alle Optionen", [p["name"] for p in profiles])
            self.assertEqual(selected, "Text")
            again = ConfigStore(db_path)
            profiles_again, _ = again.list_profiles()
            self.assertEqual(sum(p["name"] == "Test / Alle Optionen"
                                 for p in profiles_again), 1)

    def test_existing_experiment_customization_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            db_path = Path(folder) / "itomiscan.db"
            db = ConfigStore(db_path)
            custom = next(p for p in DEFAULT_PROFILES if p["name"] == "Test / Alle Optionen").copy()
            custom["resolution"] = 150
            db.save_profile(custom)
            reopened = ConfigStore(db_path)
            profiles, _ = reopened.list_profiles()
            actual = next(p for p in profiles if p["name"] == "Test / Alle Optionen")
            self.assertEqual(actual["resolution"], 150)


if __name__ == "__main__":
    unittest.main()
