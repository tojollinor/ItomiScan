"""Bounded, optional LAN service discovery for Paperless candidates.

mDNS discovery is best-effort. Never scan whole subnets, never store or
transmit credentials and never claim a discovered candidate is authenticated.
"""
import csv
import io
import ipaddress
import shutil
import subprocess


def discover_paperless(timeout=4):
    """Return HTTPS URL suggestions explicitly advertised over local DNS-SD.

    Only Paperless-named services on private IPv4 addresses are considered.
    An advertised name does not prove the endpoint runs Paperless.
    """
    if not shutil.which("avahi-browse"):
        return []
    found = set()
    for service in ("_https._tcp", "_paperless._tcp"):
        try:
            output = subprocess.run(
                ["avahi-browse", "-rtp", service],
                capture_output=True, text=True, timeout=timeout,
                check=False).stdout
        except (OSError, subprocess.TimeoutExpired):
            continue
        for row in csv.reader(io.StringIO(output), delimiter=";"):
            # Resolved records: =;interface;IPv4;name;type;domain;host;address;port;TXT...
            if len(row) < 9 or row[0] != "=" or row[2] != "IPv4":
                continue
            if "paperless" not in (row[3] + " " + row[4]).lower():
                continue
            try:
                address = ipaddress.ip_address(row[7])
                port = int(row[8])
                if not address.is_private or not 1 <= port <= 65535:
                    continue
            except ValueError:
                continue
            if service == "_paperless._tcp" and port not in (443, 8443):
                # Never silently downgrade a possibly private API to HTTP.
                continue
            suffix = "" if port == 443 else ":" + str(port)
            found.add("https://" + str(address) + suffix)
    return sorted(found)[:20]


def discover_ipp_printers(timeout=4):
    """Find DNS-SD advertised IPP printers on private IPv4 LAN addresses.

    Return candidate URIs only, never install CUPS queues automatically.
    No host/subnet port scan is performed and no printer is contacted.
    """
    from urllib.parse import quote

    if not shutil.which("avahi-browse"):
        return []
    found = set()
    for service, scheme in (("_ipps._tcp", "ipps"), ("_ipp._tcp", "ipp")):
        try:
            output = subprocess.run(
                ["avahi-browse", "-rtp", service],
                capture_output=True, text=True, timeout=timeout,
                check=False).stdout
        except (OSError, subprocess.TimeoutExpired):
            continue
        for row in csv.reader(io.StringIO(output), delimiter=";"):
            if len(row) < 9 or row[0] != "=" or row[2] != "IPv4":
                continue
            try:
                address = ipaddress.ip_address(row[7])
                port = int(row[8])
            except ValueError:
                continue
            if (address.version != 4 or not address.is_private
                    or address.is_loopback or address.is_link_local
                    or address.is_multicast or not 1 <= port <= 65535):
                continue
            # RFC 6763 TXT keys: e.g. rp=ipp/print. Ignore unsafe
            # paths and credentials rather than reconstructing them.
            path = "ipp/print"
            for field in row[9:]:
                value = field.strip().strip('"')
                if value.lower().startswith("rp="):
                    candidate = value[3:].lstrip("/")
                    if (candidate and len(candidate) < 180
                            and all(ch.isalnum() or ch in "/-_.~%" for ch in candidate)
                            and ".." not in candidate):
                        path = candidate
                    break
            uri = f"{scheme}://{address}:{port}/{quote(path, safe='/-_.~%')}"
            found.add(uri)
    return sorted(found)[:30]
