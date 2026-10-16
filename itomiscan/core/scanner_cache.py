"""Best-effort last-seen Fujitsu SANE capability cache.

This file is for rendering familiar controls while the scanner probes in the
background. Cached data NEVER proves a USB scanner is connected or ready.
"""
import json
import os
from pathlib import Path
import tempfile

CACHE_VERSION = 1
MAX_BYTES = 96 * 1024
MAX_OPTIONS = 180


def cache_path():
    return Path.home() / ".cache" / "itomiscan" / "scanner-options.json"


def _valid_options(options):
    if not isinstance(options, list) or not 0 < len(options) <= MAX_OPTIONS:
        return False
    for item in options:
        if not isinstance(item, dict):
            return False
        if not isinstance(item.get("flag"), str) or len(item["flag"]) > 96:
            return False
        if not isinstance(item.get("section"), str) or len(item["section"]) > 80:
            return False
        if not isinstance(item.get("kind"), str) or item["kind"] not in ("enum", "bool", "number", "text"):
            return False
        if type(item.get("inactive")) is not bool:
            return False
        if not isinstance(item.get("choices"), list) or len(item["choices"]) > 128:
            return False
        if any(not isinstance(v, str) or len(v) > 180 for v in item["choices"]):
            return False
        for key in ("value", "default"):
            if not isinstance(item.get(key), str) or len(item[key]) > 256:
                return False
    return True


def read_cache(path=None):
    path = Path(path) if path else cache_path()
    try:
        if path.stat().st_size > MAX_BYTES:
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("version") != CACHE_VERSION:
            return None
        device, options = data.get("device"), data.get("options")
        if not isinstance(device, str) or not device.startswith("fujitsu:"):
            return None
        if not _valid_options(options):
            return None
        return device, options
    except (OSError, ValueError, TypeError, AttributeError):
        return None


def write_cache(device, options, path=None):
    if not isinstance(device, str) or not device.startswith("fujitsu:"):
        return False
    if not _valid_options(options):
        return False
    path = Path(path) if path else cache_path()
    encoded = json.dumps(
        {"version": CACHE_VERSION, "device": device, "options": options},
        ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(encoded) > MAX_BYTES:
        return False
    temp = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd, temp = tempfile.mkstemp(prefix=".options-", dir=path.parent)
        with os.fdopen(fd, "wb") as output:
            output.write(encoded)
        os.chmod(temp, 0o600)
        os.replace(temp, path)
        return True
    except OSError:
        return False
    finally:
        if temp:
            try:
                Path(temp).unlink(missing_ok=True)
            except OSError:
                pass
