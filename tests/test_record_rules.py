"""Record- und Registrierungsregeln für den vorhandenen Basisbestand (F2).

Unterstützte Basisereignisse erfüllen beim Lesen/Bewerten dieselben
Hüllenregeln wie beim Erzeugen. Bestände sind korrekt verkettet aus
unabhängiger Digestberechnung (hashlib/json direkt, ohne Paketfunktionen).
Alle sechs Schreibwege lehnen solche Bestände ohne Byteänderung ab;
`check_journal` weist lokal ungültige Basisereignisse nicht als `valid` aus.

Grenze: `assess` bewertet das einzelne Ereignis; `check_stock_writable`
prüft global (genau ein Workspace, genau eine Registrierung je Record,
Benutzung erst nach Registrierung). Ein lokal gültiges zweites
Workspace-/Record-Ereignis bleibt lesbar, macht den Bestand aber nicht
schreibbar.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

import provenance_journal as pj
from provenance_journal.errors import PayloadError, ProfileError

from .conftest import AT, H1, H2

GENESIS = "0" * 64
GOOD_INIT = {"profile": "research-basic-v1", "root": ".", "version": "v0.1"}
GOOD_REGISTER = {"record_id": "rec-01", "profile": "research-basic-v1"}


def _forge(path: Path, specs: list[tuple[str, Any, dict]]) -> None:
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
            prev = hashlib.sha256(blob.encode("utf-8")).hexdigest()
            fh.write(json.dumps({**body, "digest": prev}, ensure_ascii=False, sort_keys=True) + "\n")


def _all_writes(path: Path) -> list:
    return [
        lambda: pj.init_journal(path),
        lambda: pj.register_record(path, "rec-neu", integrity="sha256"),
        lambda: pj.ingest_source(
            path, "rec-01", sha256=H1, media_type="text/plain", filename="n.txt",
            num_bytes=1, integrity="sha256",
        ),
        lambda: pj.produce_artifact(path, "rec-01", artifact="a.txt", sha256=H1,
                                    integrity="sha256"),
        lambda: pj.record_receipt(
            path, "rec-01", artifact="a.txt", output_sha256=H1, inputs={"r": H1},
            code_version="v", step="s", integrity="sha256",
        ),
        lambda: pj.record_decision(
            path, "rec-01", artifact="a.txt", subject_sha256=H1, verdict="ACCEPT",
            reference="PI-1", actor="A. Nau", at=AT, integrity="sha256",
        ),
    ]


def _rejects_all(path: Path, exc: type) -> None:
    before = path.read_bytes()
    for attempt in _all_writes(path):
        with pytest.raises(exc):
            attempt()
    assert path.read_bytes() == before


def _receipt_payload() -> dict:
    return {
        "artifact": "a.txt", "output_sha256": H1, "inputs": {"r": H1},
        "code_version": "v", "kind": "deterministic", "step": "s",
    }


def _decision_payload() -> dict:
    return {
        "artifact": "a.txt", "subject_sha256": H1, "verdict": "ACCEPT",
        "reference": "PI-1", "actor": "A. Nau", "at": AT,
    }


@pytest.mark.parametrize("hollow", [None, ""])
@pytest.mark.parametrize(
    "kind,payload",
    [
        ("record.registered", GOOD_REGISTER),
        ("source.ingested", {"record_id": "rec-01", "sha256": H1, "media_type": "t",
                             "filename": "q.txt", "bytes": 1}),
        ("artifact.produced", {"artifact": "a.txt", "sha256": H1}),
        ("receipt.recorded", _receipt_payload()),
        ("decision.recorded", _decision_payload()),
    ],
    ids=["register", "source", "artifact", "receipt", "decision"],
)
def test_null_and_empty_envelope_rejected(jpath: Path, hollow: Any, kind: str, payload: dict) -> None:
    _forge(jpath, [("workspace.initialised", None, dict(GOOD_INIT)), (kind, hollow, payload)])
    report = pj.check_journal(jpath, integrity="sha256")
    assert report.chain_ok
    assert report.events[1].outcome == "invalid"
    assert "record_id" in report.events[1].fields
    _rejects_all(jpath, PayloadError)


@pytest.mark.parametrize("hollow", ["rec-01", ""])
def test_workspace_with_envelope_rejected(jpath: Path, hollow: Any) -> None:
    # Hüllen-Record null ist hier die einzige gültige Form (anderswo belegt).
    _forge(jpath, [("workspace.initialised", hollow, dict(GOOD_INIT))])
    report = pj.check_journal(jpath, integrity="sha256")
    assert report.chain_ok
    assert report.events[0].outcome == "invalid"
    assert "record_id" in report.events[0].fields
    # Ungültiger Kettenanfang verletzt das Workspace-Profil.
    _rejects_all(jpath, ProfileError)


def test_envelope_payload_mismatch_rejected(jpath: Path) -> None:
    _forge(
        jpath,
        [
            ("workspace.initialised", None, dict(GOOD_INIT)),
            ("record.registered", "rec-01", dict(GOOD_REGISTER)),
            (
                "source.ingested", "rec-01",
                {"record_id": "rec-02", "sha256": H1, "media_type": "t",
                 "filename": "q.txt", "bytes": 1},
            ),
        ],
    )
    report = pj.check_journal(jpath, integrity="sha256")
    assert report.events[2].outcome == "invalid"
    assert "record_id" in report.events[2].fields
    _rejects_all(jpath, PayloadError)


def test_use_before_registration_rejected(jpath: Path) -> None:
    _forge(
        jpath,
        [
            ("workspace.initialised", None, dict(GOOD_INIT)),
            ("artifact.produced", "rec-spaet", {"artifact": "a.txt", "sha256": H1}),
            ("record.registered", "rec-spaet",
             {"record_id": "rec-spaet", "profile": "research-basic-v1"}),
        ],
    )
    _rejects_all(jpath, ProfileError)


def test_second_workspace_readable_but_not_writable(jpath: Path) -> None:
    _forge(
        jpath,
        [
            ("workspace.initialised", None, dict(GOOD_INIT)),
            ("record.registered", "rec-01", dict(GOOD_REGISTER)),
            ("workspace.initialised", None, dict(GOOD_INIT)),
        ],
    )
    report = pj.check_journal(jpath, integrity="sha256")
    assert report.chain_ok
    # Lokal vertragskonform, global nicht schreibbar: Grenze dokumentiert.
    assert [e.outcome for e in report.events] == ["valid", "valid", "valid"]
    _rejects_all(jpath, ProfileError)


def test_duplicate_registration_readable_but_not_writable(jpath: Path) -> None:
    _forge(
        jpath,
        [
            ("workspace.initialised", None, dict(GOOD_INIT)),
            ("record.registered", "rec-01", dict(GOOD_REGISTER)),
            ("record.registered", "rec-01", dict(GOOD_REGISTER)),
        ],
    )
    report = pj.check_journal(jpath, integrity="sha256")
    assert [e.outcome for e in report.events] == ["valid", "valid", "valid"]
    _rejects_all(jpath, ProfileError)
