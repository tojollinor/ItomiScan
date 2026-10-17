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

### A3. Neue Bootgrafiken unabhängig vom laufenden Theme erzeugen

Der originale N1800-Plymouth-Hook nutzt `/usr/sbin/plymouth-set-default-theme` und kopiert **das komplette ausgewählte Theme-Verzeichnis** in das von `mkinitramfs` erzeugte Abbild. Auf dem N1800 ist dies aktuell das alte statische `itomiscan`-Theme. `MODULES=dep` wird vom Hook ausdrücklich berücksichtigt; die i915-Treiberübernahme benötigt weiterhin den praktischen Abgleich des erzeugten Kandidaten.

Neu: `stage-boot-splash-assets.sh` bietet `check` (nur lesend) und `stage` (erstellt die neuen Grafikdateien **ausschließlich in einem freien Arbeitsverzeichnis**). Das Skript erzeugt animiertes und statisches Theme gemeinsam aus `itomiscan/branding.py`. Es verändert keine bestehenden Plymouth-/Bootdateien, keine GRUB-Konfiguration und keine Initramfs. Es verlangt, dass der ItomiScan-Quellbaum und Python Pillow auf dem ausführenden Rechner vorhanden sind.

**Aktualisierte Trennung:** `prepare-boot-candidate.sh` liest neue animierte Dateien über `ITOMISCAN_SPLASH_STAGE` aus dem separaten Arbeitsverzeichnis. Es kopiert sie in eine **temporäre** Initramfs-Tools-Konfiguration; ein zusätzlicher lokaler Hook überschreibt nur im entstehenden Abbild die Kopie des bisherigen Plymouth-Themes. Die Dateien unter `/usr/share/plymouth/themes/itomiscan` auf dem Gerät bleiben unverändert. Das Verfahren ist im Entwicklungszweig implementiert, aber der echte `mkinitramfs`-Hook-Lauf auf dem N1800 ist noch **nicht praktisch bestätigt**. Die Initramfs muss nach dem Build auch inhaltlich geprüft werden, nicht nur anhand von Dateinamen. `build`, GRUB-`prepare` und `once` dürfen erst nach dieser Abnahme und mit Rückfallzugriff ausgeführt werden.

### B. Geschützter Kandidaten-Build (im Entwicklungszweig vorbereitet)

Das neue Skript `prepare-boot-candidate.sh` bietet genau zwei explizite Betriebsarten: `check` (nur lesend) und `build` (erst nach ausdrücklicher Freigabe, nur vor Ort). Das Skript wird **nicht** von einem Installer oder dem Updateknopf aufgerufen.

`check` prüft Kernel und Root-UUID, BIOS-Modus, die unveränderten vorhandenen Initramfs-Dateien, den freien Kandidatenpfad und die Vollständigkeit des neuen Plymouth-Themes einschließlich Scanlinien-Animation. Die Prüfung setzt ein separat erzeugtes Theme-Arbeitsverzeichnis per `ITOMISCAN_SPLASH_STAGE` voraus. Die bestehende alte Installation ist kein Ablehnungsgrund; der Standard-Boot bleibt unverändert.

`build` nutzt Debian Bookworms `mkinitramfs -d` mit einer **temporären Kopie** von `/etc/initramfs-tools` und `MODULES=dep`. Das unveränderte alte Host-Theme muss weiterhin ausgewählt sein; der zusätzliche temporäre Hook überlagert dessen Kopie im Initramfs-Build mit dem gestagten neuen Theme. Die erzeugte Datei wird erst nach `lsinitramfs`-Prüfung von Treiber und Theme als separate Datei veröffentlicht. Ein zweifacher Größenanstieg gegenüber der bisherigen DEP-Initramfs führt zum Abbruch. GRUB, die 53-MB-Originaldatei und die bewährte 16-MB-DEP-Datei bleiben unverändert.

Kandidatenpfad: `/boot/initrd.img-6.1.0-50-686-pae-itomiscan-splash-test`. Der Build erfolgt **nicht durch diesen Chat** und ist derzeit auch nicht freigegeben. Vor `build` müssen die korrekte Ausführungsreihenfolge des zusätzlichen Hooks, der temporäre `DESTDIR`-Overlay und die Optimierungskonfiguration im kontrollierten Test nachgewiesen werden. Eine neu gebaute DEP-Initramfs ist nicht automatisch gleichwertig mit der früheren 16-MB-Datei.

