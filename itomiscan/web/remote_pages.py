"""Authenticated browser controller; commands are executed by the kiosk."""
from itomiscan.web.pages import e, layout, options, token


def remote_page(profiles, selected, latest, csrf, notice="", *, live=False):
    state = ("Noch kein Fernauftrag" if not latest else
             f"Letzter Auftrag #{latest['id']}: {latest['action']} · "
             f"{latest['status']} · {latest['detail']}")
    view = ('<article class="card"><h2>Liveansicht des Touchscreens</h2>'
            '<p>Ressourcenschonende Livebilder mit verkürztem Aktualisierungsintervall. '
            'Das Bild behält das echte Seitenverhältnis. Klicks und ausgewählte Tastaturbefehle werden an den lokalen Kiosk '
            'gesendet. Die lokale PIN-Anmeldung bleibt erforderlich.</p>')
    if live:
        view += ('<div class="remote-screen" id="remote-screen">'
                 '<img id="remote-live-frame" alt="Aktueller Scannerbildschirm" '
                 'draggable="false" hidden>'
                 '<div id="remote-live-placeholder" class="remote-placeholder" role="status">'
                 '<strong id="remote-live-heading">Livebild wird geladen …</strong>'
                 '<p id="remote-live-detail">Verbindung zum Scanner wird hergestellt.</p>'
                 '<button type="button" id="remote-reconnect" hidden>'
                 'Wiederherstellen</button>'
                 '<a id="remote-login-link" href="/login" hidden>Erneut anmelden</a>'
                 '</div></div>'
                 '<p id="remote-live-status" role="status" aria-live="polite">'
                 'Verbindung wird hergestellt …</p>'
                 '<form method="post" action="/remote/live/stop">' + token(csrf)
                 + '<button class="secondary">Liveansicht beenden</button></form>'
                 '<div class="remote-keys"><label for="remote-text">Tastatureingabe</label>'
                 '<input id="remote-text" maxlength="80" '
                 'placeholder="Text eingeben und senden">'
                 '<button type="button" id="remote-send-text">Text senden</button>'
                 '<button type="button" data-remote-key="BackSpace">Rücktaste</button>'
                 '<button type="button" data-remote-key="Return">Enter</button>'
                 '<button type="button" data-remote-key="Tab">Tab</button></div>')
    else:
        view += ('<p class="status-note">Die Liveansicht ist ausgeschaltet und '
                 'verbraucht keine Bildschirmaufnahmen.</p>'
                 '<form method="post" action="/remote/live/start">' + token(csrf)
                 + '<button>Liveansicht starten</button></form>')
    view += '</article>'
    body = ('<h1>Scanner fernsteuern</h1>'
            '<p>Aktionen werden an die lokale ItomiScan-Oberfläche übergeben. '
            'Eine aktive PIN-Sitzung und lokale Berechtigungen gelten weiterhin. '
            'Während eines Scans oder der Dokumentenprüfung werden neue Aktionen abgelehnt.</p>'
            + view + '<section class="grid" style="margin-top:16px">'
            '<article class="card"><h2>Scansteuerung</h2>'
            '<p>Gewähltes Standardprofil: <strong>' + e(selected) + '</strong></p>'
            '<form method="post" action="/remote/profile">' + token(csrf)
            + '<label>Scanprofil</label><select name="name">'
            + options([p["name"] for p in profiles], selected)
            + '</select><button class="secondary">Profil auswählen</button></form>'
            '<p>Bei aktiver PIN-Anmeldung gilt weiterhin das persönliche '
            'Profil des angemeldeten Scannerbenutzers.</p>'
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
    return layout("Fernsteuerung", body, active="/remote", csrf=csrf, notice=notice)
