"""Robuste Typ- und Feldprüfung (F4-Regression).

`verdict` wird erst als String geprüft, dann mit den erlaubten Werten
verglichen (kein roher TypeError). Ein fehlendes `params` ist erlaubt, ein
vorhandenes muss ein Objekt sein (`null`/Liste/Skalar ungültig).
Referenzen werden vollständig gegen die Tokenregel geprüft (kein Whitespace,
kein LF). ACCEPT/REJECT/WITHDRAW und der lesende UNDO-Fall bleiben.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

import provenance_journal as pj
from provenance_journal.errors import PayloadError, PayloadRejected

from .conftest import AT, H1, H2

GENESIS = "0" * 64


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


def _base_decision(**overrides) -> dict:
    payload = {
        "artifact": "a.txt",
        "subject_sha256": H2,
        "verdict": "ACCEPT",
        "reference": "PI-1",
        "actor": "A. Nau",
        "at": AT,
    }
    payload.update(overrides)
    return payload


@pytest.mark.parametrize("verdict", [[], {}, 42, None])
def test_new_verdict_wrong_type_rejected(jpath: Path, verdict: Any) -> None:
    pj.init_journal(jpath)
    pj.register_record(jpath, "rec-01")
    before = jpath.read_bytes()
    with pytest.raises(PayloadRejected) as info:
        pj.record_decision(jpath, "rec-01", **_base_decision(verdict=verdict))
    assert "verdict" in info.value.fields
    assert jpath.read_bytes() == before


@pytest.mark.parametrize("verdict", [[], {}])
def test_stock_verdict_wrong_type_diagnosed(jpath: Path, verdict: Any) -> None:
    _forge(
        jpath,
        [
            ("workspace.initialised", None,
             {"profile": "research-basic-v1", "root": ".", "version": "v0.1"}),
            ("record.registered", "rec-01",
             {"record_id": "rec-01", "profile": "research-basic-v1"}),
            ("decision.recorded", "rec-01", _base_decision(verdict=verdict)),
        ],
    )
    report = pj.check_journal(jpath, integrity="sha256")
    assert report.chain_ok
    assert report.events[2].outcome == "invalid"
    assert "verdict" in report.events[2].fields
    before = jpath.read_bytes()
    with pytest.raises(PayloadError) as info:
        pj.register_record(jpath, "rec-neu", integrity="sha256")
    assert info.value.seq == 3
    assert "verdict" in info.value.fields
    assert jpath.read_bytes() == before


@pytest.mark.parametrize("params", [None, [], "x", 42])
def test_stock_params_present_must_be_object(jpath: Path, params: Any) -> None:
    receipt = {
        "artifact": "a.txt", "output_sha256": H1, "inputs": {"r": H1},
        "code_version": "v", "kind": "deterministic", "step": "s", "params": params,
    }
    _forge(
        jpath,
        [
            ("workspace.initialised", None,
             {"profile": "research-basic-v1", "root": ".", "version": "v0.1"}),
            ("record.registered", "rec-01",
             {"record_id": "rec-01", "profile": "research-basic-v1"}),
            ("receipt.recorded", "rec-01", receipt),
        ],
    )
    report = pj.check_journal(jpath, integrity="sha256")
    assert report.events[2].outcome == "invalid"
    assert "params" in report.events[2].fields
    with pytest.raises(PayloadError):
        pj.register_record(jpath, "rec-neu", integrity="sha256")


def test_missing_params_allowed_and_none_omits_field(jpath: Path) -> None:
    pj.init_journal(jpath)
    pj.register_record(jpath, "rec-01")
    res = pj.record_receipt(
        jpath, "rec-01", artifact="a.txt", output_sha256=H1, inputs={"r": H1},
        code_version="v", step="s",
    )
    assert "params" not in res.event.payload
    res2 = pj.record_receipt(
        jpath, "rec-01", artifact="a.txt", output_sha256=H1, inputs={"r": H1},
        code_version="v", step="s", params=None,
    )
    assert "params" not in res2.event.payload
    assert all(e.outcome == "valid" for e in pj.check_journal(jpath).events)


@pytest.mark.parametrize(
    "reference", ["PI-1\n", " PI-1", "PI-1 ", "PI 1", "PI-1\nPI-2", "A\tB", ""]
)
def test_reference_whitespace_rejected(jpath: Path, reference: str) -> None:
    pj.init_journal(jpath)
    pj.register_record(jpath, "rec-01")
    before = jpath.read_bytes()
    with pytest.raises(PayloadRejected) as info:
        pj.record_decision(jpath, "rec-01", **_base_decision(reference=reference))
    assert "reference" in info.value.fields
    assert jpath.read_bytes() == before


def test_stock_reference_with_newline_invalid(jpath: Path) -> None:
    _forge(
        jpath,
        [
            ("workspace.initialised", None,
             {"profile": "research-basic-v1", "root": ".", "version": "v0.1"}),
            ("record.registered", "rec-01",
             {"record_id": "rec-01", "profile": "research-basic-v1"}),
            ("decision.recorded", "rec-01", _base_decision(reference="PI-1\n")),
        ],
    )
    report = pj.check_journal(jpath, integrity="sha256")
    assert report.events[2].outcome == "invalid"
    assert "reference" in report.events[2].fields
    with pytest.raises(PayloadError):
        pj.register_record(jpath, "rec-neu", integrity="sha256")


@pytest.mark.parametrize("verdict", ["ACCEPT", "REJECT", "WITHDRAW"])
def test_supported_verdicts_still_work(jpath: Path, verdict: str) -> None:
    pj.init_journal(jpath)
    pj.register_record(jpath, "rec-01")
    res = pj.record_decision(jpath, "rec-01", **_base_decision(verdict=verdict))
    assert res.appended
    assert pj.check_journal(jpath).events[-1].outcome == "valid"
