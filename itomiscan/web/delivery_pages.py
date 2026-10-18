"""Delivery target setup and durable spool administration (password-protected)."""
from itomiscan.web.pages import e, layout, options, token, detail_dialog


HELP = {
    "paperless": "https://paperless.lan (TLS ist Pflicht)",
    "network": "smb://server/freigabe/ordner",
    "email": "smtp://server:587/empfaenger@example.org (STARTTLS) oder smtps://server:465/...",
    "usb": "usb://DATENTRAEGER/ordner (Datenträger muss eingehängt sein)",
    "printer": "ipp://drucker/ipp/print (Drucken folgt in Block 7)",
}
LABELS = {"paperless": "Paperless", "network": "SMB-Netzwerkordner",
          "email": "E-Mail", "usb": "USB-Datenträger", "printer": "Drucker"}


def targets_page(targets, csrf, configured, notice="", *, discovered=None, searched=False):
    body = ('<h1>Dokumentenziele</h1><p>Paperless, SMB-Netzwerkordner, '
            'E-Mail und USB sind als Zustellziele vorbereitet. '
            'Für den tatsächlichen Versand muss der separate '
            'ItomiScan-Zustelldienst gestartet sein. '
            'Drucker werden im separaten Menü eingerichtet.</p>'
            '<section class="entry-list">')
    for index, entry in enumerate(targets):
        kind, tid = entry["kind"], entry["id"]
        description = ("Nicht eingerichtet" if not configured.get(tid)
                       else "Zugangsdaten gespeichert (werden nicht angezeigt)")
        detail = ('<article class="card"><h2>' + e(entry["name"]) + '</h2>'
                 '<p>' + e(LABELS.get(kind, kind)) + '<br>' +
                 e(entry["address"]) + '</p>')
        if kind in ("paperless", "email", "network"):
            detail += ('<p class="muted">' + description + '</p>'
                     '<form method="post" action="/targets/secrets">' + token(csrf)
                     + '<input type="hidden" name="target_id" value="' + e(tid) + '">'
                     + ('<label>Paperless API-Token</label><input type="password" '
                        'name="token" maxlength="400" autocomplete="new-password">'
                        if kind == "paperless" else
                        '<label>Benutzername (optional)</label><input name="username" '
                        'maxlength="400" autocomplete="off">'
                        '<label>Passwort</label><input type="password" name="password" '
                        'maxlength="400" autocomplete="new-password">'))
            if kind == "email":
                detail += ('<label>Absenderadresse</label><input name="sender" '
                         'maxlength="400" type="email">')
            detail += ('<p>Leere Felder behalten vorhandene Werte. '
                     'Zugangsdaten werden getrennt von Konfigurationsbackups gespeichert.</p>'
                     '<button>Zugangsdaten speichern</button></form>'
                     '<form method="post" action="/targets/secrets">' + token(csrf)
                     + '<input type="hidden" name="target_id" value="' + e(tid) + '">'
                     '<input type="hidden" name="clear" value="yes">'
                     '<button class="danger">Zugangsdaten entfernen</button></form>')
        if kind == "paperless":
            detail += (
                '<section class="card"><h3>Paperless-Anmeldung</h3>'
                '<p>Einmal mit Paperless-Benutzername und Passwort anmelden. '
                'ItomiScan tauscht die Zugangsdaten über HTTPS gegen einen API-Token '
                'aus und speichert nur diesen Token.</p>'
                '<form method="post" action="/targets/paperless/login">' + token(csrf)
                + '<input type="hidden" name="target_id" value="' + e(tid) + '">'
                '<label>Paperless-Benutzername</label>'
                '<input name="username" autocomplete="username" required maxlength="200">'
                '<label>Paperless-Passwort</label>'
                '<input type="password" name="password" autocomplete="new-password" '
                'required maxlength="400">'
                '<button>Mit Paperless anmelden</button></form>'
                '<details><summary>Hilfe zur Token-Einrichtung</summary>'
                '<p>In Paperless unter „Mein Profil“ einen API-Token erstellen '
                'oder erneuern. Nur den Tokenwert ohne vorangestelltes „Token “ '
                'eingeben. Der Benutzer benötigt für Uploads die Berechtigung '
                '„Dokumente hinzufügen“. Als Zieladresse die HTTPS-Basisadresse '
                'ohne /api/documents/post_document/ verwenden.</p></details>'
                '<form method="post" action="/targets/paperless/test">' + token(csrf)
                + '<input type="hidden" name="target_id" value="' + e(tid) + '">'
                '<button class="secondary">Erweiterte Diagnose / Verbindung testen</button>'
                '</form></section>')
        detail += ('<form method="post" action="/targets/delete">' + token(csrf)
                 + '<input type="hidden" name="id" value="' + e(tid) + '">'
                 '<button class="danger">Ziel entfernen</button></form></article>')
        body += detail_dialog(f'target-{index}', entry["name"],
                              LABELS.get(kind, kind) + ' · ' + entry["address"], detail)
    body += ('</section><section class="card" style="margin-top:16px">'
             '<h2>Ziel hinzufügen</h2><p>Bitte Zieltyp auswählen und passende Felder ausfüllen. '
             'Das Ziel wird zunächst ohne Zugangsdaten gespeichert.</p>'
             '<form method="post" action="/targets/save" id="new-target-form">'
             + token(csrf)
             + '<label for="target-kind">Art des Ziels</label>'
             '<select id="target-kind" name="kind">'
             + options(("paperless", "network", "email", "usb", "printer"), "paperless")
             + '</select>'
             '<label for="target-name">Anzeigename</label>'
             '<input id="target-name" name="name" maxlength="60" required>'
             '<div data-target-section="paperless">'
             '<label>Paperless-Server (HTTPS)</label>'
             '<input name="paperless_url" type="url" maxlength="350" '
             'placeholder="https://paperless.example.lan">'
             '<p class="status-note">Verschlüsselte Basisadresse. API-Token später im Ziel hinterlegen.</p></div>'
             '<div data-target-section="network" hidden>'
             '<label>SMB-Server / IP-Adresse</label>'
             '<input name="network_host" maxlength="253" placeholder="nas.lan">'
             '<label>Freigabename</label>'
             '<input name="network_share" maxlength="64" placeholder="Scans">'
             '<label>Unterordner (optional)</label>'
             '<input name="network_directory" maxlength="200" placeholder="Buchhaltung/2026">'
             '<p class="status-note">Benutzername und Passwort nach dem Speichern separat eingeben.</p></div>'
             '<div data-target-section="email" hidden>'
             '<label>SMTP-Sicherheit</label>'
             '<select name="email_security"><option value="starttls">STARTTLS (Port 587)</option>'
             '<option value="smtps">SMTPS (Port 465)</option></select>'
             '<label>SMTP-Server</label>'
             '<input name="email_host" maxlength="253" placeholder="smtp.example.de">'
             '<label>SMTP-Port (optional)</label>'
             '<input name="email_port" type="number" min="1" max="65535" placeholder="587">'
             '<label>Empfängeradresse</label>'
             '<input name="email_recipient" type="email" maxlength="254" placeholder="archiv@example.de">'
             '<p class="status-note">SMTP-Absender und Anmeldedaten nach dem Speichern im Ziel hinterlegen.</p></div>'
             '<div data-target-section="usb" hidden>'
             '<label>Name des eingehängten USB-Datenträgers</label>'
             '<input name="usb_volume" maxlength="64" placeholder="SCANSTICK">'
             '<label>Unterordner (optional)</label>'
             '<input name="usb_directory" maxlength="200" placeholder="Eingang/2026">'
             '<p class="status-note">Keine Laufwerksbuchstaben; nur tatsächlich eingehängte Datenträger.</p></div>'
             '<div data-target-section="printer" hidden>'
             '<p>Drucker möglichst unter <a href="/printers">Drucker</a> einrichten.</p></div>'
             '<details><summary>Erweiterte Eingabe: vollständige Zieladresse</summary>'
             '<label id="target-address-label">Vollständige Zieladresse (optional)</label>'
             '<input name="address" list="paperless-candidates" maxlength="350">'
             '<p id="target-address-help" class="status-note">Überschreibt die Einzelfelder, falls ausgefüllt. '
             'Keine Zugangsdaten in dieser Adresse hinterlegen.</p></details>'
             '<button>Ziel speichern</button></form></section>')

    body += ('<section class="card" style="margin-top:16px">'
             '<h2>Paperless im Netzwerk suchen</h2>'
             '<p>Findet lokal angekündigte Paperless-Dienste über mDNS/DNS-SD. '
             'Nicht angekündigte Instanzen werden nicht erkannt; '
             'die manuelle Eingabe bleibt jederzeit möglich.</p>'
             '<form method="get" action="/targets">'
             '<button type="submit" name="search" value="1">Paperless suchen</button>'
             '</form>')
    if searched:
        if discovered:
            body += '<div class="entry-list">'
            for uri in discovered:
                body += ('<div class="entry-row"><div><strong>Paperless-Kandidat</strong>'
                         '<p class="muted">' + e(uri) + '</p></div>'
                         '<button type="button" class="secondary" data-select-paperless="' +
                         e(uri) + '">Übernehmen</button></div>')
            body += '</div>'
        else:
            body += ('<p role="status">Keine angekündigte Paperless-Instanz gefunden. '
                     'Bitte Netzwerk-Ankündigung prüfen oder Adresse manuell eintragen.</p>')
        body += ('<p class="status-note">Suchtreffer sind nur Vorschläge. '
                 'HTTPS-Zertifikat, API und Zugangsdaten werden dadurch nicht bestätigt.</p>')
    body += '</section>'
    if discovered:
        body += '<datalist id="paperless-candidates">' + "".join(
            '<option value="' + e(uri) + '"></option>' for uri in discovered
        ) + '</datalist>'
    body += '<section class="card" style="margin-top:16px"><h2>Adressbeispiele</h2>'
    for kind, example in HELP.items():
        body += '<p><strong>' + e(LABELS[kind]) + ':</strong> ' + e(example) + '</p>'
    body += ('<p>API-Tokens nur mit gültigem HTTPS-Zertifikat übertragen. '
             'Netzwerkverbindungen können beim Test scheitern; die PDF verbleibt '
             'dann in der lokalen Auftragswarteschlange.</p></section>')
    body += '<script defer src="/assets/target-select.js"></script>'
    return layout("Dokumentenziele", body, active="/targets", csrf=csrf, notice=notice)


