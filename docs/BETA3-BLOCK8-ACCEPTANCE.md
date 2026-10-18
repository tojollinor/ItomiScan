# ItomiScan 1.0.0 Beta 3: Integrationsabnahme (Block 8)

Stand: 2026-10-19. Entwicklungsbranch `develop/1.0.0`. Nur Quellcode-/CI-Abnahme durchgeführt; **keine Installation oder reale Geräteabnahme**. `main`, Stable und frühere Beta-Tags bleiben unverändert.

## Prüfbereiche und Beleglage

| Bereich | Automatisierte Kontrolle | Noch manuell am N1800 |
| --- | --- | --- |
| Login/Touch/Screensaver | Xvfb-GUI-Regression mit 1024×768; PIN-Sperre und Abmeldung nach 30 s | Tatsächliche Touchgesten, unterbrechungsfreier aktiver Scan und Schoner über PIN |
| Scanner/Vorschau | Python-Syntax, Mock-/GUI-Tests der Seitenminiaturen und Werkzeuge | SANE/fi-6110dj, ADF-Duplex, 150/300/600 dpi, Scan-Stapel, Seitenaktionen, Fronttaste |
| Webadmin/Fernsteuerung | Webauthentifizierung, CSRF, Remote- und Bildschirmansichtstests | Bildfrequenz/Latenz/CPU auf N270, Zugriff per LAN/HTTPS |
| Drucker | UUID-basierte Erkennung, CUPS-Queue-Auswahl, Installations-/Missbrauchstests | Brother HL-3152CDW, IPP/IPPS, Treiberunterstützung, Testseite tatsächlich gedruckt |
| Paperless | Tokenaustausch, HTTP/OPTIONS-Lesediagnose, sichere 403-Meldungen | HTTPS-/Proxy-Prüfung beim echten DMS, POST-Upload und bestätigte Verarbeitung |
| Startseitenbuttons | Authentifizierter Webeditor, getrennte Zielrechte, Gruppen, Farben, SANE-Optionen | Darstellung auf 1024×768, individuelle Scanner-Optionen tatsächlich übernommen |
| Mehrziel-Queue | Thread-Barriere beweist zwei gleichzeitige Zustellungen; eine PDF auf einem Inode, atomare SQLite-Erstellung, unabhängiger Zustand pro Ziel | Ein echter Scan und parallel CUPS+Paperless, keine Hänger/Überhitzung |
| Fehler/Neustart | Retrys, unklare Zustellung verlangt Bestätigung; Batch-/Gelesen-Status bleibt nach Neustart | Abbruch der Netzverbindung und Neustart während aktiver Zustellung |
| Backup/Restore | Komplettbackup einschließlich ausschließlich interner Spool-Hardlinks; JSON-Export mit referenzsicherer Buttonzuordnung, Credential-ID-Schutz | Offline-Backup erstellen, Wiederherstellung in einen **separaten** Testpfad, verschlüsselte Verwahrung prüfen |
| Ressourcen | Maximal zwei Worker und begrenzte Dateien in CI überprüfbar; keine echte Belastungsmessung | < 1 GiB RAM, 32-Bit Debian 12, CPU, SSD, zwei Transfers, Laufzeit unter Last prüfen |

## Sichere lesende Vor-Ort-Prüfung

Im Verzeichnis des Entwicklungsstandes:

```bash
bash scripts/beta3-n1800-audit.sh
bash release-preflight.sh
bash release-check.sh --check
```

Die drei Befehle installieren nichts, scannen kein Dokument, senden keine Dateien, erstellen keine Druckjobs und verändern weder GRUB noch Dienste. `scanimage -L` sucht lediglich Geräte und kann bis zu 15 Sekunden dauern. Ein Live-Abnahmetest benötigt anschließend bewusst separate Freigabe vor Ort.

## Manuelle Abnahmesequenz

