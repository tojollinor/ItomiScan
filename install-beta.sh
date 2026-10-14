#!/usr/bin/env bash
# ItomiScan 1.0.0 beta deployment for Debian 12.
# Usage: sudo bash install-beta.sh --user USERNAME
set -Eeuo pipefail
umask 022
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
apt-get install -y --no-install-recommends xserver-xorg-core xserver-xorg-input-libinput xserver-xorg-video-intel xinit x11-xserver-utils xauth python3 python3-tk python3-pil python3-pil.imagetk sane-utils img2pdf git ca-certificates fonts-dejavu-core sudo openssl cups cups-client cups-filters smbclient
ok "Basispakete installiert."

step "Beta-Code"
[[ ! -e "$PROJECT" || -d "$PROJECT/.git" ]] || fail "$PROJECT existiert, ist aber kein Git-Repository."
if [[ ! -d "$PROJECT/.git" ]]; then runuser -u "$USER_NAME" -- git clone https://github.com/tojollinor/ItomiScan.git "$PROJECT"; fi
[[ -z "$(runuser -u "$USER_NAME" -- git -C "$PROJECT" status --porcelain)" ]] || fail "Lokale Aenderungen in $PROJECT vorhanden. Bitte zuerst sichern."
runuser -u "$USER_NAME" -- git -C "$PROJECT" fetch --prune origin
if runuser -u "$USER_NAME" -- git -C "$PROJECT" show-ref --verify --quiet refs/heads/develop/1.0.0; then
 runuser -u "$USER_NAME" -- git -C "$PROJECT" checkout develop/1.0.0
else
 runuser -u "$USER_NAME" -- git -C "$PROJECT" checkout -b develop/1.0.0 --track origin/develop/1.0.0
fi
runuser -u "$USER_NAME" -- git -C "$PROJECT" reset --hard origin/develop/1.0.0
/usr/bin/python3 -m compileall -q "$PROJECT/app.py" "$PROJECT/itomiscan"
ok "develop/1.0.0 ausgecheckt und Python-Code kompiliert."

step "Kiosk und Scannerrechte"
bash "$PROJECT/setup-shutdown.sh" "$USER_NAME"
chmod +x "$PROJECT/start-kiosk.sh"
runuser -u "$USER_NAME" -- git -C "$PROJECT" config core.filemode false
getent group scanner >/dev/null && usermod -aG scanner "$USER_NAME"
PROFILE="$USER_HOME/.profile"; [[ -f "$USER_HOME/.bash_profile" ]] && PROFILE="$USER_HOME/.bash_profile"
if ! grep -q '# ITOMISCAN_KIOSK_START' "$PROFILE" 2>/dev/null; then
 cat >>"$PROFILE" <<'KIOSK'

# ITOMISCAN_KIOSK_START
if [ -z "$DISPLAY" ] && [ "$(tty)" = "/dev/tty1" ]; then
  startx "$HOME/ItomiScan/start-kiosk.sh" -- :0 vt1
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
if [[ ! -e /etc/systemd/system/itomiscan-web.service ]]; then bash "$PROJECT/setup-web.sh" "$USER_NAME" "$LAN_IP"; else systemctl enable --now itomiscan-web.service; fi
if [[ ! -e /etc/systemd/system/itomiscan-delivery.service ]]; then bash "$PROJECT/setup-delivery.sh" "$USER_NAME"; else systemctl enable --now itomiscan-delivery.service; fi
bash "$PROJECT/setup-printing.sh" "$USER_NAME"
ok "Web, Zustellung und CUPS eingerichtet."

step "Funktionstests"
FAILURES=0
check(){ local label="$1"; shift; if "$@" >/dev/null 2>&1; then ok "$label"; else echo "[FEHLER] $label"; FAILURES=$((FAILURES+1)); fi; }
check "Python importiert ItomiScan" runuser -u "$USER_NAME" -- /usr/bin/env PYTHONPATH="$PROJECT" python3 -c 'import itomiscan'
check "CUPS ist aktiv" systemctl is-active --quiet cups.service
check "Webdienst ist aktiv" systemctl is-active --quiet itomiscan-web.service
check "Zustelldienst ist aktiv" systemctl is-active --quiet itomiscan-delivery.service
check "HTTPS-Port 8443 lauscht" bash -c 'exec 3<>/dev/tcp/'"$LAN_IP"'/8443'
if scanimage -L 2>&1 | grep -qi 'device'; then ok "SANE erkennt mindestens einen Scanner."; else echo "[WARNUNG] SANE erkennt aktuell keinen Scanner. Hardware/USB pruefen."; fi
[[ $FAILURES -eq 0 ]] || fail "$FAILURES kritische Funktionstest(s) fehlgeschlagen. Details: $LOG"

echo
echo "=============================================="
echo "[OK] ItomiScan Beta wurde erfolgreich eingerichtet."
echo "[OK] Benutzer: $USER_NAME"
echo "[OK] Branch: develop/1.0.0"
echo "[OK] Webadmin: https://$LAN_IP:8443"
echo "[OK] Log: $LOG"
echo "[INFO] Noch NICHT enthalten: GRUB-Bootoptimierung und Plymouth."
echo "[INFO] Naechster Schritt: Neustart und anschliessend Bootanalyse."
echo "=============================================="
