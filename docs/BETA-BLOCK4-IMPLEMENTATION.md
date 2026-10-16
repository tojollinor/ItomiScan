# ItomiScan Beta – Block 4 / 7: Webziele und Fernbedienung

Stand: 16.10.2026. Entwicklungszweig `develop/1.0.0`. Implementierungsbericht; **keine Hardwareabnahme, keine veröffentlichte Beta**.

## Änderungen

1. **Paperless-Zielvorschläge:** Optionales, zeitlich begrenztes DNS-SD/mDNS-Lesen über `avahi-browse` für Paperless-benannte HTTPS-Dienste im privaten LAN. Es findet kein Netzwerkscan ganzer Subnetze statt. Ohne Avahi oder ohne geeignete Ankündigung bleibt die Suche leer; die manuelle Eingabe bleibt möglich. Fundstellen sind Vorschläge, **keine verifizierten Paperless-Instanzen**. HTTPS-/Token-Schutz der tatsächlichen Zustellung bleibt bestehen.
2. **Druckererkennung:** Bereits vorhandenes CUPS-`lpinfo -v` bleibt Grundlage. Gefundene Adressen können jetzt direkt ins Drucker-Eingabefeld übernommen werden. Druckereignung und tatsächlicher Ausdruck weiterhin gesondert prüfen.
3. **Drucker pro Profil:** Gespeicherte Drucker stehen im Profil-Detaildialog als Dropdown bereit. Die Zuordnung liegt in der eigenen SQLite-Tabelle `profile_printers`. Der Kopierbildschirm bevorzugt diesen Drucker nur, wenn er in CUPS bereitsteht. Export/Import des Konfigurations-JSON bewahrt die Zuordnung anhand der Druckernamen; ältere Backups ohne Zuordnung bleiben gültig.
4. **Zielauswahl:** Zieltypabhängige Feldbeschriftung, Adressbeispiele und kurze Hinweise. Die bestehenden serverseitigen Zielvalidierungen werden nicht aufgeweicht.
5. **Browser-Fernbedienung:** Authentifizierte Webansicht `/remote` mit Scanprofilwahl, Scanstart, Öffnen der Scanansicht, Rückkehr zur Startseite, Neustart und Herunterfahren. Webaktionen werden durch Session, Host-/Origin- und CSRF-Prüfung geschützt. Ein lokaler Kiosk-Kommandoempfänger holt höchstens kurzlebige, explizit erlaubte Aufträge aus SQLite. PIN-Rechte sowie Scan-/Dokumentsperren gelten zusätzlich. Beim Systemstart werden ausschließlich die vorhandenen eng begrenzten `sudo -n systemctl reboot/poweroff`-Rechte verwendet; keine pauschale Root-Freigabe des Webdienstes. Ein übergebener/angenommener Befehl ist noch **kein bestätigter erfolgreicher Scan, Neustart oder Ausdruck**.
6. **Befehlsstatus:** Die letzte Aktion wird im Webbrowser dargestellt. Unbekannte Befehle und zeitlich abgelaufene Aufträge werden zurückgewiesen. Die Browseransicht aktualisiert ihren Auftragsstatus, solange sie sichtbar ist.

## Grenzen und offen

- Der Browser ist eine **native Steueransicht**, **kein Live-Desktop-Mirroring**. Eine gesicherte Vorschau der Scandokumente im Browser ist derzeit noch nicht implementiert.
- Paperless-DNS-SD ist nur Best-Effort. Nicht angekündigte Instanzen müssen manuell konfiguriert werden.
- Fernbedienung benötigt Web- und Kiosk-Prozess mit gemeinsamem SQLite-Pfad und geeignete lokale Rechte; Reboot/Poweroff erfordern vorhandene eingeschränkte sudoers-Einrichtung. Nicht automatisch auf dem Gerät aktiviert.
- Browser-, Scanner-, Touch-, Sicherheits- und Netzwerk-Praxistests am echten N1800 stehen aus.
- **Keine** Änderung an `main`, Stable, lokalen GRUB-Einträgen oder der laufenden N1800-Installation durch diese GitHub-Commits.

## Testkriterien

- Python- und Shell-Syntax, Regression, Web-Auth/CSRF, neue Queue- und Backup-Tests in GitHub Actions prüfen.
- Im LAN: Zielnamen und Hinweise, optionale Paperless-Erkennung, manuelle Adresse, Druckerübernahme und CUPS-Zuordnung testen.
- Fernsteuerung: gültige/ungültige Sitzung, CSRF, lokale PIN-Berechtigung, belegter Scanner, Dokumentenprüfung, wiederholte Anforderungen, Neustart/Poweroff nur mit bestätigter Ausführung unter physischem Zugriff.
- Auf dem N1800: begrenzten Ressourcenverbrauch, zuverlässigen Neustart, Scan-Ergebnis und lokale Wiederherstellung kontrollieren.

Der abschließende Beta-Release ist weiterhin **Block 7 von 7** und erfordert tatsächlich nachgewiesene Tests und eine gesonderte Veröffentlichung.
