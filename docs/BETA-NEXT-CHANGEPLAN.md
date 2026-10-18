# ItomiScan – nächstes Beta-Änderungspaket

Stand: 2026-10-18. Status: Umsetzung freigegeben; neuer Blockplan in `docs/BETA3-IMPLEMENTATION-PLAN.md`. Nicht als veröffentlicht, installiert oder am N1800 abgenommen betrachten.

## Geltung und Grenzen

- Ziel: Beta ausschließlich aus `develop/1.0.0`; `main` und Stable unverändert.
- Vor Release vollständigen tatsächlichen Code-/CI-Stand prüfen. Keine Behauptung erfolgreicher Hardwaretests ohne Messung.
- Bestehendes ItomiScan-Design wiederverwenden. 1024×768, Intel Atom N270 und ~1 GiB RAM berücksichtigen.
- Sicherheitskritische Webaktionen nur authentifiziert mit CSRF-Schutz, eingeschränkten Rechten, Bestätigung, Schutz laufender Aufträge.
- Boot-/GRUB-/Plymouth-Änderungen NICHT automatisch beim normalen Beta-Update auf Scanner anwenden. Backup, Einmalstart und Rollback bleiben explizite gerätebezogene Schritte.

## Änderungsregister (Status jeweils: offen, sofern nicht anders nachgewiesen)

