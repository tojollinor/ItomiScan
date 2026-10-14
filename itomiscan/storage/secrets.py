"""Permissions-restricted integration credentials, separate from public JSON exports.

No credentials are stored in SQLite, command arguments, user-visible pages or
configuration backups. A removed target's credentials remain until explicitly
cleared to avoid breaking already-spooled work.
"""
import json
import os
import tempfile
from pathlib import Path


class SecretError(ValueError):
    pass


class SecretStore:
    def __init__(self, db_path):
        self.path = Path(db_path).parent / "integrations-secrets.json"

    def _read(self):
        if not self.path.exists():
            return {}
        if self.path.is_symlink() or (self.path.stat().st_mode & 0o077):
            raise SecretError("Unsichere Zugriffsrechte auf Integrations-Zugangsdaten.")
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise SecretError("Zugangsdaten beschädigt.")
        return data

    def get(self, target_id):
        return dict(self._read().get(str(int(target_id)), {}))

    def update(self, target_id, *, token=None, username=None, password=None,
               sender=None, clear=False):
        key = str(int(target_id))
        current = self._read()
        if clear:
            current.pop(key, None)
        else:
            item = dict(current.get(key, {}))
            for field, value in (("token", token), ("username", username),
                                 ("password", password), ("sender", sender)):
                if value is not None:
                    if not isinstance(value, str) or len(value) > 400 or any(
                            ord(x) < 32 for x in value):
                        raise SecretError("Ungültiger Zugangsdatenwert.")
                    if value:
                        item[field] = value
                    else:
                        item.pop(field, None)
            current[key] = item
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.path.parent, 0o700)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                    mode="w", encoding="utf-8", dir=self.path.parent,
                    prefix=".itomi-secret-", delete=False) as f:
                temporary = Path(f.name)
                os.chmod(temporary, 0o600)
                json.dump(current, f, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
