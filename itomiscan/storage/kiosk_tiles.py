"""Persistent, validated kiosk tile definitions.

Configuration only: delivery execution and multi-target queueing are handled
separately. Never store credentials or arbitrary commands in tiles.
"""
import json
import re
import sqlite3
from itomiscan.core.profiles import validate_profile

COLORS = ("#192738", "#397edb", "#168080", "#6b4db7",
          "#a35424", "#415b75", "#226744", "#9b3757")
ICONS = ("scan", "printer", "archive", "folder", "file", "copy", "mail", "network")
MAX_TILES = 48


class TileError(ValueError):
    pass


def validate_tile(raw, target_ids=()):
    if not isinstance(raw, dict):
        raise TileError("Ungültiger Startseitenbutton.")
    label = raw.get("label", "")
    if (not isinstance(label, str) or not 1 <= len(label.strip()) <= 42
            or any(ord(c) < 32 for c in label)):
        raise TileError("Beschriftung: 1 bis 42 Zeichen.")
    action = raw.get("action", "scan")
    if action not in ("scan", "group"):
        raise TileError("Unbekannte Buttonaktion.")
    icon = raw.get("icon", "scan")
    if icon not in ICONS:
        raise TileError("Ungültiges Symbol.")
    color = raw.get("color", COLORS[0])
    if not isinstance(color, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
        raise TileError("Ungültige Buttonfarbe.")
    parent = raw.get("parent")
    if parent is not None and (type(parent) is not int or parent < 1):
        raise TileError("Ungültige Gruppe.")
    targets = raw.get("targets", [])
    if (not isinstance(targets, list) or len(targets) > 30 or
            any(type(x) is not int or x < 1 for x in targets) or
            len(targets) != len(set(targets))):
        raise TileError("Ungültige Zielauswahl.")
    if any(x not in set(target_ids) for x in targets):
        raise TileError("Eines der gewählten Ziele existiert nicht mehr.")
    if action == "group" and targets:
        raise TileError("Gruppen können keine Zustellziele enthalten.")
    settings = raw.get("scan", {})
    if action == "group":
        settings = {}
    else:
        if not isinstance(settings, dict):
            raise TileError("Ungültige Scaneinstellungen.")
        settings = validate_profile({
            "name": "Button",
            "mode": settings.get("mode", "Color"),
            "source": settings.get("source", "ADF Duplex"),
            "resolution": settings.get("resolution", 300),
            "output": settings.get("output", "PDF"),
            "settings": settings.get("settings", {}),
        })
        settings.pop("name")
    background = bool(raw.get("background", False))
    return {"label":label.strip(), "action":action, "icon":icon,
            "color":color.lower(), "parent":parent, "targets":targets,
            "scan":settings, "background":background}


def initialize(connection):
    connection.execute("""CREATE TABLE IF NOT EXISTS kiosk_tiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        position INTEGER NOT NULL,
        data TEXT NOT NULL)""")


def list_tiles(connection):
    initialize(connection)
    rows = connection.execute(
        "SELECT id, data FROM kiosk_tiles ORDER BY position,id").fetchall()
    return [dict(json.loads(row["data"]), id=row["id"]) for row in rows]


def save_tile(connection, raw, tile_id=None):
    initialize(connection)
    ids = {r[0] for r in connection.execute("SELECT id FROM targets")}
    tile = validate_tile(raw, ids)
    all_tiles = list_tiles(connection)
    if tile_id is None and len(all_tiles) >= MAX_TILES:
        raise TileError("Maximal 48 Buttons möglich.")
    current = next((x for x in all_tiles if x["id"] == tile_id), None)
    if tile_id is not None and current is None:
        raise TileError("Button nicht gefunden.")
    if tile["parent"] is not None:
        parent = next((x for x in all_tiles if x["id"] == tile["parent"]), None)
        if not parent or parent["action"] != "group" or parent["parent"] is not None:
            raise TileError("Nur eine Gruppenebene ist erlaubt.")
        if tile_id == tile["parent"]:
            raise TileError("Eine Gruppe kann sich nicht selbst enthalten.")
    if tile["action"] == "group" and (
            tile["parent"] is not None or
            current and current["action"] != "group" and
            any(x["parent"] == tile_id for x in all_tiles)):
        raise TileError("Ungültige Gruppenverschachtelung.")
    payload = json.dumps(tile, ensure_ascii=False, separators=(",", ":"))
    if tile_id is None:
        next_position = max((x["position"] for x in _positioned(connection)), default=-1)+1
        connection.execute("INSERT INTO kiosk_tiles(position,data) VALUES(?,?)",
                           (next_position,payload))
    else:
        connection.execute("UPDATE kiosk_tiles SET data=? WHERE id=?",
                           (payload,tile_id))


def _positioned(connection):
    return [dict(row) for row in connection.execute(
        "SELECT id,position FROM kiosk_tiles")]


def delete_tile(connection, tile_id):
    tiles = list_tiles(connection)
    if any(x["parent"] == tile_id for x in tiles):
        raise TileError("Gruppe enthält noch Buttons. Zuerst diese entfernen.")
    cursor = connection.execute("DELETE FROM kiosk_tiles WHERE id=?", (tile_id,))
    if cursor.rowcount != 1:
        raise TileError("Button nicht gefunden.")


def move_tile(connection, tile_id, direction):
    if direction not in (-1, 1):
        raise TileError("Ungültige Sortierung.")
    items = list_tiles(connection)
    selected = next((x for x in items if x["id"] == tile_id), None)
    if not selected:
        raise TileError("Button nicht gefunden.")
    siblings = [x for x in items if x["parent"] == selected["parent"]]
    index = siblings.index(selected)
    destination = index + direction
    if destination < 0 or destination >= len(siblings):
        return
    other = siblings[destination]
    # Persist a stable explicit global order; reorder siblings within it.
    positions = _positioned(connection)
    order = [r["id"] for r in sorted(positions, key=lambda r:r["position"])]
    a, b = order.index(selected["id"]), order.index(other["id"])
    order[a], order[b] = order[b], order[a]
    for position, ident in enumerate(order):
        connection.execute("UPDATE kiosk_tiles SET position=? WHERE id=?",
                           (position,ident))


def public_tiles(connection):
    """No endpoint credentials or target network addresses."""
    return list_tiles(connection)
