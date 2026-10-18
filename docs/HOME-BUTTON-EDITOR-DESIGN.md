# UI-2.1: Frei konfigurierbare Startseite und Gruppenbuttons

Stand: 2026-10-18. **Geplant, nicht implementiert.** Zielbranch `develop/1.0.0`. Bestehende ItomiScan-Touch- und Web-Designmuster unverändert als Grundlage.

## Nutzerziel
In der Webadministration Scan-Ziele und Drucker unabhängig voneinander konfigurieren und anschließend **Startseitenbuttons** erstellen oder bearbeiten, die vorhandene Zielverbindungen und passende Scanprofile verknüpfen. Gruppenbuttons führen auf Unterseiten, deren Buttons ebenfalls bearbeitet und sortiert werden können. Ein einzelner Scan kann an **mehrere Ziele** verteilt werden.

## Beispielkonfiguration

- **Paperless**: Aktion „Scannen und zustellen“, vorhandene gespeicherte Paperless-Verbindung wählen. Nach einem Scan wird das erzeugte Dokument an Paperless übergeben.
- **Kopieren**: „Scannen und drucken“, einen vorhandenen installierten Netzwerkdrucker und ein geeignetes Profil wählen.
- **Kopieren + Paperless**: **Einmal** scannen, **dieselbe PDF** als unabhängige Aufträge an den gewählten Drucker und an die gewählte Paperless-Verbindung zustellen. Nicht zweimal scannen, keine Abhängigkeit zwischen Druck und Paperless.
- **Gruppe „Büro“**: öffnet eine Unterseite mit eigenständigen Buttons; Navigation „Zurück“ bleibt sichtbar.

## Webeditor
1. Bereich **Startseite gestalten** mit visueller Vorschau auf 1024 × 768. Hinzufügen, Bearbeiten, Deaktivieren, Löschen, Umbenennen und Reihenfolge ändern.
2. Pro Button: Beschriftung, vorhandenes Icon, Aktionstyp, optional Zielseite/Gruppe, Scanprofil sowie ein oder mehrere **gespeicherte** Ziele wählen (z. B. Drucker + Paperless). Keine Zugangsdaten im Button speichern.
3. Gruppen: eigener Titel, eigene Reihenfolge und Unterbuttons; verschachtelte Gruppen nur, wenn Navigation und Speichergrenzen sicher und verständlich bleiben. Keine Zyklen.
4. Zielarten nach Aktion filtern: Nur konfigurierte und verfügbare Drucker für „Kopieren“, nur gespeicherte Paperless-Ziele für Paperless-Zustellung. Fehlerhafte/entfernte Ziele im Editor markieren; keinen stillen Wechsel zu anderen Zielen.
5. Vor Speichern: Pflichtfelder, eindeutige Referenzen, Benutzerrechte und gültige Kombinationen prüfen; Vorschau mit bestehenden Komponenten. Voreingestellte Buttons bei Migration übernehmen, damit alte Startseite weiterhin bedienbar bleibt.
6. Relevante Berechtigungen bleiben auch beim Drücken des Buttons erhalten; Gruppen allein gewähren keine Rechte. Bei aktiver Benutzerverwaltung Benutzer ohne Berechtigung nur erlaubte Aktionen anzeigen.
7. Kompakte Touchansicht 1024×768, klare einheitliche Karten, bei vielen Buttons Seiten/Scrolllogik, kein UI-Zoom oder neue Farbstile.

## Ablauf Mehrziel-Button

1. Benutzer tippt z. B. **Kopieren + Paperless**. Prüfen: Anmeldung/Rechte, Scannerbereit, gewähltes Profil und beide Zielreferenzen.
2. Einmal scannen und **eine** unveränderte PDF als Dokument sichern; anschließend je Ziel einen getrennten haltbaren Zustellauftrag erzeugen: Druck an CUPS, Paperless-Upload.
3. Beide Aufträge **unabhängig** bearbeiten; erfolgreicher Druck bedeutet nicht erfolgreichen Upload und umgekehrt. Fortschritt und Status pro Ziel sowie Gesamtergebnis anzeigen.
4. Bei Offline-Drucker oder Paperless-Störung lokale PDF und ausstehende Zielaufträge erhalten. Wiederholversuche sicher handhaben; bei unsicherer Druck-/Uploadbestätigung keine blinde doppelte Übertragung. Vor Ausführung Mehrziel-Queue atomar bzw. mit eindeutigem dokumentbezogenem Ablauf erfassen, damit nicht versehentlich nur ein Ziel eingeplant wird, ohne dies kenntlich zu machen.
5. Doppelklickschutz und prozessbezogene Ladeanzeige; während Scannen nicht erneut dieselbe Aktion anstoßen. Scanbearbeitung/Vorschau nach bestehenden Regeln ermöglichen.
6. Bei Löschung oder Umkonfiguration eines Druckers/Paperless-Ziels Buttons als reparaturbedürftig markieren; alte Zielreferenzen niemals stillschweigend umbiegen.

## Abgrenzung
- Startseiten-Editor verwaltet nur Darstellung, Aktionen, Zielreferenzen und Scanprofilreferenzen; **Druckerinstallation, Paperless-Zugangsdaten und Netzwerkkonfiguration bleiben** in der jeweiligen Zielverwaltung.
- Vorhandene manuelle Scan-/Kopierfunktionen müssen weiterhin verfügbar bleiben. Ggf. unveränderliche Notfallnavigation/Home/Menü vorsehen, damit man sich nicht aussperrt.
- Nicht Bestandteil dieses Entwurfs: beliebiger Skriptstart, frei programmierbare Shell-Aktionen oder anonyme Rechteumgehung.

## Tests/Abnahme
- Paperless-Button nutzt genau den zugewiesenen gespeicherten Endpunkt.
- Kombinationsbutton scannt **nur einmal** und erzeugt getrennte Aufträge für Drucker und Paperless mit derselben Quell-PDF.
- Paperless offline, Drucker online und umgekehrt: unabhängige Statusmeldung, lokale Wiederherstellbarkeit und kein unkontrollierter Doppeldruck.
- Gruppen-Navigation und Rückkehr auf die Hauptstartseite funktionieren auf dem N1800 per Touch.
- Bearbeiten, Anordnen, Löschen, inaktive/gelöschte Ziele, Berechtigungsprüfung und Migration vorhandener Startbuttons getestet.
- Webeditor und echte Touch-UI folgen bestätigtem ItomiScan-Design; main/Stable unberührt.

## Vor Umsetzung entscheiden
- Sollen Gruppen beliebig tief verschachtelbar sein oder zunächst nur **eine Unterebene**? Für 1024 × 768 ist eine Unterebene die unkomplizierteste und robusteste Voreinstellung.
- Können frei konfigurierte Buttons zusätzlich einen optionalen Bestätigungs-/Dokumentprüfschritt vor Zustellung erhalten? Bestehenden Scan-/Vorschauablauf bei der Implementierung prüfen.
