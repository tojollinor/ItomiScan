#!/usr/bin/env bash
# Read-only diagnostic for ItomiScan early graphics, Plymouth and selected initramfs.
# This script does not change GRUB, initramfs, Plymouth, services or the system.
set -u

KERNEL="$(uname -r)"
GRUB_DEFAULT_VALUE="$(sed -nE 's/^GRUB_DEFAULT="?([^"]*)"?$/\1/p' /etc/default/grub 2>/dev/null | head -n 1)"
NEXT_ENTRY=""
if command -v grub-editenv >/dev/null 2>&1; then
  NEXT_ENTRY="$(grub-editenv /boot/grub/grubenv list 2>/dev/null | sed -n 's/^next_entry=//p' | head -n 1)"
fi
SELECTED="${NEXT_ENTRY:-$GRUB_DEFAULT_VALUE}"
NORMAL_INITRD="/boot/initrd.img-${KERNEL}"
DEP_INITRD="/boot/initrd.img-${KERNEL}-dep-test"
ACTIVE_INITRD="$NORMAL_INITRD"
case "$SELECTED" in
  itomiscan-initramfs-dep-test) ACTIVE_INITRD="$DEP_INITRD" ;;
  0|"") ACTIVE_INITRD="$NORMAL_INITRD" ;;
  *)
    if grep -Fq "initrd /boot/initrd.img-${KERNEL}-dep-test" /boot/grub/grub.cfg 2>/dev/null &&
       grep -Fq "menuentry" /boot/grub/grub.cfg 2>/dev/null; then
      echo "Hinweis: GRUB-Auswahl '$SELECTED' nicht automatisch auf eine Initramfs abbildbar."
      echo "Beide bekannten Initramfs-Dateien werden geprüft."
    fi
    ACTIVE_INITRD=""
    ;;
esac

echo "===== ItomiScan: fruehe Grafik-/Plymouth-Diagnose (NUR LESEND) ====="
echo
echo "1. System / Bootmodus"
uname -a
if [[ -d /sys/firmware/efi ]]; then
  echo "Bootmodus: UEFI"
else
  echo "Bootmodus: BIOS/Legacy (kein /sys/firmware/efi)"
fi
printf 'Kernel-Kommandozeile: '
cat /proc/cmdline 2>/dev/null || true

echo
echo "2. GRUB-Grafikeinstellungen"
grep -E '^(GRUB_DEFAULT|GRUB_TIMEOUT|GRUB_TIMEOUT_STYLE|GRUB_GFXMODE|GRUB_GFXPAYLOAD_LINUX|GRUB_TERMINAL|GRUB_CMDLINE_LINUX_DEFAULT)=' /etc/default/grub 2>/dev/null || true
printf 'GRUB_DEFAULT: %s\n' "${GRUB_DEFAULT_VALUE:-nicht lesbar}"
printf 'GRUB next_entry: %s\n' "${NEXT_ENTRY:-keine}"
printf 'Voraussichtlich gewaehlter Eintrag: %s\n' "${SELECTED:-nicht lesbar}"
printf 'Zu pruefende Initramfs: %s\n' "${ACTIVE_INITRD:-nicht eindeutig; beide Dateien pruefen}"

echo
echo "3. Plymouth-Version und aktives Theme"
if command -v plymouth >/dev/null 2>&1; then plymouth --version 2>&1 || true; else echo "plymouth CLI nicht installiert"; fi
if command -v plymouth-set-default-theme >/dev/null 2>&1; then
  printf 'Theme: '
  plymouth-set-default-theme 2>&1 || true
else
  echo "plymouth-set-default-theme nicht verfuegbar"
fi
THEME_DIR="/usr/share/plymouth/themes/itomiscan"
STATIC_THEME_DIR="/usr/share/plymouth/themes/itomiscan-static"
if [[ -d "$THEME_DIR" ]]; then
  ls -lah "$THEME_DIR"
  for f in itomiscan.plymouth itomiscan.script; do
    if [[ -f "$THEME_DIR/$f" ]]; then
      echo "--- $THEME_DIR/$f (relevante Zeilen) ---"
      grep -nE 'ImageDir|ScriptFile|SetRefreshFunction|SetMessageFunction|SetHideMessageFunction|BOOT_STATUS|System wird gestartet' "$THEME_DIR/$f" 2>/dev/null | head -30 || true
    fi
  done
