"""Server-rendered, dependency-free ItomiScan administration pages.

All untrusted values are escaped before inclusion in markup. Browser receives
no JavaScript, no external assets and no stored secrets.
"""
from html import escape
import json


def e(value):
    return escape(str(value), quote=True)


CSS = """
:root{color-scheme:dark;--bg:#101927;--pane:#192738;--fg:#f1f5fb;--soft:#a8bacd;--accent:#5fc7eb;--ok:#53c49b;--line:#32455a}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font-family:system-ui,-apple-system,DejaVu Sans,sans-serif;line-height:1.45}
.wrap{max-width:1120px;margin:auto;padding:22px 22px 50px}
header{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;border-bottom:1px solid var(--line);padding-bottom:14px}
.brand{font-size:1.8rem;font-weight:800;letter-spacing:-.035em}.brand b{color:var(--accent)}
nav{display:flex;flex-wrap:wrap;gap:9px;align-items:center}a{color:var(--accent)}nav a{padding:10px 9px;text-decoration:none;color:var(--fg);border-radius:9px}
nav a:hover,nav a.active{background:#2a4560}h1{font-size:1.65rem;margin:28px 0 10px}h2{font-size:1.15rem;margin:4px 0 14px}
p{color:var(--soft)}small,.muted{color:var(--soft)}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(285px,1fr));gap:16px}
.card{background:var(--pane);padding:20px;border-radius:15px;min-width:0}.card p{margin-top:0}.wide{grid-column:1/-1}
label{display:block;color:var(--soft);font-size:.92rem;margin:11px 0 5px}
input,select,textarea,button{font:inherit;max-width:100%}
input,select,textarea{background:#0e1c2d;color:var(--fg);border:1px solid #587088;border-radius:8px;padding:10px;width:100%}
textarea{min-height:80px}input:focus,select:focus,textarea:focus{outline:2px solid var(--accent);outline-offset:1px}
button,.action{display:inline-block;background:#2a75c1;color:white;border:0;border-radius:9px;padding:11px 16px;cursor:pointer;margin-top:13px;text-decoration:none;font-weight:600}
button:hover,.action:hover{background:#3586d7}.secondary{background:#30485f}.danger{background:#8c4050}
.notice{background:#153b3a;border:1px solid #337869;padding:13px 17px;border-radius:9px;margin:18px 0}
.alert{background:#4b2834;border:1px solid #a05d6b;padding:13px 17px;border-radius:9px;margin:18px 0}
.pill{display:inline-block;padding:4px 10px;border-radius:20px;color:var(--ok);background:#1c3938;font-weight:600}
.inline{display:inline-block;margin:0}.data{background:#0d1a2a;padding:14px;border-radius:10px;white-space:pre-wrap;overflow-wrap:anywhere;max-height:270px;overflow:auto;font-size:.92rem}
table{width:100%;border-collapse:collapse}td,th{padding:10px;text-align:left;border-bottom:1px solid var(--line);word-break:break-word}
.end{margin-top:24px;border-top:1px solid var(--line);padding-top:13px}
.login{max-width:460px;margin:12vh auto 0}.login h1{margin-top:4px}
@media(max-width:650px){.wrap{padding:14px}nav a{padding:8px 5px}.card{padding:16px}table{font-size:.86rem}.brand{font-size:1.5rem}}
"""


def layout(title, body, *, active="", csrf="", notice="", error="", logged=True):
    navigation = ""
    if logged:
        links = (("/", "Übersicht"), ("/profiles", "Scanprofile"),
                 ("/users", "Benutzer"), ("/targets", "Zielsysteme"), ("/system", "System"),
                 ("/backups", "Sicherung"))
        navigation = "<nav>" + "".join(
            f'<a class="{("active" if url == active else "")}" href="{url}">{e(label)}</a>'
            for url, label in links
        ) + (f'<form class="inline" method="post" action="/logout">'
             f'<input type="hidden" name="csrf" value="{e(csrf)}">'
             '<button class="secondary">Abmelden</button></form></nav>')
    messages = (f'<div class="notice">{e(notice)}</div>' if notice else "") + (
        f'<div class="alert">{e(error)}</div>' if error else "")
    return ('<!doctype html><html lang="de"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{e(title)} · ItomiScan</title><style>{CSS}</style></head>'
            '<body><main class="wrap"><header><div class="brand">Itomi<b>Scan</b>'
            f'</div>{navigation}</header>{messages}{body}'
            '<div class="end muted">ItomiScan 1.0.0 Entwicklung · '
            'Webadministration nur im geschützten LAN/VPN</div></main></body></html>')


def token(csrf):
    return f'<input type="hidden" name="csrf" value="{e(csrf)}">'


def options(items, current):
    return "".join(f'<option value="{e(item)}"'
                   + (" selected" if str(item) == str(current) else "")
                   + f'>{e(item)}</option>' for item in items)


