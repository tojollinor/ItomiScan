# ItomiScan – einheitlicher früher Boot-Splash

**Status:** Code-Vorbereitung auf `develop/1.0.0`; keine Änderung am N1800 ausgeführt. Die reale Grafikinitialisierung und der Plymouth-Übergang müssen vor Ort getestet werden.

## Zielbild

1. GRUB bleibt kurz sichtbar (derzeit rund 2 Sekunden sind akzeptabel).
2. Sobald die früheste nutzbare Grafikausgabe verfügbar ist, erscheint das ItomiScan-Design: blauer/dunkelblauer Hintergrund, zentriertes Scannerlogo, „Itomi“ weiß, „Scan“ blau, darunter eine Statuszeile.
3. Die Scanlinienanimation läuft ununterbrochen, solange das animierte Theme angezeigt wird. Sie wird nicht wegen langer Startdauer künstlich gestoppt.
4. Die frühe feste Meldung lautet „System wird gestartet …“; zweite Zeile „Bitte warten …“. Wenn Plymouth eine tatsächliche Meldung erhält, wird nur die zweite Zeile am selben Platz aktualisiert.
5. Xorg/Tk übernimmt das gleiche Branding und darf seine realen Startmeldungen zeigen. Ein kurzer schwarzer Grafikmoduswechsel ist akzeptabel; sichtbare Konsolen-/Loginzeilen sollen möglichst verschwinden.
6. Falls die Animation in der frühen Phase unzuverlässig ist, kann das statische Fallback mit denselben Farben, Logo-/Textpositionen und integrierter Startmeldung gewählt werden.

## Bereits im Entwicklungszweig vorbereitet

- `itomiscan/branding.py` ist die gemeinsame Quelle für Farben und Positionen.
- Das animierte Plymouth-Theme bewegt die Scanlinie kontinuierlich und hat einen Message-Callback, der eine verfügbare Plymouth-Meldung in der bestehenden zweiten Textzeile zeigt.
- `static-boot.png` wird bei der Einrichtung in 1024×768 erzeugt; das eigenständige Theme liegt unter `/usr/share/plymouth/themes/itomiscan-static/`.
- `setup-boot-splash.sh` kann zwischen `animated` (Standard) und `static` wählen. Es bewahrt die konfigurierte GRUB-Wartezeit und Grafikmoduswerte.
- Das Setupskript verweigert die Ausführung, wenn GRUB als Standard oder Einmalstart die separate `itomiscan-initramfs-dep-test`-Datei auswählt. Der normale Befehl `update-initramfs -u` würde sonst nur die andere, nicht gestartete Initramfs aktualisieren.
- `inspect-boot-graphics.sh` ist eine ausschließlich lesende Diagnose für GRUB, Plymouth, Framebuffer, `i915` und beide Initramfs-Dateien.

## Nächster Vor-Ort-Ablauf

### A. Nur lesen und Belege sammeln

Es ist kein Git-Clone nötig. Als root auf dem N1800:

```bash
curl -fL --retry 2 \
  https://raw.githubusercontent.com/tojollinor/ItomiScan/develop/1.0.0/inspect-boot-graphics.sh \
  -o /tmp/inspect-boot-graphics.sh

bash -n /tmp/inspect-boot-graphics.sh
bash /tmp/inspect-boot-graphics.sh
```

Die vollständige Ausgabe zurückgeben. Dieser Befehl führt keinen Neustart aus und verändert keine Dateien.

Besonders prüfen:
- Wählt GRUB normal oder `itomiscan-initramfs-dep-test`?
- Enthält genau diese Initramfs die ItomiScan-Plymouth-Dateien?
- Sind `i915` und nötige DRM-/Framebuffer-Module enthalten beziehungsweise früh geladen?
- Welche Grafikauflösung und welcher Framebuffer stehen Linux zur Verfügung?
- Welche Plymouth-Theme-Dateien sind tatsächlich installiert?
- Welche Grafik-/Plymouth-Meldungen erscheinen im Kerneljournal?

### A2. Separate Kandidaten-Vorprüfung (nur lesen)

Die Geräte-Diagnose vom 17.10.2026 zeigt: GRUB startet standardmäßig `itomiscan-initramfs-dep-test`; diese 16-MB-Datei enthält `i915.ko` und Plymouth, jedoch das alte ItomiScan-Theme. `i915` initialisiert den Framebuffer erst bei etwa 14 Sekunden Linux-Uptime. Das System verwendet danach `i915drmfb` mit 1024×768. Damit ist ein fehlendes Grafikmodul **nicht** als Ursache nachgewiesen; ob der Aufruf im Initramfs-Startpfad zu spät erfolgt, bleibt offen.

