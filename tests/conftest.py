"""Gemeinsame Helfer für die Auftrag-01-Abnahmen (öffentliche Bibliothek)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import provenance_journal as pj

H1 = "a" * 64
H2 = "b" * 64
H3 = "c" * 64
H4 = "d" * 64

AT = "2026-10-02T10:00:00+00:00"


def forge_journal(path: Path, specs: list) -> None:
    """Schreibt einen korrekt verketteten synthetischen Bestand.

    ``specs``: Folge von ``(kind, record_id, payload)``. Nur für
    Regressionstests mit gezielt ungültigen oder speziellen Ereignissen.
    """
    prev = "0" * 64
    with open(path, "w", encoding="utf-8") as fh:
        for seq, (kind, record_id, payload) in enumerate(specs, start=1):
            body = {
                "seq": seq, "at": AT, "kind": kind, "record_id": record_id,
                "payload": payload, "prev": prev,
            }
            blob = json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
            prev = hashlib.sha256(blob.encode()).hexdigest()
            fh.write(json.dumps({**body, "digest": prev}, sort_keys=True) + "\n")


@pytest.fixture
def jdir(tmp_path: Path) -> Path:
    d = tmp_path / "daten"
    d.mkdir()
    return d


@pytest.fixture
def jpath(jdir: Path) -> Path:
    return jdir / "journal.jsonl"


@pytest.fixture
def keyfile(tmp_path: Path, jdir: Path) -> Path:
    """Schlüsseldatei außerhalb der Datenwurzel."""
    key = tmp_path / "journal.key"
    key.write_bytes(b"referenz-schluessel-auftrag-01")
    assert jdir.resolve() not in key.resolve().parents
    return key


def full_journal(path: Path, **kw) -> list:
    """Voller Ablauf über alle sechs Schreibfunktionen. Gibt Ereignisse zurück."""
    out = []
    out.append(pj.init_journal(path, **kw))
    out.append(pj.register_record(path, "rec-01", **kw))
    out.append(
        pj.ingest_source(
            path,
            "rec-01",
            sha256=H1,
            media_type="text/plain",
            filename="quelle.txt",
            num_bytes=18,
            **kw,
        )
    )
    out.append(pj.produce_artifact(path, "rec-01", artifact="auswertung.txt", sha256=H2, **kw))
    out.append(
        pj.record_receipt(
            path,
            "rec-01",
            artifact="auswertung.txt",
            output_sha256=H2,
            inputs={"quelle": H1},
            code_version="v0.1",
            step="ableitung",
            params={"schwelle": 3},
            **kw,
        )
    )
    out.append(
        pj.record_decision(
            path,
            "rec-01",
            artifact="auswertung.txt",
            subject_sha256=H2,
            verdict="ACCEPT",
            reference="PI-1",
            actor="M. Müller",
            at=AT,
            note="geprüft",
            **kw,
        )
    )
    assert all(r.appended for r in out)
    return [r.event for r in out]
