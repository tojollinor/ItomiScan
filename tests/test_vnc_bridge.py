"""Security and UI contracts of the noVNC integration."""
import unittest
from itomiscan.web import pages, remote_pages
from itomiscan.web.vnc_bridge import _receive_frame, _send_frame, MAX_WS_MESSAGE
import socket
import struct
from unittest.mock import Mock


class VNCTests(unittest.TestCase):
    def test_partial_frame_survives_timeouts_in_header_mask_and_payload(self):
        connection = Mock()
        connection.recv.side_effect = [
            b"\x82", socket.timeout(), b"\x83",
            b"\x10", socket.timeout(), b"\x20\x30\x40",
            b"\x51", socket.timeout(), b"\x62\x73",
        ]
        active = Mock(return_value=True)
        self.assertEqual(_receive_frame(connection, active=active), (True, 2, b"ABC"))
        self.assertEqual(active.call_count, 3)

    def test_timeout_does_not_keep_expired_session_alive(self):
        connection = Mock()
        connection.recv.side_effect = [b"\x82", socket.timeout()]
        with self.assertRaises(ConnectionError):
            _receive_frame(connection, active=lambda: False)

    def test_vnc_page_includes_protected_websocket_view(self):
        html = remote_pages.remote_page([], "", None, "csrf", live=True, vnc_password="abc123")
        self.assertIn('id="remote-vnc-screen"', html)
        self.assertIn('data-password="abc123"', html)
        self.assertIn('/assets/vnc.js', html)
        self.assertIn('id="remote-text"', html)
        self.assertIn('data-remote-key="Return"', html)
        self.assertIn('rfb.sendKey', pages.VNC_JS)
        self.assertNotIn('/assets/remote.js', html)

    def test_vnc_page_escape(self):
        html = remote_pages.remote_page([], "", None, "csrf", live=True, vnc_password='"><script>')
        self.assertNotIn('data-password=""><script>', html)

    def test_client_uses_same_origin_wss(self):
        self.assertIn("'/remote/vnc/ws'", pages.VNC_JS)
        self.assertIn("'wss:'", pages.VNC_JS)
        self.assertIn("'/remote/live/ping'", pages.VNC_JS)

    def test_reject_unmasked_websocket_frame(self):
        left, right = socket.socketpair()
        try:
            left.sendall(b"\x82\x01x")
            with self.assertRaises(ValueError):
                _receive_frame(right)
        finally:
            left.close()
            right.close()

    def test_server_frames_not_masked(self):
        left, right = socket.socketpair()
        try:
            _send_frame(left, b"RFB")
            self.assertEqual(right.recv(5), b"\x82\x03RFB")
        finally:
            left.close()
            right.close()


if __name__ == "__main__":
    unittest.main()