1. **Vorher Sicherung**: aktuelles Image/Konfiguration und relevante Daten extern sichern; verfügbaren SSD-Platz notieren. Vor späterer Rücksicherung Zustelldienst und GUI sauber beenden. Kein Docker-/Volume-Reset.
2. **Systemstart**: GRUB/Splash, Bootdauer, Scanner-Erkennung, 1024×768-Auflösung, Display/Touch und externe Scantaste kontrollieren. `systemd-analyze` lesen. Bootloader nicht automatisch ändern.
3. **Scan ohne Ziele**: Mehrseiten-Duplex-PDF in 300 dpi aufnehmen; Vorschau drehen, löschen, verschieben, erneut scannen, abschließen. Original muss erhalten bleiben.
4. **Startseite und Rechte**: im Web zwei Buttons mit unterschiedlichen Farben/DPI/Duplex anlegen; Gruppe öffnen/schließen; neue Buttonliste wird beim nächsten Aufruf angezeigt. Mit eingeschränktem PIN-Nutzer fremde Ziele verbergen.
5. **Ein Scan, zwei Ziele**: Button mit Paperless und einem installierten CUPS-Drucker. Vordergrundstatus zeigt beide Ziele unabhängig. Paperless-Aufgabe und CUPS-Annahme sind erst Zwischenbestätigungen; danach Dokument im DMS sowie Blatt am Gerät kontrollieren.
6. **Hintergrundmodus**: denselben Ablauf ohne Vordergrundfenster starten, Scanner-Startseite ist bedienbar. Meldezentrum öffnen, Erfolg/Fehler einsehen, als gelesen markieren und nach einem Neustart wiederfinden.
7. **Fehlerfälle**: nur eine Zielverbindung bewusst unterbrechen. Ein erfolgreiches Ziel darf nicht erneut beliefert werden; unklare Papier-/Paperless-Annahme bleibt auf `review` und darf nicht automatisch wiederholt werden.
8. **Ressourcen**: während Scan und zwei Zielübertragungen CPU, `MemAvailable`, Swap, SSD-Platz und GUI-Reaktion beobachten. Wenn Speicherdruck/OOM/übermäßiges Swapping auftreten, Beta nicht freigeben, zunächst Workeranzahl oder Prozesslast reduzieren.
9. **Recovery/Rollback**: Dienst kontrolliert anhalten, Backup aus separatem Testverzeichnis prüfen; frühere Beta starten können, ohne aktuelle Scans/Spool zu überschreiben. Kein Stable-Push.

## Veröffentlichungssperren für Block 9

- Kein Pre-Release ohne **alle drei grünen GitHub-Workflows am finalen Commit**, sauberen Quellcode und verständliche Release Notes.
- Eine virtuelle CI-Abnahme ersetzt keinen Hardwaretest. Falls Hardware nicht zugänglich, Release Notes und Status ausdrücklich als **Hardwareabnahme ausstehend** kennzeichnen. Vor einem produktiven Update Backup und Rollback bereitstellen.
- Bei offenen `sending`-Jobs oder ungeprüften `review`-Jobs keine automatische Umstellung der produktiven Installation.
- Stable, `main`, GRUB und vorhandene produktive Konfiguration unverändert lassen.

## Block-8-Funde und Korrekturen

- JSON-Konfigurationsexport erhielt Startseitenbuttons und Gruppen einschließlich sicherer Zuordnung der Ziele nach Art und Name, statt alte SQLite-Ziel-IDs blind zu übernehmen.
- SQLite-Batch-Migration wurde um das dauerhafte `read_at`-Feld für ältere Beta-3-Zwischenstände erweitert.
- Offline-Vollbackup unterstützt jetzt ausschließlich vollständig innerhalb des Spool liegende Hardlinks aus atomaren Mehrziel-Batches. Hardlinks, die auf Dateien außerhalb der Sicherung verweisen, bleiben gesperrt.
- Bei der JSON-Rücksicherung bleiben bestehende Ziel-IDs unverändert, sofern es sich um dieselben Verbindungen handelt. Eine Zieländerung bei gespeicherten Secrets oder offenen Zustelljobs wird blockiert.
- Automatisierte Regressionstests für diese Migrations-, Backup-, Credentials- und Wiederherstellungsfälle wurden ergänzt.

Der automatische CI-Prüfstand steht in GitHub Actions; Ergebnisse gehören zum jeweiligen Commit, nicht pauschal zur gesamten Geräteinstallation.
