# WEB-8: Drucker eindeutig erkennen und Adressen zuordnen

Stand: 2026-10-18. **Anforderung/Entwurf, noch nicht implementiert.** Ziel: `develop/1.0.0`.

## Anforderungen
- Je eindeutig identifiziertem physischem Drucker **ein Geräteeintrag** mit erkennbarem Hersteller/Modell, zugeordneter IP-Adresse und Button **„Hinzufügen“**. Der Identitätsnachweis ist zwingende interne Voraussetzung und wird nicht als Status „Identität bestätigt“ in der normalen Oberfläche angezeigt.
- Mehrere Drucker gleichen Modells dürfen niemals nur aufgrund ihres Anzeigenamens zusammengeführt werden.
- Eine URL oder IP ist **nicht automatisch** ein Beweis für die Geräteidentität. Bei unklarer Zuordnung Einträge getrennt zeigen und Benutzer nicht mit einer unbewiesenen Identität täuschen.
- Auf Wunsch technische Verbindungsdetails anzeigen, ohne die Hauptliste mit LPD-/IPP-/DNS-SD-URLs zu überladen.

## Technische Strategie
1. Druckerdienste via DNS-SD/mDNS (_ipp._tcp, _ipps._tcp, ggf. _printer._tcp) entdecken; SRV-Ziel/Port, TXT-Attribute (z. B. `ty`, `rp`, `UUID`, `product`) sowie A/AAAA-Adressen auflösen und zusammenhalten.
2. Per IPP/IPPS `Get-Printer-Attributes` am **tatsächlich aufgelösten Endpunkt** abfragen; `printer-uuid`, `printer-device-id`, `printer-make-and-model`, `printer-uri-supported` und erreichbare Host-/Port-Kombinationen auswerten. Vorhandene CUPS-Informationen ergänzend abgleichen. Optional nur sichere, lesende Geräteabfragen; kein blindes Scannen fremder Adressbereiche.
3. Gruppierung primär über identische belastbare Geräte-UUID oder eine überprüfte andere eindeutige Kennung. Mehrere Services desselben Geräts können so zusammengeführt werden; bei widersprechenden Kennungen nicht gruppieren. Eine gleiche IP allein ist kein verlässlicher Nachweis, da IPP-Server mehrere Warteschlangen/Geräte hosten können.
4. Kann eine LPD-URL keine Kennung bereitstellen, nur dann mit IPP verbinden, wenn die Adresse über DNS-/Service-Auflösung und weitere technische Daten eindeutig zugeordnet werden kann; sonst als separater nicht bestätigter Kandidat.
5. IPPS bevorzugen, dann IPP; LPD nur als Fallback, wenn Einrichtung unterstützt und eindeutig. Die Erreichbarkeit vor Übernahme prüfen; SSL/TLS-Fehler nicht stillschweigend ignorieren.
6. Normale Geräteliste: **nur Gerätename, zugeordnete IP-Adresse und „Hinzufügen“**. Keine Statusetiketten wie „Identität bestätigt“ oder technische Protokollangaben in der Hauptliste. Bei nicht eindeutig identifizierbaren Kandidaten stattdessen einen separaten, verständlichen Hinweis mit optionalen Details anzeigen; keine ungeprüfte automatische Zusammenführung oder Einrichtung.
7. „Hinzufügen“ richtet nur den ausgewählten, verifizierten Endpunkt über das bestehende CUPS-Setup ein, mit Ladeanzeige, Fehlerdiagnose und eindeutiger Erfolgsmeldung; keine Installation allein durch die Suche.

## Abnahmetests
- 1 Drucker mit LPD-, IPP- und IPPS-Werbung: eine Gerätezeile, sofern gemeinsame Geräteidentität verifiziert; korrekte IP und bevorzugte Verbindung.
- 2 Drucker gleicher Marke und gleichen Modells mit verschiedenen UUIDs: **zwei** Gerätezeilen.
- Ein Printserver mit mehreren Queues und einer IP: Queues bleiben unterscheidbar; keine falsche Zusammenfassung aufgrund der IP.
- mDNS-Name wechselt oder DHCP-Adresse ändert sich: Zuordnung wird aktualisiert, nicht aus einem veralteten Cache behauptet.
- Unbekannte/fehlende Kennungen oder nicht erreichbare Ports: erkennbar als unbestätigt; keine stille automatische Zusammenführung.
- Prüfen, dass nur bewusst hinzugefügte Drucker installiert und Druckprofile unverändert bleiben.
