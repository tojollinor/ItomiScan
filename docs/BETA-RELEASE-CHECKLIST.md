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
