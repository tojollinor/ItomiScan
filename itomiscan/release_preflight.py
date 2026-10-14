"""Read-only release readiness checks for the original 1-GiB N1800.

This never scans, sends documents, administers CUPS, changes systemd services,
checks out a branch, or applies an update. JSON output contains no credentials.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys

from itomiscan.storage.config import ConfigStore


NEEDED = ("scanimage", "img2pdf")
OPTIONAL = ("lp", "lpstat", "smbclient", "git", "openssl")
MIN_FREE_MIB = 512
SCANNER_RAM_MIB = 1024


def execute(args, *, timeout=6):
    try:
        return subprocess.run(args, capture_output=True, text=True,
                              timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None


def collect(*, home=None, repo=None, discover=True):
    home = Path(home or Path.home())
    repo = Path(repo or Path(__file__).resolve().parents[2])
    checks = []

    def check(name, passed, description, *, blocking=False):
        checks.append({"name": name, "passed": bool(passed),
                       "blocking": bool(blocking),
                       "detail": description})

    try:
        b = execute(["git", "-C", str(repo), "branch", "--show-current"])
        name = b.stdout.strip() if b and b.returncode == 0 else "unbekannt"
        check("git_branch", name == "develop/1.0.0",
              "Entwicklungszweig: " + name +
              "; Stable-Release benötigt spätere Freigabe.")
    except (OSError, ValueError):
        check("git_branch", False, "Git-Zweig konnte nicht ermittelt werden.")

    ram = None
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal:"):
                ram = int(line.split()[1]) // 1024
                break
        check("ram", ram is not None and ram >= 600,
              "RAM: " + (str(ram) + " MiB" if ram is not None else "unbekannt") +
              ". Mindestgrenze 600 MiB; RAM-Verbrauch separat am N1800 prüfen.",
              blocking=True)
    except (OSError, ValueError, IndexError):
        check("ram", False, "RAM nicht lesbar.", blocking=True)

    for binary in NEEDED + OPTIONAL:
        installed = shutil.which(binary) is not None
        check("dependency_" + binary, installed,
              ("Verfügbar" if installed else "Fehlt") + ": " + binary,
              blocking=binary in NEEDED)

    config = home / ".config" / "itomiscan"
    try:
        free = shutil.disk_usage(config if config.is_dir() else home).free // 1048576
        check("disk_space", free >= MIN_FREE_MIB,
              str(free) + " MiB frei; mindestens " + str(MIN_FREE_MIB) +
              " MiB Reserve empfohlen.", blocking=True)
    except OSError:
        check("disk_space", False, "Speicherplatz nicht lesbar.", blocking=True)

    db_path = config / "itomiscan.db"
    if db_path.exists() and not db_path.is_symlink():
        try:
            import sqlite3
            # Strictly read-only: preflight must not create/migrate tables,
            # write permissions or touch a live delivery lease.
            with sqlite3.connect(
                    "file:" + str(db_path) + "?mode=ro", uri=True) as db:
                if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                    raise ValueError("SQLite-Prüfung fehlgeschlagen.")
                exists = db.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' "
                    "AND name='delivery_jobs'").fetchone()
                statuses = dict(db.execute(
                    "SELECT status,COUNT(*) FROM delivery_jobs GROUP BY status"
                ).fetchall()) if exists else {}
            check("queue", True,
                  "Aufträge: " + json.dumps(statuses, sort_keys=True))
        except (OSError, ValueError, sqlite3.DatabaseError) as exc:
            check("queue", False, "Datenbank/Aufträge nicht prüfbar: " +
                  type(exc).__name__, blocking=True)
    else:
        check("queue", False,
              "Noch keine lokale SQLite-Konfiguration vorhanden; "
              "Installation/Erststart erforderlich.")

    if discover:
        result = execute(["scanimage", "-L"], timeout=9) if shutil.which("scanimage") else None
        detected = result is not None and result.returncode == 0 and (
            "fujitsu:" in result.stdout)
        check("scanner", detected, "Fujitsu-SANE-Gerät " +
              ("gefunden" if detected else "nicht nachweisbar"),
              blocking=True)
    else:
        check("scanner", False, "Hardwareerkennung deaktiviert.")

    test_status = "NICHT DURCHGEFÜHRT"
    check("physical_touch", False, "Echte 1024×768 Touch-Kalibrierung: " + test_status)
    check("physical_frontkey", False, "Fronttaste nach PIN und im Kopiermodus: " + test_status)
    check("duplex_pdf", False, "Echter mehrseitiger Duplexscan/PDF: " + test_status)
    check("network_targets", False, "Paperless/SMB/SMTP/USB: reale Zielabnahme offen.")
    check("printing", False, "IPP/CUPS-Testdruck, Kopien und Duplex: reale Abnahme offen.")
    check("rollback", False, "Rückwechsel zu stabilem Stand am Gerät: nicht getestet.")

    return {"checks": checks,
            "blocking_errors": [x["name"] for x in checks
                                if x["blocking"] and not x["passed"]],
            "physical_acceptance_pending": True,
            "release_allowed": False}


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Nur-lesender ItomiScan Vorabcheck vor Hardwareabnahme")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--no-scanner", action="store_true",
                        help="Offline prüfen, Hardwareerkennung überspringen")
    args = parser.parse_args(argv)
    result = collect(discover=not args.no_scanner)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for item in result["checks"]:
            print(("OK" if item["passed"] else "OFFEN") + " | " +
                  item["name"] + " | " + item["detail"])
        print("Kein Release durch diesen Check. Hardwareabnahme erforderlich.")
    return 1 if result["blocking_errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
