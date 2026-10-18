# ItomiScan: Beta 3 Implementierung und Abnahme

Stand: 2026-10-18. **Freigabe des Nutzers: alle besprochenen Änderungen umsetzen und Beta-Update bereitstellen.** Umsetzung erfolgt ausschließlich auf `develop/1.0.0`, `main`/Stable bleiben unverändert. **Nach jedem Block stoppen bis „Weiter“.** Keine Aussage „fertig“ ohne Code-, CI- und Hardware-Nachweis.

## Ist-Stand zum Start (Block 1)

- Letzte veröffentlichte GitHub-Pre-Release: **`v1.0.0-beta.2`** (2026-10-16); `v1.0.0-beta.1` existiert ebenfalls.
- Zuletzt geprüfter Entwicklungscommit vor Blockbeginn: **`2bfcc4a88a2761fc7b732916c445a1bcac50526b`**, alle drei regulären CI-Workflows (`development checks`, `scan quality`, `Beta Checks`) erfolgreich. Keine Behauptung, dass alle gewünschten Änderungen umgesetzt seien.
- Bereits vorhanden im Entwicklungszweig: PIN-/Webverwaltung, frühe Scan-/Zustellbasis, CUPS-Basis, Hintergrundscanner, Low-FPS-Fernsteuerung, Live-Sitzungswiederherstellung, Paperless-Tokenaustausch per Benutzername/Passwort und lesende Diagnose. Die letzten Funktionen sind noch **nicht am N1800 abgenommen**.
- Nicht implementiert: dynamische Startseitenbuttons/Untergruppen/Farbe/Scanoptionen, unabhängige parallele Mehrzielzustellung, Scanner-Statuszentrum, Vollhöhen-Vorschau, neuer Bildschirmschoner-/Logout-Ablauf, Cursor-Reset, globale Ladeanzeigen, verifizierte Druckeridentität und Ein-Klick-Installation, modernisierte Druckerverwaltung, Fernbildlatenz/-Seitenverhältnis.

## Umsetzungsblöcke

1. **Ist-Stand und verbindliches Register**: Branch, Beta, CI, dokumentierte Wünsche und Schutzregeln abgleichen. Änderungsregister korrigieren, Abnahmekriterien planen. Stopp.
2. **Scanner-Touch-GUI und Navigation**: Bildschirmschoner/30-s-Logout, Touchcursor zurücksetzen, Start/PIN/Statusnavigation, DOC-2 Vollhöhen-Vorschau mit linksseitigen Symbolaktionen. Bestehende UX nahtlos fortführen. Tests. Stopp.
3. **Webadmin/UI-Status & Fernsteuerung**: allgemeine Ladeanzeigen, Webdialoge/Listen, Monitoring, bessere Fernsteuerungs-Geometrie, Koordinaten und Latenz; bereits implementierte Wiederherstellung integrieren und prüfen. Tests. Stopp.
4. **Druckerverwaltung und Discovery**: eindeutige DNS-SD/IPP/IPPS-Geräteidentität/IP-Zuordnung (WEB-8), je Gerät ein Hinzufügen-Button, echte CUPS-Queues von bloßer Erkennung unterscheiden, Ein-Klick-Installation, modernisierte kompakte Webansicht (WEB-9). Druck-/Netzwerksicherheit und Fehlerszenarien prüfen. Stopp.
5. **Paperless und Zielintegration**: Login-Token/Dokumentationshilfe/403-Diagnose/Verbindungstest nachtesten; Paperless-LAN-Suche und Zielmasken modernisieren; Upload-Erfolgszustände korrekt benennen. Kein unnötiger OAuth-Flow ohne belegte Serverunterstützung. Stopp.
6. **Dynamischer Buttoneditor im Web**: frei konfigurierbare Button-/Gruppenstruktur, Farbe/Symbol/Beschriftung, pro Button Duplex/DPI/Farbmodus/Ausgabe, mehrfach wählbare gespeicherte Ziele, sichere referentielle Migration; Scanner-Startseite dynamisch darstellen. Tests. Stopp.
7. **Mehrziel-Scan-Workflow und Statuszentrum**: ein Dokument einmal scannen, unabhängige und nachweislich parallele ressourcenbegrenzte Worker pro Ziel; atomare Zuordnung mehrerer Jobs, Vordergrund-Statusdialog oder Hintergrundbetrieb, dauerhaftes Statuszentrum auf Scanner; Wiederholungs-/Fehlerschutz, Rechte und Datenschutz. Tests. Stopp.
8. **Systemintegration und vollständige Qualitätsabnahme**: GUI-/Web-/Queue-Regression und Xvfb, Sicherheits-/SANE-/CUPS-/Paperless-Integration soweit in CI möglich, 1024×768 und 1 GiB Ressourcen; Kiosk-N1800-Testanweisungen und bestehende Boot-Beta-Vorgaben, Installations- und Rückfallweg. Keine dauerhafte GRUB-Änderung durch Beta-Update. Stopp.
9. **Beta-3-Release**: nur nach grüner finaler CI und kontrolliertem Versions-/Artefaktstand `v1.0.0-beta.3` als **Prerelease** taggen/veröffentlichen; Release-Notes, Installations-/Updateanleitung, Rückfall und tatsächlichen veröffentlichten Release prüfen. `main` und Stable nicht anfassen. Stopp, Auftrag erledigt.

