"""Crash-resilient PDF spool with transactional SQLite delivery statuses.

The original scan is never deleted. Spool files remain even after success for
manual recovery; retention/reconciliation is a release-hardening topic.
"""
import hashlib
import os
from pathlib import Path
import shutil
import sqlite3
import time
import uuid
import json

from itomiscan.storage.config import ConfigStore, ConfigError

MAX_SPOOL_BYTES = 2 * 1024 * 1024 * 1024
MAX_JOB_BYTES = 150 * 1024 * 1024
MAX_JOBS = 500
RETRY_SECONDS = (60, 120, 300, 900, 1800, 3600)
LEASE_SECONDS = 600
NON_IDEMPOTENT = {"paperless", "email", "printer"}


class QueueError(ConfigError):
    pass


class DeliveryQueue:
    def __init__(self, db_path=None, *, clock=time.time):
        self.db = ConfigStore(db_path)
        self.clock = clock
        self.folder = self.db.path.parent / "spool"
        self.folder.mkdir(parents=True, mode=0o700, exist_ok=True)
        os.chmod(self.folder, 0o700)
        with self.db._connection(write=True) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS delivery_jobs (
                id TEXT PRIMARY KEY, target_id INTEGER NOT NULL,
                kind TEXT NOT NULL, target_name TEXT NOT NULL,
                target_address TEXT NOT NULL, filename TEXT NOT NULL,
                digest TEXT NOT NULL, size_bytes INTEGER NOT NULL,
                created_at REAL NOT NULL,
                status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
                retry_at REAL NOT NULL, leased_until REAL NOT NULL DEFAULT 0,
                last_error TEXT NOT NULL DEFAULT '', receipt TEXT NOT NULL DEFAULT ''
            )""")
            db.execute("""CREATE INDEX IF NOT EXISTS delivery_jobs_pending
                ON delivery_jobs(status,retry_at)""")
            # Online migration of queues created in Block 6. Existing jobs
            # retain defaults and all scanned PDF files remain untouched.
            existing = {row["name"] for row in db.execute("PRAGMA table_info(delivery_jobs)")}
            if "batch_id" not in existing:
                db.execute("ALTER TABLE delivery_jobs ADD COLUMN batch_id TEXT NOT NULL DEFAULT ''")
            db.execute("""CREATE TABLE IF NOT EXISTS delivery_batches (
                id TEXT PRIMARY KEY, created_at REAL NOT NULL,
                label TEXT NOT NULL, background INTEGER NOT NULL DEFAULT 0,
                owner_id INTEGER, source TEXT NOT NULL,
                read_at REAL NOT NULL DEFAULT 0
            )""")
            if "print_copies" not in existing:
                db.execute("ALTER TABLE delivery_jobs ADD COLUMN print_copies INTEGER NOT NULL DEFAULT 1")
            if "print_sides" not in existing:
                db.execute("ALTER TABLE delivery_jobs ADD COLUMN print_sides TEXT NOT NULL DEFAULT 'one-sided'")

    def _job(self, row):
        return dict(row)

    def all(self, limit=50):
        with self.db._connection() as db:
            rows = db.execute("""SELECT * FROM delivery_jobs
                ORDER BY created_at DESC LIMIT ?""", (min(max(int(limit), 1), 250),)).fetchall()
        return [self._job(row) for row in rows]

    def summary(self):
        with self.db._connection() as db:
            rows = db.execute(
                "SELECT status,COUNT(*) AS n FROM delivery_jobs GROUP BY status").fetchall()
        return {r["status"]: r["n"] for r in rows}

    def enqueue(self, source, target_id, *, copies=1, sides="one-sided"):
        from itomiscan.integrations.printing import validate_copy_options
        # Copy metadata is validated before writing the PDF into the spool.
        validate_copy_options(copies, sides)

        source = Path(source)
        if not source.is_file() or source.suffix.lower() != ".pdf" or source.is_symlink():
            raise QueueError("Für die Zustellung ist eine vorhandene PDF-Datei erforderlich.")
        size = source.stat().st_size
        if not 0 < size <= MAX_JOB_BYTES:
            raise QueueError("PDF zu groß (maximal 150 MiB pro Auftrag).")
        # Keep a safety buffer for SQLite, temp pages and the next scan.
        if shutil.disk_usage(self.folder).free < size + 256 * 1024 * 1024:
            raise QueueError("Nicht genug freier Platz für sichere PDF-Zustellung. "
                             "Die ursprüngliche Scan-Datei bleibt erhalten.")
        target = next((t for t in self.db.list_targets() if t["id"] == target_id), None)
        if not target or target["kind"] not in ("paperless", "network", "email", "usb", "printer"):
            raise QueueError("Unbekanntes oder nicht unterstütztes Dokumentenziel.")
        with self.db._connection() as db:
            used = db.execute("SELECT COALESCE(SUM(size_bytes),0),COUNT(*) FROM delivery_jobs").fetchone()
        if used[0] + size > MAX_SPOOL_BYTES or used[1] >= MAX_JOBS:
            raise QueueError("Warteschlange voll; zuerst Aufträge manuell sichern.")
        job_id = uuid.uuid4().hex
        filename = job_id + ".pdf"
        temp = self.folder / ("." + filename + ".part")
        final = self.folder / filename
        digest = hashlib.sha256()
        try:
            with source.open("rb") as src, temp.open("xb") as dst:
                os.chmod(temp, 0o600)
                while True:
                    piece = src.read(64 * 1024)
                    if not piece:
                        break
                    digest.update(piece)
                    dst.write(piece)
                dst.flush()
                os.fsync(dst.fileno())
            if temp.stat().st_size != size:
                raise QueueError("Quelldatei wurde während der Sicherung verändert.")
            os.replace(temp, final)
            # Durable directory entry before the database references it.
            fd = os.open(str(self.folder), os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
            with self.db._connection(write=True) as db:
                db.execute("""INSERT INTO delivery_jobs
                    (id,target_id,kind,target_name,target_address,filename,digest,
                    size_bytes,created_at,status,retry_at,print_copies,print_sides)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
                    job_id, target["id"], target["kind"], target["name"],
                    target["address"], filename, digest.hexdigest(), size,
                    self.clock(), "queued", self.clock(), copies, sides))
            return job_id
        finally:
            if temp.exists():
                temp.unlink()

    def enqueue_batch(self, source, target_ids, *, label="Dokument",
                      background=False, owner_id=None, expected_targets=None):
        """Copy the PDF only once; atomically register one durable job per target.

        Hardlinks share immutable spool bytes. If linking is unavailable, fail
        before recording ANY jobs. Original remains untouched on all errors.
        """
        from itomiscan.integrations.printing import validate_copy_options
        validate_copy_options(1, "one-sided")
        if (not isinstance(target_ids, (list, tuple)) or not target_ids
                or len(target_ids)>30 or any(type(i) is not int for i in target_ids)
                or len(set(target_ids))!=len(target_ids)):
            raise QueueError("Bitte 1 bis 30 unterschiedliche Ziele auswählen.")
        source=Path(source)
        if not source.is_file() or source.is_symlink() or source.suffix.lower()!=".pdf":
            raise QueueError("Eine vorhandene PDF wird benötigt.")
        size=source.stat().st_size
        if not 0<size<=MAX_JOB_BYTES:
            raise QueueError("PDF zu groß.")
        if shutil.disk_usage(self.folder).free < size+256*1024*1024:
            raise QueueError("Zu wenig freier Speicher für die sichere Zustellung.")
        targets={t["id"]:t for t in self.db.list_targets()}
        if any(i not in targets for i in target_ids):
            raise QueueError("Mindestens ein Ziel existiert nicht mehr.")
        with self.db._connection() as db:
            used=db.execute("SELECT COALESCE(SUM(size_bytes),0), COUNT(*) FROM delivery_jobs").fetchone()
        if used[0]+size*len(target_ids)>MAX_SPOOL_BYTES or used[1]+len(target_ids)>MAX_JOBS:
            raise QueueError("Warteschlange voll. Keine Ziele eingeplant.")
        batch_id=uuid.uuid4().hex
        job_ids=[uuid.uuid4().hex for _ in target_ids]
        paths=[self.folder/(i+".pdf") for i in job_ids]
        temporary=self.folder/("."+batch_id+".part")
        created=[]
        digest=hashlib.sha256()
        try:
            with source.open("rb") as src,temporary.open("xb") as dst:
                os.chmod(temporary,0o600)
                for piece in iter(lambda:src.read(64*1024),b""):
                    digest.update(piece)
                    dst.write(piece)
                dst.flush()
                os.fsync(dst.fileno())
            if temporary.stat().st_size!=size:
                raise QueueError("Quelldatei beim Einlesen verändert.")
            os.replace(temporary,paths[0])
            created.append(paths[0])
            for path in paths[1:]:
                os.link(paths[0],path)
                created.append(path)
            fd=os.open(str(self.folder),os.O_RDONLY)
            try: os.fsync(fd)
            finally: os.close(fd)
            now=self.clock()
            with self.db._connection(write=True) as db:
                # Revalidate target identity and addresses within the transaction.
                for target_id in target_ids:
                    current=db.execute(
                        "SELECT kind,name,address FROM targets WHERE id=?",
                        (target_id,)).fetchone()
                    original=targets[target_id]
                    if (current is None or current["kind"]!=original["kind"]
                            or current["address"]!=original["address"]
                            or (expected_targets is not None and
                                expected_targets.get(target_id)!=original["address"])):
                        raise QueueError("Ziel wurde während der Planung geändert.")
                db.execute("""INSERT INTO delivery_batches
                    (id,created_at,label,background,owner_id,source)
                    VALUES(?,?,?,?,?,?)""",
                    (batch_id,now,str(label)[:80],int(bool(background)),
                     owner_id,str(source.name)[:150]))
                for target_id,job_id in zip(target_ids,job_ids):
                    t=targets[target_id]
                    db.execute("""INSERT INTO delivery_jobs
                        (id,target_id,kind,target_name,target_address,filename,
                         digest,size_bytes,created_at,status,retry_at,print_copies,
                         print_sides,batch_id)
                         VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (job_id,target_id,t["kind"],t["name"],t["address"],
                         job_id+".pdf",digest.hexdigest(),size,now,
                         "queued",now,1,"one-sided",batch_id))
            return batch_id
        except Exception:
            for path in created:
                path.unlink(missing_ok=True)
            raise
        finally:
            temporary.unlink(missing_ok=True)

    def batch(self,batch_id):
        with self.db._connection() as db:
            batch=db.execute("SELECT * FROM delivery_batches WHERE id=?",(batch_id,)).fetchone()
            if not batch:
                return None
            jobs=db.execute("SELECT * FROM delivery_jobs WHERE batch_id=? ORDER BY created_at,id",
                            (batch_id,)).fetchall()
        return {"batch":dict(batch),"jobs":[dict(j) for j in jobs]}

    def mark_batch_read(self,batch_id):
        with self.db._connection(write=True) as db:
            db.execute("UPDATE delivery_batches SET read_at=? WHERE id=?",
                       (self.clock(),batch_id))

    def recent_batches(self,limit=40):
        with self.db._connection() as db:
            rows=db.execute("SELECT * FROM delivery_batches ORDER BY created_at DESC LIMIT ?",
                            (max(1,min(int(limit),100)),)).fetchall()
        return [self.batch(r["id"]) for r in rows]

    def file_for(self, job):
        # Never trust a path read from a malformed DB or a user-supplied payload.
        path = self.folder / (job["id"] + ".pdf")
        if job["filename"] != path.name or not path.is_file() or path.is_symlink():
            raise QueueError("Gesicherte PDF-Datei fehlt oder wurde verändert.")
        if path.stat().st_size != job["size_bytes"]:
            raise QueueError("Gesicherte PDF-Datei hat eine unerwartete Größe.")
        check = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(64 * 1024), b""):
                check.update(chunk)
        if check.hexdigest() != job["digest"]:
            raise QueueError("Prüfsumme der gesicherten PDF-Datei stimmt nicht.")
        return path

    def recover(self):
        """An interrupted potentially duplicate transmission requires review."""
        with self.db._connection(write=True) as db:
            rows = db.execute("""SELECT id,kind FROM delivery_jobs WHERE
                status='sending' AND leased_until<?""", (self.clock(),)).fetchall()
            for row in rows:
                review = row["kind"] in NON_IDEMPOTENT
                db.execute("""UPDATE delivery_jobs SET status=?,leased_until=0,
                    retry_at=?, last_error=? WHERE id=?""",
                    ("review" if review else "retry", self.clock(),
                     "Unklarer Zustellstatus nach Neustart; manuelle Prüfung erforderlich."
                     if review else "Unterbrochene Dateiablage wird erneut versucht.",
                     row["id"]))
            return len(rows)

    def claim(self):
        self.recover()
        with self.db._connection(write=True) as db:
            row = db.execute("""SELECT * FROM delivery_jobs
                WHERE status IN ('queued','retry') AND retry_at<=?
                ORDER BY retry_at, created_at LIMIT 1""", (self.clock(),)).fetchone()
            if row is None:
                return None
            target = db.execute("SELECT kind,address FROM targets WHERE id=?",
                                (row["target_id"],)).fetchone()
            if target is None or target["kind"] != row["kind"]:
                db.execute("UPDATE delivery_jobs SET status=?,last_error=? WHERE id=?",
                           ("failed", "Ziel entfernt, keine Zustellung.", row["id"]))
                return None
            if target["address"] != row["target_address"]:
                db.execute("UPDATE delivery_jobs SET status=?,last_error=? WHERE id=?",
                           ("review", "Zieladresse geaendert, zuerst pruefen.", row["id"]))
                return None
            db.execute("""UPDATE delivery_jobs SET status='sending',
                attempts=attempts+1, leased_until=? WHERE id=?""",
                       (self.clock() + LEASE_SECONDS, row["id"]))
            return self._job(db.execute(
                "SELECT * FROM delivery_jobs WHERE id=?", (row["id"],)).fetchone())

    def outcome(self, job_id, status, *, error="", receipt=""):
        if status not in ("done", "retry", "review", "failed"):
            raise QueueError("Ungültiger Status.")
        with self.db._connection(write=True) as db:
            job = db.execute(
                "SELECT attempts FROM delivery_jobs WHERE id=? AND status='sending'",
                (job_id,)).fetchone()
            if not job:
                raise QueueError("Auftrag wurde bereits bearbeitet oder zurückgesetzt.")
            wait = RETRY_SECONDS[min(job["attempts"] - 1, len(RETRY_SECONDS) - 1)]
            db.execute("""UPDATE delivery_jobs SET status=?, last_error=?,
                receipt=?, leased_until=0, retry_at=? WHERE id=?""",
                (status, error[:350], receipt[:250],
                 self.clock() + wait if status == "retry" else self.clock(), job_id))

    def retry(self, job_id, *, acknowledge_uncertain=False):
        with self.db._connection(write=True) as db:
            row = db.execute(
                "SELECT status FROM delivery_jobs WHERE id=?", (job_id,)).fetchone()
            if not row or row["status"] not in ("retry", "failed", "review"):
                raise QueueError("Auftrag kann nicht erneut eingeplant werden.")
            if row["status"] == "review" and not acknowledge_uncertain:
                raise QueueError("Unklare Zustellung zuerst am Ziel prüfen.")
            db.execute("""UPDATE delivery_jobs SET status='retry',retry_at=?,
                last_error='' WHERE id=?""", (self.clock(), job_id))

    def process_once(self, sender):
        job = self.claim()
        if not job:
            return None
        try:
            path = self.file_for(job)
            receipt = sender(job, path)
        except QueueError as exc:
            self.outcome(job["id"], "failed", error=str(exc))
        except Exception as exc:
            # DeliveryError is imported lazily: transport modules never start
            # their network activity when the scanner UI is imported.
            from itomiscan.integrations.delivery import DeliveryError
            if isinstance(exc, DeliveryError):
                state = "review" if exc.uncertain else ("failed" if exc.permanent else "retry")
                self.outcome(job["id"], state, error=str(exc))
            else:
                # Unknown exception might occur after submission. Never
                # automatically replay a non-idempotent operation.
                self.outcome(job["id"], "review" if job["kind"] in NON_IDEMPOTENT
                             else "retry", error="Unerwarteter Zustellfehler.")
        else:
            self.outcome(job["id"], "done", receipt=str(receipt or ""))
        return job["id"]
