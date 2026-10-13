# ItomiScan (technischer Prototyp)

Lokale, leichtgewichtige Touchoberfläche für den Fujitsu ScanSnap N1800 mit
**Debian 12 i386**, Intel Atom N270 und 1 GB RAM. Die Scaneinheit wurde unter
Linux als **fujitsu:fi-6110dj:10407** erkannt. SANE-Einzelscan wurde bereits
auf dem echten Gerät durchgeführt; die lokale GUI einschließlich Vollbild, PDF-Erstellung und Front-Scantaste wurde am Gerät erfolgreich erprobt.

## Funktionen (erste Testversion)

- Lokale Vollbild-Oberfläche (Tkinter/Xorg, ohne Fenstermanager oder Webserver; Displaygröße explizit übernommen)
- IP-Anzeige
- SANE-Scannererkennung und gerätespezifische Einstellmöglichkeiten
- Standard: ADF-Duplex, Farbe, 200 DPI
- Inaktive Optionen werden angezeigt, aber deaktiviert
- Mehrseitiges Scannen über `scanimage --batch`
- Bildvorschau mit Vor/Zurück für beide Seiten und mehrere Blätter
- Auswahl: PNG-Einzelbilder oder eine zusammengefasste PDF-Datei
- PDF-Optimierung: Farbe/Graustufen direkt als JPEG-Zwischenbilder; Schwarzweiß und PNG-Ausgabe bleiben verlustfrei als PNG
- Schnellere JPEG-Vorschau durch reduzierte Dekodierauflösung
- Speicherung im Benutzerordner `~/Scans/ItomiScan_YYYYMMDD_HHMMSS/`
- Update-Schaltfläche: GitHub `main` prüfen, mit Bestätigung fast-forward
- Testanbindung für die Fronttaste: `Return` bzw. `KP_Enter` löst den vorhandenen Scanvorgang aus (nur im Hauptfenster, nicht während eines Scans). Der Scanstart mit der externen Fronttaste wurde vom Nutzer auf dem N1800 bestätigt.
- Beenden schließt nur die Anwendung, **nicht** Debian
- **Ausschalten** im Kopfbereich: Bestätigungsdialog, danach vollständiges Herunterfahren von Debian; während eines Scans gesperrt

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
Zusätzlich erhält nur der Kiosk-Benutzer eine eng begrenzte Berechtigung für
`sudo -n /usr/bin/systemctl poweroff` (kein allgemeiner root-Zugriff).

### Einmalige Einrichtung auf bereits installierten Geräten

Der GitHub-Update-Button lädt nur den Programmcode. Die neue Systemberechtigung
muss daher einmalig **als root über SSH** eingerichtet werden:

```bash
curl -fL https://raw.githubusercontent.com/tojollinor/ItomiScan/main/setup-shutdown.sh -o /tmp/itomiscan-shutdown.sh
bash /tmp/itomiscan-shutdown.sh
```

Das Hilfsskript ermittelt den bestehenden Kiosk-Benutzer aus der ItomiScan-tty1-
Autologin-Konfiguration, prüft die sudoers-Regel und installiert bei Bedarf `sudo`.
Es fährt das Gerät dabei **nicht** herunter.

## Nach dem Start

- Dokumente einlegen, **Scannen** drücken, in der Vorschau blättern.
- Bei Ausgabe **PDF** entsteht genau eine PDF-Datei pro Scan.
- Bei **Bild (PNG)** entstehen die einzelnen PNG-Dateien.
- **Update** benötigt eine Internetverbindung; lokale Änderungen verhindern
  bewusst den Fast-Forward. Updates werden erst nach Bestätigung eingespielt.
- **Beenden** zeigt die lokale Linux-Konsole; zum erneuten Start dort
  `startx ~/ItomiScan/start-kiosk.sh -- :0 vt1` ausführen.
- **Ausschalten** nach Bestätigung: fährt den Scanner vollständig herunter.
  Ein eventuell fehlendes Ausführungsrecht wird als Fehlermeldung angezeigt.
- Für die Hardwarediagnose: `scanimage -L` und
  `scanimage -d 'fujitsu:fi-6110dj:10407' --help`.

## Wichtige Hinweise

- Vor längeren Tests zuerst wenige Seiten mit 200 DPI scannen, 1 GB RAM ist knapp.
- Die GUI wurde auf dem N1800 gestartet. Das zunächst zu kleine Fenster
  (976 × 509 bei 1024 × 768 Display) wurde im Code auf explizite Xorg-Bildschirmgröße
  umgestellt; der Nutzer bestätigte anschließend die korrekte Vollbilddarstellung.
- Die Touch-Kalibrierung muss gegebenenfalls noch angepasst werden.
- JPEG ist bei Farb-/Graustufen-PDFs verlustbehaftet; Schwarzweiß-PDFs und
  gewählte PNG-Bilder nutzen weiterhin die bisherige PNG-Verarbeitung.
- Die PDF-Erstellung wurde nach dem Update vom Nutzer als deutlich schneller bestätigt; eine Zeitmessung wurde nicht vorgenommen.
- GUI, Scannerrechte, Papierstau-/Doppeleinzugserkennung und die tatsächliche
  Duplex-Reihenfolge benötigen Gerätetests.
