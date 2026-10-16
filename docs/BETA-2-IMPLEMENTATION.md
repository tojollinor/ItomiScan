# ItomiScan v1.0.0-beta.2 — Umsetzungs- und Abnahmeplan

Auftrag bestätigt: Änderungen implementieren und als neue Beta veröffentlichen. Ausschließlich `develop/1.0.0` als Quellzweig, `main`/Stable unverändert. Veröffentlichungen nur nach erfolgreicher Regression/CI. Kein unbeauftragtes Update auf dem N1800.

## Blöcke (nach jedem Block Nutzer-Freigabe „Weiter“ abwarten)

1. **Monitoring und Branding:** redundante Statuskacheln aus der Übersicht entfernen; aktuelle Werte im CPU-/RAM-Graphen; RAM zusätzlich als belegter Speicher mit Fortschrittsbalken; Navigationslogo nur einmal; „Fernsteuerung“ statt „Fernbedienung“. Status: **in Umsetzung**, Code `pages.py`/`remote_pages.py` bearbeitet.
2a. **Kiosk-Mausposition vor PIN-Anzeige:** Den Mauszeiger bereits beim Start an eine neutrale Position ganz oben links setzen (und weiterhin ausblenden), bevor Login-/PIN-Tasten gerendert werden. Die Taste „2“ darf ohne Berührung weder Hover- noch Leuchteffekt zeigen. **Code umgesetzt, CI bestanden; physischer Touch-/Hover-Test noch offen.**
2b. **Kein Startseiten-Flackern bei aktivem Login:** Wenn PIN/Login aktiviert ist, direkt die Loginseite als erste sichtbare Kiosk-Ansicht zeichnen, ohne vorher die Startseite kurz einzublenden. Initiale Authentifizierung/Ansicht vor dem ersten Rendering klären, ohne geschützte Inhalte kurzzeitig sichtbar zu machen. **Code umgesetzt, CI bestanden; Sichtprüfung am N1800 noch offen.**
2. **Lokale Dokumentenvorschau:** Seitenübersicht links, aktive Seite rechts mit größtmöglicher verfügbarer Höhe bei 1024×768; vorhandenes Styling und Aktionen beibehalten. **Code umgesetzt, automatisierte GUI-Regression bestanden, reale N1800-Abnahme noch offen.**
3. **Drucker- und Paperless-Suche:** explizite Suchbedienung, transparente Grenzen von DNS-SD/mDNS/CUPS, Treffer auswählen/übernehmen; keine falschen Aussagen über geprüfte API, Zugangsdaten oder Druckerfunktion. Ausstehend.
4. **Ziel-Eingabemasken:** pro Zieltyp passende Felder, klare Hilfen und Validierung; bestehende Speicherlogik und Secrets erhalten. Ausstehend.
5. **Echte Fernsteuerung:** Browser-Liveansicht des lokalen Kiosks und zielgerichtete Bedienung unter sicherem authentifiziertem Zugriffsmodell; Atom-N270/1-GiB und LAN/TLS berücksichtigen, klare Trennung von lokaler Sitzung, Rechte-/PIN-Grenzen und Datenschutz. Exakte technische Machbarkeit und unterstützte Eingaben vor Implementierung prüfen. Ausstehend.
6. **Regression, Doku, Versionsstand, GitHub-Prerelease `v1.0.0-beta.2`:** GitHub-Checks auf *exaktem* Release-Commit, Beschreibung von nicht am Gerät geprüften Bereichen, Veröffentlichung als Prerelease, keine Stable-Promotion; Installationsweg per `curl`, nicht git clone. Ausstehend.

## Hardwarestand N1800

Beta 1 `v1.0.0-beta.1` war auf dem N1800 erfolgreich installiert; Touch und echter Scan waren bestätigt. Bestätigte dauerhafte Bootkonfiguration: Kernel `6.1.0-50-686-pae`, GRUB `GRUB_DEFAULT="itomiscan-initramfs-dep-test"`, verborgene Wartezeit 2 s, originale 53-MB-Initramfs als Rückfall, GUI bereit nach 34,500 s beim jüngsten Neustart. **In Beta 2 keine erneute Bootänderung** und kein automatischer Neustart.

## Abnahmekriterien

Jeder Punkt muss nicht nur Code enthalten, sondern über GUI und/oder Backend-Regression sowie, wo nötig, echte N1800-Abnahme verifiziert werden. Bestehende Scanner-/Webrechte und Nutzerdaten unangetastet; fehlende reale Hardwaretests transparent kennzeichnen.
