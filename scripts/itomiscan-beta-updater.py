#!/usr/bin/python3
"""Root-owned, narrowly scoped ItomiScan beta updater.

Installed at /usr/local/libexec/itomiscan-beta-updater with mode 0755.
Never import Python from the user-writable ItomiScan source as root.
Only published beta tags from the fixed official GitHub repository are accepted.
"""
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import pwd
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
from urllib.request import Request, urlopen

CONFIG = Path("/etc/itomiscan/updater.json")
STATE = Path("/var/lib/itomiscan-updater")
LOCK = Path("/run/lock/itomiscan-beta-updater.lock")
API = "https://api.github.com/repos/tojollinor/ItomiScan/"
ARCHIVE = "https://github.com/tojollinor/ItomiScan/archive/"
TAG_RE = re.compile(r"^v([0-9]+)\.([0-9]+)\.([0-9]+)-beta\.([0-9]+)$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
MAX_ARCHIVE = 32 * 1024 * 1024
MAX_EXTRACTED = 128 * 1024 * 1024
MAX_FILES = 2500


class UpdateError(RuntimeError):
    pass


def progress(percent, message, *, state="running"):
    print(json.dumps({"percent": int(percent), "message": message, "state": state},
                     ensure_ascii=False), flush=True)


def fetch_json(path):
    request = Request(API + path, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "ItomiScan-Device-Beta-Updater",
    })
    with urlopen(request, timeout=25) as response:
        data = response.read(2 * 1024 * 1024 + 1)
    if len(data) > 2 * 1024 * 1024:
        raise UpdateError("GitHub-Antwort zu groß.")
    return json.loads(data.decode("utf-8"))


def latest_beta(releases):
    """Never deploy arbitrary development heads or stable releases."""
    candidates = []
    for entry in releases:
        if not isinstance(entry, dict) or not entry.get("prerelease") or entry.get("draft"):
            continue
        tag = entry.get("tag_name", "")
        match = TAG_RE.fullmatch(tag) if isinstance(tag, str) else None
        if match:
            candidates.append((tuple(int(value) for value in match.groups()), tag))
    if not candidates:
        raise UpdateError("Kein veröffentlichtes Beta-Release gefunden.")
    return max(candidates)[1]


def release_commit(tag):
    if not TAG_RE.fullmatch(tag):
        raise UpdateError("Ungültiges Beta-Tag.")
    result = fetch_json("commits/" + tag)
    sha = result.get("sha")
    tree = (result.get("commit") or {}).get("tree") or {}
    tree_sha = tree.get("sha")
    if not isinstance(sha, str) or not SHA_RE.fullmatch(sha):
        raise UpdateError("GitHub-Commit nicht verifizierbar.")
    if not isinstance(tree_sha, str) or not SHA_RE.fullmatch(tree_sha):
        raise UpdateError("GitHub-Tree nicht verifizierbar.")
    return sha, tree_sha


def expected_tree(tree_sha):
    response = fetch_json("git/trees/" + tree_sha + "?recursive=1")
    if response.get("truncated"):
        raise UpdateError("GitHub-Dateiliste unvollständig.")
    entries = response.get("tree")
    if not isinstance(entries, list):
        raise UpdateError("GitHub-Dateiliste ungültig.")
    files = {}
    for entry in entries:
        if entry.get("type") == "tree":
            continue
        if entry.get("type") != "blob" or entry.get("mode") not in ("100644", "100755"):
            raise UpdateError("Nicht unterstützter Dateityp im Release.")
        path = entry.get("path")
        sha = entry.get("sha")
        if not isinstance(path, str) or not isinstance(sha, str) or not SHA_RE.fullmatch(sha):
            raise UpdateError("Ungültiger Dateieintrag.")
        pure = PurePosixPath(path)
        if pure.is_absolute() or ".." in pure.parts or not pure.parts or path in files:
            raise UpdateError("Unsicherer Dateipfad im GitHub-Release.")
        files[path] = (sha, int(entry["mode"][-3:], 8))
    if not {"app.py", "install-beta.sh", "itomiscan/gui/kiosk.py"}.issubset(files):
        raise UpdateError("Release enthält nicht die notwendigen Systemdateien.")
    if len(files) > MAX_FILES:
        raise UpdateError("Zu viele Dateien im Release.")
    return files


