# ItomiScan 1.0.0 Beta: Installations- und Freigabecheck

**Status:** Release-Kandidat, keine Gerätefreigabe. Der Entwicklungszweig ist `develop/1.0.0`. `main` bleibt unverändert.

## Installation (noch nicht auf dem N1800 abgenommen)

Voraussetzungen: Debian 12 bookworm i386, SSH, Netzwerkzugriff, vorhandener normaler Linux-Benutzer, mindestens 512 MiB freier Speicher. Die Installation richtet einen Kiosk-Autologin, HTTPS-Webadministration, Zustelldienst und lokale CUPS-Konfiguration ein. Vorhandene Programmdateien werden gesichert. Die Webadmin-Passwortvergabe ist interaktiv.

```bash
curl -fL https://raw.githubusercontent.com/tojollinor/ItomiScan/develop/1.0.0/install-beta.sh -o /tmp/itomiscan-beta-install.sh
sudo bash /tmp/itomiscan-beta-install.sh --user administrator
```

**Nicht ungeprüft auf produktiv genutzten Geräten ausführen.** Die Beta ersetzt vorhandene Dateien in `~/ItomiScan`; die Sicherung wird im Benutzer-Home angelegt. Der Installer aktiviert die Anmeldung auf tty1 und die Dienste. Die Erstinstallation und die Wiederholung des Installers benötigen einen echten Gerätetest.

## Boot-Splash (getrennt, optional)

`setup-boot-splash.sh` installiert Plymouth und verändert GRUB-Parameter einschließlich `GRUB_TIMEOUT=0`. Das kann bei Fehlkonfiguration die Wiederherstellung erschweren. Vor dem Ausführen physischen Konsolenzugang und einen alternativen Bootweg sicherstellen. Die Skriptausführung kann auf dem Atom N270 wegen `update-initramfs` mehrere Minuten dauern. Das Skript erzeugt Backups unter `/var/lib/itomiscan/boot-backups/`.

`restore-boot-splash.sh BACKUPORDNER` stellt die gesicherten Einstellungen wieder her. Die Wiederherstellung ist ebenfalls noch nicht am Gerät getestet.

## Freigabekriterien

- [ ] Debian-12-i386-Paketinstallation und Kioskstart auf dem N1800 erfolgreich
- [ ] Boot ohne GRUB-Wartepause, Splash und Übergang zur GUI praktisch geprüft
- [ ] SANE-Erkennung, Mehrseiten-ADF und Duplex-Reihenfolge geprüft
- [ ] Fehlerfälle Papier leer, Stau, Doppeleinzug und Abbruch geprüft
- [ ] Dokumentenübersicht: drehen, löschen, sortieren, erneut scannen, Leerseiten prüfen
- [ ] PDF nach Freigabe, Bildexport und korrekte Seitenreihenfolge geprüft
- [ ] Webadmin, Druck und mindestens ein Zustellziel praktisch geprüft
- [ ] Installations-Wiederholung, Sicherung und Boot-Rückweg geprüft
- [ ] Automatisierte Syntax-/Regressionstests mit protokolliertem Ergebnis

## Bekannte Einschränkungen

- Update-Schaltfläche prüft den Beta-Kanal, installiert aber keine Updates direkt aus der GUI.
- Die installierte Revision wird über GitHub abgefragt; Archivdownload und Abfrage können bei parallelen Commits auseinanderfallen. Deshalb nicht als kryptografisch verifizierte Versionsfixierung betrachten.
- Das Boot-Splash-Skript wird vom Installer absichtlich nicht automatisch ausgeführt.
- Ein optisch lückenloser Plymouth-Xorg-Übergang ist noch nicht nachgewiesen.
- Die Entwicklungsdokumentation im README enthält ältere Beschreibungen; dieser Freigabecheck beschreibt die aktuellen Einschränkungen.
- Bis zum erfolgreichen Abschluss der Kriterien ist die Beta **nicht freigegeben**.


## Block 2/4: Bedienung und Hardware (Entwicklungsstand)

Code auf `develop/1.0.0` umgesetzt, Hardwareabnahme steht aus:

