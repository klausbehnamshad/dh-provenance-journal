"""Sichere Lesehilfen für Eingabe-, Parameter- und Schlüsseldateien.

Quellen, Ergebnisse und Parameterdateien werden weder verändert noch
kopiert oder archiviert. Hash und Größe beziehen sich auf dieselben am
geöffneten Handle gelesenen Rohbytes, ohne Textnormalisierung. FIFO,
Verzeichnis, Symlink oder unlesbarer Endpunkt werden abgewiesen, ohne zu
hängen und ohne als normale Datei zu gelten: Öffnen mit
``O_NOFOLLOW | O_NONBLOCK``, danach ``S_ISREG``-Prüfung am geöffneten
Deskriptor.
"""

from __future__ import annotations

import errno
import hashlib
import json
import os
import stat as statmodul
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import FileReadError, PayloadRejected

__all__ = [
    "FileData",
    "read_file_bytes",
    "read_json_object",
    "read_key_bytes",
    "read_regular_bytes",
]

#: Fehlerdomäne für Dateiöffnungen — symbolisch, nie gegen Zahlen.
_UNSAFE_FILE_ERRNO = frozenset({errno.ELOOP, errno.EMLINK, errno.ENOTDIR, errno.ENXIO})


@dataclass(frozen=True)
class FileData:
    """Vermessung einer Eingabedatei: voller Hash, Größe, Basename."""

    sha256: str
    size: int
    name: str


def _open_regular(pfad: Path) -> int:
    """Öffnet eine reguläre Datei. Folgt keinem Link, blockiert nie."""
    p = Path(pfad)
    try:
        fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError as exc:
        raise FileReadError(p, "Datei nicht gefunden") from exc
    except OSError as exc:
        if exc.errno in _UNSAFE_FILE_ERRNO:
            raise FileReadError(
                p, "keine reguläre Datei (Link, Verzeichnis oder Spezialdatei)"
            ) from exc
        raise FileReadError(p, "Datei nicht lesbar") from exc
    try:
        if not statmodul.S_ISREG(os.fstat(fd).st_mode):
            raise FileReadError(p, "keine reguläre Datei (Verzeichnis oder Spezialdatei)")
    except BaseException:
        os.close(fd)
        raise
    return fd


def _read_all(fd: int, pfad: Path) -> bytes:
    """Liest den Deskriptor vollständig. I/O-Fehler bleiben I/O-Fehler."""
    chunks: list[bytes] = []
    while True:
        try:
            block = os.read(fd, 65536)
        except OSError as exc:
            raise FileReadError(pfad, "Lesefehler") from exc
        if not block:
            return b"".join(chunks)
        chunks.append(block)


def read_file_bytes(pfad: Path | str) -> FileData:
    """Vermisst eine Eingabedatei am geöffneten Handle (Hash, Größe, Name)."""
    p = Path(pfad)
    fd = _open_regular(p)
    try:
        digest = hashlib.sha256()
        size = 0
        while True:
            try:
                block = os.read(fd, 65536)
            except OSError as exc:
                raise FileReadError(p, "Lesefehler") from exc
            if not block:
                break
            digest.update(block)
            size += len(block)
    finally:
        os.close(fd)
    return FileData(sha256=digest.hexdigest(), size=size, name=p.name)


def read_json_object(pfad: Path | str) -> dict[str, Any]:
    """Liest eine JSON-Objektdatei (z. B. `--params-file`).

    Ungültiges JSON sowie `null`, Listen und Skalare werden vor jedem
    Anhang abgewiesen; Lesefehler bleiben I/O-Fehler.
    """
    p = Path(pfad)
    fd = _open_regular(p)
    try:
        raw = _read_all(fd, p)
    finally:
        os.close(fd)
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise PayloadRejected("params", detail="Parameterdatei ist kein gültiges JSON") from exc
    if not isinstance(data, dict):
        raise PayloadRejected("params", detail="Parameterdatei muss ein JSON-Objekt enthalten")
    return data


def read_key_bytes(pfad: Path) -> bytes:
    """Liest eine Schlüsseldatei, ohne zu folgen und ohne zu blockieren."""
    p = Path(pfad)
    fd = _open_regular(p)
    try:
        return _read_all(fd, p)
    finally:
        os.close(fd)


def read_regular_bytes(pfad: Path | str) -> bytes:
    """Liest eine kleine Beistelldatei (Moduskonfiguration) roh ein.

    Dieselben Schutzregeln wie für Eingabedateien: kein Folgen, kein
    Blockieren, nur reguläre Dateien. Die Deutung (fehlt → None,
    unbrauchbar → Konfigurationsfehler) bleibt beim Aufrufer.
    """
    p = Path(pfad)
    fd = _open_regular(p)
    try:
        return _read_all(fd, p)
    finally:
        os.close(fd)
