"""Fehler beim tatsächlichen Stream-Lesen richtig zuordnen (F5-Regression).

UTF-8-Dekodierungsfehler beim Iterieren des Streams sind `ChainError`
(ungültige Journalbytes), echte Stream-I/O-Fehler sind `JournalIOError`.
Keine rohen `UnicodeDecodeError`-/`OSError`-Ausnahmen für diese Fälle, kein
Anhang, unveränderte Journalbytes. Konfigurationsfehler bleiben getrennt.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

import provenance_journal as pj
from provenance_journal.errors import ChainError, ConfigError, JournalIOError


def test_invalid_utf8_is_chain_error(jpath: Path) -> None:
    jpath.write_bytes(b"\xff\n")
    with pytest.raises(ChainError):
        pj.read_events(jpath, integrity="sha256")
    report = pj.check_journal(jpath, integrity="sha256")
    assert not report.chain_ok
    assert report.chain_error


def test_invalid_utf8_blocks_writes_without_changes(jpath: Path) -> None:
    jpath.write_bytes(b"\xff\n")
    before = jpath.read_bytes()
    with pytest.raises(ChainError):
        pj.register_record(jpath, "rec-01", integrity="sha256")
    with pytest.raises(ChainError):
        pj.init_journal(jpath, integrity="sha256")
    assert jpath.read_bytes() == before


def test_no_forbidden_exception_types_on_bad_bytes(jpath: Path) -> None:
    jpath.write_bytes(b"\xff\n")
    for attempt in (
        lambda: pj.read_events(jpath, integrity="sha256"),
        lambda: pj.register_record(jpath, "rec-01", integrity="sha256"),
    ):
        try:
            attempt()
        except (UnicodeDecodeError, OSError) as exc:
            raise AssertionError(f"rohe Ausnahme entkommen: {type(exc).__name__}") from exc
        except ChainError:
            pass


class _FailingStream:
    """Stream, dessen Iteration mit OSError scheitert (injiziert)."""

    def __iter__(self):
        return self

    def __next__(self):
        raise OSError("injizierter Lesefehler")

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_injected_stream_io_error_is_journal_io_error(
    jpath: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pj.init_journal(jpath)
    before = jpath.read_bytes()
    monkeypatch.setattr(os, "fdopen", lambda *args, **kwargs: _FailingStream())
    with pytest.raises(JournalIOError):
        pj.read_events(jpath)
    with pytest.raises(JournalIOError):
        pj.register_record(jpath, "rec-neu")
    monkeypatch.undo()
    assert jpath.read_bytes() == before
    assert len(pj.read_events(jpath)) == 1


def test_config_errors_stay_separate(jdir: Path) -> None:
    # Fehlende Moduskonfiguration bleibt ConfigError — kein Kettenfehler.
    with pytest.raises(ConfigError, match="explizite Moduswahl"):
        pj.read_events(jdir / "journal.jsonl")
