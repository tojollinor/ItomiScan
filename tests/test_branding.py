"""Offline consistency checks for the shared animated/static boot and Tk branding."""
import tempfile
import unittest
from pathlib import Path

from PIL import Image
from itomiscan import branding


class BrandingTest(unittest.TestCase):
    def test_plymouth_assets_generated_from_shared_constants(self):
        with tempfile.TemporaryDirectory() as tmp:
            themes = Path(tmp) / "themes"
            output = themes / "itomiscan"
            branding.render_plymouth_assets(output)
            expected = ("logo-base.png", "scanline.png", "brand.png",
                        "subtitle.png", "status.png", "detail.png")
            for filename in expected:
                with Image.open(output / filename) as image:
                    image.verify()
            with Image.open(output / "logo-base.png") as logo:
                self.assertEqual(logo.size, (branding.LOGO_SIZE, branding.LOGO_SIZE))
            with Image.open(output / "scanline.png") as line:
                self.assertEqual(
                    line.size,
                    (round((branding.LINE_RIGHT - branding.LINE_LEFT)
                           * branding.LOGO_SIZE / branding.LOGO_UNITS),
                     round(branding.LINE_HEIGHT * branding.LOGO_SIZE /
                           branding.LOGO_UNITS)),
                )

            animated = (output / "itomiscan.script").read_text()
            self.assertIn(f"logo_sprite.SetY(top + {branding.LOGO_Y})", animated)
            self.assertIn("Plymouth.SetRefreshFunction(refresh_callback)", animated)
            self.assertIn(f"line_position = {branding.LINE_START}", animated)
            self.assertIn("Plymouth.SetMessageFunction(message_callback)", animated)
            self.assertIn("Plymouth.SetHideMessageFunction(hide_message_callback)", animated)
            self.assertIn(f"top + {branding.DETAIL_Y}", animated)
            self.assertTrue((output / "itomiscan.plymouth").is_file())
            self.assertIn(branding.BOOT_STATUS, branding.BOOT_STATUS)
            self.assertIn("System wird gestartet", branding.BOOT_STATUS)
            self.assertIn("Bitte warten", branding.BOOT_DETAIL)

            static_dir = themes / "itomiscan-static"
            with Image.open(static_dir / "static-boot.png") as static_image:
                self.assertEqual(static_image.size,
                                 (branding.SCREEN_WIDTH, branding.SCREEN_HEIGHT))
                self.assertEqual(static_image.getpixel((0, 0)), (16, 25, 39, 255))
            static_theme = (static_dir / "itomiscan-static.plymouth").read_text()
            static_script = (static_dir / "itomiscan-static.script").read_text()
            self.assertIn("ImageDir=/usr/share/plymouth/themes/itomiscan-static",
                          static_theme)
            self.assertIn('Image("static-boot.png")', static_script)

    def test_splash_uses_shared_scan_line_not_spinning_ring(self):
        splash = (Path(__file__).resolve().parents[1] /
                  "itomiscan/gui/splash.py").read_text()
        self.assertIn("set_logo_busy(self.logo, True)", splash)
        self.assertIn("branding.LOGO_Y", splash)
        self.assertNotIn("create_arc(", splash)

    def test_installer_generates_both_themes_and_preserves_grub_timeout(self):
        boot = (Path(__file__).resolve().parents[1] /
                "setup-boot-splash.sh").read_text()
        self.assertIn("python3 -m itomiscan.branding --output", boot)
        self.assertIn("itomiscan.script", boot)
        self.assertIn("cmp -s /etc/default/grub", boot)
        self.assertIn('ITOMISCAN_SPLASH_MODE:-animated', boot)
        self.assertIn("itomiscan-initramfs-dep-test", boot)
        self.assertIn("previous-itomiscan-static-theme", boot)
        self.assertNotIn('("GRUB_TIMEOUT", "0")', boot)
        self.assertNotIn('("GRUB_TIMEOUT_STYLE", "hidden")', boot)


if __name__ == "__main__":
    unittest.main()
