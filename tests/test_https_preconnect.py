"""A speculative browser connection must not block the HTTPS accept loop."""
import http.client
from pathlib import Path
import shutil
import socket
import ssl
import subprocess
import tempfile
import threading
import unittest

from itomiscan.storage.config import ConfigStore
from itomiscan.web.server import build_server


@unittest.skipUnless(shutil.which("openssl"), "openssl required for temporary test certificate")
class HTTPSPreconnectTests(unittest.TestCase):
    def test_idle_preconnection_does_not_block_verified_https_requests(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            cert, key = directory / "cert.pem", directory / "key.pem"
            subprocess.run([
                "openssl", "req", "-x509", "-newkey", "ec",
                "-pkeyopt", "ec_paramgen_curve:P-256", "-nodes",
                "-keyout", str(key), "-out", str(cert), "-days", "1",
                "-subj", "/CN=127.0.0.1", "-addext", "subjectAltName=IP:127.0.0.1",
            ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
            db = directory / "test.db"
            ConfigStore(db).set_password("TemporaryHTTPSRegressionPassword_2026!")
            server = build_server("127.0.0.1", 0, cert=cert, key=key, db_path=db)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            idle = socket.create_connection(server.server_address, timeout=3)
            try:
                # No ClientHello is sent on idle. The old listening SSLSocket
                # performed its handshake in accept(), blocking other clients.
                context = ssl.create_default_context(cafile=str(cert))
                for _ in range(3):
                    client = http.client.HTTPSConnection(
                        "127.0.0.1", server.server_port, context=context, timeout=3)
                    try:
                        client.request("GET", "/login")
                        response = client.getresponse()
                        self.assertEqual(response.status, 200)
                        self.assertIn(b"<form", response.read())
                    finally:
                        client.close()
            finally:
                idle.close()
                server.shutdown()
                server.server_close()
                thread.join(3)


if __name__ == "__main__":
    unittest.main()
