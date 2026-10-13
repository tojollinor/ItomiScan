# Webadministration: ItomiScan Block 4/8

Stand 13.10.2026: **Entwicklungszweig `develop/1.0.0` implementiert, nicht auf dem N1800 installiert oder im LAN getestet. `main` unverändert.**

## Architektur und Funktionen

- Separater Python-HTTP(S)-Dienst ohne Browser auf dem N1800, ohne zusätzliche Python-Webframeworks.
- Anmeldung mit **nur einem Passwort**, ohne Benutzernamen und ohne mitgelieferte Standard-Zugangsdaten.
- Übersicht mit Versions-/Systemstatus und Profil-/Zielanzahl.
- Scanprofile erstellen, anpassen, als Standard wählen; vollständige SANE-Parameter als validierte JSON-Einstellungen.
- Paperless-, IPP-/CUPS-, SMB- und SMTP-Zieladressen vorbereiten. **Keine tatsächliche Übertragung oder Druckfunktion** vor Blöcken 6 und 7.
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
- Noch keine optionalen PIN-Benutzer (Block 5), keine Zielübertragung (Block 6), kein CUPS-Kopieren (Block 7). Releases und Rollback erst in Block 8 nach ausdrücklicher Abnahme.