- [x] Bildschirmtastatur zentriert, Fokus und Tastenabstände für 1024×768 angepasst
- [x] Zieh-Scrollen auf freien Flächen der Scanoptionen und lokal begrenztes Mausrad
- [x] Ausschalten aus dem Scanheader entfernt, auch nach Berechtigungswechsel
- [x] Dokument-Abbruch als zentrierter Zwei-Schaltflächen-Dialog
- [x] Scannerfehlerdialog an Bildschirmgröße angepasst und zentriert
- [x] Logo in Scanheader ergänzt, vorhandener Scanbalken wird bei aktiver Arbeit animiert
- [x] SANE-Hardwarediagnose und vorsichtiges 300-DPI-Testprofil ergänzt
- [ ] N1800-Gerätetest: Bildschirm wird bei Texteingabe nicht leer
- [ ] N1800-Gerätetest: Zieh-Scrollen ohne versehentliche Eingabe
- [ ] N1800-Gerätetest: Scanbalkenanimation und Dialoge
- [ ] N1800-Gerätetest: SANE-Testprofil, Duplex, Doppeleinzug und Optionen

Die Checkboxen für Codeänderungen sind **keine** Testfreigabe. Neustart ist weiterhin nicht freigeschaltet, solange Systemberechtigungen fehlen. Eine automatische Installation aus der GUI ist nicht freigegeben.


## Block 3/4: Ziele und Drucker (Entwicklungsstand)

- [x] Scanziel-Auswahl als Vollbildseite statt Dialog; lokales Speichern, Paperless, Netzwerk, E-Mail, USB nach Berechtigung
- [x] Konfigurierte Zustellziele ebenfalls als Vollbildseite; fehlende Ziele melden Webadministrationsbedarf
- [x] Kopieransicht bleibt Vollbild; bestehende CUPS-Druckerwahl und Druckeinstellungen erhalten, Logo ergänzt
- [x] Webadmin: „Drucker hinzufügen“, Adresse bearbeiten, entfernen, Testdruck und Standarddrucker setzen
- [x] CUPS-Geräteerkennung über `lpinfo -v` und Vorschläge für Drucker-URIs
- [x] URI-Prüfung für IPP/IPPS, socket/RAW 9100, LPD und USB; Regressionstests eingecheckt
- [ ] Regressionstests tatsächlich ausführen und Ergebnis dokumentieren
- [ ] N1800: Druckererkennung und Rechte von `lpadmin`, `lpinfo`, `lpstat` testen
- [ ] N1800: PDF-Testdruck auf realem Brother-Drucker bestätigen
- [ ] N1800: Scanziele und Berechtigungen, Zustellwarteschlange sowie Kopierablauf prüfen

**Einschränkung:** Für socket/RAW, LPD und USB verwendet die derzeitige CUPS-Installation eine RAW-Warteschlange. Diese nimmt nur druckerfertige Daten entgegen; ein PDF wird dadurch nicht automatisch in eine für den Drucker verständliche Sprache umgewandelt. Ein geeigneter Druckertreiber bzw. CUPS-Filter ist für zuverlässigen Ausdruck erforderlich. IPP Everywhere funktioniert nur bei kompatiblen Geräten. Ohne diesen Nachweis gilt die Mehrprotokoll-Druckunterstützung noch nicht als praktisch abgenommen. Keine Behauptung, dass alle Brother-Modelle treiberlos unterstützt werden.


## Block 4/4: System, Prüfungen und Release-Entscheidung (14.10.2026)

- [x] Bestehende Installer-, Boot- und Wiederherstellungsskripte gegen die Freigabekriterien geprüft.
- [x] Installationsprüfung für LAN-HTTPS-Verfügbarkeit präzisiert: Netzwerk-Bindungsprobleme werden als Warnung ausgegeben, nicht als falsch positives Komplettversagen des Installers.
- [x] GitHub Actions Workflow `.github/workflows/beta-checks.yml` für Python-Syntax, Shell-Syntax und Unittests eingecheckt.
- [x] Lesendes N1800-Diagnoseskript `scripts/n1800-acceptance.sh` eingecheckt. Es scannt, druckt, startet neu und ändert keine Systemkonfiguration.
- [ ] GitHub Actions erfolgreich gelaufen und Protokoll eingesehen.
- [ ] Echte N1800-Geräteabnahme der offenen Punkte aus Block 1, 2 und 3.
- [ ] GRUB/Plymouth mit Rettungsweg praktisch getestet.
- [ ] Wiederholte Installation und Wiederherstellung der Sicherung auf N1800 geprüft.
- [ ] Druck und Zustellung praktisch bestätigt.
- [ ] Freigabe als GitHub Beta Release nach erfolgreicher Abnahme.

