"""Kleine Tests für die reine Historien-/Zuordnungsauswertung.

Prüfen Fassungsbindung nach voller Identität, letzte Entscheidung nach
`seq` (nicht Zeitstempel), keine Entscheidungsübertragung über Record-,
Artefakt- oder Fassungsgrenzen sowie Auswertung aus dem geprüften Snapshot
(DATEIÄNDERUNG NACH DEM EINLESEN ÄNDERT DIE AUSWERTUNG NICHT).
"""

from __future__ import annotations

from pathlib import Path

import provenance_journal as pj
from provenance_journal import history as hist

from .conftest import AT, H1, H2, H3


def _flow(path: Path, **kw) -> None:
    pj.init_journal(path, **kw)
    pj.register_record(path, "rec-01", **kw)
    (path.parent / "q.txt").write_bytes(b"daten-01")
    pj.ingest_source(
        path, "rec-01", sha256=H1, media_type="text/plain", filename="q.txt",
        num_bytes=8, **kw,
    )
    pj.produce_artifact(path, "rec-01", artifact="a.txt", sha256=H2, **kw)


def test_revision_receipt_decision_bound_by_full_identity(jpath: Path) -> None:
    _flow(jpath)
    pj.record_receipt(
        jpath, "rec-01", artifact="a.txt", output_sha256=H2, inputs={"q": H1},
        code_version="v1", step="s", **{},
    )
    pj.record_decision(
        jpath, "rec-01", artifact="a.txt", subject_sha256=H2, verdict="ACCEPT",
        reference="PI-1", actor="A. Nau", at=AT,
    )
    snapshot = hist.load_snapshot(jpath, "sha256")
    built = hist.build_history(snapshot)
    assert len(built.records) == 1
    view = built.records[0].artifacts[0]
    assert view.current is not None and view.current.sha256 == H2
    assert [r.seq for r in view.current.receipts] == [5]
    assert view.current.latest_decision is not None
    assert view.current.latest_decision.verdict == "ACCEPT"
    assert built.findings == ()


def test_second_revision_keeps_old_bindings(jpath: Path) -> None:
    _flow(jpath)
    pj.record_receipt(
        jpath, "rec-01", artifact="a.txt", output_sha256=H2, inputs={"q": H1},
        code_version="v1", step="s",
    )
    pj.record_decision(
        jpath, "rec-01", artifact="a.txt", subject_sha256=H2, verdict="ACCEPT",
        reference="PI-1", actor="A. Nau", at=AT,
    )
    pj.produce_artifact(jpath, "rec-01", artifact="a.txt", sha256=H3)
    pj.record_decision(
        jpath, "rec-01", artifact="a.txt", subject_sha256=H3, verdict="REJECT",
        reference="PI-2", actor="A. Nau", at=AT,
    )
    built = hist.build_history(hist.load_snapshot(jpath, "sha256"))
    view = built.records[0].artifacts[0]
    assert [r.sha256 for r in view.revisions] == [H2, H3]
    assert view.current is not None and view.current.sha256 == H3
    assert view.current.latest_decision is not None
    assert view.current.latest_decision.verdict == "REJECT"
    old = view.revisions[0]
    assert old.latest_decision is not None and old.latest_decision.verdict == "ACCEPT"
    assert [r.seq for r in old.receipts] == [5]


def test_later_verdict_replaces_statement_not_history(jpath: Path) -> None:
    _flow(jpath)
    for verdict, ref in (("ACCEPT", "PI-1"), ("REJECT", "PI-2"), ("WITHDRAW", "PI-3")):
        pj.record_decision(
            jpath, "rec-01", artifact="a.txt", subject_sha256=H2, verdict=verdict,
            reference=ref, actor="A. Nau", at=AT,
        )
    built = hist.build_history(hist.load_snapshot(jpath, "sha256"))
    current = built.records[0].artifacts[0].current
    assert current is not None and current.latest_decision is not None
    assert current.latest_decision.verdict == "WITHDRAW"
    assert current.latest_decision.seq == 7


def test_no_decision_transfer_across_records_or_names(jpath: Path) -> None:
    _flow(jpath)
    pj.register_record(jpath, "rec-02")
    pj.produce_artifact(jpath, "rec-02", artifact="a.txt", sha256=H2)
    pj.produce_artifact(jpath, "rec-01", artifact="b.txt", sha256=H2)
    pj.record_decision(
        jpath, "rec-01", artifact="a.txt", subject_sha256=H2, verdict="ACCEPT",
        reference="PI-1", actor="A. Nau", at=AT,
    )
    snapshot = hist.load_snapshot(jpath, "sha256")
    other = hist.check_artifact(snapshot, record_id="rec-02", artifact="a.txt", sha256=H2)
    assert other.registered and other.latest_decision is None
    renamed = hist.check_artifact(snapshot, record_id="rec-01", artifact="b.txt", sha256=H2)
    assert renamed.registered and renamed.latest_decision is None
    unknown = hist.check_artifact(snapshot, record_id="rec-01", artifact="a.txt", sha256=H3)
    assert not unknown.registered and unknown.currency == "unregistered"


