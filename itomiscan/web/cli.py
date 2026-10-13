"""Safe first-run administrator password setup. Never accepts password CLI args."""
import argparse
from getpass import getpass
import sys

from itomiscan.storage.config import ConfigStore, ConfigError


def main():
    parser = argparse.ArgumentParser(description="ItomiScan Administratorpasswort")
    parser.add_argument("action", choices=("init-admin", "change-password", "is-ready"))
    args = parser.parse_args()
    try:
        store = ConfigStore()
        if args.action == "is-ready":
            if not store.has_password():
                raise ConfigError("Noch kein Administratorpasswort gesetzt.")
            print("Administratorpasswort vorhanden.")
            return
        existing = store.has_password()
        if existing and args.action == "init-admin":
            raise ConfigError("Passwort existiert bereits. change-password verwenden.")
        if not existing and args.action == "change-password":
            raise ConfigError("Erst init-admin verwenden.")
        if existing:
            old = getpass("Bisheriges Passwort: ")
            if not store.verify_password(old):
                raise ConfigError("Das bisherige Passwort ist falsch.")
        password = getpass("Neues Administratorpasswort (mind. 10 Zeichen): ")
        again = getpass("Neues Passwort wiederholen: ")
        if password != again:
            raise ConfigError("Passwörter stimmen nicht überein.")
        store.set_password(password)
        print("Administratorpasswort gespeichert. Kein Benutzername erforderlich.")
    except (ConfigError, OSError, KeyboardInterrupt, EOFError) as exc:
        print("Fehler: " + str(exc), file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
