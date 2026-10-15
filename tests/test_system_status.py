"""Offline tests for lightweight N1800 web system diagnostics."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from itomiscan.web import system_status


class StatusSamplerTests(unittest.TestCase):
    def test_cpu_usage_uses_successive_counters_without_sleep(self):
        clock = [1.0]
        sampler = system_status.StatusSampler(clock=lambda: clock[0])
        with patch.object(system_status, "_cpu_times", side_effect=[
            (1000, 600), (1200, 700), (1400, 790),
        ]):
            self.assertEqual(sampler._cpu(), "Messung läuft …")
            clock[0] = 3.0
            self.assertEqual(sampler._cpu(), "50.0 %")
            clock[0] = 5.0
            self.assertEqual(sampler._cpu(), "55.0 %")

    def test_memory_and_disk_values_and_service_cache(self):
        clock = [15.0]
        sampler = system_status.StatusSampler(clock=lambda: clock[0])
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(system_status, "_cpu_times", return_value=(100, 60)), \
                 patch.object(system_status, "_memory_usage",
                              return_value=(1024 * 1024 * 1024,
                                            256 * 1024 * 1024,
                                            768 * 1024 * 1024)), \
                 patch.object(system_status.shutil, "disk_usage",
                              return_value=SimpleNamespace(
                                  total=64 * 1024 ** 3, used=16 * 1024 ** 3,
                                  free=48 * 1024 ** 3)), \
                 patch.object(system_status.subprocess, "run",
                              return_value=SimpleNamespace(stdout="active\n")) as run:
                info = sampler.collect(Path(directory))
                self.assertEqual(info["ram"], "256 MiB / 1.0 GiB")
                self.assertEqual(info["disk"], "16.0 GiB / 64.0 GiB")
                self.assertEqual(info["web_service"], "Aktiv")
                self.assertEqual(info["delivery_service"], "Aktiv")
                self.assertEqual(run.call_count, 2)
                clock[0] += 15
                sampler.collect(Path(directory))
                self.assertEqual(run.call_count, 2)

    def test_missing_proc_or_service_yields_available_fallback(self):
        sampler = system_status.StatusSampler()
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(system_status, "_cpu_times", side_effect=OSError), \
             patch.object(system_status, "_memory_usage", side_effect=OSError), \
             patch.object(system_status.subprocess, "run",
                          side_effect=FileNotFoundError):
            status = sampler.collect(directory)
            self.assertEqual(status["cpu"], "Nicht verfügbar")
            self.assertEqual(status["ram"], "Nicht verfügbar")
            self.assertEqual(status["web_service"], "Nicht verfügbar")


if __name__ == "__main__":
    unittest.main()