- Der Firmware-/Windows-Datenträger wurde nicht verändert.
- Mit dem Update-Button wird **nur ItomiScan-Code** aktualisiert, nicht Debian
  oder die installierten Debian-Pakete.

Repository: https://github.com/tojollinor/ItomiScan


## ItomiScan 1.0.0 (Entwicklung)

Der **Entwicklungszweig `develop/1.0.0`** enthält neue Startlogik und Touchstartseite.
Im bestehenden Scannerbetrieb bleibt `main` der Update-Kanal.

Block 2: Schlanker lokaler Splash mit Scanner-/Touchgerät-Erkennung und
Wiederholen/Diagnose; optionales, **nicht automatisch ausgeführtes**
`setup-boot-splash.sh` für Plymouth auf Debian 12. Details in
[`docs/STARTUP.md`](docs/STARTUP.md). Eine erfolgreiche Geräteabnahme steht
noch aus.


### Block 3: Touchstartseite, Profile und Bildschirmschoner

Im Entwicklungszweig (noch **nicht** über den normalen Update-Button auf dem N1800 installiert):

- Großflächige 2×2-Startseite mit Scannen, Paperless, Kopieren und Netzwerkordner. Nur Scannen ist jetzt aktiv; andere Ziele werden in den Blöcken 6/7 ergänzt und zeigen bis dahin eine klare Meldung.
- Vereinfachtes ItomiScan-Scan-Logo in kräftigen, kontrastreichen Farben; direkt mit Tk-Canvas gezeichnet, ohne große Bilddateien.
- Profile **Dokument (Farbe/200 DPI/Duplex/PDF)**, **Text (Grau/300 DPI/Duplex/PDF)** und **Foto (Farbe/300 DPI/ADF Front/PNG)**; Profil wählen und per „Jetzt scannen“ oder physischer Scan-Taste scannen.
- Einstellungen und zusätzliche aktive SANE-Optionen können in der bisherigen Detailmaske geändert und über „Profil speichern“ mit einem Namen abgelegt werden. Bis zur Webkonfiguration erfordert die Namenseingabe eine Tastatur.
- Die bestehende Vorschau für mehrseitige Scans bleibt erhalten. Das PDF wird wie bisher bereits beim Scannen erstellt, Nachbearbeiten/Seitenlöschen aus der Vorschau ist noch nicht implementiert.
- Historischer Block-3-Stand: Profile in `profiles.json`; seit Block 4 in gemeinsamer SQLite-Konfiguration. Die alte JSON-Datei bleibt erhalten.
- Fünf Minuten ohne Aktivität: dunkler Bildschirmschoner mit Uhrzeit. Berühren oder eine Taste drücken weckt die Oberfläche. Er schaltet derzeit **nicht** die Display-Hardware ab.
- GitHub-Actions-Tests für Python-/Shell-Syntax, Profile und virtuelle Tk-Oberfläche. Der Echtgerätetest bleibt offen.
- Sicherheitsregel: Die Update-Taste auf `develop/1.0.0` nimmt bewusst **keine** Updates aus dem stabilen `main` an. Erst nach Freigabe wird auf dem Gerät aktualisiert.

Technische Einzelheiten: [`docs/TOUCH-UI.md`](docs/TOUCH-UI.md).


### Block 4: Passwortgeschützte Webadministration (Entwicklung)

Getrennter kleiner Python-Webserver für Profile, vorbereitete Papier-/Druck-/Netzwerkziele, Systemstatus, SANE-Diagnose und JSON-Konfigurationssicherungen. Gemeinsame SQLite-DB; bestehende JSON-Profile werden erhalten. Erste Passwortvergabe über SSH, Anmeldung nur per Passwort ohne Benutzername, kein Standardpasswort. LAN-Betrieb ausschließlich über HTTPS. Opt-in-Einrichtung mit `setup-web.sh` erfolgt **nicht automatisch**. Keine echte Übertragung oder Druckfunktion vor Block 6/7. Siehe [docs/WEB-ADMIN.md](docs/WEB-ADMIN.md). Gerätetest offen, `main` unverändert.


### Block 5: Optionale Benutzerverwaltung (Entwicklung)

- Webadministration: Tab **Benutzer**, dort aktive Konten mit 4–6-stelliger PIN, Funktionsrechten und persönlich zugewiesenen Scanprofilen verwalten.
- PIN-Anmeldung standardmäßig deaktiviert. Nach Aktivierung erscheint auf dem N1800 erst das große PIN-Tastenfeld. Erst danach persönliche Startseite; physische Scantaste bleibt vorher gesperrt.
- Zeitgesteuerte Abmeldung (1–60 Minuten), Benutzerwechsel und Löschung der vorherigen Vorschau beim Abmelden. Ein Scanauftrag wird nicht mitten im Scannen unterbrochen.
- PINs werden nur als gesalzene Prüfsummen gespeichert und nicht exportiert. Nach fünf Fehlversuchen drei Minuten PIN-Sperre. Webadmin-Passwort bleibt unabhängig.
- Berechtigungen werden vor Aktionen und zugewiesene Profile direkt vor Scanbeginn überprüft. Gemeinsame Profiländerungen bei aktiver Benutzerverwaltung nur im Web.
- Automatisierte Tests vorhanden. **Kein realer N1800-Test, kein 1.0.0-Release und keine Änderungen an `main`.** Details: [docs/USERS.md](docs/USERS.md).
