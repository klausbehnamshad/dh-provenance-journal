"""CLI-Durchläufe über den installierten Einstieg als Subprozess.

`python -m provenance_journal` läuft als eigener Prozess mit Arbeits-
verzeichnis außerhalb des Checkouts (tmp). Der echte `provjournal`-
Konsoleneinstieg wird in der Außen-Installation der Abnahme geprüft.
SHA-256 und HMAC laufen jeweils vollständig: sechs Schreibbefehle,
Verifikation, Historie und Artefaktprüfung.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import provenance_journal

SRC = Path(provenance_journal.__file__).resolve().parent.parent
AT = "2026-10-03T12:00:00+00:00"


def run_cli(cwd: Path, *argv: str, env_extra: dict | None = None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, "-m", "provenance_journal", *argv],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


@pytest.fixture(params=["sha256", "hmac"])
def world(tmp_path: Path, request) -> dict:
    mode = request.param
    work = tmp_path / "arbeit"
    work.mkdir()
    (work / "quelle.txt").write_bytes(b"Quelle-Eins\n")
    (work / "ergebnis-v1.txt").write_bytes(b"Ergebnis-Eins\n")
    (work / "ergebnis-v2.txt").write_bytes(b"Ergebnis-Zwei\n")
    (work / "params.json").write_text('{"schwelle": 3}', encoding="utf-8")
    if mode == "hmac":
        key = tmp_path / "journal.key"
        key.write_bytes(b"e2e-schluessel-auftrag-02-01")
        base = ["--journal", "journal.jsonl", "--integrity", "hmac",
                "--key-file", str(key)]
    else:
        base = ["--journal", "journal.jsonl"]
    proc = run_cli(work, *base, "init")
    assert proc.returncode == 0, proc.stderr
    return {"work": work, "base": base, "mode": mode}


def cli(world: dict, *argv: str) -> subprocess.CompletedProcess:
    return run_cli(world["work"], *world["base"], *argv)


def journal_lines(world: dict) -> int:
    data = (world["work"] / "journal.jsonl").read_bytes()
    return len([line for line in data.split(b"\n") if line.strip()])


def test_full_flow_verify_history_check(world: dict) -> None:
    assert cli(world, "register", "--record", "rec-01").returncode == 0
    assert cli(world, "ingest", "--record", "rec-01", "--file", "quelle.txt",
               "--media-type", "text/plain").returncode == 0
    assert cli(world, "artifact", "--record", "rec-01", "--artifact", "erg.txt",
               "--file", "ergebnis-v1.txt").returncode == 0
    proc = cli(world, "receipt", "--record", "rec-01", "--artifact", "erg.txt",
               "--output", "ergebnis-v1.txt", "--input", "quelle=quelle.txt",
               "--step", "ableitung", "--code-version", "v1",
               "--params-file", "params.json")
    assert proc.returncode == 0, proc.stderr
    assert cli(world, "decide", "--record", "rec-01", "--artifact", "erg.txt",
               "--file", "ergebnis-v1.txt", "--verdict", "ACCEPT",
               "--reference", "PI-1", "--actor", "A. Nau", "--at", AT).returncode == 0

    verify = cli(world, "verify")
    assert verify.returncode == 0, verify.stderr
    assert "Kette: gültig (6 Ereignisse)" in verify.stdout
    assert "0 ungültig" in verify.stdout

    history = cli(world, "history")
    assert history.returncode == 0
    assert "rec-01" in history.stdout and "aktuelle Fassung" in history.stdout

    check = cli(world, "check-artifact", "--record", "rec-01", "--artifact", "erg.txt",
                "--file", "ergebnis-v1.txt")
    assert check.returncode == 0, check.stderr
    assert "registriert (aktuelle Fassung, seq 4)" in check.stdout
    assert "ACCEPT" in check.stdout

    as_json = cli(world, "verify", "--json")
    assert as_json.returncode == 0
    payload = json.loads(as_json.stdout)
    assert payload["chain"] == {"ok": True, "events": 6}
    assert payload["summary"] == {"valid": 6, "invalid": 0, "unchecked": 0}


def test_duplicates_append_nothing_new_revisions_stay(world: dict) -> None:
    cli(world, "register", "--record", "rec-01")
    before = journal_lines(world)
    dup = cli(world, "register", "--record", "rec-01")
    assert dup.returncode == 0
    assert "bereits vorhanden" in dup.stdout
    assert journal_lines(world) == before
    cli(world, "artifact", "--record", "rec-01", "--artifact", "erg.txt",
        "--file", "ergebnis-v1.txt")
    same = cli(world, "artifact", "--record", "rec-01", "--artifact", "erg.txt",
               "--file", "ergebnis-v1.txt")
    assert same.returncode == 0 and journal_lines(world) == before + 1
    cli(world, "artifact", "--record", "rec-01", "--artifact", "erg.txt",
        "--file", "ergebnis-v2.txt")
    assert journal_lines(world) == before + 2
    old = cli(world, "check-artifact", "--record", "rec-01", "--artifact", "erg.txt",
              "--file", "ergebnis-v1.txt")
    assert old.returncode == 0 and "historische Fassung" in old.stdout


def test_decision_sequence_and_json_views(world: dict) -> None:
    cli(world, "register", "--record", "rec-01")
    cli(world, "artifact", "--record", "rec-01", "--artifact", "erg.txt",
        "--file", "ergebnis-v1.txt")
    for verdict, ref in (("ACCEPT", "PI-1"), ("REJECT", "PI-2"), ("WITHDRAW", "PI-3")):
        proc = cli(world, "decide", "--record", "rec-01", "--artifact", "erg.txt",
                   "--file", "ergebnis-v1.txt", "--verdict", verdict,
                   "--reference", ref, "--actor", "A. Nau", "--at", AT)
        assert proc.returncode == 0, proc.stderr
    history = json.loads(cli(world, "history", "--json").stdout)
    assert history["view"] == "full"
    rev = history["records"][0]["artifacts"][0]["revisions"][0]
    assert rev["latest_decision"]["verdict"] == "WITHDRAW"
    assert rev["latest_decision"]["seq"] == 6
    assert "Abgeleitete Ansicht" in history["scope_note"]
    filtered = json.loads(cli(world, "history", "--record", "rec-01", "--json").stdout)
    assert filtered["view"] == "derived" and filtered["filters"] == {"record": "rec-01"}


def test_exit_codes_for_bad_input(world: dict) -> None:
    cli(world, "register", "--record", "rec-01")
    before = journal_lines(world)
    missing = cli(world, "ingest", "--record", "rec-01", "--file", "fehlt.txt",
                  "--media-type", "text/plain")
    assert missing.returncode == 1
    assert journal_lines(world) == before
    bad_verdict = run_cli(world["work"], *world["base"], "decide", "--record", "rec-01",
                          "--artifact", "e", "--file", "quelle.txt", "--verdict", "MAYBE",
                          "--reference", "PI-1", "--actor", "A")
    assert bad_verdict.returncode == 2
    dup_role = cli(world, "receipt", "--record", "rec-01", "--artifact", "e",
                   "--output", "quelle.txt", "--input", "q=quelle.txt",
                   "--input", "q=quelle.txt", "--step", "s", "--code-version", "v")
    assert dup_role.returncode == 2
    assert journal_lines(world) == before
