"""Beta 2 destination-specific input compatibility and safety tests."""
import unittest

from itomiscan.storage.config import validate_target, ConfigError
from itomiscan.web.target_forms import target_from_form
from itomiscan.web.delivery_pages import targets_page
from itomiscan.web.pages import TARGET_SELECT_JS


class DestinationInputTests(unittest.TestCase):
    def make(self, kind, **values):
        return target_from_form({"kind":kind, "name":"Archiv", "address":"", **values})

    def test_paperless_tls(self):
        self.assertEqual(validate_target(self.make(
            "paperless", paperless_url="https://dms.lan/"))["address"],
            "https://dms.lan")
        with self.assertRaises(ValueError):
            self.make("paperless", paperless_url="http://dms.lan")

    def test_smb_fields(self):
        item = self.make("network", network_host="nas.lan",
                         network_share="Scans", network_directory="Steuern/2026")
        self.assertEqual(validate_target(item)["address"],
                         "smb://nas.lan/Scans/Steuern/2026")
        for directory in ("../etc", "a//b", "foo;rm", "foo/.."):
            with self.subTest(directory=directory):
                with self.assertRaises(ValueError):
                    self.make("network", network_host="nas", network_share="Scans",
                              network_directory=directory)

    def test_smtp_fields(self):
        self.assertEqual(validate_target(self.make(
            "email", email_security="starttls", email_host="mail.lan",
            email_port="", email_recipient="scan@example.org"))["address"],
            "smtp://mail.lan:587/scan@example.org")
        self.assertEqual(validate_target(self.make(
            "email", email_security="smtps", email_host="mail.lan",
            email_port="", email_recipient="scan@example.org"))["address"],
            "smtps://mail.lan:465/scan@example.org")
        with self.assertRaises(ValueError):
            self.make("email", email_security="none", email_host="mail.lan",
                      email_recipient="scan@example.org")
        with self.assertRaises(ValueError):
            self.make("email", email_security="starttls", email_host="mail.lan",
                      email_port="70000", email_recipient="scan@example.org")

    def test_usb_fields_and_legacy_address(self):
        self.assertEqual(validate_target(self.make(
            "usb", usb_volume="SCANSTICK", usb_directory="Eingang/2026"))["address"],
            "usb://SCANSTICK/Eingang/2026")
        old = target_from_form({"kind":"network", "name":"Archiv",
                                "address":"smb://nas.lan/Altbestand"})
        self.assertEqual(validate_target(old)["address"],
                         "smb://nas.lan/Altbestand")

    def test_advanced_override_and_validator(self):
        item = target_from_form({"kind":"paperless", "name":"Archiv",
                                 "paperless_url":"https://normal.lan",
                                 "address":"https://override.lan"})
        self.assertEqual(validate_target(item)["address"], "https://override.lan")
        with self.assertRaises(ConfigError):
            validate_target(target_from_form({
                "kind":"paperless","name":"Archiv",
                "address":"https://user:password@dms.lan"}))

    def test_browser_has_distinct_sections(self):
        page = targets_page([], "csrf", {})
        for kind in ("paperless", "network", "email", "usb"):
            self.assertIn('data-target-section="' + kind + '"', page)
        for key in ("network_share", "network_host", "email_recipient",
                    "email_security", "usb_volume", "paperless_url"):
            self.assertIn('name="' + key + '"', page)
        self.assertIn('input.disabled = !selected', TARGET_SELECT_JS)
        self.assertIn("data-select-paperless", TARGET_SELECT_JS)


if __name__ == "__main__":
    unittest.main()
