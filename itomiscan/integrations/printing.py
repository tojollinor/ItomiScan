"""Small CUPS/IPP adapter. No pycups, shell=True or permanent privileged service.

Queues are created by lpadmin only after opt-in provisioning grants the normal
scanner user lpadmin group membership. No driver downloads or PPD injection.
"""
import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

from itomiscan.integrations.delivery import DeliveryError


QUEUE_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,39}\Z")
SIDES = ("one-sided", "two-sided-long-edge", "two-sided-short-edge")
MAX_COPIES = 20


class PrintError(DeliveryError):
    pass


def queue_name(value):
    if not isinstance(value, str) or not QUEUE_RE.fullmatch(value):
        raise PrintError(
            "CUPS-Druckername: 1 bis 40 Zeichen, beginnend mit einem Buchstaben.",
            permanent=True)
    return value


def printer_uri(uri):
    if not isinstance(uri, str):
        raise PrintError("Ungültige Druckeradresse.", permanent=True)
    try:
        parsed = urlsplit(uri)
        port = parsed.port
    except ValueError as exc:
        raise PrintError("Ungültige IPP-Adresse.", permanent=True) from exc
    if (parsed.scheme not in ("ipp", "ipps") or not parsed.hostname
            or parsed.username or parsed.password or parsed.query
            or parsed.fragment or "@" in parsed.netloc or
            (port is not None and not 1 <= port <= 65535)):
        raise PrintError("Drucker benötigen eine IPP- oder IPPS-Adresse ohne Zugangsdaten.",
                         permanent=True)
    return uri


def validate_copy_options(copies=1, sides="one-sided"):
    if type(copies) is not int or not 1 <= copies <= MAX_COPIES:
        raise PrintError("Kopienanzahl muss zwischen 1 und 20 liegen.", permanent=True)
    if sides not in SIDES:
        raise PrintError("Ungültiger Duplexdruck-Modus.", permanent=True)
    return copies, sides


def run_cups(args, *, timeout=12, input_text=None):
    if not shutil.which(args[0]):
        raise PrintError(args[0] + " ist nicht installiert.", permanent=True)
    try:
        result = subprocess.run(
            args, input=input_text, capture_output=True, text=True,
            timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PrintError("CUPS-Befehl nicht erreichbar: " + type(exc).__name__) from exc
    if result.returncode:
        # Avoid leaking remote usernames or addresses from arbitrary CUPS logs.
        raise PrintError("CUPS meldet Fehler " + str(result.returncode) +
                         ". Drucker- und Benutzerrechte prüfen.")
    return result.stdout.strip()


def list_queues():
    """Return only genuinely installed CUPS destination identifiers."""
    stdout = run_cups(["lpstat", "-e"], timeout=6)
    result = []
    for line in stdout.splitlines():
        value = line.strip()
        if QUEUE_RE.fullmatch(value):
            result.append(value)
    return sorted(set(result), key=str.casefold)


def is_configured(name):
    return queue_name(name) in list_queues()


def queue_detail(name):
    name = queue_name(name)
    if not is_configured(name):
        return {"name": name, "configured": False, "status": "Nicht eingerichtet"}
    try:
        raw = run_cups(["lpstat", "-p", name], timeout=6)
    except PrintError:
        return {"name": name, "configured": True, "status": "Status nicht abrufbar"}
    status = "Pausiert" if "disabled" in raw.lower() else "Eingerichtet"
    return {"name": name, "configured": True, "status": status}


def install_queue(name, uri):
    """Driverless Everywhere: requires deliberately provisioned CUPS permission."""
    name = queue_name(name)
    uri = printer_uri(uri)
    # No shell interpolation. lpadmin can still refuse if the local user
    # is not in lpadmin or if printer does not support IPP Everywhere.
    run_cups(["lpadmin", "-p", name, "-E", "-v", uri, "-m", "everywhere"],
             timeout=20)
    if not is_configured(name):
        raise PrintError("CUPS hat die Druckerwarteschlange nicht bestätigt.")
    return name


def uninstall_queue(name):
    name = queue_name(name)
    if not is_configured(name):
        raise PrintError("Druckerwarteschlange existiert nicht.", permanent=True)
    run_cups(["lpadmin", "-x", name], timeout=15)
    return name


def submit_pdf(name, pdf, *, copies=1, sides="one-sided"):
    """A successful lp exit means CUPS accepted the job, not paper printed."""
    name = queue_name(name)
    copies, sides = validate_copy_options(copies, sides)
    pdf = Path(pdf)
    if not pdf.is_file() or pdf.is_symlink() or pdf.suffix.lower() != ".pdf":
        raise PrintError("Gültige gesicherte PDF-Datei fehlt.", permanent=True)
    if not is_configured(name):
        raise PrintError("Drucker nicht in CUPS eingerichtet.", permanent=True)
    cmd = ["lp", "-d", name, "-n", str(copies), "-o", "sides=" + sides, str(pdf)]
    if not shutil.which("lp"):
        raise PrintError("CUPS-Client lp fehlt.", permanent=True)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True,
                                timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PrintError("Druckübergabe unklar. CUPS-Aufträge kontrollieren.",
                         uncertain=True) from exc
    if result.returncode != 0:
        # The command may already have created a job before reporting an error.
        raise PrintError("Druckübergabe fehlgeschlagen/unklar. CUPS-Aufträge prüfen.",
                         uncertain=True)
    output = result.stdout.strip()
    match = re.search(r"\b([A-Za-z][A-Za-z0-9_-]*-[0-9]+)\b", output)
    return ("Von CUPS angenommen: " + match.group(1)
            if match else "Von CUPS angenommen, physischer Ausdruck unbestätigt")


def deliver_print(job, pdf):
    """Called by the existing durable spool worker."""
    if job["kind"] != "printer":
        raise PrintError("Kein Druckauftrag.", permanent=True)
    return submit_pdf(job["target_name"], pdf,
                      copies=job.get("print_copies", 1),
                      sides=job.get("print_sides", "one-sided"))


def test_page(name):
    """CUPS text/plain test job, no scanner or customer documents."""
    name = queue_name(name)
    if not is_configured(name):
        raise PrintError("Drucker ist nicht in CUPS eingerichtet.", permanent=True)
    payload = "ItomiScan\nCUPS Testdruck\nDrucker: " + name + "\n"
    if not shutil.which("lp"):
        raise PrintError("CUPS-Client lp fehlt.", permanent=True)
    try:
        result = subprocess.run(["lp", "-d", name, "-t", "ItomiScan Testseite"],
                                input=payload, capture_output=True, text=True,
                                timeout=25, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PrintError("Testdruck unklar; CUPS-Auftraege pruefen.",
                         uncertain=True) from exc
    if result.returncode:
        raise PrintError("Testseite wurde von CUPS nicht bestätigt.",
                         uncertain=True)
    return "Testdruck von CUPS angenommen (Papierausgabe noch zu prüfen)"
