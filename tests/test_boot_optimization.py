"""Read-only regression assertions for opt-in boot optimization scripts.

No GRUB, initramfs, kernel or machine files are ever altered by these tests.
"""
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BootOptimizationTests(unittest.TestCase):
    def test_all_boot_scripts_are_shell_syntax_valid(self):
        for name in ("test-dep-initramfs.sh", "setup-boot-splash.sh",
                     "restore-boot-splash.sh", "preflight-boot-splash.sh",
                     "inspect-boot-graphics.sh", "preflight-boot-candidate.sh"):
            with self.subTest(name=name):
                result = subprocess.run(
                    ["bash", "-n", str(ROOT / name)],
                    capture_output=True, text=True, check=False)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_dep_boot_is_one_shot_and_keeps_original_default(self):
        script = (ROOT / "test-dep-initramfs.sh").read_text()
        self.assertIn("grub-reboot", script)
        self.assertIn("GRUB_DEFAULT=0", script)
        self.assertIn('cmp -s "$CUSTOM" "$backup_dir/40_custom.original"', script)
        self.assertIn("grub-script-check", script)
        self.assertIn("No changes", script.replace("Keine Änderungen vorgenommen.", "No changes"))
        self.assertNotIn("grub-set-default", script)
        self.assertNotIn("update-initramfs", script)
        self.assertNotIn("systemctl reboot", script)
        self.assertNotIn("sudo reboot", script)

    def test_boot_splash_restore_has_matching_theme_backup_filename(self):
        setup = (ROOT / "setup-boot-splash.sh").read_text()
        restore = (ROOT / "restore-boot-splash.sh").read_text()
        self.assertIn("previous-theme-name", setup)
        self.assertIn("previous-theme-name", restore)

    def test_candidate_preflight_cannot_modify_boot(self):
        script = (ROOT / "preflight-boot-candidate.sh").read_text()
        for required in ("itomiscan-splash-test", "dep-test", "i915", "plymouth"):
            self.assertIn(required, script)
        for forbidden in ("mkinitramfs -o", "update-initramfs -u", "update-grub",
                          "grub-reboot", "grub-set-default", "systemctl reboot"):
            self.assertNotIn(forbidden, script)

    def test_graphics_diagnostic_is_read_only_and_checks_both_initramfs_images(self):
        script = (ROOT / "inspect-boot-graphics.sh").read_text()
        for required in ("GRUB_GFXMODE", "GRUB_GFXPAYLOAD_LINUX", "/proc/cmdline",
                         "i915", "lsinitramfs", "itomiscan-initramfs-dep-test",
                         "static-boot", "keine Dateien oder Einstellungen geaendert"):
            self.assertIn(required, script)
        for forbidden in ("update-grub", "update-initramfs", "grub-reboot",
                          "grub-set-default", "apt-get install", "systemctl reboot"):
            self.assertNotIn(forbidden, script)


if __name__ == "__main__":
    unittest.main()
