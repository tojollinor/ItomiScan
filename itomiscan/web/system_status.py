"""Small, dependency-free status sampler for the Atom N270 web dashboard.

Read-only access to /proc, filesystem usage and approved systemd unit names.
No expensive scanner discovery is triggered by background refresh.
"""
from collections import deque
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
    available = max(0, min(total, available))
    return total, total - available, available


class StatusSampler:
    """Boot-service-owned, bounded five-minute CPU/RAM history in process RAM.

    The one-second worker is started once when the web service starts, rather
    than when somebody opens the dashboard. Nothing is written to disk.
    After restarting the web service, measurements accumulate afresh.
    """

    HISTORY_POINTS = 300
    SAMPLE_SECONDS = 1.0

    def __init__(self, *, clock=time.monotonic, wall_clock=time.time):
        self.lock = threading.Lock()
        self.clock = clock
        self.wall_clock = wall_clock
        self.previous_cpu = None
        self.previous_time = 0.0
        self.last_cpu = "Messung läuft …"
        self.cached_services = {}
        self.service_time = -100.0
        self._history = deque(maxlen=self.HISTORY_POINTS)
        self._latest = None
        self._stop = threading.Event()
        self._thread = None

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
            # A one-second schedule can wake slightly early. Do not silently
            # skip a reading because a monotonic interval was 0.999 seconds.
            if old and total > old[0] and now - old_time >= 0.8:
                delta_total = total - old[0]
                busy = max(0, min(delta_total, delta_total - (idle - old[1])))
                self.last_cpu = f"{100 * busy / delta_total:.1f} %"
            elif old and (total < old[0] or idle < old[1]):
                # A reboot or counter reset invalidates the previous sample.
                self.last_cpu = "Messung läuft …"
            return self.last_cpu

    def _memory(self):
        try:
            total, used, free = _memory_usage()
            if total <= 0:
                raise ValueError("Ungültiger Arbeitsspeicherwert")
            percent = round(100 * used / total, 1)
            return {
                "ram": f"{_format_bytes(used)} / {_format_bytes(total)}",
                "ram_percent": percent,
                "ram_total": _format_bytes(total),
                "ram_used": _format_bytes(used),
                "ram_free": _format_bytes(free),
            }
        except (OSError, ValueError, KeyError):
            return {
                "ram": "Nicht verfügbar", "ram_percent": None,
                "ram_total": "Nicht verfügbar",
                "ram_used": "Nicht verfügbar", "ram_free": "Nicht verfügbar",
            }

    @staticmethod
    def _cpu_percent(label):
        if not label.endswith(" %"):
            return None
        try:
            percent = float(label[:-2])
            return max(0.0, min(100.0, percent))
        except ValueError:
            return None

    def sample_once(self):
        """Sample CPU/RAM exactly once, storing one record with an epoch timestamp."""
        cpu = self._cpu()
        memory = self._memory()
        sample = {
            "ts": round(self.wall_clock(), 3),
            "cpu": self._cpu_percent(cpu),
            "ram": memory["ram_percent"],
        }
        with self.lock:
            self._latest = {"cpu": cpu, **memory}
            self._history.append(sample)
            # Keep a real five-minute window even after suspend or load.
            while (self._history and
                   self._history[0]["ts"] < sample["ts"] - 300):
                self._history.popleft()
        return sample

    def start(self):
        """Start in the web service startup path, never from a browser request."""
        with self.lock:
            if self._thread is not None:
                return
            self._stop.clear()
            self._thread = threading.Thread(
                target=self._run, name="itomiscan-metrics",
                daemon=True)
            worker = self._thread
        worker.start()

    def _run(self):
        next_sample = self.clock()
        while not self._stop.is_set():
            try:
                self.sample_once()
            except Exception:
                # Sampling is diagnostic only: never take down the web server.
                # Retain a gap instead of reporting an invented measurement.
                with self.lock:
                    self._latest = {"cpu": "Nicht verfügbar", **{
                        "ram": "Nicht verfügbar", "ram_percent": None,
                        "ram_total": "Nicht verfügbar", "ram_used": "Nicht verfügbar",
                        "ram_free": "Nicht verfügbar",
                    }}
                    self._history.append({"ts": round(self.wall_clock(), 3),
                                          "cpu": None, "ram": None})
            next_sample += self.SAMPLE_SECONDS
            now = self.clock()
            if next_sample < now:
                # Avoid catch-up loops after a slow or suspended host.
                next_sample = now + self.SAMPLE_SECONDS
            self._stop.wait(max(0, next_sample - now))

    def stop(self):
        self._stop.set()
        with self.lock:
            worker = self._thread
            self._thread = None
        if worker is not None and threading.current_thread() is not worker:
            worker.join(timeout=2)

    def history(self):
        """A copy, so concurrent HTTP requests never mutate the ring buffer."""
        cutoff = self.wall_clock() - 300
        with self.lock:
            samples = [dict(item) for item in self._history
                       if item["ts"] >= cutoff]
        return {
            "window_seconds": 300,
            "interval_seconds": 1,
            "samples": samples,
        }

    def latest(self):
        with self.lock:
            return dict(self._history[-1]) if self._history else None

    def _services(self):
        now = self.clock()
        with self.lock:
            if self.cached_services and now - self.service_time < 30:
                return dict(self.cached_services)
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
        """Serve cached CPU/RAM, and cheap current disk/service metadata."""
        with self.lock:
            started = self._thread is not None
            cached = dict(self._latest) if self._latest else None
            latest = dict(self._history[-1]) if self._history else None
        # Standalone samplers in unit tests still have a useful read-only
        # fallback; the running web server exclusively reads cached samples.
        if not started:
            cpu = self._cpu()
            memory = self._memory()
            cached = {"cpu": cpu, **memory}
        info = {
            "cpu": "Messung läuft …",
            "ram": "Nicht verfügbar", "ram_percent": None,
            "ram_total": "Nicht verfügbar", "ram_used": "Nicht verfügbar",
            "ram_free": "Nicht verfügbar",
            "disk": "Nicht verfügbar", "disk_percent": None,
            "disk_total": "Nicht verfügbar", "disk_used": "Nicht verfügbar",
            "disk_free": "Nicht verfügbar", "free_space": "Nicht verfügbar",
            "sample": latest,
        }
        if cached is not None:
            info.update(cached)
        try:
            disk = shutil.disk_usage(root)
            if disk.total > 0:
                used = max(0, min(disk.total, disk.used))
                info.update(
                    disk=f"{_format_bytes(used)} / {_format_bytes(disk.total)}",
                    disk_percent=round(100 * used / disk.total, 1),
                    disk_total=_format_bytes(disk.total),
                    disk_used=_format_bytes(used),
                    disk_free=_format_bytes(disk.free),
                    free_space=_format_bytes(disk.free),
                )
        except OSError:
            pass
        try:
            seconds = int(float(Path("/proc/uptime").read_text().split()[0]))
            info["uptime"] = (f"{seconds // 86400} T. "
                              f"{(seconds // 3600) % 24} Std. "
                              f"{(seconds % 3600) // 60} Min.")
        except (OSError, ValueError, IndexError):
            info["uptime"] = "Nicht verfügbar"
        info.update(self._services())
        return info
