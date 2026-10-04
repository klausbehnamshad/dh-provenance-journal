"""Ereignishülle und Digestberechnung.

Hülle und Digestformel sind aus ``src/ohpipe/journal.py`` (Commit 3cff6f6)
übernommen und bleiben erhalten: Der Digest läuft über
``(seq, at, kind, record_id, payload, prev)`` plus optionalem
``operation_intent_sha256``; ohne Schlüssel als SHA-256, mit Schlüssel als
HMAC-SHA-256 über dieselben kanonischen Bytes. Das Intent-Feld wird beim
Lesen und Hashprüfen unterstützt; eigene v0.1-Ereignisse benötigen es nicht.
"""

from __future__ import annotations

import hmac
import json
import re
from dataclasses import dataclass, field
from typing import Any

from .hashing import sha256_json

__all__ = ["ENVELOPE_FIELDS", "GENESIS", "Event"]

GENESIS = "0" * 64

#: Die Felder der Hülle. Sie stehen hier, damit ``to_json`` und ``from_json``
#: nicht zwei Listen pflegen, die auseinanderlaufen können.
#: Wert ist (Typ, optional).
ENVELOPE_FIELDS: dict[str, tuple[type, bool]] = {
    "seq": (int, False),
    "at": (str, False),
    "kind": (str, False),
    "record_id": (str, True),
    "payload": (dict, False),
    "prev": (str, False),
    "digest": (str, False),
}

_INTENT_RE = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True)
class Event:
    seq: int
    at: str
    kind: str
    record_id: str | None
    payload: dict[str, Any]
    prev: str
    operation_intent_sha256: str | None = None
    #: Hash über (seq, at, kind, record_id, payload, prev[, operation_intent_sha256])
    digest: str = field(default="")

    @staticmethod
    def compute_digest(
        seq: int,
        at: str,
        kind: str,
        record_id: str | None,
        payload: dict[str, Any],
        prev: str,
        key: bytes | None = None,
        operation_intent_sha256: str | None = None,
    ) -> str:
        body = {
            "seq": seq,
            "at": at,
            "kind": kind,
            "record_id": record_id,
            "payload": payload,
            "prev": prev,
        }
        if operation_intent_sha256 is not None:
            body["operation_intent_sha256"] = operation_intent_sha256
        if key is None:
            return sha256_json(body)
        blob = json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return hmac.new(key, blob.encode("utf-8"), "sha256").hexdigest()

    def to_json(self) -> dict[str, Any]:
        out = {name: getattr(self, name) for name in ENVELOPE_FIELDS}
        if self.operation_intent_sha256 is not None:
            out["operation_intent_sha256"] = self.operation_intent_sha256
        return out

    @classmethod
    def from_json(cls, raw: dict[str, Any]) -> Event:
        """Prüft Anwesenheit UND Typ jedes Feldes."""
        allowed = set(ENVELOPE_FIELDS) | {"operation_intent_sha256"}
        if set(raw) - allowed:
            raise ValueError(f"fremde Huellenfelder: {sorted(set(raw) - allowed)}")
        werte: dict[str, Any] = {}
        for name, (typ, optional) in ENVELOPE_FIELDS.items():
            if name not in raw:
                raise ValueError(f"Pflichtfeld {name!r} fehlt")
            v = raw[name]
            if optional and v is None:
                werte[name] = None
                continue
            # `bool` ist in Python eine `int`-Unterklasse: ohne diesen Zusatz
            # ginge `seq: true` als gültige Sequenznummer durch.
            if (isinstance(v, bool) and typ is int) or not isinstance(v, typ):
                raise ValueError(f"{name!r} ist {type(v).__name__}, erwartet {typ.__name__}")
            werte[name] = v
        operation_intent_sha256 = raw.get("operation_intent_sha256")
        if operation_intent_sha256 is not None and (
            not isinstance(operation_intent_sha256, str)
            or _INTENT_RE.fullmatch(operation_intent_sha256) is None
        ):
            raise ValueError("operation_intent_sha256 ist kein voller ASCII-Kleinhex-sha256")
        return cls(**werte, operation_intent_sha256=operation_intent_sha256)
