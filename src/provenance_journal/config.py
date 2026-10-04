"""Integritätsmodus und Schlüsselverwaltung.

Der gewählte Modus (``sha256`` oder ``hmac``) steht in einer lokalen
Konfiguration außerhalb der Ereignisbytes: einer Beistelldatei neben dem
Journal. Bei der Anlage ist ``sha256`` der dokumentierte Standard; ``hmac``
wird ausdrücklich gewählt.

Für bestehende Journale ohne Konfiguration verlangt die lesende API eine
explizite Moduswahl. Es gibt kein Ausprobieren verschiedener Modi und keinen
automatischen HMAC-Fallback.

``PROVJOURNAL_KEY`` bezeichnet den Pfad einer Schlüsseldatei, niemals den
Schlüsseltext. Der Schlüssel bleibt außerhalb der Datenwurzel; Mindestlänge
(16 Bytes) und Lageprüfung sind aus dem Ausgangsvertrag übernommen. Eine
vorhandene ``OHPIPE_JOURNAL_KEY``-Variable beeinflusst dieses Paket nicht —
sie wird nie gelesen.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from .errors import ConfigError, FileReadError
from .files import read_key_bytes, read_regular_bytes

__all__ = [
    "ENV_KEY",
    "HMAC",
    "SHA256",
    "config_path",
    "load_key_bytes",
    "read_config",
    "resolve_integrity",
    "resolve_key",
    "write_config",
]

#: Pfad auf eine Schlüsseldatei — niemals der Schlüsseltext.
ENV_KEY = "PROVJOURNAL_KEY"

#: Die alte OHPIPE-Variable wird bewusst NICHT gelesen.
LEGACY_ENV_KEY = "OHPIPE_JOURNAL_KEY"

SHA256 = "sha256"
HMAC = "hmac"

MIN_KEY_BYTES = 16


def config_path(journal_path: Path) -> Path:
    """Beistelldatei neben dem Journal, außerhalb der Ereignisbytes."""
    return Path(str(journal_path) + ".config.json")


def write_config(journal_path: Path, integrity: str) -> None:
    """Legt die Moduskonfiguration an. Bei Widerspruch zum vorhandenen Stand:
    ConfigError. Kein stilles Umschreiben."""
    if integrity not in (SHA256, HMAC):
        raise ConfigError(f"Unbekannter Integritätsmodus {integrity!r} (erwartet 'sha256'/'hmac')")
    target = config_path(journal_path)
    if target.exists():
        present = read_config(journal_path)
        if present != integrity:
            raise ConfigError(
                "Integritätsmodus widerspricht der vorhandenen Konfiguration "
                f"(vorhanden: {present!r}, verlangt: {integrity!r}); "
                "kein automatischer Moduswechsel"
            )
        return
    try:
        with open(target, "x", encoding="utf-8") as fh:
            json.dump({"integrity": integrity}, fh, sort_keys=True)
            fh.write("\n")
    except FileExistsError as exc:
        present = read_config(journal_path)
        if present != integrity:
            raise ConfigError(
                "Integritätsmodus widerspricht der vorhandenen Konfiguration "
                f"(vorhanden: {present!r}, verlangt: {integrity!r}); "
                "kein automatischer Moduswechsel"
            ) from exc
    except OSError as exc:
        raise ConfigError(f"Moduskonfiguration nicht schreibbar: {exc}") from exc


def read_config(journal_path: Path) -> str | None:
    """Liest die Moduskonfiguration. Keine Datei → None (kein Raten).

    Die Beistelldatei wird mit denselben sicheren Lesehilfen geöffnet wie
    Eingabedateien: ohne zu folgen (``O_NOFOLLOW``), ohne zu blockieren
    (``O_NONBLOCK``) und nur als reguläre Datei (``S_ISREG`` am geöffneten
    Deskriptor). FIFO, Verzeichnis, Link und unlesbare Konfiguration sind
    Konfigurationsfehler — ohne Hänger. Fehlende Datei bleibt der
    vorhandene Fall „explizite Moduswahl nötig“.
    """
    target = config_path(journal_path)
    try:
        raw = read_regular_bytes(target)
    except FileReadError as exc:
        if exc.grund == "Datei nicht gefunden":
            return None
        raise ConfigError(f"Moduskonfiguration nicht lesbar: {exc.grund}") from exc
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ConfigError(f"Moduskonfiguration unbrauchbar: {exc}") from exc
    mode = data.get("integrity") if isinstance(data, dict) else None
    if mode not in (SHA256, HMAC):
        raise ConfigError(
            "Moduskonfiguration unbrauchbar (erwartet {'integrity': 'sha256'/'hmac'})"
        )
    return mode


def resolve_integrity(journal_path: Path, integrity: str | None) -> str:
    """Bestimmt den geltenden Modus: Konfiguration schlägt nichts, sie gilt.

    Explizite Angabe und vorhandene Konfiguration müssen übereinstimmen.
    Ohne beides gibt es keinen Modus — und damit kein Ausprobieren.
    """
    if integrity is not None and integrity not in (SHA256, HMAC):
        raise ConfigError(f"Unbekannter Integritätsmodus {integrity!r} (erwartet 'sha256'/'hmac')")
    configured = read_config(journal_path)
    if configured is not None and integrity is not None and configured != integrity:
        raise ConfigError(
            f"Modusangabe {integrity!r} widerspricht der Konfiguration ({configured!r}); "
            "kein automatischer Moduswechsel, kein Fallback"
        )
    if configured is not None:
        return configured
    if integrity is not None:
        return integrity
    raise ConfigError(
        "Keine Moduskonfiguration vorhanden; explizite Moduswahl erforderlich "
        "(integrity='sha256' oder integrity='hmac')"
    )


def load_key_bytes(data_root: Path, explicit: bytes | Path | str | None = None) -> bytes:
    """Lädt den HMAC-Schlüssel aus einer Datei außerhalb der Datenwurzel."""
    raw: Path | None = None
    if explicit is not None:
        if isinstance(explicit, (bytes, bytearray)):
            data = bytes(explicit)
            if len(data) < MIN_KEY_BYTES:
                raise ConfigError("Journalschlüssel ist zu kurz (mindestens 16 Bytes).")
            return data
        raw = Path(explicit)
    else:
        env = os.environ.get(ENV_KEY)
        if not env:
            raise ConfigError(
                "HMAC gewählt, aber kein Schlüssel konfiguriert "
                f"({ENV_KEY} nicht gesetzt); Journal nicht verifiziert"
            )
        raw = Path(env)
    p = raw.expanduser()
    try:
        resolved = p.resolve()
    except OSError as exc:
        raise ConfigError(f"Journalschlüssel nicht lesbar: {exc}") from exc
    root = data_root.resolve()
    if resolved == root or root in resolved.parents:
        raise ConfigError(
            f"Der Journalschlüssel liegt in der Datenwurzel ({resolved}). Damit schützt er "
            "nichts: Wer die Journaldatei schreiben darf, hätte auch ihn."
        )
    try:
        data = read_key_bytes(resolved)
    except Exception as exc:
        raise ConfigError(
            "HMAC gewählt, aber Schlüssel fehlt oder ist nicht lesbar "
            f"({exc}); Journal nicht verifiziert"
        ) from exc
    if len(data) < MIN_KEY_BYTES:
        raise ConfigError("Journalschlüssel ist zu kurz (mindestens 16 Bytes).")
    return data


def resolve_key(
    integrity: str,
    journal_path: Path,
    key: bytes | Path | str | None = None,
) -> bytes | None:
    """Schlüssel zum Modus: sha256 braucht keinen, hmac verlangt einen."""
    if integrity == SHA256:
        return None
    return load_key_bytes(journal_path.parent, explicit=key)
