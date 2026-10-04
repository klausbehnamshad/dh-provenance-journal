"""R3: Alle erfassten Akte bleiben mit ihren Angaben einsehbar.

Ungebunden ist ein Beleg/eine Entscheidung, sobald seine vollständige
Record-/Artefakt-/Hash-Identität keine registrierte Fassung besitzt —
auch bei vorhandenem Artefaktnamen mit anderen Fassungen. Die
Ereignisliste zeigt jedes ursprüngliche Ereignis mit Details
(Quellenangaben, Receipt-Inputs/Params, jede Entscheidung mit Verdikt,
Referenz, Akteur, Zeitpunkt, Note); die kompakte Fassung daneben nur die
letzte Entscheidung.
"""

from __future__ import annotations

import json
from pathlib import Path

import provenance_journal as pj
from provenance_journal import history as hist

from .conftest import AT, H1, H2, H3
from .test_cli_e2e import run_cli


def _bestand(pfad: Path) -> None:
    pj.init_journal(pfad)
    pj.register_record(pfad, "r1")
    pj.ingest_source(
        pfad, "r1", sha256=H1, media_type="text/plain",
        filename="source-visible.txt", num_bytes=1,
    )
    pj.produce_artifact(pfad, "r1", artifact="a", sha256=H1)
    pj.record_receipt(
        pfad, "r1", artifact="a", output_sha256=H1, inputs={"quelle": H1},
        code_version="v1", step="s", params={"schwelle": 3},
    )
    pj.record_decision(
        pfad, "r1", artifact="a", subject_sha256=H1, verdict="ACCEPT",
        reference="PI-1", actor="First reviewer", at=AT, note="first decision note",
    )
    pj.record_decision(
        pfad, "r1", artifact="a", subject_sha256=H1, verdict="REJECT",
        reference="PI-2", actor="Second reviewer", at=AT,
    )
    pj.produce_artifact(pfad, "r1", artifact="a", sha256=H2)
    # Beleg und Entscheidung zu H3: gültig, aber ohne registrierte Fassung
    # unter demselben Artefaktnamen.
    pj.record_receipt(
        pfad, "r1", artifact="a", output_sha256=H3, inputs={"quelle": H1},
        code_version="v1", step="unbound-lauf",
    )
    pj.record_decision(
        pfad, "r1", artifact="a", subject_sha256=H3, verdict="WITHDRAW",
        reference="PI-3", actor="Third reviewer", at=AT,
    )
    # Akte ohne jeden registrierten Artefaktnamen.
    pj.record_receipt(
        pfad, "r1", artifact="u", output_sha256=H3, inputs={"quelle": H1},
        code_version="v1", step="only-unbound",
    )


def _ansicht(gebaut, record: str, artefakt: str):
    return next(
        a for r in gebaut.records if r.record_id == record
        for a in r.artifacts if a.artifact == artefakt
    )


def test_ungebundene_akte_bei_vorhandenem_namen_bleiben_sichtbar(jpath: Path) -> None:
    _bestand(jpath)
    gebaut = hist.build_history(hist.load_snapshot(jpath, "sha256"))
    ansicht = _ansicht(gebaut, "r1", "a")
    assert [r.seq for r in ansicht.unbound_receipts] == [9]
    assert ansicht.unbound_receipts[0].output_sha256 == H3
    assert [d.seq for d in ansicht.unbound_decisions] == [10]
    assert ansicht.unbound_decisions[0].subject_sha256 == H3
    assert ansicht.unbound_decisions[0].verdict == "WITHDRAW"
    fremd = _ansicht(gebaut, "r1", "u")
    assert fremd.revisions == ()
    assert [r.seq for r in fremd.unbound_receipts] == [11]
    assert fremd.unbound_receipts[0].output_sha256 == H3


def test_alle_entscheidungen_und_details_einsehbar(jpath: Path) -> None:
    _bestand(jpath)
    gebaut = hist.build_history(hist.load_snapshot(jpath, "sha256"))
    # Kompakte Fassung: nur die letzte Entscheidung nach seq.
    ansicht = _ansicht(gebaut, "r1", "a")
    assert ansicht.current.sha256 == H2
    assert ansicht.current.seq == 8
    assert ansicht.current.latest_decision is None
    alt = next(r for r in ansicht.revisions if r.sha256 == H1)
    assert alt.latest_decision.seq == 7
    assert alt.latest_decision.verdict == "REJECT"
    # Vollständige Ereignisliste: alle drei Entscheidungen mit Angaben.
    entscheidungen = [e for e in gebaut.events if e.kind == "decision.recorded"]
    assert [(e.payload["verdict"], e.payload["reference"]) for e in entscheidungen] == [
        ("ACCEPT", "PI-1"), ("REJECT", "PI-2"), ("WITHDRAW", "PI-3"),
    ]
    assert entscheidungen[0].payload["actor"] == "First reviewer"
    assert entscheidungen[0].payload["note"] == "first decision note"
    assert entscheidungen[0].payload["at"] == AT
    assert entscheidungen[0].payload["subject_sha256"] == H1
    assert entscheidungen[2].payload["subject_sha256"] == H3
    quelle = next(e for e in gebaut.events if e.kind == "source.ingested")
    assert quelle.payload["filename"] == "source-visible.txt"
    assert quelle.payload["sha256"] == H1
    assert quelle.payload["bytes"] == 1
    assert quelle.payload["media_type"] == "text/plain"
    beleg = next(e for e in gebaut.events if e.kind == "receipt.recorded")
    assert beleg.payload["inputs"] == {"quelle": H1}
    assert beleg.payload["params"] == {"schwelle": 3}
    assert beleg.payload["step"] == "s"
    assert beleg.payload["code_version"] == "v1"
    assert all(e.payload for e in gebaut.events)


def test_cli_zeigt_akte_details_und_hashes(tmp_path: Path) -> None:
    arbeit = tmp_path / "details"
    arbeit.mkdir()
    assert run_cli(arbeit, "--journal", "j.jsonl", "init").returncode == 0
    assert run_cli(arbeit, "--journal", "j.jsonl", "register",
                   "--record", "r1").returncode == 0
    (arbeit / "q.txt").write_bytes(b"q")
    assert run_cli(arbeit, "--journal", "j.jsonl", "ingest", "--record", "r1",
                   "--file", "q.txt", "--media-type", "text/plain").returncode == 0
    assert run_cli(arbeit, "--journal", "j.jsonl", "artifact", "--record", "r1",
                   "--artifact", "a", "--file", "q.txt").returncode == 0
    assert run_cli(arbeit, "--journal", "j.jsonl", "receipt", "--record", "r1",
                   "--artifact", "a", "--output", "q.txt", "--input", "q=q.txt",
                   "--step", "s", "--code-version", "v1").returncode == 0
    als_json = run_cli(arbeit, "--journal", "j.jsonl", "history", "--json")
    assert als_json.returncode == 0, als_json.stderr
    ansicht = json.loads(als_json.stdout)
    assert '"inputs"' in als_json.stdout
    assert "source.ingested" in {e["kind"] for e in ansicht["events"]}
    quelle = next(e for e in ansicht["events"] if e["kind"] == "source.ingested")
    assert quelle["payload"]["filename"] == "q.txt"
    assert len(quelle["payload"]["sha256"]) == 64
    terminal = run_cli(arbeit, "--journal", "j.jsonl", "history")
    assert terminal.returncode == 0
    assert "q.txt" in terminal.stdout
