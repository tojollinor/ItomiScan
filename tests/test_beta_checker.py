"""Beta update discovery should only select published prereleases."""
import io
import json
from pathlib import Path
import tempfile
import unittest

from itomiscan.gui.beta_updates import latest_published_beta, installed_version, HELPER


class Reply:
    def __init__(self, contents):
        self.contents = io.BytesIO(json.dumps(contents).encode("utf-8"))

    def __enter__(self):
        return self.contents

    def __exit__(self, *unused):
        return None


class TestBetaChecker(unittest.TestCase):
    def test_release_selection(self):
        def opener(request, timeout):
            if "releases?" in request.full_url:
                return Reply([
                    {"tag_name": "v1.0.0", "prerelease": False, "draft": False},
                    {"tag_name": "v1.0.0-beta.4", "prerelease": True, "draft": True},
                    {"tag_name": "v1.0.0-beta.3", "prerelease": True, "draft": False},
                    {"tag_name": "develop/1.0.0", "prerelease": True, "draft": False}
                ])
            self.assertTrue(request.full_url.endswith("/commits/v1.0.0-beta.3"))
            return Reply({"sha": "a" * 40})
        self.assertEqual(latest_published_beta(opener),
                         ("v1.0.0-beta.3", "a" * 40))

    def test_local_marker(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / ".itomiscan-beta-commit").write_text("a" * 40)
            (root / ".itomiscan-beta-tag").write_text("v1.0.0-beta.3")
            self.assertEqual(installed_version(root),
                             ("a" * 40, "v1.0.0-beta.3"))

    def test_root_helper_path_fixed(self):
        self.assertEqual(HELPER, "/usr/local/libexec/itomiscan-beta-updater")


if __name__ == "__main__":
    unittest.main()
