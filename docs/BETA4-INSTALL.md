# ItomiScan v1.0.0 Beta 4: SSH-Bootstrap, Kontrolle und Rollback

**Hardwareabnahme ausstehend.** Beta 4 ist ein GitHub-Prerelease für den Fujitsu ScanSnap N1800 mit Debian 12 i386. Dieses Dokument installiert nichts automatisch. Bestehende Beta-3-Installationen können den ersten Umstieg nicht per Update-Button durchführen, weil der privilegierte neue Update-Helfer dort fehlt.

## 1. Vorher absichern

Die Erstinstallation muss bewusst im Wartungsfenster auf dem Scanner erfolgen. Voraussetzungen:

- Debian 12 Bookworm i386, funktionierender Root-SSH-Zugang sowie physischer Zugriff im Fehlerfall.
- Keine aktiven Scans, ungeklärten Zustellungen, sendenden Aufträge oder noch ausstehenden Druckvorgänge.
- Mindestens 600 MiB freier SSD-Platz und zusätzlicher Platz für verifizierte Datensicherungen. Freien Platz zuvor mit df -h prüfen.
- Separate Sicherung von /home/administrator/ItomiScan, /home/administrator/.config/itomiscan (SQLite, Tokens, TLS/Secrets, Spool), /home/administrator/Scans und weiteren tatsächlich genutzten Datenpfaden. Backups nur geschützt aufbewahren und ihre Lesbarkeit/Integrität überprüfen.
- Vorherige Version und Backup-Ort notieren. Den Stand von Webadministration, Scanprofilen und offenen Zustellaufträgen protokollieren.

Der Beta-Installer sichert die vorherigen Programmdateien, erstellt aber **kein vollständiges eigenständiges Datenbackup**. Eine Vollsicherung ist deshalb eine zwingende Vorbedingung.

## 2. Einmalige Installation von Beta 4 per SSH

Die folgenden Befehle in einer bewusst gestarteten Root-SSH-Sitzung auf dem N1800 ausführen, nicht automatisch per Web-Button. Der Download ist auf den unveränderlichen GitHub-Tag v1.0.0-beta.4 begrenzt:

    curl -fL --retry 2 \
      https://raw.githubusercontent.com/tojollinor/ItomiScan/v1.0.0-beta.4/install-beta.sh \
      -o /root/itomiscan-beta4-install.sh
    bash -n /root/itomiscan-beta4-install.sh
    bash /root/itomiscan-beta4-install.sh --user administrator --ref v1.0.0-beta.4

Die Skriptausführung kann Debian-Pakete einschließlich x11vnc und novnc installieren, das vorhandene Programm aktualisieren, den root-eigenen Helfer über setup-updater.sh einrichten und Web-/Zustelldienste neu starten. Er verändert **nicht** GRUB, Kernelwahl, Plymouth oder Initramfs. Ein automatischer Neustart ist nicht vorgesehen. Das Installationsprotokoll liegt unter /var/log/itomiscan-install.log.

Der erste Installer kann bei Bedarf einen Programmsicherungsordner im Home-Verzeichnis des Scannerbenutzers mit dem Namen ItomiScan-backup-<Zeitstempel>-<Zufall> anlegen. Er ist **nicht** identisch mit den späteren, vom Update-Helfer verwalteten Sicherungen.

## 3. Danach Versions-, Rechte- und Dienststatus prüfen

Zunächst nur lesend:

    cat /home/administrator/ItomiScan/.itomiscan-beta-tag
    cat /home/administrator/ItomiScan/.itomiscan-beta-commit
    test -x /usr/local/libexec/itomiscan-beta-updater && echo "Updater vorhanden"
    sudo -u administrator sudo -n -l
    systemctl is-active itomiscan-web.service itomiscan-delivery.service
    journalctl -u itomiscan-web.service -n 40 --no-pager

Die Versionsdatei muss v1.0.0-beta.4 melden, die Commit-ID mit dem offiziellen GitHub-Tag übereinstimmen. Nach Prüfung des Erfolgs den Kiosk kontrolliert neu starten und die grundlegende Funktion des Scanners bestätigen. Wenn die Installation abbricht, nicht blind erneut installieren, sondern zuvor Log, Backups, Datenstatus und laufende Dienste prüfen.

## 4. Nachfolgende Betas über die Bildschirmoberfläche

Erst nach dem Bootstrap kann der Scanner im Bereich Updates veröffentlichte neue Beta-Tags prüfen und nach ausdrücklicher Bestätigung installieren. Der root-eigene Helfer erlaubt ausschließlich install und rollback, prüft den offiziellen Release-Commit und jede Datei gegen ihren Git-Blob-Hash, zeigt Status und Fortschritt, erstellt eine Programmsicherung und verlangt anschließend einen getrennten Neustart.

Die Installation einer älteren Beta als des vorhandenen Standes ist bewusst gesperrt. Eine nur als Entwicklungskopie identifizierte Installation ohne gültigen Release-Tag darf ein Web-Update nur ausführen, wenn GitHub die Zielversion als nachweislichen Nachfolger bestätigt.

## 5. Wiederherstellung

**Bei Fehlern des allerersten Bootstrap von Beta 3 auf Beta 4:** Der SSH-Installer legt eine eigene Programmsicherung ItomiScan-backup-* an. Dafür ist der integrierte Helferbefehl rollback noch nicht automatisch mit einem Sicherungsverweis eingerichtet. Dienste kontrolliert stoppen, die Sicherung eindeutig identifizieren und Programmdateien erst nach verifizierter Datensicherung unter Root-SSH-Zugriff zurücksetzen. Die richtige Wiederherstellung hängt vom tatsächlich vorgefundenen Zustand ab, besonders bei offenen Zustelljobs.

**Bei einem späteren Web-Update:** Die Oberfläche enthält den Button Letztes Update rückgängig machen. Falls die Oberfläche nicht mehr startet, kann der registrierte Scannerbenutzer bei vorhandener Update-Helfersicherung den folgenden eingeschränkten Befehl per SSH ausführen:

    sudo -n /usr/local/libexec/itomiscan-beta-updater rollback

Danach kontrolliert neu starten. Der Programm-Rollback setzt keine außerhalb des Programmordners liegenden Konfigurations-, Scan-, Zertifikats- oder Spooldaten zurück. Datenbankschemaänderungen müssen gesondert bewertet werden. Bei einem Stromausfall in der kurzen Umschaltphase kann ein manueller Rettungseingriff nötig sein.

## 6. Hardwareabnahme ausstehend

Nach der manuellen Installation am echten N1800 gesondert prüfen:

1. noVNC-Livebild im bestehenden HTTPS-Webadmin, Maus/Touch/Tastatur, Wiederherstellen, Berechtigungsschutz und Sitzungsablauf.
2. CPU-, RAM- und Netzwerkbelastung während der VNC-Sitzung und außerhalb davon.
3. CPU-/RAM-Verlauf nach fünf Minuten ohne Browser, Wiederöffnen der Seite, Tabwechsel und Datenträgerbelegung.
4. Benutzer-Update auf eine spätere Beta, Wiederherstellung und Neustart in einem sicheren Testfenster.
5. SANE/ADF/Duplex/PDF-Vorschau, PIN-Kiosk, Scantaste, Zustellung/Paperless, Drucken, Systemstart und vorhandenes Boot-Design.

**GitHub-CI und Beta-Release gelten nicht als physische Geräteabnahme oder Stable-Freigabe.**