def jobs_page(jobs, summary, csrf, notice=""):
    body = ('<h1>Zustellaufträge</h1><p>Dokumente liegen dauerhaft im '
            'lokalen PDF-Spool. Sie werden auch nach einem Neustart weiter '
            'verwaltet. Status <strong>Prüfen</strong> bedeutet: Eine frühere '
            'Zustellung könnte bereits erfolgt sein. Vor erneutem Senden '
            'zuerst das Ziel kontrollieren.</p>')
    body += ('<section class="grid">' + "".join(
        '<article class="card"><h2>' + e(key) + '</h2><p class="pill">'
        + e(value) + '</p></article>' for key, value in sorted(summary.items())
    ) + '</section>')
    if not jobs:
        body += '<p>Noch keine Dokumente vorgemerkt.</p>'
    else:
        body += '<section class="grid" style="margin-top:18px">'
        names = {"queued": "Wartend", "retry": "Neuer Versuch",
                 "sending": "Wird übertragen", "done": "Angenommen/gesichert",
                 "review": "Prüfen", "failed": "Konfiguration prüfen"}
        for job in jobs:
            body += ('<article class="card"><h2>Auftrag '
                     + e(job["id"][:10]) + '</h2>'
                     '<p><strong>' + e(job["target_name"]) + '</strong> · '
                     + e(job["kind"]) + '</p>'
                     '<p>Status: <strong>' + e(names.get(job["status"], job["status"]))
                     + '</strong><br>Versuche: ' + e(job["attempts"]) +
                     '<br>PDF: ' + e(job["size_bytes"]) + ' Bytes</p>')
            if job["last_error"]:
                body += '<p class="alert">' + e(job["last_error"]) + '</p>'
            if job["receipt"]:
                body += '<p>' + e(job["receipt"]) + '</p>'
            if job["status"] in ("failed", "retry", "review"):
                body += ('<form method="post" action="/jobs/retry">' + token(csrf)
                         + '<input type="hidden" name="job_id" value="' +
                         e(job["id"]) + '">')
                if job["status"] == "review":
                    body += ('<label><input type="checkbox" name="reviewed" '
                             'value="yes" required style="width:auto"> '
                             'Ich habe am Ziel geprüft, dass ich erneut '
                             'senden möchte. Doppelte Dokumente sind möglich.</label>')
                body += '<button>Erneut versuchen</button></form>'
            body += '</article>'
        body += '</section>'
    body += ('<p>PDF-Spool und erfolgreich zugestellte Dateien werden in dieser '
             'Entwicklungsphase nicht automatisch gelöscht. '
             'Automatische Speicherbereinigung und vollständige Datensicherung '
             'folgen in Block 8.</p>')
    return layout("Zustellaufträge", body, active="/jobs", csrf=csrf, notice=notice)

