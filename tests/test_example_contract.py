"""C2/C3: Beispielvertrag — exklusives Ziel, exakte Negativprobe.

`examples/run.sh` läuft als Subprozess gegen eine `provjournal`-Scheibe
auf PATH (echte CLI des Baums oder Wrapper für die Negativprobe). Alle
Bestände sind synthetisch und temporär.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import provenance_journal
from provenance_journal import history as hist

REPO = Path(provenance_journal.__file__).resolve().parent.parent.parent
SKRIPT = REPO / "examples" / "run.sh"
SRC = Path(provenance_journal.__file__).resolve().parent.parent


def _scheibe(arbeit: Path, wrapper: bool = False) -> Path:
    """Legt `provjournal` auf PATH: echt oder mit Exit-2-Negativprobe."""
    kiste = arbeit / "kiste"
    kiste.mkdir()
    ziel = kiste / "provjournal"
    if wrapper:
        ziel.write_text(
            "#!/bin/sh\n"
            "for a in \"$@\"; do\n"
            '  if [ "$a" = "veraendert.txt" ]; then\n'
            '    echo "provjournal: Konfiguration: simuliert" >&2\n'
            "    exit 2\n"
            "  fi\n"
            "done\n"
            f'exec "{sys.executable}" -m provenance_journal "$@"\n'
        )
    else:
        ziel.write_text(
            "#!/bin/sh\n"
            f'exec "{sys.executable}" -m provenance_journal "$@"\n'
        )
    ziel.chmod(ziel.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return kiste


def _lauf(arbeit: Path, ziel: Path, wrapper: bool = False) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PATH"] = str(_scheibe(arbeit, wrapper)) + os.pathsep + env["PATH"]
    env["PYTHONPATH"] = str(SRC)
    return subprocess.run(
        ["bash", str(SKRIPT), str(ziel)],
        cwd=arbeit, env=env, capture_output=True, text=True, timeout=180,
    )


def test_bestehendes_ziel_wird_abgewiesen(tmp_path: Path) -> None:
    arbeit = tmp_path / "w"
    arbeit.mkdir()
    ziel = arbeit / "versuch"
    ziel.mkdir()
    (ziel / "veraendert.txt").write_bytes(b"eigene notizen\n")
    vorher = (ziel / "veraendert.txt").read_bytes()
    dateien_vorher = sorted(p.name for p in ziel.iterdir())
    proc = _lauf(arbeit, ziel)
    assert proc.returncode != 0
    assert "existiert bereits" in proc.stdout + proc.stderr
    assert (ziel / "veraendert.txt").read_bytes() == vorher
    assert sorted(p.name for p in ziel.iterdir()) == dateien_vorher
    assert not (ziel / "journal.jsonl").exists()


def test_bestehendes_journal_wird_abgewiesen(tmp_path: Path) -> None:
    arbeit = tmp_path / "w"
    arbeit.mkdir()
    ziel = arbeit / "versuch"
    ziel.mkdir()
    (ziel / "journal.jsonl").write_text("{}\n", encoding="utf-8")
    proc = _lauf(arbeit, ziel)
    assert proc.returncode != 0
    assert (ziel / "journal.jsonl").read_text(encoding="utf-8") == "{}\n"


def test_falscher_negativ_exit_scheitert_ohne_ok(tmp_path: Path) -> None:
    arbeit = tmp_path / "w"
    arbeit.mkdir()
    proc = _lauf(arbeit, arbeit / "versuch", wrapper=True)
    assert proc.returncode != 0
    assert "BEISPIEL OK" not in proc.stdout


def test_regulaerer_ablauf_bestaetigt_werte(tmp_path: Path) -> None:
    arbeit = tmp_path / "w"
    arbeit.mkdir()
    ziel = arbeit / "versuch"
    proc = _lauf(arbeit, ziel)
    assert proc.returncode == 0, proc.stderr
    assert "BEISPIEL OK" in proc.stdout
    pfad = ziel / "journal.jsonl"
    gebaut = hist.build_history(hist.load_snapshot(pfad, None))
    ansicht = gebaut.records[0].artifacts[0]
    assert ansicht.current is not None
    v2, v1 = ansicht.current.sha256, next(
        r.sha256 for r in ansicht.revisions if r.sha256 != ansicht.current.sha256
    )
    assert ansicht.current.seq == 7
    alt = next(r for r in ansicht.revisions if r.sha256 == v1)
    assert alt.seq == 4
    assert alt.latest_decision is not None
    assert (alt.latest_decision.verdict, alt.latest_decision.seq) == ("REJECT", 8)
    verdicts = {e.payload.get("verdict") for e in gebaut.events if e.kind == "decision.recorded"}
    assert {"ACCEPT", "REJECT"} <= verdicts
    geprüft = hist.check_artifact(
        hist.load_snapshot(pfad, None), record_id="interview-01",
        artifact="transkript", sha256=v2,
    )
    assert geprüft.registered and geprüft.currency == "current"
    gefiltert = hist.filter_history(gebaut, artifact="transkript", sha256=v1)
    gefilterte_ansicht = gefiltert.records[0].artifacts[0]
    assert [r.sha256 for r in gefilterte_ansicht.revisions] == [v1]
    assert gefilterte_ansicht.current is not None
    assert gefilterte_ansicht.current.sha256 == v2
