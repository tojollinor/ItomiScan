# ItomiScan Touch-Oberfläche (Block 3/8)

Status 13.10.2026: **auf `develop/1.0.0` committet, nicht am N1800 getestet**, `main` unverändert.

## Ansicht und Navigation

- Das vereinfachte Scannerlogo wird ohne zusätzliche Bilddatei mit geometrischen Canvas-Elementen gezeichnet. Die große Schrift und kontrastreichen Schaltflächen sind auf die Anzeige 1024×768 und ältere Touchhardware ausgerichtet.
- Nach dem Splash erscheint eine Startseite mit **Scannen**, **Paperless**, **Kopieren** und **Netzwerkordner**. Nur das lokale Scannen ist verfügbar. Die weiteren Tasten sind ausdrücklich mit „In Vorbereitung“ gekennzeichnet; sie behaupten keine erfolgreiche Netzwerkübertragung.
- Die Taste **Scannen** öffnet die vorhandene Experten-/Detailansicht mit allen vom SANE-Backend erkannten, aktiven Optionen. Mit **← Startseite** gelangt man zurück; nicht während eines Scanauftrags.
- Die Taste **Jetzt scannen** auf der Startseite oder die echte Scanner-Fronttaste verwendet das aktuell gewählte Profil, zeigt den laufenden Scan in der Detailansicht und danach die bereits vorhandene, speicherschonende Bildvorschau mit Seitennavigation.
- **Beenden, Update, Ausschalten** bleiben vorhanden. Auf dem Entwicklungszweig ist das automatische GitHub-Update nach `origin/main` bewusst gesperrt, um einen ungeprüften Versionswechsel zu vermeiden.

## Scanprofile

- Voreinstellungen: Dokument = Color/200 DPI/ADF Duplex/PDF; Text = Gray/300 DPI/ADF Duplex/PDF; Foto = Color/300 DPI/ADF Front/PNG.
- Die Eingabefelder der Detailansicht bleiben veränderbar. **Profil speichern** legt Ausgabeformat, Modus, Quelle, DPI und die übrigen aktiven SANE-Eingaben unter einem Namen ab. Eine vorhandene Vorlage desselben Namens wird überschrieben; bis zu 30 Profile.
- Das Profil wird aktuell lokal in `~/.config/itomiscan/profiles.json` gespeichert. JSON-Einträge werden validiert und **atomar** ersetzt, Verzeichnis 0700, Datei 0600. Beschädigte Konfigurationsdateien werden nicht automatisch überschrieben.
- Geräteabhängig inaktive/nicht unterstützte Optionen werden beim Anwenden ignoriert. Die Felder bestimmen weiterhin wie bisher die an `scanimage` übergebenen Argumente, **ohne Shell-Aufruf**. Bestehende JPEG-PDF-Beschleunigung bleibt erhalten.
- Profile sind in Block 3 noch lokale Übergangsdaten. Mehrbenutzerverwaltung, webbasierte Bearbeitung und SQLite-Übernahme folgen in Block 4/5.

## Bildschirmschoner

- Ab fünf Minuten Eingabe-Inaktivität ohne Scanauftrag und ohne modalen Dialog erscheint eine schlichte dunkel gehaltene Uhrzeitansicht.
- Touch oder Tastendruck weckt die Ansicht und sollte keinen Scan durch den ersten Tastendruck auslösen. Die tatsächliche Touch-Reaktion muss am N1800 geprüft werden.
- Aktuell rein visuell; keine Display-Helligkeitssteuerung oder automatischer Suspend.

## Prüfungen und noch offene Punkte

- GitHub-Actions-Linux-Workflow: Python-Kompilierung, Shell-Syntax, Profildatei-Unit-Tests sowie virtuelle Tk-GUI-Prüfung unter Xvfb.
- Geräteprüfungen offen: reale Touch-Zielgrößen, Übergabe Splash → Startseite, PIN noch nicht implementiert, Startprofil, physische Scan-Taste auf der Startseite, Profil-Speichern, Bildschirmschoner, unveränderte Scan-/PDF-Engine auf dem Atom N270.
- Eine echte vollwertige Zielvorschau mit nachträglichem Löschen/Drehen/Umsortieren von Seiten ist noch nicht implementiert. Die bereits vorhandene Vorschau zeigt die gescannten Seiten. Die sichere Auftragsverwaltung und Übertragungsziele folgen in den vereinbarten späteren Blöcken.

In **Block 4/8** folgt die passwortgeschützte Webadministration, noch **nicht vorhanden**. Release 1.0.0 frühestens in Block 8 nach ausdrücklicher Abnahme.
