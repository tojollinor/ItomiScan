"""Read-only regression assertions for opt-in boot optimization scripts.

No GRUB, initramfs, kernel or machine files are ever altered by these tests.
"""
import subprocess
import tempfile
import os
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BootOptimizationTests(unittest.TestCase):
    def test_all_boot_scripts_are_shell_syntax_valid(self):
        for name in ("test-dep-initramfs.sh", "setup-boot-splash.sh",
                     "restore-boot-splash.sh", "preflight-boot-splash.sh",
                     "inspect-boot-graphics.sh", "preflight-boot-candidate.sh",
                     "prepare-boot-candidate.sh", "test-boot-splash-candidate.sh",
                     "stage-boot-splash-assets.sh", "test-login-visibility.sh"):
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

    def test_login_visibility_test_is_reversible_without_boot_modification(self):
        script = (ROOT / "test-login-visibility.sh").read_text()
        for required in ("status|apply|restore", "profile.original",
                         "sha256sum -c --status", "hush.absent",
                         "ITOMISCAN_LOGIN_VISIBILITY_TEST",
                         "itomiscan-xorg-start.log"):
            self.assertIn(required, script)
        for forbidden in ("update-grub", "update-initramfs", "systemctl restart",
                          "systemctl reboot", "grub-reboot", "grub-set-default"):
            self.assertNotIn(forbidden, script)

    def test_theme_staging_is_isolated_from_host_boot_files(self):
        stage = (ROOT / "stage-boot-splash-assets.sh").read_text()
        for required in ('itomiscan.branding --output', 'realpath -m',
                         'itomiscan-static', 'itomiscan.script', 'Plymouth.SetRefreshFunction'):
            self.assertIn(required, stage)
        for forbidden in ('update-initramfs', 'update-grub', 'grub-reboot',
                          'plymouth-set-default-theme ', 'systemctl reboot'):
            self.assertNotIn(forbidden, stage)

    def test_candidate_preflight_cannot_modify_boot(self):
        script = (ROOT / "preflight-boot-candidate.sh").read_text()
        for required in ("itomiscan-splash-test", "dep-test", "i915", "plymouth"):
            self.assertIn(required, script)
        for forbidden in ("mkinitramfs -o", "update-initramfs -u", "update-grub",
                          "grub-reboot", "grub-set-default", "systemctl reboot"):
            self.assertNotIn(forbidden, script)

    def test_candidate_builder_never_overwrites_existing_initramfs_or_edits_grub(self):
        script = (ROOT / "prepare-boot-candidate.sh").read_text()
        for required in ('mkinitramfs -d "$work/config" -o "$image"',
                         'MODULES=dep', 'ln -- "$image" "$CANDIDATE"',
                         'Plymouth.SetRefreshFunction(refresh_callback)',
                         'itomiscan-overlay', 'ITOMISCAN_SPLASH_STAGE',
                         'itomiscan-splash-test', 'lsinitramfs "$image"'):
            self.assertIn(required, script)
        for forbidden in ('\nupdate-grub ', '\ngrub-reboot ', '\ngrub-set-default ',
                          '\nupdate-initramfs -u', '\nsystemctl reboot',
                          'cp "$image" "$DEP"', 'cp "$image" "$BASE"'):
            self.assertNotIn(forbidden, script)

    def test_separate_splash_entry_preserves_dep_default_and_one_shot(self):
        script = (ROOT / "test-boot-splash-candidate.sh").read_text()
        for expected in ('ENTRY_ID="itomiscan-splash-candidate-test"',
                         'OLD_ID="itomiscan-initramfs-dep-test"',
                         'GRUB_TIMEOUT=2', 'grub-reboot "$ENTRY_ID"',
                         'grub-script-check', 'sha256sum -c',
                         '40_custom.before', 'GRUB_DEFAULT', 'initramfs'):
            self.assertIn(expected, script)
        self.assertNotIn('grub-set-default', script)
        self.assertNotIn('update-initramfs', script)
        self.assertNotIn('systemctl reboot', script)

    def test_temporary_hook_replaces_only_candidate_theme_copy(self):
        script = (ROOT / "prepare-boot-candidate.sh").read_text()
        start = script.index("<<'OVERLAY'\n") + len("<<'OVERLAY'\n")
        end = script.index("\nOVERLAY\n", start)
        hook_text = script[start:end] + "\n"
        with tempfile.TemporaryDirectory() as tempdir:
            temp = Path(tempdir)
            hook_dir = temp / "config" / "hooks"
            staged = temp / "config" / "itomiscan-overlay" / "itomiscan"
            dest = temp / "image" / "usr" / "share" / "plymouth" / "themes" / "itomiscan"
            hook_dir.mkdir(parents=True)
            staged.mkdir(parents=True)
            dest.mkdir(parents=True)
            (staged / "itomiscan.script").write_text("new animated theme")
            (dest / "itomiscan.script").write_text("old static theme")
            hook = hook_dir / "zzzz-itomiscan-overlay"
            hook.write_text(hook_text)
            result = subprocess.run(
                ["sh", str(hook)], env={**os.environ, "DESTDIR": str(temp / "image")},
                capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((dest / "itomiscan.script").read_text(), "new animated theme")
            self.assertEqual((staged / "itomiscan.script").read_text(), "new animated theme")

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
