"""Korrekt verkettete ungültige Basisnutzlast / falsches Profil (Abnahme).

Die Bestände werden mit getrennter Berechnung (hashlib/json direkt, ohne die
Paketfunktionen) korrekt verkettet, tragen aber verletzte Basisverträge. Jeder
Schreibversuch wird abgewiesen; die Bytes bleiben unverändert. Zusätzlich:
Neue Nutzlasten scheitern vor jeder Sperre als Aufruferfehler.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

import provenance_journal as pj
from provenance_journal.errors import PayloadError, PayloadRejected, ProfileError

from .conftest import AT, H1, H2

GENESIS = "0" * 64
GOOD_INIT = {"profile": "research-basic-v1", "root": ".", "version": "v0.1"}


def _chain(path: Path, specs: list[tuple[str, str | None, dict]], key: bytes | None = None) -> None:
    prev = GENESIS
    with open(path, "w", encoding="utf-8") as fh:
        for seq, (kind, record_id, payload) in enumerate(specs, start=1):
            body = {
                "seq": seq,
                "at": "2026-10-03T12:00:00+00:00",
                "kind": kind,
                "record_id": record_id,
                "payload": payload,
                "prev": prev,
            }
            blob = json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
            digest = hashlib.sha256(blob.encode("utf-8")).hexdigest()
            assert key is None  # diese Datei prüft sha256-Bestände
            line = dict(body, digest=digest)
            fh.write(json.dumps(line, ensure_ascii=False, sort_keys=True) + "\n")
            prev = digest


def _attempts(path: Path) -> list:
    # Handverkettete Bestände haben keine Beistelldatei: explizite Moduswahl.
    return [
        lambda: pj.register_record(path, "rec-neu", integrity="sha256"),
        lambda: pj.ingest_source(
            path,
            "rec-01",
            sha256=H1,
            media_type="text/plain",
            filename="n.txt",
            num_bytes=1,
            integrity="sha256",
        ),
        lambda: pj.record_decision(
            path,
            "rec-01",
            artifact="a.txt",
            subject_sha256=H2,
            verdict="REJECT",
            reference="PI-9",
            actor="A. Nau",
            at=AT,
            integrity="sha256",
        ),
    ]


def _rejects_all(path: Path, exc: type) -> None:
    before = path.read_bytes()
    for attempt in _attempts(path):
        with pytest.raises(exc):
            attempt()
    assert path.read_bytes() == before


def test_wrong_profile_rejected(jpath: Path) -> None:
    _chain(
        jpath,
        [("workspace.initialised", None, {"profile": "fremd", "root": ".", "version": "v0.1"})],
    )
    _rejects_all(jpath, ProfileError)
    with pytest.raises(ProfileError):
        pj.init_journal(jpath)


def test_negative_bytes_rejected_with_seq_and_fields(jpath: Path) -> None:
    _chain(
        jpath,
        [
            ("workspace.initialised", None, dict(GOOD_INIT)),
            ("record.registered", "rec-01", {"record_id": "rec-01", "profile": "research-basic-v1"}),
            (
                "source.ingested",
                "rec-01",
                {
                    "record_id": "rec-01",
                    "sha256": H1,
                    "media_type": "text/plain",
                    "filename": "q.txt",
                    "bytes": -1,
                },
            ),
        ],
    )
    before = jpath.read_bytes()
    with pytest.raises(PayloadError) as info:
        pj.register_record(jpath, "rec-neu", integrity="sha256")
    assert info.value.seq == 3
    assert "bytes" in info.value.fields
    assert jpath.read_bytes() == before


def test_bool_is_not_an_int(jpath: Path) -> None:
    _chain(
        jpath,
        [
            ("workspace.initialised", None, dict(GOOD_INIT)),
            ("record.registered", "rec-01", {"record_id": "rec-01", "profile": "research-basic-v1"}),
            (
                "source.ingested",
                "rec-01",
                {
                    "record_id": "rec-01",
                    "sha256": H1,
                    "media_type": "text/plain",
                    "filename": "q.txt",
                    "bytes": True,
                },
            ),
        ],
    )
    _rejects_all(jpath, PayloadError)


@pytest.mark.parametrize(
    "payload",
    [
        {"artifact": "a.txt", "output_sha256": H2, "inputs": {}, "code_version": "v",
         "kind": "deterministic", "step": "s"},
        {"artifact": "a.txt", "output_sha256": H2, "inputs": {"r": "kein-hash"},
         "code_version": "v", "kind": "deterministic", "step": "s"},
        {"artifact": "a.txt", "output_sha256": H2, "inputs": {"r": H1},
         "code_version": "v", "kind": "deterministic", "step": "s", "params": ["kein", "objekt"]},
    ],
    ids=["leere-inputs", "kein-hash", "params-kein-objekt"],
)
def test_invalid_receipt_stock_rejected(jpath: Path, payload: dict) -> None:
    _chain(
        jpath,
        [
            ("workspace.initialised", None, dict(GOOD_INIT)),
            ("record.registered", "rec-01", {"record_id": "rec-01", "profile": "research-basic-v1"}),
            ("receipt.recorded", "rec-01", payload),
        ],
    )
    _rejects_all(jpath, PayloadError)


def test_unknown_verdict_stock_rejected(jpath: Path) -> None:
    _chain(
        jpath,
        [
            ("workspace.initialised", None, dict(GOOD_INIT)),
            ("record.registered", "rec-01", {"record_id": "rec-01", "profile": "research-basic-v1"}),
            (
                "decision.recorded",
                "rec-01",
                {
                    "artifact": "a.txt",
                    "subject_sha256": H2,
                    "verdict": "VIELLEICHT",
                    "reference": "PI-1",
                    "actor": "A. Nau",
                    "at": AT,
                },
            ),
        ],
    )
    _rejects_all(jpath, PayloadError)


def test_unregistered_record_reference_rejected(jpath: Path) -> None:
    _chain(
        jpath,
        [
            ("workspace.initialised", None, dict(GOOD_INIT)),
            (
                "source.ingested",
                "rec-fremd",
                {
                    "record_id": "rec-fremd",
                    "sha256": H1,
                    "media_type": "text/plain",
                    "filename": "q.txt",
                    "bytes": 1,
                },
            ),
        ],
    )
    _rejects_all(jpath, ProfileError)


def test_conflicting_init_repeat_rejected(jpath: Path) -> None:
    pj.init_journal(jpath)
    before = jpath.read_bytes()
    # Gleicher Bestand, widersprechende Wiederholung ist über die API nicht
    # ausdrückbar (Profil/Root/Version sind fest) — der Pfad bleibt über
    # handverkettete Bestände mit falschem Profil abgedeckt (oben).
    again = pj.init_journal(jpath)
    assert not again.appended
    assert jpath.read_bytes() == before


@pytest.mark.parametrize(
    "kwargs",
    [
        {"num_bytes": -1},
        {"num_bytes": True},
        {"filename": "../ausbruch.txt"},
        {"filename": ""},
        {"sha256": "kein-hash"},
        {"media_type": ""},
    ],
)
def test_new_source_payload_rejected_before_lock(jpath: Path, kwargs: dict) -> None:
    pj.init_journal(jpath)
    pj.register_record(jpath, "rec-01")
    before = jpath.read_bytes()
    base: dict[str, Any] = {
        "sha256": H1,
        "media_type": "text/plain",
        "filename": "q.txt",
        "num_bytes": 1,
    }
    base.update(kwargs)
    with pytest.raises(PayloadRejected):
        pj.ingest_source(jpath, "rec-01", **base)  # type: ignore[arg-type]
    assert jpath.read_bytes() == before


@pytest.mark.parametrize(
    "kwargs",
    [
        {"verdict": "VIELLEICHT"},
        {"verdict": "UNDO"},
        {"reference": "mit leerzeichen"},
        {"reference": "x"},
        {"actor": "   "},
        {"at": "2026-10-02T10:00:00"},
        {"subject_sha256": "kurz"},
        {"note": 42},
    ],
)
def test_new_decision_payload_rejected(jpath: Path, kwargs: dict) -> None:
    pj.init_journal(jpath)
    pj.register_record(jpath, "rec-01")
    base: dict[str, Any] = {
        "artifact": "a.txt",
        "subject_sha256": H2,
        "verdict": "ACCEPT",
        "reference": "PI-1",
        "actor": "A. Nau",
        "at": AT,
    }
    base.update(kwargs)
    with pytest.raises(PayloadRejected):
        pj.record_decision(jpath, "rec-01", **base)  # type: ignore[arg-type]


def test_reserved_surface_fields_rejected() -> None:
    # Reservierte Namen gelten auf der obersten Nutzlastebene (Roadmap):
    # validate_new weist sie ab, statt sie still zu verwerfen.
    from provenance_journal.profile import validate_new

    for name in ("name", "text", "value", "original", "quote", "context", "replacement", "surface"):
        payload = {
            "artifact": "a.txt",
            "output_sha256": H2,
            "inputs": {"r": H1},
            "code_version": "v",
            "kind": "deterministic",
            "step": "s",
            name: "Oberfläche",
        }
        with pytest.raises(PayloadRejected) as info:
            validate_new("receipt.recorded", payload, "rec-01")
        assert name in info.value.fields


def test_model_receipt_kind_not_writable(jpath: Path) -> None:
    pj.init_journal(jpath)
    pj.register_record(jpath, "rec-01")
    with pytest.raises(PayloadRejected):
        pj.record_receipt(
            jpath,
            "rec-01",
            artifact="a.txt",
            output_sha256=H2,
            inputs={"r": H1},
            code_version="v",
            step="s",
            kind="model",
        )


def test_write_to_uninitialised_journal_rejected(jpath: Path) -> None:
    with pytest.raises(ProfileError):
        pj.register_record(jpath, "rec-01", integrity="sha256")
