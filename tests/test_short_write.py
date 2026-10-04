"""Kurze Writes und Write-/fsync-Fehler (Abnahmen).

* Restbytes werden korrekt geschrieben; ohne vollständiges Schreiben und
  fsync kein Erfolg.
* Kein falscher Erfolg, keine automatische Wiederholung, erneute Prüfung
  vor Wiederaufnahme. Nach Fehlern kann ein teilweise oder vollständig
  geschriebenes Ereignis vorhanden sein — das meldet die Diagnose.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

import provenance_journal as pj
from provenance_journal import _store
from provenance_journal.errors import ChainError, JournalIOError, UnconfirmedWrite

from .conftest import H1, H2


@pytest.fixture
def prepared(jpath: Path) -> Path:
    pj.init_journal(jpath)
    pj.register_record(jpath, "rec-01")
    return jpath


def test_short_writes_are_completed(prepared: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    real_write = os.write
    calls = {"n": 0, "bytes": 0}

    def short(fd: int, data) -> int:  # noqa: ANN001, ANN202
        calls["n"] += 1
        chunk = bytes(data[:7])
        written = real_write(fd, chunk)
        calls["bytes"] += written
        return written

    monkeypatch.setattr(os, "write", short)
    res = pj.produce_artifact(prepared, "rec-01", artifact="a.txt", sha256=H1)
    assert res.appended
    line = (prepared.read_bytes().split(b"\n"))[res.event.seq - 1]
    assert calls["bytes"] >= len(line) > 7
    assert calls["n"] > 1  # die Kurzschreibung wurde tatsächlich ausgeübt
    events = pj.read_events(prepared)
    assert events[-1].digest == res.event.digest
    assert events[-1].payload == {"artifact": "a.txt", "sha256": H1}


def test_zero_write_is_no_success(prepared: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    before = prepared.read_bytes()

    def zero(fd: int, data) -> int:  # noqa: ANN001, ANN202
        return 0

    monkeypatch.setattr(os, "write", zero)
    with pytest.raises(UnconfirmedWrite, match="unbestätigt"):
        pj.produce_artifact(prepared, "rec-01", artifact="a.txt", sha256=H1)
    assert prepared.read_bytes() == before


def test_write_error_is_no_success_and_not_retried(
    prepared: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = prepared.read_bytes()
    attempts = {"n": 0}
    real_write = os.write

    def failing(fd: int, data) -> int:  # noqa: ANN001, ANN202
        attempts["n"] += 1
        raise OSError("simulierter Plattenfehler")

    monkeypatch.setattr(os, "write", failing)
    with pytest.raises(UnconfirmedWrite, match="unbestätigt"):
        pj.produce_artifact(prepared, "rec-01", artifact="a.txt", sha256=H1)
    assert attempts["n"] == 1  # genau ein Versuch, keine automatische Wiederholung
    assert prepared.read_bytes() == before
    assert _store.os.write is not real_write  # Patch war aktiv (Sanity)


def test_resume_requires_reverification(prepared: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Erneute Prüfung vor Wiederaufnahme: Bestand ist heil (nichts angehängt),
    # also darf der Vorgang erneut ausgeführt werden — und gelingt dann.
    monkeypatch.setattr(os, "write", lambda fd, data: (_ for _ in ()).throw(OSError("x")))
    with pytest.raises(UnconfirmedWrite):
        pj.produce_artifact(prepared, "rec-01", artifact="a.txt", sha256=H1)
    monkeypatch.undo()
    pj.verify_journal(prepared)  # erneute Prüfung
    res = pj.produce_artifact(prepared, "rec-01", artifact="a.txt", sha256=H1)
    assert res.appended
    pj.verify_journal(prepared)


def test_fsync_error_is_no_success(prepared: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    before = prepared.read_bytes()

    def failing_fsync(fd: int) -> None:
        raise OSError("simulierter fsync-Fehler")

    monkeypatch.setattr(os, "fsync", failing_fsync)
    with pytest.raises(UnconfirmedWrite, match="unbestätigt"):
        pj.produce_artifact(prepared, "rec-01", artifact="a.txt", sha256=H1)
    after = prepared.read_bytes()
    assert len(after) > len(before)  # vollständig geschrieben, aber unbestätigt
    # Die Diagnose unterscheidet: Bytes sind vollständig da, Erfolg gab es nicht.
    events = pj.read_events(prepared)
    assert events[-1].payload == {"artifact": "a.txt", "sha256": H1}


def test_partial_line_is_neither_repaired_nor_resumed_blindly(
    prepared: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_write = os.write
    state = {"writes": 0}

    def half_then_fail(fd: int, data) -> int:  # noqa: ANN001, ANN202
        state["writes"] += 1
        if state["writes"] == 1:
            return real_write(fd, bytes(data[: len(data) // 2]))
        raise OSError("Abbruch nach halber Zeile")

    monkeypatch.setattr(os, "write", half_then_fail)
    before = prepared.read_bytes()
    with pytest.raises(UnconfirmedWrite):
        pj.produce_artifact(prepared, "rec-01", artifact="a.txt", sha256=H1)
    damaged = prepared.read_bytes()
    assert damaged != before
    assert damaged.startswith(before)
    with pytest.raises((ChainError, JournalIOError)):
        pj.verify_journal(prepared)
    # Keine automatische Kürzung/Reparatur: Schaden bleibt sichtbar ...
    assert prepared.read_bytes() == damaged
    # ... und ein neuer Versuch beginnt mit erneuter Prüfung, nicht mit Anhängen.
    with pytest.raises((ChainError, JournalIOError)):
        pj.produce_artifact(prepared, "rec-01", artifact="a.txt", sha256=H2)
    assert prepared.read_bytes() == damaged
