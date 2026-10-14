# ItomiScan 1.0.0 Beta: Installations- und Freigabecheck

**Status:** Release-Kandidat, keine Gerätefreigabe. Der Entwicklungszweig ist `develop/1.0.0`. `main` bleibt unverändert.

## Installation (noch nicht auf dem N1800 abgenommen)

Voraussetzungen: Debian 12 bookworm i386, SSH, Netzwerkzugriff, vorhandener normaler Linux-Benutzer, mindestens 512 MiB freier Speicher. Die Installation richtet einen Kiosk-Autologin, HTTPS-Webadministration, Zustelldienst und lokale CUPS-Konfiguration ein. Vorhandene Programmdateien werden gesichert. Die Webadmin-Passwortvergabe ist interaktiv.

```bash
curl -fL https://raw.githubusercontent.com/tojollinor/ItomiScan/develop/1.0.0/install-beta.sh -o /tmp/itomiscan-beta-install.sh
sudo bash /tmp/itomiscan-beta-install.sh --user administrator
```

**Nicht ungeprüft auf produktiv genutzten Geräten ausführen.** Die Beta ersetzt vorhandene Dateien in `~/ItomiScan`; die Sicherung wird im Benutzer-Home angelegt. Der Installer aktiviert die Anmeldung auf tty1 und die Dienste. Die Erstinstallation und die Wiederholung des Installers benötigen einen echten Gerätetest.

## Boot-Splash (getrennt, optional)

`setup-boot-splash.sh` installiert Plymouth und verändert GRUB-Parameter einschließlich `GRUB_TIMEOUT=0`. Das kann bei Fehlkonfiguration die Wiederherstellung erschweren. Vor dem Ausführen physischen Konsolenzugang und einen alternativen Bootweg sicherstellen. Die Skriptausführung kann auf dem Atom N270 wegen `update-initramfs` mehrere Minuten dauern. Das Skript erzeugt Backups unter `/var/lib/itomiscan/boot-backups/`.

`restore-boot-splash.sh BACKUPORDNER` stellt die gesicherten Einstellungen wieder her. Die Wiederherstellung ist ebenfalls noch nicht am Gerät getestet.

## Freigabekriterien

- [ ] Debian-12-i386-Paketinstallation und Kioskstart auf dem N1800 erfolgreich
- [ ] Boot ohne GRUB-Wartepause, Splash und Übergang zur GUI praktisch geprüft
- [ ] SANE-Erkennung, Mehrseiten-ADF und Duplex-Reihenfolge geprüft
- [ ] Fehlerfälle Papier leer, Stau, Doppeleinzug und Abbruch geprüft
- [ ] Dokumentenübersicht: drehen, löschen, sortieren, erneut scannen, Leerseiten prüfen
- [ ] PDF nach Freigabe, Bildexport und korrekte Seitenreihenfolge geprüft
- [ ] Webadmin, Druck und mindestens ein Zustellziel praktisch geprüft
- [ ] Installations-Wiederholung, Sicherung und Boot-Rückweg geprüft
- [ ] Automatisierte Syntax-/Regressionstests mit protokolliertem Ergebnis

## Bekannte Einschränkungen

- Update-Schaltfläche prüft den Beta-Kanal, installiert aber keine Updates direkt aus der GUI.
- Die installierte Revision wird über GitHub abgefragt; Archivdownload und Abfrage können bei parallelen Commits auseinanderfallen. Deshalb nicht als kryptografisch verifizierte Versionsfixierung betrachten.
- Das Boot-Splash-Skript wird vom Installer absichtlich nicht automatisch ausgeführt.
- Ein optisch lückenloser Plymouth-Xorg-Übergang ist noch nicht nachgewiesen.
- Die Entwicklungsdokumentation im README enthält ältere Beschreibungen; dieser Freigabecheck beschreibt die aktuellen Einschränkungen.
- Bis zum erfolgreichen Abschluss der Kriterien ist die Beta **nicht freigegeben**.


## Block 2/4: Bedienung und Hardware (Entwicklungsstand)

Code auf `develop/1.0.0` umgesetzt, Hardwareabnahme steht aus:

- [x] Bildschirmtastatur zentriert, Fokus und Tastenabstände für 1024×768 angepasst
- [x] Zieh-Scrollen auf freien Flächen der Scanoptionen und lokal begrenztes Mausrad
- [x] Ausschalten aus dem Scanheader entfernt, auch nach Berechtigungswechsel
- [x] Dokument-Abbruch als zentrierter Zwei-Schaltflächen-Dialog
- [x] Scannerfehlerdialog an Bildschirmgröße angepasst und zentriert
- [x] Logo in Scanheader ergänzt, vorhandener Scanbalken wird bei aktiver Arbeit animiert
- [x] SANE-Hardwarediagnose und vorsichtiges 300-DPI-Testprofil ergänzt
- [ ] N1800-Gerätetest: Bildschirm wird bei Texteingabe nicht leer
- [ ] N1800-Gerätetest: Zieh-Scrollen ohne versehentliche Eingabe
- [ ] N1800-Gerätetest: Scanbalkenanimation und Dialoge
- [ ] N1800-Gerätetest: SANE-Testprofil, Duplex, Doppeleinzug und Optionen

Die Checkboxen für Codeänderungen sind **keine** Testfreigabe. Neustart ist weiterhin nicht freigeschaltet, solange Systemberechtigungen fehlen. Eine automatische Installation aus der GUI ist nicht freigegeben.


## Block 3/4: Ziele und Drucker (Entwicklungsstand)

- [x] Scanziel-Auswahl als Vollbildseite statt Dialog; lokales Speichern, Paperless, Netzwerk, E-Mail, USB nach Berechtigung
- [x] Konfigurierte Zustellziele ebenfalls als Vollbildseite; fehlende Ziele melden Webadministrationsbedarf
- [x] Kopieransicht bleibt Vollbild; bestehende CUPS-Druckerwahl und Druckeinstellungen erhalten, Logo ergänzt
- [x] Webadmin: „Drucker hinzufügen“, Adresse bearbeiten, entfernen, Testdruck und Standarddrucker setzen
- [x] CUPS-Geräteerkennung über `lpinfo -v` und Vorschläge für Drucker-URIs
- [x] URI-Prüfung für IPP/IPPS, socket/RAW 9100, LPD und USB; Regressionstests eingecheckt
- [ ] Regressionstests tatsächlich ausführen und Ergebnis dokumentieren
- [ ] N1800: Druckererkennung und Rechte von `lpadmin`, `lpinfo`, `lpstat` testen
- [ ] N1800: PDF-Testdruck auf realem Brother-Drucker bestätigen
- [ ] N1800: Scanziele und Berechtigungen, Zustellwarteschlange sowie Kopierablauf prüfen

**Einschränkung:** Für socket/RAW, LPD und USB verwendet die derzeitige CUPS-Installation eine RAW-Warteschlange. Diese nimmt nur druckerfertige Daten entgegen; ein PDF wird dadurch nicht automatisch in eine für den Drucker verständliche Sprache umgewandelt. Ein geeigneter Druckertreiber bzw. CUPS-Filter ist für zuverlässigen Ausdruck erforderlich. IPP Everywhere funktioniert nur bei kompatiblen Geräten. Ohne diesen Nachweis gilt die Mehrprotokoll-Druckunterstützung noch nicht als praktisch abgenommen. Keine Behauptung, dass alle Brother-Modelle treiberlos unterstützt werden.
