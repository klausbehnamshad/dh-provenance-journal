"""R4: Bekannte Basisfehler ergeben überall Exit 1 mit sichtbarem Befund.

Gemeinsame Basisbewertung aus demselben Snapshot für verify, history und
check-artifact — in Terminal- und JSON-Ausgabe. Gültige Einzelzuordnungen
bleiben sichtbar; kein Filter verdeckt den globalen Prüfbefund.
Fachlich ungeprüfte Spezialereignisse (UNDO) sowie REJECT/WITHDRAW sind
keine Integritätsfehler.
"""

from __future__ import annotations

import json
from pathlib import Path

from .conftest import AT, H1, H2, forge_journal
from .test_cli_e2e import run_cli


def _cli(arbeit: Path, *argv: str):
    return run_cli(arbeit, "--journal", "j.jsonl", *argv)


def _bestand(arbeit: Path, specs: list) -> None:
    forge_journal(arbeit / "j.jsonl", specs)
    (arbeit / "j.jsonl.config.json").write_text('{"integrity": "sha256"}\n')


GUELTIG = [
    ("workspace.initialised", None,
     {"profile": "research-basic-v1", "root": ".", "version": "v0.1"}),
    ("record.registered", "r1", {"record_id": "r1", "profile": "research-basic-v1"}),
    ("artifact.produced", "r1", {"artifact": "a", "sha256": H1}),
]


def test_ungueltige_quelle_ergibt_ueberall_exit_1(tmp_path: Path) -> None:
    import hashlib

    arbeit = tmp_path / "basis"
    arbeit.mkdir()
    (arbeit / "alt.txt").write_bytes(b"A")
    digest = hashlib.sha256(b"A").hexdigest()
    _bestand(arbeit, [
        ("workspace.initialised", None,
         {"profile": "research-basic-v1", "root": ".", "version": "v0.1"}),
        ("record.registered", "r1",
         {"record_id": "r1", "profile": "research-basic-v1"}),
        ("artifact.produced", "r1", {"artifact": "a", "sha256": digest}),
        ("source.ingested", "r1",
         {"record_id": "r1", "sha256": digest, "media_type": "text/plain",
          "filename": "s.txt", "bytes": -1}),
    ])
    for befehl in (
        ["verify"], ["history"],
        ["check-artifact", "--record", "r1", "--artifact", "a", "--file", "alt.txt"],
    ):
        terminal = _cli(arbeit, *befehl)
        assert terminal.returncode == 1, befehl
        assert "seq 4" in terminal.stdout, befehl
        assert '"bytes"' in terminal.stdout, befehl
        als_json = _cli(arbeit, *befehl, "--json")
        assert als_json.returncode == 1, befehl
        ansicht = json.loads(als_json.stdout)
        befunde = ansicht["findings"] if befehl[0] != "verify" else ansicht["basis"]
        assert any(
            b["seq"] == 4 and b["outcome"] == "invalid" and b["fields"] == ["bytes"]
            for b in befunde
        )
    # Gültige Zuordnung bleibt daneben sichtbar.
    geprüft = json.loads(_cli(
        arbeit, "check-artifact", "--record", "r1", "--artifact", "a",
        "--file", "alt.txt", "--json").stdout)
    assert geprüft["registered"] is True


def test_ungueltige_entscheidung_und_beleg_ergibt_exit_1(tmp_path: Path) -> None:
    arbeit = tmp_path / "basis2"
    arbeit.mkdir()
    (arbeit / "alt.txt").write_bytes(b"A")
    _bestand(arbeit, GUELTIG + [
        ("receipt.recorded", "r1",
         {"artifact": "a", "output_sha256": H1, "inputs": {},
          "code_version": "v1", "kind": "deterministic", "step": "s"}),
        ("decision.recorded", "r1",
         {"artifact": "a", "subject_sha256": H1, "verdict": "VIELLEICHT",
          "reference": "PI-1", "actor": "A. Nau", "at": AT}),
    ])
    assert _cli(arbeit, "verify", "--json").returncode == 1
    assert _cli(arbeit, "history", "--json").returncode == 1
    assert _cli(arbeit, "history").returncode == 1
    prüfung = _cli(arbeit, "check-artifact", "--record", "r1", "--artifact", "a",
                   "--file", "alt.txt", "--json")
    assert prüfung.returncode == 1
    assert {b["seq"] for b in json.loads(prüfung.stdout)["findings"]} == {4, 5}


def test_filter_verdeckt_globalen_befund_nicht(tmp_path: Path) -> None:
    arbeit = tmp_path / "basis3"
    arbeit.mkdir()
    _bestand(arbeit, GUELTIG + [
        ("source.ingested", "r1",
         {"record_id": "r1", "sha256": H1, "media_type": "text/plain",
          "filename": "s.txt", "bytes": -1}),
    ])
    gefiltert = _cli(arbeit, "history", "--record", "r1", "--json")
    assert gefiltert.returncode == 1
    ansicht = json.loads(gefiltert.stdout)
    assert ansicht["filters"] == {"record": "r1"}
    assert any(b["outcome"] == "invalid" for b in ansicht["findings"])


def test_unchecked_und_negative_verdikte_sind_kein_fehler(tmp_path: Path) -> None:
    import hashlib

    arbeit = tmp_path / "spezial"
    arbeit.mkdir()
    (arbeit / "alt.txt").write_bytes(b"A")
    digest = hashlib.sha256(b"A").hexdigest()
    _bestand(arbeit, [
        ("workspace.initialised", None,
         {"profile": "research-basic-v1", "root": ".", "version": "v0.1"}),
        ("record.registered", "r1",
         {"record_id": "r1", "profile": "research-basic-v1"}),
        ("artifact.produced", "r1", {"artifact": "a", "sha256": digest}),
        ("decision.recorded", "r1",
         {"artifact": "a", "subject_sha256": digest, "verdict": "UNDO",
          "reference": "PI-0", "actor": "A. Nau", "at": AT}),
        ("decision.recorded", "r1",
         {"artifact": "a", "subject_sha256": H2, "verdict": "REJECT",
          "reference": "PI-1", "actor": "A. Nau", "at": AT}),
    ])
    assert _cli(arbeit, "verify").returncode == 0
    assert _cli(arbeit, "history").returncode == 0
    assert _cli(arbeit, "history", "--json").returncode == 0
    prüfung = _cli(arbeit, "check-artifact", "--record", "r1", "--artifact", "a",
                   "--file", "alt.txt")
    assert prüfung.returncode == 0
