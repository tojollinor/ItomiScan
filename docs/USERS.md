# PIN-Benutzerverwaltung: Block 5/8

**Stand 14.10.2026:** ausschließlich auf `develop/1.0.0` implementiert. **Nicht auf dem N1800 installiert oder praktisch getestet.** Stabiles `main` unangetastet.

## Bedienung

- PIN-Verwaltung ist standardmäßig **deaktiviert**. Nach dem Splash erscheint die Startseite wie zuvor.
- Im passwortgeschützten Webinterface befindet sich ein zusätzlicher Tab **Benutzer**. Dort Benutzer mit Namen, eindeutigen 4–6-stelligen Ziffern-PINs, Aktivstatus, Funktionen und zugewiesenen Profilen anlegen, ändern und löschen.
- Erst nachdem ein aktiver Benutzer eingerichtet ist, kann die PIN-Anmeldung aktiviert werden. Der letzte aktive Benutzer kann im aktiven PIN-Betrieb nicht gelöscht oder deaktiviert werden.
- Bei aktivierter PIN-Verwaltung erscheint nach dem Splash eine einfache große PIN-Zahlentastatur. Es werden ausschließlich maskierte Punkte angezeigt, keine PIN-Ziffern.
- Je nach Benutzer erscheinen nur freigegebene Funktionen auf der Touchstartseite. Scan, vorbereitete Ziele, Update, Beenden und Ausschalten werden **vor Ausführung** nochmals gegen SQLite geprüft. Fehlende Buttons allein sind kein Sicherheitsschutz.
- Persönliche Scanprofile werden den Benutzern im Web zugewiesen; ein persönliches Standardprofil wird gewählt. Diese persönliche Auswahl ändert **nicht** das globale Standardprofil der Scannerkonfiguration.
- Bei aktivierter PIN-Verwaltung werden Scanoptionen vor jedem Scan erneut auf das zugewiesene Profil gesetzt; gemeinsame Profile können dann nur über die Webadministration geändert werden.
- **Benutzer wechseln** und die automatische Abmeldung nach konfigurierbar 1–60 Minuten Inaktivität sperren die Oberfläche erneut. Ein bereits laufender Scan wird zunächst abgeschlossen. Danach werden alte Vorschaubilder und lokale temporäre Scanbilder aus der Oberfläche entfernt.
- Auch die physische Front-Scantaste ist vor der PIN-Eingabe gesperrt. Beim ersten Entsperren ist ein echter Touch-/Tastentest am N1800 nötig.

## Sicherheit und Datenhaltung

- SQLite-Tabellen `pin_users` und `pin_state` sind Bestandteil der vorhandenen lokalen Konfigurationsdatenbank. Die Zugangsdaten des Webadministrators bleiben unabhängig davon.
- Benutzer-PINs werden ausschließlich als gesalzener PBKDF2-HMAC-SHA256-Hash gespeichert, nie im Klartext. Neue PINs werden auf Eindeutigkeit gegen bestehende Hashes geprüft.
- Nach fünf falschen Eingaben wird die PIN-Prüfung global für drei Minuten gesperrt, einschließlich nach Neustart des GUI-Prozesses. PIN-Sperre betrifft **nur** den Scannerbildschirm, nicht die unabhängige Webadministration.
- Web-Änderungen an Konto, Funktionsrechten und Standardprofilen werden von der Oberfläche regelmäßig aus der Datenbank neu gelesen. Benutzer ohne gültige aktive Sitzung können keine Scannerfunktionen starten.
- PIN-Hinweise, PIN-Prüfsummen und Benutzerzuweisungen werden nicht im regulären JSON-Konfigurationsbackup exportiert. Ein automatischer Wiederherstellungsweg für Benutzerkonten ist noch nicht vorhanden; vollständiger System-/Datenbankrollback folgt in Block 8.
- Ein als einfacher Scannerbenutzer angemeldetes Konto bekommt über PIN **keine** Administratorrechte in Debian. Shutdown bleibt zusätzlich durch die bestehende eng begrenzte sudo-Regel geschützt.

## Verfügbare Funktionsrechte

`scan`, `paperless`, `copy`, `network`, `email`, `usb`, `update`, `shutdown`, `exit`. Die zugewiesenen Rechte für Paperless, Kopieren, Netzwerkordner, E-Mail und USB zeigen bis zur jeweiligen Integration **nur einen deutlichen Hinweis auf die noch nicht vorhandene Funktion**. Eine Freigabe macht diese Ziele nicht vorzeitig funktionsfähig.

## Tests und bekannte Grenzen

- Automatisierte Tests: SQLite-Benutzeranlage, PIN-Eindeutigkeit, persistente Sperrzeit, Entzug von Berechtigungen, Verbot des Löschens des letzten aktiven Nutzers, CSRF-geschützte Benutzerverwaltung im Webbrowser, HTML-Escaping, GUI-PIN-Sperre, Hardware-Scantasten-Sperre und automatische Abmeldung.
- Echte 1024×768-PIN-Touchbedienung, Performance der PIN-Hashprüfung auf dem Atom N270, Web-Verfügbarkeit im LAN, Benutzerwechsel nach realem Scannen und die physischen Standby-/Ausschaltabläufe sind noch **nicht** auf der Hardware verifiziert.
- Noch keine PIN-Rollenhierarchie oder Benutzersynchronisation mit Paperless; Ziele und Warteschlange folgen in Block 6 und CUPS in Block 7.

## Entwicklungs- und Freigaberegel

Nur `develop/1.0.0`, kein automatisches Update über den stabilen Scanner und kein Release. Der nachfolgende Block 6/8 implementiert die Dokumentenziele und robuste Übertragungswarteschlange. Stop nach diesem Block bis zum nächsten `Weiter`.
