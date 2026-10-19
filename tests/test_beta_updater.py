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

    def test_atomic_installation_restores_previous_on_swap_failure(self):
        from unittest.mock import patch
        import os
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / "ItomiScan"
            project.mkdir()
            (project / "app.py").write_text("old")
            stage = root / "stage"
            stage.mkdir()
            (stage / "app.py").write_text("new")
            snapshot = root / "snapshot"
            real_replace = os.replace

            def fail_stage(source, target):
                if Path(source) == stage:
                    raise OSError("simulated swap failure")
                return real_replace(source, target)

            with patch.object(helper.os, "replace", side_effect=fail_stage):
                with self.assertRaises(OSError):
                    helper.atomic_deploy(project, stage, snapshot)
            self.assertEqual((project / "app.py").read_text(), "old")
            self.assertEqual((snapshot / "app.py").read_text(), "old")

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

    def test_full_install_and_rollback_offline(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            project = home / "ItomiScan"
            project.mkdir()
            (project / "app.py").write_text("old-version\n")
            stage_files = {
                "app.py": b"print('new')\n",
                "start-kiosk.sh": b"#!/bin/sh\nexit 0\n",
                "install-beta.sh": b"#!/bin/sh\n",
                "itomiscan/gui/kiosk.py": b"x=1\n",
            }
            expected = {name: (helper.git_blob_sha(data), 0o644)
                        for name, data in stage_files.items()}
            def download(_sha, path):
                path.write_bytes(tarball(stage_files))
                return "12345" * 12 + "abcd"
            def fetch(path):
                if path.startswith("releases"):
                    return [{"tag_name": "v1.0.0-beta.4",
                             "prerelease": True, "draft": False}]
                raise AssertionError(path)
            with patch.object(helper, "STATE", home / "private-state"), \
                 patch.object(helper, "read_settings", return_value={}), \
                 patch.object(helper, "preflight",
                              return_value=("scanner", 1000, 1000, home, project)), \
                 patch.object(helper, "fetch_json", side_effect=fetch), \
                 patch.object(helper, "release_commit",
                              return_value=("a" * 40, "b" * 40)), \
                 patch.object(helper, "expected_tree", return_value=expected), \
                 patch.object(helper, "download_archive", side_effect=download), \
                 patch.object(helper, "chown_tree"), \
                 patch.object(helper, "smoke_as_user"):
                helper.install()
                self.assertIn("new", (project / "app.py").read_text())
                self.assertTrue((project / "start-kiosk.sh").stat().st_mode & 0o111)
                self.assertEqual((project / ".itomiscan-beta-tag").read_text().strip(),
                                 "v1.0.0-beta.4")
                self.assertTrue((home / "private-state" / "last.json").exists())
                helper.rollback()
                self.assertEqual((project / "app.py").read_text(), "old-version\n")
                self.assertFalse((home / "private-state" / "last.json").exists())

    def test_smoke_failure_after_swap_restores_previous_version(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            project = home / "ItomiScan"
            project.mkdir()
            (project / "app.py").write_text("old-version\n")
            stage_files = {
                "app.py": b"print('new')\n",
                "start-kiosk.sh": b"#!/bin/sh\n",
                "install-beta.sh": b"#!/bin/sh\n",
                "itomiscan/gui/kiosk.py": b"x=1\n",
            }
            expected = {name: (helper.git_blob_sha(data), 0o644)
                        for name, data in stage_files.items()}
            def download(_sha, path):
                path.write_bytes(tarball(stage_files))
                return "0" * 64
            def verify(user, path):
                if path == project and (project / "app.py").read_text() != "old-version\n":
                    raise helper.UpdateError("simulierter Fehler nach Austausch")
            with patch.object(helper, "STATE", home / "private-state"), \
                 patch.object(helper, "read_settings", return_value={}), \
                 patch.object(helper, "preflight",
                              return_value=("scanner", 1000, 1000, home, project)), \
                 patch.object(helper, "fetch_json",
                              return_value=[{"tag_name": "v1.0.0-beta.4",
                                             "prerelease": True, "draft": False}]), \
                 patch.object(helper, "release_commit",
                              return_value=("a" * 40, "b" * 40)), \
                 patch.object(helper, "expected_tree", return_value=expected), \
                 patch.object(helper, "download_archive", side_effect=download), \
                 patch.object(helper, "chown_tree"), \
                 patch.object(helper, "smoke_as_user", side_effect=verify):
                with self.assertRaises(helper.UpdateError):
                    helper.install()
                self.assertEqual((project / "app.py").read_text(), "old-version\n")

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
