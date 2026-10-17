# ItomiScan – Start, Scannerbereitschaft und Splash (Stand: 16.10.2026)

**Entwicklungsstand `develop/1.0.0`.** Neue Beta-Funktionen sind auf GitHub implementiert und durch CI geprüft; sie sind **nicht automatisch auf dem N1800 installiert oder physisch abgenommen**. `main` bleibt unberührt.

## Ablauf ab Beta-Block 5

1. Debian startet über GRUB, Kernel, Plymouth und Xorg. Die bereits vorhandenen `start-kiosk.sh`-Einstellungen begrenzen SANE auf das Fujitsu-Backend.
2. Der Tk-Kiosk baut nach dem Splash **sofort** die Hauptoberfläche auf; SANE-/Touch-Geräteerkennung blockiert diesen Übergang nicht mehr.
3. Zuletzt gespeicherte Optionen dürfen eine provisorische Darstellung ermöglichen. Sie beweisen **keine** physische Gerätebereitschaft. Die echte SANE-/Touch-Prüfung läuft im Hintergrund und liefert Ergebnisse an die Tk-Hauptschleife.
4. Bei erfolgreicher Live-Prüfung werden die Optionen aktualisiert. Ein früher Scanwunsch wird nur dann ausgeführt, sofern Profil, Rechte und Dokumentzustand beim Start erneut passen. Vorher erscheint ein abbrechbarer Hinweis.
5. Bei Scannerfehler bleibt die Oberfläche erreichbar. Ein neuer Scanwunsch startet einen erneuten Versuch. Keine automatische Zustellung eines noch nicht abgeschlossenen Dokuments.

## Durchgehendes Bootbranding

Plymouth und Tk nutzen `itomiscan/branding.py` als gemeinsame Quelle für Farben, Logo-Geometrie und Textpositionen: dunkler ItomiScan-Hintergrund, Scannerlogo, **„Itomi“ weiß und „Scan“ blau**. Die Animation bewegt die Scanlinie kontinuierlich, solange das animierte Plymouth-Theme aktiv ist; es gibt keinen künstlichen Animationstimeout.

Der frühe Plymouth-Splash startet mit der festen Meldung **„System wird gestartet …“** und „Bitte warten …“. Wenn Plymouth echte Meldungen erhält, ersetzt der Message-Callback nur die zweite Textzeile an derselben Position. Die Animation läuft unabhängig davon weiter. Sobald Xorg/Tk startet, zeigt der vorhandene Anwendungssplash seine tatsächlichen Startmeldungen.

Zusätzlich wird ein **statisches Fallback-Theme** aus denselben Farben, Grafiken und Layoutkoordinaten erzeugt. Die vollständige 1024×768-Grafik enthält eine statische Scanlinie sowie die Meldung „System wird gestartet …“. Dieses Theme kann bei Bedarf mit `ITOMISCAN_SPLASH_MODE=static` ausgewählt werden; Standard bleibt `animated`.

`setup-boot-splash.sh` ist eine separate manuelle Systemeinrichtung und kein Teil des normalen Installers oder Updateknopfs. Das Skript bewahrt jetzt die bestehende GRUB-Wartezeit und Grafikmodus-Einstellungen. **Es bricht vor Änderungen ab, wenn GRUB die separate `itomiscan-initramfs-dep-test`-Initramfs als Standard oder Einmalstart auswählt**, weil `update-initramfs -u` nur die normale Kernel-Initramfs aktualisieren würde. Daher aktuell auf dem N1800 nicht ausführen, bevor die Diagnose und ein separater Testaufbau für die DEP-Initramfs abgeschlossen sind.

Neue rein lesende Diagnose: `inspect-boot-graphics.sh`. Sie prüft BIOS/UEFI, Kernelparameter, GRUB-Grafikeinstellungen, aktives Plymouth-Theme, Intel-`i915`/Framebuffer und die Inhalte beider bekannten Initramfs-Dateien. Sie ändert weder Konfiguration noch Bootauswahl. Ein erfolgreicher Skript-/CI-Test bestätigt nicht, dass Plymouth am echten N1800 früh genug startet.

BIOS-/GRUB-Ausgaben, der frühe Kernelcursor und der Wechsel zu Xorg können hardwareabhängig weiterhin kurze Unterbrechungen verursachen. Ziel ist, den Cursor und die Login-/Konsolenmeldungen möglichst vollständig mit dem einheitlichen Splash zu verdecken. Ob GRUB/VESA eine geeignete Auflösung bereitstellt und ob `i915` früh genug initialisiert werden kann, bleibt bis zur Diagnose am Gerät offen.