**Freigabeentscheidung:** NICHT FREIGEGEBEN. Ein GitHub Release wird nicht als fertig ausgegeben, solange die Tests und Gerätetests fehlen. Das laufende Entwicklungsergebnis liegt weiterhin auf `develop/1.0.0`. Insbesondere der dokumentierte Restumfang der Scanoberfläche aus Block 1 muss vor einer Beta-Freigabe abgearbeitet werden.

### Lesender Gerätetest

Als normaler Benutzer nach der Installation:

```bash
bash ~/ItomiScan/scripts/n1800-acceptance.sh
```

Der Test zeigt nur Basissystem- und Dienststatus. Für Scanner, Drucker und Boot ist eine zusätzliche manuelle Abnahme nötig. Bei nicht erreichbarem HTTPS-Dienst: `journalctl -u itomiscan-web.service -n 80 --no-pager`.

### Wiederherstellung

Der Installer legt vor dem Überschreiben eine Sicherung `~/ItomiScan-backup-<Zeitstempel>` an. Die automatische Wiederherstellung ist nicht implementiert. Vor einer Rückkopie Dienste stoppen und die betroffene Konfiguration sichern. Boot-Rollback ausschließlich mit dem durch `setup-boot-splash.sh` angelegten Sicherungsordner über `restore-boot-splash.sh` und physischem Rettungszugang testen. Ein fehlerfreier Plymouth-Xorg-Übergang wird nicht behauptet.

## Block 3/4: Ziele und Drucker (Entwicklungsstand)

Code auf `develop/1.0.0` ergänzt:

- [x] Vollbild-Scanziele: lokal, Paperless, Netzwerkordner, E-Mail und USB
- [x] Sichtbarer Status für eingerichtete und nicht eingerichtete Ziele
- [x] Eigene Vollbild-Hinweisseite bei nicht konfiguriertem Ziel
- [x] Zielauswahl mit Seitenwechsel für mehr als fünf Einträge
- [x] Kopieransicht mit CUPS-Warteschlangen und bevorzugtem Standarddrucker
- [x] Webadministration: Drucker suchen, manuell per IP/Hostname und Protokoll erfassen
- [x] IPP/IPPS, RAW 9100, LPD/LPR sowie erweiterte USB-Adresse unterstützt
- [x] Druckerziel anhand stabiler ID bearbeiten, CUPS-Konfiguration aktualisieren
- [x] Drucker als Standard festlegen, Testauftrag senden, Zuordnung entfernen
- [x] Schutz gegen das versehentliche Verwaisen einer installierten CUPS-Warteschlange
- [x] Zusätzliche isolierte Regressionstests für Druckeradresse, Bearbeitung und Webrouten angelegt
- [ ] Tests tatsächlich ausführen und protokollieren
- [ ] N1800: Drucker suchen, hinzufügen, ändern, löschen und Standardwahl testen
- [ ] N1800: IPP/IPPS-Druckauftrag physisch prüfen; RAW/LPD/USB nur mit passendem Treiber/Format
- [ ] N1800: mindestens ein reales Zustellziel einschließlich Fehler- und Wiederholungsfall testen

**Hinweis:** CUPS bestätigt nur die Auftragsannahme, nicht die physische Ausgabe. Zielstatus \"eingerichtet\" bestätigt nur einen gespeicherten Eintrag, keine erfolgreiche Verbindung. Druckertreiber und die benötigten Druckdatenformate bleiben geräteabhängig. Kein Release vor erfolgreicher Geräteabnahme.


## Splashscreen- und Menü-Nacharbeit (14.10.2026)

- [x] Scan- und Kopieren-Kacheln im Home-Layout verkleinert (Code).
- [x] Ausschalten und Neustarten in beiden Gerätemenüs ergänzt; Schließen bleibt letzter Menüpunkt.
- [x] Kiosk-Sudoers-Regel für `systemctl poweroff` und `systemctl reboot` ergänzt.
- [x] Plymouth-Design mit Scan-Logo, Titel, Untertitel, Hintergrund, Status und Ring an Tk-Splash angeglichen.
- [x] Tk-Splash auf dieselben 1024x768-Bezugspositionen wie Plymouth umgestellt.
- [x] Xorg-Root-Hintergrund bereits vor Tk-Start auf Splash-Hintergrundfarbe gesetzt.
- [ ] Optisch lückenloser Übergang Plymouth zu Xorg auf N1800 bestätigt. Ein kurzer Grafikmoduswechsel kann hardwarebedingt sichtbar bleiben.
- [ ] Neustart-/Ausschaltaktionen und kleinere Schaltflächen am N1800 geprüft.

