"""Simple printer dashboard; technical URI controls remain in Details/Advanced."""
from urllib.parse import urlsplit

from itomiscan.web.pages import e, layout, token, detail_dialog


def _ip(address):
    try:
        return urlsplit(address).hostname or "Adresse unbekannt"
    except ValueError:
        return "Adresse unbekannt"


def printers_page(saved_targets, installed, csrf, *, notice="", issue="",
                  discovered=None, searched=False, unknown=0, identities=None):
    identities = identities or {}
    installed = set(installed)
    content = ('<h1>Drucker</h1><p>Netzwerkdrucker suchen und mit einem Klick '
               'einrichten.</p>')
    if issue:
        content += '<div class="alert">' + e(issue) + '</div>'
    content += '<h2>Eingerichtete Drucker</h2><section class="entry-list">'
    active = [target for target in saved_targets if target["name"] in installed]
    if not active:
        content += '<p class="muted">Noch keine Drucker eingerichtet.</p>'
    for i, item in enumerate(active):
        name = item["name"]
        title = identities.get(item["id"], {}).get("name") or name.replace("_", " ")
        detail = ('<article class="card"><h2>' + e(title) + '</h2>'
                  '<p>Druckaufträge gelten nach Übergabe an CUPS als angenommen. '
                  'Den tatsächlichen Ausdruck bitte am Gerät prüfen.</p>')
        for action, label, cls in (
            ("default", "Als Standarddrucker festlegen", "secondary"),
            ("install", "Verbindung aktualisieren", "secondary"),
            ("test", "Testseite drucken", "secondary"),
            ("uninstall", "Drucker aus CUPS entfernen", "danger"),
        ):
            detail += ('<form method="post" action="/printers/' + action + '">' +
                       token(csrf) + '<input type="hidden" name="target_id" value="' +
                       e(item["id"]) + '"><button class="' + cls + '">' +
                       label + '</button></form>')
        detail += ('<details><summary>Technische Verbindung bearbeiten</summary>'
                   '<form method="post" action="/printers/edit">' + token(csrf) +
                   '<input type="hidden" name="target_id" value="' + e(item["id"]) +
                   '"><label>Verbindungsadresse</label><input name="address" required '
                   'maxlength="350" value="' + e(item["address"]) +
                   '"><button>Verbindung speichern</button></form></details>'
                   '<form method="post" action="/targets/delete">' + token(csrf) +
                   '<input type="hidden" name="id" value="' + e(item["id"]) +
                   '"><button class="danger">Gespeichertes Ziel entfernen</button>'
                   '</form></article>')
        content += detail_dialog(
            'printer-' + str(i), title, _ip(item["address"]), detail)
    content += '</section>'

    waiting = [target for target in saved_targets if target["name"] not in installed]
    if waiting:
        content += '<h2>Einrichtung abschließen</h2><section class="entry-list">'
        for item in waiting:
            content += ('<div class="entry-row"><div><strong>' +
                        e(item["name"].replace("_", " ")) + '</strong><p class="muted">' +
                        e(_ip(item["address"])) + '</p></div>'
                        '<form method="post" action="/printers/install">' + token(csrf) +
                        '<input type="hidden" name="target_id" value="' +
                        e(item["id"]) + '"><button>Einrichten</button></form>'
                        '</div>')
        content += '</section>'

    content += ('<h2>Verfügbare Drucker</h2>'
                '<form method="get" action="/printers">'
                '<button name="search" value="1">Drucker suchen</button></form>')
    if searched:
        if discovered:
            content += '<section class="entry-list">'
            saved_uris = {x["address"] for x in saved_targets}
            saved_ids = {item["identity"] for item in identities.values()}
            for device in discovered:
                if device["uri"] in saved_uris or device["identity"] in saved_ids:
                    continue
                content += (
                    '<div class="entry-row"><div><strong>' +
                    e(device["name"]) + '</strong><p class="muted">' +
                    e(device["ip"]) + '</p></div>'
                    '<form method="post" action="/printers/add">' + token(csrf) +
                    '<input type="hidden" name="identity" value="' +
                    e(device["identity"]) + '">'
                    '<input type="hidden" name="uri" value="' +
                    e(device["uri"]) + '">'
                    '<button>Hinzufügen</button></form></div>')
            content += '</section>'
        else:
            content += ('<p role="status">Keine eindeutig erkannten Drucker gefunden. '
                        'Manuelle Einrichtung ist weiterhin möglich.</p>')
        if unknown:
            content += ('<p class="status-note">' + e(unknown) +
                        ' weitere Verbindungen konnten nicht eindeutig '
                        'einem Drucker zugeordnet werden.</p>')
    content += (
        '<details class="card" style="margin-top:18px">'
        '<summary>Drucker manuell hinzufügen (Erweitert)</summary>'
        '<p>Für Sonderfälle. Zuerst speichern, anschließend einrichten. '
        'Treiberlose Einrichtung benötigt IPP/IPPS Everywhere.</p>'
        '<form method="post" action="/printers/save">' + token(csrf) +
        '<label>Druckername</label><input name="name" maxlength="40" '
        'pattern="[A-Za-z][A-Za-z0-9_-]{0,39}" required>'
        '<label>Verbindung</label><select name="protocol">'
        '<option value="ipps">IPPS (verschlüsselt)</option>'
        '<option value="ipp">IPP</option>'
        '<option value="socket">RAW 9100 (nur mit Treiber)</option>'
        '<option value="lpd">LPD (nur mit Treiber)</option></select>'
        '<label>IP-Adresse oder Hostname</label>'
        '<input name="host" maxlength="253" placeholder="192.168.1.20">'
        '<label>Vollständige Verbindungsadresse (optional)</label>'
        '<input name="address" maxlength="350" placeholder="ipp://drucker/ipp/print">'
        '<button>Druckerziel speichern</button></form></details>'
        '<p class="status-note">Eine Druckersuche richtet keine Warteschlangen '
        'ein. CUPS- und Netzwerkfehler werden bei der Einrichtung angezeigt.</p>')
    return layout("Drucker", content, active="/printers", csrf=csrf, notice=notice)
