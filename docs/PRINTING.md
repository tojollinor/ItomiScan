# ItomiScan: CUPS-Netzwerkdrucker und Kopieren (Block 7/8)

**Stand 14.10.2026:** Entwicklungszweig `develop/1.0.0`. Code umgesetzt, automatisierte Tests vorhanden. **Nicht auf dem Fujitsu N1800 installiert oder mit echten Druckern getestet**. Stabiler Zweig `main` unverändert.

## Prinzip

- ItomiScan verwendet den vorhandenen CUPS-Druckdienst und dessen Kommandozeilenwerkzeuge `lpstat`, `lpadmin` und `lp`. Keine pycups-Abhängigkeit, kein eigener komplexer Druckserver.
- Drucker benötigen **IPP Everywhere** (treiberlos; `ipp://` oder `ipps://`). Es werden keine Druckertreiber aus externen Quellen heruntergeladen, kein automatisches Drucker-Discovery-Scanning im LAN und kein CUPS-Port nach außen geöffnet.
- Der passwortgeschützte Webbereich **Drucker** erlaubt das Eintragen von IPP-Netzwerkadressen, die explizite Registrierung als CUPS-Queue, die Ausgabe einer Testseite sowie das Entfernen einer CUPS-Queue. Status beruht auf der lokalen CUPS-Konfiguration, **nicht** auf einer verifizierten Papierausgabe.
- Die Druckereinrichtung benötigt lokal ausreichende CUPS-Rechte. Das manuelle Einrichtungs-Skript nimmt den normalen Scannerbenutzer bewusst in die Gruppe `lpadmin` auf. **Sicherheitsfolge:** Der Benutzer darf damit CUPS-Druckwarteschlangen verwalten; dies ist keine allgemeine Root-Berechtigung, aber ein zusätzliches Privileg. Nur nach ausdrücklicher Freigabe ausführen.

## Kopieransicht am Original-Touchdisplay

Die bisherige Startseiten-Kachel **Kopieren** öffnet einen eigenen, großen Tkinter-Bildschirm ohne Browser, Bildschirmtastatur oder Fremd-Assets. Darin werden alle in ItomiScan gespeicherten Netzwerkdrucker angezeigt, aber nur **tatsächlich in CUPS vorhandene** Queues sind wählbar.

Bedienelemente: Drucker auswählen, Kopienzahl **1 bis 20** mit großen +/−-Tasten, Vorlageneinzug **ADF Front** oder **ADF Duplex**, Ausdruck **einseitig**, **Duplex lange Kante** oder **Duplex kurze Kante**, Button **Scannen & drucken** und **Zurück**. Bei fehlendem Drucker wird der Druckstart deaktiviert. Die physische Scantaste startet im geöffneten Kopiermodus die gewählte Kopie, ansonsten weiterhin den bisherigen Scan.

Die lokale Scannerberechtigung `scan` und die Berechtigung `copy` sind unterschiedlich. Ein Benutzer mit ausschließlich `copy` darf kopieren, jedoch keine eigenständige lokale Scanaktion ausführen. Die PIN-Verwaltung muss die Funktion `copy` ausdrücklich freigeben; die Berechtigung wird vor Scanbeginn erneut in SQLite geprüft.

## Ablauf und Auftragsgarantie

1. Im Kopiermodus den lokalen CUPS-Drucker und die Kopieroptionen auswählen. Vor dem Scannen werden Printer-Name, SANE-Einzug und erlaubte Druckparameter validiert.
2. Die **bestehende Scanengine** erzeugt eine PDF unter `~/Scans/.../Dokument.pdf`. Ein persönliches PNG-Scanprofil wird für die Kopie nur vorübergehend auf PDF-Ausgabe umgestellt, die gespeicherten Profile werden nicht verändert. Das vorhandene schnelle JPEG→img2pdf-Verfahren bleibt bestehen.
3. Kopienzahl und Duplexoption werden zusammen mit der unveränderten PDF als SQLite-Job und SHA-256-gesicherte Spooldatei persistiert. Bestehende Block-6-Jobs werden durch eine schonende Datenbankmigration erhalten; neue Druckspalten erhalten Standardwerte.
4. Der separat gestartete Zustelldienst nimmt Druckaufträge auf und ruft `lp -d <name> -n <kopien> -o sides=<modus> <pdf>` als Argumentliste auf, ohne Shellausführung. Erfolgreiche CUPS-Bestätigung bedeutet **Auftrag in CUPS angenommen**, noch **nicht** Papierausgabe bestätigt.
5. Ein unklarer oder unterbrochener Druckvorgang wird mit Status **Prüfen** abgelegt. Er wird nicht automatisch erneut gedruckt. Die Webadministration kann nach Kontrolle der CUPS-Aufträge eine bewusste Wiederholung auslösen. Der PDF-Originalscan und die Spooldatei bleiben erhalten.

