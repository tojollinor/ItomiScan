"""Optional local PIN accounts and centrally enforced scanner permissions.

PINs are hashed and never exported. The kiosk and web management share SQLite.
A global persisted lockout slows PIN guessing on the physical touch panel.
"""
import hashlib
import hmac
import json
import re
import secrets
import time

from itomiscan.storage.config import ConfigError, ConfigStore


PERMISSIONS = ("scan", "paperless", "copy", "network", "email", "usb",
               "update", "shutdown", "exit")
FEATURES = {
    "scan": "Scannen", "paperless": "Paperless", "copy": "Kopieren",
    "network": "Netzwerkordner", "email": "E-Mail", "usb": "USB",
    "update": "Update", "shutdown": "Ausschalten", "exit": "Beenden",
}
DEFAULT_PERMISSIONS = ("scan",)
PIN_ITERATIONS = 150000
MAX_USERS = 20
MAX_TRIES = 5
LOCK_SECONDS = 180


class PinError(ConfigError):
    """PIN login or account validation failed."""


def check_pin(pin):
    if not isinstance(pin, str) or not re.fullmatch(r"[0-9]{4,6}", pin):
        raise PinError("PIN muss aus 4 bis 6 Ziffern bestehen.")
    return pin


def validate_permissions(permissions):
    if not isinstance(permissions, (list, tuple, set)) or len(permissions) > len(PERMISSIONS):
        raise PinError("Ungültige Funktionsauswahl.")
    if any(key not in PERMISSIONS for key in permissions):
        raise PinError("Unbekannte Funktionsberechtigung.")
    return [key for key in PERMISSIONS if key in permissions]


