"""CUPS jobs and printer management: isolated subprocess mocks, no real printing."""
import subprocess
import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from itomiscan.integrations.delivery import DeliveryError, deliver
from itomiscan.integrations.printing import (
    PrintError, deliver_print, install_queue, list_queues, printer_uri,
    queue_name, submit_pdf, test_page, uninstall_queue, validate_copy_options,
    address_from_host, default_printer,
)
from itomiscan.storage.config import ConfigStore
from itomiscan.storage.queue import DeliveryQueue, QueueError
from itomiscan.storage.secrets import SecretStore


class CUPSIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = ConfigStore(self.root / "config" / "itomiscan.db")
        self.db.save_target({
            "kind": "printer", "name": "OfficeLaser",
            "address": "ipps://printer.lan/ipp/print"})
        self.target_id = next(
            x["id"] for x in self.db.list_targets() if x["kind"] == "printer")
        self.queue = DeliveryQueue(self.db.path)
        self.pdf = self.root / "original.pdf"
        self.pdf.write_bytes(b"%PDF-1.4\n" + b"sample" * 100 + b"\n%%EOF")

    def test_validate_copy_parameters(self):
        self.assertEqual(validate_copy_options(3, "two-sided-long-edge"),
                         (3, "two-sided-long-edge"))
        for copies in (0, -1, 21, True, "2", 100000):
            with self.subTest(copies=copies):
                with self.assertRaises(PrintError):
                    validate_copy_options(copies)
        with self.assertRaises(PrintError):
            validate_copy_options(1, "unlimited")
        for name in ("../evil", "-drop", "has spaces", "X;shutdown"):
            with self.subTest(name=name):
                with self.assertRaises(PrintError):
                    queue_name(name)
        for uri in ("http://printer.lan", "ipp://user:pw@host/printers/lp",
                    "file:///etc/passwd", "ipps://host/print?param=1"):
            with self.subTest(uri=uri):
                with self.assertRaises(PrintError):
                    printer_uri(uri)

    def test_config_rejects_unsafe_printers(self):
        for name, address in (
            ("Printer with spaces", "ipp://host/ipp/print"),
            ("TrustedPrinter", "http://host/ipp/print"),
            ("-unsafe", "ipp://host/ipp/print"),
        ):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    self.db.save_target({"kind": "printer",
                                         "name": name, "address": address})

    def test_non_ipp_raw_provisioning_requires_driver(self):
        for uri in ("socket://printer.lan:9100", "lpd://printer.lan/queue",
                    "usb://printer.lan/device"):
            with self.subTest(uri=uri):
                with self.assertRaises(PrintError):
                    install_queue("OfficeLaser", uri)

    @patch("itomiscan.integrations.printing.accepting_jobs", return_value=False)
    @patch("itomiscan.integrations.printing.is_configured", return_value=True)
    def test_submit_rejects_queue_not_accepting_jobs(self, _configured, _accepting):
        with self.assertRaises(PrintError):
            submit_pdf("OfficeLaser", self.pdf)

    @patch("itomiscan.integrations.printing.shutil.which", return_value="/usr/bin/fake")
    @patch("itomiscan.integrations.printing.subprocess.run")
    def test_install_and_uninstall_queue_no_shell(self, runner, _which):
        runner.side_effect = [
            Mock(returncode=0, stdout="", stderr=""),
            Mock(returncode=0, stdout="device for OfficeLaser: ipps://printer.lan/ipp/print\n", stderr=""),
            Mock(returncode=0, stdout="device for OfficeLaser: ipps://printer.lan/ipp/print\n", stderr=""),
            Mock(returncode=0, stdout="", stderr=""),
        ]
        self.assertEqual(install_queue("OfficeLaser", "ipps://printer.lan/ipp/print"),
                         "OfficeLaser")
        self.assertEqual(uninstall_queue("OfficeLaser"), "OfficeLaser")
        commands = [call.args[0] for call in runner.call_args_list]
        self.assertEqual(commands[0],
                         ["lpadmin", "-p", "OfficeLaser", "-E", "-v",
                          "ipps://printer.lan/ipp/print", "-m", "everywhere"])
        self.assertEqual(commands[-1],
                         ["lpadmin", "-x", "OfficeLaser"])
        self.assertTrue(all(isinstance(cmd, list) for cmd in commands))

    @patch("itomiscan.integrations.printing.accepting_jobs", return_value=True)
    @patch("itomiscan.integrations.printing.shutil.which", return_value="/usr/bin/fake")
    @patch("itomiscan.integrations.printing.subprocess.run")
    def test_lp_receives_validated_number_and_duplex(self, runner, _which, _accepting):
        runner.side_effect = [
            Mock(returncode=0, stdout="device for OfficeLaser: ipps://printer.lan/ipp/print\n", stderr=""),
            Mock(returncode=0,
                 stdout="request id is OfficeLaser-91 (1 file(s))", stderr=""),
        ]
        result = submit_pdf("OfficeLaser", self.pdf, copies=4,
                            sides="two-sided-short-edge")
        self.assertIn("OfficeLaser-91", result)
        command = runner.call_args_list[1].args[0]
        self.assertEqual(command[:8],
                         ["lp", "-d", "OfficeLaser", "-n", "4",
                          "-o", "sides=two-sided-short-edge", str(self.pdf)])
        self.assertTrue(all("shell" not in call.kwargs or
                            not call.kwargs["shell"] for call in runner.call_args_list))

    @patch("itomiscan.integrations.printing.accepting_jobs", return_value=True)
    @patch("itomiscan.integrations.printing.shutil.which", return_value="/usr/bin/fake")
    @patch("itomiscan.integrations.printing.subprocess.run")
    def test_print_disconnect_is_uncertain_and_never_auto_replayed(self, runner, _which, _accepting):
        runner.side_effect = [
            Mock(returncode=0, stdout="device for OfficeLaser: ipps://printer.lan/ipp/print\n", stderr=""),
            subprocess.TimeoutExpired(["lp"], 30),
        ]
        ident = self.queue.enqueue(self.pdf, self.target_id, copies=2,
                                   sides="two-sided-long-edge")
        self.assertEqual(self.queue.all()[0]["print_copies"], 2)
        self.assertEqual(self.queue.all()[0]["print_sides"],
                         "two-sided-long-edge")
        self.queue.process_once(
            lambda job, pdf: deliver(job, pdf, SecretStore(self.db.path)))
        job = self.queue.all()[0]
        self.assertEqual(job["status"], "review")
        self.assertTrue(self.queue.file_for(job).exists())
        with self.assertRaises(QueueError):
            self.queue.retry(ident)

    def test_interrupted_cups_job_requires_manual_review(self):
        job_id = self.queue.enqueue(self.pdf, self.target_id, copies=2)
        with self.queue.db._connection(write=True) as con:
            con.execute(
                "UPDATE delivery_jobs SET status='sending',leased_until=1 WHERE id=?",
                (job_id,))
        self.queue.recover()
        self.assertEqual(self.queue.all()[0]["status"], "review")
        self.assertIsNone(self.queue.claim())

    def test_legacy_block6_queue_schema_online_upgrade(self):
        # Recreate a Block-6 table without print settings, then migrate
        # through DeliveryQueue while retaining the original row data.
        with self.db._connection(write=True) as con:
            con.execute("DROP TABLE IF EXISTS delivery_jobs")
            con.execute("""CREATE TABLE delivery_jobs (
                id TEXT PRIMARY KEY,target_id INTEGER,kind TEXT,
                target_name TEXT,target_address TEXT,filename TEXT,
                digest TEXT,size_bytes INTEGER,created_at REAL,
                status TEXT,attempts INTEGER,retry_at REAL,leased_until REAL,
                last_error TEXT,receipt TEXT
            )""")
            con.execute("""INSERT INTO delivery_jobs VALUES (
                'oldjob',1,'paperless','Test','https://example.org',
                'oldjob.pdf','sum',99,1,'done',1,1,0,'','accepted'
            )""")
        upgraded = DeliveryQueue(self.db.path)
        old = upgraded.all()[0]
        self.assertEqual(old["id"], "oldjob")
        self.assertEqual(old["status"], "done")
        self.assertEqual(old["print_copies"], 1)
        self.assertEqual(old["print_sides"], "one-sided")

    def test_missing_queue_cannot_create_job_submission(self):
        with patch("itomiscan.integrations.printing.list_queues", return_value=[]):
            with self.assertRaises(PrintError):
                submit_pdf("OfficeLaser", self.pdf)

    @patch("itomiscan.integrations.printing.shutil.which", return_value="/usr/bin/fake")
    @patch("itomiscan.integrations.printing.subprocess.run")
    def test_text_only_print_test_page(self, runner, _which):
        runner.side_effect = [
            Mock(returncode=0, stdout="device for OfficeLaser: ipps://printer.lan/ipp/print\n", stderr=""),
            Mock(returncode=0, stdout="request id is OfficeLaser-10", stderr=""),
        ]
        self.assertIn("CUPS angenommen", test_page("OfficeLaser"))
        text = runner.call_args_list[1].kwargs["input"]
        self.assertIn("ItomiScan", text)


    def test_manual_printer_address_builder(self):
        self.assertEqual(address_from_host("ipps", "192.168.1.20"),
                         "ipps://192.168.1.20/ipp/print")
        self.assertEqual(address_from_host("socket", "laser.lan"),
                         "socket://laser.lan:9100")
        self.assertEqual(address_from_host("lpd", "laser.lan"),
                         "lpd://laser.lan/queue")
        for protocol, host in (("file", "laser.lan"), ("ipp", "x/../../"),
                               ("socket", "bad@host"), ("ipp", "-bad")):
            with self.subTest(protocol=protocol, host=host):
                with self.assertRaises(PrintError):
                    address_from_host(protocol, host)

    def test_printer_address_edit_keeps_existing_target_id(self):
        self.db.update_target_address(self.target_id, "ipp://printer.lan/ipp/print")
        rows = [x for x in self.db.list_targets() if x["kind"] == "printer"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], self.target_id)
        self.assertEqual(rows[0]["address"], "ipp://printer.lan/ipp/print")
        with self.assertRaises(Exception):
            self.db.update_target_address(self.target_id, "file:///tmp/unsafe")

    @patch("itomiscan.integrations.printing.run_cups")
    def test_default_printer_reads_only_installed_queue(self, run):
        run.side_effect = ["system default destination: OfficeLaser"]
        with patch("itomiscan.integrations.printing.list_queues", return_value=["OfficeLaser", "OtherPrinter"]):
            self.assertEqual(default_printer(), "OfficeLaser")


if __name__ == "__main__":
    unittest.main()
