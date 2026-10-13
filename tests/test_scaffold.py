"""Offline smoke test for the new package skeleton (no scanner needed)."""

import importlib
import unittest


PACKAGES = (
    "itomiscan",
    "itomiscan.core",
    "itomiscan.gui",
    "itomiscan.web",
    "itomiscan.storage",
    "itomiscan.integrations",
)


class PackageStructureTests(unittest.TestCase):
    def test_all_namespace_packages_import(self):
        for package in PACKAGES:
            with self.subTest(package=package):
                self.assertIsNotNone(importlib.import_module(package))


if __name__ == "__main__":
    unittest.main()
