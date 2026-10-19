# ItomiScan: Beta-Update und Wiederherstellung

Status: Auf dem Entwicklungsbranch implementiert. Praktische Hardwareabnahme am N1800 steht aus.

## Einmalige Einrichtung

Die bereits veröffentlichte Beta 3 kann Updates nur erkennen. Sie enthält noch keinen privilegierten Installationshelfer. Deshalb muss **Beta 4 (v1.0.0-beta.4) einmalig manuell** über das bestehende install-beta.sh und SSH eingespielt werden. Der feste Tag, die Vorprüfungen und der Rückfallweg stehen in [BETA4-INSTALL.md](BETA4-INSTALL.md). Dabei installiert setup-updater.sh den root-eigenen Helfer unter /usr/local/libexec/itomiscan-beta-updater, legt die geschützte Konfiguration unter /etc/itomiscan/updater.json an und gewährt dem Scannerbenutzer ausschließlich die sudo-Aufrufe für install und rollback. Keine allgemeine Root-Shell.

## Bedienung

1. Menü Updates öffnen (Berechtigung update ist nötig, falls PIN-Konten aktiv sind).
2. Auf Updates prüfen. Die Beta-Suche wertet nur veröffentlichte Prereleases des offiziellen GitHub-Repositories aus. Stable wird nur angezeigt, nicht automatisch installiert.
3. Bei neuer Beta Beta installieren wählen und bestätigen.
4. Der Helfer löst das offizielle Beta-Tag zu einem Commit auf, lädt dessen Git-Tree und prüft jede Archivdatei gegen ihren Git-Blob-Hash. Unbekannte Dateien, Links oder Dateipfade mit Traversal werden abgewiesen.
5. Eine getrennte Sicherung des bisherigen Programmverzeichnisses wird unter /var/lib/itomiscan-updater erstellt. Nach Syntax- und Importprüfungen erfolgt der Austausch über Umbenennungen auf demselben Dateisystem; ein Fehler führt zur sofortigen Wiederherstellung der bisherigen Programmdateien.
6. Bei Erfolg meldet der Dialog, dass ein Neustart zur Aktivierung nötig ist. Der Neustart benötigt eine separate Bestätigung und die Berechtigung shutdown.

Fehlen bei einem verifizierten VNC-Release die festen Debian-Pakete x11vnc oder novnc, werden nur diese Pakete vor dem Austausch nachinstalliert. Fehler dabei brechen das Update ab.

## Rückkehr zur letzten Sicherung

Über Letztes Update rückgängig machen in der Update-Oberfläche oder, falls die GUI nicht mehr startet, über SSH mit dem Scannerbenutzer:

    sudo -n /usr/local/libexec/itomiscan-beta-updater rollback

Anschließend kontrolliert neu starten. Die Sicherung enthält das bisherige Programmverzeichnis. Scan- und Konfigurationsdaten unter dem externen Benutzer-Konfigurationsverzeichnis werden weder beim Update noch beim Code-Rollback überschrieben. Bei späteren Datenbankschemaänderungen kann eine separate Kompatibilitätsprüfung nötig sein.

Eine Stromunterbrechung im kurzen Zeitraum zwischen Umbenennungen kann eine manuelle Rettung per SSH erforderlich machen. Vollautomatische Wiederherstellung nach Stromausfall wird nicht behauptet.

## Hardwareabnahme

Der echte N1800 wurde nicht mit diesem Updater getestet. Zu prüfen sind: installierte Version, freier Speicher, GitHub-Zugriff, Downgrade-Schutz, vorhandene Datensicherung, Installationsfortschritt, vollständiger Neustart, Webservice und Kiosk, VNC-Fernsteuerung, CPU-/RAM-Verbrauch sowie gezielte manuelle Wiederherstellung. GitHub-CI und simulierte Rollback-Tests ersetzen diese Prüfungen nicht.

## Integrations-Nachprüfung (Block 5)

Die Softwaretests prüfen zusätzlich WebSocket-Anmeldung, Herkunftsprüfung, VNC-Bytestrom und den lokal gebundenen VNC-Prozess. Der Rollback-Helfer verwendet bei gescheiterter Installation einen zufällig benannten Quarantänepfad. Dadurch kann ein bereits vorhandener Pfad `ItomiScan.updater-failed` die Wiederherstellung nicht verhindern oder fremde Daten löschen. Nach erfolgreicher Installation führt ein nichtkritischer Fehler bei der Bereinigung des alten Austauschverzeichnisses nicht mehr zu einem Rollback; eine manuelle SSH-Bereinigung kann dann nötig bleiben. Hardware- und Stromausfalltests stehen weiterhin aus.

## Vorwärtsvergleich bei unbekanntem lokalen Release-Tag

Ist nur die installierte Commit-ID bekannt, erlaubt der Helfer ein automatisches Update ausschließlich, wenn die GitHub-Compare-API den Ziel-Commit als Nachfolger des installierten Commits bestätigt (Status `ahead`). Ältere, abweichende oder unklare Commits werden nicht überschrieben. Dasselbe Schutzkriterium verwendet die Benutzeroberfläche beim Anzeigen des Installationsbuttons. Damit kann eine manuell installierte Entwicklungsversion nicht unbeabsichtigt durch die ältere Beta 3 ersetzt werden.
