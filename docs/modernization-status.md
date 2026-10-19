# Modernisierung 1.0.0: Implementierungsstand

Stand: 19. Oktober 2026. Ausgangspunkt: `2709518` auf `develop/1.0.0`.
Dies ist **keine Abschluss- oder Releasefreigabe** für den Gesamtauftrag.

## Implementiert und gezielt geprüft

- Eigentümerbezogene Entwurfsmanifeste in SQLite; unveränderliche, atomar
  geschriebene Seitenkopien mit SHA-256-Dateinamen. Geräteeigentümer bei
  deaktivierter Benutzerverwaltung. Unveränderte Seiten werden nicht erneut
  geschrieben. Reihenfolge, entfernte Seiten, Originalversionen, Vorschauposition,
  Ausgabeformat, Profil, Scanparameter und Zustellabsichten werden gesichert.
- Wiederherstellung nach Anmeldung und Programmstart. Abmeldung löscht nur den
  sichtbaren Sitzungszustand. Fehlgeschlagene Sicherung verhindert freiwillige
  Abmeldung; eine Sicherheitsansicht verdeckt Dokumente auch bei Schreibfehlern.
- Vollsicherungen enthalten Entwurfsseiten und Arbeitsverzeichnisse. Abschluss
  und ausdrücklich bestätigtes Verwerfen entfernen das offene Manifest;
  vorhandene Dokumentdateien werden dabei nicht automatisch gelöscht.
- Keine Ersatzkacheln oder Profil-Schnellstarts bei leerer Startseitenkonfiguration.
  Der Scanstart prüft zusätzlich auf konfigurierte aktive Scanaktionen. Änderungen
  an Buttons werden auf der sichtbaren Startseite ohne Neustart eingelesen.
- Statusbeschriftung; Benutzerabmeldung im Menü; Menü unterstützt auch mehr
  als sechs Einträge. Offene Tastaturen und Dialoge werden vor PIN-Seite und
  Bildschirmschoner geschlossen. PIN-Ziffernblock bei 1024 × 768 korrigiert.
- Gemeinsame Touchbestätigungen mit Abbrechen als Standard für bisherige
  messagebox-Aufrufe in Anwendung, Zustellstatus und Updateansicht.

## Abgleich mit dem Gesamtauftrag

| Abschnitt | Stand und noch notwendige Arbeit |
| --- | --- |
| 1–2 Auftrag und Grenzen | Branch-, CI- und Gerätestand erhoben; keine Änderungen an main, Stable, Netzwerkkonfiguration oder Projektweisungen. |
| 3 Kioskmodernisierung | Teilweise. PIN-/Tastaturübergänge verbessert; vollständige zentrale Ansichtsverwaltung und gesamte Gestaltung noch offen. |
| 4 Konfigurierte Startseite | Ersatzbuttons entfernt, Scanstart bei leerer Konfiguration gesperrt, Aktualisierung ergänzt. Freie Geometrie, individuelle Sichtbarkeit und Kontozuweisung fehlen. |
| 5 Visueller Editor | Noch offen; vorhandene Formularverwaltung ist kein Drag-and-Drop-Editor. |
| 6 Menü/Navigation | Teilweise. Statusbeschriftung und Abmeldung angepasst; einheitliche persistente Navigation aller Arbeitsansichten noch abzugleichen. |
| 7 Zentraler Status | Noch offen; vorhandene Gerätestatus- und Zustellansichten sind noch kein gemeinsames Meldungsmodell mit Verlauf. |
| 8 Benutzerverwaltung | Bestehende PIN-Sicherheitsregeln erhalten. Benutzerbuttons und Benutzername-plus-PIN noch offen. |
| 9 Sitzungsverhalten | Entwürfe geschützt, überlagernde Dialoge geschlossen. Getrennte konfigurierbare Sperr-/Abmeldeaktionen und Zeiten noch offen. |
| 10 Entwürfe | Persistenz und Eigentümertrennung umgesetzt. Vollständige Hardwareabnahme, Wiederherstellung sämtlicher Arbeitsansichten und Verhalten bei Stromausfall während laufender Erfassung noch offen. |
| 11 Scan/Bearbeitung | Bestehende Bearbeitung erhalten und Entwurfssicherung integriert. Vollständiger Funktionsabgleich einschließlich physischer Scanabläufe noch offen. |
| 12 Touchdialoge | Gemeinsames System ergänzt. Spezialisierte Dokument-/Scannerdialoge und sämtliche Dialoggrößen noch vollständig zu vereinheitlichen. |
| 13 Webadministration | Navigation, Systemunterseiten, Dashboardverlauf und Responsive-Abnahme noch offen. |
| 14 noVNC | Vorherige Reparaturen bleiben enthalten. Bereinigung redundanter Steuerung und vollständige Tastatur-/Mausabnahme noch offen. |
| 15 Ladeanimation | Noch nicht bearbeitet. |
| 16 Zielverwaltung | Noch nicht modernisiert. |
| 17 Netzwerkprotokolle | Noch offen; bestehender Netzwerkzusteller unterstützt SMB, nicht sämtliche beauftragten Protokolle. |
| 18 SMB-Netzwerksuche | Noch offen. |
| 19 USB-Ziele | Flexible/stabile Datenträgerauswahl und Auswerfen noch offen. |
| 20 Netzwerkkonfiguration | Validierung, Anwendung mit Bestätigungsfrist und Rollback noch offen. Reales Netzwerk bleibt unverändert. |
| 21 Drucker/Zustellungen | Bestehende Tests erhalten. Vollständige fachliche und gestalterische Abnahme noch offen. |
| 22 Regressionen | Vorhandene automatisierte Regressionen ausgeführt; Hardwarefunktionen noch nicht bestätigt. |
| 23 Prüfungen | Entwurfs-, Sicherheits-, Backup- und GUI-Regressionen ergänzt. Vollständige Prüfung des gesamten neuen Funktionsumfangs erst nach dessen Umsetzung möglich. |
| 24 SSH | Diagnosen und Tests in isolierten /tmp-Verzeichnissen. Xvfb nur nach /tmp entpackt; keine Paketinstallation erforderlich. |
| 25 Hardwaretests | Noch ausstehend. Kein Hardwareerfolg behauptet. |
| 26 Release | Kein neuer Release oder Tag. Beta.6 bleibt letzter bestätigter Release. |
| 27 Zusatzvorschläge | Erst nach Umsetzung und technischer Prüfung der beschlossenen Anforderungen vorzulegen. |
| 28 Abschluss | Gesamtauftrag nicht abgeschlossen; diese Matrix hält die offenen Anforderungen ausdrücklich fest. |

## Prüfbelege

Die isolierte Debian-Prüfung des ersten Entwurfsstands bestand 231 Headless-Tests
einschließlich Webserver, TLS, VNC, Zustellung, Berechtigungen und Vollbackup.
Nachfolgende GUI-Prüfungen decken Benutzerwechsel, Schreibfehler, PIN-/DPI-Übergang,
leere Startseite sowie sichere Bestätigungen ab. Maßgeblich für einen späteren
Testkandidaten sind die CI-Ergebnisse seines exakten Commits und die anschließend
vom Benutzer bestätigten Hardwaretests.
