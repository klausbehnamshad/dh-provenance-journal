"""R1: Ein Lesevorgang je Befehl; geprüfter Snapshot unveränderlich.

Öffentliche Leser/Auswertung plus CLI als Subprozess: Nach dem ersten
echten Lesen darf Löschen/Ergänzen des Journals die Auswertung nicht
ändern; nachträgliche Mutation einer herausgegebenen Kopie (Fassungshash,
Entscheidungshash, verschachtelte Inputs/Params) registriert keinen nie
aufgezeichneten Hash und übernimmt keine Entscheidung.
"""

from __future__ import annotations

import json
from pathlib import Path

import provenance_journal as pj
from provenance_journal import cli
from provenance_journal import history as hist

from .conftest import AT, H1, H2, H3, H4


def _voller_stand(pfad: Path) -> None:
    pj.init_journal(pfad)
    pj.register_record(pfad, "r1")
    pj.produce_artifact(pfad, "r1", artifact="a", sha256=H1)
    pj.record_receipt(
        pfad, "r1", artifact="a", output_sha256=H1, inputs={"quelle": H2},
        code_version="v1", step="s", params={"schwelle": 3},
    )
    pj.record_decision(
        pfad, "r1", artifact="a", subject_sha256=H1, verdict="ACCEPT",
        reference="PI-1", actor="A. Nau", at=AT,
    )


def test_geloeschtes_journal_aendert_geprueften_stand_nicht(jpath: Path) -> None:
    _voller_stand(jpath)
    snapshot = hist.load_snapshot(jpath, "sha256")
    jpath.unlink()
    gebaut = hist.build_history(snapshot)
    assert len(gebaut.records[0].artifacts[0].revisions) == 1
    geprüft = hist.check_artifact(snapshot, record_id="r1", artifact="a", sha256=H1)
    assert geprüft.registered and geprüft.currency == "current"
    assert geprüft.latest_decision is not None
    assert geprüft.latest_decision.verdict == "ACCEPT"


def test_mutierte_kopie_registriert_nie_aufgezeichneten_hash(jpath: Path) -> None:
    _voller_stand(jpath)
    snapshot = hist.load_snapshot(jpath, "sha256")
    kopie = snapshot.events
    kopie[2].payload["sha256"] = H4
    kopie[3].payload["inputs"]["quelle"] = H4
    kopie[3].payload["params"]["schwelle"] = 99
    kopie[4].payload["subject_sha256"] = H4
    fremd = hist.check_artifact(snapshot, record_id="r1", artifact="a", sha256=H4)
    assert not fremd.registered
    assert fremd.latest_decision is None
    # Der unveränderte geprüfte Stand gilt weiter — mit alter Bewertung.
    original = hist.check_artifact(snapshot, record_id="r1", artifact="a", sha256=H1)
    assert original.registered and original.currency == "current"
    assert original.latest_decision is not None
    assert original.latest_decision.verdict == "ACCEPT"
    assert original.receipts[0].inputs == {"quelle": H2}
    erneut = snapshot.events
    assert erneut[2].payload["sha256"] == H1
    assert erneut[3].payload["inputs"] == {"quelle": H2}
    assert erneut[3].payload["params"] == {"schwelle": 3}
    assert erneut[4].payload["subject_sha256"] == H1


def test_verify_liest_nur_einmal(capsys, jpath: Path, monkeypatch) -> None:
    _voller_stand(jpath)
    original = cli.load_snapshot
    aufrufe = []

    def beobachtend(*args, **kwargs):
        snapshot = original(*args, **kwargs)
        aufrufe.append(snapshot)
        if len(aufrufe) == 1:
            jpath.unlink()
        return snapshot

    monkeypatch.setattr(cli, "load_snapshot", beobachtend)
    code = cli.main(["--journal", str(jpath), "verify", "--json"])
    assert code == 0
    assert len(aufrufe) == 1
    bericht = json.loads(capsys.readouterr().out)
    assert bericht["chain"] == {"ok": True, "events": 5}
