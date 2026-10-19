"""Authenticated, on-demand loopback-only x11vnc bridge for the kiosk display.

The HTTPS web server is the only network-facing endpoint. x11vnc is started
only for an authorized RemoteLive lease, never exposed on the LAN.
"""
import base64
import hashlib
import os
from pathlib import Path
import secrets
import select
import shutil
import socket
import struct
import subprocess
import tempfile
import threading
import time

NOVNC_ROOT = Path("/usr/share/novnc")
MAX_WS_MESSAGE = 1024 * 1024


class VNCUnavailable(ValueError):
    pass


class VNCBridge:
    def __init__(self, live):
        self.live = live
        self._lock = threading.RLock()
        self._process = None
        self._owner = None
        self._password = None
        self._private = None
        self._port = None
        threading.Thread(target=self._watch, name="itomiscan-vnc-watch", daemon=True).start()

    def ready(self):
        return bool(shutil.which("x11vnc") and (NOVNC_ROOT / "core" / "rfb.js").is_file())

    def _stop_locked(self):
        process = self._process
        self._process = None
        self._owner = self._password = self._port = None
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
        if self._private is not None:
            self._private.cleanup()
            self._private = None

    def stop(self, owner):
        with self._lock:
            if owner == self._owner:
                self._stop_locked()

    def _watch(self):
        while True:
            time.sleep(2)
            with self._lock:
                if self._owner and (not self.live.authorized(self._owner)
                                    or self._process.poll() is not None):
                    self._stop_locked()

    def start(self, owner):
        with self._lock:
            if not self.ready():
                raise VNCUnavailable("x11vnc oder noVNC fehlt. Bitte Beta-VNC-Pakete installieren.")
            if self._owner == owner and self._process and self._process.poll() is None:
                return self._password
            if self._owner is not None and self.live.active():
                raise VNCUnavailable("Die Fernsteuerung wird bereits anderswo verwendet.")
            self._stop_locked()
            self._private = tempfile.TemporaryDirectory(prefix="itomiscan-vnc-")
            path = Path(self._private.name) / "password"
            password = secrets.token_urlsafe(12)
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "w") as output:
                output.write(password + "\n")
            # Reserve a random localhost port; x11vnc will bind immediately after.
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", 0))
                port = probe.getsockname()[1]
            command = [
                shutil.which("x11vnc"), "-display", ":0",
                "-localhost", "-rfbport", str(port), "-passwdfile", str(path),
                "-once", "-nevershared", "-noxdamage", "-quiet",
            ]
            try:
                self._process = subprocess.Popen(
                    command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL, close_fds=True)
                deadline = time.monotonic() + 4
                while time.monotonic() < deadline:
                    if self._process.poll() is not None:
                        raise VNCUnavailable("x11vnc konnte den Kiosk-Bildschirm nicht öffnen.")
                    # Do not connect to the RFB port here: -once counts connections.
                    time.sleep(0.1)
                    if time.monotonic() + 0.1 >= deadline:
                        break
                self._owner, self._password, self._port = owner, password, port
                return password
            except Exception:
                self._stop_locked()
                raise

    def password(self, owner):
        with self._lock:
            if (owner == self._owner and self.live.authorized(owner)
                    and self._process and self._process.poll() is None):
                return self._password
            return None

    def connect(self, owner):
        with self._lock:
            if not self.password(owner):
                raise VNCUnavailable("VNC-Sitzung nicht aktiv.")
            port = self._port
        return socket.create_connection(("127.0.0.1", port), timeout=3)


def _read_exact(connection, count):
    data = bytearray()
    while len(data) < count:
        piece = connection.recv(count - len(data))
        if not piece:
            raise ConnectionError("Verbindung geschlossen.")
        data.extend(piece)
    return bytes(data)


def _send_frame(connection, payload, opcode=2, lock=None):
    header = bytearray([0x80 | opcode])
    size = len(payload)
    if size < 126:
        header.append(size)
    elif size < 65536:
        header.extend([126])
        header.extend(struct.pack("!H", size))
    else:
        header.extend([127])
        header.extend(struct.pack("!Q", size))
    if lock is None:
        connection.sendall(bytes(header) + payload)
    else:
        with lock:
            connection.sendall(bytes(header) + payload)


