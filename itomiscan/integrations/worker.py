"""Separate unprivileged delivery worker; start explicitly via systemd/terminal.

Never imported from the GUI at module load. It polls SQLite for due jobs;
non-idempotent uncertain deliveries are held, never replayed automatically.
"""
import argparse
import fcntl
import os
import stat
import time
from pathlib import Path

from itomiscan.integrations.delivery import deliver
from itomiscan.storage.queue import DeliveryQueue
from itomiscan.storage.secrets import SecretStore


def process_once(queue):
    return queue.process_once(
        lambda job, path: deliver(job, path, SecretStore(queue.db.path)))


def main():
    parser = argparse.ArgumentParser(description="ItomiScan Ziel-Warteschlange")
    parser.add_argument("--once", action="store_true",
                        help="Genau einen fälligen Auftrag bearbeiten")
    parser.add_argument("--interval", type=int, default=15)
    args = parser.parse_args()
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        parser.error("Niemals als root ausführen.")
    if not 5 <= args.interval <= 300:
        parser.error("Prüfintervall 5 bis 300 Sekunden.")
    queue = DeliveryQueue()
    # Prevent two independently started workers from submitting the same job.
    lock_path = Path(queue.db.path).parent / ".delivery-worker.lock"
    if lock_path.is_symlink():
        parser.error("Unsichere Worker-Sperrdatei.")
    flags = os.O_CREAT | os.O_RDWR
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(lock_path, flags, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            parser.error("Ungültige Worker-Sperrdatei.")
        os.fchmod(fd, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.error("Zustelldienst läuft bereits. Kein zweiter Worker.")
        queue.recover()
        if args.once:
            process_once(queue)
            return
        while True:
            process_once(queue)
            time.sleep(args.interval)
    finally:
        os.close(fd)


if __name__ == "__main__":
    main()
