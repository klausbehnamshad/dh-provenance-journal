"""Schreibschutz gegen manipulierte Kette (Abnahme).

Jeder öffentliche Schreibweg lehnt ab; die Journalbytes bleiben unverändert.
Die Manipulation geschieht an den persistierten Bytes (kein In-Memory-
Scheinangriff): Ein Zeichen in einer mittleren Zeile wird gedreht, ohne die
Hashkette nachzurechnen.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import provenance_journal as pj
from provenance_journal.errors import VerificationError

from .conftest import AT, H1, H2, full_journal


def _tamper_middle(path: Path) -> bytes:
    before = path.read_bytes()
    lines = before.split(b"\n")
    assert len([line for line in lines if line.strip()]) == 6
    # Zeichen in der dritten Zeile (source.ingested) drehen: Digest bleibt,
    # Bytes ändern sich -> DigestMismatch bei der nächsten Prüfung.
    third = lines[2]
    idx = third.index(b"quelle")
    flipped = b"X" if third[idx : idx + 1] != b"X" else b"Y"
    lines[2] = third[:idx] + flipped + third[idx + 1 :]
    path.write_bytes(b"\n".join(lines))
    assert path.read_bytes() != before
    return before


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


@pytest.mark.parametrize("idx", range(6))
def test_every_write_path_refuses_tampered_chain(jpath: Path, idx: int) -> None:
    full_journal(jpath)
    _tamper_middle(jpath)
    tampered = jpath.read_bytes()
    with pytest.raises(VerificationError):
        _write_attempts(jpath)[idx]()
    assert jpath.read_bytes() == tampered


def test_sequence_gap_refuses_and_preserves_bytes(jpath: Path) -> None:
    full_journal(jpath)
    before = jpath.read_bytes()
    lines = [line for line in before.split(b"\n") if line.strip()]
    # Zwei Zeilen vertauschen: Sequenz und Verkettung brechen gleichzeitig.
    lines[1], lines[2] = lines[2], lines[1]
    jpath.write_bytes(b"\n".join(lines) + b"\n")
    with pytest.raises(VerificationError):
        pj.register_record(jpath, "rec-neu")
    assert jpath.read_bytes() != before  # nur unsere Vertauschung, kein Anhang
    assert len([line for line in jpath.read_bytes().split(b"\n") if line.strip()]) == 6


def test_read_also_refuses_tampered_chain(jpath: Path) -> None:
    full_journal(jpath)
    _tamper_middle(jpath)
    tampered = jpath.read_bytes()
    with pytest.raises(VerificationError):
        pj.read_events(jpath)
    report = pj.check_journal(jpath)
    assert not report.chain_ok
    assert report.chain_error
    assert jpath.read_bytes() == tampered
