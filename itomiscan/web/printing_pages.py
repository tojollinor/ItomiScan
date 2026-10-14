"""Password-protected CUPS printer management screen (no JS/assets)."""
from itomiscan.web.pages import e, layout, token


def printers_page(saved_targets, installed, csrf, *, notice="", issue="", discovered=None):
    intro = (
        '<h1>Drucker verwalten</h1>'
        '<p>Drucker zuerst als Druckziel hinterlegen und anschließend '
        'über CUPS registrieren. Das Gerät benötigt einmalig die manuelle '
        'Einrichtung mit <code>setup-printing.sh</code>. '
        'Die folgenden Aktionen betreffen die Druckwarteschlangen des '
        'Scanners, nicht die Einstellungen der Netzwerkdrucker selbst.</p>'
    )
    if issue:
        intro += '<div class="alert">' + e(issue) + '</div>'
    content = intro + '<section class="grid">'
    for entry in saved_targets:
        name = entry["name"]
        exists = name in installed
        status = "In CUPS eingerichtet" if exists else "Noch nicht in CUPS"
        content += ('<article class="card"><h2>' + e(name) + '</h2>'
                    '<p>' + e(entry["address"]) + '</p>'
                    '<p class="pill">' + e(status) + '</p>'
                    '<p>Ein Druckauftrag gilt nach erfolgreicher Übergabe '
                    'an CUPS zunächst als angenommen. Papierausgabe bitte '
                    'am Gerät kontrollieren.</p>')
        if exists:
            content += ('<form method="post" action="/printers/test">' +
                        token(csrf) +
                        '<input type="hidden" name="target_id" value="' +
                        e(entry["id"]) + '">' +
                        '<button>Testseite drucken</button></form>' +
                        '<form method="post" action="/printers/uninstall">' +
                        token(csrf) +
                        '<input type="hidden" name="target_id" value="' +
                        e(entry["id"]) + '">' +
                        '<button class="danger">CUPS-Zuordnung aufheben</button></form>')
        else:
            content += ('<form method="post" action="/printers/install">' +
                        token(csrf) +
                        '<input type="hidden" name="target_id" value="' +
                        e(entry["id"]) + '">' +
                        '<button>In CUPS einrichten</button></form>')
        content += ('<form method="post" action="/targets/delete">' +
                    token(csrf) +
                    '<input type="hidden" name="id" value="' +
                    e(entry["id"]) + '">' +
                    '<button class="secondary">Gespeichertes Ziel entfernen</button></form>'
                    '</article>')
    content += '</section>'
    content += ('<section class="card" style="margin-top:17px">'
                '<h2>Drucker hinzufügen</h2>'
                '<form method="post" action="/printers/save">' + token(csrf)
                + '<label>CUPS-Name (Buchstaben, Zahlen, _ oder -)</label>'
                '<input name="name" pattern="[A-Za-z][A-Za-z0-9_-]{0,39}" '
                'maxlength="40" required placeholder="BueroLaser">'
                '<label>Netzwerkadresse</label>'
                '<input name="address" maxlength="350" required '
                'placeholder="ipps://drucker.lan/ipp/print">'
                '<p>IPP/IPPS unterstützt bei geeigneten Druckern treiberlosen Betrieb. RAW 9100 (socket://), LPD (lpd://) und USB (usb://) benötigen ein geeignetes Druckdatenformat beziehungsweise einen passenden Treiber. Der Druck einer PDF ist damit nicht automatisch gewährleistet. Der Drucker '
                'muss das gewählte Protokoll unterstützen. Zugangsdaten gehören nicht in '
                'die Druckeradresse. Der nächste Schritt registriert den '
                'Drucker in CUPS.</p>'
                '<button>Druckerziel speichern</button></form></section>')
    if discovered:
        content += '<section class="card" style="margin-top:17px"><h2>Erkannte Drucker</h2><p>Gefunden durch CUPS (lpinfo -v). Adresse für die Einrichtung übernehmen:</p>'
        for uri in discovered:
            content += '<p><code>' + e(uri) + '</code></p>'
        content += '</section>'
    if installed:
        content += '<section class="card" style="margin-top:17px"><h2>CUPS-Warteschlangen</h2><p>'
        content += e(", ".join(installed)) + '</p></section>'
    content += (
        '<p>Bei Netzwerkproblemen bleibt die gescannte PDF-Datei lokal '
        'gesichert. Unklare CUPS-Übergaben müssen vor erneutem Senden '
        'im Menü <strong>Aufträge</strong> geprüft werden.</p>'
    )
    return layout("Drucker", content, active="/printers", csrf=csrf, notice=notice)
