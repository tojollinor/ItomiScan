"""Lightweight local scan presets. Replaced by central configuration in Block 4.

Profiles contain only non-secret scanning parameters. Writes are atomic.
"""
import json
import os
import tempfile
from pathlib import Path

FORMATS = ("PDF", "Bild (PNG)")
MODES = ("Color", "Gray", "Lineart", "Halftone")
SOURCES = ("ADF Front", "ADF Back", "ADF Duplex")

DEFAULT_PROFILES = (
    {"name": "Dokument", "mode": "Color", "resolution": 200,
     "source": "ADF Duplex", "output": "PDF"},
    {"name": "Text", "mode": "Gray", "resolution": 300,
     "source": "ADF Duplex", "output": "PDF"},
    {"name": "Foto", "mode": "Color", "resolution": 300,
     "source": "ADF Front", "output": "Bild (PNG)"},
)


class ProfileError(ValueError):
    """Invalid or unwriteable profile configuration."""


def validate_profile(data):
    if not isinstance(data, dict):
        raise ProfileError("Ungültige Profilstruktur.")
    name = data.get("name")
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 32:
        raise ProfileError("Profilname muss 1 bis 32 Zeichen haben.")
    if any(ord(c) < 32 or c in "/\\" for c in name):
        raise ProfileError("Profilname enthält unzulässige Zeichen.")
    mode = data.get("mode")
    if mode not in MODES:
        raise ProfileError("Farbmodus ist ungültig.")
    source = data.get("source")
    if source not in SOURCES:
        raise ProfileError("Einzug ist ungültig.")
    resolution = data.get("resolution")
    if type(resolution) is not int or not 50 <= resolution <= 600:
        raise ProfileError("Auflösung muss zwischen 50 und 600 DPI liegen.")
    output = data.get("output")
    if output not in FORMATS:
        raise ProfileError("Ausgabeformat ist ungültig.")
    return {"name": name.strip(), "mode": mode, "resolution": resolution,
            "source": source, "output": output}


class ProfileStore:
    """User-local JSON store; no database server and no root rights needed."""

    def __init__(self, path=None):
        self.path = Path(path) if path is not None else (
            Path.home() / ".config" / "itomiscan" / "profiles.json")
        self.warning = ""
        self.selected = "Dokument"
        self.profiles = [dict(item) for item in DEFAULT_PROFILES]
        self._load()

    def _load(self):
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or data.get("version") != 1:
                raise ProfileError("Unbekannte Konfigurationsversion.")
            profiles = data.get("profiles")
            if not isinstance(profiles, list) or not 1 <= len(profiles) <= 30:
                raise ProfileError("Ungültige Anzahl Profile.")
            valid = [validate_profile(p) for p in profiles]
            names = [p["name"] for p in valid]
            if len(names) != len(set(names)):
                raise ProfileError("Doppelte Profilnamen.")
            selected = data.get("selected")
            if selected not in names:
                selected = names[0]
        except (OSError, UnicodeError, json.JSONDecodeError, ProfileError) as exc:
            # Never overwrite a damaged configuration just because loading failed.
            self.warning = "Profilkonfiguration nicht lesbar: " + str(exc)
            return
        self.profiles, self.selected = valid, selected

    def names(self):
        return [p["name"] for p in self.profiles]

    def current(self):
        return dict(next(p for p in self.profiles if p["name"] == self.selected))

    def select(self, name):
        if name not in self.names():
            raise ProfileError("Unbekanntes Profil: " + str(name))
        self.selected = name
        self._write()

    def save(self, profile):
        item = validate_profile(profile)
        for index, existing in enumerate(self.profiles):
            if existing["name"] == item["name"]:
                self.profiles[index] = item
                break
        else:
            if len(self.profiles) >= 30:
                raise ProfileError("Maximal 30 Profile möglich.")
            self.profiles.append(item)
        self.selected = item["name"]
        self._write()

    def _write(self):
        if self.warning:
            raise ProfileError(self.warning + " (bitte zuerst reparieren).")
        data = {"version": 1, "selected": self.selected,
                "profiles": self.profiles}
        target = self.path
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8",
                                             dir=str(target.parent), prefix=".profiles-",
                                             suffix=".tmp", delete=False) as stream:
                temporary = Path(stream.name)
                os.chmod(temporary, 0o600)
                json.dump(data, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
        except OSError as exc:
            raise ProfileError("Profile konnten nicht gespeichert werden: " + str(exc)) from exc
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
