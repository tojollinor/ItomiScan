"""Authenticated browser controller; commands are executed by the kiosk."""
from itomiscan.web.pages import e, layout, options, token


def remote_page(profiles, selected, latest, csrf, notice=""):
    state = ("Noch kein Fernauftrag" if not latest else
             f"Letzter Auftrag #{latest['id']}: {latest['action']} · "
             f"{latest['status']} · {latest['detail']}")
    body = ('<h1>Scanner fernbedienen</h1>'
            '<p>Aktionen werden an die lokale ItomiScan-Oberfläche übergeben. '
            'Eine aktive PIN-Sitzung und lokale Berechtigungen gelten weiterhin. '
            'Während eines Scans oder der Dokumentenprüfung werden neue Aktionen abgelehnt.</p>'
            '<section class="grid"><article class="card"><h2>Scansteuerung</h2>'
            '<p>Gewähltes Standardprofil: <strong>' + e(selected) + '</strong></p>'
            '<p>Scanprofile können unter Scanprofile verwaltet und gewechselt werden.</p>'
            '<form method="post" action="/remote/command">' + token(csrf)
            + '<button name="action" value="scan">Mit aktuellem Profil scannen</button>'
            '<button class="secondary" name="action" value="open_scan">Scanansicht öffnen</button>'
            '<button class="secondary" name="action" value="home">Startseite anzeigen</button>'
            '</form></article><article class="card"><h2>Systemaktionen</h2>'
            '<p>Nur ausführen, wenn der Scanner frei ist. '
            'Keine automatische Neuinstallation oder Rechteerweiterung.</p>'
            '<form method="post" action="/remote/command" data-power-confirm>'
            + token(csrf) +
            '<input type="hidden" name="confirmed" value="yes">'
            '<button name="action" value="restart">Scanner neu starten</button>'
            '<button class="danger" name="action" value="poweroff">Scanner herunterfahren</button>'
            '</form></article></section>'
            '<article class="card" style="margin-top:16px"><h2>Auftragsstatus</h2>'
            '<p id="remote-command-status" role="status">' + e(state) + '</p>'
            '<p class="muted">Angenommen bedeutet nur, dass der Auftrag an den Kiosk '
            'übergeben wurde, nicht dass ein Scan oder Neustart abgeschlossen ist.</p>'
            '</article><script defer src="/assets/remote.js"></script>')
    return layout("Fernbedienung", body, active="/remote", csrf=csrf, notice=notice)
