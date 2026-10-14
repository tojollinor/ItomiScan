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

from itomiscan.storage.config import ConfigStore, ConfigError

MAX_SPOOL_BYTES = 2 * 1024 * 1024 * 1024
MAX_JOB_BYTES = 150 * 1024 * 1024
MAX_JOBS = 500
RETRY_SECONDS = (60, 120, 300, 900, 1800, 3600)
LEASE_SECONDS = 600
NON_IDEMPOTENT = {"paperless", "email"}


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

    def enqueue(self, source, target_id):
        source = Path(source)
        if not source.is_file() or source.suffix.lower() != ".pdf" or source.is_symlink():
            raise QueueError("Für die Zustellung ist eine vorhandene PDF-Datei erforderlich.")
        size = source.stat().st_size
        if not 0 < size <= MAX_JOB_BYTES:
            raise QueueError("PDF zu groß (maximal 150 MiB pro Auftrag).")
        target = next((t for t in self.db.list_targets() if t["id"] == target_id), None)
        if not target or target["kind"] not in ("paperless", "network", "email", "usb"):
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
                    size_bytes,created_at,status,retry_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?)""", (
                    job_id, target["id"], target["kind"], target["name"],
                    target["address"], filename, digest.hexdigest(), size,
                    self.clock(), "queued", self.clock()))
            return job_id
        finally:
            if temp.exists():
                temp.unlink()

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
