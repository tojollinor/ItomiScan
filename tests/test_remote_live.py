"""Session/lease and remote input tests, with no X server dependency."""
import tempfile
import unittest
from pathlib import Path

from itomiscan.storage.remote_live import RemoteLive, viewer_id


class RemoteLiveTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.now = [100.]
        self.live = RemoteLive(Path(self.dir.name) / "itomi.db",
                               clock=lambda: self.now[0])
        self.first = viewer_id("first-browser")
        self.other = viewer_id("second-browser")

    def test_exclusive_lease_and_short_expiration(self):
        self.assertFalse(self.live.active())
        self.live.start(self.first)
        self.assertTrue(self.live.authorized(self.first))
        self.assertFalse(self.live.authorized(self.other))
        with self.assertRaises(ValueError):
            self.live.start(self.other)
        self.now[0] += 20
        self.live.ping(self.first)
        self.now[0] += 20
        self.assertTrue(self.live.authorized(self.first))
        self.now[0] += 26
        self.assertFalse(self.live.authorized(self.first))
        self.live.start(self.other)
        self.assertTrue(self.live.authorized(self.other))

    def test_input_whitelist_queue_and_expiration(self):
        self.live.start(self.first)
        self.live.enqueue(self.first, "click", x=0, y=1000)
        self.live.enqueue(self.first, "key", key_name="BackSpace")
        with self.assertRaises(ValueError):
            self.live.enqueue(self.other, "click", x=100, y=200)
        with self.assertRaises(ValueError):
            self.live.enqueue(self.first, "key", key_name="Control_L")
        with self.assertRaises(ValueError):
            self.live.enqueue(self.first, "click", x=1001, y=10)
        with self.assertRaises(ValueError):
            self.live.enqueue(self.first, "click", x=True, y=10)
        self.assertEqual(self.live.take()["kind"], "click")
        self.assertEqual(self.live.take()["key_name"], "BackSpace")
        self.assertIsNone(self.live.take())
        self.live.enqueue(self.first, "click", x=400, y=500)
        self.now[0] += 4
        self.assertIsNone(self.live.take())

    def test_stopped_session_clears_pending_events(self):
        self.live.start(self.first)
        self.live.enqueue(self.first, "key", key_name="Return")
        self.live.stop(self.first)
        self.assertIsNone(self.live.take())
        self.assertFalse(self.live.authorized(self.first))


if __name__ == "__main__":
    unittest.main()