def _receive_frame(connection):
    start = _read_exact(connection, 2)
    final = bool(start[0] & 0x80)
    opcode = start[0] & 0x0f
    masked = bool(start[1] & 0x80)
    length = start[1] & 0x7f
    if length == 126:
        length = struct.unpack("!H", _read_exact(connection, 2))[0]
    elif length == 127:
        length = struct.unpack("!Q", _read_exact(connection, 8))[0]
    if not masked or length > MAX_WS_MESSAGE:
        raise ValueError("Ungültiger WebSocket-Frame.")
    key = _read_exact(connection, 4)
    data = _read_exact(connection, length)
    return final, opcode, bytes(value ^ key[index % 4] for index, value in enumerate(data))


def serve_websocket(handler, bridge, owner):
    """Upgrade only an authenticated, same-origin, single-viewer WSS request."""
    if not handler.server.secure:
        return handler._error(403, "VNC benötigt HTTPS.")
    expected = "https://%s:%s" % (handler.server.bind_ip, handler.server.server_port)
    if handler.headers.get("Origin") != expected:
        return handler._error(403, "Ungültiger WebSocket-Ursprung.")
    if handler.headers.get("Upgrade", "").lower() != "websocket":
        return handler._error(400, "WebSocket-Upgrade erforderlich.")
    if "upgrade" not in handler.headers.get("Connection", "").lower().split(","):
        return handler._error(400, "WebSocket-Verbindung erforderlich.")
    key = handler.headers.get("Sec-WebSocket-Key", "")
    try:
        raw = base64.b64decode(key, validate=True)
        if len(raw) != 16:
            raise ValueError()
    except (ValueError, Exception):
        return handler._error(400, "Ungültiger WebSocket-Schlüssel.")
    if handler.headers.get("Sec-WebSocket-Version") != "13":
        return handler._error(400, "WebSocket-Version nicht unterstützt.")
    if handler.headers.get("Sec-WebSocket-Extensions"):
        return handler._error(400, "WebSocket-Erweiterungen nicht unterstützt.")
    try:
        backend = bridge.connect(owner)
    except (OSError, VNCUnavailable):
        return handler._error(503, "VNC-Verbindung nicht bereit.")
    accept = base64.b64encode(hashlib.sha1(
        (key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")
    ).digest()).decode("ascii")
    handler.send_response(101, "Switching Protocols")
    handler.send_header("Upgrade", "websocket")
    handler.send_header("Connection", "Upgrade")
    handler.send_header("Sec-WebSocket-Accept", accept)
    handler.send_header("Sec-WebSocket-Protocol", "binary")
    handler.end_headers()
    handler.close_connection = True
    writing = threading.Lock()
    ended = threading.Event()

    def downstream():
        try:
            while not ended.is_set() and bridge.live.authorized(owner):
                readable, _, _ = select.select([backend], [], [], 1)
                if readable:
                    data = backend.recv(32768)
                    if not data:
                        break
                    _send_frame(handler.connection, data, lock=writing)
        except (OSError, ValueError, ConnectionError):
            pass
        finally:
            ended.set()
            try:
                handler.connection.shutdown(socket.SHUT_RD)
            except OSError:
                pass

    threading.Thread(target=downstream, daemon=True).start()
    try:
        handler.connection.settimeout(2)
        fragment = bytearray()
        while not ended.is_set() and bridge.live.authorized(owner):
            try:
                final, opcode, payload = _receive_frame(handler.connection)
            except socket.timeout:
                continue
            if opcode == 8:
                break
            if opcode == 9:
                _send_frame(handler.connection, payload, opcode=10, lock=writing)
                continue
            if opcode not in (0, 2):
                raise ValueError("Nur binäre VNC-Daten erlaubt.")
            fragment.extend(payload)
            if len(fragment) > MAX_WS_MESSAGE:
                raise ValueError("VNC-Nachricht zu groß.")
            if final:
                backend.sendall(fragment)
                fragment.clear()
    except (OSError, ConnectionError, ValueError):
        pass
    finally:
        ended.set()
        backend.close()
