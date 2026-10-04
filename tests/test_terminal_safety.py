"""R6: Terminalwerte sicher anzeigen; I/O-Fehler ohne Traceback.

Alle aus Journal oder Argumenten stammenden Terminalwerte sind
JSON-quotiert — insbesondere unbekannte Ereignisarten in Ereignis- und
Befundzeilen. Werte mit LF/CR/ANSI erzeugen keine zusätzlichen Zeilen
und keine Terminalsteuerung; JSON bleibt ein gültiges Objekt.
Gewöhnliche Öffnungs-, Lese- und Sperrfehler fallen in die vorhandene
I/O-Fehlerdomäne (Exit 1, Diagnose ohne Traceback).
"""

from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path

import pytest

import provenance_journal as pj
from provenance_journal import history as hist
from provenance_journal.errors import JournalIOError

from .conftest import forge_journal
from .test_cli_e2e import run_cli


def _cli(arbeit: Path, *argv: str):
    return run_cli(arbeit, "--journal", "j.jsonl", *argv)


def _laden(arbeit: Path) -> None:
    assert _cli(arbeit, "init").returncode == 0
    assert _cli(arbeit, "register", "--record", "r1").returncode == 0


def test_steuerzeichen_erzeugen_keine_zusatzzeilen(tmp_path: Path) -> None:
    arbeit = tmp_path / "steuer"
    arbeit.mkdir()
    forge_journal(arbeit / "j.jsonl", [
        ("workspace.initialised", None,
         {"profile": "research-basic-v1", "root": ".", "version": "v0.1"}),
        ("record.registered", "r1", {"record_id": "r1", "profile": "research-basic-v1"}),
        ("spezial\nFORGED-STATUS\x1b[31m", "r1", {}),
    ])
    (arbeit / "j.jsonl.config.json").write_text('{"integrity": "sha256"}\n')
    for befehl in (["history"], ["verify"]):
        proc = _cli(arbeit, *befehl)
        assert proc.returncode == 0, befehl
        assert "\x1b[31m" not in proc.stdout, befehl
        assert "\nFORGED-STATUS" not in proc.stdout, befehl
        assert "Traceback" not in proc.stderr, befehl
    als_json = _cli(arbeit, "history", "--json")
    assert als_json.returncode == 0
    ansicht = json.loads(als_json.stdout)
    assert len(ansicht["events"]) == 3


def test_unlesbare_lockdatei_ohne_traceback(tmp_path: Path) -> None:
    if os.geteuid() == 0:  # pragma: no cover
        pytest.skip("root umgeht Dateirechte")
    arbeit = tmp_path / "sperre"
    arbeit.mkdir()
    _laden(arbeit)
    stand = (arbeit / "j.jsonl").read_bytes()
    sperre = arbeit / "j.jsonl.lock"
    sperre.write_bytes(b"")
    sperre.chmod(0o000)
    try:
        proc = _cli(arbeit, "history")
        assert proc.returncode == 1
        assert "Traceback" not in proc.stderr
        with pytest.raises(JournalIOError):
            hist.load_snapshot(arbeit / "j.jsonl", "sha256")
    finally:
        sperre.chmod(0o600)
    assert (arbeit / "j.jsonl").read_bytes() == stand


def test_unlesbare_journaldatei_ohne_traceback(tmp_path: Path) -> None:
    if os.geteuid() == 0:  # pragma: no cover
        pytest.skip("root umgeht Dateirechte")
    arbeit = tmp_path / "leserecht"
    arbeit.mkdir()
    _laden(arbeit)
    (arbeit / "j.jsonl").chmod(0o000)
    try:
        proc = _cli(arbeit, "verify")
        assert proc.returncode == 1
        assert "Traceback" not in proc.stderr
    finally:
        (arbeit / "j.jsonl").chmod(0o600)


def test_injizierter_sperrfehler_ist_io_fehler(jpath: Path, monkeypatch, capsys) -> None:
    from provenance_journal import cli

    pj.init_journal(jpath)
    pj.register_record(jpath, "r1")

    def boom(*args, **kwargs):
        raise OSError("eingespritzter Sperrfehler")

    monkeypatch.setattr(fcntl, "flock", boom)
    with pytest.raises(JournalIOError):
        pj.register_record(jpath, "r2")
    code = cli.main(["--journal", str(jpath), "register", "--record", "r2"])
    assert code == 1
    fehler = capsys.readouterr().err
    assert "Traceback" not in fehler
