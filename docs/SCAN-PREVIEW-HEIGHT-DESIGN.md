# DOC-2: Scanvorschau nutzt volle verfügbare Höhe (Entwurf)

Status: 2026-10-18. **Geplant, nicht implementiert und nicht auf dem N1800 getestet.** Änderungsregister: `docs/BETA-NEXT-CHANGEPLAN.md`.
Auslöser: Screenshot des Nutzers vom 18.10.2026, Scanvorschau mit zwei Seiten auf 1024×768.

## Problem

Die Thumbnail-Leiste links endet bereits mit dem aktuellen Vorschaufenster. Ein erheblicher Teil der Fensterhöhe wird von separaten Seitenwechsel-Schaltflächen, mehreren Aktionszeilen und Abstand unterhalb der Seitenansicht belegt. Die eigentliche Dokumentenvorschau wird dadurch zu klein. Die geforderte volle Inhaltshöhe wird nicht erreicht.

## Vorgesehene Anordnung (1024×768)

```text
┌─────────────────────────────────────────────────────────────────┐
│ ItomiScan                                  IP …                 │ Kopfbereich, bestehender Stil
├─────────────┬───────────────────────────────────────────────────┤
│ Seiten      │ SCANVORSCHAU                    Seite 1 / 2       │
│ ┌─────────┐ │                                                   │
│ │ Seite 1 │ │                                                   │
│ └─────────┘ │                                                   │
│ ┌─────────┐ │          Dokument (fit-to-area)                    │ Gemeinsamer
│ │ Seite 2 │ │          mit neutralem Hintergrund                │ flexibler
│ └─────────┘ │                                                   │ Vorschaubereich
│  Scrollen   │                                                   │
│             │                                                   │
├─────────────┴───────────────────────────────────────────────────┤
│ Erneut scannen | Drehen | Löschen | Leer prüfen | ← Seite | →   │ Kompakte Werkzeugleiste
├─────────────────────────────────────────────────────────────────┤
│ Home | Menü          Weitere Seiten scannen | Fertig übernehmen│ Bestehende Navigation
└─────────────────────────────────────────────────────────────────┘
```

## Layoutregeln

1. Hauptansicht füllt die nutzbare Fläche zwischen bestehendem Header und unverändert erforderlicher Bottom-Navigation. Keine zusätzliche vertikale Leerfläche.
2. Linke Miniaturleiste über die **gesamte Höhe des flexiblen Vorschaubereichs**, unabhängig von Anzahl und Höhe der Seiten. Bei vielen Seiten vertikal scrollbar; jeweils aktive Seite mit vorhandener Akzentfarbe hervorgehoben.
3. Rechts nimmt der Viewer die komplette verbleibende Breite und dieselbe Höhe wie die Miniaturleiste ein. Die PDF-/Bildseite wird proportional und ohne Abschneiden in die **größtmögliche verfügbare Fläche** eingepasst. Hochkantdokumente bleiben hochkant, kein Stretching.
4. Titel „SCANVORSCHAU“, Seitenzähler und Dokumentstatus möglichst in die obere schmale Zeile legen. Den langen gespeicherten Dateipfad nicht ständig als zusätzliche eigene Zeile zeigen; optional im Informationsdialog oder gekürzt als Status.
5. Alle bereits vorhandenen Aktionen erhalten: Erneut scannen, Drehen, Löschen, Leere Seiten prüfen, Seite zurück/vor, Weitere Seiten scannen und Fertig/Dokument übernehmen. Die Werkzeugaktionen kompakt auf einer Leiste; bei zu wenig Breite priorisiert gruppieren, nicht unlesbar verkleinern.
6. Feste Home-/Menü- und Abschlussbuttons bleiben erreichbar und in den bestehenden Größen/Abständen. Keine neue Farbwelt, keine abweichenden Rundungen/Icons. Berührungsflächen groß genug für die Originalhardware.
7. Die Inhalte werden **reaktiv** zur verfügbaren Höhe positioniert. Keine festen Pixelhöhen für den Dokument-Viewer, die bei unterschiedlichen Seitenzahlen oder Textlängen ungenutzten Raum erzeugen. Rendering/PDF-Skalierung ohne zusätzliche Vollauflösungs-Kopien im RAM (Atom N270, ca. 1 GiB).
8. Auswahl einer Miniatur aktualisiert Viewer und Seitenzähler; Drehen/Löschen/Seitenwechsel hält Auswahl und Leiste synchron. Die bereits bestehenden Scan- und Abschlussaktionen dürfen keine Funktion verlieren.

## Abnahme auf dem N1800

- 1024×768: Miniaturleiste und Hauptviewer sind vom unteren Rand der Vorschau-Kopfzeile bis zur kompakten Werkzeugleiste gleich hoch, kein künstlicher Leerstreifen dazwischen.
- Einzelnes A4, zweiseitiger Duplex-Scan und mehrseitiger Stapel: Dokument jeweils maximal groß, ohne Verzerrung, vollständig sichtbar.
- Zehn und mehr Seiten: Miniaturen scrollbar, ausgewählte Seite sichtbar, Vorschauhöhe unverändert.
- Touch-Test sämtlicher Aktionen und Seitenwechsel, keine Überlappungen, kein abgeschnittener Text.
- Neu scannen, Drehen, Löschen, Leerseitenprüfung und Abschließen funktionsfähig. PDF-/Bildansicht bleibt speicherschonend.
- Nicht betroffene Bildschirme und bestehende Gestaltung unverändert.

## Grenzen

Dies ist ein **Layout- und Umsetzungskonzept**, kein bestätigter Mockup- oder Code-Stand. Vor Implementierung aktuelle Tkinter-Widget-Hierarchie und reale verfügbare Pixelhöhe ermitteln. Keine Änderungen an anderen Ansichten, GRUB, Splash oder Releases.
