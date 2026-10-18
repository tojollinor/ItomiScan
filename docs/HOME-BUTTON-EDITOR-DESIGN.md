# UI-2.1: Frei konfigurierbare Startseite und Mehrziel-Workflows

Stand: 2026-10-19. **Webeditor, dynamische Scanner-Startseite und Mehrziel-Zustellkern im Entwicklungsbranch implementiert; Praxistest am N1800 weiterhin offen.** Zielbranch `develop/1.0.0`; bestehendes bestätigtes ItomiScan-Design verwenden.

## Grundprinzip

Jeder Startseitenbutton ist eine eigenständige, frei konfigurierbare Scanaktion. Der Benutzer legt **direkt am Button** die gewünschten Scanoptionen und **beliebig mehrere bestehende Ziele** fest. Ein Klick scannt das Dokument genau einmal; das Ergebnis wird anschließend für alle ausgewählten Ziele verwendet. Ein Button muss nicht zwingend ein globales Scanprofil referenzieren. Gruppenbuttons führen zu frei gestaltbaren Unterseiten.

## Webeditor „Startseite gestalten“

- **Ausschließlich in der Webadministration** Buttons erstellen, bearbeiten, umbenennen, duplizieren, deaktivieren, verschieben/sortieren und löschen. Pro Button **Farbe frei wählen** (vordefinierte abgestimmte Palette und optional eigener HEX-Farbwert), Symbol und Beschriftung festlegen. Automatisch gut lesbare Kontrastfarben für Text/Symbole; nicht betroffene Gestaltungsbereiche unverändert. Auf dem Scanner selbst keine Bearbeitungsoberfläche.
- Gruppenbutton inklusive eigener Farbe erstellen und Unterseite mit eigenen Buttons gestalten; Zurück/Home-Navigation. Sichere Navigation ohne Gruppenzyklen, Tiefe später festlegen.
- **Scanoptionen je Scanbutton**: ein-/doppelseitig (ADF Front/Duplex), Auflösung/DPI, Farbe/Graustufen/Schwarzweiß, Dokumentformat/Ausgabe (PDF usw.), gegebenenfalls weitere SANE-Optionen, sofern Scanner und gewählter Modus sie tatsächlich unterstützen. Optional vorhandenes Scanprofil als Ausgangsvorlage übernehmen; Änderungen am Button unabhängig davon speichern. Nicht unterstützte Kombinationen erkennbar ablehnen, nicht still ignorieren.
- **Ziele je Button** als Mehrfachauswahl vorhandener gespeicherter Verbindungen: Paperless, eingerichteter Drucker, Netzwerkordner und andere implementierte Zielarten. Eine Verbindung kann mehreren Buttons zugewiesen sein; Credentials bleiben ausschließlich in der Zielverwaltung.
- **Übertragungsmodus pro Button**: „Fortschritt anzeigen“ (Standard) oder „Im Hintergrund übertragen“. Beide verwenden die gleiche zuverlässige Auftragserfassung und -überwachung.
- Pro Druckziel bei Bedarf Kopienzahl, ein-/doppelseitigen Ausdruck und verfügbare Druckeroptionen, ohne Scaneinstellungen (Duplex-Scan) mit Druckduplex zu verwechseln.
- Vorschau im Editor im Verhältnis 1024×768; bestehende Tasten-/Layoutmuster. Keine unkontrollierte Änderung vorhandener Startbuttons bei Migration.
- Benutzer- und Zielberechtigungen bei Anzeige **und** Ausführung prüfen; defekte oder entfernte Zielverknüpfungen als reparaturbedürftig markieren; keine stillen Ersatzadressen.

## Beispiele

| Button | Scaneinstellungen | Ziele | Modus |
| --- | --- | --- | --- |
| Paperless | Duplex, 300 dpi, Farbe, PDF | gespeicherte Paperless-Verbindung | Fortschritt anzeigen |
| Kopieren | Duplex, 200 dpi, Graustufen, PDF | Netzwerkdrucker | Fortschritt anzeigen |
| Kopieren + Paperless | Duplex, 300 dpi, Farbe, PDF | Drucker **und** Paperless | Im Hintergrund |
| Gruppe „Büro“ | entfällt | Unterseite | entfällt |

Diese Werte sind **Beispiele**, keine fest vorgegebenen Optionen.

