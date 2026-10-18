# WEB-9: Vereinfachte ItomiScan-Druckerverwaltung (UI/UX-Entwurf)

Stand: 2026-10-18. **Entwurf, nicht implementiert.** Bezug: WEB-8 Druckeridentifikation und IP-Zuordnung; bestehende ItomiScan-Webdesignsprache beibehalten.

## Ausgangsproblem

Die jetzige Seite zeigt zuerst eine technische CUPS-/Zielverwaltung, verlangt Namen, Protokoll, Host und Sonderadressen, trennt „Speichern“ von „In CUPS einrichten“, listet rohe DNS-SD-/LPD-/IPP-URLs als eigene Druckerkandidaten und führt automatisch erkannte CUPS-Ziele als scheinbar installierte „CUPS-Warteschlangen“ auf. Für Endanwender ist unklar, was bereits hinzugefügt ist.

## Sollaufbau (Desktop und mobil)

**Drucker** (knappe einzeilige Erklärung, keine technische Einführung)

### Eingerichtete Drucker
- Pro wirklich installierter, verwalteter Warteschlange eine kompakte Karten-/Listenzeile: verständlicher Druckername, IP-Adresse oder Host, bei Bedarf Kennzeichnung „Standard“.
- Primäre Aktion „Testseite“ und sekundäre Aktion „Details“; im Detaildialog „Als Standard“, „Verbindung aktualisieren“, „Entfernen“ mit Bestätigung.
- „Noch keine Drucker eingerichtet“ als klarer Leerzustand. Automatisch erkannte CUPS-Ziele **nicht** als installiert anzeigen. Erkennung (`lpstat -e`) und echte Einrichtung (`lpstat -v`/konfigurierte Queue) unterscheiden.
- Existierende ItomiScan-Ziele, die noch nicht in CUPS eingerichtet sind, transparent als „Einrichtung abschließen“ behandeln, nicht mit physisch installierten Geräten verwechseln.

### Verfügbare Drucker
- Ein Hauptbutton **„Drucker suchen“**, bei längerer Suche sofort sichtbare einheitliche Ladeanzeige („Netzwerk wird nach Druckern durchsucht …“) und deaktivierter Suchbutton; Ende mit Ergebnis, Fehler oder Leerzustand.
- Liste **eines Eintrags je verlässlich zugeordnetem physischem Gerät**, je Eintrag nur **Name, IP-Adresse, „Hinzufügen“**. Keine Protokoll-URL, UUID, „Identität bestätigt“ oder CUPS-Fachwörter.
- Klick auf „Hinzufügen“ startet die nötigen Schritte unter einem Vorgang (ItomiScan-Ziel anlegen und geeignete Druckerwarteschlange konfigurieren), mit Fortschrittszustand, eindeutiger Erfolgs-/Fehlermeldung. Erst nach bestätigter erfolgreicher Einrichtung unter „Eingerichtete Drucker“ anzeigen.
- Schon eingerichtete Geräte nicht erneut als „Hinzufügen“ anbieten.
- Nicht eindeutig zuordenbare Funde oder nicht erreichbare Geräte nicht fälschlich als identifizierte Drucker ausgeben; separate verständliche Problemzeile („Gerät konnte nicht eindeutig erkannt werden“) mit optionalem Diagnose-Detail.
- IPPS vor IPP, ggf. Fallback nur wenn technisch begründet und unterstützt; keine stillschweigende TLS-Abschwächung. Verbindungen und Gerätezusammenführung gemäß WEB-8.

### Manuell hinzufügen (eingeklappt)
- Eine unaufdringliche Option **„Drucker manuell hinzufügen“** am Ende der Seite.
- Einfacher Modus: Name (vorbelegt/automatisch vorgeschlagen), IP/Hostname; Verbindung automatisch ermitteln und technisch prüfen.
- Erweitert: Protokoll, Queue/Pfad, vollständige URI, treiber-/formatbezogene Diagnose. Sensible oder unsichere Änderungen nur mit Bestätigung.
- Keine Roh-URL-Felder oder CUPS-Setupanleitungen im Standardablauf, sofern automatische Einrichtung möglich ist.

## Verhaltensregeln

1. Vorhandene Farben, Typografie, Abstände, Buttons und Dialogmuster des bestätigten Webdesigns wiederverwenden; Desktop und schmale Mobilansicht.
2. Eine einzige verständliche Nutzersicht; intern CUPS, erkannte Geräte, ItomiScan-Ziele korrekt getrennt verwalten.
3. Kein stiller Ersatz vorhandener Druckprofile oder Löschung bestehender Druckerdaten bei Migration. Manuelle technische Einstellungen bleiben möglich.
4. Längere Vorgänge stets mit ItomiScan-Ladeanzeige und genauem Vorgangstext; Buttons gegen Doppelklick sperren, Statusfehler klar kommunizieren.
5. Installation niemals durch reine Suche starten. „Hinzufügen“ erfordert authentifizierte, CSRF-geschützte POST-Aktion und sichere Validierung vor CUPS-Schreibzugriff.
6. Keine neue Laufzeitabhängigkeit ohne nachgewiesene Notwendigkeit, Atom N270 und ca. 1 GiB RAM beachten.

## Abnahmekriterien

- Brother HL-3152CDW mit mehreren automatisch erkannten LPD-/IPP-/DNS-SD-Endpunkten erscheint genau einmal, **wenn** die Geräteidentität sicher zugeordnet wurde, mit korrekter IP und genau einem „Hinzufügen“-Button.
- Zwei gleiche Brother-Geräte mit verschiedenen Gerätekennungen erscheinen getrennt und mit eigener IP.
- `lpstat -e` listet erkannten Brother, `lpstat -v` listet keine feste Queue: Gerät gehört **nicht** zu „Eingerichtete Drucker“.
- Erfolgreiche Einrichtung verschiebt das Gerät in „Eingerichtete Drucker“ und ermöglicht Testseite/Details.
- Such-/Installationsfehler, Zeitüberschreitung und unbekannte Identität werden verständlich angezeigt; Ladeanzeige endet zuverlässig.
- Löschen/Standarddrucker/technische Bearbeitung bleiben über Detaildialog erreichbar.
- Nicht betroffene Seiten unverändert, keine Änderungen an main/Stable und keine automatischen Installationen durch Entwurf.

## Umsetzung

Vor tatsächlicher Implementierung Workflow `itomiscan/web/printing_pages.py`, bestehende Webrouten, CUPS-Funktionen und Identitätsabfrage prüfen. Dies ist ein **freizugebender Entwurf**; noch kein geänderter Funktionscode.
