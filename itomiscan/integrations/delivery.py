"""Small streaming delivery adapters for PDF documents.

Never delete a source PDF. Exceptions distinguish definitely-unsent from
possibly-submitted data: uncertain delivery is held for manual review.
"""
import email.message
import hashlib
import http.client
import os
from pathlib import Path
import re
import shutil
import smtplib
import socket
import ssl
import subprocess
import tempfile
from urllib.parse import unquote, urlsplit


class DeliveryError(RuntimeError):
    def __init__(self, message, *, uncertain=False, permanent=False):
        super().__init__(message)
        self.uncertain = uncertain
        self.permanent = permanent


def safe_address(job):
    address = job["target_address"]
    url = urlsplit(address)
    if url.username or url.password or url.query or url.fragment:
        raise DeliveryError("Ungültige Zieladresse.", permanent=True)
    return url


def _stream_copy(source, destination, *, digest=None):
    """Stage to a same-directory file, fsync, verify and atomically publish."""
    destination = Path(destination)
    if destination.is_symlink() or destination.parent.is_symlink():
        raise DeliveryError("Unsicherer Zielpfad.", permanent=True)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        sha = hashlib.sha256()
        with destination.open("rb") as src:
            for piece in iter(lambda: src.read(64 * 1024), b""):
                sha.update(piece)
        if digest and sha.hexdigest() == digest:
            return "Bereits vorhanden und identisch"
        raise DeliveryError("Zieldatei vorhanden, Inhalt unterscheidet sich.",
                            permanent=True)
    part = destination.parent / ("." + destination.name + ".part")
    try:
        with Path(source).open("rb") as src, part.open("xb") as dst:
            for piece in iter(lambda: src.read(64 * 1024), b""):
                dst.write(piece)
            dst.flush()
            os.fsync(dst.fileno())
        # A concurrent actor writing the same deterministic name must never
        # be overwritten (Linux hard link fails atomically if destination exists).
        try:
            os.link(part, destination)
        except FileExistsError:
            raise DeliveryError("Zieldatei wurde gleichzeitig angelegt.",
                                permanent=True)
        os.unlink(part)
        fd = os.open(str(destination.parent), os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        return "Gesichert"
    except OSError as exc:
        raise DeliveryError("Speicherziel nicht verfügbar: " + str(exc)) from exc
    finally:
        if part.exists():
            part.unlink()


def deliver_usb(job, path, *, mounts=None, is_mount=os.path.ismount):
    """usb://VOLUMENAME/optional/path; never write to an unmounted directory."""
    url = safe_address(job)
    if url.scheme != "usb" or not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", url.netloc):
        raise DeliveryError("Ungültige USB-Zieladresse.", permanent=True)
    parts = [unquote(x) for x in url.path.split("/") if x]
    if any(not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", x) or x in (".", "..")
           for x in parts):
        raise DeliveryError("Ungültiger USB-Unterordner.", permanent=True)
    user = os.environ.get("USER") or Path.home().name
    roots = mounts if mounts is not None else (
        Path("/media") / user, Path("/run/media") / user)
    for root in roots:
        volume = Path(root) / url.netloc
        if volume.is_symlink() or not is_mount(volume):
            continue
        target_dir = volume
        for part in parts:
            target_dir = target_dir / part
            if target_dir.is_symlink():
                raise DeliveryError("USB-Pfad enthält symbolischen Link.",
                                    permanent=True)
        return _stream_copy(path, target_dir / job["filename"], digest=job["digest"])
    raise DeliveryError("USB-Stick nicht eingesteckt oder nicht eingehängt.")


def deliver_paperless(job, path, credentials):
    """POST multipart PDF in 64-KiB chunks to Paperless-ngx; verified TLS."""
    url = safe_address(job)
    if url.scheme != "https" or not url.hostname:
        raise DeliveryError("Paperless benötigt eine HTTPS-Adresse.", permanent=True)
    token = credentials.get("token", "")
    if not token:
        raise DeliveryError("Paperless-API-Token fehlt.", permanent=True)
    boundary = "itomiscan" + job["id"]
    filename = job["filename"]
    header = (f"--{boundary}\r\n"
              f'Content-Disposition: form-data; name="document"; filename="{filename}"\r\n'
              "Content-Type: application/pdf\r\n\r\n").encode("ascii")
    ending = f"\r\n--{boundary}--\r\n".encode("ascii")
    api = url.path.rstrip("/") + "/api/documents/post_document/"
    request_bytes = 0
    conn = None
    try:
        conn = http.client.HTTPSConnection(url.hostname, url.port or 443,
                                           timeout=15, context=ssl.create_default_context())
        # Network connection before any bytes have been written is safe to retry.
        conn.connect()
        conn.putrequest("POST", api)
        conn.putheader("Authorization", "Token " + token)
        conn.putheader("Content-Type", "multipart/form-data; boundary=" + boundary)
        conn.putheader("Content-Length",
                       str(len(header) + Path(path).stat().st_size + len(ending)))
        conn.endheaders()
        conn.send(header)
        request_bytes += len(header)
        with Path(path).open("rb") as doc:
            for chunk in iter(lambda: doc.read(64 * 1024), b""):
                conn.send(chunk)
                request_bytes += len(chunk)
        conn.send(ending)
        request_bytes += len(ending)
        response = conn.getresponse()
        body = response.read(250)  # keep only a short non-secret task receipt
        if 200 <= response.status < 300:
            return "Paperless angenommen (HTTP " + str(response.status) + ")"
        if response.status in (401, 403, 404, 413, 415, 422):
            raise DeliveryError("Paperless HTTP " + str(response.status),
                                permanent=True)
        raise DeliveryError("Paperless HTTP " + str(response.status),
                            uncertain=True)
    except DeliveryError:
        raise
    except (OSError, ssl.SSLError, TimeoutError, http.client.HTTPException) as exc:
        raise DeliveryError("Paperless-Verbindung fehlgeschlagen.",
                            uncertain=bool(request_bytes)) from exc
    finally:
        if conn:
            conn.close()


def deliver_email(job, path, credentials):
    """SMTP/SMTPS with encrypted transport. Bounded PDF size protects Atom RAM."""
    url = safe_address(job)
    if url.scheme not in ("smtp", "smtps") or not url.hostname:
        raise DeliveryError("E-Mail benötigt eine SMTP-Zieladresse.",
                            permanent=True)
    recipient = unquote(url.path.lstrip("/"))
    sender = credentials.get("sender", "")
    if not sender or not recipient or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", recipient) or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", sender):
        raise DeliveryError("SMTP-Absender oder Empfänger fehlt.", permanent=True)
    if Path(path).stat().st_size > 8 * 1024 * 1024:
        raise DeliveryError("E-Mail-PDF überschreitet 8 MiB Speicherschutzlimit.",
                            permanent=True)
    mail = email.message.EmailMessage()
    mail["Subject"] = "ItomiScan Dokument " + job["id"][:10]
    mail["From"], mail["To"] = sender, recipient
    mail["Message-ID"] = "<" + job["id"] + "@itomiscan.local>"
    mail.set_content("Dieses Dokument wurde mit ItomiScan eingescannt.")
    # Only this adapter loads the attachment into RAM, bounded above at 8 MiB.
    mail.add_attachment(Path(path).read_bytes(), maintype="application",
                        subtype="pdf", filename=job["filename"])
    submitted = False
    smtp = None
    try:
        if url.scheme == "smtps":
            smtp = smtplib.SMTP_SSL(url.hostname, url.port or 465,
                                    timeout=15, context=ssl.create_default_context())
        else:
            smtp = smtplib.SMTP(url.hostname, url.port or 587, timeout=15)
            smtp.ehlo()
            smtp.starttls(context=ssl.create_default_context())
            smtp.ehlo()
        if credentials.get("username"):
            if not credentials.get("password"):
                raise DeliveryError("SMTP-Passwort fehlt.", permanent=True)
            smtp.login(credentials["username"], credentials["password"])
        submitted = True
        smtp.send_message(mail)
        return "E-Mail vom SMTP-Server angenommen"
    except DeliveryError:
        raise
    except smtplib.SMTPAuthenticationError as exc:
        raise DeliveryError("SMTP-Anmeldung abgelehnt.", permanent=True) from exc
    except (smtplib.SMTPException, OSError, TimeoutError) as exc:
        raise DeliveryError("SMTP-Verbindung oder Versand fehlgeschlagen.",
                            uncertain=submitted) from exc
    finally:
        if smtp:
            try:
                smtp.quit()
            except (OSError, smtplib.SMTPException):
                smtp.close()


