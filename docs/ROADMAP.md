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

**Block-1-Status:** Umsetzung der GitHub-Sicherung und Paketstruktur; lokale N1800-Installation bleibt unangetastet. Keine bereits geplanten Funktionen der Blöcke 2–8 als umgesetzt ausgeben.

**Technische Randbedingungen:** Kein unnötiger RAM-/CPU-Verbrauch; bestehendes `app.py` und aktuelle SANE-Funktion nicht unnötig umbauen. GitHub-Commits sind Implementierungsnachweise, kein Beleg für Hardwaretests.
