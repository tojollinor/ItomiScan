"""Offline tests for release selection, Git blob verification, and unsafe archives."""
import hashlib
import io
from pathlib import Path
import tarfile
import tempfile
import types
import unittest
import importlib.util

HELPER = Path(__file__).resolve().parents[1] / "scripts" / "itomiscan-beta-updater.py"
spec = importlib.util.spec_from_file_location("itomiscan_beta_updater_helper", HELPER)
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


def tarball(entries):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        directory = tarfile.TarInfo("ItomiScan-abcdefg/")
        directory.type = tarfile.DIRTYPE
        archive.addfile(directory)
        for filename, data in entries.items():
            item = tarfile.TarInfo("ItomiScan-abcdefg/" + filename)
            item.size = len(data)
            archive.addfile(item, io.BytesIO(data))
    return output.getvalue()


class BetaUpdaterTests(unittest.TestCase):
    def test_beta_selection_rejects_drafts_stable_and_unpublished(self):
        entries = [
            {"tag_name": "v1.0.0-beta.3", "prerelease": True, "draft": False},
            {"tag_name": "v1.0.0-beta.12", "prerelease": True, "draft": False},
            {"tag_name": "v1.0.0-beta.999", "prerelease": True, "draft": True},
            {"tag_name": "v1.0.1", "prerelease": False, "draft": False},
            {"tag_name": "develop/1.0.0", "prerelease": True, "draft": False},
        ]
        self.assertEqual(helper.latest_beta(entries), "v1.0.0-beta.12")

    def test_blob_digest_matches_git_format(self):
        content = b"hello\n"
        expected = hashlib.sha1(b"blob 6\0hello\n").hexdigest()
        self.assertEqual(helper.git_blob_sha(content), expected)

    def test_release_archive_extracts_exactly_committed_files(self):
        contents = {"app.py": b"print('ok')\n", "itomiscan/gui/kiosk.py": b"x=1\n"}
        expected = {k: (helper.git_blob_sha(v), 0o644) for k, v in contents.items()}
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "source.tar.gz"
            archive.write_bytes(tarball(contents))
            stage = Path(temp) / "stage"
            helper.extract_verified_archive(archive, stage, expected)
            self.assertEqual((stage / "app.py").read_bytes(), contents["app.py"])

    def test_rejects_tampered_file_without_leaving_it_installed(self):
        contents = {"app.py": b"tampered"}
        expected = {"app.py": (helper.git_blob_sha(b"original"), 0o644)}
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "source.tar.gz"
            archive.write_bytes(tarball(contents))
            with self.assertRaises(helper.UpdateError):
                helper.extract_verified_archive(archive, Path(temp) / "stage", expected)

    def test_rejects_path_traversal(self):
        contents = {"../escape": b"bad"}
        expected = {"../escape": (helper.git_blob_sha(b"bad"), 0o644)}
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "source.tar.gz"
            archive.write_bytes(tarball(contents))
            with self.assertRaises(helper.UpdateError):
                helper.extract_verified_archive(archive, Path(temp) / "stage", expected)
            self.assertFalse((Path(temp) / "escape").exists())

    def test_rejects_symlinks_in_archive(self):
        output = io.BytesIO()
        with tarfile.open(fileobj=output, mode="w:gz") as archive:
            root = tarfile.TarInfo("ItomiScan-abcdefg/")
            root.type = tarfile.DIRTYPE
            archive.addfile(root)
            entry = tarfile.TarInfo("ItomiScan-abcdefg/app.py")
            entry.type = tarfile.SYMTYPE
            entry.linkname = "/etc/passwd"
            archive.addfile(entry)
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "source.tar.gz"
            source.write_bytes(output.getvalue())
            with self.assertRaises(helper.UpdateError):
                helper.extract_verified_archive(
                    source, Path(temp) / "stage",
                    {"app.py": (helper.git_blob_sha(b"a"), 0o644)})

    def test_requires_published_beta_tag_for_commit_resolution(self):
        with self.assertRaises(helper.UpdateError):
            helper.release_commit("develop/1.0.0")

    def test_progress_contract_json_lines(self):
        import contextlib
        import json
        import sys
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            helper.progress(35, "Download läuft")
        self.assertEqual(json.loads(stream.getvalue())["percent"], 35)


if __name__ == "__main__":
    unittest.main()
