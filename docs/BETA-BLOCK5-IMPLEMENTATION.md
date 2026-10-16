# ItomiScan Beta – Block 5: Scanner-Hintergrundstart und Dokumentenprüfung

Stand: 16.10.2026, Branch `develop/1.0.0`. Dies ist ein Entwicklungs- und Prüfnachweis, **kein veröffentlichtes Release und keine N1800-Hardwareabnahme**.

## Umsetzung

- Kiosk zeigt zuerst die Hauptoberfläche mit Profilwahl. Scannererkennung, Optionsabfrage und Touch-Geräteprüfung laufen danach in einem Thread. Die tatsächliche Bereitstellung wird ausschließlich auf dem Tk-Hauptthread verarbeitet.
- Optionaler Cache unter `~/.cache/itomiscan/scanner-options.json`: Version, Fujitsu-Gerätekennung und begrenzte, validierte SANE-Optionen. Schreibvorgang ist atomar, Datei erhält Modus 0600. Der Cache ist **nur ein UI-Hilfsmittel**, kein Nachweis über einen angeschlossenen Scanner oder dessen Bereitschaft. Live-SANE-Ergebnis ersetzt ihn.
- Ein früh gedrückter Scanbutton zeigt eine abbrechbare Warteansicht mit dem bestehenden ItomiScan-Stil. Der Scanstart wird erst nach positivem Live-Ergebnis ausgelöst; Rechte, Profil und Dokumentstatus werden beim tatsächlichen Start erneut geprüft. Abbruch oder Scan-Erkennungsfehler löscht die Absicht.
- Nach einem Gerätefehler wird bei neuem Scanwunsch die Hintergrundprüfung erneut gestartet. Der bisherige direkte Start `app.py` bleibt als Kompatibilitätsfall erhalten.
- Die Dokumentenprüfung ist **im Code bereits vorhanden**: Seiten drehen, löschen, sortieren/verschieben, Leerseitenprüfung mit Bestätigung, gezieltes erneutes Scannen, weitere Seiten und das Fertigstellen erst nach Freigabe. Diese Funktionen wurden deshalb nicht neu implementiert oder mit konkurrierenden Mechanismen überschrieben. Regressionstests für dokumentierte Verhaltensweisen befinden sich in `tests/test_review_workflow.py`.

## Prüfungen und ausstehende Abnahme

- `tests/test_scanner_cache.py` prüft gültigen Cache-Roundtrip sowie defekte/fremde/überlange Inhalte.
- Erweiterte `tests/test_gui_smoke.py` prüfen frühe Scananforderungen, Abbruch und tatsächliche Live-Bereitschaft.
- GitHub-Actions-Status nur für den **letzten Commit** separat auswerten; ein erfolgreicher Syntaxcheck allein genügt nicht als Freigabe.
- Auf dem N1800 messen: Bildschirmzeit bis GUI unabhängig vom Scanner, Hintergrundbereitstellung, frühes Scannen, Abbruch, Fehler und erneutes Erkennen, persistenter Cache nach Neustart, PIN-Rechte, mehrseitige Scans und Dokumentbearbeitung.
- Praktischer Touch- und Scannerfunktionstest nach dem separaten Test mit 16-MB-Initramfs weiterhin offen. Dauerhafte Bootaktivierung ist Block 6, nicht Teil dieser Codeänderungen.
- Browser-Fernbedienung bietet noch **keine** Live-Bildschirmspiegelung oder Browser-Dokumentenvorschau; das darf durch diesen Block nicht als umgesetzt gelten.
