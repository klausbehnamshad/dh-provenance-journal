"""Konkurrenz und sichere Pfade (Abnahme).

Portiert nach Schutzvertrag (nicht nach Dateiname): Gleichzeitige Schreiber
serialisieren über die Journalsperre; Symlink/Verzeichnis/FIFO am Journal-
oder Lockpfad sowie fehlendes Elternverzeichnis beim Schreiben sind Befunde
(fail-closed), kein Datenzustand. Kein Test hängt: FIFO-Öffnung nutzt
O_NONBLOCK, die S_ISREG-Prüfung schlägt vor jedem Lesen an.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path

import pytest

import provenance_journal as pj
from provenance_journal._store import Journal
from provenance_journal.errors import JournalIOError, JournalUnsafe

from .conftest import H1


def _receipt_args(i: int, j: int) -> dict:
    return {
        "artifact": f"a-{i}-{j}.txt",
        "output_sha256": H1,
        "inputs": {"quelle": H1},
        "code_version": "v0.1",
        "step": f"s-{i}-{j}",
    }


def test_concurrent_writers_keep_chain_intact(jpath: Path) -> None:
    pj.init_journal(jpath)
    pj.register_record(jpath, "rec-01")
    errors: list[BaseException] = []

    def worker(i: int) -> None:
        try:
            for j in range(20):
                pj.record_receipt(jpath, "rec-01", **_receipt_args(i, j))
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(16)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    events = pj.verify_journal(jpath)
    assert len(events) == 2 + 16 * 20
    seqs = [e.seq for e in events]
    assert seqs == list(range(1, len(events) + 1))
    steps = {e.payload["step"] for e in events if e.kind == "receipt.recorded"}
    assert len(steps) == 16 * 20


def test_symlinked_journal_refused_on_read_and_write(jdir: Path) -> None:
    real = jdir / "real.jsonl"
    pj.init_journal(real)
    before = real.read_bytes()
    link = jdir / "journal.jsonl"
    os.symlink(real, link)
    # Ohne Beistelldatei am Linkpfad verlangt die API erst die Moduswahl
    # (ConfigError) — mit explizitem Modus greift der Pfadbefund.
    with pytest.raises(JournalUnsafe):
        pj.read_events(link, integrity="sha256")
    with pytest.raises(JournalUnsafe):
        pj.register_record(link, "rec-01", integrity="sha256")
    assert real.read_bytes() == before


def test_broken_symlink_is_presence_not_absence(jdir: Path) -> None:
    link = jdir / "journal.jsonl"
    os.symlink(jdir / "ziel-gibt-es-nicht.jsonl", link)
    with pytest.raises(JournalUnsafe):
        pj.read_events(link, integrity="sha256")
    with pytest.raises(JournalUnsafe):
        pj.init_journal(link)


def test_symlinked_lock_refused(jdir: Path) -> None:
    real = jdir / "real.jsonl"
    pj.init_journal(real)
    before = real.read_bytes()
    (jdir / "real.jsonl.lock").unlink()  # Link ersetzt die Sperrdatei
    other = jdir / "fremd.lock"
    other.write_bytes(b"x")
    os.symlink(other, jdir / "real.jsonl.lock")
    with pytest.raises(JournalUnsafe):
        pj.register_record(real, "rec-01")
    assert real.read_bytes() == before


def test_symlinked_parent_cannot_move_journal(jdir: Path, tmp_path: Path) -> None:
    draussen = tmp_path / "draussen"
    draussen.mkdir()
    link = jdir / "unter"
    os.symlink(draussen, link)
    with pytest.raises(JournalUnsafe):
        pj.init_journal(link / "journal.jsonl")
    assert list(draussen.iterdir()) == []


def test_directory_at_journal_path_refused(jdir: Path) -> None:
    d = jdir / "journal.jsonl"
    d.mkdir()
    with pytest.raises(JournalUnsafe):
        pj.read_events(d, integrity="sha256")
    with pytest.raises(JournalUnsafe):
        pj.init_journal(d)


def test_fifo_at_journal_path_refused_without_blocking(jdir: Path) -> None:
    fifo = jdir / "journal.jsonl"
    os.mkfifo(fifo)
    with pytest.raises(JournalUnsafe):
        pj.read_events(fifo, integrity="sha256")
    with pytest.raises(JournalUnsafe):
        pj.init_journal(fifo)


def test_directory_at_lock_path_refused(jdir: Path) -> None:
    real = jdir / "journal.jsonl"
    pj.init_journal(real)
    before = real.read_bytes()
    (jdir / "journal.jsonl.lock").unlink()  # Verzeichnis ersetzt die Sperrdatei
    (jdir / "journal.jsonl.lock").mkdir()
    with pytest.raises(JournalUnsafe):
        pj.register_record(real, "rec-01")
    assert real.read_bytes() == before


def test_missing_parent_on_write_creates_nothing(jdir: Path) -> None:
    target = jdir / "fehlt" / "journal.jsonl"
    with pytest.raises(JournalUnsafe):
        pj.init_journal(target)
    assert not (jdir / "fehlt").exists()


def test_missing_journal_on_read_is_no_finding(jdir: Path) -> None:
    from provenance_journal.errors import ConfigError

    with pytest.raises(ConfigError, match="explizite Moduswahl"):
        pj.read_events(jdir / "journal.jsonl")
    assert pj.read_events(jdir / "journal.jsonl", integrity="sha256") == []
    report = pj.check_journal(jdir / "journal.jsonl", integrity="sha256")
    assert report.chain_ok and report.events == ()


def test_lock_check_without_lockfile_is_no_finding(jdir: Path) -> None:
    Journal(jdir / "journal.jsonl").pruefe_lockpfad()


def test_lock_check_finds_symlinked_lock(jdir: Path) -> None:
    real = jdir / "journal.jsonl"
    pj.init_journal(real)
    (jdir / "journal.jsonl.lock").unlink()  # Link ersetzt die Sperrdatei
    os.symlink(jdir / "fremd.lock", jdir / "journal.jsonl.lock")
    with pytest.raises(JournalUnsafe):
        Journal(real).pruefe_lockpfad()


def test_unsafe_reason_is_single_line_and_path_free(jdir: Path) -> None:
    link = jdir / "journal.jsonl"
    os.symlink(jdir / "nichts.jsonl", link)
    try:
        pj.read_events(link, integrity="sha256")
    except JournalUnsafe as exc:
        assert "\n" not in str(exc)
        assert str(link) not in str(exc)
        assert exc.pfad == link
    else:  # pragma: no cover
        raise AssertionError("kein Befund erhoben")


def test_unsafe_is_fail_closed_io_error(jdir: Path) -> None:
    assert issubclass(JournalUnsafe, JournalIOError)
