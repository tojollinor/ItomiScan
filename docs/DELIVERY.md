# ItomiScan Dokumentenziele und Warteschlange: Block 6/8

**Stand 14.10.2026: auf `develop/1.0.0` implementiert und offline getestet. Nicht auf dem N1800 installiert oder an reale Ziele angeschlossen. `main` unverändert.**

## Scanablauf

1. Touchstartseite: **Paperless** oder **Netzwerkordner** wählen, alternativ unten **E-Mail / USB**. Im Folgedialog eines der über die Weboberfläche eingetragenen, freigegebenen Ziele berühren.
2. Der ausgewählte Scanmodus wird mit dem persönlichen oder globalen Scanprofil gestartet. Bei PNG-Ausgabe wird für das Ziel zusätzlich eine PDF erzeugt, ohne die bisherige lokale PNG-Ausgabe zu entfernen.
3. Originale verbleiben unter `~/Scans/ItomiScan_...`. Die Ziel-PDF wird zusätzlich mit UUID-Dateiname, SHA-256 und `fsync` unter `~/.config/itomiscan/spool/` abgelegt. Erst danach wird der Auftrag in SQLite festgehalten.
4. Der separat gestartete, nicht privilegierte Zustelldienst bearbeitet fällige Aufträge; ein Fehler beim Netzwerk führt nicht zur Löschung der PDF. Die Browserseite **Aufträge** zeigt Status, Fehler, Versuche und manuelle Wiederholungsmöglichkeit.
5. Ein echtes Archivieren in Paperless ist nach Annahme der Upload-Anfrage noch nicht bewiesen: Es wird die **Annahme zur Verarbeitung**, nach Möglichkeit inklusive Task-ID, bestätigt. Bei unklarem Versand wird der Auftrag **Prüfen** und niemals automatisch doppelt gesendet.

## Zielarten und Voraussetzungen

| Ziel | Beispieladresse | Voraussetzungen / Sicherheitsgrenzen |
| --- | --- | --- |
| **Paperless** | `https://paperless.example.lan` | Gültiges HTTPS-Zertifikat inklusive vertrauenswürdiger CA; API-Token über Web eintragen. POST als `multipart/form-data` nach `/api/documents/post_document/`. Antwort bestätigt nur Verarbeitungsstart. |
| **Netzwerkordner (SMB)** | `smb://nas/freigabe/ordner` | Paket `smbclient` auf dem Gerät, Freigabe erreichbar, Schreibrechte; Benutzername/Passwort über Web geschützt. Temporäre SMB-Authentifizierungsdatei Modus 0600. Keine Shellausführung. Bei unklarer SMB-Zustellung manuelle Prüfung. |
| **E-Mail** | `smtps://smtp.example.lan:465/name@example.org` oder `smtp://smtp.example.lan:587/name@example.org` | SMTP mit TLS oder STARTTLS, Absender und ggf. Anmeldedaten über Web. Mail-Anhang wegen 1 GiB RAM maximal 8 MiB. Bei unklarer Sendebestätigung manuelle Prüfung statt blindem erneuten Versand. |
| **USB** | `usb://SCANUSB/Scans` | Der Stick muss bereits unter `/media/<benutzer>/SCANUSB` oder `/run/media/<benutzer>/SCANUSB` **eingehängt** sein; ohne Mount wird **nicht** in einen lokalen Ersatzordner geschrieben. Keine USB-Automount-Implementierung in diesem Block. PDF wird zunächst als `.part` geschrieben und dann umbenannt, gleicher UUID-Dateiname erkennt Wiederholungen. |

**Zugangsdatenschutz:** `~/.config/itomiscan/integrations-secrets.json` (nur Scannerbenutzer, 0600). Verschlüsselte Übertragung im Web (Block 4). Diese Datei ist **nicht** in den üblichen JSON-Backups enthalten, ebenso wenig Passwörter oder PIN-Hashes. Für einen vollständigen gesicherten Restore inklusive Secrets muss in Block 8 ein ausdrücklich autorisiertes Verfahren eingerichtet werden.

**Zielanlage im Browser:** Menü `Zielsysteme` zum Anlegen von Typ und Adresse, anschließend das jeweilige API-Token / Benutzerkonto / Passwort oder SMTP-Absender in der separaten Zugangsdaten-Maske speichern. Leere Felder erhalten bestehende Werte; ausdrückliches `Zugangsdaten entfernen` löscht sie. Das Entfernen eines Zieles löscht vorhandene Scanaufträge nicht automatisch. Seit Block 7 können zusätzlich IPP-Everywhere-Drucker registriert und gescannte Kopien über die gemeinsame Warteschlange gedruckt werden.

## Zustellstatus und Fehlerfälle