class UserStore:
    """No implicit enablement, and no security-sensitive backup export."""

    def __init__(self, path=None, *, clock=time.time):
        self.config = ConfigStore(path)
        self.clock = clock
        with self.config._connection(write=True) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS pin_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                active INTEGER NOT NULL CHECK(active IN (0,1)),
                salt BLOB NOT NULL,
                digest BLOB NOT NULL,
                iterations INTEGER NOT NULL,
                permissions TEXT NOT NULL,
                assigned_profiles TEXT NOT NULL,
                default_profile TEXT NOT NULL
            )""")
            db.execute("""CREATE TABLE IF NOT EXISTS pin_state (
                id INTEGER PRIMARY KEY CHECK(id=1),
                enabled INTEGER NOT NULL CHECK(enabled IN (0,1)),
                timeout_minutes INTEGER NOT NULL,
                failures INTEGER NOT NULL,
                locked_until REAL NOT NULL
            )""")
            db.execute("""INSERT OR IGNORE INTO pin_state
                (id,enabled,timeout_minutes,failures,locked_until)
                VALUES(1,0,1,0,0)""")

    def settings(self):
        with self.config._connection() as db:
            row = db.execute(
                "SELECT enabled,timeout_minutes,locked_until FROM pin_state WHERE id=1"
            ).fetchone()
        return {
            "enabled": bool(row["enabled"]),
            "timeout_minutes": row["timeout_minutes"],
            "locked_seconds": max(0, int(row["locked_until"] - self.clock()) + 1)
                              if row["locked_until"] > self.clock() else 0,
        }

    def list_users(self):
        with self.config._connection() as db:
            records = db.execute("""SELECT id,name,active,permissions,
                assigned_profiles,default_profile FROM pin_users ORDER BY name COLLATE NOCASE
            """).fetchall()
        return [self._public(item) for item in records]

    @staticmethod
    def _public(row):
        return {
            "id": row["id"], "name": row["name"],
            "active": bool(row["active"]),
            "permissions": json.loads(row["permissions"]),
            "assigned_profiles": json.loads(row["assigned_profiles"]),
            "default_profile": row["default_profile"],
        }

    def get_user(self, user_id):
        with self.config._connection() as db:
            row = db.execute("""SELECT id,name,active,permissions,assigned_profiles,
                default_profile FROM pin_users WHERE id=?""", (user_id,)).fetchone()
        return self._public(row) if row else None

    def _profile_selection(self, assigned, default):
        available = [p["name"] for p in self.config.list_profiles()[0]]
        if not isinstance(assigned, (list, tuple)) or not assigned or len(assigned) > 30:
            raise PinError("Mindestens ein Scanprofil zuweisen.")
        if len(assigned) != len(set(assigned)) or any(
                not isinstance(p, str) or p not in available for p in assigned):
            raise PinError("Unbekannte oder doppelte Profilzuweisung.")
        if default not in assigned:
            raise PinError("Standardprofil muss einem zugewiesenen Profil entsprechen.")
        return [p for p in available if p in assigned]

    def save_user(self, *, user_id=None, name, pin=None, permissions,
                  assigned_profiles, default_profile, active=True):
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 40 or any(
                ord(ch) < 32 or ch in "<>&\"'" for ch in name):
            raise PinError("Benutzername muss 1 bis 40 Zeichen enthalten.")
        name = name.strip()
        allowed = validate_permissions(permissions)
        profiles = self._profile_selection(assigned_profiles, default_profile)
        if type(active) is not bool:
            raise PinError("Ungültiger Benutzerstatus.")
        if user_id is not None and (type(user_id) is not int or user_id <= 0):
            raise PinError("Ungültige Benutzer-ID.")
        if user_id is None and not pin:
            raise PinError("Neue Benutzer benötigen eine PIN.")
        if pin:
            check_pin(pin)
        elif pin is not None and not isinstance(pin, str):
            raise PinError("Ungültige PIN.")

        with self.config._connection(write=True) as db:
            old = None
            if user_id is not None:
                old = db.execute("SELECT * FROM pin_users WHERE id=?", (user_id,)).fetchone()
                if not old:
                    raise PinError("Benutzer existiert nicht.")
            elif db.execute("SELECT COUNT(*) FROM pin_users").fetchone()[0] >= MAX_USERS:
                raise PinError("Maximal 20 Benutzer sind möglich.")
            conflict = db.execute(
                "SELECT id FROM pin_users WHERE name=? AND id!=?",
                (name, user_id or -1)).fetchone()
            if conflict:
                raise PinError("Benutzername existiert bereits.")
            if pin:
                # Verify uniqueness without ever storing or comparing plaintext PINs.
                for row in db.execute(
                        "SELECT id,salt,digest,iterations FROM pin_users WHERE id!=?",
                        (user_id or -1,)):
                    calculated = hashlib.pbkdf2_hmac(
                        "sha256", pin.encode("ascii"), row["salt"], row["iterations"])
                    if hmac.compare_digest(calculated, row["digest"]):
                        raise PinError("Diese PIN ist bereits einem Benutzer zugeordnet.")
                salt = secrets.token_bytes(16)
                digest = hashlib.pbkdf2_hmac(
                    "sha256", pin.encode("ascii"), salt, PIN_ITERATIONS)
                iterations = PIN_ITERATIONS
            else:
                salt, digest, iterations = old["salt"], old["digest"], old["iterations"]
            enabled = bool(db.execute(
                "SELECT enabled FROM pin_state WHERE id=1").fetchone()[0])
            remaining = db.execute(
                "SELECT COUNT(*) FROM pin_users WHERE active=1 AND id!=?",
                (user_id or -1,)).fetchone()[0]
            if enabled and not active and remaining == 0:
                raise PinError("Mindestens ein aktiver Benutzer muss angemeldet werden können.")
            if old:
                db.execute("""UPDATE pin_users SET name=?,active=?,salt=?,digest=?,
                    iterations=?,permissions=?,assigned_profiles=?,default_profile=?
                    WHERE id=?""", (
                    name, int(active), salt, digest, iterations,
                    json.dumps(allowed), json.dumps(profiles), default_profile, user_id))
                return user_id
            cursor = db.execute("""INSERT INTO pin_users
                (name,active,salt,digest,iterations,permissions,assigned_profiles,default_profile)
                VALUES(?,?,?,?,?,?,?,?)""", (
                name, int(active), salt, digest, iterations, json.dumps(allowed),
                json.dumps(profiles), default_profile))
            return cursor.lastrowid

    def delete_user(self, user_id):
        if type(user_id) is not int or user_id <= 0:
            raise PinError("Ungültige Benutzer-ID.")
        with self.config._connection(write=True) as db:
            exists = db.execute(
                "SELECT active FROM pin_users WHERE id=?", (user_id,)).fetchone()
            if not exists:
                raise PinError("Benutzer existiert nicht.")
            on = bool(db.execute(
                "SELECT enabled FROM pin_state WHERE id=1").fetchone()[0])
            others = db.execute(
                "SELECT COUNT(*) FROM pin_users WHERE active=1 AND id!=?",
                (user_id,)).fetchone()[0]
            if on and exists["active"] and not others:
                raise PinError("Letzten aktiven Benutzer nicht löschen.")
            db.execute("DELETE FROM pin_users WHERE id=?", (user_id,))

    def configure(self, *, enabled=None, timeout_minutes=None):
        if enabled is not None and type(enabled) is not bool:
            raise PinError("Ungültiger Aktivierungsstatus.")
        if timeout_minutes is not None and (type(timeout_minutes) is not int
                                             or not 1 <= timeout_minutes <= 60):
            raise PinError("Abmeldung zwischen 1 und 60 Minuten einstellen.")
        with self.config._connection(write=True) as db:
            if enabled:
                active = db.execute(
                    "SELECT COUNT(*) FROM pin_users WHERE active=1").fetchone()[0]
                if not active:
                    raise PinError("Vor Aktivierung einen aktiven Benutzer mit PIN erstellen.")
            if enabled is not None:
                db.execute("UPDATE pin_state SET enabled=?,failures=0,locked_until=0 WHERE id=1",
                           (int(enabled),))
            if timeout_minutes is not None:
                db.execute("UPDATE pin_state SET timeout_minutes=? WHERE id=1",
                           (timeout_minutes,))

    def verify_pin(self, pin):
        """Return a sanitized account or None. Rate limiting persists across app restart."""
        if not isinstance(pin, str) or not re.fullmatch(r"[0-9]{4,6}", pin):
            return None
        with self.config._connection(write=True) as db:
            state = db.execute(
                "SELECT enabled,failures,locked_until FROM pin_state WHERE id=1").fetchone()
            if not state["enabled"] or state["locked_until"] > self.clock():
                return None
            match = None
            for row in db.execute("SELECT * FROM pin_users WHERE active=1"):
                calculated = hashlib.pbkdf2_hmac(
                    "sha256", pin.encode("ascii"), row["salt"], row["iterations"])
                if hmac.compare_digest(calculated, row["digest"]):
                    match = row
            if match:
                db.execute("UPDATE pin_state SET failures=0,locked_until=0 WHERE id=1")
                return self._public(match)
            failures = (state["failures"] if state["locked_until"] <= 0 else 0) + 1
            until = self.clock() + LOCK_SECONDS if failures >= MAX_TRIES else 0
            db.execute("UPDATE pin_state SET failures=?, locked_until=? WHERE id=1",
                       (failures, until))
            return None

    def authorized(self, user_id, permission):
        """Re-read DB on every sensitive action; hidden buttons are not the boundary."""
        if permission not in PERMISSIONS:
            return False
        with self.config._connection() as db:
            state = db.execute("SELECT enabled FROM pin_state WHERE id=1").fetchone()
            if not state["enabled"]:
                return True
            if type(user_id) is not int:
                return False
            row = db.execute("""SELECT active,permissions FROM pin_users
                WHERE id=?""", (user_id,)).fetchone()
        return bool(row and row["active"] and permission in json.loads(row["permissions"]))
