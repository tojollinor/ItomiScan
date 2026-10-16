"""Short-lived, single-consumer web-to-kiosk command queue.

Web requests are authenticated and CSRF-checked by the HTTP handler before
they reach this module. The kiosk validates local permissions independently.
Commands cannot execute shell code or access arbitrary files.
"""
import sqlite3
import time

ACTIONS = frozenset(("scan", "open_scan", "home", "restart", "poweroff"))
MAX_AGE = 30


class RemoteCommands:
    def __init__(self, db_path, clock=time.time):
        self.db_path = str(db_path)
        self.clock = clock
        with self._connect() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS remote_commands (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT NOT NULL,
                    created REAL NOT NULL,
                    status TEXT NOT NULL,
                    detail TEXT NOT NULL DEFAULT ''
                )
            """)

    def _connect(self):
        db = sqlite3.connect(self.db_path, timeout=5)
        db.row_factory = sqlite3.Row
        return db

    def request(self, action):
        if action not in ACTIONS:
            raise ValueError("Unbekannte Fernbedienungsaktion.")
        now = self.clock()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("UPDATE remote_commands SET status='expired' "
                       "WHERE status='pending' AND created<?",
                       (now - MAX_AGE,))
            if db.execute("SELECT 1 FROM remote_commands WHERE status='pending'"
                          ).fetchone():
                raise ValueError("Eine Fernbedienungsaktion wartet bereits.")
            result = db.execute(
                "INSERT INTO remote_commands(action,created,status) VALUES (?,?,'pending')",
                (action, now))
            db.execute("DELETE FROM remote_commands WHERE id < ?",
                       (max(0, result.lastrowid - 50),))
            return result.lastrowid

    def take(self):
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT id,action,created FROM remote_commands "
                "WHERE status='pending' ORDER BY id LIMIT 1").fetchone()
            if row is None:
                return None
            if self.clock() - row["created"] > MAX_AGE:
                db.execute("UPDATE remote_commands SET status='expired' WHERE id=?",
                           (row["id"],))
                return None
            db.execute("UPDATE remote_commands SET status='received' WHERE id=?",
                       (row["id"],))
            return dict(row)

    def finish(self, command_id, status, detail=""):
        if status not in ("done", "rejected", "error"):
            raise ValueError("Ungültiger Befehlsstatus.")
        with self._connect() as db:
            db.execute("UPDATE remote_commands SET status=?,detail=? WHERE id=?",
                       (status, str(detail)[:180], command_id))

    def latest(self):
        with self._connect() as db:
            row = db.execute(
                "SELECT id,action,status,detail FROM remote_commands "
                "ORDER BY id DESC LIMIT 1").fetchone()
        return dict(row) if row else None
