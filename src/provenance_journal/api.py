"""Öffentliche Python-Schreibschnittstelle (klein, dokumentiert).

Einstiegspunkte (CLI ``provjournal`` und Historie):

* Schreiben: ``init_journal``, ``register_record``, ``ingest_source``,
  ``produce_artifact``, ``record_receipt``, ``record_decision``.
  Jede Funktion prüft unter derselben exklusiven Sperre den bestehenden
  Bestand (Sequenz, Verkettung, Digest, Basisprofil, vorhandene
  Basisnutzlasten) und hängt erst danach an. Rückgabe ist ``WriteResult``
  mit dem Ereignis und ``appended`` (False = bereits registriert, kein
  neuer Eintrag). Alle Rückgaben sind Kopien.
* Lesen/Prüfen: ``read_events`` (verifizierte Kette), ``verify_journal``
  (wirft beim ersten Bruch), ``check_journal`` (Bericht mit getrennter
  Ketten- und Fachprüfung für Altbestand).

Es gibt keinen offen verwendbaren Schreibweg an dieser Prüfung vorbei;
``_store`` ist privat.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import config as _config
from . import profile as _profile
from ._store import Journal
from .envelope import Event
from .errors import ConfigError, PayloadRejected, ProfileError

__all__ = [
    "CheckReport",
    "EventAssessment",
    "WriteResult",
    "check_journal",
    "ingest_source",
    "init_journal",
    "produce_artifact",
    "read_events",
    "record_decision",
    "record_receipt",
    "register_record",
    "verify_journal",
]


@dataclass(frozen=True)
class WriteResult:
    """Ergebnis eines Schreibaufrufs. Kopie — kein lebendiger Bestand."""

    event: Event
    appended: bool  # False: bereits registriert, nichts angehängt


@dataclass(frozen=True)
class EventAssessment:
    seq: int
    kind: str
    outcome: str  # "valid" | "invalid" | "unchecked"
    fields: tuple[str, ...] = ()
    detail: str = ""


@dataclass(frozen=True)
class CheckReport:
    """Getrennte Ketten- und Fachprüfung (lesender Altbestand)."""

    chain_ok: bool
    chain_error: str | None = None
    events: tuple[EventAssessment, ...] = ()


def _open(path: Path | str, integrity: str | None, key: Any) -> Journal:
    journal_path = Path(path)
    mode = _config.resolve_integrity(journal_path, integrity)
    resolved_key = _config.resolve_key(mode, journal_path, key)
    return Journal(journal_path, resolved_key)


def _check_intent(operation_intent_sha256: str | None) -> None:
    if operation_intent_sha256 is None:
        return
    if not isinstance(operation_intent_sha256, str) or _profile.SHA256_RE.fullmatch(
        operation_intent_sha256
    ) is None:
        raise PayloadRejected(
            "operation_intent_sha256", detail="kein voller ASCII-Kleinhex-sha256"
        )


def _stable(payload: dict[str, Any]) -> dict[str, Any]:
    """Eigene tiefe Kopie der Aufrufdaten — vor jeder Prüfung.

    Validierung, Digest und gespeicherte Nutzlast verwenden dieselben
    stabilen Daten: Verändert der Aufrufer seine Wörterbücher (etwa
    ``inputs`` oder verschachtelte ``params``), während der Anhang auf die
    Sperre wartet, gilt der Aufrufzustand — niemals ein ungültiger oder
    digestinkonsistenter Eintrag.
    """
    return copy.deepcopy(payload)


def init_journal(
    path: Path | str,
    *,
    integrity: str = "sha256",
    key: Any = None,
    operation_intent_sha256: str | None = None,
) -> WriteResult:
    """Legt das Journal an (Profil research-basic-v1, root ".").

    Nur die Initialisierung darf mit einem leeren Journal beginnen. Eine
    identische Wiederholung ergibt bereits registriert; eine widersprechende
    wird abgewiesen. Der Modus wird in der Beistelldatei festgehalten.
    """
    journal_path = Path(path)
    if integrity not in (_config.SHA256, _config.HMAC):
        raise ConfigError(f"Unbekannter Integritätsmodus {integrity!r}")
    resolved_key = _config.resolve_key(integrity, journal_path, key)
    configured = _config.read_config(journal_path)
    if configured is not None and configured != integrity:
        raise ConfigError(
            f"Modusangabe {integrity!r} widerspricht der Konfiguration ({configured!r}); "
            "kein automatischer Moduswechsel, kein Fallback"
        )
    payload = _stable(
        {
            "profile": _profile.PROFILE,
            "root": _profile.WORKSPACE_ROOT,
            "version": _profile.PROFILE_VERSION,
        }
    )
    _check_intent(operation_intent_sha256)
    _profile.validate_new(_profile.WORKSPACE_INITIALISED, payload, None)
    journal = Journal(journal_path, resolved_key)
    # Erst die Transaktion (Sperre + Prüfung + ggf. Anhang): Ein fehlendes
    # Elternverzeichnis ist hier JournalUnsafe, und es entsteht nichts.
    # Die Beistelldatei folgt danach; schlägt sie fehl, stellt eine
    # idempotente Wiederholung sie wieder her.
    with journal.transaction() as tx:
        snapshot = tx.snapshot
        if not snapshot:
            event = tx.append(
                _profile.WORKSPACE_INITIALISED,
                payload,
                record_id=None,
                operation_intent_sha256=operation_intent_sha256,
            )
            appended = True
        else:
            _profile.check_stock_writable(snapshot)
            first = snapshot[0]
            if first.payload != payload:
                raise ProfileError(
                    "widersprechende workspace.initialised-Wiederholung abgewiesen"
                )
            event = copy.deepcopy(first)
            appended = False
    _config.write_config(journal_path, integrity)
    return WriteResult(event, appended)


def register_record(
    path: Path | str,
    record_id: str,
    *,
    integrity: str | None = None,
    key: Any = None,
    operation_intent_sha256: str | None = None,
) -> WriteResult:
    """Registriert einen Record einmalig. Wiederholung ergibt bereits registriert."""
    payload = _stable({"record_id": record_id, "profile": _profile.PROFILE})
    _check_intent(operation_intent_sha256)
    _profile.validate_new(_profile.RECORD_REGISTERED, payload, record_id)
    journal = _open(path, integrity, key)
    with journal.transaction() as tx:
        snapshot = tx.snapshot
        records = _profile.check_stock_writable(snapshot)
        if record_id in records:
            for event in snapshot:
                if event.kind == _profile.RECORD_REGISTERED and event.record_id == record_id:
                    return WriteResult(copy.deepcopy(event), False)
            raise ProfileError(f"Record {record_id!r}: inkonsistenter Bestand")
        event = tx.append(
            _profile.RECORD_REGISTERED,
            payload,
            record_id=record_id,
            operation_intent_sha256=operation_intent_sha256,
        )
        return WriteResult(event, True)


def ingest_source(
    path: Path | str,
    record_id: str,
    *,
    sha256: str,
    media_type: str,
    filename: str,
    num_bytes: int,
    integrity: str | None = None,
    key: Any = None,
    operation_intent_sha256: str | None = None,
) -> WriteResult:
    """Registriert eine Quelle. Gleicher Record und gleicher Hash ergibt
    bereits registriert (Dateiname entscheidet nicht)."""
    payload = _stable(
        {
            "record_id": record_id,
            "sha256": sha256,
            "media_type": media_type,
            "filename": filename,
            "bytes": num_bytes,
        }
    )
    _check_intent(operation_intent_sha256)
    _profile.validate_new(_profile.SOURCE_INGESTED, payload, record_id)
    journal = _open(path, integrity, key)
    with journal.transaction() as tx:
        snapshot = tx.snapshot
        records = _profile.check_stock_writable(snapshot)
        if record_id not in records:
            raise ProfileError(f"Record {record_id!r} ist nicht registriert")
        for event in snapshot:
            if (
                event.kind == _profile.SOURCE_INGESTED
                and event.record_id == record_id
                and event.payload.get("sha256") == sha256
            ):
                return WriteResult(copy.deepcopy(event), False)
        event = tx.append(
            _profile.SOURCE_INGESTED,
            payload,
            record_id=record_id,
            operation_intent_sha256=operation_intent_sha256,
        )
        return WriteResult(event, True)


def produce_artifact(
    path: Path | str,
    record_id: str,
    *,
    artifact: str,
    sha256: str,
    integrity: str | None = None,
    key: Any = None,
    operation_intent_sha256: str | None = None,
) -> WriteResult:
    """Registriert eine Ergebnisfassung. Gleicher Record, Artefaktname und
    Hash ergibt bereits registriert; anderer Hash bleibt neue Fassung —
    frühere Fassungen bleiben erhalten."""
    payload = _stable({"artifact": artifact, "sha256": sha256})
    _check_intent(operation_intent_sha256)
    _profile.validate_new(_profile.ARTIFACT_PRODUCED, payload, record_id)
    journal = _open(path, integrity, key)
    with journal.transaction() as tx:
        snapshot = tx.snapshot
        records = _profile.check_stock_writable(snapshot)
        if record_id not in records:
            raise ProfileError(f"Record {record_id!r} ist nicht registriert")
        for event in snapshot:
            if (
                event.kind == _profile.ARTIFACT_PRODUCED
                and event.record_id == record_id
                and event.payload.get("artifact") == artifact
                and event.payload.get("sha256") == sha256
            ):
                return WriteResult(copy.deepcopy(event), False)
        event = tx.append(
            _profile.ARTIFACT_PRODUCED,
            payload,
            record_id=record_id,
            operation_intent_sha256=operation_intent_sha256,
        )
        return WriteResult(event, True)


def record_receipt(
    path: Path | str,
    record_id: str,
    *,
    artifact: str,
    output_sha256: str,
    inputs: dict[str, str],
    code_version: str,
    step: str,
    kind: str = "deterministic",
    params: dict[str, Any] | None = None,
    integrity: str | None = None,
    key: Any = None,
    operation_intent_sha256: str | None = None,
) -> WriteResult:
    """Hängt einen Laufbeleg an. Laufbelege sind eigenständige Akte und werden
    regulär angehängt — eine gleiche Ausgabe allein macht sie nicht zu
    Duplikaten. Es werden nur die ausdrücklich erlaubten Felder gemappt
    (kein ``created_at``/``input_fingerprint`` aus Fachobjekten)."""
    payload: dict[str, Any] = {
        "artifact": artifact,
        "output_sha256": output_sha256,
        "inputs": inputs,
        "code_version": code_version,
        "kind": kind,
        "step": step,
    }
    if params is not None:
        payload["params"] = params
    payload = _stable(payload)
    _check_intent(operation_intent_sha256)
    _profile.validate_new(_profile.RECEIPT_RECORDED, payload, record_id)
    journal = _open(path, integrity, key)
    with journal.transaction() as tx:
        snapshot = tx.snapshot
        records = _profile.check_stock_writable(snapshot)
        if record_id not in records:
            raise ProfileError(f"Record {record_id!r} ist nicht registriert")
        event = tx.append(
            _profile.RECEIPT_RECORDED,
            payload,
            record_id=record_id,
            operation_intent_sha256=operation_intent_sha256,
        )
        return WriteResult(event, True)


def record_decision(
    path: Path | str,
    record_id: str,
    *,
    artifact: str,
    subject_sha256: str,
    verdict: str,
    reference: str,
    actor: str,
    at: str,
    note: str | None = None,
    integrity: str | None = None,
    key: Any = None,
    operation_intent_sha256: str | None = None,
) -> WriteResult:
    """Hängt eine Entscheidung an (ACCEPT/REJECT/WITHDRAW). Entscheidungen sind
    eigenständige Akte: Weitere Entscheidungen bleiben erhalten, auch zur
    selben Fassung. Es werden nur die ausdrücklich erlaubten Felder gemappt
    (kein ``id``/``reason_code`` aus Fachobjekten)."""
    payload: dict[str, Any] = {
        "artifact": artifact,
        "subject_sha256": subject_sha256,
        "verdict": verdict,
        "reference": reference,
        "actor": actor,
        "at": at,
    }
    if note is not None:
        payload["note"] = note
    payload = _stable(payload)
    _check_intent(operation_intent_sha256)
    _profile.validate_new(_profile.DECISION_RECORDED, payload, record_id)
    journal = _open(path, integrity, key)
    with journal.transaction() as tx:
        snapshot = tx.snapshot
        records = _profile.check_stock_writable(snapshot)
        if record_id not in records:
            raise ProfileError(f"Record {record_id!r} ist nicht registriert")
        event = tx.append(
            _profile.DECISION_RECORDED,
            payload,
            record_id=record_id,
            operation_intent_sha256=operation_intent_sha256,
        )
        return WriteResult(event, True)


def read_events(
    path: Path | str, *, integrity: str | None = None, key: Any = None
) -> list[Event]:
    """Liest den Bestand und prüft die Kette (Seq, prev, Digest).

    Keine Profilprüfung: Bestehende OHPIPE-Journale ohne Konfiguration werden
    mit expliziter Moduswahl gelesen; Spezialereignisse bleiben erhalten.
    Rückgabe sind Kopien.
    """
    journal = _open(path, integrity, key)
    return journal.verify()


def verify_journal(
    path: Path | str, *, integrity: str | None = None, key: Any = None
) -> list[Event]:
    """Prüft die Kette und wirft beim ersten Bruch. Gibt den geprüften
    Snapshot zurück — Auswertung benutzt dieselben geprüften Daten."""
    return read_events(path, integrity=integrity, key=key)


def check_journal(
    path: Path | str, *, integrity: str | None = None, key: Any = None
) -> CheckReport:
    """Bericht mit getrennter Ketten- und Fachprüfung.

    Kettenprüfung (Seq, prev, Digest) zuerst; scheitert sie, entfällt die
    Fachprüfung. Besteht sie, wird jede Basisnutzlast als gültig/ungültig
    (mit Feldnamen) oder als fachlich nicht geprüft (Spezialvariante)
    ausgewiesen. Die Journalbytes bleiben unverändert.
    """
    journal = _open(path, integrity, key)
    try:
        raw = list(journal)
    except Exception as exc:
        return CheckReport(chain_ok=False, chain_error=str(exc))
    try:
        snapshot = journal.verify(raw)
    except Exception as exc:
        return CheckReport(chain_ok=False, chain_error=str(exc))
    assessed = []
    for event in snapshot:
        result = _profile.assess(event)
        assessed.append(
            EventAssessment(
                seq=event.seq,
                kind=event.kind,
                outcome=result.outcome,
                fields=tuple(result.fields),
                detail=result.detail,
            )
        )
    return CheckReport(chain_ok=True, events=tuple(assessed))