## Sichere 16-MB-Initramfs, nur ausdrücklich manuell am N1800

Bekannte Umgebung: Debian 12 Bookworm i386, Kernel `6.1.0-50-686-pae`, BIOS/Legacy, Root-UUID `5b4ffd28-6d80-43e9-bb65-bb62d0b845ac`. Die originale Initramfs (53 MB) bleibt unter `/boot/initrd.img-6.1.0-50-686-pae` erhalten. Die separat vorbereitete und einmal erfolgreich gestartete Testdatei ist `/boot/initrd.img-6.1.0-50-686-pae-dep-test` (ca. 16 MB). **Dieser GitHub-Zweig enthält keine automatisch generierte Hardware-Initramfs.**

Vor einem Test: Benutzer muss vor Ort sein, physische Recovery gewährleisten, eingebaute Originaldatei/Konfiguration sichern. **Der BIOS-Watchdog ist deaktiviert; ein automatischer Rückfall kann bei Kernel-Hängern nicht garantiert werden.** Touch und Scannen nach dem letzten Einmalstart wurden noch nicht bestätigt.

Die folgenden Befehle werden nur in einem ausdrücklich freigegebenen Wartungsfenster als root ausgeführt:

```bash
cd /home/administrator/ItomiScan
bash test-dep-initramfs.sh status       # Nur lesend
bash test-dep-initramfs.sh prepare      # Test-GRUB-Eintrag vorbereiten, mit Backup
bash test-dep-initramfs.sh once         # Nur den nächsten Boot testweise auswählen
# reboot erst nach eigenständiger Prüfung und physischem Rettungsplan auslösen
```

- `prepare` ergänzt (falls noch nicht vorhanden) einen dedizierten GRUB-Testeintrag, sichert dabei `40_custom`, `grub.cfg` und `/etc/default/grub` unter `/var/lib/itomiscan/boot-backups/`, prüft generierte GRUB-Syntax. Es ersetzt **keine** Initramfs und verändert `GRUB_DEFAULT=0` nicht.
- `once` verlangt einen bereits vorhandenen Testeintrag und eine freie `next_entry`-Einmalwahl. Es führt `grub-reboot` aus, löst aber **keinen** echten Neustart aus.
- Das System sollte nach diesem einmaligen Boot wieder den unveränderten Standard laden. Nur bei erfolgreicher Abnahme wäre eine gesondert geplante permanente Umstellung überhaupt vertretbar. Bis dahin bleibt die Original-Initramfs der Standard.
- Wenn ein bereitgestellter Einmalstart doch **nicht** durchgeführt werden soll, kann root vor dem Neustart `grub-editenv /boot/grub/grubenv unset next_entry` verwenden und danach `bash test-dep-initramfs.sh status` kontrollieren.
- GRUB bei `GRUB_TIMEOUT=0` ist nicht zuverlässig über ein Tastaturmenü rettbar. Backup/physischer Recovery-Zugang müssen real vorhanden sein.

Messungen aus dem **früheren** Hardwaretest (Linux-Uptime, BIOS nicht eingeschlossen):

| Stand | Linux-Start | GUI bereit |
| --- | ---: | ---: |
| Original bei Kontrolltest | 33,215 s | 42,420 s |
| 16-MB-Initramfs-Einmaltest | 28,929 s | 38,300 s |
| Erste ursprüngliche GUI-Messung (vor SANE-Optimierung) | nicht vergleichbar | 58,190 s |

**Nicht übertragen:** Diese Werte enthalten noch **nicht** den neuen GUI-vor-SANE-Ablauf. Vor einer neuen Leistungsangabe müssen Linux-/GUI-Zeitstempel mit der neuen Beta erneut am Gerät gemessen werden.

## Praktische Abnahme nach späterer Installation

1. Kaltstart, Logo-/Splashwechsel und Bootzeit mit `systemd-analyze time` und `~/.local/state/itomiscan/boot-timing.log` messen.
2. Touch-Reaktion, PIN-Pad, Fronttaste und Hauptoberfläche prüfen.
3. Scannererkennung inklusive Optionen, früher Scanstart, Abbruch und erneutes Verbinden prüfen.
4. Duplex und mehrseitige Dokumentbearbeitung: drehen, sortieren, löschen, Leerseiten bestätigen, erneut scannen, hinzufügen, PDF-Freigabe.
5. CUPS-/Paperless-Ziele und Webadministration gesondert prüfen.
6. Nach Neustart Standard-GRUB sowie vorhandenes Original und `next_entry` prüfen. Bei Problemen Originalsystem verwenden.

Keiner dieser realen Abnahmepunkte wird allein durch GitHub Actions als bestanden ausgewiesen.
