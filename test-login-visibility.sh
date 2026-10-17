#!/usr/bin/env bash
# N1800 reversible login text reduction. No reboots or service changes.
set -Eeuo pipefail
mode="$1"
profile="/home/administrator/.profile"
hush="/home/administrator/.hushlogin"
state="/var/lib/itomiscan/login-visibility-test"
old='  startx "$HOME/ItomiScan/start-kiosk.sh" -- :0 vt1'
new='  startx "$HOME/ItomiScan/start-kiosk.sh" -- :0 vt1 >> "$HOME/itomiscan-xorg-start.log" 2>&1'
case "$mode" in status|apply|restore) ;; *) echo "Usage: bash test-login-visibility.sh status|apply|restore"; exit 2;; esac
[[ -f "$profile" ]] || { echo "Missing profile"; exit 3; }
if [[ "$mode" == status ]]; then
  echo "Read-only login test status"
  [[ -d "$state" ]] && echo "Test backup exists" || echo "No test backup"
  [[ -e "$hush" ]] && echo "Hushlogin exists" || echo "Hushlogin absent"
  grep -n "startx" "$profile" || true
  exit 0
fi
[[ $EUID -eq 0 ]] || { echo "root required"; exit 3; }
[[ ! -L "$profile" && ! -L "$hush" ]] || { echo "Unexpected symlink"; exit 3; }
[[ "$(stat -c %U:%G "$profile")" == "administrator:administrator" ]] || { echo "Profile owner differs"; exit 3; }
if [[ "$mode" == restore ]]; then
  [[ -f "$state/profile.original" && -f "$state/profile.installed.sha256" ]] || { echo "No test backup"; exit 4; }
  printf "%s  %s\n" "$(cat "$state/profile.installed.sha256")" "$profile" | sha256sum -c --status || { echo "Profile changed; manual rollback required"; exit 4; }
  [[ ! -f "$state/hush.absent" || ( -f "$hush" && ! -s "$hush" ) ]] || { echo "Hushlogin changed; manual rollback required"; exit 4; }
  cp -a "$state/profile.original" "$profile"
  [[ ! -f "$state/hush.absent" ]] || rm -- "$hush"
  mv "$state" "$state.restored.$(date -u +%Y%m%dT%H%M%SZ).$$"
  echo "Original profile restored. No restart performed."
  exit 0
fi
[[ ! -e "$state" ]] || { echo "Test already installed; abort"; exit 4; }
[[ "$(grep -Fxc "$old" "$profile")" == 1 ]] || { echo "Expected startx line not unique"; exit 4; }
install -d -m 0700 "$state"
cp -a "$profile" "$state/profile.original"
cmp "$profile" "$state/profile.original"
[[ -e "$hush" ]] || : > "$state/hush.absent"
python3 - "$profile" "$old" "$new" <<'PY'
from pathlib import Path
import sys
p = Path(sys.argv[1])
t = p.read_text()
assert t.splitlines().count(sys.argv[2]) == 1
p.write_text(t.replace(sys.argv[2], "# ITOMISCAN_LOGIN_VISIBILITY_TEST\n" + sys.argv[3], 1))
PY
chown administrator:administrator "$profile"
bash -n "$profile"
[[ -e "$hush" ]] || install -o administrator -g administrator -m 0644 /dev/null "$hush"
sha256sum "$profile" | cut -d " " -f1 > "$state/profile.installed.sha256"
echo "Login visibility test staged. No reboot or service restart performed."
echo "Rollback: bash test-login-visibility.sh restore"