## Zustellung und Parallelität

1. Button drücken, Berechtigungen, Scannerbereitschaft, Scanoptionen und alle Zielreferenzen prüfen. **Ein** Scan erzeugt ein Dokument, einschließlich mehrerer Seiten und ggf. bestehender Abschluss-/Vorschaufunktionen.
2. Aus diesem Dokument werden für alle Ziele getrennte, dauerhaft gespeicherte Zustelljobs in einer gemeinsamen Dokument-/Batch-ID angelegt. Vollständige Planung sicherstellen; Teilfehler beim Einplanen sichtbar behandeln. Das Originaldokument bleibt erhalten.
3. Nach dem Scannen die Jobs **parallel bzw. über begrenzte unabhängige Worker** abarbeiten, damit z. B. ein langsamer Drucker nicht den Paperless-Upload blockiert. Ressourcengrenzen für Atom N270 und ~1 GiB RAM vorsehen. Nicht nur parallel einreihen und dann absichtlich seriell bearbeiten.
4. Jeder Zieljob besitzt einen eigenen Zustand: wartend, wird übertragen, erfolgreich an Ziel übergeben, fehlgeschlagen / erneuter Versuch notwendig. Beim Druck tatsächliche Papierausgabe **nicht** als bestätigt behaupten, wenn nur CUPS den Auftrag angenommen hat. Bei Paperless zwischen akzeptiertem Upload und tatsächlicher Archivierung unterscheiden, wenn keine Endbestätigung vorliegt.
5. Fehler eines Ziels stoppen **nicht** die anderen. PDF und offene Zieljobs bleiben für Wiederholung/Diagnose erhalten; unsichere Zustellungen (Druck oder Upload möglicherweise schon angekommen) nicht blind nochmals senden.
6. Fortschritt anhand tatsächlicher messbarer Daten (Seiten/Bytes) anzeigen, ansonsten klaren Status statt erfundener Prozentwerte. Keine Erfolgsmeldung für alle Ziele, solange nicht jedes Ziel den definierten Erfolgszustand erreicht hat.

## Vordergrundmodus: Zustellfenster

Direkt nach dem Scan öffnet sich eine im bestehenden Stil gestaltete Zustellübersicht mit **einer Zeile/Kachel je Ziel**:
- Zielname mit Icon, aktueller Zustand und ggf. verständliche Fehlermeldung;
- laufende Aktualisierung ohne flackernden Neuaufbau; gegebenenfalls echter Fortschrittswert;
- Gesamthinweis „2 von 3 Zielen übergeben“ statt pauschalem „Erfolgreich“;
- nach Fertigstellung klarer Abschluss mit Option „Schließen“; bei Fehlern Detailansicht mit sicherem „Erneut versuchen“ nur bei eindeutig fehlgeschlagener Zustellung;
- während der Übertragung bleiben die Aufträge beim Schließen erhalten, nichts wird abgebrochen.

## Hintergrundmodus und zentraler Statusbereich

- Bei „Im Hintergrund übertragen“ kehrt der Scanner nach sicherer Jobannahme zur Startseite zurück; Zustellung läuft unabhängig weiter.
- **Eigener, dauerhaft erreichbarer Statusbereich** in der Scanner-GUI: dezentes Statussymbol/Anzahl offener Meldungen in der bestehenden Navigation; beim Antippen öffnet sich eine passende Statusseite.
- Meldungen für **Erfolg, Warnung und Fehler**, mit Uhrzeit, Dokument/Batch, betroffener Zielverbindung, technischem Zustand und optionalen Details/Handlungsmöglichkeiten; bei Mehrziel-Vorgängen Einzelergebnisse und zusammenfassender Gesamtstatus.
- Neue relevante Ereignisse kurz als unaufdringliche Mitteilung anzeigen, aber laufendes Scannen/Touchaktionen nicht blockieren. Fehler deutlich kennzeichnen; erfolgte Übertragungen nicht dauerhaft störend einblenden.
- Status/Jobs aus der persistenten lokalen Warteschlange lesen, damit Meldungen bei GUI-Neustart, Benutzerwechsel oder Netzwerkausfall nicht verloren gehen. Bei aktiver Benutzerverwaltung Dokumentnamen/Status nicht unberechtigten Benutzern preisgeben.
- Benutzer kann Benachrichtigungen ansehen und als gelesen markieren; **Gelesen** ist nicht gleich **erfolgreich zugestellt**, und Einträge verschwinden nicht aus der Auftrags-/Fehlerhistorie.