| Kennung | Anforderung | Status |
| --- | --- | --- |
| UI-1.5 | CPU- und RAM-Graph getrennt, 1-s-Intervall, 5 Minuten/300 Werte, laufende Prozentanzeige; nur offene Monitoring-Ansicht aktualisieren | Offen |
| UI-1.6 | Touch-PIN-Pad deutlich größer und gut bedienbar | Offen |
| UI-1.7 | Weiß-blaues ItomiScan-Logo zusätzlich in Tab-/Navigationsleiste | Offen |
| UI-1.10 | Touchpuls/visuelle Touchrückmeldung vollständig entfernen, Cursor weiter verbergen | Offen |
| WEB-1 | Benutzer, Profile, Drucker und Ziele in kompakten Listen mit Detaildialogen | Offen |
| WEB-2 | Paperless-Instanzen im LAN auffinden, Fund bestätigen, manuelle Einrichtung beibehalten | Offen |
| WEB-3 | Netzwerkdrucker bevorzugt via DNS-SD/IPP entdecken, manuelle Eingabe beibehalten | Offen |
| WEB-4 | Drucker-Dropdown für relevante Scan-/Kopierprofile, nur konfigurierte Drucker | Offen |
| WEB-5 | Zielauswahl, Namen, Auswahl- und Eingabedialoge vereinheitlichen | Offen |
| WEB-6 | Geschützte browserbasierte Fernbedienung von Profilwahl, Scanstart und Ergebnis; Konflikte mit lokaler Bedienung verhindern | Offen |
| WEB-7 | Neustart-/Herunterfahren-Buttons mit Bestätigung, Berechtigung und Auftragsschutz | Offen |
| WEB-8 | Druckersuche mit eindeutiger Geräteidentität und IP-Zuordnung: DNS-SD/mDNS (SRV/TXT/A/AAAA) auflösen und via IPP/IPPS Get-Printer-Attributes u. a. `printer-uuid`, `printer-device-id`, Hersteller/Modell sowie erreichbaren Endpunkt prüfen; Adressen nur bei belastbarer Übereinstimmung (z. B. identische UUID/Gerätekennung oder verifizierte gemeinsame Geräteidentität) zu einem physischen Drucker gruppieren. Namen, gleiche Modelle und bloße IP-Nähe reichen nicht; mehrdeutige Geräte getrennt anzeigen. In der normalen Liste ausschließlich Gerätename, zugeordnete IP-Adresse und „Hinzufügen“ anzeigen, keine Bestätigungs- oder Protokollstatus; bevorzugt intern IPPS/IPP vor LPD. Genau ein „Hinzufügen“-Button je eindeutig identifiziertem Gerät, Rückmeldung bei Verbindung/Einrichtung, keine automatische Installation ohne Klick. Details siehe `docs/PRINTER-IDENTITY-DESIGN.md`. | Geplant, nicht implementiert |
| WEB-9 | Druckerverwaltung vollständig vereinfachen: oben eingerichtete Geräte mit kompakten Aktionen, darunter automatisch erkannte Geräte je physischem Drucker mit „Hinzufügen“; manuelle technische Einrichtung nur unter „Erweitert“, CUPS-Details nicht in Hauptliste, globale Lade-/Erfolg-/Fehlerrückmeldungen und unveränderte Sicherheitsprüfungen; Konzept in `docs/PRINTER-PAGE-UX-DESIGN.md`. | Geplant, nicht implementiert |
| UI-2.1 | Frei erstellbare/änderbare Startseiten- und Gruppenbuttons mit **Farbwahl und eigenen Scaneinstellungen je Button** (Duplex, DPI, Farbe, Ausgabe etc.), beliebig mehreren gespeicherten Zielverbindungen, tatsächlicher ressourcenbegrenzter paralleler Zustellung nach einmaligem Scan; pro Button Fortschrittsfenster oder Hintergrundübertragung; Status aller Ziele, persistentem zentralem Erfolg-/Fehler-/Warnungsbereich auf dem Scanner. Konzept: `docs/HOME-BUTTON-EDITOR-DESIGN.md`. | Geplant, nicht implementiert | 
| WEB-10 | Paperless-ngx-Integration verständlicher: Schritt-für-Schritt-Tokenhilfe, erforderliche Upload-Berechtigungen, HTTPS-Basisadresse, Tokenprüfung mit sicherem nicht-schreibendem API-Request, testbare Verbindung pro gespeichertem Ziel, differenzierte Ursachen für 401/403/404/TLS/Proxy/Timeout ohne Offenlegung von Token/Servergeheimnissen; optional OAuth/OIDC als gesonderte spätere Erweiterung nach Machbarkeits-/Sicherheitsprüfung. Konzept: `docs/PAPERLESS-CONNECTION-DESIGN.md`. | Im Code implementiert (Token-Login/Lesediagnose), CI grün, N1800-Abnahme offen; OAuth nicht implementiert |
| UI-2.2 | Bildschirmschoner immer nach konfigurierter Leerlaufzeit, auch bei offener PIN-Eingabe; 30 s später sicherer Logout, aktiven Scan/Druck nicht abbrechen; Aufwachen ohne Klickdurchgriff | Offen |
| UI-2.3 | Nach jedem abgeschlossenen Touchklick unsichtbaren Mauszeiger auf (0,0) bewegen; keine Buttons im Hoverzustand, ohne Remote-Klicks zu verfälschen | Offen |
| UI-2.4 | Einheitliche, ressourcensparende Ladeanzeige für potenziell längere Vorgänge (Suche, Speichern, Scannen, Senden, Updates etc.), mit echten Status- und Fehlerzuständen | Offen |
| WEB-11 | Fernsteuerung: tatsächliches Screenshot-Seitenverhältnis, korrekte Touchkoordinaten und geringere Latenz bei begrenzter CPU-Last; bestehende Sitzungserneuerung beibehalten | Offen |
| SCAN-1 | Scannerinitialisierung nach bedienbarer Oberfläche im Hintergrund, Hardwarebereitschaft vor Scan erzwingen | Offen |
| SCAN-2 | Geräte-/Optionscache mit Hintergrundvalidierung; kein Cache als Nachweis echter Geräteverfügbarkeit | Offen |
| SCAN-3 | Früher Scanstart wartet mit Ladeanzeige, beginnt erst nach Scannerbereitschaft | Offen |
| DOC-1 | Übersicht vor Versenden, Seiten drehen/löschen/sortieren, leere Seiten entfernen, erneut scannen und hinzufügen | Offen |
| DOC-2 | Scanvorschau auf 1024×768 vollständig in der verfügbaren Inhaltshöhe nutzen: links durchgehende scrollbare Miniaturleiste, rechts maximal große Seitenvorschau, kompakte feste Aktionsleiste; Details in `docs/SCAN-PREVIEW-HEIGHT-DESIGN.md` | Geplant, nicht implementiert |
| BOOT-1 | Einheitlicher Plymouth-/GUI-Splash mit Logo sowie Schriftzug „Itomi“ weiß / „Scan“ blau; sichtbare Übergänge soweit hardwarebedingt möglich reduzieren | Code teilweise vorhanden; Hardwareabnahme offen |
| BOOT-2 | Optimierte 16-MB-Initramfs (`MODULES=dep`) mit gesonderter Opt-in-Aktivierung und Original als Rückfall erhalten | Einmaliger Boot-Test erfolgreich; dauerhafte Einrichtung offen |
| BOOT-3 | Boot-Messungen, SANE-Optimierung und Nachweis 38,300 s bis GUI dokumentieren, erneute Messung nach Integration | Einmalige Messung vorhanden; Abschluss offen |