**Keine Installation veranlasst.** Alle Punkte sind Änderungen am Entwicklungszweig. `setup-boot-splash.sh` bleibt ausdrücklich optional und wird vom Installer nicht automatisch ausgeführt. Kein Beta-Release ohne Gerätetest.


## Restarbeiten: erster Korrekturblock

- [x] Bildschirmtastatur ohne `transient(root)` im fenstermanagerlosen Kiosk anzeigen und explizit fokussieren.
- [x] Diagnoseskript unabhängig vom Home-Verzeichnis des aufrufenden Benutzers machen; Python-Syntax nur bei vorhandenem Quellcode als OK melden.
- [x] Kioskberechtigungen für Poweroff und Reboot getrennt prüfen.
- [x] Wiederholtes Öffnen der Vollbild-Scanziele ohne übereinanderliegende Seiten; lokale Scanziele nach Berechtigung filtern.
- [ ] Bildschirmtastatur und Vollbild-Navigation auf N1800 praktisch testen.
- [ ] Scanablauf, Dokumentbearbeitung, Druckertreiber und Updateinstallation weiter vervollständigen und testen.
- [ ] Nahtloser Plymouth/Xorg-Übergang am N1800 prüfen; derzeit nur Design und Hintergrundübergang vorbereitet.

**Keine Installation, kein Release und keine Änderung an main.** Die Checkboxen bezeichnen ausschließlich eingecheckte Codekorrekturen.


## Restarbeiten: zweiter Korrekturblock (Dokumentenprüfung)

- [x] Eingelesene Seiten eines zusätzlichen Scanbatches vor der Übernahme einzeln mit Pillow validieren.
- [x] Bei Kopier- oder Validierungsfehlern neu angelegte Dateien des fehlgeschlagenen Batches entfernen, bestehende Dokumentseiten erhalten.
- [x] Beim Löschen der letzten Seite auch die Thumbnail-Leiste zurücksetzen.
- [ ] Fehlerfalltest: unterbrochener ADF-Batch, fehlerhafte Bilddatei, voller Datenträger.
- [ ] Echte Prüfung von Mehrseiten-ADF, Duplex, Reihenfolge, Seitenersatz und PDF-Ausgabe auf dem N1800.

**Stand:** Quellcodekorrekturen eingecheckt, keine lokale oder N1800-Ausführung bestätigt. Kein Release und keine Installation.


## Restarbeiten: dritter Korrekturblock (Kopieren und CUPS)

- [x] CUPS-Auftragsannahme einer eingerichteten Warteschlange per `lpstat -a` mit C-Locale auswerten.
- [x] Kopieransicht bietet nur eingerichtete und auftragsannehmende Drucker als bereit an.
- [x] Beim Start des Kopiervorgangs die Auftragsannahme erneut prüfen.
- [x] Beim tatsächlichen PDF-Versand an CUPS die Auftragsannahme erneut prüfen.
- [ ] N1800: CUPS-Status bei pausierter, offline und wieder aktivierter Warteschlange testen.
- [ ] Druckertreiber/Filter: RAW/LPD/socket/USB benötigen einen passenden PDF-fähigen Filter oder druckerfertige Daten; unverändert offen.
- [ ] CUPS-Auftragsannahme und physische Papierausgabe mit echten Druckern prüfen.

**Keine Installation, kein Release.** Diese Änderungen lösen keine Druckertreiber- oder Gerätekompatibilitätsprobleme.


## Nacharbeit Block 4: Update und Start (14.10.2026)

- [x] Installationsarchiv auf den vor dem Download ermittelten Commit fixiert; Versionsdatei verwendet genau diesen Commit.
- [x] Tk-Startanzeige: Diagnose bei erneutem Start mit korrekter `place_forget()`-Methode ausblenden.
- [x] Plymouth-Icon: weißes Dokumentelement an die Tk-Logozeichnung angeglichen.
- [ ] Installer auf Debian 12 i386 im Gerätetest ausführen und Archiv-/Versionsidentität kontrollieren.
- [ ] Xorg/Plymouth-Übergang am echten 1024×768-N1800 prüfen. Gleiche Gestaltung bedeutet **nicht** automatisch einen unterbrechungsfreien Wechsel des Grafikmodus.
- [ ] Boot-Rollback testen, bevor GRUB_TIMEOUT=0 aktiviert wird.
- [ ] Update-Installation aus der GUI ist weiterhin **nicht** implementiert; nur Prüfung verfügbar. Privilegierte Installation bleibt separat und erfordert Freigabe.
- [ ] Vor einer Beta-Freigabe offene Treiber-, Scan- und UI-Tests vollständig durchführen.

