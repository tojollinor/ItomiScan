#!/usr/bin/env bash
# ItomiScan Beta 3 N1800 read-only acceptance snapshot. No scanning, uploads,
# CUPS configuration, service restarts, DB migrations or boot changes.
set -u
set -o pipefail
cd "$(dirname "$0")/.." || exit 2
echo "=== ItomiScan Beta 3: N1800 Vor-Ort-Vorprüfung (NUR LESEND) ==="
date -Is
echo
echo "--- System & Version ---"
uname -a
if command -v git >/dev/null 2>&1; then
  git branch --show-current
  git rev-parse --short=12 HEAD
  if [[ -n "$(git status --porcelain 2>/dev/null)" ]]; then
    echo "WARNUNG: lokale Änderungen vorhanden"
  fi
fi
echo
echo "--- Boot ---"
if command -v systemd-analyze >/dev/null 2>&1; then
  systemd-analyze 2>&1 || true
  systemd-analyze blame 2>/dev/null | head -n 12 || true
fi
echo
echo "--- CPU & RAM ---"
awk '/MemTotal:|MemAvailable:|SwapTotal:|SwapFree:/ {print}' /proc/meminfo
awk '/^cpu / {print "CPU-Zähler:",$0}' /proc/stat
if command -v free >/dev/null 2>&1; then free -m; fi
echo
echo "--- Speicherplatz ---"
df -h "${HOME}"
echo
echo "--- Dienste ---"
for unit in itomiscan-delivery.service itomiscan-web.service cups.service; do
  systemctl is-active "$unit" 2>/dev/null || true
done
echo
echo "--- Abhängigkeiten ---"
for tool in python3 scanimage img2pdf lpstat lpadmin avahi-browse smbclient; do
  if command -v "$tool" >/dev/null 2>&1; then
    echo "OK: $tool"
  else
    echo "FEHLT / ggf. optional: $tool"
  fi
done
echo
echo "--- SANE, ausschließlich Geräteabfrage (maximal 15 s) ---"
if command -v scanimage >/dev/null 2>&1 && command -v timeout >/dev/null 2>&1; then
  timeout 15 scanimage -L 2>&1 || echo "SANE nicht rechtzeitig verfügbar oder keine Geräte"
fi
echo
echo "--- Eingerichtete CUPS-Geräte (keine Testdrucke) ---"
if command -v lpstat >/dev/null 2>&1; then
  timeout 8 lpstat -v 2>&1 || true
fi
echo
echo "--- SQLite-Datei (lesend, keine Schema-Aktualisierung) ---"
python3 -B - <<'PY'
import sqlite3
from pathlib import Path
p=Path.home()/'.config'/'itomiscan'/'itomiscan.db'
if not p.is_file():
    print('Keine bestehende Datenbank gefunden')
else:
    try:
        with sqlite3.connect('file:'+str(p)+'?mode=ro',uri=True,timeout=2) as db:
            print('Integrität:',db.execute('PRAGMA quick_check').fetchone()[0])
            tables={r[0] for r in db.execute(
                'SELECT name FROM sqlite_master WHERE type="table"')}
            for name in ('delivery_jobs','delivery_batches','kiosk_tiles'):
                if name in tables:
                    print(name,':',db.execute('SELECT COUNT(*) FROM '+name).fetchone()[0])
            if 'delivery_jobs' in tables:
                print('Auftragszustände:',db.execute(
                    'SELECT status,COUNT(*) FROM delivery_jobs GROUP BY status').fetchall())
    except (OSError,sqlite3.Error) as exc:
        print('DB nicht lesbar:',type(exc).__name__)
PY
echo
echo "=== MANUELL DURCHZUFÜHREN, NICHT DURCH DIESES SKRIPT ==="
echo "1. PIN/Logout/Screensaver mit 30 Sekunden und aktiver Übertragung"
echo "2. 1024x768: Buttons, Gruppen, Scrollen, Vorschau, Seitenaktionen"
echo "3. SANE Duplex, DPI, Mehrseiten-PDF, Seiten drehen/löschen/sortieren"
echo "4. Ein Scan -> Paperless und Drucker parallel, Status pro Ziel"
echo "5. Eine fehlerhafte Zielverbindung: kein Doppelversand, Review-Hinweis"
echo "6. Hintergrundmodus, dauerhafte Meldungen nach Neustart, Benutzertrennung"
echo "7. CPU/RAM bei laufendem Scan+zwei Lieferungen beobachten, 1 GiB Grenze"
echo "8. CUPS-Papierausgabe / Paperless-Dokumentverarbeitung am Ziel bestätigen"
echo "9. Backup/Rollback mit echten gesicherten Daten ohne Überschreiben prüfen"
echo "Es wurden keine Einstellungen geändert und keine Dokumente versendet."
