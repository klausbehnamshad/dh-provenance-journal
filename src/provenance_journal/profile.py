"""Schreibbares Basisprofil research-basic-v1.

Isoliert aus dem Public-Vertrag (Commit 3cff6f6), aber bewusst KEIN blinder
Port: Die vollständige ``Decision``-Klasse hängt an ``manual_context`` und
Spezialregeln, ``Receipt`` liefert Fachobjekte ohne Nutzlastvalidierung.
Übernommen sind deshalb nur die ausdrücklich erlaubten Feldsätze und die
Basisregeln:

* ``events.check_payload`` → Feldsatz- und Hüllenregeln (Allowlist statt
  Filter, Klartextverdacht, Hüllen-/Nutzlast-Record-Gleichheit);
* ``decision`` → ``SHA256_RE``, ``REFERENCE_RE``, zeitzonenbehaftete Zeit,
  nichtleere Bezeichner (nur ACCEPT/REJECT/WITHDRAW; UNDO bleibt Lesefall);
* ``receipt`` → Rollen-zu-Hash-Zuordnung der Eingaben, nichtleere Schritt-
  und Versionsangabe, gültiger Ausgabehash, ``params`` als JSON-Objekt.

Die Objektserialisierungen ``Receipt.to_json()`` (``created_at``,
``input_fingerprint``) und ``Decision.to_json()`` (``id``, ``reason_code``)
sind NICHT der Ereignisvertrag: Es werden nur die erlaubten Felder gemappt.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .envelope import Event
from .errors import PayloadError, PayloadRejected, ProfileError

__all__ = [
    "ACCEPTING_VERDICTS",
    "PROFILE",
    "PROFILE_VERSION",
    "RESERVED_TOP_LEVEL",
    "SUPPORTED_KINDS",
    "Assessment",
    "WORKSPACE_INITIALISED",
    "RECORD_REGISTERED",
    "SOURCE_INGESTED",
    "ARTIFACT_PRODUCED",
    "RECEIPT_RECORDED",
    "DECISION_RECORDED",
    "WORKSPACE_ROOT",
    "assess",
    "check_stock_writable",
    "validate_new",
]

PROFILE = "research-basic-v1"
WORKSPACE_ROOT = "."
PROFILE_VERSION = "v0.1"

WORKSPACE_INITIALISED = "workspace.initialised"
RECORD_REGISTERED = "record.registered"
SOURCE_INGESTED = "source.ingested"
ARTIFACT_PRODUCED = "artifact.produced"
RECEIPT_RECORDED = "receipt.recorded"
DECISION_RECORDED = "decision.recorded"

SUPPORTED_KINDS = frozenset(
    {
        WORKSPACE_INITIALISED,
        RECORD_REGISTERED,
        SOURCE_INGESTED,
        ARTIFACT_PRODUCED,
        RECEIPT_RECORDED,
        DECISION_RECORDED,
    }
)

#: Reservierte Namen auf der obersten Nutzlastebene. Sie tragen typischerweise
#: eine Oberflächenform; das Journal ist append-only — eine Klartextspur darin
#: wäre dauerhaft. Übernommen aus der Roadmap.
RESERVED_TOP_LEVEL = frozenset(
    {"name", "text", "value", "original", "quote", "context", "replacement", "surface"}
)

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
#: Ein Token ohne Whitespace (3–64 Zeichen).
REFERENCE_RE = re.compile(r"^[\w.:@/+-]{3,64}$")

#: Eigene v0.1-Entscheidungen unterstützen ACCEPT, REJECT und WITHDRAW.
#: UNDO und spezialisierte Verträge bleiben Lesefälle.
ACCEPTING_VERDICTS = frozenset({"ACCEPT", "REJECT", "WITHDRAW"})
READ_ONLY_VERDICTS = frozenset({"UNDO"})

DETERMINISTIC_KIND = "deterministic"


def parse_aware_iso(value: str) -> datetime | None:
    """Ein Zeitpunkt zählt nur mit Zeitzone."""
    try:
        dt = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    return dt if dt.tzinfo is not None else None


def _is_full_sha256(value: Any) -> bool:
    return isinstance(value, str) and SHA256_RE.fullmatch(value) is not None


def _is_nonempty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _check_inputs(value: Any) -> str | None:
    """Prüft die Rollen-zu-Hash-Zuordnung. Gibt None zurück oder den Fehlergrund."""
    if not isinstance(value, dict) or not value:
        return "inputs ist kein nichtleeres Objekt"
    for rolle, digest in value.items():
        if not _is_nonempty_str(rolle):
            return "inputs enthält eine leere Rolle"
        if not _is_full_sha256(digest):
            return "inputs enthält keinen vollen sha256"
    return None


def _check_params(value: Any) -> str | None:
    """``params`` ist bei Verwendung ein JSON-Objekt.

    Ein fehlendes Feld ist erlaubt; ein vorhandenes Feld — einschließlich
    ``null`` — muss ein Objekt sein. ``record_receipt(..., params=None)``
    schreibt das Feld gar nicht erst.
    """
    if not isinstance(value, dict):
        return "params ist kein JSON-Objekt"
    try:
        json.dumps(value, sort_keys=True, ensure_ascii=False)
    except (TypeError, ValueError):
        return "params ist nicht JSON-serialisierbar"
    return None


def _check_filename(value: Any) -> str | None:
    if not _is_nonempty_str(value):
        return "filename ist leer"
    assert isinstance(value, str)
    if value in (".", "..") or "/" in value or "\\" in value or value != Path(value).name:
        return "filename ist kein Basename"
    return None


@dataclass(frozen=True)
class Assessment:
    """Bewertung eines Bestandsereignisses gegen das Basisprofil."""

    outcome: str  # "valid" | "invalid" | "unchecked"
    fields: tuple[str, ...] = ()
    detail: str = ""


def _field_rules(kind: str, payload: dict[str, Any]) -> Assessment | None:
    """Feldregeln je Ereignisart. None = keine Beanstandung der Felder."""
    get = payload.get
    if kind == WORKSPACE_INITIALISED:
        bad = []
        if get("profile") != PROFILE:
            bad.append("profile")
        if get("root") != WORKSPACE_ROOT:
            bad.append("root")
        if get("version") != PROFILE_VERSION:
            bad.append("version")
        if bad:
            return Assessment("invalid", tuple(bad), "falsches Profil")
        return None
    if kind == RECORD_REGISTERED:
        bad = []
        if not _is_nonempty_str(get("record_id")):
            bad.append("record_id")
        if get("profile") != PROFILE:
            bad.append("profile")
        if bad:
            return Assessment("invalid", tuple(bad), "Registrierung unvollständig")
        return None
    if kind == SOURCE_INGESTED:
        bad = []
        if not _is_nonempty_str(get("record_id")):
            bad.append("record_id")
        if not _is_full_sha256(get("sha256")):
            bad.append("sha256")
        if not _is_nonempty_str(get("media_type")):
            bad.append("media_type")
        filename_problem = _check_filename(get("filename"))
        if filename_problem:
            bad.append("filename")
        nbytes = get("bytes")
        if type(nbytes) is not int or nbytes < 0:
            bad.append("bytes")
        if bad:
            return Assessment("invalid", tuple(bad), "Quellenangabe unvollständig")
        return None
    if kind == ARTIFACT_PRODUCED:
        bad = []
        if not _is_nonempty_str(get("artifact")):
            bad.append("artifact")
        if not _is_full_sha256(get("sha256")):
            bad.append("sha256")
        if bad:
            return Assessment("invalid", tuple(bad), "Ergebnisangabe unvollständig")
        return None
    if kind == RECEIPT_RECORDED:
        if get("kind") != DETERMINISTIC_KIND:
            return Assessment("unchecked", ("kind",), "kein deterministischer Laufbeleg")
        bad = []
        if not _is_nonempty_str(get("artifact")):
            bad.append("artifact")
        if not _is_full_sha256(get("output_sha256")):
            bad.append("output_sha256")
        inputs_problem = _check_inputs(get("inputs"))
        if inputs_problem:
            bad.append("inputs")
        if not _is_nonempty_str(get("code_version")):
            bad.append("code_version")
        if not _is_nonempty_str(get("step")):
            bad.append("step")
        if "params" in payload:
            params_problem = _check_params(payload["params"])
            if params_problem:
                bad.append("params")
        if bad:
            return Assessment("invalid", tuple(bad), "Laufbeleg unvollständig")
        return None
    if kind == DECISION_RECORDED:
        verdict = get("verdict")
        # Typ vor Mitgliedschaft: `[] in frozenset(...)` würfe TypeError.
        if isinstance(verdict, str) and verdict in READ_ONLY_VERDICTS:
            return Assessment("unchecked", ("verdict",), "UNDO bleibt Lesefall")
        bad = []
        if not _is_nonempty_str(get("artifact")):
            bad.append("artifact")
        if not _is_full_sha256(get("subject_sha256")):
            bad.append("subject_sha256")
        if not isinstance(verdict, str) or verdict not in ACCEPTING_VERDICTS:
            bad.append("verdict")
        reference = get("reference")
        if not isinstance(reference, str) or REFERENCE_RE.fullmatch(reference) is None:
            bad.append("reference")
        if not _is_nonempty_str(get("actor")):
            bad.append("actor")
        if not isinstance(get("at"), str) or parse_aware_iso(get("at")) is None:
            bad.append("at")
        note = get("note")
        if note is not None and not isinstance(note, str):
            bad.append("note")
        if bad:
            return Assessment("invalid", tuple(bad), "Entscheidung unvollständig")
        return None
    raise AssertionError(f"nicht unterstützte Art: {kind}")


_REQUIRED: dict[str, frozenset[str]] = {
    WORKSPACE_INITIALISED: frozenset({"profile", "root", "version"}),
    RECORD_REGISTERED: frozenset({"record_id", "profile"}),
    SOURCE_INGESTED: frozenset({"record_id", "sha256", "media_type", "filename", "bytes"}),
    ARTIFACT_PRODUCED: frozenset({"artifact", "sha256"}),
    RECEIPT_RECORDED: frozenset(
        {"artifact", "output_sha256", "inputs", "code_version", "kind", "step"}
    ),
    DECISION_RECORDED: frozenset(
        {"artifact", "subject_sha256", "verdict", "reference", "actor", "at"}
    ),
}

_OPTIONAL: dict[str, frozenset[str]] = {
    WORKSPACE_INITIALISED: frozenset(),
    RECORD_REGISTERED: frozenset(),
    SOURCE_INGESTED: frozenset(),
    ARTIFACT_PRODUCED: frozenset(),
    RECEIPT_RECORDED: frozenset({"params"}),
    DECISION_RECORDED: frozenset({"note"}),
}


def assess(event: Event) -> Assessment:
    """Bewertet ein Bestandsereignis: Kette ist hier bereits geprüft.

    * ``valid`` — unterstützte Basisnutzlast, vertragskonform.
    * ``invalid`` — unterstützte Art, aber Feldvertrag verletzt (mit
      Ereignisnummer und Feldnamen, ausgewiesen über ``PayloadError``).
    * ``unchecked`` — fachliche Spezialvariante oder unbekannte Art: Kette
      prüfbar, Fachsemantik nicht geprüft. Ausschließlich lesbar.
    """
    if event.kind not in SUPPORTED_KINDS:
        return Assessment("unchecked", (), f"unbekannte Ereignisart {event.kind!r}")
    payload = event.payload
    if not isinstance(payload, dict):
        return Assessment("invalid", (), "Nutzlast ist kein Objekt")
    suspect = sorted(set(payload) & RESERVED_TOP_LEVEL)
    if suspect:
        return Assessment("invalid", tuple(suspect), "reservierte Oberflächenfelder")
    # Dieselben Hüllenregeln wie beim Erzeugen: Nur workspace.initialised
    # trägt Hüllen-Record null; alle anderen Basisarten brauchen eine
    # nichtleere Hüllen-Record-ID (null und "" sind ungültig).
    if event.kind == WORKSPACE_INITIALISED:
        if event.record_id is not None:
            return Assessment("invalid", ("record_id",), "Hüllen-Record muss null sein")
    elif not _is_nonempty_str(event.record_id):
        return Assessment("invalid", ("record_id",), "Record-Ereignis ohne Hüllen-Record")
    # Variantenvorprüfung vor der Pflichtfeldprüfung: Ein fremder Beleg ohne
    # kind-Angabe (OHPIPE: optional) oder ein UNDO ist keine defekte Basis-
    # nutzlast, sondern eine fachlich nicht geprüfte Variante.
    if event.kind == RECEIPT_RECORDED and payload.get("kind") != DETERMINISTIC_KIND:
        return Assessment("unchecked", ("kind",), "kein deterministischer Laufbeleg")
    verdict = payload.get("verdict")
    if (
        event.kind == DECISION_RECORDED
        and isinstance(verdict, str)
        and verdict in READ_ONLY_VERDICTS
    ):
        return Assessment("unchecked", ("verdict",), "UNDO bleibt Lesefall")
    required = _REQUIRED[event.kind]
    allowed = required | _OPTIONAL[event.kind]
    missing = sorted(required - set(payload))
    if missing:
        return Assessment("invalid", tuple(missing), "Pflichtfelder fehlen")
    extra = set(payload) - allowed
    # Zusatzfelder deuten auf eine fremde oder spezialisierte Variante
    # (OHPIPE-Optionen wie note/cues, B3b-/P4-Fachverträge): lesbar, aber
    # fachlich nicht geprüft — kein Schreibbestand. Neue Nutzlasten mit
    # Zusatzfeldern werden dagegen strikt abgewiesen (validate_new).
    if extra:
        return Assessment("unchecked", tuple(sorted(extra)), "spezialisierte Variante")
    result = _field_rules(event.kind, payload)
    if result is not None:
        return result
    # Hülle bestimmt die Record-Zuordnung; wo die Nutzlast record_id trägt,
    # muss sie exakt übereinstimmen — ohne Ausnahme für null.
    if "record_id" in payload and payload["record_id"] != event.record_id:
        return Assessment("invalid", ("record_id",), "Hülle und Nutzlast widersprechen sich")
    return Assessment("valid")


def validate_new(kind: str, payload: dict[str, Any], record_id: str | None) -> None:
    """Prüft eine NEUE Nutzlast vor dem Schreiben. Wirft ``PayloadRejected``.

    Meldungen nennen Feldnamen, niemals abgelehnte Werte. Es wird nichts
    stillschweigend verworfen: Ein unbekanntes Feld ist ein Aufruferfehler.
    """
    if kind not in SUPPORTED_KINDS:
        raise PayloadRejected(kind, detail=f"unbekannte Ereignisart {kind!r}")
    if not isinstance(payload, dict):
        raise PayloadRejected(kind, detail="Nutzlast ist kein Objekt")
    suspect = sorted(set(payload) & RESERVED_TOP_LEVEL)
    if suspect:
        raise PayloadRejected(
            suspect, detail="reservierte Oberflächenfelder stehen in keiner Nutzlast"
        )
    required = _REQUIRED[kind]
    allowed = required | _OPTIONAL[kind]
    extra = sorted(set(payload) - allowed)
    if extra:
        raise PayloadRejected(extra, detail="nicht erlaubte Felder werden nicht verworfen")
    missing = sorted(required - set(payload))
    if missing:
        raise PayloadRejected(missing, detail="Pflichtfelder fehlen")
    if kind == WORKSPACE_INITIALISED:
        if record_id is not None:
            raise PayloadRejected("record_id", detail="gehört nicht zu dieser Ereignisart")
    elif not _is_nonempty_str(record_id):
        raise PayloadRejected("record_id", detail="Record-Ereignis ohne Record")
    try:
        json.dumps(payload, sort_keys=True, ensure_ascii=False)
    except (TypeError, ValueError):
        raise PayloadRejected(kind, detail="Nutzlast ist nicht JSON-serialisierbar") from None
    if (
        kind == DECISION_RECORDED
        and isinstance(payload.get("verdict"), str)
        and payload.get("verdict") in READ_ONLY_VERDICTS
    ):
        raise PayloadRejected("verdict", detail="UNDO bleibt Lesefall und wird nicht geschrieben")
    probe = Event(
        seq=0,
        at="",
        kind=kind,
        record_id=record_id,
        payload=payload,
        prev="",
        digest="",
    )
    result = assess(probe)
    if result.outcome != "valid":
        raise PayloadRejected(
            list(result.fields) or kind,
            detail=result.detail or "Feldvertrag verletzt",
        )


def check_stock_writable(snapshot: list[Event]) -> set[str]:
    """Gesamtprüfung der Schreibbarkeit unter der Schreibsperre.

    Über die Einzelpayload-Bewertung (``assess``) hinaus gelten global:
    genau ein Workspace am Anfang, jeder Record genau einmal registriert
    und vor seiner ersten Benutzung. Gibt die Menge der registrierten
    Records zurück. Spezialereignisse und unbekannte Arten machen den
    Bestand ausschließlich lesbar; ungültige Basisnutzlasten werden mit
    Ereignisnummer und Feldnamen ausgewiesen.
    """
    if not snapshot:
        raise ProfileError("leeres Journal; Initialisierung erforderlich")
    first = snapshot[0]
    if first.kind != WORKSPACE_INITIALISED or first.record_id is not None:
        raise ProfileError("kein gültiger workspace.initialised-Eintrag am Kettenanfang")
    result = assess(first)
    if result.outcome != "valid":
        raise ProfileError(f"falsches Profil im Bestand: {result.detail}")
    records: set[str] = set()
    workspaces = 0
    for event in snapshot:
        outcome = assess(event)
        if outcome.outcome == "invalid":
            raise PayloadError(event.seq, list(outcome.fields), outcome.detail)
        if outcome.outcome == "unchecked":
            raise ProfileError(
                f"fachlicher Altbestand bei seq={event.seq} "
                f"({event.kind}): ausschließlich lesbar"
            )
        # Ab hier ist der Bestand lokal Basis-vertragskonform: Hüllen-Record
        # null nur am Workspace, sonst nichtleer; Nutzlast-Record gleich Hülle.
        if event.kind == WORKSPACE_INITIALISED:
            workspaces += 1
            if workspaces > 1:
                raise ProfileError(
                    f"zweiter workspace.initialised-Eintrag bei seq={event.seq}; "
                    "im schreibbaren Basisbestand steht genau ein Workspace am Anfang"
                )
        elif event.kind == RECORD_REGISTERED:
            rid = event.payload["record_id"]
            if rid in records:
                raise ProfileError(
                    f"Record {rid!r} mehrfach registriert (seq={event.seq}); "
                    "jeder Record wird genau einmal registriert"
                )
            records.add(rid)
        elif event.record_id not in records:
            raise ProfileError(
                f"seq={event.seq} benutzt Record {event.record_id!r} vor dessen "
                "Registrierung (Record-Konsistenz verletzt)"
            )
    return records
