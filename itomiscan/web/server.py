"""Password-only, TLS-enforced ItomiScan remote configuration server.

Stdlib-only. Never listens remotely without TLS and an initialized password.
The kiosk doesn't use the browser; this is a separately started admin process.
"""
import argparse
import email
from email import policy
from email.parser import BytesParser
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
import logging
import os
from pathlib import Path
import secrets
import shutil
import socket
import ssl
import subprocess
import threading
import time
from urllib.parse import parse_qs, urlsplit

from itomiscan.core.profiles import validate_profile
from itomiscan.storage.config import ConfigError, ConfigStore
from itomiscan.storage.users import PERMISSIONS, PinError, UserStore
from itomiscan.web import pages, user_pages, delivery_pages, printing_pages
from itomiscan.web.system_status import StatusSampler
from itomiscan.integrations.discovery import discover_paperless
from itomiscan.integrations.printing import (
    PrintError, list_queues, install_queue, uninstall_queue, test_page,
    discover_printers, set_default_printer, printer_uri, queue_name, address_from_host,
)
from itomiscan.storage.queue import DeliveryQueue, QueueError
from itomiscan.storage.secrets import SecretStore, SecretError


MAX_BODY = 160 * 1024
SESSION_TTL = 30 * 60
LOCKOUT = 3 * 60
MAX_FAILURES = 5
COOKIE = "itomiscan_session"
LOG = logging.getLogger("itomiscan.web")


def inspect_system(store, bind, sampler=None, queue=None, diagnostic=""):
    """Expose limited, read-only system metrics to authenticated administrators."""
    root = Path(__file__).resolve().parents[2]
    result = {
        "hostname": socket.gethostname(),
        "ip": bind,
        "platform": "Debian/Linux",
        "branch": "Unbekannt",
        "commit": "Unbekannt",
        "scanner": ("Scanner gefunden" if "fujitsu:" in diagnostic.lower()
                    else "Nicht geprüft" if not diagnostic.strip()
                    else "Diagnose beachten"),
    }
    for key, args in (
        ("branch", ["git", "-C", str(root), "branch", "--show-current"]),
        ("commit", ["git", "-C", str(root), "rev-parse", "--short=10", "HEAD"]),
    ):
        try:
            process = subprocess.run(args, capture_output=True, text=True,
                                     timeout=2, check=False)
            if process.returncode == 0 and process.stdout.strip():
                result[key] = process.stdout.strip()[:64]
        except (OSError, subprocess.TimeoutExpired):
            pass
    result.update((sampler or StatusSampler()).collect(store.path.parent))
    result["jobs_pending"] = "Nicht verfügbar"
    result["jobs_review"] = "Nicht verfügbar"
    if queue is not None:
        try:
            counts = queue.summary()
            result["jobs_pending"] = str(sum(counts.get(k, 0) for k in
                                             ("queued", "pending", "retry", "leased")))
            result["jobs_review"] = str(counts.get("review", 0))
        except (OSError, ValueError, ConfigError):
            pass
    return result


class Sessions:
    """Short-lived server-side sessions, CSRF tokens and simple IP throttling."""

    def __init__(self, clock=time.monotonic):
        self.lock = threading.RLock()
        self.entries = {}
        self.failures = {}
        self.clock = clock

    def allowed(self, ip):
        with self.lock:
            fails, until = self.failures.get(ip, (0, 0))
            if until and until > self.clock():
                return False
            if until and until <= self.clock():
                self.failures.pop(ip, None)
            return True

    def bad_password(self, ip):
        with self.lock:
            count, until = self.failures.get(ip, (0, 0))
            if until and until <= self.clock():
                count = 0
            count += 1
            self.failures[ip] = (
                count, self.clock() + LOCKOUT if count >= MAX_FAILURES else 0)

    def create(self, ip):
        with self.lock:
            self.failures.pop(ip, None)
            token = secrets.token_urlsafe(32)
            csrf = secrets.token_urlsafe(24)
            self.entries[token] = (self.clock() + SESSION_TTL, csrf)
            return token, csrf

    def get(self, token):
        if not token:
            return None
        with self.lock:
            entry = self.entries.get(token)
            if not entry:
                return None
            if entry[0] <= self.clock():
                self.entries.pop(token, None)
                return None
            self.entries[token] = (self.clock() + SESSION_TTL, entry[1])
            return entry[1]

    def remove(self, token):
        with self.lock:
            self.entries.pop(token, None)

    def clear(self):
        with self.lock:
            self.entries.clear()


class AdminServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, store, secure):
        super().__init__(address, AdminHandler)
        self.store = store
        self.secure = secure
        self.bind_ip = address[0]
        self.sessions = Sessions()
        self.users = UserStore(store.path)
        self.queue = DeliveryQueue(store.path)
        self.secrets = SecretStore(store.path)
        self.diagnostic = ""
        self.status_sampler = StatusSampler()


class AdminHandler(BaseHTTPRequestHandler):
    server_version = "ItomiScan"
    sys_version = ""

    def log_message(self, _format, *args):
        # Never log raw request lines (may contain query strings).
        pass

    def log_request(self, code="-", size="-"):
        path = urlsplit(self.path).path[:160]
        LOG.info("HTTP %s %s status=%s client=%s",
                 self.command, json.dumps(path, ensure_ascii=True),
                 code, self.client_address[0])

    def _log_rejected_origin(self, host_ok, origin_ok):
        host = self.headers.get("Host", "")[:160]
        origin = self.headers.get("Origin", "")[:160]
        LOG.warning(
            "HTTP 403 security_check host_ok=%s origin_ok=%s "
            "host=%s origin=%s client=%s",
            host_ok, origin_ok,
            json.dumps(host, ensure_ascii=True),
            json.dumps(origin, ensure_ascii=True),
            self.client_address[0])

    def _host_ok(self):
        host = self.headers.get("Host", "")
        return host in (
            f"{self.server.bind_ip}:{self.server.server_address[1]}",
            self.server.bind_ip
        )

    def _origin_ok(self):
        origin = self.headers.get("Origin", "")
        if not origin:
            return True
        # Some browsers send an opaque Origin for self-signed TLS.
        # Login has no CSRF token, so its explicit opt-in remains mandatory.
        # Authenticated mutations may use Origin:null, but only after the
        # session is verified here AND a matching CSRF token in do_POST.
        # A foreign non-null origin is never allowed.
        if origin == "null":
            if urlsplit(self.path).path == "/login":
                flag = Path.home() / ".config" / "itomiscan" / "allow-null-origin"
                return flag.is_file()
            return bool(self._authenticated())
        scheme = "https" if self.server.secure else "http"
        expected = f"{scheme}://{self.server.bind_ip}:{self.server.server_address[1]}"
        return origin == expected

    def _response(self, code, body, *, mime="text/html; charset=utf-8",
                  location=None, cookie=None, attachment=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy",
                         "default-src 'none'; style-src 'unsafe-inline'; "
                         "script-src 'self'; connect-src 'self'; "
                         "form-action 'self'; frame-ancestors 'none'; base-uri 'none'")
        if location:
            self.send_header("Location", location)
        if cookie:
            self.send_header("Set-Cookie", cookie)
        if attachment:
            self.send_header("Content-Disposition", attachment)
        self.end_headers()
        self.wfile.write(body)

    def _redirect(self, location, cookie=None):
        self._response(303, b"", location=location, cookie=cookie)

    def _error(self, status, message):
        self._response(status, pages.layout(
            "Hinweis", f'<div class="alert">{pages.e(message)}</div>', logged=False))

    def _session_token(self):
        jar = cookies.SimpleCookie()
        try:
            jar.load(self.headers.get("Cookie", ""))
            return jar[COOKIE].value if COOKIE in jar else ""
        except cookies.CookieError:
            return ""

    def _authenticated(self):
        return self.server.sessions.get(self._session_token())

    def _cookie(self, value, expired=False):
        result = f"{COOKIE}={value}; Path=/; HttpOnly; SameSite=Strict"
        if self.server.secure:
            result += "; Secure"
        if expired:
            result += "; Max-Age=0"
        else:
            result += f"; Max-Age={SESSION_TTL}"
        return result

    def do_GET(self):
        if not self._host_ok():
            return self._error(421, "Unbekannter Hostname. Bitte die konfigurierte IP benutzen.")
        path = urlsplit(self.path).path
        if path == "/login":
            if self._authenticated():
                return self._redirect("/")
            return self._response(200, pages.login())
        csrf = self._authenticated()
        if not csrf:
            return self._redirect("/login")
        notice = parse_qs(urlsplit(self.path).query).get("ok", [""])[0][:180]
        try:
            if path == "/assets/printer-choose.js":
                return self._response(
                    200, pages.PRINTER_CHOOSE_JS,
                    mime="text/javascript; charset=utf-8")
            if path == "/assets/admin-dialogs.js":
                return self._response(200, pages.DIALOG_JS,
                                      mime="text/javascript; charset=utf-8")
            if path == "/assets/status.js":
                return self._response(
                    200, pages.STATUS_JS,
                    mime="text/javascript; charset=utf-8")
            if path == "/":
                status = inspect_system(
                    self.server.store, self.server.bind_ip,
                    self.server.status_sampler, self.server.queue, self.server.diagnostic)
                profiles, _selected = self.server.store.list_profiles()
                targets = self.server.store.list_targets()
                html = pages.overview(status, {
                    "profiles": len(profiles), "targets": len(targets)}, csrf, notice)
            elif path == "/profiles":
                profiles, selected = self.server.store.list_profiles()
                html = pages.profiles_page(profiles, selected, csrf, notice)
            elif path == "/users":
                profiles, _ = self.server.store.list_profiles()
                html = user_pages.users_page(
                    self.server.users.list_users(), self.server.users.settings(),
                    [p["name"] for p in profiles], csrf, notice)
            elif path == "/targets":
                targets = self.server.store.list_targets()
                flags = {item["id"]: bool(self.server.secrets.get(item["id"])) for item in targets}
                html = delivery_pages.targets_page(targets, csrf, flags, notice,
                                                  discovered=discover_paperless())
            elif path == "/printers":
                try:
                    cups = list_queues()
                    issue = ""
                except PrintError as exc:
                    cups, issue = [], str(exc)
                targets = [x for x in self.server.store.list_targets()
                           if x["kind"] == "printer"]
                try:
                    discovered = discover_printers()
                except PrintError:
                    discovered = []
                html = printing_pages.printers_page(
                    targets, cups, csrf, notice=notice, issue=issue,
                    discovered=discovered)
            elif path == "/jobs":
                html = delivery_pages.jobs_page(self.server.queue.all(),
                                                self.server.queue.summary(), csrf, notice)
            elif path == "/system":
                html = pages.system_page(
                    inspect_system(
                        self.server.store, self.server.bind_ip,
                        self.server.status_sampler, self.server.queue,
                        self.server.diagnostic),
                    self.server.store.get_settings(), csrf,
                    self.server.diagnostic, notice)
            elif path == "/backups":
                html = pages.backup_page(csrf, notice)
            elif path == "/backup.json":
                data = json.dumps(self.server.store.backup(), ensure_ascii=False,
                                  indent=2).encode("utf-8")
                return self._response(
                    200, data, mime="application/json; charset=utf-8",
                    attachment='attachment; filename="itomiscan-konfiguration.json"')
            elif path == "/api/metrics":
                data = json.dumps(self.server.status_sampler.collect(
                    self.server.store.path.parent), ensure_ascii=False)
                return self._response(200, data, mime="application/json; charset=utf-8")
            elif path == "/api/status":
                data = json.dumps(inspect_system(
                    self.server.store, self.server.bind_ip,
                    self.server.status_sampler, self.server.queue,
                    self.server.diagnostic), ensure_ascii=False)
                return self._response(200, data, mime="application/json; charset=utf-8")
            else:
                return self._error(404, "Seite nicht gefunden.")
            return self._response(200, html)
        except (OSError, ValueError, ConfigError) as exc:
            return self._error(500, "Konfiguration nicht lesbar: " + str(exc))

    def _read_form(self):
        raw_length = self.headers.get("Content-Length", "")
        if not raw_length.isdecimal():
            raise ValueError("Content-Length fehlt.")
        length = int(raw_length)
        if length <= 0 or length > MAX_BODY:
            raise ValueError("Formulardaten überschreiten die zulässige Größe.")
        raw = self.rfile.read(length)
        ctype = self.headers.get("Content-Type", "").lower()
        if ctype.startswith("application/x-www-form-urlencoded"):
            values = parse_qs(raw.decode("utf-8"), keep_blank_values=True,
                              max_num_fields=70)
            if any(len(value) != 1 and key != "assigned_profiles"
                   for key, value in values.items()):
                raise ValueError("Doppelte Formularfelder sind nicht erlaubt.")
            return {key: value if key == "assigned_profiles" else value[0]
                    for key, value in values.items()}
        if ctype.startswith("multipart/form-data;"):
            prefix = ("MIME-Version: 1.0\r\nContent-Type: "
                      + self.headers.get("Content-Type", "") + "\r\n\r\n")
            message = BytesParser(policy=policy.default).parsebytes(
                prefix.encode("ascii") + raw)
            if not message.is_multipart():
                raise ValueError("Ungültiger Datei-Upload.")
            form = {}
            parts = list(message.iter_parts())
            if len(parts) > 6:
                raise ValueError("Zu viele Formularfelder.")
            for part in parts:
                if part.get_content_disposition() != "form-data":
                    continue
                name = part.get_param("name", header="content-disposition")
                if name not in ("csrf", "backup") or name in form:
                    raise ValueError("Unerwartetes oder doppeltes Formularfeld.")
                value = part.get_payload(decode=True) or b""
                form[name] = value if name == "backup" else value.decode("utf-8")
            return form
        raise ValueError("Unbekannter Formulartyp.")

    def do_POST(self):
        host_ok = self._host_ok()
        origin_ok = self._origin_ok()
        if not host_ok or not origin_ok:
            self._log_rejected_origin(host_ok, origin_ok)
            return self._error(403, "Ungültiger Ursprung.")
        path = urlsplit(self.path).path
        try:
            form = self._read_form()
        except (ValueError, UnicodeError, OverflowError) as exc:
            return self._error(413, str(exc))
        ip = self.client_address[0]
        if path == "/login":
            if not self.server.sessions.allowed(ip):
                return self._error(429, "Zu viele Versuche. Bitte später erneut anmelden.")
            password = form.get("password", "")
            if (not isinstance(password, str)
                    or not self.server.store.verify_password(password)):
                self.server.sessions.bad_password(ip)
                return self._response(401, pages.login(
                    "Das Passwort ist nicht korrekt."))
            token, _csrf = self.server.sessions.create(ip)
            return self._redirect("/", cookie=self._cookie(token))
        csrf = self._authenticated()
        if not csrf:
            return self._redirect("/login")
        supplied = form.get("csrf", "")
        if not isinstance(supplied, str) or not secrets.compare_digest(csrf, supplied):
            return self._error(403, "Sicherheitsprüfung fehlgeschlagen. Bitte Seite neu laden.")
        try:
            if path == "/logout":
                self.server.sessions.remove(self._session_token())
                return self._redirect("/login", cookie=self._cookie("", expired=True))
            if path == "/users/config":
                self.server.users.configure(
                    enabled=form.get("enabled") == "yes",
                    timeout_minutes=int(form.get("timeout_minutes", "")))
                return self._redirect("/users?ok=Anmeldung%20konfiguriert")
            if path == "/users/save":
                raw_id = form.get("user_id", "")
                selected = form.get("assigned_profiles", [])
                if not isinstance(selected, list):
                    selected = [selected]
                permissions = [p for p in PERMISSIONS
                               if form.get("perm_" + p) == "yes"]
                self.server.users.save_user(
                    user_id=int(raw_id) if raw_id else None,
                    name=form.get("name", ""), pin=form.get("pin", "") or None,
                    active=form.get("active") == "yes", permissions=permissions,
                    assigned_profiles=selected,
                    default_profile=form.get("default_profile", ""))
                return self._redirect("/users?ok=Benutzer%20gespeichert")
            if path == "/users/delete":
                self.server.users.delete_user(int(form.get("user_id", "")))
                return self._redirect("/users?ok=Benutzer%20entfernt")
            if path == "/profiles/save":
                advanced = json.loads(form.get("advanced", "{}"))
                item = validate_profile({
                    "name": form.get("name", ""), "mode": form.get("mode", ""),
                    "source": form.get("source", ""),
                    "resolution": int(form.get("resolution", "")),
                    "output": form.get("output", ""), "settings": advanced})
                self.server.store.save_profile(item)
                return self._redirect("/profiles?ok=Profil%20gespeichert")
            if path == "/profiles/select":
                self.server.store.select_profile(form.get("name", ""))
                return self._redirect("/profiles?ok=Standardprofil%20gewechselt")
            if path == "/targets/save":
                self.server.store.save_target({
                    "kind": form.get("kind", ""), "name": form.get("name", ""),
                    "address": form.get("address", "")})
                return self._redirect("/targets?ok=Ziel%20gespeichert")
            if path == "/targets/delete":
                target_id = int(form.get("id", ""))
                target = next((t for t in self.server.store.list_targets()
                               if t["id"] == target_id), None)
                if not target:
                    raise ValueError("Ziel existiert nicht.")
                if target["kind"] == "printer" and target["name"] in list_queues():
                    raise ValueError("Drucker zuerst aus CUPS entfernen, "
                                     "danach gespeichertes Ziel löschen.")
                self.server.store.delete_target(target_id)
                return self._redirect("/targets?ok=Ziel%20entfernt")
            if path == "/printers/save":
                name = form.get("name", "")
                address = form.get("address", "").strip()
                if not address:
                    address = address_from_host(form.get("protocol", ""),
                                                form.get("host", "").strip())
                printer_uri(address)
                queue_name(name)
                self.server.store.save_target({
                    "kind": "printer", "name": name, "address": address})
                return self._redirect("/printers?ok=Druckerziel%20gespeichert")
            if path == "/printers/edit":
                address = form.get("address", "")
                printer_uri(address)
                self.server.store.update_target_address(
                    int(form.get("target_id", "")), address)
                return self._redirect("/printers?ok=Druckeradresse%20aktualisiert")
            if path in ("/printers/install", "/printers/test", "/printers/uninstall", "/printers/default"):
                target_id = int(form.get("target_id", ""))
                target = next((x for x in self.server.store.list_targets()
                               if x["id"] == target_id and x["kind"] == "printer"), None)
                if not target:
                    raise ValueError("Der Drucker ist nicht mehr als Ziel registriert.")
                if path == "/printers/install":
                    install_queue(target["name"], target["address"])
                    return self._redirect("/printers?ok=Drucker%20eingerichtet")
                if path == "/printers/default":
                    set_default_printer(target["name"])
                    return self._redirect("/printers?ok=Standarddrucker%20gesetzt")
                if path == "/printers/test":
                    test_page(target["name"])
                    return self._redirect("/printers?ok=CUPS%20hat%20Testauftrag%20angenommen")
                uninstall_queue(target["name"])
                return self._redirect("/printers?ok=CUPS%20Zuordnung%20entfernt")
            if path == "/targets/secrets":
                target_id = int(form.get("target_id", ""))
                target = next((t for t in self.server.store.list_targets()
                               if t["id"] == target_id), None)
                if not target or target["kind"] not in ("paperless", "network", "email"):
                    raise ValueError("Ungültiges Ziel für Zugangsdaten.")
                if form.get("clear") == "yes":
                    self.server.secrets.update(target_id, clear=True)
                else:
                    allowed = {"paperless": ("token",),
                               "network": ("username", "password"),
                               "email": ("username", "password", "sender")}[target["kind"]]
                    values = {key: form[key] for key in allowed
                              if form.get(key)}
                    self.server.secrets.update(target_id, **values)
                return self._redirect("/targets?ok=Zugangsdaten%20gespeichert")
            if path == "/jobs/retry":
                job_id = form.get("job_id", "")
                if not isinstance(job_id, str) or len(job_id) != 32:
                    raise ValueError("Ungültige Auftrags-ID.")
                self.server.queue.retry(job_id,
                    acknowledge_uncertain=form.get("reviewed") == "yes")
                return self._redirect("/jobs?ok=Auftrag%20neu%20eingeplant")
            if path == "/system/settings":
                self.server.store.set_settings({
                    "screensaver_minutes": int(form.get("screensaver_minutes", "")),
                    "device_label": form.get("device_label", "")})
                return self._redirect("/system?ok=Einstellungen%20gespeichert")
            if path == "/system/diagnose":
                try:
                    scan = subprocess.run(["scanimage", "-L"],
                                          capture_output=True, text=True, timeout=8,
                                          check=False)
                    output = (scan.stdout + "\n" + scan.stderr).strip()[:2500]
                    self.server.diagnostic = (
                        "SANE Rückgabecode: " + str(scan.returncode) + "\n"
                        + (output or "Keine Ausgabe."))
                except (OSError, subprocess.TimeoutExpired) as exc:
                    self.server.diagnostic = "Scanerkennung fehlgeschlagen: " + str(exc)
                return self._redirect("/system?ok=Diagnose%20abgeschlossen")
            if path == "/system/password":
                current, new, confirm = (
                    form.get("current_password", ""), form.get("new_password", ""),
                    form.get("confirm_password", ""))
                if not self.server.store.verify_password(current):
                    raise ValueError("Das aktuelle Passwort ist falsch.")
                if new != confirm:
                    raise ValueError("Die neuen Passwörter stimmen nicht überein.")
                self.server.store.set_password(new)
                self.server.sessions.clear()
                return self._redirect("/login", cookie=self._cookie("", expired=True))
            if path == "/backups/restore":
                raw = form.get("backup", b"")
                if not isinstance(raw, bytes) or len(raw) > 128 * 1024:
                    raise ValueError("JSON-Sicherung ist zu groß oder ungültig.")
                payload = json.loads(raw.decode("utf-8"))
                self.server.store.restore(payload)
                return self._redirect("/backups?ok=Konfiguration%20wiederhergestellt")
            return self._error(404, "Aktion nicht gefunden.")
        except (ValueError, OSError, UnicodeError, KeyError, TypeError, PrintError) as exc:
            return self._error(400, "Eingaben nicht übernommen: " + str(exc))


