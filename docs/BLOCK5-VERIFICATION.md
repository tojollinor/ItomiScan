# ItomiScan 1.0.0: Block 5, Integration und Sicherheitsabnahme

Status: Softwaretests im Entwicklungsbranch durchgeführt; **N1800-Hardwareabnahme ausdrücklich ausstehend**. Keine Beta-Veröffentlichung in diesem Block.

## Prüfung VNC und Webadministration

- WebSocket-Handshake nur nach Webanmeldung und gültiger Live-Sitzung.
- Cross-Origin-WebSocket-Anfragen werden abgewiesen; das binäre Subprotokoll ist verpflichtend.
- CSP erlaubt ausdrücklich nur WSS zur gebundenen eigenen Webadresse; keine Wildcard.
- Authentifizierter, bidirektionaler Binärdatenstrom wurde zwischen einem lokalen Testclient und einem simulierten VNC-Backend getestet. Paketgrößenbegrenzung, Maskierung und Fragmente werden validiert.
- x11vnc startet nur nach Bedarf und bindet ausschließlich an localhost. Zweite Besitzer und fehlende Pakete sind in den Unit-Tests abgedeckt.
- Bei einem erneuten Verbindungsaufbau können verspätete Disconnect-Events der alten Browser-Verbindung nicht mehr den neuen Verbindungsstatus übersteuern.
- Weder echter x11vnc-Prozess noch echtes N1800-Bild oder die HTTPS-Zertifikat-Aushandlung wurden durch den simulierten Backend-Test verifiziert.

## Prüfung Beta-Updater und Rollback

- Es werden ausschließlich veröffentlichte Beta-Tags des offiziellen Repositories ausgewählt. Der unveränderliche Git-Commit und die Git-Blob-Dateihashes dienen zur Integritätsprüfung.
- Installations- und Rollback-Ablauf wurden in temporären Testverzeichnissen simuliert. Sowohl ein fehlgeschlagener Verzeichnisaustausch als auch ein Fehler nach der Installation stellen den vorigen Programmstand wieder her.
- Symlinks und manipulierte/überschüssige Archivdateien werden abgewiesen. Unsichere oder unvollständige Git-Dateilisten führen zum Abbruch.
- Der privilegierte Wiederherstellungshelfer benutzt für die Zwischenablage gescheiterter neuer Installationen keine vorhersehbaren, benutzerkontrollierten Verzeichnisse.
- Bei manuell installierten Entwicklungsständen ohne verlässliches Beta-Tag muss die GitHub-Compare-API einen echten Vorwärtswechsel bestätigen; der Button darf nicht unbeabsichtigt eine ältere Beta anbieten.
- Kein tatsächlicher Download/Installationsvorgang oder Neustart auf dem N1800 durchgeführt. Das Upgrade-Prozedere einer noch zu veröffentlichenden Beta benötigt zuerst eine manuelle Bootstrap-Installation.

## Prüfung Systemmonitoring

- CPU/RAM-Erfassung beginnt unabhängig vom Browser mit dem Start des Webdienstes; sekündliche Messwerte werden auf maximal 300 Punkte und maximal fünf Minuten in einem RAM-Ringpuffer begrenzt.
- RAM-Nutzung weiterhin als `MemTotal - MemAvailable` mit Grenzwert- und Cache-Plausibilitätstests.
- Festplattenbelegung wird als eigene Fortschrittsanzeige angezeigt.
- HTTP-Historie ist erst nach Anmeldung zugänglich. Die Browser-Grafiken laden beim Öffnen und nach Rückkehr zu einem zuvor versteckten Tab erneut die Serverhistorie; Messlücken werden ohne erfundene Verbindungsstriche dargestellt.
- Kein zusätzlicher SSD-Schreibprozess für die Messhistorie. Die Daten gehen bei Webdienstneustart verloren.

## Ausdrücklich offene Hardwaretests

1. Neue Beta zunächst kontrolliert auf dem N1800 installieren und danach Dienste-/Versionsstatus feststellen.
2. x11vnc-Pakete und Start unter dem tatsächlichen Xorg-Display :0 prüfen; Bild, Maus, Touch und Tastatur im Browser testen.
3. WebSocket über das reale HTTPS-Zertifikat und die tatsächliche LAN-Adresse testen.
4. CPU-, RAM- und Netzwerkbelastung während VNC-Sitzung messen; Standby-Verbrauch ohne Verbindung beobachten.
5. Systemmonitoring mindestens fünf Minuten ohne Browser laufen lassen, danach Verlauf öffnen, neu laden, Tab verstecken und wieder öffnen.
6. Beta-Update und letzten Rollback nach einer sicheren Systemdatensicherung praktisch testen, danach kontrollierten Neustart durchführen.
7. Bestätigen, dass Scannen, Zustellung, Drucken, Boot-Splash und PIN-Kiosk unverändert funktionieren.

**Keine Veröffentlichung, kein Merge nach main und keine Stable-Änderung in Block 5.**
