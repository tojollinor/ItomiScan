# ItomiScan 1.0.0: Vorabnahme und Release-Sperre (Block 8/8)

**Stand 14.10.2026:** Die Entwicklung der Blöcke 1–8 befindet sich ausschließlich auf `develop/1.0.0`. Dies ist **kein** freigegebener Stable-Release. `main` und der auf dem Scanner verwendete Prototyp bleiben unverändert. GitHub Actions ersetzen keinen echten N1800-Hardwaretest.

## Zusätzliche UI-/Web-Korrekturrunde (15.10.2026)

Die zehn nachträglich beauftragten Korrekturen zu Boot-/App-Splash, Touchoberfläche,
Vollbildmenü/Bildschirmschoner, Mauszeiger/Touchpuls, Benutzerverwaltung und
Web-Systemdiagnose wurden im Entwicklungszweig bearbeitet. Maßgeblicher
Abnahmeplan mit vollständigen Gerätenachweisen:
[`docs/ACCEPTANCE-UI-WEB-2026-10-15.md`](ACCEPTANCE-UI-WEB-2026-10-15.md).

**Abnahme weiter gesperrt:** Die Korrekturen gelten nicht allein durch Commits,
CI-Warteschlangen oder Quellcodeprüfung als bestätigt. Boot-Plymouth muss
separat installiert werden; ein normales GUI-Update reicht nicht.
`main`, Stable-Tag und auf dem N1800 installierte Version bleiben unberührt.

## Lieferumfang und Grenzen

- Originale SANE-Scanpipeline mit schnellem JPEG/PDF-Pfad, Splash, großer Touchstartseite, konfigurierbaren Scanprofilen und vollständiger Expertenansicht.
- HTTPS-Webadmin, optionale PIN-Benutzer mit Rechteprüfung, Paperless-/SMB-/SMTP-/USB-Ziele und CUPS-Kopieren.
- Dauerhafte lokale SQLite-/PDF-Warteschlange mit SHA-256, Fehlerstatus `review` bei unklarer Paperless-/Mail-/Druckübernahme und gesondertem nicht privilegiertem Worker.
- Vollständige **offline** Systemsicherung mit Scanoriginalen, Spool, SQLite-Benutzern/PIN-Hashes und Geheimnissen. ZIP-Dateien werden ohne Komprimierung gestreamt, um CPU und RAM zu schonen. SHA-256-Verifikation und Wiederherstellung **nur in einen neuen Staging-Ordner**. Niemals direkt über eine laufende Datenbank entpacken.
- Read-only-Vorabcheck für Abhängigkeiten, SQLite-Zustand, RAM, freien Speicher und SANE-Geräteerkennung. Hardwareabnahme gilt unabhängig vom CI-Erfolg weiterhin als **offen**.
- Manuell freizugebende lokale Einrichtungsskripte `setup-web.sh`, `setup-delivery.sh` und `setup-printing.sh` (CUPS verlangt zusätzlich bewusst eingerichtete Gruppenrechte). Keine automatische Ausführung auf `main`.

## Prüfen ohne Installation

Im Entwicklungsverzeichnis als normaler Scannerbenutzer:

```bash
cd ~/ItomiScan
bash release-check.sh
python3 -B -m itomiscan.release_preflight --json
```

Der Vorabcheck scannt keine Seite und verschickt keine Daten. Er setzt **nie** `release_allowed=true`. Für eine spätere tatsächliche Geräteabnahme muss die Entwicklungsfassung bewusst auf dem N1800 installiert werden. Das erfolgt nicht durch diese Checks.

## Komplette Datensicherung

Die vorhandenen Dienste und die Kiosk-Anwendung vor der **offline** Sicherung anhalten. Sicherungsdatei auf ein geschütztes Speichermedium **außerhalb** der gesicherten Verzeichnisse schreiben:

```bash
python3 -B -m itomiscan.storage.backup_cli create /SICHERER/PFAD/itomiscan-vor-update.zip
python3 -B -m itomiscan.storage.backup_cli verify /SICHERER/PFAD/itomiscan-vor-update.zip
python3 -B -m itomiscan.storage.backup_cli restore-to-staging /SICHERER/NEUER-ORDNER/itomiscan-vor-update.zip /SICHERER/NEUER-ORDNER/pruefung
```

**Achtung:** Die ZIP-Sicherung enthält unverschlüsselte private Dokumente, Passwörter, API-Tokens, TLS-Schlüssel und PIN-Hashes. Datei ausschließlich verschlüsselt außerhalb des Gerätes aufbewahren. In den ersten Tests wurde die Sicherung in einen neuen Staging-Ordner erfolgreich zurückgespielt, nicht in das laufende System.

Der Dienst benutzt einen exklusiven Worker-Lock, um konkurrierende PDF-Zustellungen zu verhindern. Die Sicherung verweigert einen aktiven Worker oder einen gerade sendenden Auftrag. Vor dem Sichern alle relevanten Dienste beenden und nach der Sicherung ihre jeweiligen Status prüfen.

