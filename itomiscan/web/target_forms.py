"""Convert type-specific target form fields into existing validated URI storage.

Never accept credentials inside destination URLs; callers must still run the
existing ConfigStore.save_target / validate_target checks.
"""
import re
from urllib.parse import quote


_HOST = re.compile(r"[A-Za-z0-9.-]{1,253}\Z")
_PART = re.compile(r"[A-Za-z0-9._-]{1,64}\Z")
_EMAIL = re.compile(r"[^@\s/]+@[^@\s/]+\.[^@\s/]+\Z")


def _part(value, field):
    value = value.strip()
    if not _PART.fullmatch(value) or value in (".", ".."):
        raise ValueError(field + ": nur Buchstaben, Zahlen, Punkt, _ und -.")
    return value


def _host(value):
    value = value.strip()
    if (not _HOST.fullmatch(value) or ".." in value or
            value.startswith((".", "-")) or value.endswith((".", "-"))):
        raise ValueError("Ungültiger Servername oder IPv4-Adresse.")
    return value


def _directory(value):
    value = value.strip().strip("/")
    if not value:
        return ""
    return "/".join(_part(part, "Unterordner") for part in value.split("/"))


def _port(value, default):
    value = value.strip()
    if not value:
        return default
    try:
        number = int(value)
    except ValueError as exc:
        raise ValueError("Port muss eine Zahl sein.") from exc
    if not 1 <= number <= 65535:
        raise ValueError("Port muss zwischen 1 und 65535 liegen.")
    return number


def target_from_form(form):
    """Keep the existing single-URI API and an explicit advanced URI override.

    The advanced address field is intentionally optional in the browser.
    On ordinary forms, a structured destination is constructed server-side,
    so no JavaScript is required for correct storage.
    """
    kind = form.get("kind", "")
    address = form.get("address", "").strip()
    if address:
        return {"kind": kind, "name": form.get("name", ""), "address": address}
    if kind == "paperless":
        address = form.get("paperless_url", "").strip().rstrip("/")
        if not address.startswith("https://"):
            raise ValueError("Paperless benötigt eine vollständige HTTPS-Adresse.")
    elif kind == "network":
        host = _host(form.get("network_host", ""))
        share = _part(form.get("network_share", ""), "SMB-Freigabe")
        folder = _directory(form.get("network_directory", ""))
        address = "smb://" + host + "/" + share + ("/" + folder if folder else "")
    elif kind == "email":
        mode = form.get("email_security", "starttls")
        if mode not in ("starttls", "smtps"):
            raise ValueError("Unbekannte SMTP-Verschlüsselung.")
        server = _host(form.get("email_host", ""))
        recipient = form.get("email_recipient", "").strip()
        if not _EMAIL.fullmatch(recipient):
            raise ValueError("Ungültige E-Mail-Empfängeradresse.")
        scheme = "smtp" if mode == "starttls" else "smtps"
        port = _port(form.get("email_port", ""), 587 if mode == "starttls" else 465)
        address = f"{scheme}://{server}:{port}/{quote(recipient, safe='@._+-')}"
    elif kind == "usb":
        volume = _part(form.get("usb_volume", ""), "USB-Datenträger")
        folder = _directory(form.get("usb_directory", ""))
        address = "usb://" + volume + ("/" + folder if folder else "")
    else:
        # Printer targets continue to use the dedicated printer setup page.
        raise ValueError("Für diesen Zieltyp eine vollständige Adresse eingeben.")
    return {"kind": kind, "name": form.get("name", ""), "address": address}
