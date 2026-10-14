"""Separate unprivileged delivery worker; start explicitly via systemd/terminal.

Never imported from the GUI at module load. It polls SQLite for due jobs;
non-idempotent uncertain deliveries are held, never replayed automatically.
"""
import argparse
import os
import time

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
    queue.recover()
    if args.once:
        process_once(queue)
        return
    while True:
        process_once(queue)
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
