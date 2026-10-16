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


def targets_page(targets, csrf, configured, notice="", *, discovered=None):
    body = ('<h1>Dokumentenziele</h1><p>Paperless, SMB-Netzwerkordner, '
            'E-Mail und USB sind als Zustellziele vorbereitet. '
            'Für den tatsächlichen Versand muss der separate '
            'ItomiScan-Zustelldienst gestartet sein. '
            'Drucker kommen in Block 7 hinzu.</p>'
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
        detail += ('<form method="post" action="/targets/delete">' + token(csrf)
                 + '<input type="hidden" name="id" value="' + e(tid) + '">'
                 '<button class="danger">Ziel entfernen</button></form></article>')
        body += detail_dialog(f'target-{index}', entry["name"],
                              LABELS.get(kind, kind) + ' · ' + entry["address"], detail)
    body += ('</section><section class="card" style="margin-top:16px">'
             '<h2>Ziel hinzufügen</h2><form method="post" action="/targets/save">'
             + token(csrf)
             + '<label>Art</label><select name="kind">'
             + options(("paperless", "network", "email", "usb", "printer"), "paperless")
             + '</select><label>Anzeigename</label><input name="name" '
             'maxlength="60" required><label>Zieladresse</label>'
             '<input name="address" list="paperless-candidates" maxlength="350" required>'
             '<button>Ziel speichern</button></form></section>')
    if discovered:
        body += '<datalist id="paperless-candidates">' + "".join(
            '<option value="' + e(uri) + '"></option>' for uri in discovered
        ) + '</datalist>'
        body += ('<p class="muted">Mögliche Paperless-Dienste im LAN: '
                 + ", ".join(e(uri) for uri in discovered) +
                 '. Die Erkennung bestätigt noch keine erreichbare Paperless-API.</p>')
    body += '<section class="card" style="margin-top:16px"><h2>Adressbeispiele</h2>'
    for kind, example in HELP.items():
        body += '<p><strong>' + e(LABELS[kind]) + ':</strong> ' + e(example) + '</p>'
    body += ('<p>API-Tokens nur mit gültigem HTTPS-Zertifikat übertragen. '
             'Netzwerkverbindungen können beim Test scheitern; die PDF verbleibt '
             'dann in der lokalen Auftragswarteschlange.</p></section>')
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