## Weiterführende GUI-Optimierung

Bestehende Scanneransichten hinsichtlich Platznutzung, konsistenter Header-/Footer-Navigation, eindeutiger Symbole, erreichbarer Hauptaktionen, responsiven Ladezuständen und einheitlichen Status-/Fehlermeldungen prüfen. Ressourcensparend und touchfreundlich auf 1024×768; bestätigte Designs und nicht betroffene Bereiche unangetastet. Konkrete Änderungen vor Umsetzung getrennt abnehmen.

## Technischer Ist-Zustand und notwendige Erweiterungen

- `itomiscan/gui/home.py`: aktuell überwiegend fest programmierte Startaktionen; dynamische Button- und Gruppenverwaltung erforderlich.
- `itomiscan/storage/config.py`: Profile und Ziele bereits getrennt gespeichert; neue persistente Buttondefinitionen und gruppierte Zielreferenzen erforderlich.
- `itomiscan/storage/queue.py`: vorhandene Zustelljobs werden einzeln eingeplant und durch den bisherigen Worker bearbeitet. Für die zugesagte **tatsächliche parallele Zustellung** braucht es Batch-Identität, sichere Mehrziel-Einplanung und begrenzte gleichzeitige Worker. Seit Block 7 vorhanden: Batch-ID, atomare Job-Erzeugung, auf dem Dateisystem einmal gespeicherte PDF per Hardlinks und höchstens zwei parallele Worker.
- Bestehende Benutzerberechtigungen, PDF-/Vorschauverarbeitung und unbestätigte Zustellfälle integrieren. Keine unnötigen Vollkopien großer PDFs im RAM.

## Abnahmetests

1. Button mit frei gesetzten DPI/Duplex/Farboptionen startet die passenden unterstützten SANE-Optionen; anderer Button hat davon unabhängige Einstellungen.
2. Button mit Drucker + Paperless scannt nur einmal; beide Ziele erhalten unabhängig ihre Jobs für dasselbe Dokument.
3. Ein langsamer/nicht verfügbarer Drucker blockiert nicht die Übertragung an Paperless; Parallelität im Test nachweisen.
4. Vordergrund-Fenster zeigt sämtliche Zielzustände korrekt und ohne erfundene Prozente; Hintergrundmodus zeigt Aufträge im Statusbereich.
5. Fehler/Erfolge sind auch nach Neustart noch sichtbar, sicher wiederholbar und benutzergerecht geschützt.
6. Gruppen/Buttons anlegen, sortieren, ändern und deaktivieren; fehlende Ziele, verweigerte Berechtigungen und ungültige Scanoptionen korrekt behandeln.
7. 1024×768-Touchtest und Regression vorhandener GUI-/Webfunktionen, keine automatische Stable-Änderung.

## Offene Gestaltungsdetails

- Maximale Verschachtelungstiefe für Gruppen festlegen; als pragmatischer Entwurf zunächst eine Unterebene.
- Welche Aktionen nach Abschluss einer Vorschau den Versand starten, ohne das Konzept „ein Scan = ein Dokument“ zu verändern.

## Block 6: Tatsächliche Code-Umsetzung

