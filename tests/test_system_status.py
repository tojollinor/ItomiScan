"""Offline tests for lightweight N1800 web system diagnostics."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from itomiscan.web import system_status


class StatusSamplerTests(unittest.TestCase):
    def test_proc_stat_parser_ignores_guest_counters(self):
        proc = "cpu  100 0 50 750 10 0 0 0 42 20\n"
        with patch.object(system_status.Path, "read_text", return_value=proc):
            total, idle = system_status._cpu_times()
        self.assertEqual(total, 910)
        self.assertEqual(idle, 760)

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
                self.assertEqual(info["disk_percent"], 25.0)
                self.assertEqual(info["ram_percent"], 25.0)
                self.assertEqual(info["web_service"], "Aktiv")
                self.assertEqual(info["delivery_service"], "Aktiv")
                self.assertEqual(run.call_count, 2)
                clock[0] += 15
                sampler.collect(Path(directory))
                self.assertEqual(run.call_count, 2)

    def test_memavailable_includes_reclaimable_cache_and_clamps_values(self):
        meminfo = ("MemTotal: 1024000 kB\n"
                   "MemFree: 100000 kB\n"
                   "MemAvailable: 256000 kB\n"
                   "Cached: 400000 kB\n")
        with patch.object(system_status.Path, "read_text",
                          return_value=meminfo):
            total, used, free = system_status._memory_usage()
        self.assertEqual(total, 1024000 * 1024)
        self.assertEqual(free, 256000 * 1024)
        self.assertEqual(used, (1024000 - 256000) * 1024)
        for available, used, free in ((500, 0, 100), (-5, 100, 0)):
            invalid = f"MemTotal: 100 kB\nMemAvailable: {available} kB\n"
            with patch.object(system_status.Path, "read_text",
                              return_value=invalid):
                self.assertEqual(system_status._memory_usage(),
                                 (100 * 1024, used * 1024, free * 1024))

    def test_sample_history_retains_only_latest_five_minutes_and_300_points(self):
        clock = [0.0]
        sampler = system_status.StatusSampler(
            clock=lambda: clock[0], wall_clock=lambda: clock[0])
        with patch.object(system_status, "_cpu_times") as cpu, \
             patch.object(system_status, "_memory_usage",
                          return_value=(1024, 256, 768)):
            cpu.side_effect = [(1000 + i * 200, 700 + i * 100)
                               for i in range(320)]
            for tick in range(320):
                clock[0] = float(tick)
                sampler.sample_once()
        samples = sampler.history()["samples"]
        self.assertEqual(len(samples), 300)
        self.assertEqual(samples[0]["ts"], 20.0)
        self.assertEqual(samples[-1]["ts"], 319.0)
        self.assertEqual(samples[-1]["cpu"], 50.0)
        self.assertEqual(samples[-1]["ram"], 25.0)
        samples[-1]["ram"] = -999
        self.assertEqual(sampler.history()["samples"][-1]["ram"], 25.0)
        clock[0] = 901.0
        self.assertEqual(sampler.history()["samples"], [])

    def test_sampler_starts_on_server_without_browser(self):
        import threading
        observed = threading.Event()
        sampler = system_status.StatusSampler()
        with patch.object(sampler, "sample_once",
                          side_effect=lambda: observed.set()):
            sampler.start()
            sampler.start()
            self.assertTrue(observed.wait(2))
            sampler.stop()

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
