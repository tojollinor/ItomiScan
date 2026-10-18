"""Web-only kiosk tile editor: existing ItomiScan forms and detail dialogs."""
from itomiscan.web.pages import e, layout, token, detail_dialog, options
from itomiscan.storage.kiosk_tiles import ICONS, COLORS

def _edit_form(csrf, tile, targets, groups):
    scan = tile.get("scan") or {}
    bits = ['<form method="post" action="/home-buttons/save">', token(csrf)]
    if tile.get("id"):
        bits.append('<input type="hidden" name="tile_id" value="'+e(tile["id"])+'">')
    bits.extend([
        '<label>Beschriftung</label><input name="label" maxlength="42" required value="'+e(tile.get("label",""))+'">',
        '<label>Art</label><select name="action">',
        options(("scan","group"),tile.get("action","scan")),
        '</select><p class="status-note">scan = Scanaktion; group = Unterseite öffnen.</p>',
        '<label>Symbol</label><select name="icon">',
        options(ICONS,tile.get("icon","scan")),'</select>',
        '<label>Buttonfarbe</label><input type="color" name="color" value="'+e(tile.get("color",COLORS[0]))+'">',
        '<p class="status-note">Individuelle Farbe. Kontrastfarbe wird automatisch bestimmt.</p>',
        '<label>Innerhalb der Gruppe</label><select name="parent"><option value="">Startseite</option>',
    ])
    for group in groups:
        if group["id"] != tile.get("id"):
            bits.append('<option value="'+e(group["id"])+'"'+
                        (' selected' if tile.get("parent")==group["id"] else '')+
                        '>'+e(group["label"])+'</option>')
    bits.extend(['</select><fieldset><legend>Scaneinstellungen (bei Scanbuttons)</legend>',
        '<label>Einzug</label><select name="source">',
        options(("ADF Duplex","ADF Front","ADF Back"),scan.get("source","ADF Duplex")),
        '</select><label>Auflösung (DPI)</label><input type="number" name="resolution" min="50" max="600" required value="'+e(scan.get("resolution",300))+'">',
        '<label>Farbmodus</label><select name="mode">',
        options(("Color","Gray","Lineart","Halftone"),scan.get("mode","Color")),
        '</select><label>Ausgabe</label><select name="output">',
        options(("PDF","Bild (PNG)"),scan.get("output","PDF")),
        '</select><details><summary>Weitere SANE-Einstellungen (JSON)</summary>'
        '<textarea name="advanced" rows="3">'+
        e(__import__("json").dumps(scan.get("settings", {}),ensure_ascii=False))+
        '</textarea></details></fieldset>',
        '<fieldset><legend>Zielverbindungen (Mehrfachauswahl)</legend>',
        '<p class="status-note">Ein Dokument, mehrere gespeicherte Ziele. '
        'Die tatsächliche parallele Zustellung folgt in Block 7.</p>'
    ])
    if not targets:
        bits.append('<p>Keine Ziele gespeichert. Zuerst <a href="/targets">Ziel hinzufügen</a>.</p>')
    for target in targets:
        checked=' checked' if target["id"] in tile.get("targets",[]) else ''
        bits.append('<label class="tile-check"><input type="checkbox" name="targets" value="'+
                    e(target["id"])+'"'+checked+'>'+e(target["name"])+' ('+
                    e(target["kind"])+')</label>')
    bits.extend(['</fieldset><label class="tile-check"><input type="checkbox" '
                 'name="background" value="yes"'+
                 (' checked' if tile.get("background") else '')+
                 '>Im Hintergrund zustellen (Block 7)</label>',
                 '<label class="tile-check"><input type="checkbox" name="enabled" value="yes"'+
                 (' checked' if tile.get("enabled", True) else '')+
                 '>Button aktiv</label><button type="submit">Button speichern</button></form>'])
    return ''.join(bits)

def home_buttons_page(tiles, targets, csrf, notice=""):
    groups=[t for t in tiles if t["action"]=="group"]
    body=('<h1>Startseite gestalten</h1><p>Buttons erstellen, sortieren und bearbeiten. '
          'Änderungen erscheinen beim nächsten Aufruf der Scanner-Startseite.</p>'
          '<section class="entry-list">')
    if not tiles:
        body+='<p class="muted">Noch keine individuellen Buttons. Die bisherige Startseite bleibt erhalten.</p>'
    for tile in tiles:
        title=tile["label"]
        kind="Gruppe" if tile["action"]=="group" else "Scanaktion"
        parent=next((g["label"] for g in groups if g["id"]==tile["parent"]),None)
        subtitle=kind+(" · "+parent if parent else " · Startseite")
        detail='<article class="card">'+_edit_form(csrf,tile,targets,groups)
        detail+=('<form method="post" action="/home-buttons/delete">'+token(csrf)+
                 '<input type="hidden" name="tile_id" value="'+e(tile["id"])+'">'+
                 '<button class="danger">Button löschen</button></form></article>')
        body+=detail_dialog('tile-'+str(tile["id"]),title,subtitle,detail)
        for direction,label in ((-1,"↑"),(1,"↓")):
            body+=('<form class="inline" method="post" action="/home-buttons/move">'+
                   token(csrf)+'<input type="hidden" name="tile_id" value="'+e(tile["id"])+
                   '"><input type="hidden" name="direction" value="'+str(direction)+'">'+
                   '<button class="secondary" title="'+("Nach oben" if direction<0 else "Nach unten")+
                   '">'+label+'</button></form>')
    body+='</section><section class="card" style="margin-top:16px"><h2>Button hinzufügen</h2>'
    body+=_edit_form(csrf,{},targets,groups)+'</section>'
    return layout("Startseite gestalten",body,active="/home-buttons",csrf=csrf,notice=notice)
