"""Owner-scoped durable scan snapshots; immutable assets precede DB commits."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import uuid

from itomiscan.storage.config import ConfigStore


class DraftStore:
    def __init__(self, path=None):
        self.config = ConfigStore(path)
        self.root = self.config.path.parent / "drafts"
        self.assets = self.root / "assets"
        self.assets.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._cache = {}
        with self.config._connection(write=True) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS scan_drafts (
                owner TEXT PRIMARY KEY, data TEXT NOT NULL)""")

    @staticmethod
    def owner(user_id):
        if user_id is None:
            return "device"
        if type(user_id) is not int or user_id < 1:
            raise ValueError("Ungültiger Entwurfseigentümer.")
        return f"user:{user_id}"

    def _asset(self, source):
        source = Path(source)
        stat = source.stat()
        key = (str(source.resolve()), stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
        cached = self._cache.get(key)
        if cached and (self.assets / cached).is_file():
            return cached
        digest = hashlib.sha256()
        descriptor, temporary = tempfile.mkstemp(dir=self.assets, prefix=".writing-")
        try:
            with os.fdopen(descriptor, "wb") as output, source.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 256), b""):
                    digest.update(block)
                    output.write(block)
                output.flush()
                os.fsync(output.fileno())
            suffix = source.suffix.lower()
            if suffix not in (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".pnm"):
                raise ValueError("Unbekanntes Seitenformat.")
            name = digest.hexdigest() + suffix
            destination = self.assets / name
            if not destination.exists():
                os.replace(temporary, destination)
                if os.name == "posix":
                    fd = os.open(self.assets, os.O_RDONLY | os.O_DIRECTORY)
                    try:
                        os.fsync(fd)
                    finally:
                        os.close(fd)
            self._cache[key] = name
            return name
        finally:
            Path(temporary).unlink(missing_ok=True)

    def save(self, user_id, pages, state):
        owner = self.owner(user_id)
        # Serialize before any writes; never accept non-JSON application objects.
        state = json.loads(json.dumps(state, allow_nan=False))
        assets = [self._asset(page) for page in pages]
        with self.config._connection(write=True) as db:
            row = db.execute("SELECT data FROM scan_drafts WHERE owner=?", (owner,)).fetchone()
            previous = json.loads(row[0]) if row else {}
            originals = previous.get("originals", {})
            for page, asset in zip(pages, assets):
                originals.setdefault(str(Path(page).resolve()), asset)
            data = json.dumps({"pages": assets, "originals": originals, "state": state},
                              sort_keys=True, ensure_ascii=False, allow_nan=False)
            if row and row[0] == data:
                return False
            db.execute("INSERT OR REPLACE INTO scan_drafts(owner,data) VALUES(?,?)", (owner, data))
        return True

    def load(self, user_id):
        with self.config._connection() as db:
            row = db.execute("SELECT data FROM scan_drafts WHERE owner=?",
                             (self.owner(user_id),)).fetchone()
        if not row:
            return None
        data = json.loads(row[0])
        for name in [*data["pages"], *data["originals"].values()]:
            if (not isinstance(name, str) or Path(name).name != name
                    or not (self.assets / name).is_file()):
                raise OSError("Gesicherte Dokumentseite nicht verfügbar.")
        return data

    def restore(self, user_id):
        import shutil
        data = self.load(user_id)
        if data is None:
            return None
        folder = self.root / ("work-" + uuid.uuid4().hex)
        folder.mkdir(mode=0o700)
        pages = []
        for index, name in enumerate(data["pages"]):
            destination = folder / (f"page-{index:04d}" + Path(name).suffix)
            shutil.copyfile(self.assets / name, destination)
            pages.append(destination)
        return pages, folder, data["state"]

    def finish(self, user_id):
        # Only explicit completion/discard removes the manifest. Never delete
        # document data here; output and queued delivery may still reference it.
        with self.config._connection(write=True) as db:
            db.execute("DELETE FROM scan_drafts WHERE owner=?", (self.owner(user_id),))
