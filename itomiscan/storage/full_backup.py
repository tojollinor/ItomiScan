"""Small streaming offline state backups. Archives contain private secrets.

Never expose archives from the web server. Shut down the delivery worker and
kiosk before taking a snapshot. PDFs are stored without recompression to keep
CPU and memory use low on the 1-GiB ScanSnap N1800.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import tempfile
import zipfile

CHUNK = 128 * 1024
MAGIC = "itomiscan-full-v1"
MAX_FILES = 10000
MAX_TOTAL = 40 * 1024 ** 3
CONFIG_NAMES = ("itomiscan.db", "profiles.json", "integrations-secrets.json",
                "tls/cert.pem", "tls/key.pem")


class BackupError(ValueError):
    pass


def safe_name(name):
    """Only the known backup tree, not arbitrary ZIP paths."""
    if not isinstance(name, str) or len(name) > 400 or "\\" in name:
        return False
    parts = name.split("/")
    if any(not part or part in (".", "..") or "\x00" in part
           for part in parts):
        return False
    if name in ("config/" + p for p in CONFIG_NAMES):
        return True
    if re.fullmatch(r"spool/[a-f0-9]{32}\.pdf", name):
        return True
    return name.startswith("scans/") and len(parts) >= 2


def check_regular(path):
    path = Path(path)
    for candidate in (path, *path.parents):
        if candidate.is_symlink():
            raise BackupError("Symbolische Links sind nicht erlaubt.")
    st = path.stat()
    if not stat.S_ISREG(st.st_mode) or st.st_nlink > 1:
        raise BackupError("Nur normale, unverlinkte Dateien zulässig.")


def source_files(home, conf, snapshot):
    result = [("config/itomiscan.db", snapshot)]
    for name in CONFIG_NAMES[1:]:
        path = conf / name
        if path.exists() or path.is_symlink():
            result.append(("config/" + name, path))
    for root, prefix in ((conf / "spool", "spool"),
                         (home / "Scans", "scans")):
        if root.is_symlink():
            raise BackupError("Unsicherer Datenordner.")
        if root.exists():
            for path in sorted(root.rglob("*")):
                if path.is_symlink():
                    raise BackupError("Symbolischer Link in den Quelldaten.")
                if path.is_file():
                    result.append((prefix + "/" + path.relative_to(root).as_posix(),
                                   path))
    if len(result) > MAX_FILES or len({n for n, _ in result}) != len(result):
        raise BackupError("Zu viele oder doppelte Dateien.")
    return result


def create_backup(output, *, home=None, config_dir=None):
    home = Path(home or Path.home()).expanduser().absolute()
    conf = Path(config_dir or home / ".config" / "itomiscan").absolute()
    output = Path(output).expanduser().absolute()
    if not conf.is_dir() or conf.is_symlink():
        raise BackupError("ItomiScan Konfiguration nicht gefunden.")
    if output.exists() or output.is_symlink():
        raise BackupError("Bestehende Sicherungen werden nicht überschrieben.")
    if output.is_relative_to(conf) or output.is_relative_to(home / "Scans"):
        raise BackupError("Sicherung darf nicht im gesicherten Verzeichnis liegen.")
    check_regular(conf / "itomiscan.db")
    output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    tmp_file = None
    try:
        with tempfile.TemporaryDirectory(prefix="itomiscan-sqlite-") as temp:
            snapshot = Path(temp) / "itomiscan.db"
            with sqlite3.connect("file:" + str(conf / "itomiscan.db") + "?mode=ro",
                                 uri=True) as original:
                exists = original.execute(
                    "SELECT 1 FROM sqlite_master WHERE name='delivery_jobs'").fetchone()
                if exists and original.execute(
                        "SELECT COUNT(*) FROM delivery_jobs WHERE status='sending'"
                        ).fetchone()[0]:
                    raise BackupError("Zustellung aktiv. Zuerst den Worker beenden.")
                with sqlite3.connect(snapshot) as dest:
                    original.backup(dest)
            sources = source_files(home, conf, snapshot)
            with tempfile.NamedTemporaryFile(dir=output.parent,
                    prefix=".itomiscan-", suffix=".part",
                    delete=False) as tmp:
                tmp_file = Path(tmp.name)
                os.chmod(tmp_file, 0o600)
            files, total = [], 0
            with zipfile.ZipFile(tmp_file, "w",
                    compression=zipfile.ZIP_STORED, allowZip64=True) as zf:
                for name, path in sources:
                    if not safe_name(name):
                        raise BackupError("Unsicherer Dateiname in der Sicherung.")
                    check_regular(path)
                    before = path.stat()
                    total += before.st_size
                    if total > MAX_TOTAL:
                        raise BackupError("Sicherung überschreitet die Größenbegrenzung.")
                    h, size = hashlib.sha256(), 0
                    with path.open("rb") as src, zf.open(name, "w", force_zip64=True) as dst:
                        for chunk in iter(lambda: src.read(CHUNK), b""):
                            dst.write(chunk)
                            h.update(chunk)
                            size += len(chunk)
                    after = path.stat()
                    if (size != before.st_size or after.st_size != before.st_size
                            or after.st_mtime_ns != before.st_mtime_ns):
                        raise BackupError("Datei wurde während des Backups verändert.")
                    files.append({"name": name, "sha256": h.hexdigest(), "size": size})
                zf.writestr("manifest.json", json.dumps(
                    {"format": MAGIC, "files": files}, separators=(",", ":")))
            with tmp_file.open("rb") as stream:
                os.fsync(stream.fileno())
            os.replace(tmp_file, output)
            os.chmod(output, 0o600)
            tmp_file = None
            return {"files": len(files), "bytes": total, "path": str(output)}
    finally:
        if tmp_file is not None:
            tmp_file.unlink(missing_ok=True)


def read_manifest(archive):
    try:
        manifest = json.loads(archive.read("manifest.json"))
    except (KeyError, ValueError) as exc:
        raise BackupError("Ungültiges Sicherungsmanifest.") from exc
    if not isinstance(manifest, dict) or manifest.get("format") != MAGIC:
        raise BackupError("Fremdes Backup-Format.")
    files = manifest.get("files")
    if not isinstance(files, list) or len(files) > MAX_FILES:
        raise BackupError("Ungültige Sicherungsdateiliste.")
    allowed = set()
    total = 0
    for entry in files:
        if not isinstance(entry, dict):
            raise BackupError("Ungültiger Eintrag.")
        name, size, digest = entry.get("name"), entry.get("size"), entry.get("sha256")
        if (not safe_name(name) or name in allowed or type(size) is not int or
                size < 0 or not isinstance(digest, str) or
                not re.fullmatch(r"[a-f0-9]{64}", digest)):
            raise BackupError("Unsicherer Backup-Eintrag.")
        allowed.add(name)
        total += size
        if total > MAX_TOTAL:
            raise BackupError("Backup überschreitet die Größenbegrenzung.")
    infos = archive.infolist()
    names = [x.filename for x in infos]
    if len(infos) != len(allowed) + 1 or set(names) != allowed | {"manifest.json"}:
        raise BackupError("Zusätzliche oder doppelte ZIP-Dateien.")
    if "config/itomiscan.db" not in allowed:
        raise BackupError("Datenbank fehlt in der Sicherung.")
    for info in infos:
        if info.is_dir() or info.file_size > MAX_TOTAL:
            raise BackupError("Ungültiger ZIP-Eintrag.")
        if ((info.external_attr >> 16) & 0o170000) == 0o120000:
            raise BackupError("Symlink im ZIP verboten.")
    return files, total


def verify_backup(path):
    with zipfile.ZipFile(path, "r") as archive:
        files, total = read_manifest(archive)
        for entry in files:
            h, size = hashlib.sha256(), 0
            with archive.open(entry["name"]) as stream:
                for piece in iter(lambda: stream.read(CHUNK), b""):
                    size += len(piece)
                    h.update(piece)
            if h.hexdigest() != entry["sha256"] or size != entry["size"]:
                raise BackupError("Sicherung beschädigt: " + entry["name"])
        return {"files": len(files), "bytes": total}
