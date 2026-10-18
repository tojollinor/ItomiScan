# WEB-10: Paperless-Verbindung einrichten, testen und verständlich diagnostizieren

Stand: 2026-10-18. **Konzept, nicht implementiert**. Zielbranch `develop/1.0.0`.

## Bestandsanalyse

- ItomiScan sendet beim Upload aus `itomiscan/integrations/delivery.py` bereits `Authorization: Token <Wert>` per HTTPS an `/api/documents/post_document/`.
- Die Zielverwaltung in `itomiscan/web/delivery_pages.py` bietet bislang nur ein Token-Passwortfeld, ohne Schritt-für-Schritt-Erklärung oder Verbindungstest.
- Antwort 403 wird lediglich als `Paperless HTTP 403` gemeldet; genaue Ursache ist damit **nicht bekannt**. Tokenberechtigung, Proxy oder CSRF-Konfiguration unterscheiden. Keine pauschale Aussage, der Token sei falsch.

## Weboberfläche und Anleitung

1. Im Paperless-Zieldialog eine gut verständliche kurze Anleitung direkt neben dem Eingabefeld:
   - In Paperless mit dem vorgesehenen Benutzer anmelden.
   - Unter **Mein Profil** einen API-Token erstellen/erneuern; alternativ Paperless-API `POST /api/token/` für technisch erfahrene Benutzer.
   - Für diesen Benutzer die erforderlichen Rechte zum Hinzufügen von Dokumenten sicherstellen.
   - Den **reinen Tokenwert** (ohne vorangestelltes `Token `) in ItomiScan eintragen.
   - HTTPS-**Basisadresse** (z. B. `https://paperless.example.de`, nicht `.../api/documents/post_document/`) konfigurieren.
   - Verschlüsselte Speicherung und niemals Anzeige des vollständigen gespeicherten Tokens; ein explizites Ersetzen und Löschen ermöglichen.
2. Ein **„Verbindung testen“**-Button für jedes gespeicherte Paperless-Ziel, mit sofortiger Ladeanzeige und nachvollziehbarem Abschluss. Keine PDF hochladen, keine neuen Dokumente oder Accounts erzeugen.
3. Testablauf: Server und Zertifikat/TLS validieren; ausschließlich sichere lesende Paperless-API-Operation (z. B. `GET /api/documents/?page_size=1` oder ein geeigneter aktueller nichtmutierender API-Endpunkt) mit `Authorization: Token <token>` nutzen. Authentifizierung, API-Erreichbarkeit und bereitstehende Rechte soweit möglich getrennt interpretieren. **Ein erfolgreicher GET-Test beweist nicht automatisch die Uploadberechtigung**; das muss die UI klar formulieren. Bei Bedarf eigener optionaler Test-Upload mit ausdrücklicher Bestätigung und erkennbaren Auswirkungen, nicht als Normaltest.
4. Ergebnis differenziert:
   - 200: „API erreichbar, Token für die geprüfte Abfrage akzeptiert“; Uploadrecht nicht ungeprüft behaupten.
   - 401: Authentifizierung abgelehnt, Token erneuern/eingeben.
   - 403: Zugriff verweigert. Nach Möglichkeit sicheren, begrenzten, redigierten Hinweis aus Paperless-Antwort extrahieren. Ursachen: Berechtigungen des Tokenbenutzers; Reverse-Proxy-/CSRF-Sperre; keine Ursache ohne Nachweis behaupten.
   - 404: Basisadresse/API-Pfad prüfen.
   - TLS-/DNS-/Timeout-/Netzwerkfehler getrennt und verständlich melden.
5. Fehlermeldungen geben konkreten nächsten Prüfschritt und zeigen die tatsächlich getestete (unbedenkliche) Ziel-URL, HTTP-Code und optional dokumentierte Fehlerklasse, **niemals Token, Passwörter, Sessioncookies oder ungefilterte Serverantworten**.
6. Bestehenden PDF-Versand nicht bei jedem Verbindungstest auslösen; Aufgabenqueue und Original-PDF unangetastet lassen.

## Authentifizierungsvarianten

- **API-Token als Standard**, da bereits von ItomiScan unterstützt.
- Optionale **OAuth/OIDC-Anmeldung** erst separat prüfen: Paperless-ngx dokumentiert Headless-OIDC-API mit django-allauth, aber Serverkonfiguration, Geräte-Flow-/Callback-Unterstützung, Token-Erneuerung, Rechte und sicherer Secretspeicher müssten vor Angebot implementiert und nachgewiesen sein. **Nicht** als bereits verfügbare oder überall kompatible Option darstellen.

