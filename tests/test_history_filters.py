"""R2: Fassungsstatus folgt der höchsten Registrierungs-seq; Filter wählen nur aus.

Der aktuelle Stand bestimmt sich aus dem vollständigen Snapshot — ein
Filter ändert niemals „aktuell/historisch“. Filter gelten gemeinsam und
einheitlich für Fassungen, ungebundene Akte sowie Terminal- und
JSON-Ereignislisten: Record über die Hülle, Artefakt über das direkt
vorhandene artifact-Feld, Hash über den direkten Gegenstandshash der
jeweiligen Art. Input-Hashes begründen keinen Treffer; Ereignisse ohne
das gefilterte Feld passen nicht.
"""

from __future__ import annotations

import json
from pathlib import Path

import provenance_journal as pj
from provenance_journal import history as hist

from .conftest import AT, H1, H2, H3, forge_journal
from .test_cli_e2e import run_cli


def _bestand(pfad: Path) -> None:
    pj.init_journal(pfad)
    pj.register_record(pfad, "r1")
    pj.register_record(pfad, "r2")
    pj.ingest_source(
        pfad, "r1", sha256=H1, media_type="text/plain", filename="q.txt",
        num_bytes=1,
    )
    pj.produce_artifact(pfad, "r1", artifact="a", sha256=H1)
    pj.record_receipt(
        pfad, "r1", artifact="a", output_sha256=H1, inputs={"q": H1},
        code_version="v1", step="s",
    )
    pj.produce_artifact(pfad, "r1", artifact="a", sha256=H2)
    pj.record_receipt(
        pfad, "r1", artifact="u", output_sha256=H3, inputs={"q": H1},
        code_version="v1", step="fremd",
    )
    pj.produce_artifact(pfad, "r2", artifact="b", sha256=H2)


def _ansicht(gebaut, record: str, artefakt: str):
    treffer = next(
        a for r in gebaut.records if r.record_id == record
        for a in r.artifacts if a.artifact == artefakt
    )
    return treffer


def test_letzte_registrierung_bestimmt_aktuell_auch_bei_aba(jpath: Path) -> None:
    forge_journal(jpath, [
        ("workspace.initialised", None,
         {"profile": "research-basic-v1", "root": ".", "version": "v0.1"}),
        ("record.registered", "r1", {"record_id": "r1", "profile": "research-basic-v1"}),
        ("artifact.produced", "r1", {"artifact": "a", "sha256": H1}),
        ("artifact.produced", "r1", {"artifact": "a", "sha256": H2}),
        ("artifact.produced", "r1", {"artifact": "a", "sha256": H1}),
    ])
    gebaut = hist.build_history(hist.load_snapshot(jpath, "sha256"))
    ansicht = _ansicht(gebaut, "r1", "a")
    assert ansicht.current is not None
    assert ansicht.current.seq == 5
    assert ansicht.current.sha256 == H1


def test_hashfilter_macht_alte_fassung_nicht_aktuell(jpath: Path) -> None:
    _bestand(jpath)
    voll = hist.build_history(hist.load_snapshot(jpath, "sha256"))
    assert _ansicht(voll, "r1", "a").current.sha256 == H2
    gefiltert = hist.filter_history(voll, sha256=H1)
    ansicht = _ansicht(gefiltert, "r1", "a")
    assert [r.sha256 for r in ansicht.revisions] == [H1]
    # Status aus dem vollständigen Snapshot, nicht aus der Auswahl.
    assert ansicht.current is not None and ansicht.current.sha256 == H2
    assert all(r.sha256 != ansicht.current.sha256 for r in ansicht.revisions)


def test_filter_gelten_gemeinsam_fuer_ereignisse(jpath: Path) -> None:
    _bestand(jpath)
    voll = hist.build_history(hist.load_snapshot(jpath, "sha256"))
    assert len(voll.events) == 9
    gefiltert = hist.filter_history(
        voll, record_id="r1", artifact="a", sha256=H1,
    )
    # Nur Ereignisse mit allen drei Feldern passen: Fassung und Beleg zu H1.
    # Quelle und Registrierung tragen kein artifact-Feld und fallen heraus.
    assert [(e.seq, e.kind) for e in gefiltert.events] == [
        (5, "artifact.produced"),
        (6, "receipt.recorded"),
    ]
    # Hashfilter H1: kein Beleg zu H3, kein r2-Ereignis bleibt übrig.
    nur_hash = hist.filter_history(voll, sha256=H1)
    gegenstaende = {
        (e.kind, e.payload.get("sha256") or e.payload.get("output_sha256")
         or e.payload.get("subject_sha256"))
        for e in nur_hash.events
    }
    assert gegenstaende
    assert all(wert == H1 for _art, wert in gegenstaende)


def test_input_hash_begruendet_keinen_treffer(jpath: Path) -> None:
    _bestand(jpath)
    voll = hist.build_history(hist.load_snapshot(jpath, "sha256"))
    gefiltert = hist.filter_history(voll, sha256=H1)
    # Der Beleg zu H3 nennt H1 nur als Input — kein direkter Treffer.
    assert [e.seq for e in gefiltert.events if e.kind == "receipt.recorded"] == [6]
    assert ("r1", "u") not in [
        (a.record_id, a.artifact)
        for r in gefiltert.records for a in r.artifacts
    ]


def test_ungebundene_fremdhashes_fallen_aus_gefilterter_ansicht(jpath: Path) -> None:
    _bestand(jpath)
    voll = hist.build_history(hist.load_snapshot(jpath, "sha256"))
    assert len(_ansicht(voll, "r1", "u").unbound_receipts) == 1
    gefiltert = hist.filter_history(voll, sha256=H1)
    assert ("r1", "u") not in [
        (a.record_id, a.artifact)
        for r in gefiltert.records for a in r.artifacts
    ]


def test_cli_filter_status_und_ereignisse_konsistent(tmp_path: Path) -> None:
    arbeit = tmp_path / "filter"
    arbeit.mkdir()
    (arbeit / "q.txt").write_bytes(b"q")
    assert run_cli(arbeit, "--journal", "j.jsonl", "init").returncode == 0
    assert run_cli(arbeit, "--journal", "j.jsonl", "register",
                   "--record", "r1").returncode == 0
    assert run_cli(arbeit, "--journal", "j.jsonl", "artifact", "--record", "r1",
                   "--artifact", "a", "--file", "q.txt").returncode == 0
    (arbeit / "q.txt").write_bytes(b"qq")
    assert run_cli(arbeit, "--journal", "j.jsonl", "artifact", "--record", "r1",
                   "--artifact", "a", "--file", "q.txt").returncode == 0
    alt_hash = __import__("hashlib").sha256(b"q").hexdigest()
    gefiltert = run_cli(arbeit, "--journal", "j.jsonl", "history",
                        "--sha256", alt_hash, "--json")
    assert gefiltert.returncode == 0, gefiltert.stderr
    ansicht = json.loads(gefiltert.stdout)
    revisionen = ansicht["records"][0]["artifacts"][0]["revisions"]
    assert [r["sha256"] for r in revisionen] == [alt_hash]
    assert revisionen[0]["current"] is False
    assert ansicht["events"]
    assert all(
        (e["payload"].get("sha256") or e["payload"].get("output_sha256")
         or e["payload"].get("subject_sha256")) == alt_hash
        for e in ansicht["events"]
    )
    terminal = run_cli(arbeit, "--journal", "j.jsonl", "history",
                       "--sha256", alt_hash)
    assert terminal.returncode == 0
    assert "frühere Fassung" in terminal.stdout
    assert "aktuelle Fassung" not in terminal.stdout
