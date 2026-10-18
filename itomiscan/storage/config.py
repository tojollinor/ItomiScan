"""Shared SQLite configuration for kiosk and authenticated remote administration.

No third-party packages, no background services on import, no stored plaintext
credentials. The previous profiles.json is read once and never deleted.
"""
import hashlib
import hmac
import ipaddress
import json
import os
import re
import secrets
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit

SETTINGS = {"screensaver_minutes": (1, 60), "device_label": (0, 48)}
TARGET_KINDS = {"paperless", "printer", "network", "email", "usb"}
SCHEMA_VERSION = 1
MIN_PASSWORD_LENGTH = 10
PBKDF2_ITERATIONS = 260000


class ConfigError(ValueError):
    pass


def validate_target(data):
    if not isinstance(data, dict):
        raise ConfigError("Ungültiges Ziel.")
    kind = data.get("kind")
    name = data.get("name", "")
    address = data.get("address", "")
    if kind not in TARGET_KINDS:
        raise ConfigError("Unbekannter Zieltyp.")
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 60:
        raise ConfigError("Name muss 1 bis 60 Zeichen enthalten.")
    if not isinstance(address, str) or not 1 <= len(address.strip()) <= 350:
        raise ConfigError("Adresse muss 1 bis 350 Zeichen enthalten.")
    if any(ord(ch) < 32 for ch in name + address):
        raise ConfigError("Steuerzeichen sind unzulässig.")
    parsed = urlsplit(address)
    schemes = {
        "paperless": {"https", "http"},
        "printer": {"ipp", "ipps", "socket", "lpd", "usb"},
        "network": {"smb"},
        "email": {"smtp", "smtps"},
        "usb": {"usb"},
    }
    if parsed.scheme.lower() not in schemes[kind] or not parsed.hostname:
        raise ConfigError("Ungültige Adresse für " + kind + ".")
    if parsed.username or parsed.password or "@" in parsed.netloc or parsed.query or parsed.fragment:
        raise ConfigError("Keine Kennwörter oder Benutzernamen in Zieladressen speichern.")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ConfigError("Ungültiger Netzwerkport.") from exc
    if port is not None and not 1 <= port <= 65535:
        raise ConfigError("Ungültiger Netzwerkport.")
    if kind == "printer":
        from itomiscan.integrations.printing import PrintError, printer_uri, queue_name
        try:
            queue_name(name.strip())
            printer_uri(address.strip())
        except PrintError as exc:
            raise ConfigError(str(exc)) from exc
    if kind == "paperless" and parsed.scheme != "https":
        raise ConfigError("Paperless benötigt HTTPS.")
    if kind == "usb":
        import re
        if parsed.port is not None or not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", parsed.netloc):
            raise ConfigError("Ungültiger USB-Datenträger.")
        parts = [s for s in parsed.path.split("/") if s]
        if any(not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", s) or s in (".", "..") for s in parts):
            raise ConfigError("Ungültiger USB-Unterordner.")
    return {"kind": kind, "name": name.strip(), "address": address.strip()}


def validate_setting(key, value):
    if key not in SETTINGS:
        raise ConfigError("Unbekannte Einstellung.")
    if key == "screensaver_minutes":
        if type(value) is not int or not 1 <= value <= 60:
            raise ConfigError("Bildschirmschoner: 1 bis 60 Minuten.")
    elif not isinstance(value, str) or len(value) > 48 or any(
            ord(c) < 32 for c in value):
        raise ConfigError("Ungültiger Gerätename.")
    return value


class ConfigStore:
    """Short-lived connections allow kiosk and web process to share configuration."""

    def __init__(self, path=None):
        self.path = Path(path) if path is not None else (
            Path.home() / ".config" / "itomiscan" / "itomiscan.db")
        self.legacy = self.path.parent / "profiles.json"
        self._init_db()

    @contextmanager
    def _connection(self, write=False):
        connection = sqlite3.connect(str(self.path), timeout=8)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA busy_timeout=8000")
            if write:
                connection.execute("BEGIN IMMEDIATE")
            yield connection
            if write:
                connection.commit()
        except Exception:
            if write:
                connection.rollback()
            raise
        finally:
            connection.close()

    def _load_initial_profiles(self):
        from itomiscan.core.profiles import DEFAULT_PROFILES, validate_profile
        if not self.legacy.exists():
            return [validate_profile(item) for item in DEFAULT_PROFILES], "Dokument"
        try:
            data = json.loads(self.legacy.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or data.get("version") != 1:
                raise ConfigError("Unbekannte Version der früheren Profilkonfiguration.")
            records = data.get("profiles")
            if not isinstance(records, list) or not 1 <= len(records) <= 30:
                raise ConfigError("Ungültige Profile im bisherigen Datenbestand.")
            profiles = [validate_profile(item) for item in records]
            names = [p["name"] for p in profiles]
            if len(set(names)) != len(names):
                raise ConfigError("Doppelte Profilnamen in der bisherigen Datei.")
            selected = data.get("selected")
            if selected not in names:
                selected = names[0]
            return profiles, selected
        except (OSError, UnicodeError, ValueError, TypeError) as exc:
            raise ConfigError(
                "Die bisherige profiles.json ist ungültig; Datei nicht verändert: "
                + str(exc)) from exc

    def _init_db(self):
        # Parse legacy profiles before creating a new DB, so invalid files do
        # not silently cause the default profiles to replace old user data.
        initial = self._load_initial_profiles() if not self.path.exists() else None
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.path.parent, 0o700)
        with self._connection(write=True) as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS meta (
                    key TEXT PRIMARY KEY, value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS profiles (
                    name TEXT PRIMARY KEY, data TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY, value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS auth (
                    id INTEGER PRIMARY KEY CHECK(id=1),
                    salt BLOB NOT NULL, hash BLOB NOT NULL,
                    iterations INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS targets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kind TEXT NOT NULL, name TEXT NOT NULL,
                    address TEXT NOT NULL, UNIQUE(kind,name)
                );
                CREATE TABLE IF NOT EXISTS printer_identity (
                    target_id INTEGER PRIMARY KEY, device_uuid TEXT NOT NULL UNIQUE,
                    display_name TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS profile_printers (
                    profile_name TEXT PRIMARY KEY,
                    target_id INTEGER NOT NULL
                );
            """)
            stored = db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
            if stored and int(stored[0]) != SCHEMA_VERSION:
                raise ConfigError("SQLite-Schema nicht unterstützt.")
            db.execute("INSERT OR IGNORE INTO meta (key,value) VALUES ('schema_version','1')")
            count = db.execute("SELECT COUNT(*) FROM profiles").fetchone()[0]
            if count == 0:
                if initial is None:
                    initial = self._load_initial_profiles()
                for profile in initial[0]:
                    db.execute("INSERT INTO profiles (name,data) VALUES (?,?)",
                               (profile["name"], json.dumps(profile, ensure_ascii=False)))
                db.execute("INSERT OR REPLACE INTO settings (key,value) VALUES (?,?)",
                           ("selected_profile", json.dumps(initial[1])))
            db.execute("INSERT OR IGNORE INTO settings (key,value) VALUES (?,?)",
                       ("screensaver_minutes", "5"))
            db.execute("INSERT OR IGNORE INTO settings (key,value) VALUES (?,?)",
                       ("device_label", json.dumps("ItomiScan")))
        os.chmod(self.path, 0o600)
        self.ensure_experiment_profile()

    def ensure_experiment_profile(self):
        """Add the opt-in test preset to existing installations without changing selection."""
        from itomiscan.core.profiles import DEFAULT_PROFILES, validate_profile
        profile = validate_profile(next(p for p in DEFAULT_PROFILES
                                        if p["name"] == "Test / Alle Optionen"))
        with self._connection(write=True) as db:
            existing = db.execute("SELECT 1 FROM profiles WHERE name=?", (profile["name"],)).fetchone()
            count = db.execute("SELECT COUNT(*) FROM profiles").fetchone()[0]
            if not existing and count < 30:
                db.execute("INSERT INTO profiles(name,data) VALUES (?,?)",
                           (profile["name"], json.dumps(profile, ensure_ascii=False)))

    def list_profiles(self):
        with self._connection() as db:
            records = db.execute("SELECT data FROM profiles ORDER BY rowid").fetchall()
            selected = db.execute(
                "SELECT value FROM settings WHERE key='selected_profile'").fetchone()
        profiles = [json.loads(row[0]) for row in records]
        if not profiles:
            raise ConfigError("Keine Scanprofile in der Datenbank.")
        names = {p["name"] for p in profiles}
        choice = json.loads(selected[0]) if selected else profiles[0]["name"]
        return profiles, choice if choice in names else profiles[0]["name"]

    def select_profile(self, name):
        with self._connection(write=True) as db:
            if not db.execute("SELECT 1 FROM profiles WHERE name=?", (name,)).fetchone():
                raise ConfigError("Unbekanntes Profil.")
            db.execute("INSERT OR REPLACE INTO settings(key,value) VALUES (?,?)",
                       ("selected_profile", json.dumps(name)))

    def save_profile(self, profile):
        from itomiscan.core.profiles import validate_profile
        item = validate_profile(profile)
        with self._connection(write=True) as db:
            exists = db.execute("SELECT 1 FROM profiles WHERE name=?",
                                (item["name"],)).fetchone()
            if not exists and db.execute("SELECT COUNT(*) FROM profiles").fetchone()[0] >= 30:
                raise ConfigError("Maximal 30 Profile möglich.")
            db.execute("INSERT OR REPLACE INTO profiles(name,data) VALUES (?,?)",
                       (item["name"], json.dumps(item, ensure_ascii=False)))
            db.execute("INSERT OR REPLACE INTO settings(key,value) VALUES (?,?)",
                       ("selected_profile", json.dumps(item["name"])))

    def get_profile_printer(self, profile_name):
        with self._connection() as db:
            row = db.execute(
                "SELECT pp.target_id FROM profile_printers pp "
                "JOIN targets t ON t.id=pp.target_id AND t.kind='printer' "
                "WHERE pp.profile_name=?", (profile_name,)).fetchone()
        return row[0] if row else None

    def set_profile_printer(self, profile_name, target_id):
        with self._connection(write=True) as db:
            if not db.execute("SELECT 1 FROM profiles WHERE name=?",
                              (profile_name,)).fetchone():
                raise ConfigError("Unbekanntes Scanprofil.")
            if target_id is None:
                db.execute("DELETE FROM profile_printers WHERE profile_name=?",
                           (profile_name,))
            else:
                target = db.execute(
                    "SELECT 1 FROM targets WHERE id=? AND kind='printer'",
                    (target_id,)).fetchone()
                if target is None:
                    raise ConfigError("Druckerziel nicht eingerichtet.")
                db.execute("INSERT OR REPLACE INTO profile_printers "
                           "(profile_name,target_id) VALUES (?,?)",
                           (profile_name, target_id))

    def get_settings(self):
        with self._connection() as db:
            rows = db.execute("SELECT key,value FROM settings").fetchall()
        result = {row["key"]: json.loads(row["value"]) for row in rows}
        return {key: result.get(key, 5 if key == "screensaver_minutes" else "ItomiScan")
                for key in SETTINGS}

    def set_settings(self, values):
        if not isinstance(values, dict) or any(k not in SETTINGS for k in values):
            raise ConfigError("Unbekannte Einstellung.")
        for key, value in values.items():
            validate_setting(key, value)
        with self._connection(write=True) as db:
            for key, value in values.items():
                db.execute("INSERT OR REPLACE INTO settings(key,value) VALUES (?,?)",
                           (key, json.dumps(value, ensure_ascii=False)))

    def list_targets(self):
        with self._connection() as db:
            rows = db.execute(
                "SELECT id,kind,name,address FROM targets ORDER BY kind,name").fetchall()
        return [dict(row) for row in rows]

    def save_target(self, target):
        data = validate_target(target)
        with self._connection(write=True) as db:
            db.execute("INSERT INTO targets (kind,name,address) VALUES (?,?,?) "
                       "ON CONFLICT(kind,name) DO UPDATE SET address=excluded.address",
                       (data["kind"], data["name"], data["address"]))

    def printer_identities(self):
        with self._connection() as db:
            rows = db.execute(
                "SELECT pi.target_id,pi.device_uuid,pi.display_name FROM printer_identity pi "
                "JOIN targets t ON t.id=pi.target_id WHERE t.kind='printer'").fetchall()
        return {r["target_id"]:{"identity":r["device_uuid"],"name":r["display_name"]}
                for r in rows}

    def assign_printer_identity(self, target_id, identity, display_name):
        if (type(target_id) is not int or target_id <= 0 or
                not isinstance(identity,str) or not re.fullmatch(
                    r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}",identity) or
                not isinstance(display_name,str) or
                not 1 <= len(display_name.strip()) <= 80):
            raise ConfigError("Ungültige Druckeridentität.")
        with self._connection(write=True) as db:
            row=db.execute("SELECT 1 FROM targets WHERE id=? AND kind='printer'",
                           (target_id,)).fetchone()
            if not row:
                raise ConfigError("Druckerziel existiert nicht.")
            db.execute("INSERT INTO printer_identity "
                       "(target_id,device_uuid,display_name) VALUES(?,?,?) "
                       "ON CONFLICT(target_id) DO UPDATE SET "
                       "device_uuid=excluded.device_uuid,display_name=excluded.display_name",
                       (target_id,identity,display_name.strip()))

    def update_target_address(self, target_id, address, *, kind="printer"):
        """Update an existing target by ID, never silently create a new target."""
        if type(target_id) is not int or target_id <= 0:
            raise ConfigError("Ungültige Ziel-ID.")
        with self._connection(write=True) as db:
            row = db.execute("SELECT kind,name FROM targets WHERE id=?",
                             (target_id,)).fetchone()
            if not row or row["kind"] != kind:
                raise ConfigError("Ziel existiert nicht.")
            data = validate_target({"kind": kind, "name": row["name"],
                                    "address": address})
            db.execute("UPDATE targets SET address=? WHERE id=?",
                       (data["address"], target_id))

    def delete_target(self, target_id):
        if type(target_id) is not int or target_id <= 0:
            raise ConfigError("Ungültige Ziel-ID.")
        with self._connection(write=True) as db:
            db.execute("DELETE FROM profile_printers WHERE target_id=?", (target_id,))
            db.execute("DELETE FROM printer_identity WHERE target_id=?", (target_id,))
            db.execute("DELETE FROM targets WHERE id=?", (target_id,))

    def has_password(self):
        with self._connection() as db:
            return db.execute("SELECT 1 FROM auth WHERE id=1").fetchone() is not None

    def set_password(self, password):
        if not isinstance(password, str) or not 10 <= len(password) <= 128:
            raise ConfigError("Administratorpasswort: 10 bis 128 Zeichen.")
        salt = secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
        with self._connection(write=True) as db:
            db.execute("INSERT OR REPLACE INTO auth (id,salt,hash,iterations) "
                       "VALUES(1,?,?,?)", (salt, digest, PBKDF2_ITERATIONS))

    def verify_password(self, password):
        if not isinstance(password, str) or len(password) > 128:
            return False
        with self._connection() as db:
            auth = db.execute("SELECT salt,hash,iterations FROM auth WHERE id=1").fetchone()
        if not auth:
            return False
        calculated = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), auth["salt"], auth["iterations"])
        return hmac.compare_digest(calculated, auth["hash"])

    def backup(self):
        profiles, selected = self.list_profiles()
        with self._connection() as db:
            printers = db.execute(
                "SELECT pp.profile_name,t.name FROM profile_printers pp "
                "JOIN targets t ON t.id=pp.target_id AND t.kind='printer'"
            ).fetchall()
        printer_map = {row[0]: row[1] for row in printers}
        identity_map = self.printer_identities()
        printer_identity_export = {
            t["name"]: identity_map[t["id"]] for t in self.list_targets()
            if t["kind"] == "printer" and t["id"] in identity_map}
        return {"version": 1, "profiles": profiles, "selected": selected,
                "targets": [{k: item[k] for k in ("kind","name","address")}
                            for item in self.list_targets()],
                "settings": self.get_settings(),
                "profile_printers": printer_map,
                "printer_identities": printer_identity_export,
                "note": "Enthält keine Passwörter, Tokens oder Sitzungsdaten."}

    def restore(self, payload):
        from itomiscan.core.profiles import validate_profile
        if not isinstance(payload, dict) or payload.get("version") != 1:
            raise ConfigError("Unbekanntes Sicherungsformat.")
        profiles = payload.get("profiles")
        targets = payload.get("targets")
        settings = payload.get("settings")
        if not isinstance(profiles, list) or not 1 <= len(profiles) <= 30:
            raise ConfigError("Ungültige Scanprofile.")
        valid_profiles = [validate_profile(item) for item in profiles]
        names = [p["name"] for p in valid_profiles]
        if len(set(names)) != len(names) or payload.get("selected") not in names:
            raise ConfigError("Doppelte Profile oder ungültige Auswahl.")
        if not isinstance(targets, list) or len(targets) > 100:
            raise ConfigError("Ungültige Anzahl Zielsysteme.")
        valid_targets = [validate_target(item) for item in targets]
        combos = [(t["kind"], t["name"]) for t in valid_targets]
        if len(combos) != len(set(combos)):
            raise ConfigError("Doppelte Zielsysteme.")
        if not isinstance(settings, dict) or set(settings) != SETTINGS.keys():
            raise ConfigError("Ungültige Einstellungen.")
        profile_printers = payload.get("profile_printers", {})
        valid_printers = {t["name"] for t in valid_targets if t["kind"] == "printer"}
        if (not isinstance(profile_printers, dict)
                or any(not isinstance(k, str) or not isinstance(v, str)
                       or k not in names or v not in valid_printers
                       for k, v in profile_printers.items())):
            raise ConfigError("Ungültige Profil-Druckerzuordnung.")
        for key, value in settings.items():
            validate_setting(key, value)
        with self._connection(write=True) as db:
            db.execute("DELETE FROM profiles")
            for item in valid_profiles:
                db.execute("INSERT INTO profiles(name,data) VALUES(?,?)",
                           (item["name"], json.dumps(item, ensure_ascii=False)))
            db.execute("DELETE FROM profile_printers")
            db.execute("DELETE FROM targets")
            for item in valid_targets:
                db.execute("INSERT INTO targets(kind,name,address) VALUES(?,?,?)",
                           (item["kind"], item["name"], item["address"]))
            for name, printer in profile_printers.items():
                row = db.execute(
                    "SELECT id FROM targets WHERE kind='printer' AND name=?",
                    (printer,)).fetchone()
                db.execute("INSERT INTO profile_printers(profile_name,target_id) "
                           "VALUES (?,?)", (name, row[0]))
            db.execute("INSERT OR REPLACE INTO settings (key,value) VALUES(?,?)",
                       ("selected_profile", json.dumps(payload["selected"])))
            for key, value in settings.items():
                db.execute("INSERT OR REPLACE INTO settings (key,value) VALUES (?,?)",
                           (key, json.dumps(value, ensure_ascii=False)))
