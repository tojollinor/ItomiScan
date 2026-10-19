#!/usr/bin/env bash
# One-time explicit migration for the existing Beta 4 web service.
# The beta updater intentionally never edits systemd unit files.
set -euo pipefail
if [[ "$EUID" -ne 0 || "$#" -ne 0 ]]; then
  echo "Als root ohne Argumente ausführen." >&2
  exit 2
fi
UNIT=/etc/systemd/system/itomiscan-web.service
DROPIN=/etc/systemd/system/itomiscan-web.service.d
[[ -f "$UNIT" && ! -L "$UNIT" ]] || {
  echo "Erwarteter Webdienst fehlt oder ist ein Symlink." >&2; exit 3;
}
grep -Fq 'User=administrator' "$UNIT" || {
  echo "Unerwarteter Webdienst-Benutzer, keine Änderung." >&2; exit 3;
}
grep -Fq 'ExecStart=/usr/bin/python3 -m itomiscan.web.server ' "$UNIT" || {
  echo "Unerwarteter Webdienst, keine Änderung." >&2; exit 3;
}
grep -Fq 'PrivateTmp=yes' "$UNIT" || {
  echo "Abweichende Service-Konfiguration, bitte manuell prüfen." >&2; exit 3;
}
if [[ -e "$DROPIN/20-kiosk-x11.conf" ]]; then
  echo "Migration existiert bereits. Nichts verändert."
  exit 0
fi
# Xorg listens on /tmp/.X11-unix/X0. A service-private /tmp hides it.
# Keep every other sandbox setting; x11vnc remains loopback-only/on-demand.
install -d -o root -g root -m 0755 "$DROPIN"
TEMP="$(mktemp "$DROPIN/.20-kiosk-x11.XXXXXX")"
trap 'rm -f "$TEMP"' EXIT
printf '[Service]\nPrivateTmp=no\n' >"$TEMP"
chmod 0644 "$TEMP"
mv -n "$TEMP" "$DROPIN/20-kiosk-x11.conf"
systemctl daemon-reload
echo "Service-Drop-in eingerichtet. Der neue Wert greift nach Dienstneustart."
echo "Jetzt im Wartungsfenster: systemctl restart itomiscan-web.service"
