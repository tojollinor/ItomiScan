"""Validated profiles stored centrally in SQLite since Block 4.

The old profiles.json is migrated once, retained as an unmodified fallback.
"""
import re
from itomiscan.storage.config import ConfigError, ConfigStore

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
    # Diagnostic preset: the GUI exposes every option detected by SANE.
    # Do not force contradictory scanner capabilities on simultaneously.
    {"name": "Test / Alle Optionen", "mode": "Color", "resolution": 300,
     "source": "ADF Duplex", "output": "PDF"},
)



# Enable independent image enhancements, not contradictory device settings.
# The complete set of recognized SANE controls stays editable in the GUI.
EXPERIMENT_ENABLE = frozenset((
    "--swdeskew", "--swdespeck", "--swcrop", "--overscan", "--lowmemory",
))


def experiment_settings(options):
    """Choose only advertised, active capabilities for a diagnostic preset."""
    selected = {}
    for opt in options:
        flag = opt.get("flag")
        if opt.get("inactive") or not flag:
            continue
        choices = opt.get("choices") or ()
        if flag == "--mode" and "Color" in choices:
            selected[flag] = "Color"
        elif flag == "--source" and "ADF Duplex" in choices:
            selected[flag] = "ADF Duplex"
        elif flag == "--resolution":
            if opt.get("kind") == "enum" and "300" in choices:
                selected[flag] = "300"
        elif flag in EXPERIMENT_ENABLE and opt.get("kind") == "bool" and "yes" in choices:
            selected[flag] = "yes"
    return selected


class ProfileError(ValueError):
    pass


def validate_profile(data):
    if not isinstance(data, dict):
        raise ProfileError("Ungültige Profilstruktur.")
    name = data.get("name")
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 32:
        raise ProfileError("Profilname muss 1 bis 32 Zeichen haben.")
    if any(ord(c) < 32 or c == "\\" for c in name):
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
    settings = data.get("settings", {})
    if not isinstance(settings, dict) or len(settings) > 75:
        raise ProfileError("Ungültige zusätzliche Scaneinstellungen.")
    clean = {}
    for flag, value in settings.items():
        if not isinstance(flag, str) or not re.fullmatch(
                r"(?:--[a-z][a-z0-9-]*|-[ltxy])", flag):
            raise ProfileError("Ungültiger Scannerparameter.")
        if not isinstance(value, str) or len(value) > 120 or any(
                ord(character) < 32 for character in value):
            raise ProfileError("Ungültiger Scannerwert.")
        clean[flag] = value
    return {"name": name.strip(), "mode": mode, "resolution": resolution,
            "source": source, "output": output, "settings": clean}


class ProfileStore:
    """Compatibility facade: live-read shared SQLite on kiosk/web requests."""

    def __init__(self, path=None):
        self.warning = ""
        self.profiles = [dict(p) for p in DEFAULT_PROFILES]
        self.selected = "Dokument"
        self.db = None
        self.path = None
        try:
            self.db = ConfigStore(path)
            self.path = self.db.path
            self.reload()
        except (ConfigError, OSError, ValueError) as exc:
            self.warning = "Profilkonfiguration nicht lesbar: " + str(exc)

    def reload(self):
        if self.db is None:
            return
        self.profiles, self.selected = self.db.list_profiles()

    def names(self):
        self.reload()
        return [p["name"] for p in self.profiles]

    def current(self):
        self.reload()
        return dict(next(p for p in self.profiles if p["name"] == self.selected))

    def select(self, name):
        if self.warning:
            raise ProfileError(self.warning)
        try:
            self.db.select_profile(name)
            self.reload()
        except (ConfigError, OSError) as exc:
            raise ProfileError(str(exc)) from exc

    def save(self, profile):
        if self.warning:
            raise ProfileError(self.warning)
        try:
            self.db.save_profile(validate_profile(profile))
            self.reload()
        except (ConfigError, OSError) as exc:
            raise ProfileError(str(exc)) from exc