## Kontrollierter Codewechsel (noch nicht ausführen)

Ein späterer Wechsel auf den explizit freigegebenen Git-Tag kann über das gesonderte Skript `release-switch.sh` nach Anhalten der Dienste und erfolgreichem Vollbackup erfolgen. Es verändert **keinen** Branch auf GitHub und bewegt `main` nicht. Es erlaubt nur `v1.0.0`, die zuvor angelegte Prototyp-Sicherungsreferenz oder eine konkrete 40-stellige Commit-ID. Der Codewechsel erzeugt keine automatische Datenbank-Rückmigration und startet keine Dienste neu.

Der Tag `v1.0.0` wird **erst nach ausdrücklicher Endfreigabe** angelegt; solange er nicht existiert, darf ein Umstieg auf diesen Tag nicht möglich sein.

## Hardware-Abnahmeprotokoll: alles noch OFFEN

| Bereich | Benötigter praktischer Test auf Fujitsu N1800 |
| --- | --- |
| Start | BIOS/Textausgaben so wenig wie möglich; Splash erscheint, SANE und Touch werden erkannt, Fehler/Timeout sind verständlich |
| Touch | Volle 1024×768-Anzeige, Touchkalibrierung, PIN-Tastatur, Benutzerauswahl, Bildschirmschoner, keine unbeabsichtigten Klicks |
| Physische Taste | Scannen aus Startansicht, PIN-Sperre, Kopiermodus und Dialoge; keine Doppelstarts |
| Scanner | Einseitig/Duplex, Seitenreihenfolge, Farben/Gray/Lineart, 200/300 DPI, ADF-Leerfach und Doppeleinzug |
| Datei | Mehrseitige PDFs, PNG, große Dokumente, Bildvorschau; originaler schneller JPEG/PDF-Pfad weiterhin funktionstüchtig |
| Benutzer | Aktivierung/Deaktivierung, fehlerhafte PIN, Sperrzeit, Inaktivitätsabmeldung, Rechtewechsel während Sitzung |
| Webadmin | HTTPS über LAN/VPN, Zertifikate, Login/CSRF, Einstellungen, Zustand und Neustart der Dienste |
| Ziele | Echtes Paperless-Upload inkl. Verarbeitung, SMB-Schreibrechte, SMTP/TLS, eingehängter und entfernter USB-Stick |
| Fehler/Recovery | Netzwerkunterbrechung während Transfer, Neustart mit wartenden Jobs, manuelle Prüfung unklarer Zustellung |
| CUPS | Druckerregister/Testseite, echtes Kopieren 1/2-seitig, Mehrfachkopien, Papiermangel und Wiederholungsfälle |
| 1 GiB RAM | CPU-Last, RAM-Spitzenwerte und Wechsel zwischen Scan/Web/Worker während mehrseitigem Farbduplex |
| Sicherung | Vollbackup auf externem verschlüsseltem Medium, Verifikation, Probewiederherstellung, kontrollierter Rollback |
| Ausschalten | Schaltfläche und reale Hardware-Poweroff-Regel funktionieren, Scannen unterbricht kein Herunterfahren |
| Endfreigabe | Nutzer bestätigt Hardwaretest und erlaubte Stable-Promotion ausdrücklich |

## Offene technische Grenzen

- Scanner- und Druckertests sind aktuell simuliert beziehungsweise auf generischen CI-Runnern ausgeführt worden. Ein CI-Erfolg ist **kein physischer Scan- oder Drucknachweis**.
- Vollbackup und Staging-Restore sind vorhanden, eine automatische Live-Restore-Prozedur ist absichtlich **nicht** vorhanden.
- Automatische Bereinigung erfolgreicher Spool-Jobs ist absichtlich deaktiviert. Aufbewahrungsfristen und löschsichere Bestätigungen sind gesonderte Verbesserungen, damit Dokumente nicht unbemerkt verschwinden.
- Paperless meldet zunächst Annahme zur Verarbeitung; fertige OCR/Archivierung ist gesondert zu prüfen.
- Kein eigenständiges OCR auf dem N270. Komplexe Seitenbearbeitung und automatische USB-Mounts sind nicht in 1.0.0 implementiert.
- Finale Versionskennzeichnung, Änderung von `main`, Tag, Release-Seite und Deployment sind ausdrücklich **nicht freigegeben**.

## Entscheidung nach den Tests

Falls wesentliche Gerätefunktionen fehlschlagen, ist 1.0.0 **nicht** releasefähig. Offene Punkte werden gezielt korrigiert und erneut getestet. Erst danach darf nach **neuer ausdrücklicher Nutzerfreigabe** ein Git-Tag `v1.0.0` und ein offizieller Stable-Release entstehen.