def git_blob_sha(contents):
    return hashlib.sha1(b"blob " + str(len(contents)).encode("ascii")
                        + b"\0" + contents).hexdigest()


def download_archive(sha, destination):
    if not SHA_RE.fullmatch(sha):
        raise UpdateError("Ungültiger Archiv-Commit.")
    request = Request(ARCHIVE + sha + ".tar.gz", headers={
        "User-Agent": "ItomiScan-Device-Beta-Updater"})
    downloaded = 0
    digest = hashlib.sha256()
    with urlopen(request, timeout=60) as response, destination.open("xb") as output:
        while True:
            chunk = response.read(128 * 1024)
            if not chunk:
                break
            downloaded += len(chunk)
            if downloaded > MAX_ARCHIVE:
                raise UpdateError("Archiv überschreitet Größenlimit.")
            digest.update(chunk)
            output.write(chunk)
    if not downloaded:
        raise UpdateError("Leeres Release-Archiv.")
    return digest.hexdigest()


def extract_verified_archive(archive, destination, expected):
    """Validate every Git blob before extraction; reject links and extra files."""
    destination.mkdir(mode=0o755)
    seen = set()
    total = 0
    with tarfile.open(archive, "r:gz") as packed:
        members = packed.getmembers()
        if not members or len(members) > MAX_FILES * 3:
            raise UpdateError("Release-Archiv ist leer oder zu groß.")
        root = members[0].name.split("/", 1)[0]
        if not root or root in (".", ".."):
            raise UpdateError("Ungültiges Archivverzeichnis.")
        for member in members:
            name = member.name
            if name == root and member.isdir():
                continue
            if not name.startswith(root + "/"):
                raise UpdateError("Archiv enthält fremde Dateipfade.")
            relative = name[len(root) + 1:]
            parts = PurePosixPath(relative)
            if not relative or parts.is_absolute() or ".." in parts.parts:
                raise UpdateError("Archiv enthält unsichere Dateipfade.")
            if member.isdir():
                continue
            if not member.isfile() or relative not in expected or relative in seen:
                raise UpdateError("Archiv enthält unbekannte Datei oder Verknüpfung.")
            if member.size < 0 or member.size > MAX_EXTRACTED:
                raise UpdateError("Unzulässige Dateigröße.")
            total += member.size
            if total > MAX_EXTRACTED:
                raise UpdateError("Archiv überschreitet entpacktes Größenlimit.")
            stream = packed.extractfile(member)
            if stream is None:
                raise UpdateError("Archivdatei ist nicht lesbar.")
            data = stream.read(member.size + 1)
            if len(data) != member.size or git_blob_sha(data) != expected[relative][0]:
                raise UpdateError("Dateihash stimmt nicht mit GitHub-Commit überein.")
            target = destination.joinpath(*parts.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as output:
                output.write(data)
            target.chmod(expected[relative][1])
            seen.add(relative)
    if seen != set(expected):
        raise UpdateError("Release-Dateien fehlen im Archiv.")


def preflight(settings):
    if os.geteuid() != 0:
        raise UpdateError("Updater muss über die autorisierte Root-Hilfe starten.")
    if not isinstance(settings, dict):
        raise UpdateError("Updater-Konfiguration ungültig.")
    user = settings.get("user")
    home = settings.get("home")
    if not isinstance(user, str) or not re.fullmatch(r"[a-z_][a-z0-9_-]*", user):
        raise UpdateError("Konfigurierter Benutzer ungültig.")
    account = pwd.getpwnam(user)
    if account.pw_uid == 0 or home != account.pw_dir or not home.startswith("/home/"):
        raise UpdateError("Updater-Konfiguration passt nicht zum Scanbenutzer.")
    project = Path(home) / "ItomiScan"
    if not project.is_dir() or project.is_symlink() or not (project / "app.py").is_file():
        raise UpdateError("ItomiScan-Installation nicht gefunden.")
    if shutil.disk_usage(home).free < 600 * 1024 * 1024:
        raise UpdateError("Weniger als 600 MiB für Update und Sicherung frei.")
    return user, account.pw_uid, account.pw_gid, Path(home), project


def read_settings():
    st = CONFIG.stat()
    if st.st_uid != 0 or (st.st_mode & 0o022):
        raise UpdateError("Updater-Konfiguration ist nicht ausreichend geschützt.")
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def compile_python(stage):
    for path in stage.rglob("*.py"):
        compile(path.read_bytes(), str(path), "exec")


def smoke_as_user(user, stage):
    command = ["/usr/sbin/runuser", "-u", user, "--", "/usr/bin/env",
               "PYTHONPATH=" + str(stage), "/usr/bin/python3", "-c",
               "import itomiscan; import itomiscan.gui.kiosk; import itomiscan.web.server"]
    result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                            timeout=35, check=False, text=True)
    if result.returncode != 0:
        raise UpdateError("Importtest fehlgeschlagen: " + result.stderr[-350:])


