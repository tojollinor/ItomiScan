"""Short-lived, single-viewer remote kiosk session and bounded input queue.

Only the authenticated web handler can create leases. A kiosk-side consumer
checks lease freshness independently before generating screenshots or input.
Never accepts shell commands, file names, or arbitrary key symbols.
"""
import hashlib
import sqlite3
import time
from pathlib import Path

LEASE_SECONDS = 25
INPUT_SECONDS = 3
KEYS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789") | {
    "Return", "BackSpace", "Tab", "Escape", "space", "minus", "period", "at",
}
FRAME_SECONDS = 3


def viewer_id(session_token):
    return hashlib.sha256(session_token.encode("ascii")).hexdigest()


class RemoteLive:
    def __init__(self, db_path, *, clock=time.time):
        self.db_path = str(db_path)
        self.frame_path = Path(db_path).parent / "remote-screen.jpg"
        self.clock = clock
        with self._db() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS remote_live (
                slot INTEGER PRIMARY KEY CHECK(slot=1),
                owner TEXT NOT NULL,
                until_time REAL NOT NULL
            )""")
            db.execute("""CREATE TABLE IF NOT EXISTS remote_live_input (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner TEXT NOT NULL,
                kind TEXT NOT NULL,
                x INTEGER NOT NULL DEFAULT 0,
                y INTEGER NOT NULL DEFAULT 0,
                key_name TEXT NOT NULL DEFAULT '',
                created REAL NOT NULL
            )""")

    def _db(self):
        db = sqlite3.connect(self.db_path, timeout=2)
        db.row_factory = sqlite3.Row
        return db

    def start(self, owner):
        if not owner or len(owner) != 64:
            raise ValueError("Ungültige Browser-Sitzung.")
        now = self.clock()
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            entry = db.execute("SELECT owner,until_time FROM remote_live WHERE slot=1").fetchone()
            if entry and entry["until_time"] > now and entry["owner"] != owner:
                raise ValueError("Die Fernsteuerung wird bereits in einem anderen Browser verwendet.")
            db.execute("INSERT OR REPLACE INTO remote_live(slot,owner,until_time) VALUES (1,?,?)",
                       (owner, now + LEASE_SECONDS))
            db.execute("DELETE FROM remote_live_input")
            db.commit()
        self.frame_path.unlink(missing_ok=True)

    def authorized(self, owner):
        with self._db() as db:
            row = db.execute(
                "SELECT 1 FROM remote_live WHERE slot=1 AND owner=? AND until_time>?",
                (owner, self.clock())).fetchone()
        return row is not None

    def active(self):
        with self._db() as db:
            row = db.execute("SELECT owner FROM remote_live WHERE slot=1 AND until_time>?",
                             (self.clock(),)).fetchone()
        if not row:
            self.frame_path.unlink(missing_ok=True)
        return bool(row)

    def ping(self, owner):
        with self._db() as db:
            cur = db.execute("UPDATE remote_live SET until_time=? "
                             "WHERE slot=1 AND owner=? AND until_time>?",
                             (self.clock() + LEASE_SECONDS, owner, self.clock()))
            db.commit()
        if cur.rowcount != 1:
            raise ValueError("Fernsteuerung ist nicht aktiv.")

    def stop(self, owner):
        with self._db() as db:
            db.execute("DELETE FROM remote_live WHERE slot=1 AND owner=?", (owner,))
            db.execute("DELETE FROM remote_live_input WHERE owner=?", (owner,))
            db.commit()
        if not self.active():
            self.frame_path.unlink(missing_ok=True)

    def enqueue(self, owner, kind, *, x=0, y=0, key_name=""):
        if kind == "click":
            if type(x) is not int or type(y) is not int or not 0 <= x <= 1000 or not 0 <= y <= 1000:
                raise ValueError("Ungültige Bildschirmkoordinaten.")
        elif kind == "key":
            if key_name not in KEYS:
                raise ValueError("Taste nicht unterstützt.")
        else:
            raise ValueError("Unbekannte Eingabe.")
        now = self.clock()
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            lease = db.execute(
                "SELECT 1 FROM remote_live WHERE slot=1 AND owner=? AND until_time>?",
                (owner, now)).fetchone()
            if not lease:
                raise ValueError("Fernsteuerung ist nicht aktiv.")
            db.execute("DELETE FROM remote_live_input WHERE created<?", (now - INPUT_SECONDS,))
            queued = db.execute("SELECT count(*) FROM remote_live_input").fetchone()[0]
            if queued >= 5:
                raise ValueError("Zu viele Fernsteuerungs-Eingaben. Bitte warten.")
            db.execute("INSERT INTO remote_live_input(owner,kind,x,y,key_name,created) "
                       "VALUES (?,?,?,?,?,?)", (owner, kind, x, y, key_name, now))
            db.commit()

    def take(self):
        now = self.clock()
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM remote_live_input WHERE created<?", (now - INPUT_SECONDS,))
            row = db.execute(
                "SELECT owner FROM remote_live WHERE slot=1 AND until_time>?",
                (now,)).fetchone()
            if not row:
                db.execute("DELETE FROM remote_live_input")
                db.commit()
                return None
            item = db.execute("SELECT * FROM remote_live_input WHERE owner=? "
                              "ORDER BY id LIMIT 1", (row["owner"],)).fetchone()
            if item:
                db.execute("DELETE FROM remote_live_input WHERE id=?", (item["id"],))
            db.commit()
        return dict(item) if item else None