def paperless_diagnostic_page(target, result, csrf):
    """No secrets, document names, tokens or raw remote response bodies."""
    heading = ('<h1>Paperless: Erweiterte Diagnose</h1>'
               '<p><strong>' + e(target["name"]) + '</strong> · ' +
               e(target["address"]) + '</p>')
    content = heading + '<section class="entry-list">'
    for step in result.get("steps", ()):
        state = ("OK" if step["ok"] is True else
                 "Nicht geprüft" if step["ok"] is None else "Problem")
        code = (" · HTTP " + str(step["http"])) if "http" in step else ""
        content += ('<article class="card"><h2>' + e(step["name"]) + '</h2>'
                    '<p><strong>' + e(state) + '</strong>' + e(code) + '</p>'
                    '<p>' + e(step["message"]) + '</p></article>')
    content += '</section>'
    if result.get("message"):
        content += '<p role="status">' + e(result["message"]) + '</p>'
    content += ('<p class="status-note">Es wurde kein Dokument hochgeladen. '
                'Ein erfolgreicher API-Lesetest bestätigt nicht die Uploadberechtigung.</p>'
                '<p><a href="/targets">Zurück zur Zielverwaltung</a></p>')
    return layout("Paperless-Diagnose", content, active="/targets", csrf=csrf)
