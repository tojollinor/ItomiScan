"""Offline readiness tests; never contact real scanner or X server."""

import tempfile
import unittest
from pathlib import Path

from itomiscan.core.startup import StartupFailure, touch_detected, wait_until_ready


class DummyClock:
    def __init__(self):
        self.current = 0.0

    def __call__(self):
        return self.current

    def sleep(self, seconds):
        self.current += seconds


class StartupTests(unittest.TestCase):
    def test_touch_detected_by_kernel_event(self):
        devices = (
            'I: Bus=0003 Vendor=0430 Product=0501 Version=0100\n'
            'N: Name="Fujitsu Component USB Touch Panel"\n'
            'H: Handlers=mouse0 event3\n'
        )
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "devices"
            path.write_text(devices)
            self.assertTrue(touch_detected(path))
            path.write_text(devices.replace("Product=0501", "Product=0001"))
            self.assertFalse(touch_detected(path))

    def test_scanner_retries_then_returns_device_and_options(self):
        clock = DummyClock()
        stages = []
        devices = iter([None, "fujitsu:fi-6110dj:10407"])
        device, options = wait_until_ready(
            lambda: next(devices), lambda d: [{"source": "ADF Duplex"}],
            lambda stage, msg: stages.append(stage), touch_probe=lambda: True,
            timeout=4, retry_delay=0.2, clock=clock, sleep=clock.sleep)
        self.assertTrue(device.startswith("fujitsu:"))
        self.assertEqual(len(options), 1)
        self.assertEqual(stages[-1], "ready")

    def test_missing_touch_has_finite_deadline(self):
        clock = DummyClock()
        with self.assertRaisesRegex(StartupFailure, "Touchscreen"):
            wait_until_ready(lambda: None, lambda d: [], lambda *_: None,
                             touch_probe=lambda: False, timeout=2,
                             retry_delay=0.1, clock=clock, sleep=clock.sleep)
        self.assertLessEqual(clock.current, 2.1)

    def test_missing_scanner_has_finite_deadline(self):
        clock = DummyClock()
        with self.assertRaisesRegex(StartupFailure, "Scanner nicht bereit"):
            wait_until_ready(lambda: None, lambda d: [], lambda *_: None,
                             touch_probe=lambda: True, timeout=2,
                             retry_delay=0.2, clock=clock, sleep=clock.sleep)
        self.assertLessEqual(clock.current, 2.1)

    def test_options_failure_is_retried(self):
        clock = DummyClock()
        tries = [0]
        def options(_device):
            tries[0] += 1
            if tries[0] == 1:
                raise RuntimeError("Gerät beschäftigt")
            return ["ok"]
        result = wait_until_ready(lambda: "fujitsu:scanner", options,
                                  lambda *_: None, touch_probe=lambda: True,
                                  timeout=4, retry_delay=0.2,
                                  clock=clock, sleep=clock.sleep)
        self.assertEqual(result[1], ["ok"])
        self.assertEqual(tries[0], 2)


if __name__ == "__main__":
    unittest.main()