def chown_tree(stage, uid, gid):
    for folder, dirs, files in os.walk(stage, followlinks=False):
        os.chown(folder, uid, gid)
        for file in files:
            os.chown(Path(folder) / file, uid, gid)


def marker(stage, tag, sha):
    (stage / ".itomiscan-beta-tag").write_text(tag + "\n", encoding="ascii")
    (stage / ".itomiscan-beta-commit").write_text(sha + "\n", encoding="ascii")


def atomic_deploy(project, stage, snapshot):
    """Prepare backup before replacing code. Restore immediately on failure."""
    previous = project.with_name(project.name + ".updater-previous")
    if previous.exists() or previous.is_symlink():
        raise UpdateError("Eine frühere Update-Transaktion ist noch offen.")
    if not project.is_dir() or project.is_symlink():
        raise UpdateError("Installationspfad hat sich unerwartet geändert.")
    shutil.copytree(project, snapshot, symlinks=True)
    os.replace(project, previous)
    try:
        os.replace(stage, project)
    except BaseException:
        os.replace(previous, project)
        raise
    return previous


def restore_after_failure(project, previous):
    if not previous.exists():
        return
    failed = project.with_name(project.name + ".updater-failed")
    if failed.exists():
        shutil.rmtree(failed)
    if project.exists():
        os.replace(project, failed)
    os.replace(previous, project)
    if failed.exists():
        shutil.rmtree(failed)


def write_backup_reference(path, tag, sha):
    STATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    doc = {"path": str(path), "tag": tag, "sha": sha}
    temp = STATE / "last.json.tmp"
    with temp.open("w", encoding="utf-8") as out:
        json.dump(doc, out)
        out.flush()
        os.fsync(out.fileno())
    temp.chmod(0o600)
    os.replace(temp, STATE / "last.json")