**Grenzen:** Papiermangel, Drucker-Stau, exakte Papierausgabe, Duplexreihenfolge, Scan-/Kopiergeschwindigkeit, CUPS-Autokonvertierung, Drucker-LAN-Erreichbarkeit sowie Verhalten auf Atom N270/1 GiB sind am Gerät noch zu prüfen. Die Kopieransicht zeigt bis zu sechs Drucker gleichzeitig; für weitere Drucker gibt es eine einfache Seitennavigation mit großen Pfeilen. Eine Druckerwarteschlange muss existieren, bevor kopiert werden kann.

## Vorbereitung erst nach ausdrücklicher Deployment-Freigabe

Auf dem Scanner mit freigegebener ItomiScan-Entwicklungs-/Releasefassung, als root:

```bash
cd /home/SCANNERBENUTZER/ItomiScan
bash setup-printing.sh SCANNERBENUTZER
```

`SCANNERBENUTZER` ersetzen. Das Setup installiert auf Debian mit apt die Pakete `cups`, `cups-client`, `cups-filters`, startet den lokalen CUPS-Dienst, deaktiviert dessen Remote-Administration und nimmt den normalen Scannerbenutzer in `lpadmin` auf. Ein laufender ItomiScan-Webdienst wird für die neue Gruppenzugehörigkeit neu gestartet. Kein vorhandener Drucker wird automatisch registriert oder bedruckt.

Danach in der Webadministration unter **Drucker** zum Beispiel `OfficeLaser` mit `ipps://drucker.lan/ipp/print` anlegen, **In CUPS einrichten** anklicken und optional **Testseite drucken**. Falls der Drucker IPP Everywhere nicht unterstützt oder die URI nicht stimmt, Fehler zunächst anhand der tatsächlichen CUPS-Queue und des Druckerhandbuchs prüfen.

Die bestehende CUPS-Installation kann bei Bedarf manuell geprüft werden:

```bash
lpstat -e
lpstat -p
systemctl status cups
```

Der Zustell-Worker aus Block 6 (`itomiscan-delivery.service`) muss zur automatischen Ausführung der wartenden Druckjobs ebenfalls bewusst eingerichtet und aktiviert werden. **Der bestehende Scanner auf `main` wird durch diese Skripte nicht automatisch verändert.**

## Tests und Release

GitHub Actions prüft Python- und Shell-Syntax, die CUPS-Kommandos mit Mocks, ungültige Queue-/IPP-Daten, Kopienzahl und Duplex, Verhalten bei nicht installierten Queues, Zustellunterbrechung/Neustart (Status `review`), SQLite-Migration, PIN-Rechte einschließlich Copy-only-Konto, Fronttastenrouting sowie CSRF-geschützte Druckerverwaltung im Browser.

Ein echter IPP-Drucker und das Fujitsu-N1800-Touchdisplay sind noch nicht praktisch getestet. Block 8/8 umfasst Integrationstests, RAM- und Fehlerverhalten, Spool- und Konfigurationsbackup samt Rollback, aktualisierten Installer und 1.0.0-Release **nur nach ausdrücklicher Endfreigabe**.

## Block 8: Übergabe und Abnahme

Auch CUPS-Aufträge befinden sich in der vollständigen Sicherung. Ein als `done` markierter Job bedeutet nur CUPS-Annahme. Bei unklarem Status `review` muss vor einer erneuten Ausgabe überprüft werden, ob schon gedruckt wurde. Netzwerkeinrichtung, echter Ausdruck und Duplex-Reihenfolge müssen am Gerät geprüft werden. Release-Gates: `docs/RELEASE-READINESS-1.0.0.md`.