def login(error=""):
    content = ('<div class="login card"><h1>Webadministration</h1>'
               '<p>Bitte das Administratorpasswort eingeben. '
               'Ein Benutzername ist nicht erforderlich.</p>'
               '<form method="post" action="/login"><label for="password">Passwort</label>'
               '<input id="password" type="password" name="password" '
               'autocomplete="current-password" maxlength="128" required>'
               '<button>Anmelden</button></form><p><small>Die erste Einrichtung erfolgt '
               'sicher über die lokale Konsole/SSH. Es gibt kein Standardpasswort.'
               '</small></p></div>')
    return layout("Anmelden", content, logged=False, error=error)


def overview(status, counts, csrf, notice=""):
    body = '<h1>Übersicht</h1><p>Scanner und Einstellungen im Blick.</p>'
    items = (
        ("Scanner", status.get("scanner", "Nicht geprüft"),
         "Erkennung über die Systemdiagnose starten."),
        ("Scanprofile", str(counts["profiles"]), "Gemeinsam mit dem Touchdisplay gespeichert."),
        ("Zielsysteme", str(counts["targets"]),
         "Konfiguration vorbereitet; Übertragung und Druck folgen."),
        ("Versionszweig", status.get("branch", "Unbekannt"),
         "Entwicklung ist kein Release."),
    )
    body += '<section class="grid">' + "".join(
        f'<article class="card"><h2>{e(name)}</h2><p class="pill">{e(value)}</p>'
        f'<p>{e(description)}</p></article>' for name, value, description in items
    ) + '</section>'
    return layout("Übersicht", body, active="/", csrf=csrf, notice=notice)


def profiles_page(profiles, selected, csrf, notice=""):
    body = '<h1>Scanprofile</h1><p>Die Änderungen stehen dem Touchdisplay beim nächsten Profilaufruf zur Verfügung.</p>'
    body += '<section class="grid">'
    for item in profiles:
        name = item["name"]
        body += (f'<article class="card"><h2>{e(name)}'
                 + (' <span class="pill">Ausgewählt</span>' if name == selected else "")
                 + '</h2><form method="post" action="/profiles/save">'
                 + token(csrf)
                 + f'<label>Profilname</label><input name="name" maxlength="32" required value="{e(name)}">'
                 + '<label>Farbmodus</label><select name="mode">' +
                 options(("Color", "Gray", "Lineart", "Halftone"), item["mode"]) +
                 '</select><label>Einzug</label><select name="source">' +
                 options(("ADF Front", "ADF Back", "ADF Duplex"), item["source"]) +
                 f'</select><label>Auflösung (DPI)</label><input type="number" name="resolution" min="50" max="600" value="{e(item["resolution"])}">'
                 + '<label>Ausgabe</label><select name="output">' +
                 options(("PDF", "Bild (PNG)"), item["output"]) +
                 f'</select><label>Erweiterte SANE-Einstellungen (JSON)</label>'
                 f'<textarea name="advanced">{e(json.dumps(item.get("settings", {}), ensure_ascii=False, indent=2))}</textarea>'
                 '<button>Profil speichern</button></form>'
                 '<form method="post" action="/profiles/select">'
                 + token(csrf) + f'<input type="hidden" name="name" value="{e(name)}">'
                 '<button class="secondary">Als Standard verwenden</button></form></article>')
    body += '</section><div class="card" style="margin-top:16px"><h2>Neues Profil</h2>'
    body += ('<form method="post" action="/profiles/save">' + token(csrf)
             + '<label>Name</label><input name="name" maxlength="32" required>'
             + '<label>Farbmodus</label><select name="mode">'
             + options(("Color", "Gray", "Lineart", "Halftone"), "Color")
             + '</select><label>Einzug</label><select name="source">'
             + options(("ADF Duplex", "ADF Front", "ADF Back"), "ADF Duplex")
             + '</select><label>Auflösung (DPI)</label><input type="number" name="resolution" min="50" max="600" value="200">'
             + '<label>Ausgabe</label><select name="output">'
             + options(("PDF", "Bild (PNG)"), "PDF")
             + '</select><label>Erweiterte SANE-Einstellungen (JSON)</label>'
             + '<textarea name="advanced">{}</textarea><button>Profil hinzufügen</button></form></div>')
    return layout("Scanprofile", body, active="/profiles", csrf=csrf, notice=notice)


