"""Delivery spool, offline recovery, secret handling and transport safety."""
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from itomiscan.integrations.delivery import (
    DeliveryError, deliver, deliver_paperless, deliver_smb, deliver_usb)
from itomiscan.storage.config import ConfigStore
from itomiscan.storage.queue import DeliveryQueue, QueueError
from itomiscan.storage.secrets import SecretStore


class Clock:
    def __init__(self):
        self.now = 1000

    def __call__(self):
        return self.now


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.path = Path(self.dir.name) / "settings" / "itomiscan.db"
        self.clock = Clock()
        self.db = ConfigStore(self.path)
        self.queue = DeliveryQueue(self.path, clock=self.clock)
        self.pdf = Path(self.dir.name) / "source.pdf"
        self.pdf.write_bytes(b"%PDF-1.4\n" + b"x" * 240 + b"\n%%EOF")
        for kind, address in (("paperless", "https://example.org"),
                              ("network", "smb://nas/share/Scans"),
                              ("usb", "usb://SCANUSB/Scans"),
                              ("email", "smtps://mail.example.org/scan@example.org")):
            self.db.save_target({"kind":kind, "name":kind,
                                 "address":address})
        self.targets = {r["kind"]:r["id"] for r in self.db.list_targets()}

    def create(self, kind="usb"):
        return self.queue.enqueue(self.pdf, self.targets[kind])

    def test_removed_or_changed_target_never_sends_to_stale_destination(self):
        original = self.create("usb")
        self.db.delete_target(self.targets["usb"])
        self.assertIsNone(self.queue.process_once(lambda *_: self.fail("must not send")))
        self.assertEqual(self.queue.all()[0]["status"], "failed")
        self.assertTrue(self.pdf.exists())

        self.db.save_target({"kind":"paperless","name":"Archiv2",
                             "address":"https://one.example.org"})
        target = next(x for x in self.db.list_targets() if x["name"]=="Archiv2")
        second = self.queue.enqueue(self.pdf, target["id"])
        self.db.save_target({"kind":"paperless","name":"Archiv2",
                             "address":"https://two.example.org"})
        self.assertIsNone(self.queue.process_once(lambda *_: self.fail("must not send")))
        state = next(x["status"] for x in self.queue.all() if x["id"] == second)
        self.assertEqual(state, "review")

    def test_file_is_spooled_and_retained_after_success(self):
        ident = self.create()
        source_hash = hashlib.sha256(self.pdf.read_bytes()).hexdigest()
        job = self.queue.all()[0]
        self.assertEqual(job["digest"], source_hash)
        self.assertEqual(self.queue.file_for(job).read_bytes(), self.pdf.read_bytes())
        self.assertEqual(self.queue.process_once(lambda j,p: "success"), ident)
        self.assertEqual(self.queue.all()[0]["status"], "done")
        self.assertTrue(self.queue.file_for(self.queue.all()[0]).exists())
        self.assertTrue(self.pdf.exists())

    def test_transient_failure_retries_after_clock_advance(self):
        ident = self.create("usb")
        attempts = []
        def down_then_up(job, path):
            attempts.append(job["id"])
            if len(attempts) == 1:
                raise DeliveryError("USB nicht vorhanden.")
            return "done"
        self.queue.process_once(down_then_up)
        self.assertEqual(self.queue.all()[0]["status"], "retry")
        self.assertIsNone(self.queue.process_once(down_then_up))
        self.clock.now += 61
        self.queue.process_once(down_then_up)
        self.assertEqual(len(attempts), 2)
        self.assertEqual(self.queue.all()[0]["status"], "done")

    def test_uncertain_http_result_never_replayed_automatically(self):
        ident = self.create("paperless")
        def uncertain(job, path):
            raise DeliveryError("Timeout nach Übermittlung", uncertain=True)
        self.queue.process_once(uncertain)
        self.assertEqual(self.queue.all()[0]["status"], "review")
        self.clock.now += 9000
        self.assertIsNone(self.queue.process_once(lambda *_: "should-not-happen"))
        with self.assertRaises(QueueError):
            self.queue.retry(ident)
        self.queue.retry(ident, acknowledge_uncertain=True)
        self.queue.process_once(lambda *_: "accepted")
        self.assertEqual(self.queue.all()[0]["status"], "done")

    def test_interrupted_sending_requires_review_for_email_and_paperless(self):
        for kind in ("email", "paperless", "usb"):
            self.create(kind)
        for _ in range(3):
            self.assertIsNotNone(self.queue.claim())
        self.clock.now += 610
        self.assertEqual(self.queue.recover(), 3)
        states = {j["kind"]:j["status"] for j in self.queue.all()}
        self.assertEqual(states["paperless"], "review")
        self.assertEqual(states["email"], "review")
        self.assertEqual(states["usb"], "retry")

    def test_modified_spool_rejected_and_original_retained(self):
        self.create()
        record = self.queue.all()[0]
        path = self.queue.file_for(record)
        path.write_bytes(b"tampered")
        self.queue.process_once(lambda *_: "should-not-send")
        self.assertEqual(self.queue.all()[0]["status"], "failed")
        self.assertTrue(self.pdf.exists())

    def test_low_free_disk_refuses_spool_without_losing_original(self):
        from types import SimpleNamespace
        with patch("itomiscan.storage.queue.shutil.disk_usage",
                   return_value=SimpleNamespace(free=64 * 1024 * 1024)):
            with self.assertRaisesRegex(QueueError, "genug freier Platz"):
                self.create("usb")
        self.assertTrue(self.pdf.is_file())
        self.assertEqual(self.queue.all(), [])

    def test_directory_and_oversized_source_refused(self):
        with self.assertRaises(QueueError):
            self.queue.enqueue(Path(self.dir.name), self.targets["usb"])
        with self.assertRaises(QueueError):
            self.queue.enqueue(self.pdf.with_suffix(".png"), self.targets["usb"])

    def test_usb_delivery_atomic_and_idempotent(self):
        ident = self.create()
        job = self.queue.all()[0]
        root = Path(self.dir.name) / "media"
        volume = root / "SCANUSB"
        volume.mkdir(parents=True)
        src = self.queue.file_for(job)
        send = lambda: deliver_usb(job, src, mounts=[root],
                                   is_mount=lambda p: p == volume)
        self.assertEqual(send(), "Gesichert")
        self.assertEqual(send(), "Bereits vorhanden und identisch")
        copy = volume / "Scans" / job["filename"]
        self.assertEqual(copy.read_bytes(), src.read_bytes())
        self.assertFalse(list(copy.parent.glob("*.part")))

    def test_usb_missing_device_is_retryable(self):
        self.create()
        job = self.queue.all()[0]
        with self.assertRaises(DeliveryError) as error:
            deliver_usb(job, self.queue.file_for(job), mounts=[], is_mount=lambda _: False)
        self.assertFalse(error.exception.permanent)
        self.assertFalse(error.exception.uncertain)

    def test_http_token_and_smtp_password_not_in_config_backup(self):
        ident = self.targets["paperless"]
        secrets = SecretStore(self.path)
        secrets.update(ident, token="test-secret-token")
        self.assertEqual(secrets.get(ident)["token"], "test-secret-token")
        self.assertEqual(secrets.path.stat().st_mode & 0o777, 0o600)
        self.assertNotIn("test-secret-token", str(self.db.backup()))
        secrets.update(ident, clear=True)
        self.assertEqual(secrets.get(ident), {})

    def test_paperless_upload_stream_and_task_receipt(self):
        from unittest.mock import MagicMock
        self.create("paperless")
        job = self.queue.all()[0]
        connection = MagicMock()
        response = MagicMock()
        response.status = 200
        response.read.return_value = b'"b337f63e-9057-4dab-9bf3-1f5f83fac700"'
        connection.getresponse.return_value = response
        with patch("itomiscan.integrations.delivery.http.client.HTTPSConnection",
                   return_value=connection) as opener:
            result = deliver_paperless(job, self.queue.file_for(job),
                                       {"token":"dummy-token"})
        self.assertIn("Task", result)
        connection.putrequest.assert_called_once()
        self.assertEqual(connection.putrequest.call_args[0][0], "POST")
        self.assertEqual(connection.putrequest.call_args[0][1],
                         "/api/documents/post_document/")
        sent = b"".join(call.args[0] for call in connection.send.call_args_list)
        self.assertIn(b'Content-Disposition: form-data; name="document"', sent)
        self.assertIn(b"%PDF-1.4", sent)
        self.assertIn(b"%%EOF", sent)

    def test_paperless_disconnect_after_body_requires_review(self):
        from unittest.mock import MagicMock
        self.create("paperless")
        job = self.queue.all()[0]
        connection = MagicMock()
        connection.getresponse.side_effect = ConnectionResetError("closed")
        with patch("itomiscan.integrations.delivery.http.client.HTTPSConnection",
                   return_value=connection):
            with self.assertRaises(DeliveryError) as exc:
                deliver_paperless(job, self.queue.file_for(job), {"token":"dummy"})
        self.assertTrue(exc.exception.uncertain)

    def test_paperless_requires_encrypted_token(self):
        self.create("paperless")
        job = self.queue.all()[0]
        job["target_address"] = "http://example.org"
        with self.assertRaises(DeliveryError) as ctx:
            deliver_paperless(job, self.queue.file_for(self.queue.all()[0]),
                              {"token":"test"})
        self.assertTrue(ctx.exception.permanent)

    def test_missing_smbclient_fails_actionably(self):
        self.create("network")
        job = self.queue.all()[0]
        with patch("itomiscan.integrations.delivery.shutil.which", return_value=None):
            with self.assertRaisesRegex(DeliveryError, "smbclient"):
                deliver_smb(job, self.queue.file_for(job), {})

    def test_worker_dispatches_correct_kind(self):
        self.create("usb")
        job = self.queue.all()[0]
        secret = SecretStore(self.path)
        with patch("itomiscan.integrations.delivery.deliver_usb", return_value="ok") as mock:
            self.assertEqual(deliver(job, self.queue.file_for(job), secret), "ok")
            mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
