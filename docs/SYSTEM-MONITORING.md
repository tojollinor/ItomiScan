# ItomiScan: kontinuierliches Systemmonitoring

## Speicherung und Messbeginn

Die Webadministration startet mit dem systemd-Webdienst einen eigenen Hintergrund-Thread. Dieser misst CPU und RAM unabhängig vom Browser alle 1 Sekunde. Der Thread wird beim Schließen des Webservers beendet. Der Prozess verwaltet einen auf 300 Messpunkte und maximal 300 Sekunden beschränkten Ringpuffer im RAM. Keine Messwerte werden in Dateien, SQLite oder auf die SSD geschrieben.

Erfasst wird **ab Start des Webdienstes**, nicht rückwirkend ab Kernel-, Plymouth- oder GRUB-Start. Weil der Dienst beim Hochfahren automatisch startet, steht die bisherige Historie beim späteren Öffnen der Webadministration bereit. Ein Webdienst-Neustart leert den Puffer erwartungsgemäß.

## Anzeigen

- Die bestehenden CPU-/RAM-Diagramme auf der Übersichts- und Systemseite laden zuerst den authentifizierten Endpunkt `/api/metrics/history` und stellen die zurückliegenden 300 Sekunden anhand echter Zeitstempel dar. Fehlende Zeitabschnitte bleiben leer.
- Anschließend aktualisiert die Webseite wie bisher einmal pro Sekunde die letzten Messwerte über `/api/metrics`. Die Auswertung erfolgt serverseitig, unabhängig von offenen Browserfenstern.
- Der doppelte RAM-Balken auf der Übersicht ist zu einer **Datenträgerbelegung** geworden. Er zeigt tatsächliche Belegung in Prozent sowie belegten und freien Speicherplatz. Vorhandene Karten, Abstände und Farben bleiben erhalten.
- Zugang zu beiden Endpunkten besteht nur nach regulärer Webanmeldung. Ihre Daten sind rein diagnostisch.

## RAM-Plausibilität

Die Berechnung entspricht weiterhin `MemTotal - MemAvailable` aus `/proc/meminfo`, nicht `MemTotal - MemFree`. Linux kann Caches unter Speicherdruck freigeben. Eine geringe Veränderung des RAM-Prozents ist deshalb plausibel. Die verfügbare Menge wird auf `0 <= MemAvailable <= MemTotal` begrenzt; bei unlesbaren Daten erscheint `Nicht verfügbar`.

## Prüfungen und offene Abnahme

Automatisierte Tests kontrollieren die CPU-Delta-Berechnung, RAM-Formel und Grenzwerte, Datenträgerbelegung, Ringpuffergrenze, zeitliches Verwerfen, unmittelbaren Start ohne Browser, HTTP-Anmeldung und die Initialisierung der Diagramme.

**Hardwareabnahme ausstehend:** Auf dem N1800 sind 5 Minuten Laufzeit ab Webdienststart, Diagramme nach einem Seitenwechsel, Neustartverhalten, reale CPU-/RAM-Werte, Datenträgerwerte und Ressourcenauswirkungen zu prüfen. CI ersetzt diese Prüfungen nicht.
