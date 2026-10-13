# ItomiScan 1.0.0: Architekturvertrag

**Status 13.10.2026:** Boot-/App-Splash und Bereitschaftslogik (Block 2) sowie neue Touchstartseite, lokale Profile und Bildschirmschoner (Block 3) auf `develop/1.0.0` implementiert. Offline-/Xvfb-Tests vorhanden, N1800-Praxistest offen. Web- und Zielintegrationen sowie Benutzerverwaltung noch nicht implementiert.

## Plattform und vorhandener Code

- Fujitsu ScanSnap N1800 auf Originalplatine: Debian 12 i386, Intel Atom N270, ca. 1 GiB RAM, Originaldisplay 1024×768.
- `app.py` bleibt vorerst funktionierender Tkinter/Xorg-Einstiegspunkt. `install.sh`, `start-kiosk.sh`, `setup-shutdown.sh` bleiben in Block 1 unverändert.
- SANE (`scanimage`) bleibt Scan-Backend, `img2pdf` bleibt PDF-Pfad; bestätigte JPEG-Beschleunigung, Vollbild und Fronttaste beim Umbau erhalten.
- Keine Chromium-/Electron-Oberfläche, kein schwerer Datenbankserver und keine lokale OCR als Pflicht.

## Zielmodule (zunächst nur Paketstruktur)

- `itomiscan/core/`: Geräteerkennung, Scanjobs, Zustandsmaschine, zuverlässige Scan-/Exportlogik; später zentrale Dienstschnittstelle.
- `itomiscan/gui/`: große lokale Touchoberfläche und Splash fertig im Entwicklungszweig; PIN-Anmeldung, Auftragsansicht und Zielintegrationen folgen später.
- `itomiscan/web/`: separater kleiner HTTP-Dienst für **Fernadministration**, nicht zur lokalen Anzeige.
- `itomiscan/storage/`: SQLite-Speicherung für Profile, Aufträge, Benutzer, Konfiguration sowie sichere Warteschlange.
- `itomiscan/integrations/`: Paperless-API, CUPS, SMB/Netzwerkziele, E-Mail und USB-Ziele.

Kein Paket startet beim Import automatisch Hardware, Netzwerkserver oder Hintergrundthreads. Komponenten werden erst in späteren Blöcken schrittweise an den bestehenden Einstiegspunkt angeschlossen. Nicht alle Dienste müssen permanent laufen.

## Betriebsmodell

- Lokale GUI bleibt ohne Root-Rechte. Privilegierte Aktionen über gezielte und geprüfte Rechte, niemals generelle sudo-Freigabe.
- GUI, Scandienst und Webadministration logisch trennen; ein Scanjob wird zentral verwaltet, nicht durch parallele unabhängige Scanaufrufe.
- Scanprofile liegen übergangsweise unter `~/.config/itomiscan/profiles.json` und werden per atomarem Dateiersatz geschrieben (nur Scanparameter, keine Passwörter). Die zentrale Konfiguration inklusive Migration nach SQLite ist für Block 4 vorgesehen.
- Dateien für noch nicht zugestellte Aufträge bleiben lokal erhalten, bis das Ziel den Eingang bestätigt. Wiederholung muss doppelte Übertragungen möglichst vermeiden.
- Webzugriff nur auf explizit konfigurierter LAN-/VPN-Adresse, authentifiziert und gegen CSRF/Rate-Limit-/Sitzungsrisiken geschützt. **Kein dauerhaftes Standardpasswort**: Erstkonfiguration setzt Admin-Passwort; danach Anmeldung nur per Passwort ohne Benutzernameneingabe.
- Optional PIN-Benutzer: ohne Aktivierung kein Login, bei Aktivierung eigene Touch-PIN-Oberfläche; Benutzerrechte serverseitig erzwingen, PINs niemals im Klartext, automatische Abmeldung einstellbar.
- Sicherheitsrelevante Zugangsdaten nicht in Logs, Scandateien oder exportierter Konfiguration offenlegen.

## Start und Fehlerbehandlung (Block 2)

- App-Splash mit Tkinter bereits auf dem Entwicklungszweig eingebunden; früher Plymouth-Boot-Splash als **optionales, noch nicht am Gerät ausgeführtes** Skript vorbereitet.
- Hauptansicht erst freigeben, wenn SANE-Erkennung, benötigte Optionen und das Kernel-Touch-Eingabegerät vorhanden sind und die lokale GUI angelegt wurde. Kernel-Erkennung **beweist keine tatsächlich korrekte Berührung oder Kalibrierung**.
- Netzwerkdrucker und Paperless nicht als blockierende Startvoraussetzungen behandeln; Fehler separat anzeigen.
- Auf dem Entwicklungszweig begrenzte Initialisierungsdauer und SANE-Subprozess-Timeouts, Wiederholen/Diagnose/Beenden nach Fehlschlag. Details: `docs/STARTUP.md`.
- Geräteseitige Funktion und Splash-Integration sind **erst nach N1800-Praxistest bestätigt**.

## Oberflächen- und Zielprinzipien

- Vier große Hauptaktionen auf der neuen Startseite: Scannen (funktionsfähig) sowie Paperless, Kopieren, Netzwerkordner (**noch nicht verfügbar**, Platzhalter mit verständlicher Meldung). Weitere Funktionen folgen blockweise.
- Vereinfachtes, kontrastreiches Scan-Symbol als flache Canvas-Zeichnung im GUI und Splash, an das vereinbarte minimalistische Logo angelehnt; ohne hochauflösende Bildressourcen für das ältere Display.
- Lokales Scannen öffnet die beibehaltene SANE-Detailmaske mit bestehender PDF-/PNG-Vorschau und Navigation. Bereits bisher gespeicherte Scans bleiben gespeichert; nachträgliches Editieren und eine zielbezogene Freigabe-/Sendevorschau folgen später.
- Erweiterte Netz- und Integrationskonfiguration im Web; alltägliche Optionen am Scanner.

## Deployment-Regel

`main` versorgt den aktuell installierten Scanner. Arbeiten für 1.0.0 ausschließlich in `develop/1.0.0`; niemals versehentlich über den bestehenden Update-Button in die Entwicklungsfassung wechseln. Promotion nach getesteter Freigabe; Release erst in Block 8.
