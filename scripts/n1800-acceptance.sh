#!/usr/bin/env bash
# Read-only N1800 acceptance diagnostics. No scanning, printing, reboot or configuration writes.
set -u
PROJECT="${HOME}/ItomiScan"
failures=0
check() {
  local label="$1"
  shift
  if "$@" >/dev/null 2>&1; then
    printf '[OK] %s\n' "$label"
  else
    printf '[FEHLER] %s\n' "$label"
    failures=$((failures+1))
  fi
}
echo "ItomiScan N1800 - Diagnose ohne Systemaenderungen"
echo "Zeit: $(date -Is)"
echo "Kernel: $(uname -srmo)"
echo "Benutzer: $(id -un)"
echo "Netzwerk: $(hostname -I 2>/dev/null || true)"
check "Quellcode vorhanden" test -f "$PROJECT/app.py"
check "Python-Syntax" python3 -m compileall -q "$PROJECT/app.py" "$PROJECT/itomiscan"
check "Scanner erreichbar" bash -c 'timeout 30 scanimage -L 2>&1 | grep -q "^device "'
check "CUPS erreichbar" lpstat -r
check "CUPS-Drucker auflistbar" lpstat -e
check "Webdienst aktiv" systemctl is-active --quiet itomiscan-web.service
check "Zustelldienst aktiv" systemctl is-active --quiet itomiscan-delivery.service
check "Benutzer darf ausschalten" sudo -n -l /usr/bin/systemctl poweroff
echo
echo "Fehler: $failures"
echo "HINWEIS: Boot, Touch, Mehrseiten-ADF, Doppeleinzug, PDF-Ausgabe, Druck und Zustellung sind hiermit NICHT getestet."
exit "$((failures > 0))"