- Webadministration **Startseite** (`/home-buttons`): Buttons anlegen/bearbeiten/löschen/sortieren; Gruppen-Buttons mit einer Unterebene, frei wählbare HEX-Farbe und Symbol.
- Pro Scanbutton eigene SANE-Grundeinstellungen: Einzug (inkl. Duplex), DPI, Farbmodus, PDF/PNG. Datenbank verwendet dieselbe Scanprofilvalidierung wie bestehende Profile, ohne Benutzername/Passwort oder Token zu kopieren.
- Gespeicherte Ziele werden per ID mehrfach auswählbar verknüpft; bei Löschen eines in Verwendung befindlichen Ziels schützt die Konfiguration vor ungültigen Referenzen. Formulare sind authentifiziert und CSRF-geschützt.
- Die Scanner-Startseite liest neue Konfiguration beim Aufruf, zeigt individuell gefärbte Kacheln und scrollbare Gruppenseiten auf 1024×768. Ohne konfigurierte Kacheln bleibt die vorhandene Startseite. Benutzerrechte werden weiter geprüft.
- Ein Scanbutton mit höchstens einem Ziel kann seine Einstellungen für den bestehenden Scanablauf verwenden. **Wichtig: Bei mehreren Zielen erscheint vorerst eine erklärende Meldung, kein unvollständiger Teilversand.** Tatsächliche parallele Jobs, Fortschrittsfenster und Hintergrund-Zustellung werden erst mit Block 7 implementiert.
- CI- und Xvfb-Regressionstests für CRUD, CSRF, Gruppen, mehrfach gewählte Ziele, und Touch-Navigation ergänzt.
- Noch offen für Block 7/8: Zielgruppenberechtigung pro Button vollständig prüfen, PDF-Ausgabe-/Druckoptionen in Kombinationsabläufen, Sicherung/Wiederherstellung von Buttondefinitionen mit stabiler Zielreferenz, Hardwaretest auf N1800 sowie Laufzeit-/Speicherabnahme. Keine Änderung an main/Stable.

## Block 7: Tatsächlicher Umsetzungsstand

- Ein Scanbutton mit mehreren gewählten Zielen erstellt nach **einem** Scan und abgeschlossener Vorschau genau **eine gemeinsame Batch-ID**. Sämtliche Zielaufträge werden in **einer SQLite-Transaktion** eingetragen. Die unveränderte PDF wird nur einmal im gesicherten Spool abgelegt und pro Ziel mit Hardlinks referenziert; die ursprüngliche Scan-PDF bleibt erhalten.
- Der gesonderte `itomiscan-delivery.service`-Worker arbeitet nun mit maximal **zwei parallelen Übertragungs-Threads**. Jeder Zielauftrag behält eigene Zustände (`queued`, `sending`, `retry`, `done`, `failed`, `review`) und Wiederholungsregeln. Die bestehenden Sperrdatei- und Lease-Regeln bleiben.
- Vordergrundmodus: Nach sicherer Batch-Einplanung öffnet sich die Statusseite mit separatem Zustand für **jedes** Ziel, sichtbarer Gesamtzahl und periodischer Aktualisierung (keine erfundenen Prozentwerte). Hintergrundmodus: Rückkehr zum normalen Scannerbetrieb, Status weiterhin über **Meldungen** erreichbar.
- Erfolge/Fehler erscheinen dort dauerhaft aus SQLite; neue abgeschlossen/fehlgeschlagen gemeldete Hintergrundaufträge können eine kurze, nicht blockierende Meldung zeigen. Diese Meldung erscheint nicht über einer PIN-Eingabe oder einem Bildschirmschoner.
- Benutzerbezogene Statusansichten zeigen nur Batches desselben lokalen Benutzers, sofern Benutzerverwaltung aktiv ist. Gelesen-Markierung wird dauerhaft gespeichert und löscht keinen Auftrag.
- Bei Status `failed` kann ein Auftrag nach ausdrücklicher Bestätigung neu eingeplant werden; `review` darf wegen möglicher Doppelzustellung **nicht** automatisch erneut gesendet werden und verlangt zuerst manuelle Zielprüfung.
- Beim Drücken des Startbuttons wird die Zieladresse festgehalten. Eine zwischenzeitliche Änderung verhindert die gesamte Einplanung und bewahrt die lokale PDF.
- Regressionstests: parallele Worker mit Barriere, gemeinsamer PDF-Inode, Absturz-/Neustartpersistenz, unabhängiger Fehler pro Ziel, Schutz vor ungewisser Wiederholung, abweichende Zieladresse und Touch-Statusnavigation.
- Offene Hardwareabnahme: echtes SANE-Duplex/PDF, Parallelität mit Paperless und CUPS auf N1800, Reaktionszeit, Speicherverbrauch bei längeren Dokumenten und Statusdialog auf 1024×768; keine Live-Hardwarezugriffe durchgeführt.
- Paperless: „An Ziel übergeben“ bedeutet bestätigte API-Annahme, **nicht** zwingend abgeschlossene Paperless-Dokumentenverarbeitung. CUPS: angenommen ist **nicht** gleich gedruckt.
