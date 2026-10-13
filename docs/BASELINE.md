# ItomiScan 1.0.0: geschützter Ausgangsstand

Stand: 13.10.2026. Status: **Bestandsaufnahme, keine neue Geräteinstallation**.

- Repository: `tojollinor/ItomiScan`.
- `main`: bestehender Update-Kanal des N1800, in Block 1 unverändert.
- Gesicherter Referenz-Commit: `91a1d80a5d4a7dae7624bc0c04babd832fb44b27`.
- Sicherungszweig: `backup/prototype-2026-10-13` (zunächst genau dieser Commit).
- Entwicklungszweig: `develop/1.0.0`; neue Funktionen ausschließlich hier entwickeln, bis geprüft und ausdrücklich zur Übernahme freigegeben.
- Wiederherstellung des Quellstands: Dateien/Commits aus dem Sicherungszweig bzw. aus dem genannten Commit übernehmen. **Nicht** blind den installierten Geräte-Branch zurücksetzen; laufende Scanaufträge und lokale Änderungen zuerst prüfen.
- Der bestehende ItomiScan-Update-Button bezieht Updates von `origin/main`, nicht von `develop/1.0.0`.

Bereits am echten Scanner bestätigt: Vollbild 1024×768, deutlich schnellere PDF-Erstellung, GitHub-Update und physische Enter/Scan-Taste. Weiterhin nicht bestätigt: tatsächliches Ausschalten über den neuen Button; ADF-Duplex-Reihenfolge, Touch-Kalibrierung und Spezialfälle.

Der Stand ist kein eigenes GitHub-Release und kein auf dem Gerät erstelltes Systemabbild. Für ein echtes Geräte-/OS-Backup sind später SSD-/Systemabbild und Konfigurationssicherung separat zu planen.
