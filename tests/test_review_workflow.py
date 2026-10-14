"""Headless regression checks for scan continuation and document review."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PIL import Image
from app import ItomiScan


class ReviewWorkflowTests(unittest.TestCase):
    def test_append_after_deleting_last_page_uses_original_settings(self):
        with tempfile.TemporaryDirectory() as folder:
            obj = SimpleNamespace(
                busy=False, review_pending=True, pages=[],
                output_path=Path(folder) / "Dokument.pdf",
                batch_settings=(["--resolution=300", "--source=ADF Duplex"], "Color", "PDF"),
                chosen_args=Mock(side_effect=AssertionError("changed UI must not be read")),
                fields=[], format_var=Mock(), scan_button=Mock(),
                progress=Mock(), status_var=Mock(), tempdir=None,
                device="fujitsu:test", scan_worker=Mock())
            with patch("app.threading.Thread") as thread:
                ItomiScan.append_pages(obj)
            self.assertTrue(obj.busy)
            self.assertTrue(obj.appending_pages)
            self.assertEqual(obj.last_scan_settings,
                             (["--resolution=300", "--source=ADF Duplex"], "Color", "PDF"))
            obj.chosen_args.assert_not_called()
            thread.assert_called_once()
            self.assertEqual(thread.call_args.kwargs["args"],
                             (["--resolution=300", "--source=ADF Duplex"], "PDF", "Color"))
            obj.tempdir.cleanup()

    def test_failed_append_preserves_review_and_pages(self):
        page = Path("/tmp/itomiscan-existing-page.jpg")
        obj = SimpleNamespace(
            appending_pages=True, pages=[page], review_pending=True,
            busy=True, scan_button=Mock(), progress=Mock(), status_var=Mock(),
            root=Mock())
        with patch("app.show_scanner_error"):
            ItomiScan.scan_failed(obj, "Kein Papier")
        self.assertEqual(obj.pages, [page])
        self.assertTrue(obj.review_pending)
        self.assertFalse(obj.busy)
        self.assertIn("1 bisherige", obj.status_var.set.call_args.args[0])

    def test_confirmed_blank_pages_are_removed_from_staging(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            first = directory / "page-0001.png"
            blank = directory / "page-0002.png"
            Image.new("RGB", (20, 20), "black").save(first)
            Image.new("RGB", (20, 20), "white").save(blank)
            obj = SimpleNamespace(
                busy=True, pages=[first, blank], page_index=1,
                output_path=directory / "Dokument.pdf", status_var=Mock(),
                show_page=Mock(), root=Mock())
            with patch("app.messagebox.askyesno", return_value=True):
                ItomiScan._confirm_blank_pages(obj, [first, blank], [1])
            self.assertEqual(obj.pages, [first])
            self.assertTrue(first.exists())
            self.assertFalse(blank.exists())
            obj.show_page.assert_called_once()

    def test_rejected_blank_page_confirmation_preserves_files(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            first = directory / "page-0001.png"
            blank = directory / "page-0002.png"
            first.write_bytes(b"original")
            blank.write_bytes(b"blank")
            obj = SimpleNamespace(
                busy=True, pages=[first, blank], page_index=0,
                output_path=directory / "Dokument.pdf", status_var=Mock(),
                root=Mock())
            with patch("app.messagebox.askyesno", return_value=False):
                ItomiScan._confirm_blank_pages(obj, [first, blank], [1])
            self.assertEqual(obj.pages, [first, blank])
            self.assertTrue(blank.exists())


if __name__ == "__main__":
    unittest.main()
