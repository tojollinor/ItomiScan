"""Verify and unpack an ItomiScan complete backup into an isolated directory.

Staging is intentional: never overwrite a live SQLite DB, scanner originals or
private credentials while services might be running.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import zipfile

from itomiscan.storage.full_backup import (
    BackupError, CHUNK, create_backup, read_manifest, verify_backup,
)


def restore_to_staging(archive_path, output_dir):
    """Checksummed extraction; existing files and active scanner stay untouched."""
    archive_path = Path(archive_path).expanduser().absolute()
    dest = Path(output_dir).expanduser().absolute()
    if not archive_path.is_file() or archive_path.is_symlink():
        raise BackupError("Archiv fehlt oder ist ein symbolischer Link.")
    if dest.exists() or dest.is_symlink():
        raise BackupError("Zielordner existiert bereits, kein Überschreiben.")
    if archive_path.is_relative_to(dest):
        raise BackupError("Zielordner enthält das Sicherungsarchiv.")
    verify_backup(archive_path)
    dest.mkdir(mode=0o700, parents=True)
    try:
        with zipfile.ZipFile(archive_path, "r") as zf:
            entries, _ = read_manifest(zf)
            for item in entries:
                path = dest.joinpath(*item["name"].split("/"))
                path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                if path.parent.is_symlink():
                    raise BackupError("Unsicherer Wiederherstellungspfad.")
                with zf.open(item["name"]) as src, path.open("xb") as dst:
                    os.chmod(path, 0o600)
                    shutil.copyfileobj(src, dst, CHUNK)
                    dst.flush()
                    os.fsync(dst.fileno())
            database = dest / "config" / "itomiscan.db"
            with sqlite3.connect(
                    "file:" + str(database) + "?mode=ro", uri=True) as con:
                if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise BackupError("Restaurierte SQLite-Datenbank beschädigt.")
        return {"staging": str(dest), "files": len(entries)}
    except Exception:
        shutil.rmtree(dest)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Offline-Sicherung inklusive Scans, PIN-Daten und Geheimnissen")
    operations = parser.add_subparsers(dest="action", required=True)
    create = operations.add_parser("create", help="Vollbackup erstellen (0600)")
    create.add_argument("archive")
    create.add_argument("--home")
    create.add_argument("--config-dir")
    verify = operations.add_parser("verify", help="Alle SHA-256-Werte prüfen")
    verify.add_argument("archive")
    restore = operations.add_parser("restore-to-staging",
                                    help="In einen neuen isolierten Ordner entpacken")
    restore.add_argument("archive")
    restore.add_argument("directory")
    args = parser.parse_args(argv)
    try:
        if args.action == "create":
            result = create_backup(args.archive, home=args.home,
                                   config_dir=args.config_dir)
        elif args.action == "verify":
            result = verify_backup(args.archive)
        else:
            result = restore_to_staging(args.archive, args.directory)
    except (BackupError, OSError, ValueError, sqlite3.DatabaseError,
            zipfile.BadZipFile) as exc:
        parser.exit(2, "Sicherung fehlgeschlagen: " + str(exc) + "\n")
    print(json.dumps(result, ensure_ascii=False))
    print("WARNUNG: Die Sicherung enthält private Zugangsdaten, unverschlüsselt!",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
