# ItomiScan 1.0.0: Architekturvertrag

**Status 14.10.2026:** Blöcke 1–7 auf `develop/1.0.0` implementiert. Block 7 ergänzt CUPS/IPPS-Netzwerkdrucker, Touch-Kopieransicht und gesicherte Druckjobs. Automatisierte Tests grün; reale N1800-/LAN-/CUPS-Abnahme ausstehend. Block 8 enthält Integration/Backup/Rollback/Installer/Release.

## Plattform und vorhandener Code

- Fujitsu ScanSnap N1800 auf Originalplatine: Debian 12 i386, Intel Atom N270, ca. 1 GiB RAM, Originaldisplay 1024×768.
- `app.py` bleibt vorerst funktionierender Tkinter/Xorg-Einstiegspunkt. `install.sh`, `start-kiosk.sh`, `setup-shutdown.sh` bleiben in Block 1 unverändert.
- SANE (`scanimage`) bleibt Scan-Backend, `img2pdf` bleibt PDF-Pfad; bestätigte JPEG-Beschleunigung, Vollbild und Fronttaste beim Umbau erhalten.
- Keine Chromium-/Electron-Oberfläche, kein schwerer Datenbankserver und keine lokale OCR als Pflicht.

## Zielmodule (zunächst nur Paketstruktur)

- `itomiscan/core/`: Geräteerkennung, Scanjobs, Zustandsmaschine, zuverlässige Scan-/Exportlogik; später zentrale Dienstschnittstelle.
- `itomiscan/gui/`: Touchoberfläche, Splash, PIN-Gate sowie Zielauswahl für Paperless/SMB und E-Mail/USB; Zustellaufträge werden im Web verwaltet.
- `itomiscan/web/`: kleiner unabhängiger, ausdrücklich aktivierbarer HTTPS-Webdienst mit Anmeldung, Profilen, Zieladressen, Status und Sicherung; kein Browser auf dem Gerät.
- `itomiscan/storage/`: SQLite für Profile, Einstellungen, Zieladressen, Nutzer/PIN-Rechte und gesicherte PDF-/Druckaufträge samt Kopienzahl und Duplex. Die vorherigen Block-6-Jobs bleiben bei der Migration erhalten.
- `itomiscan/integrations/`: Paperless-HTTPS, SMB, SMTP/TLS, USB und CUPS über einen gemeinsamen Nicht-root-Zustellworker. CUPS-Queues per Web nur nach ausdrücklichem lokalem `setup-printing.sh` mit `lpadmin`-Recht administrierbar.

Kein Paket startet beim Import automatisch Hardware, Netzwerkserver oder Hintergrundthreads. Komponenten werden erst in späteren Blöcken schrittweise an den bestehenden Einstiegspunkt angeschlossen. Nicht alle Dienste müssen permanent laufen.

## Betriebsmodell

- Lokale GUI bleibt ohne Root-Rechte. Privilegierte Aktionen über gezielte und geprüfte Rechte, niemals generelle sudo-Freigabe.
- GUI, Scandienst und Webadministration logisch trennen; ein Scanjob wird zentral verwaltet, nicht durch parallele unabhängige Scanaufrufe.
- Gemeinsame SQLite-Konfiguration unter `~/.config/itomiscan/itomiscan.db` (Datei 0600, Elternverzeichnis 0700). Bestehende `profiles.json` wird beim ersten Start übernommen und bleibt unverändert erhalten.
- Aufträge werden als unveränderte Originalscans unter ~/Scans und als SHA-256-verifizierte PDF-Kopie unter ~/.config/itomiscan/spool/ gehalten. SQLite speichert Versuche/Zustellstatus; eindeutig fehlgeschlagene Zustellungen können erneut versucht werden, bei unklarer Paperless-/E-Mail-/SMB-Übertragung muss manuell geprüft werden. Paperless bestätigt zunächst nur die Annahme zur Verarbeitung, nicht die fertige Archivierung.
- Der Webdienst bindet standardmäßig nur an 127.0.0.1, im LAN nur nach passwortgeschützter Erstkonfiguration über SSH und mit HTTPS-Zertifikat. Anmeldung ausschließlich per Passwort ohne Benutzername. PBKDF2, Sitzungsablauf, HttpOnly-/SameSite-Cookies, CSRF, Rate-Limits und Host-/Origin-Kontrolle implementiert.
- Optionale PIN-Anmeldung seit Block 5: Ausgeschaltet = Startseite sofort; eingeschaltet = PIN-Ziffernfeld mit individueller Rechte- und Profilzuweisung. Eindeutige 4–6-stellige PINs werden gesalzen gehasht gespeichert, fünf Fehlversuche verursachen drei Minuten globale PIN-Sperre; automatische Abmeldung nach 1–60 Minuten. Berechtigungen werden bei jeder sensiblen Aktion gegen die SQLite-Datenbank geprüft und persönliche Profile vor dem Scan erneut angewendet. Details unter `docs/USERS.md`.
- Sicherung ohne Admin-Hash, Sitzungen und Ziel-Zugangsdaten. In Block 4 werden nur Zieladressen gespeichert, noch keine API-/SMB-/SMTP-Passwörter. Webdienst ohne Root-Rechte. Details `docs/WEB-ADMIN.md`.

## Start und Fehlerbehandlung (Block 2)

- App-Splash mit Tkinter bereits auf dem Entwicklungszweig eingebunden; früher Plymouth-Boot-Splash als **optionales, noch nicht am Gerät ausgeführtes** Skript vorbereitet.
- Hauptansicht erst freigeben, wenn SANE-Erkennung, benötigte Optionen und das Kernel-Touch-Eingabegerät vorhanden sind und die lokale GUI angelegt wurde. Kernel-Erkennung **beweist keine tatsächlich korrekte Berührung oder Kalibrierung**.
- Netzwerkdrucker und Paperless nicht als blockierende Startvoraussetzungen behandeln; Fehler separat anzeigen.
- Auf dem Entwicklungszweig begrenzte Initialisierungsdauer und SANE-Subprozess-Timeouts, Wiederholen/Diagnose/Beenden nach Fehlschlag. Details: `docs/STARTUP.md`.
- Geräteseitige Funktion und Splash-Integration sind **erst nach N1800-Praxistest bestätigt**.

## Oberflächen- und Zielprinzipien

- Vier große Hauptaktionen: Scannen, Paperless, Netzwerkordner und Kopieren. Kopieren bietet große Druckerwahl, Kopien 1–20 sowie Scan-/Druck-Duplex. E-Mail/USB über ergänzende Zielauswahl. Ausgehende PDF- und Druckzustellung laufen über den gesondert gestarteten Worker; vorhandenes `main` unverändert.
- Vereinfachtes, kontrastreiches Scan-Symbol als flache Canvas-Zeichnung im GUI und Splash, an das vereinbarte minimalistische Logo angelehnt; ohne hochauflösende Bildressourcen für das ältere Display.
- Lokales Scannen öffnet die beibehaltene SANE-Detailmaske mit bestehender PDF-/PNG-Vorschau und Navigation. Bereits bisher gespeicherte Scans bleiben gespeichert; nachträgliches Editieren und eine zielbezogene Freigabe-/Sendevorschau folgen später.
- Erweiterte Netz- und Integrationskonfiguration im Web; alltägliche Optionen am Scanner.

## Deployment-Regel

`main` versorgt den aktuell installierten Scanner. Arbeiten für 1.0.0 ausschließlich in `develop/1.0.0`; niemals versehentlich über den bestehenden Update-Button in die Entwicklungsfassung wechseln. Promotion nach getesteter Freigabe; Release erst in Block 8.
