"""Feste Digestvektoren (Abnahme: Referenzdigests stimmen).

Die Erwartungswerte stehen fest in tests/fixtures/digest_vectors.json und
stammen aus einer getrennten Referenzberechnung (hashlib/hmac/json direkt,
nicht die zu prüfende Funktion). Jeder Vektor hält Eingaben, zu hashende
Bytes und erwarteten Digest fest; die Bytes lassen sich zusätzlich mit
`printf '%s' "$blob" | sha256sum` nachrechnen.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path

import pytest

from provenance_journal.envelope import Event

FIXTURE = Path(__file__).parent / "fixtures" / "digest_vectors.json"


def _vectors() -> list[dict]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["vectors"]


@pytest.mark.parametrize("vector", _vectors(), ids=[v["id"] for v in _vectors()])
def test_vector_matches_reference(vector: dict) -> None:
    blob_bytes = vector["blob"].encode(vector["blob_encoding"])
    if vector["mode"] == "sha256":
        assert hashlib.sha256(blob_bytes).hexdigest() == vector["expected_digest"]
        key = None
    else:
        key_hex = vector["inputs"]["key_hex"]
        assert key_hex, "hmac-Vektor ohne Schlüssel"
        assert (
            hmac.new(bytes.fromhex(key_hex), blob_bytes, "sha256").hexdigest()
            == vector["expected_digest"]
        )
        key = bytes.fromhex(key_hex)
    inputs = vector["inputs"]
    got = Event.compute_digest(
        inputs["seq"],
        inputs["at"],
        inputs["kind"],
        inputs["record_id"],
        inputs["payload"],
        inputs["prev"],
        key,
        inputs["operation_intent_sha256"],
    )
    assert got == vector["expected_digest"]


def test_missing_and_null_intent_share_digest() -> None:
    by_id = {v["id"]: v for v in _vectors()}
    assert (
        by_id["sha256-intent-missing"]["expected_digest"]
        == by_id["sha256-intent-null"]["expected_digest"]
    )
    assert (
        by_id["sha256-intent-set"]["expected_digest"]
        != by_id["sha256-intent-null"]["expected_digest"]
    )


def test_wire_form_distinguishes_missing_from_null() -> None:
    event = Event(
        seq=1,
        at="2026-10-03T12:00:00+00:00",
        kind="record.registered",
        record_id="rec-42",
        payload={"record_id": "rec-42", "profile": "research-basic-v1"},
        prev="0" * 64,
        operation_intent_sha256=None,
        digest="x",
    )
    assert "operation_intent_sha256" not in event.to_json()


def test_package_roundtrip_preserves_set_intent(tmp_path: Path) -> None:
    import provenance_journal as pj

    path = tmp_path / "journal.jsonl"
    pj.init_journal(path)
    pj.register_record(path, "rec-42")
    res = pj.ingest_source(
        path,
        "rec-42",
        sha256="a" * 64,
        media_type="text/plain",
        filename="q.txt",
        num_bytes=1,
        operation_intent_sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    )
    assert res.event.operation_intent_sha256 is not None
    reread = pj.read_events(path)
    assert reread[-1].operation_intent_sha256 == res.event.operation_intent_sha256
    assert reread[-1].digest == res.event.digest
