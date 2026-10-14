#!/usr/bin/env bash
# ItomiScan 1.0.0 beta deployment for Debian 12.
# Usage: sudo bash install-beta.sh --user USERNAME
set -Eeuo pipefail
umask 022
[[ $EUID -eq 0 ]] || { echo "Bitte mit sudo ausführen." >&2; exit 2; }
LOG=/var/log/itomiscan-install.log
exec > >(tee -a "$LOG") 2>&1
trap 'rc=$?; echo "[FEHLER] Zeile $LINENO: $BASH_COMMAND (Exit $rc)"; echo "[FEHLER] Log: $LOG"; exit $rc' ERR
ok(){ echo "[OK] $*"; }
info(){ echo "[INFO] $*"; }
fail(){ echo "[FEHLER] $*" >&2; exit 2; }
step(){ echo; echo "===== $* ====="; }

USER_NAME=""
while [[ $# -gt 0 ]]; do
 case "$1" in
  --user) [[ $# -ge 2 ]] || fail "--user benoetigt einen Benutzernamen."; USER_NAME="$2"; shift 2 ;;
  -h|--help) echo "Verwendung: sudo bash install-beta.sh --user BENUTZERNAME"; exit 0 ;;
  *) fail "Unbekannter Parameter: $1" ;;
 esac
done

step "Vorpruefung"
[[ $EUID -eq 0 ]] || fail "Installer muss mit sudo/root ausgefuehrt werden."
[[ -n "$USER_NAME" ]] || fail "Linux-Benutzer fehlt. --user BENUTZERNAME angeben."
[[ "$USER_NAME" =~ ^[a-z_][a-z0-9_-]*$ ]] || fail "Ungueltiger Benutzername: $USER_NAME"
id "$USER_NAME" >/dev/null 2>&1 || fail "Benutzer '$USER_NAME' existiert nicht."
[[ "$(id -u "$USER_NAME")" -ne 0 ]] || fail "root darf nicht als ItomiScan-Benutzer verwendet werden."
command -v apt-get >/dev/null || fail "apt-get fehlt; Debian-System erwartet."
[[ -r /etc/os-release ]] || fail "/etc/os-release fehlt."
. /etc/os-release
[[ "${ID:-}" == "debian" && "${VERSION_CODENAME:-}" == "bookworm" ]] || fail "Freigegeben ist Debian 12 (bookworm); erkannt: ${PRETTY_NAME:-unbekannt}."
USER_HOME="$(getent passwd "$USER_NAME" | cut -d: -f6)"
[[ -d "$USER_HOME" ]] || fail "Home-Verzeichnis fehlt: $USER_HOME"
PROJECT="$USER_HOME/ItomiScan"
FREE_KB="$(df -Pk "$USER_HOME" | awk 'NR==2{print $4}')"
[[ "${FREE_KB:-0}" -ge 524288 ]] || fail "Weniger als 512 MiB freier Speicher."
getent hosts github.com >/dev/null 2>&1 || fail "github.com kann nicht aufgeloest werden."
ok "Debian 12, Benutzer, Home, Speicher und DNS geprueft."

step "Basispakete"
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends xserver-xorg-core xserver-xorg-input-libinput xserver-xorg-video-intel xinit x11-xserver-utils xauth python3 python3-tk python3-pil python3-pil.imagetk sane-utils img2pdf git ca-certificates fonts-dejavu-core sudo openssl cups cups-client cups-filters smbclient curl
ok "Basispakete installiert."

step "Beta-Code (curl-Archiv, ohne git pull/reset)"
command -v curl >/dev/null || fail "curl fehlt."
if [[ -e "$PROJECT" && ! -d "$PROJECT" ]]; then fail "$PROJECT ist keine Verzeichnisinstallation."; fi
WORK="$(mktemp -d /tmp/itomiscan-beta.XXXXXXXX)"
trap 'rm -rf "$WORK"' EXIT
mkdir "$WORK/source"
# Resolve the exact commit BEFORE downloading. Archive and installed revision
# must describe the same source even if develop advances mid-install.
ARCHIVE_SHA="$(curl -fsSL --retry 2 --connect-timeout 15 --max-time 30 \
  -H 'Accept: application/vnd.github+json' \
  'https://api.github.com/repos/tojollinor/ItomiScan/commits/develop/1.0.0' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["sha"])')"
[[ "$ARCHIVE_SHA" =~ ^[0-9a-f]{40}$ ]] || fail "GitHub-Revision nicht verifizierbar."
curl -fL --retry 2 --connect-timeout 15 --max-time 180 \
  "https://github.com/tojollinor/ItomiScan/archive/${ARCHIVE_SHA}.tar.gz" \
  -o "$WORK/beta.tar.gz"
tar -xzf "$WORK/beta.tar.gz" --strip-components=1 -C "$WORK/source"
[[ -f "$WORK/source/app.py" && -f "$WORK/source/itomiscan/gui/kiosk.py" ]] || fail "Archiv unvollständig."
/usr/bin/python3 -m compileall -q "$WORK/source/app.py" "$WORK/source/itomiscan"
bash -n "$WORK/source/install-beta.sh"
if [[ -d "$PROJECT" ]]; then
 BACKUP="$(mktemp -d "$USER_HOME/ItomiScan-backup-$(date -u +%Y%m%dT%H%M%SZ)-XXXXXXXX")"
 # Preserve file ownership, modes and existing local configuration.
 cp -a "$PROJECT/." "$BACKUP/"
 info "Sicherung: $BACKUP"
else
 install -d -o "$USER_NAME" -g "$(id -gn "$USER_NAME")" "$PROJECT"
 info "Erstinstallation: $PROJECT"
fi
cp -a "$WORK/source/." "$PROJECT/"
# Record the same commit whose archive was downloaded.
printf '%s\n' "$ARCHIVE_SHA" > "$PROJECT/.itomiscan-beta-commit"
chown -R "$USER_NAME:$(id -gn "$USER_NAME")" "$PROJECT"
ok "Beta aus Archiv installiert, alte Dateien und Konfiguration gesichert."

step "Kiosk und Scannerrechte"
bash "$PROJECT/setup-shutdown.sh" "$USER_NAME"
chmod +x "$PROJECT/start-kiosk.sh"
if [[ -d "$PROJECT/.git" ]]; then runuser -u "$USER_NAME" -- git -C "$PROJECT" config core.filemode false; fi
if getent group scanner >/dev/null; then usermod -aG scanner "$USER_NAME"; fi
PROFILE="$USER_HOME/.profile"; [[ -f "$USER_HOME/.bash_profile" ]] && PROFILE="$USER_HOME/.bash_profile"
if ! grep -q '# ITOMISCAN_KIOSK_START' "$PROFILE" 2>/dev/null; then
 cat >>"$PROFILE" <<'KIOSK'

# ITOMISCAN_KIOSK_START
if [ -z "$DISPLAY" ] && [ "$(tty)" = "/dev/tty1" ]; then
  exec startx "$HOME/ItomiScan/start-kiosk.sh" -- :0 vt1 >/dev/null 2>&1
fi
KIOSK
 chown "$USER_NAME:$(id -gn "$USER_NAME")" "$PROFILE"
fi
install -d /etc/systemd/system/getty@tty1.service.d
cat >/etc/systemd/system/getty@tty1.service.d/itomiscan.conf <<EOF
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin $USER_NAME --noclear %I \$TERM
EOF
systemctl daemon-reload
ok "Kiosk-Autologin, Scannergruppe und Shutdown-Recht eingerichtet."

step "Webadmin vorbereiten"
if ! runuser -u "$USER_NAME" -- /usr/bin/env PYTHONPATH="$PROJECT" /usr/bin/python3 -m itomiscan.web.cli is-ready >/dev/null 2>&1; then
 info "Jetzt einmalig das Webadmin-Passwort festlegen."
 runuser -u "$USER_NAME" -- /usr/bin/env PYTHONPATH="$PROJECT" /usr/bin/python3 -m itomiscan.web.cli init-admin
fi
LAN_IP="$(hostname -I | tr ' ' '\n' | awk '/^(10\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[01])\.)/{print; exit}')"
[[ -n "$LAN_IP" ]] || fail "Keine private LAN-IPv4 automatisch gefunden. Webserver wurde nicht eingerichtet."
ok "Webadmin vorbereitet; LAN-IP: $LAN_IP"

step "ItomiScan-Dienste"
if [[ ! -e /etc/systemd/system/itomiscan-web.service ]]; then bash "$PROJECT/setup-web.sh" "$USER_NAME" "$LAN_IP"; else systemctl restart itomiscan-web.service; fi
if [[ ! -e /etc/systemd/system/itomiscan-delivery.service ]]; then bash "$PROJECT/setup-delivery.sh" "$USER_NAME"; else systemctl restart itomiscan-delivery.service; fi
bash "$PROJECT/setup-printing.sh" "$USER_NAME"
ok "Web, Zustellung und CUPS eingerichtet."

step "Funktionstests"
FAILURES=0
check(){ local label="$1"; shift; if "$@" >/dev/null 2>&1; then ok "$label"; else echo "[FEHLER] $label"; FAILURES=$((FAILURES+1)); fi; }
check "Python importiert ItomiScan" runuser -u "$USER_NAME" -- /usr/bin/env PYTHONPATH="$PROJECT" python3 -c 'import itomiscan'
check "CUPS ist aktiv" systemctl is-active --quiet cups.service
check "Webdienst ist aktiv" systemctl is-active --quiet itomiscan-web.service
check "Zustelldienst ist aktiv" systemctl is-active --quiet itomiscan-delivery.service
# The web server binds the private LAN address, not 127.0.0.1.
# A startup race with DHCP is reported separately from code health.
if bash -c 'exec 3<>/dev/tcp/'"$LAN_IP"'/8443' 2>/dev/null; then
  ok "HTTPS-Port 8443 auf $LAN_IP erreichbar"
else
  echo "[WARNUNG] HTTPS auf $LAN_IP:8443 derzeit nicht erreichbar; DHCP/Bindung und journalctl -u itomiscan-web pruefen."
fi
if timeout 35s runuser -u "$USER_NAME" -- scanimage -L 2>&1 | grep -Eq "^device .+ is a "; then ok "SANE erkennt mindestens einen Scanner."; else echo "[WARNUNG] SANE erkennt aktuell keinen Scanner. Hardware/USB pruefen."; fi
[[ $FAILURES -eq 0 ]] || fail "$FAILURES kritische Funktionstest(s) fehlgeschlagen. Details: $LOG"

echo
echo "=============================================="
echo "[OK] ItomiScan Beta wurde erfolgreich eingerichtet."
echo "[OK] Benutzer: $USER_NAME"
echo "[OK] Beta-Kanal: develop/1.0.0"
echo "[OK] Webadmin: https://$LAN_IP:8443"
echo "[OK] Log: $LOG"
echo "[INFO] Plymouth wird separat nach Prüfung eingerichtet. Boot-Konfiguration unverändert."
echo "[INFO] Naechster Schritt: Neustart und anschliessend Bootanalyse."
echo "=============================================="