- **queued (Wartend):** Dokument lokal gespeichert und noch nicht gesendet.
- **sending:** Ein Zustelldienst hat den Auftrag für die Bearbeitung reserviert.
- **retry:** Sicherer Wiederholungsversuch nach einem erkennbar nicht erfolgten Versand oder nicht erreichbarem Speicherziel, mit zunehmender Pause.
- **done:** Datei am Netzwerk-/USB-Ziel gesichert oder vom E-Mail-/Paperless-Server zur Verarbeitung **angenommen**. Für Paperless heißt das nicht zwingend erfolgreich indexiert.
- **failed:** Nicht automatisch behebbarer Konfigurations- oder Prüfsummenfehler; Original bleibt vorhanden.
- **review (Prüfen):** Zustellung eventuell bereits erfolgt, etwa nach Netzwerkunterbrechung nach Upload. Vor dem erneuten Versuch muss der Bediener das Ziel prüfen und den erneuten Versand ausdrücklich bestätigen.
- **Crash-Wiederherstellung:** Abgelaufene Übertragungsreservierung wird für Paperless/E-Mail zu `review`; für Dateiziele wird ein Versuch mit gleichem UUID-Dateinamen neu geplant. Der Dateiname verhindert neue lokale Namen bei Wiederholungen, ersetzt aber keine vollständige atomare Ende-zu-Ende-Bestätigung.

Der lokale Spool hat zur Schutzbegrenzung 500 Aufträge, maximal 150 MiB je PDF und insgesamt 2 GiB erfasste Spool-PDFs. **Auch abgeschlossene Spool-PDFs bleiben vorerst erhalten**; dadurch wächst der Speicherverbrauch. Eine geprüfte Aufbewahrungs-/Bereinigungsregel, eine vollständige Systemsicherung sowie ggf. ein Freigabe-/Löschdialog gehören zu Block 8. Niemals manuell die DB-Einträge entfernen, während der Dienst läuft.

## Zustelldienst später aktivieren

**Nicht auf der bisherigen stabilen Version ausführen. Erst wenn der Entwicklungs-/Release-Code bewusst auf dem N1800 installiert wurde:**

Als root mit **tatsächlichem Scanner-Linux-Benutzernamen** (ersetzen):

```bash
cd /home/BENUTZERNAME/ItomiScan
bash setup-delivery.sh BENUTZERNAME
```

Das Opt-in-Skript richtet `itomiscan-delivery.service` ein, läuft als normaler Benutzer und prüft alle 15 Sekunden auf fällige Aufträge. `systemctl status itomiscan-delivery` zeigt den Zustand, `systemctl disable --now itomiscan-delivery` stoppt ihn. Es wird **nicht automatisch** durch `install.sh` oder den bestehenden GitHub-Update-Button aktiviert.

Für einen einzelnen manuellen Test im Projektverzeichnis als Scannerbenutzer:

```bash
python3 -m itomiscan.integrations.worker --once
```

Ein vorhandenes SMB-Ziel benötigt zusätzlich eine installierte `smbclient`-Binärdatei. Das Paket, vertrauenswürdige TLS-Zertifikate, USB-Mounts und die Firewall-Freigaben müssen vor der Hardwareabnahme geprüft werden.

## Teststatus

- GitHub Actions: Python-/Shell-Syntax, SQLite-/GUI-/HTTP-Tests und ergänzende Warteschlangen-/Zieltests. Getestet werden Prüfsummen, Ausfall- und Wiederholungsversuche, nach Neustart fortbestehende Aufträge, manuelle Prüfung unsicherer Zustellung, USB-Mount-Abbruch, atomare Dateiablage und geschützte API-Tokens.
- Paperless: HTTP-Anfrage und Task-ID im Mock-Test geprüft, keine realen API-Zugangsdaten oder Verbindungen.
- Reale SMTP-, SMB-, USB- und Paperless-Geräteabnahme sowie CPU-/RAM-Messung auf Atom N270/1 GiB **ausstehend**.
- SMS, OCR, automatische Paperless-Tags, Papierkorbleerung und dauerhaftes Mount-Management sind nicht Teil dieses Blocks.
- Block 7/8: CUPS-Drucker und Kopierfunktion auf dem Entwicklungszweig implementiert (siehe `docs/PRINTING.md`). Nächster Block 8/8: Integrations-/Gerätetest, Installer, Daten-/Rollback-Sicherung und Release nur nach ausdrücklicher Endfreigabe.

## Block 8: Sicherung und Speicherreserve

Der Zustellworker verwendet eine exklusive Sperre, um doppelte Workerprozesse und gleichzeitige Offline-Backups auszuschließen. Die PDF-Spool-Erstellung prüft eine freie SSD-Reserve. Das vollständige Offline-Backup enthält Spool-Aufträge, Scanoriginale, SQLite und Integrationstokens. Manuelle Zielabnahme und tatsächlicher Wiederanlauf auf dem N1800 stehen aus. **Erfolgreiche Dateien werden weiterhin nicht automatisch gelöscht.** Weitere Einzelheiten: `docs/RELEASE-READINESS-1.0.0.md`.