def test_historical_bytes_stay_checkable(jpath: Path) -> None:
    _flow(jpath)
    pj.record_receipt(
        jpath, "rec-01", artifact="a.txt", output_sha256=H2, inputs={"q": H1},
        code_version="v1", step="s",
    )
    pj.record_decision(
        jpath, "rec-01", artifact="a.txt", subject_sha256=H2, verdict="ACCEPT",
        reference="PI-1", actor="A. Nau", at=AT,
    )
    pj.produce_artifact(jpath, "rec-01", artifact="a.txt", sha256=H3)
    snapshot = hist.load_snapshot(jpath, "sha256")
    old = hist.check_artifact(snapshot, record_id="rec-01", artifact="a.txt", sha256=H2)
    assert old.registered and old.currency == "historical"
    assert old.revision_seq == 4
    assert [r.seq for r in old.receipts] == [5]
    assert old.latest_decision is not None and old.latest_decision.verdict == "ACCEPT"
    new = hist.check_artifact(snapshot, record_id="rec-01", artifact="a.txt", sha256=H3)
    assert new.registered and new.currency == "current"


def test_invalid_and_unchecked_stay_visible_without_binding(jpath: Path) -> None:
    import hashlib
    import json

    prev = "0" * 64
    lines = []
    specs = [
        ("workspace.initialised", None,
         {"profile": "research-basic-v1", "root": ".", "version": "v0.1"}),
        ("record.registered", "rec-01",
         {"record_id": "rec-01", "profile": "research-basic-v1"}),
        ("artifact.produced", None, {"artifact": "a.txt", "sha256": H2}),
        ("decision.recorded", "rec-01",
         {"artifact": "a.txt", "subject_sha256": H2, "verdict": "UNDO",
          "reference": "PI-0", "actor": "A. Nau", "at": AT}),
    ]
    with open(jpath, "w", encoding="utf-8") as fh:
        for seq, (kind, record_id, payload) in enumerate(specs, start=1):
            body = {"seq": seq, "at": AT, "kind": kind, "record_id": record_id,
                    "payload": payload, "prev": prev}
            blob = json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
            prev = hashlib.sha256(blob.encode()).hexdigest()
            fh.write(json.dumps({**body, "digest": prev}, sort_keys=True) + "\n")
    snapshot = hist.load_snapshot(jpath, "sha256")
    built = hist.build_history(snapshot)
    assert [f.outcome for f in built.findings] == ["invalid", "unchecked"]
    # Registrierter Record ohne Fassung bleibt als leere Ansicht sichtbar,
    # begründet aber keine Zuordnung.
    assert [r.record_id for r in built.records] == ["rec-01"]
    assert built.records[0].artifacts == ()
    checked = hist.check_artifact(snapshot, record_id="rec-01", artifact="a.txt", sha256=H2)
    assert not checked.registered


def test_evaluation_uses_verified_snapshot_only(jpath: Path) -> None:
    _flow(jpath)
    snapshot = hist.load_snapshot(jpath, "sha256")
    before = hist.build_history(snapshot)
    assert len(before.records[0].artifacts[0].revisions) == 1
    pj.produce_artifact(jpath, "rec-01", artifact="a.txt", sha256=H3)
    after_same_snapshot = hist.build_history(snapshot)
    assert len(after_same_snapshot.records[0].artifacts[0].revisions) == 1
    fresh = hist.build_history(hist.load_snapshot(jpath, "sha256"))
    assert len(fresh.records[0].artifacts[0].revisions) == 2


def test_filter_marks_derived_view(jpath: Path) -> None:
    _flow(jpath)
    pj.register_record(jpath, "rec-02")
    full = hist.build_history(hist.load_snapshot(jpath, "sha256"))
    assert not full.derived and full.filters == {}
    part = hist.filter_history(full, record_id="rec-02")
    assert part.derived and part.filters == {"record": "rec-02"}
    assert [r.record_id for r in part.records] == ["rec-02"]
    empty = hist.filter_history(full, record_id="rec-fremd")
    assert empty.records == () and empty.derived
