"""PIN user and permission management pages. No PINs or digests rendered."""
from itomiscan.web.pages import e, layout, options, token
from itomiscan.storage.users import FEATURES, PERMISSIONS


def user_form(user, profile_names, csrf):
    record = user or {"id": "", "name": "", "active": True,
                      "permissions": ["scan"], "assigned_profiles": profile_names[:1],
                      "default_profile": profile_names[0]}
    title = e(record["name"]) if user else "Neuen Benutzer anlegen"
    html = ('<article class="card"><h2>' + title + '</h2>'
            '<form method="post" action="/users/save">' + token(csrf)
            + '<input type="hidden" name="user_id" value="' + e(record["id"]) + '">'
            '<label>Benutzername</label><input name="name" required maxlength="40" value="'
            + e(record["name"]) + '">'
            '<label>Persönliche PIN (4 bis 6 Ziffern)</label>'
            '<input type="password" name="pin" inputmode="numeric" pattern="[0-9]{4,6}" '
            'maxlength="6" autocomplete="new-password" '
            + ('' if user else 'required ')
            + 'placeholder="' + ('Leer lassen: PIN beibehalten' if user else 'PIN festlegen') + '">'
            '<label><input type="checkbox" style="width:auto" name="active" value="yes"'
            + (' checked' if record["active"] else '')
            + '> Benutzer aktiv</label>'
            '<p class="muted">Freigegebene Funktionen</p>')
    for permission in PERMISSIONS:
        html += ('<label><input type="checkbox" style="width:auto" '
                 'name="perm_' + e(permission) + '" value="yes"'
                 + (' checked' if permission in record["permissions"] else '')
                 + '> ' + e(FEATURES[permission]) + '</label>')
    html += '<p class="muted">Zugewiesene Scanprofile</p>'
    for name in profile_names:
        html += ('<label><input type="checkbox" style="width:auto" '
                 'name="assigned_profiles" value="' + e(name) + '"'
                 + (' checked' if name in record["assigned_profiles"] else '')
                 + '> ' + e(name) + '</label>')
    html += ('<label>Persönliches Standardprofil</label>'
             '<select name="default_profile">'
             + options(profile_names, record["default_profile"]) + '</select>'
             '<button>Benutzer speichern</button></form>')
    if user:
        html += ('<form method="post" action="/users/delete">' + token(csrf)
                 + '<input type="hidden" name="user_id" value="' + e(record["id"]) + '">'
                 '<button class="danger">Benutzer löschen</button></form>')
    return html + '</article>'


def users_page(users, settings, profile_names, csrf, notice=""):
    state = "Aktiviert" if settings["enabled"] else "Deaktiviert"
    body = ('<h1>PIN-Benutzerverwaltung</h1>'
            '<p>Optional: ohne PIN direkt zur Startseite, mit PIN persönliche '
            'Schaltflächen, Scanprofile und zeitgesteuerte Abmeldung.</p>'
            '<article class="card"><h2>Scanner-Anmeldung: ' + e(state) + '</h2>'
            '<p>Vor der Aktivierung mindestens einen aktiven Benutzer mit '
            'eindeutiger PIN anlegen.</p>'
            '<form method="post" action="/users/config">' + token(csrf)
            + '<label><input type="checkbox" style="width:auto" name="enabled" value="yes"'
            + (' checked' if settings["enabled"] else '')
            + '> PIN-Anmeldung beim Gerätestart verwenden</label>'
            '<label>Automatische Abmeldung nach Minuten Inaktivität</label>'
            '<input name="timeout_minutes" type="number" min="1" max="60" required value="'
            + e(settings["timeout_minutes"]) + '">'
            '<button>Einstellung speichern</button></form></article>'
            '<h2 style="margin-top:25px">Benutzer und Berechtigungen</h2>'
            '<section class="grid">')
    for user in users:
        body += user_form(user, profile_names, csrf)
    body += user_form(None, profile_names, csrf) + '</section>'
    body += ('<p>PINs und PIN-Prüfsummen werden weder angezeigt noch in '
             'JSON-Konfigurationssicherungen exportiert. '
             'Die Webadministration nutzt weiter ein unabhängiges Passwort.</p>')
    return layout("Benutzer", body, active="/users", csrf=csrf, notice=notice)
