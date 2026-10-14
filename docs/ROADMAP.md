# ItomiScan 1.0.0: verbindlicher Umsetzungsplan

Stand: 13.10.2026. Planung mit **8 endlichen Blöcken**. Nach jedem Block stoppen und erst auf „Weiter“ fortfahren. Keine stillschweigende Erweiterung des Umfangs; größere neue Wünsche für spätere Version vormerken.

| Block | Lieferumfang | Abnahme |
| --- | --- | --- |
| **1/8** | Absicherung, Entwicklungszweig, Modulstruktur, Dokumentation | `main` identisch zur Ausgangsbasis; separate Sicherung; Entwicklungsdateien auf `develop/1.0.0` |
| **2/8** | Boot-/App-Splash, Bereitschaftsprüfung, Fehleranzeige | N1800 startet ohne unnötige Konsolenausgaben (soweit hardwareseitig möglich), GUI erst bei Bereitschaft |
| **3/8** | Große Touchstartseite, Design/Logo, Scanprofile, Scanvorschau, Bildschirmschoner | Scans/PDF, physische Taste und Vollbild weiterhin nutzbar |
| **4/8** | Geschützte Webadministration, Konfiguration, Diagnose, Status, Sicherung | Administration im LAN, Login/Passwort und grundlegende Härtung geprüft |
| **5/8** | Optionale PIN-Benutzer, Rechte, Profile, Abmeldung | Ohne PIN direkt zur Startseite; mit PIN nur freigegebene Funktionen |
| **6/8** | Paperless, Netzwerkziel, E-Mail, USB, zuverlässige Auftragswarteschlange | Erfolgreiche Ablage und Fehler-/Netzwerkausfalltest |
| **7/8** | CUPS-Netzwerkdrucker, Kopierfunktion, Druckaufträge | Papier scannen und auf gewähltem Drucker ausgeben |
| **8/8** | Integrationstests, 1-GiB-Optimierung, Fehlerschutz, Rollback, Installer, KB und Release | Release **1.0.0** nur nach ausdrücklicher Endfreigabe |

**Block 1:** abgeschlossen: GitHub-Sicherung und Paketstruktur.

**Block 2:** App-Splash, asynchrone Hardwarebereitschaft, Fehleransicht, Neustartversuch sowie optionales Plymouth-Einrichtungsskript auf `develop/1.0.0` implementiert. Tests unter Linux/Xvfb vorhanden; Hardwaretest/Boot-Splash-Aktivierung offen.

**Block 3:** Große 2×2-Touchstartseite, einfaches ItomiScan-Scan-Logo (flache Tk-Canvas-Zeichnung), Scanprofile mit atomarer JSON-Speicherung, Schnellscan über gewähltes Profil, alte SANE-Detailansicht mit Vorschau/Profil speichern/Zurück-Taste sowie 5-Minuten-Bildschirmschoner auf `develop/1.0.0` implementiert. Paperless/Netzwerk/Kopieren nur klar markierte Platzhalter. GitHub-Actions-Prüfungen für Syntax, Python-Unit-Tests und virtuelle GUI erfolgreich; **Praxistest am N1800 offen**.

**Block 4:** Passwortgeschützte HTTPS-Webadministration, SQLite-Konfiguration, Profile, Zieldefinitionen, Status/Diagnose und JSON-Sicherung auf `develop/1.0.0` implementiert; automatisierte HTTP-/GUI-Tests grün. Manuelles Dienst-Setup vorbereitet; Gerätetest offen. Echte Netzwerkziele/Druck bleiben für spätere Blöcke.

**Block 5:** Optionale PIN-Benutzerverwaltung mit Benutzer-/Rechteformularen in der Webadministration, PIN-Ziffernfeld auf dem Gerät, persönlicher Profilzuweisung, gesalzen gehashten PINs, Fehlversuchsperre und Abmeldung nach Inaktivität. Funktionsberechtigungen werden unmittelbar vor den Aktionen geprüft. GitHub-Tests laufen, Geräteprüfung ausstehend.

**Block 6:** Dokumentenziele Paperless-HTTPS, SMB via smbclient, SMTP/TLS und USB sowie eine dauerhaft gesicherte PDF/SQLite-Warteschlange implementiert. Touch-Zielauswahl, verschlüsselt erreichbare Webverwaltung von Zugangsdaten, Auftragsstatus und manuelle Prüfung unsicherer Zustellungen vorhanden. Optionaler separater Nicht-root-Dienst für automatische Wiederholung, nicht auf N1800 installiert. CI/Offline-Tests bestanden; reale Netzwerk-/USB-Gerätetests offen. Originalscan bleibt lokal erhalten.

**Blöcke 7–8:** noch nicht umgesetzt. Release 1.0.0 erst nach ausdrücklicher Endfreigabe.

**Technische Randbedingungen:** Kein unnötiger RAM-/CPU-Verbrauch; bestehendes `app.py` und aktuelle SANE-Funktion nicht unnötig umbauen. GitHub-Commits sind Implementierungsnachweise, kein Beleg für Hardwaretests.
