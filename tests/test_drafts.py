import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from unittest.mock import Mock
from types import SimpleNamespace

from itomiscan.storage.drafts import DraftStore


class DraftTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.path = self.root / "config" / "test.db"
        self.store = DraftStore(self.path)
        self.first = self.root / "first.png"
        self.second = self.root / "second.png"
        self.first.write_bytes(b"first original")
        self.second.write_bytes(b"second original")

    def test_restart_and_other_users_preserve_order_and_state(self):
        state = {"page_index": 1, "pending_batch": {"targets": [7]},
                 "batch_settings": [["--resolution=300"], "Color", "PDF"]}
        self.store.save(1, [self.second, self.first], state)
        self.store.save(2, [self.first], {"page_index": 0})
        restored = DraftStore(self.path).restore(1)
        pages, folder, actual = restored
        self.assertEqual([p.read_bytes() for p in pages], [b"second original", b"first original"])
        self.assertEqual(actual, state)
        self.assertIsNone(self.store.load(3))
        self.assertIsNone(self.store.load(None))
        self.assertNotEqual(folder, self.first.parent)

    def test_edits_and_deletion_retain_immutable_originals(self):
        self.store.save(1, [self.first, self.second], {})
        original = self.store.load(1)["pages"][0]
        self.first.write_bytes(b"rotated first")
        self.store.save(1, [self.first], {"page_index": 0})
        self.second.unlink()
        data = self.store.load(1)
        self.assertEqual(len(data["pages"]), 1)
        self.assertEqual(len(data["originals"]), 2)
        self.assertEqual((self.store.assets / original).read_bytes(), b"first original")
        self.assertEqual(self.store.restore(1)[0][0].read_bytes(), b"rotated first")

    def test_failed_asset_write_keeps_previous_manifest(self):
        self.store.save(1, [self.first], {"page_index": 0})
        previous = self.store.load(1)
        with patch("itomiscan.storage.drafts.os.fsync", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.store.save(1, [self.second], {})
        self.assertEqual(self.store.load(1), previous)
        self.assertEqual(list(self.store.assets.glob(".writing-*")), [])

    def test_unchanged_snapshot_does_not_rewrite_manifest_or_assets(self):
        self.assertTrue(self.store.save(None, [self.first], {}))
        with patch.object(self.store, "_asset", wraps=self.store._asset):
            with patch("itomiscan.storage.drafts.tempfile.mkstemp", side_effect=AssertionError):
                self.assertFalse(self.store.save(None, [self.first], {}))

    def test_empty_review_survives_and_finish_is_owner_scoped(self):
        self.store.save(1, [], {"view": "review"})
        self.store.save(2, [self.first], {})
        self.assertEqual(self.store.restore(1)[0], [])
        self.store.finish(1)
        self.assertIsNone(self.store.load(1))
        self.assertIsNotNone(self.store.load(2))
        self.assertTrue(self.first.exists())

    def test_owner_validation(self):
        for value in (True, 0, -1, "1", "../other"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.store.load(value)

    def test_restored_work_cannot_modify_snapshot(self):
        self.store.save(1, [self.first], {})
        restored = self.store.restore(1)[0][0]
        restored.write_bytes(b"edited")
        self.assertEqual(self.store.restore(1)[0][0].read_bytes(), b"first original")

    def test_batch_address_keys_restore_as_integer_target_ids(self):
        from app import ItomiScan
        state = {"pending_batch": {"ids": [7], "addresses": {"7": "smb://nas/scans"}}}
        obj = SimpleNamespace(
            drafts=Mock(), _draft_owner=Mock(return_value=1),
            format_var=Mock(get=Mock(return_value="PDF")), show_scan=Mock(),
            show_page=Mock(), review_button=Mock(), append_button=Mock(), status_var=Mock())
        obj.drafts.restore.return_value = ([self.first], self.root, state)
        ItomiScan._restore_draft(obj)
        self.assertEqual(obj.pending_batch["addresses"], {7: "smb://nas/scans"})


if __name__ == "__main__":
    unittest.main()