## Qualitäts- und Sicherheitsregeln

- Nie fremde Credentials/Token in HTML, Logs, Exporte oder Tests schreiben. Bestehende Datenbank/Volumes erhalten, SQLite-Migration transaktional mit Rückwärts-/Rollback-Plan.
- Automatisierte Tests werden als solche bezeichnet; physische Scans/Touches/Druck/Netzwerktests nur als erfolgreich markieren, wenn tatsächlich am Gerät durchgeführt.
- Mehrzielübertragung: „parallel“ bedeutet mehr als paralleles Enqueue. Keine Doppelzustellung bei ungewissem Ergebnis, Original-PDF erhalten.
- Webauthentifizierung/CSRF, Touch-PIN-Rechte, Druckeridentitätsprüfung und TLS bleiben zwingend.
- Bestehende UI-Designmuster (Farben, Größen, Symbole, Abstände) wiederverwenden, nicht betroffene Ansichten unverändert.
- Keine ungeprüften Release-Tags, keinen Stable-Push, kein automatisches Umschreiben von Bootloader/Plymouth.

## Blockstatus

| Block | Stand |
| --- | --- |
| 1 | Abgeschlossen: Ist-Stand/Plan/Register, keine Anwendungsänderung |
| 2 | Code umgesetzt: IdleScreen (PIN zulässig, Logout nach 30 s, sichere Verzögerung bei Scan), Cursor nach Klick parken, DOC-2 Filmstreifen/Icons/Viewer; virtuelle GUI-Regression ergänzt. N1800-Abnahme offen. CI des letzten Commits prüfen. |
| 3 | Auf `develop/1.0.0` umgesetzt: globale Web-Ladeansicht (ItomiScan-Scanlogo, kontextspezifische Texte, Doppelsubmit-Sperre), Bildseitenverhältnis und 900-ms-Bildabfrage in Web-Fernsteuerung, 800-ms-Bildaufnahmen bei aktivem Viewer mit 120-ms-Kiosk-Polling. Bestehendes 1-s-Monitoring (CPU-/RAM-Werte und 300-Punkte-Diagramme) geprüft und erhalten. Neue Web-Regressionsprüfung; CI-/Hardwareergebnis gesondert nachweisen. |
| 4 | Kernfunktionen umgesetzt: bestätigte IPP-UUID-Zuordnung aus lokalem mDNS/IPv4, gespeicherte UUID gegen doppelte Einrichtung und bei Backup/Restore, CUPS `lpstat -v` statt `-e`, moderne Druckerübersicht und ein Klick zum Hinzufügen mit erneuter Identitätsprüfung. Automatisierte Tests vorhanden; N1800/Brother und IPPS-Zertifikat/IPP-Everywhere-Kompatibilität noch nicht geprüft. IPv6/AAAA und Geräte ohne IPP-UUID nur über manuelle Einrichtung, weitere Kompatibilität für Hardwareabnahme notieren. |
| 5–9 | Offen, Freigabe je Fortsetzung über „Weiter“ |
