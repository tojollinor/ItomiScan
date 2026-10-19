"""Security and UI contracts of the noVNC integration."""
import unittest
from itomiscan.web import pages, remote_pages
from itomiscan.web.vnc_bridge import _receive_frame, _send_frame, MAX_WS_MESSAGE
import socket
import struct


class VNCTests(unittest.TestCase):
    def test_vnc_page_includes_protected_websocket_view(self):
        html = remote_pages.remote_page([], "", None, "csrf", live=True, vnc_password="abc123")
        self.assertIn('id="remote-vnc-screen"', html)
        self.assertIn('data-password="abc123"', html)
        self.assertIn('/assets/vnc.js', html)
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
            left.sendall(b"\\x82\\x01x")
            with self.assertRaises(ValueError):
                _receive_frame(right)
        finally:
            left.close()
            right.close()

    def test_server_frames_not_masked(self):
        left, right = socket.socketpair()
        try:
            _send_frame(left, b"RFB")
            self.assertEqual(right.recv(5), b"\\x82\\x03RFB")
        finally:
            left.close()
            right.close()


if __name__ == "__main__":
    unittest.main()
