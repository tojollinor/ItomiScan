"""Block 5: offline VNC WebSocket integration and security tests.

A loopback HTTP socket is temporarily marked secure ONLY to exercise the WSS
upgrade handler's authentication and bytes. It does not claim to test TLS
certificates or the actual x11vnc process on the N1800.
"""
import base64
import http.client
import os
import re
import socket
import struct
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.parse import urlencode

from itomiscan.storage.config import ConfigStore
from itomiscan.storage.remote_live import viewer_id
from itomiscan.web.server import build_server
from itomiscan.web import vnc_bridge
from itomiscan.web.vnc_bridge import (
    VNCBridge, VNCUnavailable, _receive_frame, MAX_WS_MESSAGE
)


def recv_exact(sock, count):
    result = bytearray()
    while len(result) < count:
        data = sock.recv(count - len(result))
        if not data:
            raise ConnectionError("socket closed before requested bytes")
        result.extend(data)
    return bytes(result)


def masked_frame(payload, opcode=2, final=True):
    mask = b"\x10\x20\x30\x40"
    first = (0x80 if final else 0) | opcode
    length = len(payload)
    if length < 126:
        prefix = bytes((first, 0x80 | length))
    elif length < 65536:
        prefix = bytes((first, 0xfe)) + struct.pack("!H", length)
    else:
        prefix = bytes((first, 0xff)) + struct.pack("!Q", length)
    return prefix + mask + bytes(value ^ mask[i % 4] for i, value in enumerate(payload))


class WebSocketIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        db = Path(self.temp.name) / "scan.db"
        ConfigStore(db).set_password("AnotherStrongTestPassword_2026!")
        self.server = build_server("127.0.0.1", 0, db_path=db)
        # Simulate the handler's secure branch without generating a certificate.
        # Never bind to a LAN address or claim this exercises TLS negotiation.
        self.server.secure = True
        self.port = self.server.server_port
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.thread.join, 3)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.cookie = ""

    def authenticate(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=4)
        body = urlencode({"password": "AnotherStrongTestPassword_2026!"})
        conn.request("POST", "/login", body, {
            "Host": "127.0.0.1:%s" % self.port,
            "Content-Type": "application/x-www-form-urlencoded",
        })
        resp = conn.getresponse()
        self.assertEqual(resp.status, 303)
        self.cookie = resp.getheader("Set-Cookie").split(";", 1)[0]
        resp.read()
        conn.close()
        return viewer_id(self.cookie.split("=", 1)[1])

    def upgrade(self, origin=None, *, protocol="binary", extensions=None, cookie=None):
        request = [
            "GET /remote/vnc/ws HTTP/1.1",
            "Host: 127.0.0.1:%s" % self.port,
            "Upgrade: websocket",
            "Connection: keep-alive, Upgrade",
            "Sec-WebSocket-Key: " + base64.b64encode(b"0123456789abcdef").decode(),
            "Sec-WebSocket-Version: 13",
            "Origin: " + (origin if origin is not None
                          else "https://127.0.0.1:%s" % self.port),
        ]
        if protocol is not None:
            request.append("Sec-WebSocket-Protocol: " + protocol)
        if extensions is not None:
            request.append("Sec-WebSocket-Extensions: " + extensions)
        if cookie:
            request.append("Cookie: " + cookie)
        sock = socket.create_connection(("127.0.0.1", self.port), timeout=4)
        sock.settimeout(4)
        sock.sendall(("\r\n".join(request) + "\r\n\r\n").encode("ascii"))
        response = bytearray()
        while b"\r\n\r\n" not in response and len(response) < 8192:
            response.extend(sock.recv(1))
        return sock, response.decode("latin1")

    def test_websocket_cannot_open_without_session(self):
        sock, response = self.upgrade()
        try:
            self.assertIn("403", response.split("\r\n", 1)[0])
        finally:
            sock.close()

    def test_websocket_rejects_other_origin_and_unknown_subprotocol(self):
        owner = self.authenticate()
        self.server.remote_live.start(owner)
        backend = Mock()
        self.server.vnc.connect = backend
        sock, response = self.upgrade(origin="https://evil.example",
                                      cookie=self.cookie)
        try:
            self.assertIn("403", response.split("\r\n", 1)[0])
        finally:
            sock.close()
        sock, response = self.upgrade(protocol="unexpected", cookie=self.cookie)
        try:
            self.assertIn("400", response.split("\r\n", 1)[0])
        finally:
            sock.close()
        backend.assert_not_called()

    def test_secure_policy_permits_only_own_wss_endpoint(self):
        owner = self.authenticate()
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=4)
        conn.request("GET", "/", headers={
            "Host": "127.0.0.1:%s" % self.port, "Cookie": self.cookie})
        resp = conn.getresponse()
        self.assertEqual(resp.status, 200)
        policy = resp.getheader("Content-Security-Policy")
        self.assertIn("connect-src 'self' wss://127.0.0.1:%s" % self.port, policy)
        self.assertNotIn("wss://*", policy)
        resp.read()
        conn.close()

    def test_authenticated_binary_vnc_stream_is_bidirectional(self):
        owner = self.authenticate()
        self.server.remote_live.start(owner)
        left, right = socket.socketpair()
        self.addCleanup(left.close)
        self.addCleanup(right.close)
        right.settimeout(4)
        self.server.vnc.connect = Mock(return_value=left)
        sock, response = self.upgrade(cookie=self.cookie)
        try:
            self.assertIn("101", response.split("\r\n", 1)[0])
            self.assertIn("Sec-WebSocket-Protocol: binary", response)
            sock.sendall(masked_frame(b"RFB-client"))
            self.assertEqual(recv_exact(right, len(b"RFB-client")), b"RFB-client")
            right.sendall(b"RFB-server")
            header = recv_exact(sock, 2)
            self.assertEqual(header, b"\x82\x0a")
            self.assertEqual(recv_exact(sock, 10), b"RFB-server")
            sock.sendall(masked_frame(b"\x01\x02", final=False))
            sock.sendall(masked_frame(b"\x03\x04", opcode=0))
            self.assertEqual(recv_exact(right, 4), b"\x01\x02\x03\x04")
            self.server.vnc.connect.assert_called_once_with(owner)
        finally:
            sock.close()

    def test_edge_websocket_without_subprotocol_accepts_extension_offer(self):
        """Edge may offer compression but no binary subprotocol."""
        owner = self.authenticate()
        self.server.remote_live.start(owner)
        left, right = socket.socketpair()
        self.addCleanup(left.close)
        self.addCleanup(right.close)
        right.settimeout(4)
        self.server.vnc.connect = Mock(return_value=left)
        sock, response = self.upgrade(
            protocol=None, extensions="permessage-deflate; client_max_window_bits",
            cookie=self.cookie)
        try:
            self.assertIn("101", response.split("\r\n", 1)[0])
            self.assertNotIn("Sec-WebSocket-Extensions:", response)
            self.assertNotIn("Sec-WebSocket-Protocol:", response)
            sock.sendall(masked_frame(b"Edge-RFB"))
            self.assertEqual(recv_exact(right, 8), b"Edge-RFB")
            right.sendall(b"RFB-ok")
            self.assertEqual(recv_exact(sock, 2), b"\x82\x06")
            self.assertEqual(recv_exact(sock, 6), b"RFB-ok")
        finally:
            sock.close()

    def test_full_framebuffer_and_incremental_update_cross_proxy_unchanged(self):
        owner = self.authenticate()
        self.server.remote_live.start(owner)
        left, right = socket.socketpair()
        self.addCleanup(left.close)
        self.addCleanup(right.close)
        right.settimeout(10)
        self.server.vnc.connect = Mock(return_value=left)
        sock, response = self.upgrade(cookie=self.cookie)
        sock.settimeout(10)
        try:
            self.assertIn("101", response.split("\r\n", 1)[0])
            # A real 1024x768 RAW rectangle exceeds one WebSocket frame and
            # deliberately crosses the proxy's 32768-byte recv boundaries.
            pixels = bytes((20, 12, 6, 0)) * (1024 * 768)
            full = struct.pack("!BBHHHHHi", 0, 0, 1, 0, 0, 1024, 768, 0) + pixels
            update = struct.pack("!BBHHHHHi", 0, 0, 1, 12, 18, 1, 1, 0) + b"\xff\x00\x00\x00"
            stream = full + update
            sender = threading.Thread(target=right.sendall, args=(stream,), daemon=True)
            sender.start()
            received = bytearray()
            while len(received) < len(stream):
                header = recv_exact(sock, 2)
                self.assertEqual(header[0], 0x82)
                length = header[1]
                self.assertLess(length, 128)
                if length == 126:
                    length = struct.unpack("!H", recv_exact(sock, 2))[0]
                elif length == 127:
                    length = struct.unpack("!Q", recv_exact(sock, 8))[0]
                received.extend(recv_exact(sock, length))
            sender.join(5)
            self.assertFalse(sender.is_alive())
            self.assertEqual(received, stream)
            # Pointer, key-down and key-up bytes remain unchanged upstream.
            inputs = struct.pack("!BBHH", 5, 1, 512, 384) + struct.pack("!BBHI", 4, 1, 0, 0xff0d) + struct.pack("!BBHI", 4, 0, 0, 0xff0d)
            sock.sendall(masked_frame(inputs))
            self.assertEqual(recv_exact(right, len(inputs)), inputs)
        finally:
            sock.close()

    def test_slow_partial_client_frame_is_not_discarded(self):
        owner = self.authenticate()
        self.server.remote_live.start(owner)
        left, right = socket.socketpair()
        self.addCleanup(left.close)
        self.addCleanup(right.close)
        right.settimeout(5)
        self.server.vnc.connect = Mock(return_value=left)
        sock, response = self.upgrade(cookie=self.cookie)
        try:
            self.assertIn("101", response.split("\r\n", 1)[0])
            packet = masked_frame(b"RFB 003.008\n")
            sock.sendall(packet[:1])
            time.sleep(2.2)  # Cross the production socket timeout mid-header.
            sock.sendall(packet[1:])
            self.assertEqual(recv_exact(right, 12), b"RFB 003.008\n")
        finally:
            sock.close()

    def test_expired_lease_closes_both_streams(self):
        owner = self.authenticate()
        self.server.remote_live.start(owner)
        left, right = socket.socketpair()
        self.addCleanup(left.close)
        self.addCleanup(right.close)
        right.settimeout(5)
        self.server.vnc.connect = Mock(return_value=left)
        sock, response = self.upgrade(cookie=self.cookie)
        try:
            self.assertIn("101", response.split("\r\n", 1)[0])
            with self.server.remote_live._db() as db:
                db.execute("UPDATE remote_live SET until_time=0")
            self.assertEqual(right.recv(1), b"")
            self.assertEqual(sock.recv(1), b"")
        finally:
            sock.close()

    def test_unmasked_or_oversized_websocket_data_rejected(self):
        left, right = socket.socketpair()
        try:
            left.sendall(b"\x82\x01Z")
            with self.assertRaises(ValueError):
                _receive_frame(right)
        finally:
            left.close()
            right.close()
        left, right = socket.socketpair()
        try:
            left.sendall(b"\xff\xff" + struct.pack("!Q", MAX_WS_MESSAGE + 1))
            with self.assertRaises(ValueError):
                _receive_frame(right)
        finally:
            left.close()
            right.close()