## Dokumentation und Tests

- Fehlende/ungültige/abgelaufene Token, Nutzer ohne Uploadrecht, Paperless hinter Reverse Proxy, 401/403/404, TLS-Fehler, Timeout.
- Gültiger Token mit read-only-Rechten: Verbindungstest kann erfolgreich sein, Upload muss korrekt als nicht autorisiert gemeldet werden.
- Alle Statusanzeigen im bestehenden Design, Ladezustand und CSRF-Schutz für den Testaufruf (auch ohne Änderung am Ziel), keine Secrets in Logs oder Browserquelltext.
- Regression: Unveränderte bestehende Paperless-Ziele/Token und funktionierender Dokumentversand.

## Referenzen

- https://docs.paperless-ngx.com/api/
- https://github.com/paperless-ngx/paperless-ngx/blob/dev/docs/api.md

## Implementierungsstand 2026-10-18

Auf `develop/1.0.0` umgesetzt, aber noch **nicht auf dem N1800 getestet**:
- Paperless-Benutzername und Passwort als **einmaliger** Austausch gegen API-Token via HTTPS `POST /api/token/`; das Passwort wird nicht persistiert.
- Vorhandene manuelle Token-Eingabe bleibt bestehen.
- „Erweiterte Diagnose / Verbindung testen“ im gespeicherten Paperless-Ziel: HTTPS/Profil-Tokenprüfung, lesender Dokumenten-API-Check, Hinweise zu 401/403/404/429, TLS/Netzwerk/Timeout.
- Kein Testdokument und keine Änderung vorhandener Aufträge beim Verbindungstest.
- Bei Uploadfehlern präzisere HTTP-Meldungen mit Hinweis auf die erweiterte Diagnose.
- Automatisierte Tests unter `tests/test_paperless_diagnostics.py`. Hardware- und externe Paperless-Integrationstests stehen aus.

**Grenze:** Ohne tatsächlichen PDF-Test-Upload kann die Berechtigung zum Hinzufügen von Dokumenten nicht sicher bestätigt werden. Kein OAuth/OIDC-Login implementiert. Token-Login via Benutzername/Passwort setzt lokale Paperless-API-Zugangsdaten voraus.

## Block 5: Erweiterte Diagnose und Zielverwaltung (2026-10-19)

- Bestehende Paperless-Anmeldung mittels lokalem Benutzername/Passwort und Austausch gegen API-Token über HTTPS erhalten; Token auch weiterhin manuell hinterlegbar. Kein Passwort im Konfigurationsbackup.
- Lesende Diagnose prüft HTTPS-Basisadresse, authentifiziertes `GET /api/profile/`, `GET /api/documents/?page_size=1` sowie eine **nicht schreibende OPTIONS-Anfrage** an `/api/documents/post_document/`. Ergebnisse sind getrennt; fehlende Leseberechtigung bedeutet nicht automatisch fehlende Uploadberechtigung.
- **OPTIONS kann eine server-/proxyabhängige 403/405-Meldung liefern.** Auch bei 200/204 wird damit **keine tatsächliche Uploadberechtigung oder Archivierung bestätigt**. Kein Test-PDF wird erzeugt oder hochgeladen.
- Bedienung der Ziele in der Webadministration vereinfacht (gespeicherte Ziele, Ziel hinzufügen, Paperless-Hilfe zu 403, erweiterte technische Beispiele).
- HTTP 403 kann neben fehlender Dokumentberechtigung auch vom Reverse Proxy und in neueren Paperless-Konstellationen durch nicht richtig erkannte Trusted-Proxies bzw. Login-Ratelimits kommen. Die Diagnose nennt mögliche Ursachen, behauptet aber keine unbewiesene.
- LAN-Fundstellen über DNS-SD bleiben Vorschläge; sie werden **nur durch ausdrückliche Übernahme** gespeichert. Nicht angekündigte Paperless-Instanzen weiterhin manuell konfigurieren. Zertifikatsvalidierung bleibt aktiv.
- Automatisierte Tests ergänzen OPTIONS und 403; tatsächlicher Test mit dem Paperless des Benutzers, Reverse Proxy und N1800 steht noch aus. OAuth/OIDC weiterhin nicht implementiert.
