# ItomiScan Touch-Oberfläche (Block 3/8)

Status 13.10.2026: Block-3-Funktionen auf `develop/1.0.0` committet, nicht am N1800 getestet; `main` unverändert. Seit Block 4 liegen Profile in SQLite.

## Ansicht und Navigation

- Das vereinfachte Scannerlogo wird ohne zusätzliche Bilddatei mit geometrischen Canvas-Elementen gezeichnet. Die große Schrift und kontrastreichen Schaltflächen sind auf die Anzeige 1024×768 und ältere Touchhardware ausgerichtet.
- Startseite: Scannen, Paperless, Kopieren und Netzwerkordner. Paperless/Netzwerk wählen ein Ziel und planen die PDF-Übertragung; Kopieren öffnet seit Block 7 einen großen CUPS-Kopierdialog. E-Mail/USB über zusätzliche Auswahl. Der separate Worker übernimmt Druck und Übertragungen.
- Die Taste **Scannen** öffnet die vorhandene Experten-/Detailansicht mit allen vom SANE-Backend erkannten, aktiven Optionen. Mit **← Startseite** gelangt man zurück; nicht während eines Scanauftrags.
- Die Taste **Jetzt scannen** auf der Startseite oder die echte Scanner-Fronttaste verwendet das aktuell gewählte Profil, zeigt den laufenden Scan in der Detailansicht und danach die bereits vorhandene, speicherschonende Bildvorschau mit Seitennavigation.
- **Beenden, Update, Ausschalten** bleiben vorhanden. Auf dem Entwicklungszweig ist das automatische GitHub-Update nach `origin/main` bewusst gesperrt, um einen ungeprüften Versionswechsel zu vermeiden.

## Scanprofile

- Voreinstellungen: Dokument = Color/200 DPI/ADF Duplex/PDF; Text = Gray/300 DPI/ADF Duplex/PDF; Foto = Color/300 DPI/ADF Front/PNG.
- Die Eingabefelder der Detailansicht bleiben veränderbar. **Profil speichern** legt Ausgabeformat, Modus, Quelle, DPI und die übrigen aktiven SANE-Eingaben unter einem Namen ab. Eine vorhandene Vorlage desselben Namens wird überschrieben; bis zu 30 Profile.
- Historischer Block-3-Stand: Profile lagen in `~/.config/itomiscan/profiles.json`. Seit Block 4 wird nach `~/.config/itomiscan/itomiscan.db` migriert. JSON bleibt als unverändertes Original.
- Geräteabhängig inaktive/nicht unterstützte Optionen werden beim Anwenden ignoriert. Die Felder bestimmen weiterhin wie bisher die an `scanimage` übergebenen Argumente, **ohne Shell-Aufruf**. Bestehende JPEG-PDF-Beschleunigung bleibt erhalten.
- Webbasierte Profilverwaltung und SQLite-Migration bestehen seit Block 4. Ab Block 5 können Benutzer eigene zugewiesene Profile und Berechtigungen erhalten, einschließlich PIN-Ziffernfeld und automatischer Abmeldung. Gemeinsame Profile werden bei aktiver PIN-Verwaltung nur im Web verändert.

## Bildschirmschoner

- Ab fünf Minuten Eingabe-Inaktivität ohne Scanauftrag und ohne modalen Dialog erscheint eine schlichte dunkel gehaltene Uhrzeitansicht.
- Touch oder Tastendruck weckt die Ansicht und sollte keinen Scan durch den ersten Tastendruck auslösen. Die tatsächliche Touch-Reaktion muss am N1800 geprüft werden.
- Aktuell rein visuell; keine Display-Helligkeitssteuerung oder automatischer Suspend.

## Prüfungen und noch offene Punkte

- GitHub-Actions-Linux-Workflow: Python-Kompilierung, Shell-Syntax, Profildatei-Unit-Tests sowie virtuelle Tk-GUI-Prüfung unter Xvfb.
- Geräteprüfungen offen: reale Touch-Zielgrößen, Übergabe Splash → Startseite oder PIN-Eingabe, physische Scantaste vor und nach Login, persönliche Scanprofile, zeitgesteuerte Abmeldung, Bildschirmschoner und unveränderte Scan-/PDF-Verarbeitung auf dem Atom N270.
- Eine echte vollwertige Zielvorschau mit nachträglichem Löschen/Drehen/Umsortieren von Seiten ist noch nicht implementiert. Die bereits vorhandene Vorschau zeigt die gescannten Seiten. Die sichere Auftragsverwaltung und Übertragungsziele folgen in den vereinbarten späteren Blöcken.

**Blöcke 4 und 5 sind im Entwicklungszweig implementiert:** passwortgeschützte Webadministration und optionale PIN-Benutzer. Hardwareabnahme offen. Release 1.0.0 frühestens in Block 8 nach ausdrücklicher Freigabe.

## Ergänzung Block 6: Zielauswahl und PDF-Zustellung

Nach der Zielauswahl wird das konfigurierte, berechtigte Scanprofil genutzt. Eine gewählte PNG-Ausgabe bleibt lokal erhalten; für ausgehende Zustellungen wird zusätzlich eine PDF erzeugt. Die ursprüngliche Scan-Datei wird nicht gelöscht. Wartende PDF-Aufträge sind in SQLite samt SHA-256 geschützt und im Browser unter **Aufträge** sichtbar. Bei nicht erreichbarem Ziel bleibt die Datei lokal; der Worker unternimmt nur sichere Wiederholungsversuche. Es gibt noch **keine** vollständige nachträgliche Seitenbearbeitung. Der CUPS-Kopiermodus ist seit Block 7 implementiert; Originalhardware nicht getestet.

## Block 7: Touch-Kopieren

Der Kopieren-Button öffnet eine eigenständige große Oberfläche für lokal eingerichtete CUPS-Drucker, Kopienanzahl 1–20, ADF Front/Duplex und einseitigen/Duplexdruck. Bei mehr als sechs Druckern kann seitenweise geblättert werden. Die physische Fronttaste startet hier den Kopierauftrag. PIN-Recht `copy` gilt unabhängig vom Recht `scan`. Die Kopie wird zunächst als PDF gesichert und erst danach durch den Zustelldienst an CUPS übergeben. Echte Druckerabnahme am N1800 steht aus. Einzelheiten: [PRINTING.md](PRINTING.md).