class VNCProcessTests(unittest.TestCase):
    def bridge(self, live):
        # Do not spawn the perpetual watcher in an isolated process unit test.
        bridge = VNCBridge.__new__(VNCBridge)
        bridge.live = live
        bridge._lock = threading.RLock()
        bridge._process = None
        bridge._owner = None
        bridge._password = None
        bridge._private = None
        bridge._port = None
        return bridge

    def test_on_demand_process_is_localhost_only_and_reused_per_owner(self):
        owner = "a" * 64
        live = Mock()
        live.active.return_value = True
        live.authorized.return_value = True
        bridge = self.bridge(live)
        proc = Mock()
        proc.poll.return_value = None
        with patch.object(bridge, "ready", return_value=True), \
             patch.object(vnc_bridge.shutil, "which", return_value="/usr/bin/x11vnc"), \
             patch.object(vnc_bridge.subprocess, "Popen", return_value=proc) as created, \
             patch.object(vnc_bridge.time, "sleep"):
            password = bridge.start(owner)
            self.assertTrue(password)
            command = created.call_args.args[0]
            self.assertIn("-localhost", command)
            self.assertIn("-once", command)
            self.assertIn("-nevershared", command)
            self.assertIn("-passwdfile", command)
            self.assertEqual(command[command.index("-display") + 1], ":0")
            self.assertEqual(command[command.index("-rfbport") + 1],
                             str(bridge._port))
            passwd = Path(command[command.index("-passwdfile") + 1])
            self.assertEqual(passwd.stat().st_mode & 0o777, 0o600)
            self.assertEqual(bridge.start(owner), password)
            self.assertEqual(created.call_count, 1)
            with self.assertRaises(VNCUnavailable):
                bridge.start("b" * 64)
            bridge.stop(owner)
            proc.terminate.assert_called_once()
            self.assertFalse(passwd.exists())

    def test_unavailable_vnc_package_does_not_launch(self):
        bridge = self.bridge(Mock())
        with patch.object(bridge, "ready", return_value=False), \
             patch.object(vnc_bridge.subprocess, "Popen") as proc:
            with self.assertRaises(VNCUnavailable):
                bridge.start("a" * 64)
            proc.assert_not_called()


if __name__ == "__main__":
    unittest.main()