## Boot-Teststand (über SSH-Ausgaben des Nutzers)

- Hardware Debian 12 i386, Kernel `6.1.0-50-686-pae`; ursprüngliche Initramfs 53 MB, Test 16 MB.
- Separate Initramfs unter `/boot/initrd.img-6.1.0-50-686-pae-dep-test`; GRUB-Testeintrag `itomiscan-initramfs-dep-test`.
- GRUB-Einmalstart ausprobiert; `next_entry=` nach Neustart zurückgesetzt.
- Original-Start: 33,215 s Linux; 42,420 s GUI bereit. Test: 28,929 s Linux; 38,300 s GUI bereit.
- Frühere GUI-Messung 58,190 s; SANE-Beschleunigung auf Branch: `0d25d599f26a432c756ff22072be7d5867a044bb`.
- Scanner- und Touch-Funktion **nach** Initramfs-Test noch nicht durch den Nutzer bestätigt.
- iTCO-Hardware-Watchdog durch BIOS deaktiviert; keine automatische Rückfallgarantie. Deshalb vor jeder bleibenden Bootänderung physische Rettungsmöglichkeit vorsehen.

## Neuer freigegebener Umsetzungsauftrag

Der bisherige Blockplan war vor WEB-8–11 und UI-2.1–2.4 entstanden. Der vollständige neue Blockplan ist in [BETA3-IMPLEMENTATION-PLAN.md](BETA3-IMPLEMENTATION-PLAN.md) dokumentiert. Nach jedem Block Stopp bis „Weiter“.

## Historischer Blockplan (ersetzt durch BETA3-IMPLEMENTATION-PLAN.md)

1. Ist-Stand, KB/Weisungen und Änderungsregister prüfen/erstellen.
2. GUI: PIN, Branding/Tab, Touchrückmeldung, zusammenhängender Splash.
3. Webadmin: 1-s-Systemgraphen, Listen und Detaildialoge.
4. Zielverwaltung: Paperless-/Drucker-Suche, Druckerwahl, Beschriftungen, Fernsteuerung, Poweraktionen.
5. Scan-/Dokument-Workflow: Hintergrundscanner, Cache, Ladeanzeige und vollständige Seitenbearbeitung.
6. Bootpaket mit sicherem Opt-in-/Rollback-Weg, Regression, CI und N1800-Abnahmeplan.
7. Beta-Versionierung, Release-Artefakte und nachgewiesene Veröffentlichung, ohne Stable-Promotion.

Kein Punkt als erledigt markieren, bevor Implementierung und geforderte Tests tatsächlich überprüft sind.
