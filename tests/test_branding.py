"""Offline consistency checks for the shared boot and Tk scanner logo."""
import tempfile
import unittest
from pathlib import Path

from PIL import Image
from itomiscan import branding


class BrandingTest(unittest.TestCase):
    def test_plymouth_assets_generated_from_shared_constants(self):
        with tempfile.TemporaryDirectory() as tmp:
            branding.render_plymouth_assets(tmp)
            expected = ("logo-base.png", "scanline.png", "brand.png",
                        "subtitle.png", "status.png", "detail.png")
            for filename in expected:
                image = Image.open(Path(tmp) / filename)
                image.verify()
            with Image.open(Path(tmp) / "logo-base.png") as logo:
                self.assertEqual(logo.size, (branding.LOGO_SIZE, branding.LOGO_SIZE))
            with Image.open(Path(tmp) / "scanline.png") as line:
                self.assertEqual(
                    line.size,
                    (round((branding.LINE_RIGHT - branding.LINE_LEFT)
                           * branding.LOGO_SIZE / branding.LOGO_UNITS),
                     round(branding.LINE_HEIGHT * branding.LOGO_SIZE /
                           branding.LOGO_UNITS)),
                )

    def test_splash_uses_shared_scan_line_not_spinning_ring(self):
        splash = (Path(__file__).resolve().parents[1] /
                  "itomiscan/gui/splash.py").read_text()
        self.assertIn("set_logo_busy(self.logo, True)", splash)
        self.assertIn("branding.LOGO_Y", splash)
        self.assertNotIn("create_arc(", splash)

    def test_installer_generates_and_animates_plymouth_theme(self):
        boot = (Path(__file__).resolve().parents[1] /
                "setup-boot-splash.sh").read_text()
        self.assertIn("python3 -m itomiscan.branding --output", boot)
        self.assertIn("Plymouth.SetRefreshFunction(refresh_callback)", boot)
        self.assertIn("cmp -s /etc/default/grub", boot)


if __name__ == "__main__":
    unittest.main()