def deliver_smb(job, path, credentials):
    """SMB via smbclient and 0600 auth file, no password in command line.

    Guest shares may omit username/password. Conservative target path grammar
    prevents command-interpreter injection in smbclient -c (no OS shell used).
    """
    url = safe_address(job)
    host = url.hostname
    segments = [unquote(x) for x in url.path.split("/") if x]
    if (url.scheme != "smb" or not host or
            not re.fullmatch(r"[A-Za-z0-9._-]{1,253}", host) or
            not segments or any(not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", s)
                                or s in (".", "..") for s in segments)):
        raise DeliveryError("SMB-Ziel muss smb://server/freigabe/unterordner sein.",
                            permanent=True)
    if not shutil.which("smbclient"):
        raise DeliveryError("smbclient ist nicht installiert.", permanent=True)
    share = segments[0]
    directory = "/".join(segments[1:])
    remote = (directory + "/" if directory else "") + job["filename"]
    partial = remote + ".part"
    # Strict remote filename grammar (only UUID plus a vetted simple directory).
    authfile = None
    try:
        with tempfile.NamedTemporaryFile(
                mode="w", prefix="itomiscan-smb-", delete=False) as auth:
            authfile = Path(auth.name)
            os.chmod(authfile, 0o600)
            for key in ("username", "password"):
                value = credentials.get(key, "")
                if "\n" in value or "\r" in value:
                    raise DeliveryError("Ungültige SMB-Anmeldedaten.", permanent=True)
                auth.write(key + " = " + value + "\n")
            auth.flush()
            os.fsync(auth.fileno())
        # Fail safe: if the previous attempt completed its remote rename, stop
        # and require review rather than blindly uploading over the file.
        exists = subprocess.run(
            ["smbclient", "//" + host + "/" + share, "-A", str(authfile),
             "-c", 'allinfo "' + remote + '"'],
            capture_output=True, text=True, timeout=25)
        if exists.returncode == 0:
            raise DeliveryError("Datei existiert bereits auf SMB. Manuell prüfen.",
                                uncertain=True)
        command = 'put "' + str(path) + '" "' + partial + '"; rename "' + partial + '" "' + remote + '"'
        result = subprocess.run(
            ["smbclient", "//" + host + "/" + share, "-A", str(authfile),
             "-c", command],
            capture_output=True, text=True, timeout=75)
        if result.returncode != 0:
            raise DeliveryError("SMB-Übertragung fehlgeschlagen; Ziel prüfen.",
                                uncertain=True)
        return "SMB-Datei übertragen"
    except subprocess.TimeoutExpired as exc:
        raise DeliveryError("SMB-Zeitüberschreitung; Zustellung prüfen.",
                            uncertain=True) from exc
    except OSError as exc:
        raise DeliveryError("SMB-Ziel nicht erreichbar.") from exc
    finally:
        if authfile is not None:
            authfile.unlink(missing_ok=True)


def deliver(job, path, secrets):
    kind = job["kind"]
    credentials = secrets.get(job["target_id"])
    if kind == "paperless":
        return deliver_paperless(job, path, credentials)
    if kind == "email":
        return deliver_email(job, path, credentials)
    if kind == "usb":
        return deliver_usb(job, path)
    if kind == "network":
        return deliver_smb(job, path, credentials)
    raise DeliveryError("Zieltyp wird nicht unterstützt.", permanent=True)