def install():
    settings = read_settings()
    user, uid, gid, home, project = preflight(settings)
    progress(5, "Berechtigungen und Speicher geprüft.")
    releases = fetch_json("releases?per_page=30")
    tag = latest_beta(releases)
    sha, tree_sha = release_commit(tag)
    local_marker = project / ".itomiscan-beta-commit"
    local_sha = local_marker.read_text(encoding="ascii").strip() if local_marker.exists() else ""
    local_tag_file = project / ".itomiscan-beta-tag"
    local_tag = local_tag_file.read_text(encoding="ascii").strip() if local_tag_file.exists() else ""
    if local_sha == sha:
        raise UpdateError("Die neueste Beta ist bereits installiert.")
    if TAG_RE.fullmatch(local_tag) and (tuple(map(int, TAG_RE.fullmatch(local_tag).groups()))
                                         >= tuple(map(int, TAG_RE.fullmatch(tag).groups()))):
        raise UpdateError("Kein neueres veröffentlichtes Beta-Release verfügbar.")
    progress(15, "Freigegebene Version " + tag + " gefunden.")
    tree = expected_tree(tree_sha)
    progress(28, "GitHub-Commit und Dateiliste geprüft.")
    with tempfile.TemporaryDirectory(prefix=".itomiscan-update-", dir=home) as workspace:
        work = Path(workspace)
        work.chmod(0o755)
        archive = work / "release.tar.gz"
        sha256 = download_archive(sha, archive)
        progress(45, "Download abgeschlossen; SHA256: " + sha256[:16] + "…")
        stage = work / "stage"
        extract_verified_archive(archive, stage, tree)
        progress(62, "Alle Dateien anhand ihrer Git-Blob-Hashes geprüft.")
        compile_python(stage)
        # The verified VNC release needs these fixed Debian packages, not
        # arbitrary names supplied by the archive or web interface.
        if "itomiscan/web/vnc_bridge.py" in tree and (
                not shutil.which("x11vnc") or
                not Path("/usr/share/novnc/core/rfb.js").is_file()):
            progress(65, "Fehlende VNC-Pakete werden eingerichtet.")
            subprocess.run(["/usr/bin/apt-get", "update"], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                           timeout=150)
            subprocess.run(["/usr/bin/apt-get", "install", "-y",
                            "--no-install-recommends", "x11vnc", "novnc"],
                           check=True, stdout=subprocess.DEVNULL,
                           stderr=subprocess.PIPE, timeout=240)
        marker(stage, tag, sha)
        chown_tree(stage, uid, gid)
        smoke_as_user(user, stage)
        progress(72, "Python- und Importprüfung erfolgreich.")
        STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
        snapshot = STATE / ("backup-" + str(int(time.time())) + "-" + sha[:8])
        progress(76, "Sichere Kopie der bisherigen Installation wird erstellt.")
        previous = atomic_deploy(project, stage, snapshot)
        try:
            smoke_as_user(user, project)
            progress(94, "Installierte Beta erneut überprüft.")
            # Installationsmarker are validated after the atomic swap.
            if (project / ".itomiscan-beta-commit").read_text().strip() != sha:
                raise UpdateError("Installationsversion nicht konsistent.")
            write_backup_reference(snapshot, local_tag, local_sha)
            shutil.rmtree(previous)
        except BaseException:
            restore_after_failure(project, previous)
            raise
    progress(100, tag + " installiert. Neustart zur Aktivierung erforderlich.", state="success")


def rollback():
    settings = read_settings()
    user, uid, gid, home, project = preflight(settings)
    pointer = STATE / "last.json"
    if not pointer.exists():
        raise UpdateError("Keine Wiederherstellungssicherung vorhanden.")
    info = json.loads(pointer.read_text(encoding="utf-8"))
    backup = Path(info.get("path", ""))
    if backup.parent != STATE or not backup.name.startswith("backup-") or not backup.is_dir():
        raise UpdateError("Ungültige Sicherungsreferenz.")
    progress(12, "Vorherige Installation wird vorbereitet.")
    with tempfile.TemporaryDirectory(prefix=".itomiscan-rollback-", dir=home) as workspace:
        work = Path(workspace)
        work.chmod(0o755)
        stage = work / "restored"
        shutil.copytree(backup, stage, symlinks=True)
        compile_python(stage)
        chown_tree(stage, uid, gid)
        smoke_as_user(user, stage)
        progress(66, "Sicherung validiert.")
        previous = project.with_name(project.name + ".updater-previous")
        if previous.exists():
            raise UpdateError("Noch offene Update-Transaktion.")
        os.replace(project, previous)
        try:
            os.replace(stage, project)
            smoke_as_user(user, project)
        except BaseException:
            restore_after_failure(project, previous)
            raise
        shutil.rmtree(previous)
        pointer.unlink()
    progress(100, "Vorherige Installation wiederhergestellt. Neustart erforderlich.",
             state="success")


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ("install", "rollback"):
        progress(0, "Nur install oder rollback ist zulässig.", state="error")
        return 2
    if os.geteuid() != 0:
        progress(0, "Updater benötigt die freigegebene Root-Hilfe.", state="error")
        return 2
    with LOCK.open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            progress(0, "Bereits eine Aktualisierung aktiv.", state="error")
            return 3
        try:
            if sys.argv[1] == "install":
                install()
            else:
                rollback()
            return 0
        except (OSError, RuntimeError, ValueError, KeyError, tarfile.TarError,
                subprocess.SubprocessError) as exc:
            progress(0, "Update fehlgeschlagen: " + str(exc), state="error")
            return 1


if __name__ == "__main__":
    sys.exit(main())
