#!/usr/bin/env bash
# ItomiScan boot-splash candidate preflight, intentionally READ-ONLY.
# Checks N1800 facts before any separate image is built.
set -uo pipefail
kernel="6.1.0-50-686-pae"
uuid="5b4ffd28-6d80-43e9-bb65-bb62d0b845ac"
original="/boot/initrd.img-${kernel}"
dep="/boot/initrd.img-${kernel}-dep-test"
candidate="/boot/initrd.img-${kernel}-itomiscan-splash-test"
problems=0
warn() { printf '[OFFEN] %s\n' "$*"; problems=$((problems+1)); }
good() { printf '[OK] %s\n' "$*"; }
echo "=== ItomiScan Kandidaten-Vorpruefung (ausschliesslich lesend) ==="
if [[ "$(uname -r)" == "$kernel" ]]; then good "Kernel ${kernel}"; else warn "Kernel abweichend: $(uname -r)"; fi
if [[ ! -d /sys/firmware/efi ]]; then good "BIOS/Legacy"; else warn "UEFI statt BIOS"; fi
if command -v findmnt >/dev/null 2>&1; then
  current="$(findmnt -nro UUID / 2>/dev/null || true)"
  [[ "$current" == "$uuid" ]] && good "Root-UUID korrekt" || warn "Root-UUID abweichend: $current"
else warn "findmnt fehlt"; fi
for file in "$original" "$dep"; do
  if [[ -s "$file" ]]; then
    good "Vorhandene Initramfs: $file ($(stat -c %s "$file" 2>/dev/null) Byte)"
  else warn "Vorhandene Initramfs fehlt: $file"; fi
done
if [[ -e "$candidate" ]]; then
  warn "Kandidaten-Ziel bereits belegt: $candidate; niemals ueberschreiben"
else good "Separater Kandidatenpfad frei: $candidate"; fi
if [[ -r /etc/default/grub ]]; then
  grep -E '^(GRUB_DEFAULT|GRUB_TIMEOUT|GRUB_TIMEOUT_STYLE|GRUB_GFXMODE|GRUB_GFXPAYLOAD_LINUX)=' /etc/default/grub || true
else warn "GRUB-Vorgaben nicht lesbar"; fi
if command -v lsinitramfs >/dev/null 2>&1 && [[ -s "$dep" ]]; then
  contents="$(lsinitramfs "$dep" 2>/dev/null || true)"
  for item in 'kernel/drivers/gpu/drm/i915/i915.ko' 'usr/share/plymouth/themes/itomiscan/itomiscan.script'; do
    if grep -Fq "$item" <<< "$contents"; then good "DEP enthaelt $item"; else warn "DEP enthaelt nicht $item"; fi
  done
else warn "Initramfs-Inhaltspruefung nicht moeglich"; fi
echo
echo "Plymouth-Theme auf dem Root-Dateisystem:"
for dir in /usr/share/plymouth/themes/itomiscan /usr/share/plymouth/themes/itomiscan-static; do
  if [[ -d "$dir" ]]; then
    printf '%s: ' "$dir"
    find "$dir" -maxdepth 1 -type f -printf '%f ' 2>/dev/null
    printf '\n'
  else echo "$dir: fehlt"; fi
done
echo
echo "Benannte Plymouth-Abhaengigkeiten:"
for cmd in mkinitramfs update-initramfs plymouth-set-default-theme; do
  command -v "$cmd" >/dev/null 2>&1 && good "$cmd vorhanden" || warn "$cmd fehlt"
done
printf '\nFuer einen Kandidaten fehlen noch %s geklaerte Voraussetzung(en)/Hinweise.\n' "$problems"
echo "Keine Dateien angelegt. Keine Initramfs erzeugt. Kein GRUB-Eintrag geschrieben."
echo "Naechster Schritt: isolierte Erzeugung erst nach Abgleich der Boot-Hooks und Theme-Inhalte."