**Wichtig:** Keine Installation, kein GitHub-Release, keine Änderung an `main`. Eingecheckte Änderungen sind keine Gerätetests.


## Nacharbeit Block 5: Druckertreiber-Sicherheit

- [x] Die automatische CUPS-Druckereinrichtung erlaubt nur IPP/IPPS mit `-m everywhere`.
- [x] Socket/RAW, LPD und USB werden bei der **automatischen** Einrichtung mit verständlicher Treiber-/Filtermeldung abgewiesen, statt fälschlich als PDF-kompatibel zu gelten.
- [x] Regressionstests für die Ablehnung und für CUPS-Warteschlangen ohne Auftragsannahme ergänzt.
- [x] Bestehende PDF-Drucktests auf die neue CUPS-Auftragsannahmeprüfung angepasst.
- [ ] Bestehende RAW-Druckerwarteschlangen werden durch dieses Update **nicht** automatisch entfernt; bei der Geräteabnahme gesondert prüfen.
- [ ] Für RAW/LPD/USB optional später eine explizite Treiberauswahl mit lokal verfügbaren CUPS-Modellen und validiertem Filter ergänzen.
- [ ] Tests in GitHub Actions ausführen und Ergebnisse prüfen.

**Keine Installation auf dem N1800, kein Release.**


## Neuer sechsfacher Arbeitsplan: Block 1/6 Startseite und Menü

- [x] Scan-/Kopier-Kacheln auf 1024×768 weiter verkleinert (Schrift, Innenabstand und Außenabstand).
- [x] Menüfenster mittig und innerhalb der verfügbaren Displayabmessungen positioniert; kein `transient` auf dem randlosen Kiosk-Hauptfenster.
- [x] Vorhandene Menüaktionen im Code geprüft: Updates, Neustarten, Ausschalten, Beenden, Schließen; Rechteprüfung vorhanden.
- [ ] Tatsächliche Bildschirmdarstellung und Touchziele am N1800 prüfen.
- [ ] Neustart/Ausschalten mit eingerichteten sudoers-Rechten am Gerät prüfen.
- [ ] Menü und Startseite visuell auf vollständige Anforderungsübereinstimmung abnehmen.

Nächste Blöcke: 2/6 Splashscreen/Tastatur, 3/6 Scanablauf, 4/6 Dokumentenübersicht, 5/6 Updates/Systemstart, 6/6 Tests/Releasevorbereitung. Nach jedem Block Halt für Nutzerfreigabe. Druckertreiber zurückgestellt. Keine Installation und kein Release.


## Neuer sechsfacher Arbeitsplan: Block 2/6 Splashscreen und Tastatur

- [x] Bildschirmtastatur: Modal-Grab erst nach vollständigem Aufbau und Sichtbarkeit des Tk-Fensters; Fokus anschließend auf Eingabefeld.
- [x] Tk-Splash: Akzentfarbe an das Startseitenlogo angepasst.
- [x] Plymouth-Splash: Akzentfarbe an Tk-Splash und Startseitenlogo angepasst.
- [x] Fehler beim Aufbau der Hauptoberfläche: Splash bleibt mit Diagnose und erneutem Versuch sichtbar, statt in eine unbehandelte Tk-Ausnahme zu laufen.
- [ ] Gerätetest: Tastatur öffnet ohne schwarzen/leeren Bildschirm; Texteingabe, Shift, Löschen, Abbrechen und Übernehmen funktionieren.
- [ ] Gerätetest: Plymouth/Tk-Übergang und Auflösung 1024×768 prüfen. Ein Grafikmoduswechsel kann weiter sichtbar bleiben.
- [ ] Gerätetest: absichtlich fehlende Scannererkennung und Fehler beim Aufbau der Hauptoberfläche kontrolliert durchspielen.

**Keine Geräteinstallation und keine Releasefreigabe.** Nächster Block 3/6: Scanablauf.


