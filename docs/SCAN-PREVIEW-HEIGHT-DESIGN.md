# DOC-2: Scanvorschau über volle Inhaltshöhe (überarbeiteter Entwurf)

Status: 2026-10-18. **Geplant; noch nicht implementiert oder am N1800 getestet.** Bezug: Screenshot vom 18.10.2026; Änderungsregister `docs/BETA-NEXT-CHANGEPLAN.md`.

## Ziel

Auf dem 1024×768-Touchdisplay muss die Dokumentenvorschau die maximal nutzbare **Höhe** erhalten. Die bisherige breite Werkzeugleiste unter dem Viewer entfällt vollständig. Werkzeuge und Seitennavigation ziehen **nach links** und verwenden eindeutige Symbole statt breiter Textbuttons. Die bestehende Designsystematik (Farben, Abstände, Rahmen, Klickverhalten) bleibt erhalten.

## Schematischer Aufbau (keine pixelgenaue Darstellung)

```text
┌─────────────────────────────────────────────────────────────────────────┐
│ ItomiScan                                            IP …               │
├──────────────────┬───────┬──────────────────────────────────────────────┤
│ SEITEN           │TOOLS  │ SCANVORSCHAU                  Seite 1 / 2     │
│ ┌──────────────┐ │  ↻    │                                              │
│ │ Miniatur 1   │ │  ⟳    │                                              │
│ └──────────────┘ │  ✕    │                                              │
│ ┌──────────────┐ │  ◫    │          DOKUMENT MAXIMAL GROSS              │
│ │ Miniatur 2   │ │       │          und proportional eingepasst         │
│ └──────────────┘ │  ↑    │                                              │
│   ⇅ scrollen     │  ↓    │                                              │
│                  │       │                                              │
│                  │       │                                              │
├──────────────────┴───────┴──────────────────────────────────────────────┤
│ Home  Menü                     Weitere Seiten scannen  Fertig übernehmen│
└─────────────────────────────────────────────────────────────────────────┘
```

- Die **linke Funktionszone** umfasst eine scrollbare Miniaturspalte und direkt daneben eine schmale vertikale Symbolleiste. Beides ist Teil des selben hochflexiblen Hauptbereichs wie die rechte Dokumentenvorschau.
- Symbolfunktionen von oben: erneutes Scannen (↻), aktuelle Seite drehen (⟳), aktuelle Seite löschen (✕), leere Seiten prüfen (◫), vorherige/nächste Seite (↑/↓). Die endgültigen Piktogramme aus den **vorhandenen UI-Iconmustern** auswählen und auf Verständlichkeit überprüfen; diese Textzeichen sind nur Platzhalter.
- **Keine** zusätzliche Zeile mit `Zurück / Weiter` und **keine** mehrzeilige Aktionsmatrix unter dem Viewer.
- Die untere, dauerhaft erreichbare Hauptnavigation enthält weiterhin Home, Menü, **Weitere Seiten scannen** und **Fertig · Dokument übernehmen**. Diese entscheidenden Textbeschriftungen bleiben, damit sie sich nicht mit den Seitenwerkzeugen verwechseln.
- Dokumentstatus/Dateipfad nicht als permanenten zusätzlichen Höhenverbrauch anzeigen. Kurzstatus in die obere Zeile integrieren, vollständigen Pfad bei Bedarf im Detail anzeigen.

## Layout- und Interaktionsregeln

1. Die Kopfzeile und die untere Hauptnavigation behalten das bestätigte ItomiScan-Design. Der dazwischenliegende Bereich wächst bis zur maximal verfügbaren Höhe.
2. Links Seitenminiaturen über die gesamte freie Inhaltshöhe scrollbar; der aktive Eintrag behält die vorhandene blaue Markierung. Viele Seiten verändern die Höhe des Viewers nicht.
3. Daneben schmale vertikale Iconleiste, als Richtgröße ca. **52–60 px Breite** mit **mindestens 44–48 px hohen Touchzielen** (vor der Implementierung anhand realer Geometrie prüfen). Nicht skalierbare winzige Iconbuttons vermeiden.
4. Die rechte Vorschau bekommt **sämtliche restliche Breite und Höhe** des Hauptbereichs. Seiten proportional und vollständig einpassen (fit-to-area), ohne Verzerrung oder Abschneiden, unabhängig von Hoch-/Querformat.
5. Seitennavigation wählt immer eine der Miniaturen an und aktualisiert den Zähler; Drehen/Löschen/Leerseitenprüfung hält Auswahl, Reihenfolge und Vorschau synchron. Nicht verfügbare Aktionen deaktivieren.
6. Für riskante Aktionen (insbesondere Löschen) das vorhandene Bestätigungsmuster wiederverwenden; keine neuen Dialogdesigns.
7. Symbolbuttons erhalten eindeutige Tooltips bzw. im UI vorhandene Hilfe-/Langdruckmuster, soweit auf Touch nutzbar. Sie dürfen nicht auf farbliche Unterscheidung allein angewiesen sein.
8. Kein unnötiges Neurendern aller PDF-Seiten in voller Auflösung. Die ressourcensparende Vorschau auf Atom N270 (~1 GiB RAM) beibehalten.
9. Nur die Scanvorschauseite ändern. Andere Seiten, Startlogik, Benutzerverwaltung, Bootkonfiguration und Releases bleiben unberührt.

## Abnahmekriterien

- Auf 1024×768 füllen Miniaturzone, Werkzeug-Icons und Dokument-Viewer gemeinsam die volle Höhe **zwischen Kopfzeile und einziger Bottom-Navigation**. Keine zusätzliche Aktionszeile unter der Vorschau.
- Mindestens eine, zwei und zehn Seiten: Viewerhöhe konstant maximal; Miniaturen scrollbar; aktive Auswahl sofort sichtbar.
- Erneut scannen, Drehen, Löschen, Leerseitenprüfung, Vor-/Zurückblättern, weitere Seiten scannen und Fertig/Dokument übernehmen funktionieren per Touch.
- Keine überlappenden oder abgeschnittenen Bedienelemente. Die Hauptaktionen bleiben eindeutig beschriftet und ausreichend groß.
- PDF- und Bildansichten passen A4 hochkant sowie Querformat vollständig ein. Keine auffällige Vergrößerung des Speicherverbrauchs.
- Bestehende UI-Farben/-Größen/-Muster übernommen; nicht betroffene Ansichten unverändert.

## Umsetzung

Vor der Implementierung die vorhandene Tkinter-Widgethierarchie und tatsächlichen Innenmaße messen. Dieser Entwurf ist der verbindliche geplante DOC-2-Layoutstand, **kein bereits realisierter GUI-Code**.
