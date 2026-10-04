"""Sichere Zeilengrenze vor jedem Anhang (F1-Regression).

Ein nichtleeres Journal ohne abschließenden LF darf von keinem öffentlichen
Schreibweg verändert oder als erfolgreich initialisiert bestätigt werden.
Die reine lesende Digestprüfung akzeptiert einen solchen Bestand weiterhin;
Schreibbarkeit und Digestgültigkeit sind verschieden.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import provenance_journal as pj
from provenance_journal.errors import ChainError, VerificationError

from .conftest import AT, H1, H2


def _write_attempts(path: Path) -> list:
    return [
        lambda: pj.init_journal(path),
        lambda: pj.register_record(path, "rec-neu"),
        lambda: pj.ingest_source(
            path, "rec-01", sha256=H1, media_type="text/plain", filename="n.txt", num_bytes=1
        ),
        lambda: pj.produce_artifact(path, "rec-01", artifact="neu.txt", sha256=H2),
        lambda: pj.record_receipt(
            path,
            "rec-01",
            artifact="neu.txt",
            output_sha256=H2,
            inputs={"quelle": H1},
            code_version="v0.1",
            step="s",
        ),
        lambda: pj.record_decision(
            path,
            "rec-01",
            artifact="neu.txt",
            subject_sha256=H2,
            verdict="REJECT",
            reference="PI-2",
            actor="A. Nau",
            at=AT,
        ),
    ]


def _strip_final_lf(path: Path) -> bytes:
    raw = path.read_bytes()
    assert raw.endswith(b"\n")
    path.write_bytes(raw.removesuffix(b"\n"))
    return path.read_bytes()


@pytest.mark.parametrize("idx", range(6))
def test_full_json_without_lf_refuses_every_write(jpath: Path, idx: int) -> None:
    pj.init_journal(jpath)
    pj.register_record(jpath, "rec-01")
    stripped = _strip_final_lf(jpath)
    # Lesen akzeptiert den Bestand weiterhin (Digest gültig) ...
    assert len(pj.read_events(jpath)) == 2
    assert pj.check_journal(jpath).chain_ok
    # ... aber kein Schreibweg verändert ihn oder meldet Erfolg.
    with pytest.raises(ChainError):
        _write_attempts(jpath)[idx]()
    assert jpath.read_bytes() == stripped


def test_partial_line_without_lf_refuses_every_write(jpath: Path) -> None:
    pj.init_journal(jpath)
    raw = jpath.read_bytes()
    assert raw.endswith(b"\n")
    partial = raw + b'{"seq": 2, "halb'
    jpath.write_bytes(partial)
    for attempt in _write_attempts(jpath):
        with pytest.raises(VerificationError):
            attempt()
    assert jpath.read_bytes() == partial


def test_normal_file_with_lf_accepts_writes(jpath: Path) -> None:
    pj.init_journal(jpath)
    assert jpath.read_bytes().endswith(b"\n")
    res = pj.register_record(jpath, "rec-01")
    assert res.appended
    assert jpath.read_bytes().endswith(b"\n")
    pj.verify_journal(jpath)
