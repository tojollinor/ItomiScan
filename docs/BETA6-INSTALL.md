# ItomiScan v1.0.0 Beta 6: Browser-Fernsteuerung und Updatefenster

**Hardwareabnahme ausstehend.** Beta 6 ist ausschließlich ein GitHub-Prerelease; `main` und Stable bleiben unverändert.

## Behobene Punkte

- WebSocket-Handshake: Das im Microsoft-Edge-Netzwerkmitschnitt beobachtete Angebot `permessage-deflate; client_max_window_bits` wird nicht mehr fälschlich zurückgewiesen. Die Bridge handelt **keine Kompression** aus und überträgt weiterhin unkomprimierte, maskierte Client-Frames.
- Ein fehlendes optionales `Sec-WebSocket-Protocol` wird akzeptiert. Ein tatsächlich angebotenes und gültiges `binary`-Unterprotokoll wird weiter bestätigt. Andere angeforderte Unterprotokolle werden weiterhin abgelehnt.
- Sicherheitskontrollen (gültige Web-Anmeldung, aktiver Live-Lease, Origin, HTTPS, Frame-Grenzen und Loopback-VNC) bleiben unverändert.
- Das Kiosk-Updatefenster zeigt den Schließen-Button jetzt direkt oben rechts und nutzt eine an den N1800 angepasste Dialoghöhe. Das Fenster lässt sich jederzeit schließen, auch wenn die Updateprüfung oder Installation läuft. **Ein laufendes Update wird dadurch nicht abgebrochen**; der Hintergrundprozess läuft geschützt weiter und meldet den Abschluss in der Statusanzeige.

## Installation über den bestehenden Beta-Updater

Auf Beta 5: Kiosk-Oberfläche → Updates → Auf Updates prüfen → neue Beta 6 bestätigen. Vorher laufende Scans und offene Zustellungen abschließen, Konfigurations- und Datenbackup prüfen. Der privilegierte Beta-Updater verifiziert das Prerelease und den Git-Commit sowie die Dateihashes, sichert die vorherige Programmversion und kann diese über den bestehenden Rollback-Weg wiederherstellen. Nach erfolgreichem Update das Gerät kontrolliert neu starten.

**Keine erneute systemd-/SSH-Migration erforderlich**, wenn die in Beta 5 dokumentierte X11-Migration bereits aktiv ist (`PrivateTmp=no`). Bestehende Systemdienstdateien werden durch den Web-Updater nicht verändert. Falls noch `PrivateTmp=yes` aktiv ist, gilt weiterhin die gesonderte Migrationsanleitung in `docs/BETA5-INSTALL.md`.

## Abnahme

- Browser: Start/Stop/Neuverbinden, HTTP 101 WebSocket-Upgrade in Edge, Livebild, Maus- und Tastatureingaben.
- Updatefenster: Schließen ohne aktive Aufgabe, während Prüfung und während laufender Installation; Hintergrundstatus und Fortschritt, nach Abschluss neuer Dialog.
- Rollback, Neustart, Scans, Duplex/PDF, Systemmonitor und TLS-Verhalten auf dem echten ScanSnap N1800.

**Hardwareabnahme ausstehend.** Die automatischen Tests ersetzen keinen Vor-Ort-Test. Keine automatische Stable-Publikation.