## Neuer sechsfacher Arbeitsplan: Block 3/6 Mehrseitiger Scanablauf

- [x] Weiterer Scanbatch verwendet unverändert die gespeicherten Einstellungen und das Ausgabeformat des ersten Batches; nachträglich geänderte, eventuell ungültige GUI-Felder blockieren ihn nicht mehr.
- [x] Fehlgeschlagener zusätzlicher Batch meldet ausdrücklich, dass die bisherigen Bildseiten erhalten geblieben sind.
- [x] Bestehende Batch-Übernahme geprüft: Seiten werden erst nach vollständig validierter Kopie in die Vorschau übernommen; bei Kopierfehlern werden neu erzeugte Dateien zurückgerollt.
- [ ] Reale N1800-Tests: mehrere getrennte ADF-Batches, gemischte Seitenanzahl, Duplex-Reihenfolge und Fehler beim zweiten Einzug.
- [ ] Reale N1800-Tests: Zeitüberschreitung, leerer Einzug, Papierstau, Doppeleinzug, wenig Speicherplatz und Dokumentabschluss.
- [ ] Automatisierte GUI-Integrationstests und GitHub Actions-Ergebnis prüfen; die obigen Änderungen sind bislang Codeänderungen ohne Geräteabnahme.

**Keine Installation, kein Release.** Nächster Block 4/6: Dokumentenübersicht und Seitenbearbeitung.


## Neuer sechsfacher Arbeitsplan: Block 4/6 Dokumentenübersicht

- [x] Bereits vorhandene Schnellaktionen im Code geprüft: Seitennavigation, drehen, löschen, verschieben, erneut scannen, Leerseiten prüfen, weitere Seiten scannen, Dokument übernehmen.
- [x] Bestätigte Leerseiten werden auch aus dem temporären Dokumentordner entfernt; Fehler beim Dateilöschen werden gemeldet.
- [x] Nach Löschen der letzten Seite kann der Benutzer weitere Seiten in dasselbe noch offene Dokument scannen.
- [x] Drehen validiert die neue Bilddatei vor dem Ersetzen und bereinigt die temporäre Drehdatei bei Fehlern.
- [ ] Echte Touch-Abnahme auf 1024×768: Übersicht, alle Schnellaktionen, Seitenreihenfolge und Seitenauswahl.
- [ ] Nachträgliches Ersetzen einer Seite, Leerseitenerkennung mit hellen Originalen und PDF-Reihenfolge praktisch prüfen.
- [ ] Automatisierte Regressionstests laufen lassen und Ergebnisse protokollieren.

**Keine Installation, kein Release.** Nächster Block 5/6: Updates und Systemstart.


## Neuer sechsfacher Arbeitsplan: Block 5/6 Updates und Systemstart

- [x] Installer erstellt eindeutige, vollständige Backups auch bei zwei Installationen in derselben Sekunde (mktemp-Verzeichnis).
- [x] Updateprüfung validiert GitHub-Commit-ID und unterscheidet unbekannten lokalen Installationsstand von einem bestätigten Update.
- [x] Neues nur lesendes Skript `diagnose-boot.sh`: `systemd-analyze time`, `blame`, `critical-chain`, GRUB-Status, fehlgeschlagene Dienste und Plymouth-Status.
- [x] Vorhandenes `setup-boot-splash.sh` setzt GRUB_TIMEOUT=0 und installiert Plymouth ausschließlich nach ausdrücklichem manuellem Aufruf, nicht beim Standard-Update.
- [ ] **GUI-Updateinstallation nicht implementiert**: Ein sicherer privilegierter Updatehelfer mit eng begrenzten Rechten, Verifikation und automatischem Rollback muss vor Freigabe entworfen und getestet werden. Die GUI darf nicht einfach `sudo bash` ausführen.
- [ ] Vollständigen Wiederherstellungsablauf einschließlich Servicezustand und Konfiguration auf dem Gerät prüfen; Backups allein sind noch kein getestetes Rollback.
- [ ] N1800: GRUB/Plymouth, Neustart, Bootdauer und Dienste mit `bash diagnose-boot.sh` untersuchen; keine Bootänderung ohne Rettungsweg.
- [ ] Installer- und Syntaxprüfungen tatsächlich ausführen und dokumentieren.

**Keine Installation, kein Release.** Nächster Block 6/6: Regressionstests und Releasevorbereitung. Die GUI-Updateinstallation bleibt als offener Freigabeblocker dokumentiert.
