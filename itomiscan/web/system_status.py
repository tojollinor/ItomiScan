"""Small, dependency-free status sampler for the Atom N270 web dashboard.

Read-only access to /proc, filesystem usage and approved systemd unit names.
No expensive scanner discovery is triggered by background refresh.
"""
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time


UNITS = (
    ("web_service", "itomiscan-web.service"),
    ("delivery_service", "itomiscan-delivery.service"),
)


def _format_bytes(value):
    value = max(0, int(value))
    if value >= 1024 ** 3:
        return f"{value / (1024 ** 3):.1f} GiB"
    return f"{value / (1024 ** 2):.0f} MiB"


def _cpu_times():
    parts = Path("/proc/stat").read_text().splitlines()[0].split()
    if parts[0] != "cpu" or len(parts) < 5:
        raise ValueError("/proc/stat hat kein CPU-Gesamtprofil")
    # Linux guest and guest_nice are already included in user/nice.
    # Count only the first eight /proc/stat fields to avoid double counting.
    counters = [int(value) for value in parts[1:9]]
    # idle + iowait are time without CPU work.
    idle = counters[3] + (counters[4] if len(counters) > 4 else 0)
    return sum(counters), idle


def _memory_usage():
    entries = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        if ":" not in line:
            continue
        key, rest = line.split(":", 1)
        try:
            entries[key] = int(rest.split()[0]) * 1024
        except (ValueError, IndexError):
            continue
    total = entries["MemTotal"]
    available = entries.get("MemAvailable", entries.get("MemFree", 0))
    available = min(total, available)
    return total, total - available, available


class StatusSampler:
    def __init__(self, *, clock=time.monotonic):
        self.lock = threading.Lock()
        self.clock = clock
        self.previous_cpu = None
        self.previous_time = 0.0
        self.last_cpu = "Messung läuft …"
        self.cached_services = {}
        self.service_time = -100.0

    def _cpu(self):
        try:
            total, idle = _cpu_times()
        except (OSError, ValueError, IndexError):
            return "Nicht verfügbar"
        now = self.clock()
        with self.lock:
            old = self.previous_cpu
            old_time = self.previous_time
            self.previous_cpu = (total, idle)
            self.previous_time = now
            if old and total > old[0] and now - old_time >= 1:
                delta_total = total - old[0]
                busy = max(0, min(delta_total, delta_total - (idle - old[1])))
                self.last_cpu = f"{100 * busy / delta_total:.1f} %"
            return self.last_cpu

    def _services(self):
        now = self.clock()
        with self.lock:
            if self.cached_services and now - self.service_time < 30:
                return dict(self.cached_services)
            # Keep these checks outside the lock so concurrent web requests
            # can still read the most recent sample.
        result = {}
        for key, unit in UNITS:
            try:
                state = subprocess.run(
                    ["systemctl", "is-active", unit],
                    text=True, capture_output=True, timeout=1, check=False)
                result[key] = {
                    "active": "Aktiv",
                    "inactive": "Inaktiv",
                    "failed": "Fehler",
                    "activating": "Startet",
                    "deactivating": "Stoppt",
                    "unknown": "Nicht installiert",
                }.get(state.stdout.strip(), "Nicht verfügbar")
            except (OSError, subprocess.TimeoutExpired):
                result[key] = "Nicht verfügbar"
        with self.lock:
            self.cached_services = result
            self.service_time = now
        return result

    def collect(self, root):
        info = {
            "cpu": self._cpu(),
            "ram": "Nicht verfügbar",
            "ram_total": "Nicht verfügbar",
            "ram_used": "Nicht verfügbar",
            "ram_free": "Nicht verfügbar",
            "disk": "Nicht verfügbar",
            "disk_total": "Nicht verfügbar",
            "disk_used": "Nicht verfügbar",
            "disk_free": "Nicht verfügbar",
            "free_space": "Nicht verfügbar",
        }
        try:
            total, used, free = _memory_usage()
            info.update(ram=f"{_format_bytes(used)} / {_format_bytes(total)}",
                        ram_total=_format_bytes(total),
                        ram_used=_format_bytes(used),
                        ram_free=_format_bytes(free))
        except (OSError, ValueError, KeyError):
            pass
        try:
            disk = shutil.disk_usage(root)
            info.update(disk=f"{_format_bytes(disk.used)} / {_format_bytes(disk.total)}",
                        disk_total=_format_bytes(disk.total),
                        disk_used=_format_bytes(disk.used),
                        disk_free=_format_bytes(disk.free),
                        free_space=_format_bytes(disk.free))
        except OSError:
            pass
        try:
            seconds = int(float(Path("/proc/uptime").read_text().split()[0]))
            info["uptime"] = f"{seconds // 86400} T. {(seconds // 3600) % 24} Std. {(seconds % 3600) // 60} Min."
        except (OSError, ValueError, IndexError):
            info["uptime"] = "Nicht verfügbar"
        info.update(self._services())
        return info
