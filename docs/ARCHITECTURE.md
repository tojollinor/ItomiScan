# ItomiScan 1.0.0: Architekturvertrag

**Status 13.10.2026:** Architekturziel und Projektstruktur vorbereitet, neue Komponenten **noch nicht implementiert**.

## Plattform und vorhandener Code

- Fujitsu ScanSnap N1800 auf Originalplatine: Debian 12 i386, Intel Atom N270, ca. 1 GiB RAM, Originaldisplay 1024×768.
- `app.py` bleibt vorerst funktionierender Tkinter/Xorg-Einstiegspunkt. `install.sh`, `start-kiosk.sh`, `setup-shutdown.sh` bleiben in Block 1 unverändert.
- SANE (`scanimage`) bleibt Scan-Backend, `img2pdf` bleibt PDF-Pfad; bestätigte JPEG-Beschleunigung, Vollbild und Fronttaste beim Umbau erhalten.
- Keine Chromium-/Electron-Oberfläche, kein schwerer Datenbankserver und keine lokale OCR als Pflicht.

## Zielmodule (zunächst nur Paketstruktur)

- `itomiscan/core/`: Geräteerkennung, Scanjobs, Zustandsmaschine, zuverlässige Scan-/Exportlogik; später zentrale Dienstschnittstelle.
- `itomiscan/gui/`: lokale große 1024×768-Touchoberfläche, PIN-Tastatur, Profil-/Auftragsansicht, Splash-Bereitschaft.
- `itomiscan/web/`: separater kleiner HTTP-Dienst für **Fernadministration**, nicht zur lokalen Anzeige.
- `itomiscan/storage/`: SQLite-Speicherung für Profile, Aufträge, Benutzer, Konfiguration sowie sichere Warteschlange.
- `itomiscan/integrations/`: Paperless-API, CUPS, SMB/Netzwerkziele, E-Mail und USB-Ziele.

Kein Paket startet beim Import automatisch Hardware, Netzwerkserver oder Hintergrundthreads. Komponenten werden erst in späteren Blöcken schrittweise an den bestehenden Einstiegspunkt angeschlossen. Nicht alle Dienste müssen permanent laufen.

## Betriebsmodell

- Lokale GUI bleibt ohne Root-Rechte. Privilegierte Aktionen über gezielte und geprüfte Rechte, niemals generelle sudo-Freigabe.
- GUI, Scandienst und Webadministration logisch trennen; ein Scanjob wird zentral verwaltet, nicht durch parallele unabhängige Scanaufrufe.
- Einstellungen und Scanprofile werden zentral gespeichert und atomar übernommen; SQLite später mit Migrations-/Backup-Verfahren.
- Dateien für noch nicht zugestellte Aufträge bleiben lokal erhalten, bis das Ziel den Eingang bestätigt. Wiederholung muss doppelte Übertragungen möglichst vermeiden.
- Webzugriff nur auf explizit konfigurierter LAN-/VPN-Adresse, authentifiziert und gegen CSRF/Rate-Limit-/Sitzungsrisiken geschützt. **Kein dauerhaftes Standardpasswort**: Erstkonfiguration setzt Admin-Passwort; danach Anmeldung nur per Passwort ohne Benutzernameneingabe.
- Optional PIN-Benutzer: ohne Aktivierung kein Login, bei Aktivierung eigene Touch-PIN-Oberfläche; Benutzerrechte serverseitig erzwingen, PINs niemals im Klartext, automatische Abmeldung einstellbar.
- Sicherheitsrelevante Zugangsdaten nicht in Logs, Scandateien oder exportierter Konfiguration offenlegen.

## Start und Fehlerbehandlung (Block 2)

- Früher Boot-Splash nach Möglichkeiten der Hardware/Bootkette; bei GUI-Start eigener Splash.
- Hauptansicht erst freigeben, wenn SANE-Erkennung, benötigte Optionen, lokale GUI und Touch-Eingabegerät initialisiert sind.
- Netzwerkdrucker und Paperless nicht als blockierende Startvoraussetzungen behandeln; Fehler separat anzeigen.
- Endlosschleifen verhindern: definierte Frist für Initialisierung, Wiederholen/Diagnose ohne Konsolenausgaben im normalen Benutzerbetrieb.
- Geräteseitige Funktion und Splash-Integration sind **erst nach N1800-Praxistest bestätigt**.

## Oberflächen- und Zielprinzipien

- Vier große Hauptaktionen: Scannen, Paperless, Kopieren, Netzwerkordner; weitere Funktionen über aufgabenorientierte Screens und ggf. Schnellaktionen.
- Einfacher, kontrastreicher ItomiScan-Schriftzug und Icon für das ältere Display; endgültige Logo-Assets erst nach expliziter Auswahl/Übernahme.
- Vor dem Speichern oder Senden Vorschau, sofern Profil keine automatische Verarbeitung festlegt.
- Erweiterte Netz- und Integrationskonfiguration im Web; alltägliche Optionen am Scanner.

## Deployment-Regel

`main` versorgt den aktuell installierten Scanner. Arbeiten für 1.0.0 ausschließlich in `develop/1.0.0`; niemals versehentlich über den bestehenden Update-Button in die Entwicklungsfassung wechseln. Promotion nach getesteter Freigabe; Release erst in Block 8.
