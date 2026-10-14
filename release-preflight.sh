#!/usr/bin/env bash
# Read-only release readiness check; no updates or service changes.
set -euo pipefail
ROOT="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
echo "ItomiScan – Release-Vorabprüfung (nur lesend)"
echo "============================================="
HEAD="$(git rev-parse HEAD 2>/dev/null || printf unbekannt)"
BRANCH="$(git branch --show-current 2>/dev/null || printf unbekannt)"
echo "Git: $BRANCH @ $HEAD"
if [[ -n "$(git status --porcelain 2>/dev/null)" ]]; then
  echo "WARNUNG: Arbeitsverzeichnis ist nicht sauber. Upgrade/Rollback sperren."
fi
if [[ -r /etc/os-release ]]; then
  . /etc/os-release
  echo "Linux: ${PRETTY_NAME:-unbekannt}"
  [[ "${VERSION_CODENAME:-}" == "bookworm" ]] || echo "WARNUNG: Debian 12 erwartet."
fi
echo "Architektur: $(uname -m)"
echo "RAM:"
awk '/MemTotal:/ {printf "  %0.0f MiB\n",$2/1024}' /proc/meminfo 2>/dev/null || true
echo "Freier Speicherplatz:"
df -h "$HOME" | tail -1
echo "Systemwerkzeuge:"
for cmd in python3 scanimage img2pdf git smbclient lp lpstat lpadmin; do
  if command -v "$cmd" >/dev/null 2>&1; then
    echo "  OK: $cmd"
  else
    echo "  Fehlt (ggf. optionale Funktion): $cmd"
  fi
done
echo "Python-Pakete:"
python3 -B - <<'PY'
try:
    import tkinter
    print("  Tkinter: OK")
except ImportError:
    print("  Tkinter: FEHLT")
try:
    import PIL
    print("  Pillow: OK")
except ImportError:
    print("  Pillow: FEHLT")
PY
echo "Lokale Konfiguration:"
python3 -B - <<'PY'
from pathlib import Path
import sqlite3
p = Path.home() / ".config" / "itomiscan" / "itomiscan.db"
if not p.exists():
    print("  Noch keine SQLite-Konfiguration vorhanden.")
else:
    try:
        with sqlite3.connect("file:" + str(p) + "?mode=ro", uri=True) as db:
            print("  Integrität:", db.execute("PRAGMA integrity_check").fetchone()[0])
            has_jobs = db.execute(
                "SELECT 1 FROM sqlite_master WHERE name='delivery_jobs'").fetchone()
            if has_jobs:
                rows = db.execute(
                    "SELECT status,COUNT(*) FROM delivery_jobs GROUP BY status").fetchall()
                print("  Zustellaufträge:", rows)
    except (OSError, sqlite3.DatabaseError) as exc:
        print("  FEHLER:", type(exc).__name__)
PY
echo "Dienststatus (nur lesen):"
for unit in itomiscan-web.service itomiscan-delivery.service cups.service; do
  if systemctl is-active --quiet "$unit" 2>/dev/null; then
    echo "  Aktiv: $unit"
  else
    echo "  Nicht aktiv: $unit"
  fi
done
echo ""
echo "WICHTIG: Dies ist KEIN Hardware-Abnahmetest."
echo "Nicht geprüft: Touch, ADF-Duplex, echte Dokumentenziele,"
echo "CUPS-Papierausgabe, Fronttaste, 1-GiB-RAM-Last."
echo "main und Release-Tags bleiben unverändert."
