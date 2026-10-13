# Start und Splash-Screen (Block 2/8)

**Status: umgesetzt auf `develop/1.0.0`, nicht auf dem echten N1800 installiert oder getestet.** `main` bleibt unverändert.

## Startablauf

1. Debian/Xorg starten wie bisher über tty1. `start-kiosk.sh` ruft jetzt `python3 -m itomiscan.gui.kiosk` auf.
2. Sofort ein dunkles ItomiScan-Startbild mit großem, leichtgewichtigem Tk-Spinner anzeigen. Die bisherige Scanneroberfläche existiert bis zur Bereitschaft **noch nicht**.
3. Im Hintergrund warten, bis das erkannte Fujitsu-USB-Touchpanel (`0430:0501`, Kernel-Eventgerät), der SANE-Scanner und die gerätespezifischen Einstellungen verfügbar sind. Der Scannerdienst läuft als normaler Benutzer. Die Anzeige nennt den aktuellen Schritt.
4. Erst danach die bisherige Tkinter-Bedienoberfläche erzeugen. Der SANE-Gerätestatus und die ermittelten Optionen werden **übernommen**, nicht erneut im GUI-Thread ermittelt.
5. Nach etwa 45 Sekunden ohne vollständige Initialisierung (plus ggf. noch laufendem, einzeln begrenztem Scanner-Aufruf) erscheint eine Fehlermeldung mit `Erneut versuchen`, `Diagnose` und `Beenden`. Die App hängt nicht endlos beim Warten.

Die Prüfung erkennt die Linux-USB-Eingabehardware; **sie beweist noch nicht die Touch-Kalibrierung oder tatsächlich erfolgreiche Berührungen**. Das muss am N1800 vor Ort verifiziert werden. Netzwerke, Paperless und Drucker blockieren den Start nicht.

## Bootvorgang vor Xorg

Optionales, bewusst **nicht automatisch ausgeführtes** Skript `setup-boot-splash.sh` für Debian 12 Bookworm: installiert den schlanken Standard-Plymouth-Spinner, speichert `/etc/default/grub` und das bisherige Plymouth-Theme unter `/var/lib/itomiscan/boot-backups/...`, setzt `quiet splash` ohne vorhandene Kernel-Parameter zu entfernen und aktualisiert Initramfs/GRUB. Es wird **nicht** von `install.sh`, der GUI oder dem GitHub-Update-Button ausgeführt. Erst nach Boot-/Displaytest am echten N1800 mit SSH-Backup aktivieren.

Als root, **nur zum späteren bewussten Gerätetest**:

```bash
bash setup-boot-splash.sh
```

Plymouth beginnt erst, wenn Kernel und Grafik dies unterstützen. BIOS, GRUB oder Übergänge zwischen Plymouth, tty1 und Xorg können sichtbar bleiben. Das Skript garantiert weder unterbrechungsfreie grafische Anzeige noch eine erfolgreiche Darstellung mit dem Intel-945GSE-Controller. Bei Bootproblemen steht die alte GRUB-Datei als Sicherung bereit; eine Rettung über Konsole/SSH muss möglich bleiben.

## Tests (ohne echte Hardware)

```bash
python3 -m compileall -q app.py itomiscan tests
python3 -m unittest discover -s tests -v
bash -n start-kiosk.sh setup-boot-splash.sh install.sh
```

Hardwaretest offen: Start nach Kaltstart, Touch nach Boot, Scannerverfügbarkeit, Abbruchfall ohne Scanner/Touch, Recovery per Retry, Plymouth-Anzeige auf LVDS. `main` ist weiterhin ausschließlich der stabile Update-Kanal.