Das ergänzte `preflight-boot-candidate.sh` prüft ausschließlich lesend die N1800-Hardwarekennzeichen, die vorhandenen Initramfs-Dateien, das Freisein eines neuen Kandidatenpfads und die benötigten Tools. Der Pfad für einen *späteren* Kandidaten lautet `/boot/initrd.img-6.1.0-50-686-pae-itomiscan-splash-test`. Er wird von dieser Vorprüfung weder angelegt noch verändert.

```bash
curl -fL --retry 2 \
  https://raw.githubusercontent.com/tojollinor/ItomiScan/develop/1.0.0/preflight-boot-candidate.sh \
  -o /tmp/preflight-boot-candidate.sh
bash -n /tmp/preflight-boot-candidate.sh
bash /tmp/preflight-boot-candidate.sh
```

**Offene technische Voraussetzung vor einem echten Build:** Die vollständige Debian-initramfs-tools-/Plymouth-Hook-Reihenfolge und die tatsächlich installierten Theme-Dateien am N1800 prüfen. Ein simples `mkinitramfs -o` mit den Standardwerten könnte die bisherige 16-MB-Optimierung verlieren. Ein blindes Entpacken/Neupacken der Initramfs könnte durch spezielle initramfs-Archivstrukturen den Start beschädigen. Daher kein Build oder Einmalboot allein aufgrund der bisherigen Diagnose auslösen.

### B. Kandidaten-Initramfs vorbereiten (noch nicht automatisiert)

Erst nach A eine **neue separate Kandidaten-Datei** erstellen. Nicht überschreiben:
- die originale 53-MB-Initramfs,
- die bereits getestete 16-MB-DEP-Initramfs,
- den bestehenden Standard-GRUB-Eintrag.

Die Kandidaten-Initramfs soll die benötigten Plymouth-Theme-Dateien und nur die für das Gerät erforderlichen frühen Grafikmodule enthalten. `i915`, DRM und Framebuffer-Unterstützung werden anhand von A ausgewählt. Keine Annahme, dass das bloße Hinzufügen von `i915` automatisch den frühen Bildwechsel beseitigt.

Danach separaten GRUB-Testeintrag mit eindeutiger ID erstellen. Vor Teststart GRUB-Syntax, Initramfs-Inhalt, Originaldateien, Einmalwahl und physische Rückfallmöglichkeit kontrollieren. Keine permanente Standardumstellung vor erfolgreicher Abnahme.

### C. Grafikmodus untersuchen

Wenn der Diagnosebericht keinen geeigneten frühen Grafikmodus nachweist, am GRUB-Menü lokal die verfügbaren Modi mit `videoinfo` prüfen. Erst einen tatsächlich angebotenen Modus testen, vorzugsweise 1024×768. Danach in einem separaten Testeintrag `gfxmode`/Weitergabe des Grafikmodus an den Kernel prüfen. Nicht blind `GRUB_GFXMODE=1024x768` oder `gfxpayload=keep` dauerhaft setzen: BIOS/VBE und `i915` können beim Treiberwechsel dennoch umschalten.

### D. Einmaliger physischer Starttest

Nur wenn jemand direkt am N1800 ist und Wiederherstellung gewährleisten kann:
1. Einmalig den Kandidaten-Eintrag wählen.
2. Prüfen, wann der erste Splash erscheint und ob die Scanlinie sichtbar weiterläuft.
3. Auf schwarzen Übergang, blinkenden Cursor, Login-/Konsolenzeilen und den Wechsel zu Xorg achten.
4. Kontrollieren, dass der Kiosk, Touch/PIN und ein echter Scan weiterhin funktionieren.
5. Bootzeit und GUI-Bereitschaft separat messen.
6. GRUB-Einmalwahl und verwendete Initramfs nach dem Neustart kontrollieren.

Wenn die frühe Animation nicht zuverlässig funktioniert, dieselbe Hardware-/Initramfs-Konfiguration mit `ITOMISCAN_SPLASH_MODE=static` testen. Keine automatische Rückstufung aufgrund einer Zeitüberschreitung; Animation läuft solange das animierte Theme aktiv ist.

## Sicherheit und Grenzen

- Die aktuelle N1800-Installation wird aus diesem Entwicklungszweig nicht verändert.
- Keine automatische Installation, kein Reboot, keine Änderung an `main` oder Stable.
- Das BIOS-Logo vor GRUB kann nicht durch Plymouth ersetzt werden.
- Plymouth kann erst zeichnen, wenn eine nutzbare Grafikausgabe verfügbar ist. Der Zeitraum davor kann nicht garantiert vollständig überdeckt werden.
- `quiet`, `splash`, `loglevel=3`, `systemd.show_status=false` und `vt.global_cursor_default=0` können Routineausgaben und Cursor verbergen, ersetzen aber nicht die korrekte frühe Grafikinitialisierung.
- Diagnose und CI beweisen nicht, dass die Animation oder ein VESA-/Framebuffer-Modus am echten N1800 funktioniert.
