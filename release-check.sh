#!/usr/bin/env bash
# Release candidate checklist, intentionally NON-INSTALLING.
# Never promotes a Git branch, creates tags or changes systemd/CUPS.
set -euo pipefail

MODE="${1:---check}"
if [[ "$MODE" != "--check" ]]; then
  echo "Nur --check unterstützt. Release/Installation erfordert separate Freigabe." >&2
  exit 2
fi
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

echo "ItomiScan 1.0.0: lesender Vorabcheck"
echo "Arbeitsordner: $ROOT"
if [[ -e .git ]]; then
  BRANCH="$(git branch --show-current)"
  echo "Git-Zweig: $BRANCH"
  if [[ "$BRANCH" == "main" ]]; then
    echo "Dies ist die stabile Installation. Dieses Skript aktualisiert nichts."
  fi
  if [[ -n "$(git status --porcelain)" ]]; then
    echo "Warnung: lokale Änderungen vorhanden. Vor Update prüfen."
  fi
else
  echo "Kein Git-Repository. Quelle vor Einsatz prüfen." >&2
fi
/usr/bin/python3 -B - <<'PY'
import ast
from pathlib import Path
paths = [Path("app.py"), *Path("itomiscan").rglob("*.py")]
for path in paths:
    ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
print("Python-Syntax erfolgreich geprüft, ohne Dateien zu verändern.")
PY
bash -n install.sh setup-web.sh setup-delivery.sh setup-printing.sh setup-shutdown.sh
echo "Hardware-Vorabcheck (ohne SANE-Scannerdetektion):"
/usr/bin/python3 -m itomiscan.release_preflight --no-scanner || true
echo "Hardware-Abnahme noch offen: Touch, Fronttaste, Duplex, PDF/PNG,"
echo "PIN, HTTPS, Paperless/SMB/SMTP/USB, CUPS und Rollback."
echo "Keine Installation, kein Git-Update, keine Serviceänderung und kein Release."
