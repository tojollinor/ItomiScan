#!/usr/bin/env bash
# Manual code-only release switch/rollback, NOT automatically executed.
# Configuration and scans stay untouched. Must supply a verified full backup.
# Usage (as scanner user, after stopping services): 
#   bash release-switch.sh v1.0.0 /secure/full-backup.zip --confirm
set -euo pipefail
if [[ "$#" -ne 3 || "$3" != "--confirm" ]]; then
  echo "Verwendung: bash release-switch.sh VERSION/TARGET VOLLBACKUP.zip --confirm" >&2
  exit 2
fi
TARGET="$1"
BACKUP="$2"
if [[ "$TARGET" != "v1.0.0" &&
      "$TARGET" != "backup/prototype-2026-10-13" &&
      ! "$TARGET" =~ ^[0-9a-f]{40}$ ]]; then
  echo "Nur freigegebener Release-Tag, gesicherter Prototyp oder Commit-SHA erlaubt." >&2
  exit 2
fi
if [[ "$(id -u)" -eq 0 ]]; then
  echo "Nicht als root ausführen." >&2
  exit 2
fi
ROOT="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
[[ -d .git ]] || { echo "Kein Git-Checkout." >&2; exit 3; }
if [[ -n "$(git status --porcelain)" ]]; then
  echo "Lokale Änderungen vorhanden. Wechsel abgebrochen." >&2
  exit 3
fi
for svc in itomiscan-web.service itomiscan-delivery.service; do
  if systemctl is-active --quiet "$svc" 2>/dev/null; then
    echo "Zuerst Dienst stoppen: $svc" >&2
    exit 3
  fi
done
if pgrep -u "$(id -u)" -f 'python3.*itomiscan.gui.kiosk' >/dev/null 2>&1; then
  echo "Kiosk läuft noch. Zuerst am lokalen Gerät beenden." >&2
  exit 3
fi
if [[ ! -f "$BACKUP" ]]; then
  echo "Vollbackup fehlt: $BACKUP" >&2
  exit 3
fi
/usr/bin/python3 -B -m itomiscan.storage.backup_cli verify "$BACKUP"
REV="$(git rev-parse --verify "$TARGET^{commit}" 2>/dev/null)" || {
  echo "Zielrevision unbekannt. Keine automatischen Git-Fetches." >&2
  exit 3
}
PRIOR="$(git rev-parse HEAD)"
if [[ "$PRIOR" == "$REV" ]]; then
  echo "Bereits auf Zielrevision $REV."
  exit 0
fi
RECOVERY="$HOME/.config/itomiscan/previous-code-revision"
mkdir -p "$(dirname "$RECOVERY")"
if [[ -L "$RECOVERY" ]]; then
  echo "Unsicherer Wiederherstellungspfad." >&2
  exit 3
fi
# Never force-reset, rewrite remote branches or move main. The checkout
# can be undone with this exact old commit SHA after services are stopped.
printf '%s\n' "$PRIOR" > "$RECOVERY"
chmod 0600 "$RECOVERY"
git switch --detach "$REV"
echo "Code gewechselt zu $REV; bisheriger Commit: $PRIOR"
echo "Dienste nicht gestartet. Vor Neustart Python, DB und Hardware prüfen."
echo "Bei Datenbankinkompatibilität das geprüfte Backup getrennt restaurieren."
