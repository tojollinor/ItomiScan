# ItomiScan: UI-/Web-Korrekturrunde und N1800-Abnahme

**Stand:** 15.10.2026  
**Status:** Quellcode auf `develop/1.0.0` geändert; Geräteinstallation und praktische Abnahme **offen**.  
**Wichtig:** Dies ist eine Test-/Releasevorbereitung, keine Bestätigung eines Stable-Releases.

## Verbindlicher Umfang: zehn Änderungsnummern

| Nr. | Korrektur | Implementierung im Entwicklungszweig | Hardware-/Browsertest |
| --- | --- | --- | --- |
| 1 | Plymouth-Bootsplash und Tk-Startbild optisch vereinheitlichen, Übergang optimieren | Gemeinsame Markenparameter/Assets und bereinigter Opt-in-Installer; technisch unterbrechungsfreier Xorg-Wechsel nicht garantiert | OFFEN: echter Kaltstart und Bildvergleich |
| 2 | QWERTZ- und numerische Bildschirmtastatur in der unteren Displayhälfte | Toplevel auf max. halbe Displayhöhe begrenzt, Tasten verkleinert, PIN-Feld unten angeordnet | OFFEN: 1024×768, Tippen, Übernehmen/Abbrechen |
| 3 | Home-Symbol vergrößern | Größerer Touchbutton in Scan-Fußleiste | OFFEN: Erkennbarkeit/Bedienung |
| 4 | Scannen/Kopieren in Größe der Scan-Zielbuttons | Zweispaltiges, reserviertes Kachelraster | OFFEN: Größenvergleich und Freiraum |
| 5 | CPU/RAM/Datenträger/Dienste im Web-Admin | /proc, statvfs, systemctl, Status-API, 30-s-Aktualisierung | OFFEN: Live-Werte und Ressourcenlast |
| 6 | Benutzeranlage: „Ungültiger Ursprung“ | `Origin: null` nur bei gültiger Sitzung und CSRF-Token für authentifizierte POSTs; fremde Origin-Werte bleiben abgewiesen | OFFEN: realer Browser, Benutzer anlegen/ändern |
| 7 | Grafisches Logo im Web-Admin | SVG aus gemeinsamer Marken-Geometrie, zweifarbiger Schriftzug | OFFEN: Mobil/Desktop |
| 8 | Animiertes Scandokument statt Ladekreis | Tk und Plymouth verwenden Scanlinienlogo, gemeinsame Geometrie | OFFEN: Boot und Scanstart |
| 9 | Vollbildmenü, manuelle Bildschirmschoner-Aktivierung, Logo | Gemeinsame Kachelseite für Start/Scan, direkte manuelle Vorschau, zweifarbiges Branding | OFFEN: Rückweg, Rechte, Touchaufwecken |
| 10 | Mauszeiger ausblenden und Touchpuls | X11-XFixes plus Tk-Fallback, nicht interaktiver kurzer Ring | OFFEN: Mauszeiger wirklich verborgen, keine Klickblockade |

**Fernwartung ist ausdrücklich verworfen und nicht Bestandteil dieser Version.**

## Abnahme am realen Fujitsu N1800

1. Vor jeder Änderung: installierte Git-Revision notieren, aktiven Bootmodus und GRUB/Plymouth prüfen; bisherige Konfiguration und wichtige Scan-Daten sichern. Die **installierte Version** ist von GitHub-HEAD zu unterscheiden.
2. Entwicklungsstand erst nach expliziter Entscheidung für den Geräteversuch und nach geprüftem Vollbackup installieren. `main` und Stable bleiben unverändert.
3. Achtung: `setup-boot-splash.sh` ist **opt-in und wird durch GUI-Updates/normalen Installer nicht ausgeführt**. Das Skript schreibt GRUB, Plymouth und initramfs; ausschließlich auf dem Gerät nach Sicherung und mit administrativen Rechten ausführen. Ohne diesen Schritt ist keine Bootlogo-Korrektur am N1800 zu erwarten.
4. Neustarten und den gesamten Bildschirm ab BIOS bis ItomiScan filmen/ansehen. Farben, Schriftzug, Größe, Logo und Scanlinienbewegung der beiden Startanzeigen vergleichen; mögliche Xorg-Umschaltblitze und Bootdauer notieren.
5. Nach Neustart Bootdauer über `systemd-analyze`, `systemd-analyze blame` und `systemd-analyze critical-chain` lesen. Keine Systemdienste blind deaktivieren.
6. Beide Bildschirmtastaturen, PIN-NumPad, Home-Symbol und Hauptkacheln auf dem echten 1024×768-Panel testen. Touch-Puls muss kurz erscheinen, Mauszeiger darf nicht stehen bleiben. Physische Scantaste darf keine Doppelauslösung verursachen.
7. Menü sowohl von Startseite als auch Scanansicht öffnen; „Bildschirmschoner anzeigen“ testen, einmal tippen zum Aufwecken, Rücknavigation und PIN-Rechte überprüfen. Automatischen 5-Minuten-Timer getrennt testen.
8. Im Web-Admin über die tatsächlich genutzte HTTPS-Adresse anmelden, einen Testbenutzer mit PIN anlegen, ändern und entfernen. „Ungültiger Ursprung“ darf bei legitimem Betrieb nicht erscheinen; fremder Origin, fehlende Anmeldung und ungültige CSRF-Tokens müssen weiterhin blockiert werden.
9. Systemwerte unter geringer und erhöhter Last beobachten; RAM- und SSD-Werte mit Linux abgleichen. Nach 30 Sekunden müssen die Werte ohne Formulardatenverlust aktualisiert werden. Dienste ohne Installation müssen deutlich als inaktiv/nicht vorhanden erkennbar sein.
10. Regression: einseitige und Duplex-Dokumente, PDF/PNG, Seitenprüfung, Zustellwarteschlange, Netzwerk-/Druckziele sowie Vollbackup-/Rollback-Weg kontrollieren. Keine automatische Zustellung zum Test erzwingen.

## Freigabekriterien

- `develop/1.0.0` hat einen eindeutig dokumentierten HEAD-Commit.
- Python-/Shell-Syntax, Unit-/Web-Sicherheitstests und GUI-Smoke-Tests müssen nachweislich bestanden sein. **Queued, in_progress oder fehlende CI-Resultate gelten nicht als bestanden.**
- Reale N1800-Geräteabnahme mit konkreter Revision und Prüfergebnis dokumentiert.
- Unabgenommene Features als **offen**, nicht als funktionsfähig/released bezeichnen.
- Keine Stable-Promotion, kein Tag `v1.0.0`, kein `main`-Merge und keine Produktionsbereitstellung ohne erneute ausdrückliche Freigabe.

## Referenzen

- `docs/RELEASE-READINESS-1.0.0.md` für die vollständige ursprüngliche 1.0.0-Funktionsabnahme.
- `release-check.sh` und `python3 -B -m itomiscan.release_preflight --json` für lesende Vorprüfungen.
- `setup-boot-splash.sh` für gesondert genehmigte, reversible Boot-Thema-Einrichtung.
