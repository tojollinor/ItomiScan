"""Read-only LAN printer identity verification, without extra dependencies.

Only mDNS-resolved private IPv4 IPP/IPPS endpoints are contacted. All
connections and responses are bounded. A name, model or IP alone is NEVER an
identity; no automatic CUPS installation takes place during discovery.
"""
import csv
import http.client
import io
import ipaddress
import re
import shutil
import ssl
import struct
import subprocess
from urllib.parse import quote

MAX_REPLY = 65536
UUID_RE = re.compile(r"^(?:urn:uuid:)?[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
VALID_PATH = re.compile(r"[A-Za-z0-9/_.~%-]{1,179}\Z")
TAGS = {0x41, 0x42, 0x44, 0x45, 0x46, 0x47, 0x48, 0x49}


def _private_ip(value):
    try:
        ip = ipaddress.ip_address(value)
        return ip.version == 4 and ip.is_private and not (
            ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_unspecified)
    except ValueError:
        return False


def _txt(row):
    result = {}
    for item in row[9:]:
        item = item.strip().strip('"')
        if "=" in item:
            key, value = item.split("=", 1)
            result[key.lower()] = value.strip('"')
    return result


def browse_endpoints(timeout=4):
    """Keep every distinct service/queue separate until IPP proves identity."""
    if not shutil.which("avahi-browse"):
        return []
    endpoints = {}
    for service, scheme in (("_ipps._tcp", "ipps"), ("_ipp._tcp", "ipp")):
        try:
            output = subprocess.run(
                ["avahi-browse", "-rtp", service], capture_output=True, text=True,
                timeout=timeout, check=False).stdout
        except (OSError, subprocess.TimeoutExpired):
            continue
        for row in csv.reader(io.StringIO(output), delimiter=";"):
            if len(row) < 9 or row[0] != "=" or row[2] != "IPv4":
                continue
            ip = row[7].strip()
            if not _private_ip(ip):
                continue
            try:
                port = int(row[8])
            except ValueError:
                continue
            if not 1 <= port <= 65535:
                continue
            txt = _txt(row)
            path = txt.get("rp", "ipp/print").lstrip("/")
            if not VALID_PATH.fullmatch(path) or ".." in path:
                continue
            uri = f"{scheme}://{ip}:{port}/{quote(path, safe='/-_.~%')}"
            endpoints[uri] = {
                "uri": uri, "ip": ip, "port": port, "path": "/" + path,
                "scheme": scheme, "name": row[3][:100], "txt": txt,
            }
    return list(endpoints.values())[:40]


def _attribute(name, value):
    encoded = name.encode("ascii")
    tag = {
        "attributes-charset": 0x47,
        "attributes-natural-language": 0x48,
        "printer-uri": 0x45,
    }.get(name, 0x44)
    return (bytes((tag,)) + struct.pack(">H", len(encoded)) + encoded +
            struct.pack(">H", len(value)) + value)

def _request(endpoint):
    """IPP Get-Printer-Attributes, bounded response and validated TLS for IPPS."""
    path = endpoint["path"]
    host = endpoint["ip"]
    uri = endpoint["uri"]
    # Request all printer attributes; the parser only keeps vetted names.
    body = (b"\x02\x00\x00\x0b\x00\x00\x00\x01\x01" +
            _attribute("attributes-charset", b"utf-8") +
            _attribute("attributes-natural-language", b"en") +
            _attribute("printer-uri", uri.encode("ascii")) + b"\x03")
    connection = (http.client.HTTPSConnection(host, endpoint["port"], timeout=3,
                  context=ssl.create_default_context()) if endpoint["scheme"] == "ipps"
                  else http.client.HTTPConnection(host, endpoint["port"], timeout=3))
    try:
        connection.request("POST", path, body=body,
                           headers={"Content-Type": "application/ipp",
                                    "Accept": "application/ipp"})
        response = connection.getresponse()
        if response.status != 200 or "application/ipp" not in response.getheader("Content-Type", ""):
            return {}
        raw = response.read(MAX_REPLY + 1)
        if len(raw) > MAX_REPLY:
            return {}
        return parse_ipp(raw)
    finally:
        connection.close()


def parse_ipp(raw):
    """Extract the first string-valued printer attributes; reject IPP errors."""
    if len(raw) < 9 or raw[0] not in (1, 2) or raw[2:4] != b"\x00\x00":
        return {}
    index = 8
    current = ""
    attrs = {}
    while index < len(raw):
        tag = raw[index]
        index += 1
        if tag == 3:
            break
        if tag <= 0x0f:
            continue
        if index + 4 > len(raw):
            break
        name_len = int.from_bytes(raw[index:index+2], "big")
        index += 2
        if index + name_len + 2 > len(raw):
            break
        if name_len:
            current = raw[index:index+name_len].decode("utf-8", "replace")
        index += name_len
        value_len = int.from_bytes(raw[index:index+2], "big")
        index += 2
        if index + value_len > len(raw):
            break
        if tag in TAGS and current in ("printer-uuid", "printer-device-id",
                                        "printer-make-and-model", "printer-name"):
            attrs.setdefault(current, raw[index:index+value_len].decode("utf-8", "replace")[:240])
        index += value_len
    return attrs


def discover_verified_printers(*, browse=browse_endpoints, query=_request):
    """Return one selectable device per verified UUID, plus unverified count."""
    devices = {}
    unverified = 0
    for endpoint in browse():
        try:
            attrs = query(endpoint)
        except (OSError, ValueError, ssl.SSLError, http.client.HTTPException):
            unverified += 1
            continue
        uuid = attrs.get("printer-uuid", "").strip().lower()
        if not UUID_RE.fullmatch(uuid):
            # Do not trust DNS-SD TXT UUID or model alone as definitive identity.
            unverified += 1
            continue
        uuid = uuid.removeprefix("urn:uuid:")
        label = (attrs.get("printer-make-and-model") or
                 endpoint.get("name") or "Netzwerkdrucker").strip()[:80]
        key = uuid
        existing = devices.get(key)
        candidate = {"name": label, "ip": endpoint["ip"],
                     "uri": endpoint["uri"], "identity": uuid}
        if existing is None:
            devices[key] = candidate
        elif (candidate["uri"].startswith("ipps://") and
              not existing["uri"].startswith("ipps://")):
            devices[key] = candidate
    return sorted(devices.values(), key=lambda x:(x["name"].casefold(),x["ip"])), unverified