**Nur lesende Vorprüfung am Gerät (erst nach dem Update des Diagnosecodes):**

```bash
curl -fL --retry 2 \
  https://raw.githubusercontent.com/tojollinor/ItomiScan/develop/1.0.0/prepare-boot-candidate.sh \
  -o /tmp/prepare-boot-candidate.sh
bash -n /tmp/prepare-boot-candidate.sh
bash /tmp/prepare-boot-candidate.sh check
```

Die Befehlsvariante `build` **nicht** ausführen, bevor Theme, Hooks und Rückfallplan am Gerät separat geprüft wurden.



Erst nach A eine **neue separate Kandidaten-Datei** erstellen. Nicht überschreiben:
- die originale 53-MB-Initramfs,
- die bereits getestete 16-MB-DEP-Initramfs,
- den bestehenden Standard-GRUB-Eintrag.

Die Kandidaten-Initramfs soll die benötigten Plymouth-Theme-Dateien und nur die für das Gerät erforderlichen frühen Grafikmodule enthalten. `i915`, DRM und Framebuffer-Unterstützung werden anhand von A ausgewählt. Keine Annahme, dass das bloße Hinzufügen von `i915` automatisch den frühen Bildwechsel beseitigt.

Danach separaten GRUB-Testeintrag mit eindeutiger ID erstellen. Vor Teststart GRUB-Syntax, Initramfs-Inhalt, Originaldateien, Einmalwahl und physische Rückfallmöglichkeit kontrollieren. Keine permanente Standardumstellung vor erfolgreicher Abnahme.

### B2. Separater GRUB-Testeintrag und einmaliger Boot (vorbereitet, nicht aktiviert)

Das eigenständige `test-boot-splash-candidate.sh` bietet drei ausdrücklich getrennte Modi. `status` ist nur lesend; `prepare` sichert `40_custom`, `grub.cfg` und `/etc/default/grub`, prüft Kernel, Root-UUID, Kandidaten-Datei, animiertes Theme und bestehende GRUB-Konfiguration und ergänzt nur einen neuen Testeintrag. `once` plant ausschließlich den nächsten Start via `grub-reboot` vor; das Skript löst niemals selbst einen Neustart aus.

Der Testeintrag lautet `itomiscan-splash-candidate-test` und zeigt auf `/boot/initrd.img-6.1.0-50-686-pae-itomiscan-splash-test`. Als erwartete Bootvorgabe bleibt **`GRUB_DEFAULT="itomiscan-initramfs-dep-test"`**, mit der vorhandenen Wartezeit **`GRUB_TIMEOUT=2`**. Das Skript akzeptiert bewusst weder einen veränderten Kernel noch eine abweichende Standardauswahl. Besteht bereits eine GRUB-Einmalwahl, wird nichts überschrieben. Vor `prepare` muss die neue Kandidaten-Initramfs tatsächlich erzeugt und kontrolliert sein.

Nur `status` darf im normalen Betrieb ohne Wartungsfreigabe aufgerufen werden:

```bash
curl -fL --retry 2 \
  https://raw.githubusercontent.com/tojollinor/ItomiScan/develop/1.0.0/test-boot-splash-candidate.sh \
  -o /tmp/test-boot-splash-candidate.sh
bash -n /tmp/test-boot-splash-candidate.sh
bash /tmp/test-boot-splash-candidate.sh status
```

**Nicht jetzt ausführen:** `prepare` und `once`. Die beiden Modi benötigen eine bewusst freigegebene Wartung direkt am Gerät und einen physischen Rettungsweg. Auch nach erfolgreicher Einmalwahl ist der automatische Rückfall auf die 16-MB-Standarddatei nur für einen normalen erfolgreichen GRUB-Neustart zu erwarten; bei einem Hänger vor dem Rückfall gibt es keine automatische Rettung.

**Abnahmeprotokoll am echten N1800:** Beginn und Ende des blinkenden Cursors beobachten, erstes farbiges Logo, tatsächliche Scanlinien-Animation, Übergang von statischer zu dynamischer Meldung, sichtbare Linux-Logintexte, Dauer einer schwarzen Umschaltung, Start der Tk-Oberfläche und PIN, Scannen/Touch/Fronttaste sowie Linux-/GUI-Startzeiten dokumentieren. Nach erfolgreichem Test GRUB-Standard und tatsächliche Initramfs erneut lesend überprüfen. Erst danach getrennt über dauerhafte Änderungen entscheiden.

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
