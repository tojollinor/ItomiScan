# ItomiScan (technischer Prototyp)

Lokale, leichtgewichtige Touchoberfläche für den Fujitsu ScanSnap N1800 mit
**Debian 12 i386**, Intel Atom N270 und 1 GB RAM. Die Scaneinheit wurde unter
Linux als **fujitsu:fi-6110dj:10407** erkannt. SANE-Einzelscan wurde bereits
auf dem echten Gerät durchgeführt; die neue GUI ist noch **nicht am Gerät erprobt**.

## Funktionen (erste Testversion)

- Lokale Vollbild-Oberfläche (Tkinter/Xorg, kein Desktop, kein Webserver)
- IP-Anzeige
- SANE-Scannererkennung und gerätespezifische Einstellmöglichkeiten
- Standard: ADF-Duplex, Farbe, 200 DPI
- Inaktive Optionen werden angezeigt, aber deaktiviert
- Mehrseitiges Scannen über `scanimage --batch`
- Bildvorschau mit Vor/Zurück für beide Seiten und mehrere Blätter
- Auswahl: PNG-Einzelbilder oder eine zusammengefasste PDF-Datei
- Speicherung im Benutzerordner `~/Scans/ItomiScan_YYYYMMDD_HHMMSS/`
- Update-Schaltfläche: GitHub `main` prüfen, mit Bestätigung fast-forward
- Beenden schließt nur die Anwendung, **nicht** Debian

**Noch nicht realisiert:** Druckausgabe, Profilverwaltung, Webadministration,
OCR, automatischer Zuschnitt für alle Papierformate und sichere Sensor-/Fehlerdiagnose.
SANE kann bei Fehlern oder Papiermangel einen Rückgabecode/Fehlertext liefern;
dieser wird angezeigt. Inaktive Hardwareoptionen lassen sich nicht erzwingen.
Nach Wechsel des Scanmodus können je nach Backend andere Optionen verfügbar
werden; dafür ist noch eine dynamische Aktualisierung geplant.

## Installation auf dem N1800

Voraussetzungen: Debian 12, aktives LAN, SSH, funktionierender SANE-Treiber.
Die Installation verwendet den **vorhandenen normalen Linux-Benutzer** (nicht root).
Seinen Namen bitte bei `BENUTZERNAME` ersetzen.

Als root via SSH:

```bash
apt install -y git
git clone https://github.com/tojollinor/ItomiScan.git /tmp/itomiscan-setup
bash /tmp/itomiscan-setup/install.sh BENUTZERNAME
reboot
```

Beim nächsten Start meldet die Konsole `tty1` den angegebenen Benutzer
automatisch an und startet nur dort Xorg mit ItomiScan. Andere SSH-Zugänge
werden nicht umkonfiguriert. Die GUI läuft **ohne root-Rechte**.

Das Skript installiert Debian-Pakete einschließlich `sane-utils`, Xorg,
`python3-tk`, Pillow und `img2pdf`. Für den Webserver wird nichts geöffnet.

## Nach dem Start

- Dokumente einlegen, **Scannen** drücken, in der Vorschau blättern.
- Bei Ausgabe **PDF** entsteht genau eine PDF-Datei pro Scan.
- Bei **Bild (PNG)** entstehen die einzelnen PNG-Dateien.
- **Update** benötigt eine Internetverbindung; lokale Änderungen verhindern
  bewusst den Fast-Forward. Updates werden erst nach Bestätigung eingespielt.
- **Beenden** zeigt die lokale Linux-Konsole; zum erneuten Start dort
  `startx ~/ItomiScan/start-kiosk.sh -- :0 vt1` ausführen.
- Für die Hardwarediagnose: `scanimage -L` und
  `scanimage -d 'fujitsu:fi-6110dj:10407' --help`.

## Wichtige Hinweise

- Vor längeren Tests zuerst wenige Seiten mit 200 DPI scannen, 1 GB RAM ist knapp.
- Die Grafikoberfläche wurde bisher nicht auf dem N1800 getestet. Die
  Touch-Kalibrierung muss gegebenenfalls noch angepasst werden.
- GUI, Scannerrechte, Papierstau-/Doppeleinzugserkennung und die tatsächliche
  Duplex-Reihenfolge benötigen Gerätetests.
- Der Firmware-/Windows-Datenträger wurde nicht verändert.
- Mit dem Update-Button wird **nur ItomiScan-Code** aktualisiert, nicht Debian
  oder die installierten Debian-Pakete.

Repository: https://github.com/tojollinor/ItomiScan
