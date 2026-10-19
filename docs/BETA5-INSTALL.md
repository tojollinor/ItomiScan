# ItomiScan v1.0.0 Beta 5: Update über die Webadministration

**Hardwareabnahme ausstehend.** Die Veröffentlichung ist ein GitHub-Prerelease,
kein Stable-Release. Diese Anleitung führt keine Befehle automatisch aus.

## 1. Vor dem Update

- Scanner und ausstehende Zustellungen im Wartungsfenster anhalten.
- Gesonderte Sicherung von Konfiguration, Datenbank, Scan-Dateien und Programm
  anfertigen, lesbar prüfen und Rollback-Möglichkeit sicherstellen.
- In der ItomiScan-Webadministration unter Updates die neue Beta suchen.
- Freigegebenes Prerelease `v1.0.0-beta.5` auswählen und Installation ausdrücklich
  bestätigen. Der vorhandene eingeschränkte Beta-Updater prüft GitHub-Release,
  Commit und Archivdateien, sichert die vorige Programmversion und installiert
  die neue Beta. Neustart erst nach Erfolg und in einem Wartungsfenster durchführen.

## 2. Einmalige systemd-Migration auf bereits installierter Beta 4

**Wichtig:** Die Web-Update-Hilfe aktualisiert *nur Programmdateien* und lässt
bestehende systemd-Units absichtlich unverändert. Auf Geräten mit
`PrivateTmp=yes` bleibt `/tmp/.X11-unix/X0` im Webserver-Mount-Namespace
verborgen. Die X11-Fernsteuerung kann daher trotz Programmupdate scheitern.

Nach erfolgreichem Web-Update diese gesonderte, **ausdrücklich autorisierte**
Migration über eine Root-SSH-Sitzung ausführen:

```sh
bash -n /home/administrator/ItomiScan/migrate-vnc-service-beta5.sh
bash /home/administrator/ItomiScan/migrate-vnc-service-beta5.sh
systemctl cat itomiscan-web.service
systemctl show itomiscan-web.service -p PrivateTmp
```

Das Skript prüft die bestehende ItomiScan-Unit und legt ausschließlich die
systemd-Override-Datei
`/etc/systemd/system/itomiscan-web.service.d/20-kiosk-x11.conf` mit
`PrivateTmp=no` an. Das verringert gezielt die temporäre Dateisystem-Isolation
des Webdienstes; alle anderen vorhandenen systemd-Schutzmaßnahmen bleiben
erhalten. Keine zusätzlichen LAN-/VNC-Ports werden geöffnet.

Nur bei geplanter Unterbrechung und ohne aktive Fernwartung:

```sh
systemctl restart itomiscan-web.service
systemctl is-active itomiscan-web.service
journalctl -u itomiscan-web.service -n 45 --no-pager
```

Diese gesonderte Systemmigration ist **nicht Teil des atomaren Programm-Rollbacks**.
Beim Rollback auf Beta 4 bleibt das Override bestehen. Ein Zurücksetzen sollte nur
nach einer ausdrücklichen Sicherheits- und Funktionsprüfung erfolgen. Wer diese
Migration nicht akzeptiert, sollte die Fernsteuerung zunächst ausgeschaltet lassen.

## 3. Prüfen

- Webanmeldung und Liveansicht starten; prüfen, ob VNC tatsächlich Bild und Eingabe
  überträgt. Eine geladene HTML-Seite allein ist kein Funktionstest.
- Die Verbindung beenden und sicherstellen, dass der VNC-Prozess endet und nur
  Loopback verwendet wird.
- Während eines Kaltstarts überprüfen, ob der Webserver nach später DHCP-Adresse
  startet und der fünfminütige CPU-/RAM-Verlauf bereits Werte enthält.
- Datenträgerbelegung einmalig dargestellt, kein zweiter Belegungswert.
- Update-/Rollback-Tests sowie Scanner-/ADF-/Duplex-/PDF-/Druckfunktionen nur auf
  dem echten ScanSnap N1800 abschließend abnehmen.

**Hardwareabnahme ausstehend.**
