# ItomiScan v1.0.0-beta.2 — Umsetzungs- und Abnahmeplan

Auftrag bestätigt: Änderungen implementieren und als neue Beta veröffentlichen. Ausschließlich `develop/1.0.0` als Quellzweig, `main`/Stable unverändert. Veröffentlichungen nur nach erfolgreicher Regression/CI. Kein unbeauftragtes Update auf dem N1800.

## Blöcke (nach jedem Block Nutzer-Freigabe „Weiter“ abwarten)

1. **Monitoring und Branding:** redundante Statuskacheln aus der Übersicht entfernen; aktuelle Werte im CPU-/RAM-Graphen; RAM zusätzlich als belegter Speicher mit Fortschrittsbalken; Navigationslogo nur einmal; „Fernsteuerung“ statt „Fernbedienung“. Status: **Code umgesetzt, CI für Block 1 und 2 bestanden**, reale Browserabnahme offen.
2a. **Kiosk-Mausposition vor PIN-Anzeige:** Den Mauszeiger bereits beim Start an eine neutrale Position ganz oben links setzen (und weiterhin ausblenden), bevor Login-/PIN-Tasten gerendert werden. Die Taste „2“ darf ohne Berührung weder Hover- noch Leuchteffekt zeigen. **Code umgesetzt, CI bestanden; physischer Touch-/Hover-Test noch offen.**
2b. **Kein Startseiten-Flackern bei aktivem Login:** Wenn PIN/Login aktiviert ist, direkt die Loginseite als erste sichtbare Kiosk-Ansicht zeichnen, ohne vorher die Startseite kurz einzublenden. Initiale Authentifizierung/Ansicht vor dem ersten Rendering klären, ohne geschützte Inhalte kurzzeitig sichtbar zu machen. **Code umgesetzt, CI bestanden; Sichtprüfung am N1800 noch offen.**
2. **Lokale Dokumentenvorschau:** Seitenübersicht links, aktive Seite rechts mit größtmöglicher verfügbarer Höhe bei 1024×768; vorhandenes Styling und Aktionen beibehalten. **Code umgesetzt, automatisierte GUI-Regression bestanden, reale N1800-Abnahme noch offen.**
3. **Drucker- und Paperless-Suche:** Explizite authentifizierte Suchknöpfe, CUPS- und mDNS/DNS-SD-Fundlisten, direkte manuelle Übernahme in Eingabemasken, keine automatischen Netzwerksuchen beim normalen Seitenaufruf; IPP/IPPS-Treffer auf private IPv4 beschränkt. `avahi-utils` in Beta-Installer ergänzt. **Code umgesetzt, CI für finalen Blockstand noch zu bestätigen; praktische N1800-Netzwerkabnahme offen.** Paperless ohne DNS-SD-Ankündigung kann nicht gefunden werden; es findet kein unspezifischer LAN-Portscan statt.
4. **Ziel-Eingabemasken:** Getrennte Formularelemente für Paperless (HTTPS), SMB (Server/Freigabe/Unterordner), E-Mail (STARTTLS/SMTPS, Server, Port, Empfänger) und USB (Datenträger/Unterordner) samt optionale vollständige Zieladresse implementiert. Server setzt Adressen aus Einzelfeldern zusammen und führt die vorhandene Validierung unverändert aus. SQL-Schema und separate Zugangsdaten unverändert; HTTP- und Kompatibilitätstests bestanden. **Code umgesetzt und CI bestanden; reale N1800-Oberflächenabnahme noch offen.**
5. **Browser-Fernsteuerung:** Zeitlich begrenzte, angemeldete Liveansicht des Kiosks über aktualisierte JPEG-Bilder, Klicks und ausgewählte Tasten. Gleichzeitige Betrachtung auf eine Sitzung begrenzt, Bilder nur bei aktiver Nutzung und danach gelöscht. Zusatzbibliothek `libxtst6` im Installer. **Code und Testfälle ergänzt; reale X11-Bildanzeige und Eingaben am N1800 weiterhin zu prüfen.** Bildaktualisierung etwa alle 1,5 Sekunden, keine flüssige Videoübertragung.
6. **Regression, Doku, Versionsstand, GitHub-Prerelease `v1.0.0-beta.2`:** GitHub-Checks auf *exaktem* Release-Commit, Beschreibung von nicht am Gerät geprüften Bereichen, Veröffentlichung als Prerelease, keine Stable-Promotion; Installationsweg per `curl`, nicht git clone. Ausstehend.

## Hardwarestand N1800

Beta 1 `v1.0.0-beta.1` war auf dem N1800 erfolgreich installiert; Touch und echter Scan waren bestätigt. Bestätigte dauerhafte Bootkonfiguration: Kernel `6.1.0-50-686-pae`, GRUB `GRUB_DEFAULT="itomiscan-initramfs-dep-test"`, verborgene Wartezeit 2 s, originale 53-MB-Initramfs als Rückfall, GUI bereit nach 34,500 s beim jüngsten Neustart. **In Beta 2 keine erneute Bootänderung** und kein automatischer Neustart.

## Abnahmekriterien

Jeder Punkt muss nicht nur Code enthalten, sondern über GUI und/oder Backend-Regression sowie, wo nötig, echte N1800-Abnahme verifiziert werden. Bestehende Scanner-/Webrechte und Nutzerdaten unangetastet; fehlende reale Hardwaretests transparent kennzeichnen.
