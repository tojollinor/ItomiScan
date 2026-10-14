"""Regression checks for the opt-in all-options scan preset."""
import tempfile
import unittest
from pathlib import Path

from itomiscan.core.profiles import DEFAULT_PROFILES, validate_profile, experiment_settings
from itomiscan.storage.config import ConfigStore


class ExperimentProfileTests(unittest.TestCase):
    def test_unknown_backend_specific_sane_options_are_visible(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        from app import read_options
        output = ("  Standard:\n"
                  "    --source ADF Front|ADF Duplex [ADF Duplex]\n"
                  "  Advanced:\n"
                  "    --vendor-special no|yes [no]\n")
        with patch("app.shell", return_value=SimpleNamespace(returncode=0,
                                                               stdout=output, stderr="")):
            options = read_options("fujitsu:test")
        self.assertIn("--vendor-special", [opt["flag"] for opt in options])

    def test_only_active_supported_features_are_enabled(self):
        options = [
            {"flag": "--source", "choices": ["ADF Front", "ADF Duplex"], "inactive": False},
            {"flag": "--mode", "choices": ["Gray", "Color"], "inactive": False},
            {"flag": "--swdeskew", "kind": "bool", "choices": ["no", "yes"], "inactive": False},
            {"flag": "--swcrop", "kind": "bool", "choices": ["no", "yes"], "inactive": True},
            {"flag": "--df-action", "kind": "enum", "choices": ["Stop", "Continue"], "inactive": False},
            {"flag": "--resolution", "kind": "number", "choices": [], "inactive": False},
        ]
        settings = experiment_settings(options)
        self.assertEqual(settings["--source"], "ADF Duplex")
        self.assertEqual(settings["--mode"], "Color")
        self.assertEqual(settings["--swdeskew"], "yes")
        self.assertNotIn("--swcrop", settings)
        self.assertNotIn("--df-action", settings)
        self.assertNotIn("--resolution", settings)

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
