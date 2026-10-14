"""Disk-backed scanner backup tests: secrets, PIN users, PDFs, checksum and staging."""
import hashlib
from pathlib import Path
import tempfile
import unittest

from itomiscan.storage.config import ConfigStore
from itomiscan.storage.queue import DeliveryQueue
from itomiscan.storage.secrets import SecretStore
from itomiscan.storage.users import UserStore
from itomiscan.storage.full_backup import BackupError, create_backup, verify_backup
from itomiscan.storage.backup_cli import restore_to_staging


class OfflineBackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.home = self.base / "home"
        self.conf = self.home / ".config" / "itomiscan"
        self.conf.mkdir(parents=True)
        self.store = ConfigStore(self.conf / "itomiscan.db")
        self.queue = DeliveryQueue(self.store.path)
        self.secret_store = SecretStore(self.store.path)
        self.store.save_target({
            "kind": "paperless", "name": "Archiv",
            "address": "https://paperless.example.org"})
        target = self.store.list_targets()[0]["id"]
        self.secret_store.update(target, token="test-token")
        users = UserStore(self.store.path)
        users.save_user(name="Account", pin="4815", permissions=["scan"],
                        assigned_profiles=["Dokument"], default_profile="Dokument")
        users.configure(enabled=True)
        self.scan = self.home / "Scans" / "Scan"
        self.scan.mkdir(parents=True)
        self.pdf = self.scan / "Dokument.pdf"
        self.pdf.write_bytes(b"%PDF-1.4\n" + b"test" * 800)
        self.job_id = self.queue.enqueue(self.pdf, target)
        (self.conf / "tls").mkdir()
        (self.conf / "tls" / "key.pem").write_bytes(b"test-private-key")
        self.archive = self.base / "backup.zip"

    def test_complete_backup_and_restoration_to_new_folder(self):
        result = create_backup(self.archive, home=self.home, config_dir=self.conf)
        self.assertGreaterEqual(result["files"], 4)
        self.assertEqual(self.archive.stat().st_mode & 0o777, 0o600)
        self.assertEqual(result["files"], verify_backup(self.archive)["files"])
        staging = self.base / "staging"
        restore_to_staging(self.archive, staging)
        recovered_users = UserStore(staging / "config" / "itomiscan.db")
        self.assertEqual(recovered_users.verify_pin("4815")["name"], "Account")
        self.assertEqual((staging / "config" / "integrations-secrets.json").read_bytes(),
                         self.secret_store.path.read_bytes())
        self.assertEqual((staging / "spool" / (self.job_id + ".pdf")).read_bytes(),
                         self.pdf.read_bytes())
        self.assertEqual((staging / "scans" / "Scan" / "Dokument.pdf").read_bytes(),
                         self.pdf.read_bytes())
        self.assertEqual((staging / "config" / "tls" / "key.pem").read_bytes(),
                         b"test-private-key")

    def test_refuses_busy_worker_and_archive_overwrite(self):
        with self.store._connection(write=True) as db:
            db.execute("UPDATE delivery_jobs SET status='sending'")
        with self.assertRaises(BackupError):
            create_backup(self.archive, home=self.home, config_dir=self.conf)
        with self.store._connection(write=True) as db:
            db.execute("UPDATE delivery_jobs SET status='queued'")
        create_backup(self.archive, home=self.home, config_dir=self.conf)
        with self.assertRaises(BackupError):
            create_backup(self.archive, home=self.home, config_dir=self.conf)

    def test_recovery_never_overwrites_existing_scans(self):
        create_backup(self.archive, home=self.home, config_dir=self.conf)
        previous_hash = hashlib.sha256(self.pdf.read_bytes()).hexdigest()
        restore_to_staging(self.archive, self.base / "stage")
        self.assertEqual(hashlib.sha256(self.pdf.read_bytes()).hexdigest(), previous_hash)
        with self.assertRaises(BackupError):
            restore_to_staging(self.archive, self.base / "stage")

    def test_no_live_archive_in_scan_tree(self):
        with self.assertRaises(BackupError):
            create_backup(self.scan / "backup.zip",
                          home=self.home, config_dir=self.conf)

    def test_refuse_symlink_in_saved_scans(self):
        self.pdf.unlink()
        self.pdf.symlink_to(self.conf / "itomiscan.db")
        with self.assertRaises(BackupError):
            create_backup(self.archive, home=self.home, config_dir=self.conf)


if __name__ == "__main__":
    unittest.main()
