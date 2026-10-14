# Webadministration: ItomiScan Block 4/8

Stand 13.10.2026: **Entwicklungszweig `develop/1.0.0` implementiert, nicht auf dem N1800 installiert oder im LAN getestet. `main` unverändert.**

## Architektur und Funktionen

- Separater Python-HTTP(S)-Dienst ohne Browser auf dem N1800, ohne zusätzliche Python-Webframeworks.
- Anmeldung mit **nur einem Passwort**, ohne Benutzernamen und ohne mitgelieferte Standard-Zugangsdaten.
- Übersicht mit Versions-/Systemstatus und Profil-/Zielanzahl.
- Scanprofile erstellen, anpassen, als Standard wählen; vollständige SANE-Parameter als validierte JSON-Einstellungen.
- Paperless-, SMB-, SMTP- und USB-Ziele sind seit Block 6 mit lokalem PDF-Auftragsspeicher und geschützten Zugangsdaten angebunden. Für tatsächliche Zustellung muss der optionale Zustelldienst gestartet werden. IPP-/CUPS-Kopieren ist seit Block 7 implementiert.
- Einstellungen: Gerätename, Bildschirmschonerzeit und Änderung des Administratorpassworts.
- SANE-Diagnose nur auf Anforderung (`scanimage -L`, kurzer Timeout), Uptime und freier Speicher.
- Konfiguration als JSON herunterladen und per Dateiimport wiederherstellen. **Keine Passwörter, Hashes oder Sitzungen in Sicherungen.**

## Gemeinsame Konfiguration

- Dateipfad für normalen Scannerbenutzer: `~/.config/itomiscan/itomiscan.db` (SQLite, Datei 0600, Verzeichnis 0700).
- Web und Touch lesen dieselbe Datenbank über unabhängige kurzlebige Verbindungen.
- Bestehende `profiles.json` wird beim ersten Start validiert in SQLite übernommen; die alte Datei wird **nicht gelöscht**.
- Änderungen der Profile sind nach dem nächsten Aufruf der Profilansicht am Gerät sichtbar. Geänderte Bildschirmschonerzeit spätestens nach GUI-Neustart.
- In dieser Phase speichert der Webdienst keine Paperless-Tokens oder sonstigen Netzwerk-Zugangsdaten.

## Schutzmaßnahmen

- Keine Netzwerkbindung ohne explizite Konfiguration: Standard `127.0.0.1:8443`. Nur konkrete IPv4-Adresse erlaubt, niemals `0.0.0.0`.
- Nicht-Loopback-Verbindungen verlangen TLS-Zertifikat und Schlüssel. Opt-in-Skript `setup-web.sh` akzeptiert ausschließlich passende LAN-/VPN-IPv4.
- Vor erstem Serverstart muss ein Administratorpasswort mit mindestens zehn Zeichen via SSH/Terminal festgelegt werden. Keine Passwörter als Argumente oder in der Shell-History.
- Passwort-Hash: PBKDF2-HMAC-SHA256 mit individuellem Salt. Sitzungen mit Ablauf nach 30 Minuten Inaktivität; Cookie HttpOnly, SameSite=Strict und unter TLS Secure.
- CSRF-Token für Formularaktionen, Host-/Origin-Kontrolle, HTML-Escaping, restriktive Content-Security-Policy, Loginbegrenzung nach fünf Fehlversuchen und limitierte Formulargrößen.
- Webdienst läuft als normaler Scannerbenutzer und wird ausschließlich nach bewusster Aktivierung via systemd eingerichtet.

## Manuelle Ersteinrichtung erst nach Deployment und Freigabe

**Aktuell NICHT auf dem unveränderten `main`-Scanner ausführen.** Die Anleitung gilt erst, wenn die neue Fassung ausdrücklich auf das Gerät übernommen wurde.

1. Als normaler Scannerbenutzer über SSH im ItomiScan-Verzeichnis das Passwort eingeben:

```bash
cd ~/ItomiScan
python3 -m itomiscan.web.cli init-admin
```

2. Für eine konkrete **eigene** LAN-/VPN-IP den Opt-in-Webdienst als root installieren (Platzhalter **nicht unverändert ausführen**):

```bash
cd /home/BENUTZERNAME/ItomiScan
bash setup-web.sh BENUTZERNAME 192.168.1.50
```

3. Danach von einem anderen Gerät im LAN/VPN `https://<TATSÄCHLICHE-IP>:8443` öffnen. Das bei der Einrichtung erzeugte selbstsignierte Zertifikat muss kontrolliert geprüft und vertrauenswürdig eingerichtet werden. Browserwarnungen nicht blind ignorieren, Routerport nicht ins öffentliche Internet weiterleiten.

4. Service prüfen: `systemctl status itomiscan-web`; abschalten: `systemctl disable --now itomiscan-web`.

## Teststatus und Grenzen

- CI prüft Python-/Shell-Syntax, SQLite/Profil-Migration, virtuelle Tk-Oberfläche und echte lokale HTTP-Anfragen getrennt.
- Geprüfte Szenarien: Authentifizierung, nicht autorisierter Zugriff, CSRF, Host/Origin, HTML-Escaping, Profil- und Zielanlage, JSON-Sicherung/Import, TLS-Pflicht beim Nicht-Loopback-Binden.
- **Am N1800 noch offen:** HTTPS mit Zertifikat/Vertrauensstellung, tatsächlicher LAN-Zugriff, RAM-/CPU-Belastung, Scannerrechte, paralleles Scannen mit Webzugriff und Wiederherstellungstest.
- **Block 5:** der zusätzliche Tab `Benutzer` verwaltet aktive/inaktive PIN-Benutzer, Rechte, zugewiesene Scanprofile sowie die optionale PIN-Anmeldung und Inaktivitätsfrist. Benutzer-PINs/-Hashes gehören nicht zum JSON-Konfigurationsbackup. Zielübertragung und CUPS-Kopieren wurden in den Folgeblöcken 6/7 ergänzt; Release frühestens in Block 8.

## Ergänzung Block 6: Dokumentenziele

Im Browser gibt es jetzt **Zielsysteme** zum Anlegen von HTTPS-Paperless, SMB-Freigaben, SMTP und eingehängten USB-Datenträgern. API-Token, SMB-/SMTP-Zugang und Mail-Absender werden in einer separaten, nur für den Scannerbenutzer lesbaren Datei gespeichert. Zugangsdaten und lokaler PDF-Spool gehören **nicht** zum üblichen JSON-Konfigurationsbackup.

Der neue Tab **Aufträge** zeigt wartende, zugestellte, erneut versuchte und zu prüfende Zustellungen. Unsichere Versandzustände können nur mit expliziter Bestätigung erneut ausgelöst werden. Reale Weiterleitung benötigt den separat gestarteten Dienst `itomiscan-delivery.service`, der auf dem bestehenden Gerät **nicht** installiert ist. Details: `docs/DELIVERY.md`.

## Block 7: Netzwerkdrucker im Browser

Der Tab **Drucker** ermöglicht nach der einmaligen, ausdrücklich freigegebenen CUPS-Ersteinrichtung die Verwaltung von IPP-/IPPS-Zielen, die Registrierung als CUPS-Queue und eine Testseite. CUPS selbst bleibt lokal, die Webadministration geschützt. Das Skript `setup-printing.sh` gibt dem Scannerbenutzer bewusst `lpadmin`-Gruppenrechte; dies erlaubt die Verwaltung lokaler CUPS-Queues und ist deshalb ein zusätzlicher Sicherheitsentscheid. Die bestehenden PDF-/Druckaufträge sind im Tab **Aufträge** sichtbar. Unklare CUPS-Übergaben erhalten Status **Prüfen** und werden nicht automatisch ein zweites Mal gedruckt. Einzelheiten in [PRINTING.md](PRINTING.md).
