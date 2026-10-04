"""Normaler Append und Duplikatregeln (Abnahme).

Revisionen und weitere Entscheidungen bleiben erhalten; echte
Registrierungsduplikate werden erkannt (appended=False, kein neuer Eintrag).
Rückgaben sind Kopien: Nachträgliche Mutation verändert weder Bytes noch
spätere Leseergebnisse.
"""

from __future__ import annotations

from pathlib import Path

import provenance_journal as pj

from .conftest import AT, H1, H2


def test_workspace_and_record_registered_once(jpath: Path) -> None:
    first = pj.init_journal(jpath)
    assert first.appended and first.event.seq == 1
    again = pj.init_journal(jpath)
    assert not again.appended
    assert again.event.seq == 1
    assert again.event.digest == first.event.digest

    reg = pj.register_record(jpath, "rec-01")
    assert reg.appended
    dup = pj.register_record(jpath, "rec-01")
    assert not dup.appended
    assert dup.event.seq == reg.event.seq
    assert len(pj.read_events(jpath)) == 2


def test_source_duplicate_ignores_filename(jpath: Path) -> None:
    pj.init_journal(jpath)
    pj.register_record(jpath, "rec-01")
    first = pj.ingest_source(
        jpath, "rec-01", sha256=H1, media_type="text/plain", filename="a.txt", num_bytes=5
    )
    assert first.appended
    dup = pj.ingest_source(
        jpath, "rec-01", sha256=H1, media_type="text/plain", filename="b.txt", num_bytes=5
    )
    assert not dup.appended
    assert dup.event.seq == first.event.seq
    assert dup.event.payload["filename"] == "a.txt"
    other = pj.ingest_source(
        jpath, "rec-01", sha256=H2, media_type="text/plain", filename="a.txt", num_bytes=5
    )
    assert other.appended


def test_artifact_revisions_preserved(jpath: Path) -> None:
    pj.init_journal(jpath)
    pj.register_record(jpath, "rec-01")
    v1 = pj.produce_artifact(jpath, "rec-01", artifact="auswertung.txt", sha256=H1)
    assert v1.appended
    dup = pj.produce_artifact(jpath, "rec-01", artifact="auswertung.txt", sha256=H1)
    assert not dup.appended
    v2 = pj.produce_artifact(jpath, "rec-01", artifact="auswertung.txt", sha256=H2)
    assert v2.appended
    assert v2.event.seq == v1.event.seq + 1
    events = pj.read_events(jpath)
    revisions = [
        e for e in events if e.kind == "artifact.produced" and e.payload["artifact"] == "auswertung.txt"
    ]
    assert [e.payload["sha256"] for e in revisions] == [H1, H2]


def test_receipts_and_decisions_always_appended(jpath: Path) -> None:
    pj.init_journal(jpath)
    pj.register_record(jpath, "rec-01")
    pj.produce_artifact(jpath, "rec-01", artifact="a.txt", sha256=H1)
    kwargs = {
        "artifact": "a.txt",
        "output_sha256": H1,
        "inputs": {"quelle": H2},
        "code_version": "v0.1",
        "step": "ableitung",
    }
    r1 = pj.record_receipt(jpath, "rec-01", **kwargs)
    r2 = pj.record_receipt(jpath, "rec-01", **kwargs)
    assert r1.appended and r2.appended
    assert r2.event.seq == r1.event.seq + 1

    d1 = pj.record_decision(
        jpath, "rec-01", artifact="a.txt", subject_sha256=H1,
        verdict="ACCEPT", reference="PI-1", actor="A. Nau", at=AT,
    )
    d2 = pj.record_decision(
        jpath, "rec-01", artifact="a.txt", subject_sha256=H1,
        verdict="REJECT", reference="PI-2", actor="A. Nau", at=AT,
    )
    assert d1.appended and d2.appended
    events = pj.read_events(jpath)
    decisions = [e for e in events if e.kind == "decision.recorded"]
    assert [e.payload["verdict"] for e in decisions] == ["ACCEPT", "REJECT"]
    assert decisions[0].payload["subject_sha256"] == decisions[1].payload["subject_sha256"] == H1


def test_returned_events_are_copies(jpath: Path) -> None:
    pj.init_journal(jpath)
    reg = pj.register_record(jpath, "rec-01")
    before = jpath.read_bytes()
    reg.event.payload["record_id"] = "manipuliert"
    reg.event.payload["neu"] = "x"
    assert jpath.read_bytes() == before
    reread = pj.read_events(jpath)
    assert reread[1].payload == {"record_id": "rec-01", "profile": "research-basic-v1"}
    reread[1].payload["record_id"] = "manipuliert"
    assert pj.read_events(jpath)[1].payload["record_id"] == "rec-01"
