#!/usr/bin/env bash
# Reversible ItomiScan tty1/Plymouth handover test.
# check (read-only), apply (stage), restore (revert). No reboot or boot-image changes.
set -Eeuo pipefail
mode="$1"
case "$mode" in check|apply|restore) ;; echo 'Usage: bash test-silent-handover.sh check|apply|restore' >&2; exit 2;; esac
[[ $EUID == 0 ]] || { echo 'Root required' >&2; exit 2; }
p=/etc/systemd/system/plymouth-quit.service.d/90-itomiscan-retain-splash.conf
g=/etc/systemd/system/getty@tty1.service.d/90-itomiscan-quiet-getty.conf
state=/var/lib/itomiscan/silent-handover-test
fail() { echo "STOP: $*" >&2; exit 3; }
if [[ "$mode" == restore ]]; then
  [[ -f "$state/plymouth.sha" && -f "$state/getty.sha" ]] || fail 'Backup missing'
  [[ -f "$p" && -f "$g" && ! -L "$p" && ! -L "$g" ]] || fail 'Expected test files missing'
  [[ "$(sha256sum "$p" | cut -d' ' -f1)" == "$(cat "$state/plymouth.sha")" ]] || fail 'Plymouth test modified'
  [[ "$(sha256sum "$g" | cut -d' ' -f1)" == "$(cat "$state/getty.sha")" ]] || fail 'Getty test modified'
  rm -- "$p" "$g"
  systemctl daemon-reload
  mv "$state" "$state.restored.$(date +%Y%m%d%H%M%S)"
  echo 'Test removed; original service settings active for next start.'
  exit 0
fi
[[ ! -e "$state" && ! -e "$p" && ! -e "$g" ]] || fail 'Existing test files/state'
[[ "$(uname -r)" == '6.1.0-50-686-pae' && ! -d /sys/firmware/efi ]] || fail 'Unexpected platform'
psrc="$(systemctl cat --no-pager plymouth-quit.service)"
gsrc="$(systemctl cat --no-pager getty@tty1.service)"
pcmd="$(printf '%s\n' "$psrc" | grep '^ExecStart=.' | tail -1)"
gcmd="$(printf '%s\n' "$gsrc" | grep '^ExecStart=.' | tail -1)"
[[ "$pcmd" == 'ExecStart=-/usr/bin/plymouth quit' ]] || fail "Plymouth changed: $pcmd"
[[ "$gcmd" == *'/sbin/agetty --autologin administrator --noclear'* ]] || fail "Getty changed: $gcmd"
[[ "$gcmd" != *'--noissue'* ]] || fail 'Getty is already noissue'
[[ "$gcmd" != *'|'* && "$gcmd" != *';'* && "$gcmd" != *'&'* ]] || fail 'Unrecognized getty command'
newcmd="$(printf '%s\n' "$gcmd" | sed 's@/sbin/agetty @/sbin/agetty --noissue @')"
[[ "$newcmd" != "$gcmd" ]] || fail 'Cannot insert noissue'
echo "Plymouth: $pcmd"
echo "Getty: $gcmd"
echo "Getty (test): $newcmd"
if [[ "$mode" == check ]]; then echo 'Read-only check OK'; exit 0; fi
install -d -m 0755 "$(dirname "$p")" "$(dirname "$g")"
install -d -m 0700 "$(dirname "$state")"
mkdir -m 0700 "$state"
printf '%s\n' "$pcmd" > "$state/plymouth.before"
printf '%s\n' "$gcmd" > "$state/getty.before"
cat > "$p" <<'UNIT'
[Service]
ExecStart=
ExecStart=-/usr/bin/plymouth quit --retain-splash
UNIT
printf '[Service]\nExecStart=\n%s\n' "$newcmd" > "$g"
sha256sum "$p" | cut -d' ' -f1 > "$state/plymouth.sha"
sha256sum "$g" | cut -d' ' -f1 > "$state/getty.sha"
systemctl daemon-reload
if ! systemctl show plymouth-quit.service -p ExecStart --value | grep -q -- '--retain-splash' ||
   ! systemctl show getty@tty1.service -p ExecStart --value | grep -q -- '--noissue'; then
  rm -f -- "$p" "$g"
  systemctl daemon-reload
  mv "$state" "$state.failed.$(date +%Y%m%d%H%M%S)"
  fail 'Effective units mismatch; test files rolled back'
fi
echo 'Test staged successfully. No reboot or service restart.'
echo 'Restore: bash test-silent-handover.sh restore'