def build_server(bind="127.0.0.1", port=8443, *,
                 cert=None, key=None, db_path=None):
    """Factory for opt-in non-root service, suitable for local security tests."""
    try:
        ip = ipaddress.ip_address(bind)
    except ValueError as exc:
        raise ValueError("Bitte eine konkrete lokale IPv4-Adresse konfigurieren.") from exc
    if ip.version != 4 or ip.is_unspecified or ip.is_multicast:
        raise ValueError("Wildcard/Multicast-Adressen sind nicht erlaubt.")
    if not isinstance(port, int) or not 0 <= port <= 65535:
        raise ValueError("Ungültiger Port.")
    if bool(cert) != bool(key):
        raise ValueError("TLS-Zertifikat und privater Schlüssel werden gemeinsam benötigt.")
    if not ip.is_loopback and not cert:
        raise ValueError("LAN-Zugriff ist ausschließlich mit TLS erlaubt.")
    db = ConfigStore(db_path)
    if not db.has_password():
        raise ValueError("Administratorpasswort fehlt. Erst init-admin über SSH ausführen.")
    server = AdminServer((bind, port), db, secure=bool(cert))
    if cert:
        try:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            context.load_cert_chain(certfile=cert, keyfile=key)
            server.socket = context.wrap_socket(server.socket, server_side=True)
        except Exception:
            server.server_close()
            raise
    return server


def main():
    parser = argparse.ArgumentParser(description="ItomiScan Fernadministration")
    parser.add_argument("--bind", default="127.0.0.1",
                        help="Konkrete IPv4-Adresse (Standard: nur localhost)")
    parser.add_argument("--port", type=int, default=8443)
    parser.add_argument("--cert", help="TLS Zertifikat PEM, für LAN verpflichtend")
    parser.add_argument("--key", help="TLS Schlüssel PEM, für LAN verpflichtend")
    args = parser.parse_args()
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        parser.error("Webdienst niemals als root starten.")
    try:
        server = build_server(args.bind, args.port, cert=args.cert, key=args.key)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    scheme = "https" if args.cert else "http"
    print(f"ItomiScan Webadministration: {scheme}://{args.bind}:{server.server_port}", flush=True)
    try:
        server.serve_forever(poll_interval=0.3)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