def targets_page(targets, csrf, notice=""):
    body = ('<h1>Zielsysteme</h1><p>Adressen hier vorbereiten. '
            '<strong>Die Übertragung an Paperless, das Speichern im Netzwerk '
            'und das Drucken sind noch nicht aktiv.</strong> '
            'API-Tokens und Zugangsdaten gehören derzeit nicht in diese Felder.</p>')
    body += '<section class="grid">'
    for item in targets:
        body += (f'<article class="card"><h2>{e(item["name"])}</h2>'
                 f'<p>{e(item["kind"])} · {e(item["address"])}</p>'
                 f'<form method="post" action="/targets/delete">' + token(csrf)
                 + f'<input type="hidden" name="id" value="{e(item["id"])}">'
                 '<button class="danger">Ziel entfernen</button></form></article>')
    body += '</section><div class="card" style="margin-top:16px"><h2>Neues Ziel vorbereiten</h2>'
    body += ('<form method="post" action="/targets/save">' + token(csrf)
             + '<label>Zieltyp</label><select name="kind">'
             + options(("paperless", "printer", "network", "email"), "paperless")
             + '</select><label>Anzeigename</label><input name="name" required maxlength="60">'
             + '<label>Adresse (ohne Zugangsdaten)</label>'
             '<input name="address" required maxlength="350" placeholder="https://paperless.lan oder ipp://drucker/ipp/print">'
             '<button>Ziel speichern</button></form></div>')
    return layout("Zielsysteme", body, active="/targets", csrf=csrf, notice=notice)


def system_page(state, settings, csrf, diagnostic="", notice=""):
    body = '<h1>System und Diagnose</h1><section class="grid"><article class="card"><h2>Gerätestatus</h2>'
    for title, key in (("Host", "hostname"), ("IP", "ip"), ("System", "platform"),
                       ("Git-Zweig", "branch"), ("Commit", "commit"),
                       ("Uptime", "uptime"), ("Freier Speicher", "free_space")):
        body += f'<p><strong>{e(title)}:</strong> {e(state.get(key, "Nicht verfügbar"))}</p>'
    body += ('</article><article class="card"><h2>Geräteeinstellungen</h2>'
             '<p>Änderungen des Bildschirmschoners greifen am Display spätestens '
             'nach einem Neustart der Oberfläche.</p>'
             '<form method="post" action="/system/settings">' + token(csrf)
             + f'<label>Gerätename</label><input maxlength="48" name="device_label" value="{e(settings["device_label"])}">'
             + f'<label>Bildschirmschoner (Minuten)</label><input type="number" name="screensaver_minutes" min="1" max="60" value="{e(settings["screensaver_minutes"])}">'
             + '<button>Einstellungen speichern</button></form></article></section>')
    body += ('<article class="card" style="margin-top:16px"><h2>SANE-Scannererkennung</h2>'
             '<p>Diese Diagnose startet ausschließlich <code>scanimage -L</code>. '
             'Ein laufender Scan sollte vorher abgeschlossen sein.</p>'
             '<form method="post" action="/system/diagnose">' + token(csrf)
             + '<button class="secondary">Scanner prüfen</button></form>'
             + (f'<pre class="data">{e(diagnostic)}</pre>' if diagnostic else "")
             + '</article><article class="card" style="margin-top:16px"><h2>Administratorpasswort ändern</h2>'
             '<form method="post" action="/system/password">' + token(csrf)
             + '<label>Aktuelles Passwort</label><input type="password" name="current_password" autocomplete="current-password" required>'
             + '<label>Neues Passwort (mindestens 10 Zeichen)</label><input type="password" name="new_password" minlength="10" maxlength="128" autocomplete="new-password" required>'
             + '<label>Neues Passwort wiederholen</label><input type="password" name="confirm_password" minlength="10" maxlength="128" autocomplete="new-password" required>'
             + '<button>Passwort ändern</button></form></article>')
    return layout("System", body, active="/system", csrf=csrf, notice=notice)


def backup_page(csrf, notice=""):
    body = ('<h1>Konfiguration sichern</h1><section class="grid"><article class="card">'
            '<h2>Export</h2><p>Profile, Einstellungen und Zieladressen als JSON-Datei sichern. '
            'Administratorpasswort, Hash, Sitzungen und Zugangsdaten sind nicht enthalten.</p>'
            '<a class="action" href="/backup.json">JSON-Sicherung herunterladen</a></article>'
            '<article class="card"><h2>Wiederherstellen</h2>'
            '<p>Der Import ersetzt Scanprofile, Geräteeinstellungen und Zieladressen. '
            'Das Administratorpasswort bleibt erhalten. Bitte vorher eine Sicherung herunterladen.</p>'
            '<form method="post" action="/backups/restore" enctype="multipart/form-data">'
            + token(csrf) +
            '<label>Konfigurationsdatei (JSON, maximal 128 KB)</label>'
            '<input type="file" name="backup" accept=".json,application/json" required>'
            '<button class="danger">Konfiguration wiederherstellen</button></form></article>'
            '</section>')
    return layout("Sicherung", body, active="/backups", csrf=csrf, notice=notice)
