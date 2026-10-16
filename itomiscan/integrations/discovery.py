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