else
  echo "ItomiScan-Plymouth-Theme-Verzeichnis fehlt: $THEME_DIR"
fi
if [[ -d "$STATIC_THEME_DIR" ]]; then
  echo "--- Statischer Fallback: $STATIC_THEME_DIR ---"
  ls -lah "$STATIC_THEME_DIR"
  grep -nE 'ImageDir|ScriptFile|static-boot\.png' "$STATIC_THEME_DIR/itomiscan-static.plymouth" "$STATIC_THEME_DIR/itomiscan-static.script" 2>/dev/null || true
else
  echo "Statisches Fallback-Theme fehlt: $STATIC_THEME_DIR"
fi

echo
echo "4. Grafiktreiber und Framebuffer"
if command -v lsmod >/dev/null 2>&1; then
  lsmod | grep -E '^(i915|drm|drm_kms_helper|fbcon|vesafb|simpledrm|efifb|intel_agp)' || echo "Kein passender Grafik-/Framebuffer-Treiber in lsmod gelistet (built-in Treiber erscheinen dort nicht)."
fi
for d in /sys/class/graphics/fb*; do
  [[ -e "$d" ]] || continue
  echo "--- $d ---"
  for f in name virtual_size bits_per_pixel modes; do
    if [[ -r "$d/$f" ]]; then printf '%s: ' "$f"; cat "$d/$f"; fi
  done
done
if command -v lspci >/dev/null 2>&1; then
  lspci -nnk 2>/dev/null | grep -A4 -B1 -Ei 'VGA compatible controller|Display controller|Intel.*945GSE|Integrated Graphics' || true
fi

echo
echo "5. Bootmeldungen zu Grafik und Plymouth"
if command -v journalctl >/dev/null 2>&1; then
  journalctl -b -k -o short-monotonic --no-pager 2>/dev/null |
    grep -Ei 'i915|drm|framebuffer|fbcon|vesa|plymouth|fb0|LVDS|firmware|simpledrm' |
    tail -80 || echo "Keine passenden Kernelmeldungen lesbar/gefunden."
fi
systemctl --no-pager --full status plymouth-start.service plymouth-quit.service plymouth-quit-wait.service 2>&1 | head -90 || true

echo
echo "6. Initramfs-Inhalte (nur auflisten)"
for image in "$NORMAL_INITRD" "$DEP_INITRD"; do
  [[ -f "$image" ]] || continue
  echo "--- $image ---"
  ls -lh "$image"
  if command -v lsinitramfs >/dev/null 2>&1; then
    listing="$(lsinitramfs "$image" 2>/dev/null | grep -Ei 'plymouth|itomiscan|i915\.ko|drm\.ko|fbcon|vesafb|simpledrm|initramfs-tools/hooks' | head -100 || true)"
    if [[ -n "$listing" ]]; then
      printf '%s\n' "$listing"
    else
      echo "Keine passenden Plymouth-/ItomiScan-/Grafikdateien in der gefilterten Liste gefunden."
    fi
  else
    echo "lsinitramfs nicht installiert; Inhalte nicht geprueft."
  fi
done
if [[ -n "$ACTIVE_INITRD" ]]; then
  echo
  echo "7. Bewertung der ausgewaehlten Initramfs"
  if [[ -f "$ACTIVE_INITRD" ]]; then
    echo "Auswahlkandidat vorhanden: $ACTIVE_INITRD"
    if command -v lsinitramfs >/dev/null 2>&1; then
      lsinitramfs "$ACTIVE_INITRD" 2>/dev/null |
        grep -Ei 'usr/share/plymouth/themes/itomiscan|itomiscan\.script|i915\.ko|drm\.ko|fbcon' |
        head -80 || true
    fi
  else
    echo "Auswahlkandidat fehlt: $ACTIVE_INITRD"
  fi
fi

echo
echo "===== Diagnose abgeschlossen. Es wurden keine Dateien oder Einstellungen geaendert. ====="
