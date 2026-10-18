"""Device identity grouping and CUPS auto-discovery regression checks."""
import struct
import subprocess
import unittest
from unittest.mock import Mock, patch
from itomiscan.integrations.printer_identity import (
    discover_verified_printers, parse_ipp, browse_endpoints)
from itomiscan.integrations.printing import list_queues


def endpoint(uri, ip, scheme="ipp"):
    return {"uri": uri, "ip": ip, "scheme": scheme, "port":631,
            "path":"/ipp/print", "name":"Brother HL-3152CDW"}


class PrinterIdentityTests(unittest.TestCase):
    def test_same_uuid_groups_across_services_but_prefers_ipps(self):
        a = endpoint("ipp://10.0.0.25:631/ipp/print", "10.0.0.25")
        b = endpoint("ipps://10.0.0.25:443/ipp/print", "10.0.0.25", "ipps")
        device_id = "urn:uuid:11111111-2222-3333-4444-555555555555"
        rows, unknown = discover_verified_printers(
            browse=lambda:[a,b],
            query=lambda _: {"printer-uuid":device_id,
                             "printer-make-and-model":"Brother HL-3152CDW"})
        self.assertEqual(unknown, 0)
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["uri"].startswith("ipps://"))

    def test_two_identical_models_are_separate(self):
        xs = [endpoint("ipp://10.0.0.25:631/ipp/print","10.0.0.25"),
              endpoint("ipp://10.0.0.26:631/ipp/print","10.0.0.26")]
        def query(x):
            suffix = "555555555525" if x["ip"].endswith("25") else "555555555526"
            return {"printer-uuid":"urn:uuid:11111111-2222-3333-4444-"+suffix,
                    "printer-make-and-model":"Brother HL-3152CDW"}
        rows, unknown = discover_verified_printers(browse=lambda:xs,query=query)
        self.assertEqual(len(rows), 2)
        self.assertEqual(unknown, 0)

    def test_no_uuid_not_selectable(self):
        xs = [endpoint("ipp://10.0.0.25:631/ipp/print","10.0.0.25")]
        rows, missing = discover_verified_printers(
            browse=lambda:xs,query=lambda _:{"printer-make-and-model":"Brother"})
        self.assertEqual(rows, [])
        self.assertEqual(missing, 1)

    @patch("itomiscan.integrations.printing.shutil.which",return_value="/usr/bin/lpstat")
    @patch("itomiscan.integrations.printing.subprocess.run")
    def test_autodiscovered_cups_is_not_installed(self, run, _):
        run.return_value = Mock(returncode=1,stdout="",
                                stderr="lpstat: No destinations added.")
        self.assertEqual(list_queues(), [])
        self.assertEqual(run.call_args.args[0], ["lpstat","-v"])
        run.return_value = Mock(returncode=0,
           stdout="device for Office: ipp://10.0.0.25/ipp/print\n",stderr="")
        self.assertEqual(list_queues(), ["Office"])

    def test_device_identity_survives_backup_restore(self):
        import tempfile
        from pathlib import Path
        from itomiscan.storage.config import ConfigStore
        with tempfile.TemporaryDirectory() as directory:
            store=ConfigStore(Path(directory)/'itomiscan.db')
            store.save_target({'kind':'printer','name':'Office','address':'ipp://10.0.0.25/ipp/print'})
            ident=next(x['id'] for x in store.list_targets() if x['name']=='Office')
            uuid='11111111-2222-3333-4444-555555555555'
            store.assign_printer_identity(ident,uuid,'Brother HL-3152CDW')
            backup=store.backup()
            self.assertEqual(backup['printer_identities']['Office']['identity'],uuid)
            store.restore(backup)
            self.assertIn(uuid,[x['identity'] for x in store.printer_identities().values()])

    def test_ipp_parser_extracts_uuid(self):
        name=b"printer-uuid"
        value=b"urn:uuid:11111111-2222-3333-4444-555555555555"
        raw=(b"\x02\x00\x00\x00\x00\x00\x00\x01\x04" +
             b"\x45"+struct.pack(">H",len(name))+name+
             struct.pack(">H",len(value))+value+b"\x03")
        self.assertEqual(parse_ipp(raw)["printer-uuid"], value.decode())


if __name__ == "__main__":
    unittest.main()
