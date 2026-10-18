"""Paperless-ngx credential exchange and read-only connection diagnostics.

Passwords are exchanged once for an API token and never persisted.
All network operations require HTTPS with normal certificate validation.
"""
import http.client
import json
import socket
import ssl
from urllib.parse import urlsplit

MAX_RESPONSE = 4096


class PaperlessDiagnosticError(ValueError):
    pass


def _base(address):
    url = urlsplit(address)
    if (url.scheme != "https" or not url.hostname or url.username or url.password
            or url.query or url.fragment or url.path.rstrip("/").endswith("/api")):
        raise PaperlessDiagnosticError(
            "Paperless-Basisadresse muss HTTPS verwenden und darf keine Zugangsdaten enthalten.")
    return url


def _request(address, method, suffix, *, token=None, payload=None):
    url = _base(address)
    path = url.path.rstrip("/") + suffix
    connection = http.client.HTTPSConnection(
        url.hostname, url.port or 443, timeout=9,
        context=ssl.create_default_context())
    try:
        headers = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = "Token " + token
        body = None
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        data = response.read(MAX_RESPONSE + 1)
        if len(data) > MAX_RESPONSE:
            data = data[:MAX_RESPONSE]
        return response.status, response.getheader("Content-Type", ""), data
    finally:
        connection.close()


def _explain(code):
    if code == 401:
        return "Authentifizierung abgelehnt. API-Token oder Benutzeranmeldung prüfen."
    if code == 403:
        return ("Zugriff verweigert (403). Paperless-Benutzerrechte und "
                "vorgeschalteten Proxy bzw. CSRF-Einstellungen prüfen.")
    if code == 404:
        return "API-Endpunkt nicht gefunden (404). Paperless-Basisadresse und Proxy-Pfad prüfen."
    if code == 429:
        return "Zu viele Anmeldeversuche (429). Bitte später erneut versuchen."
    if 300 <= code < 400:
        return "Weiterleitung statt API-Antwort. Anmeldeschutz oder Reverse Proxy prüfen."
    if code >= 500:
        return "Paperless oder Reverse Proxy meldet einen Serverfehler."
    return "Unerwartete API-Antwort (HTTP %s)." % code


def _network_error(exc):
    if isinstance(exc, ssl.SSLCertVerificationError):
        return "TLS-Zertifikat nicht vertrauenswürdig oder Hostname stimmt nicht."
    if isinstance(exc, ssl.SSLError):
        return "TLS-Verbindung fehlgeschlagen. Zertifikat oder Protokoll prüfen."
    if isinstance(exc, (socket.timeout, TimeoutError)):
        return "Zeitüberschreitung: Paperless antwortet nicht rechtzeitig."
    if isinstance(exc, socket.gaierror):
        return "DNS-Auflösung fehlgeschlagen. Servernamen prüfen."
    return "Verbindung zum Paperless-Server fehlgeschlagen. Adresse und Netzwerk prüfen."


def diagnose_paperless(address, token):
    """No uploads or mutations. Structured, secret-free diagnostic summary."""
    if not token:
        return {"ok": False, "steps": [{"name": "Token", "ok": False,
                 "message": "Kein API-Token gespeichert. Bitte zuerst anmelden oder Token hinterlegen."}]}
    steps = []
    try:
        _base(address)
        steps.append({"name": "HTTPS-Adresse", "ok": True,
                      "message": "HTTPS-Basisadresse gültig."})
        status, content_type, body = _request(address, "GET", "/api/profile/", token=token)
        if status != 200:
            steps.append({"name": "Anmeldung", "ok": False, "http": status,
                          "message": _explain(status)})
            return {"ok": False, "steps": steps}
        if "json" not in content_type.lower():
            steps.append({"name": "API-Antwort", "ok": False,
                          "message": "Statt JSON wird eine andere Seite geliefert. Proxy prüfen."})
            return {"ok": False, "steps": steps}
        try:
            profile = json.loads(body)
        except (ValueError, UnicodeError):
            profile = None
        if not isinstance(profile, dict):
            steps.append({"name": "API-Antwort", "ok": False,
                          "message": "Ungültige Profilantwort von Paperless."})
            return {"ok": False, "steps": steps}
        steps.append({"name": "Token-Anmeldung", "ok": True,
                      "message": "Token wird von der Paperless-API akzeptiert."})
        status, _, _ = _request(address, "GET", "/api/documents/?page_size=1", token=token)
        if status == 200:
            steps.append({"name": "Dokumenten-Lesezugriff", "ok": True,
                          "message": "Dokumentenliste kann gelesen werden."})
        else:
            steps.append({"name": "Dokumenten-Lesezugriff", "ok": False, "http": status,
                          "message": _explain(status) +
                          " Das sagt noch nichts über die Berechtigung zum Hochladen."})
        steps.append({"name": "Upload-Berechtigung", "ok": None,
                      "message": "Nicht durch einen rein lesenden Test nachweisbar. "
                                 "Für das Hochladen braucht der Benutzer die Berechtigung "
                                 "zum Hinzufügen von Dokumenten."})
        return {"ok": True, "steps": steps,
                "message": "Anmeldung erfolgreich; ein Dokument wurde nicht hochgeladen."}
    except (OSError, ssl.SSLError, TimeoutError, http.client.HTTPException) as exc:
        steps.append({"name": "Verbindung", "ok": False, "message": _network_error(exc)})
        return {"ok": False, "steps": steps}
    except (PaperlessDiagnosticError, ValueError) as exc:
        steps.append({"name": "Adresse", "ok": False, "message": str(exc)})
        return {"ok": False, "steps": steps}


def exchange_credentials(address, username, password):
    """Use Paperless token API; do not retain username or password."""
    if not username or not password or len(username) > 200 or len(password) > 400:
        raise PaperlessDiagnosticError("Bitte Benutzername und Passwort eingeben.")
    try:
        status, content_type, data = _request(
            address, "POST", "/api/token/",
            payload={"username": username, "password": password})
    except (OSError, ssl.SSLError, TimeoutError, http.client.HTTPException) as exc:
        raise PaperlessDiagnosticError(_network_error(exc)) from None
    if status != 200:
        raise PaperlessDiagnosticError(_explain(status))
    if "json" not in content_type.lower():
        raise PaperlessDiagnosticError("Token-API liefert kein JSON. Proxy prüfen.")
    try:
        token = json.loads(data).get("token", "")
    except (ValueError, UnicodeError, AttributeError):
        token = ""
    if not isinstance(token, str) or not 1 <= len(token) <= 400:
        raise PaperlessDiagnosticError("Paperless hat keinen gültigen Token zurückgegeben.")
    return token
