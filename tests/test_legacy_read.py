"""Lesender Altbestand (Abnahme).

Originalbytes bleiben unverändert; Spezialereignisse werden mit tatsächlich
angebotener Prüfreichweite erhalten: Kettenprüfung (Seq, prev, Digest)
gegen Fachprüfung (Basisprofil) getrennt ausgewiesen. Schreiben in
Altbestände ist abgewiesen — neue Einträge entstehen nur im eigenen
Basisprofil.
"""

from __future__ import annotations

import hashlib
import hmac as hmac_mod
import json
from pathlib import Path

import pytest

import provenance_journal as pj
from provenance_journal.errors import ConfigError, ProfileError, VerificationError

GENESIS = "0" * 64
LEGACY_KEY = b"altbestand-schluessel-01-23456789"
INTENT = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def _legacy_chain(path: Path, key: bytes | None) -> None:
    """Handverketteter Altbestand mit Spezialereignissen (getrennte Berechnung)."""
    specs = [
        # Fremdes Init-Profil, record_id null, mit Intent-Feld.
        ("workspace.initialised", None, {"profil": "ohpipe-voll", "wurzel": "/daten"},
         INTENT),
        # Gültige Basis-Registrierung.
        ("record.registered", "rec-alt",
         {"record_id": "rec-alt", "profile": "research-basic-v1"}, None),
        # Unbekannte Ereignisart (P4-Fachvertrag).
        ("p4c.prepared", "rec-alt",
         {"v": 1, "phase": "review", "operation": "op", "actor": "a",
          "actor_state": "s", "at": "2026-09-01T10:00:00+00:00", "basis": "b",
          "registry_before": "x", "registry_after": "y", "refs": [],
          "marker": "m"}, None),
        # UNDO-Entscheidung: bekannte Art, Lesefall-Verdikt.
        ("decision.recorded", "rec-alt",
         {"artifact": "a.txt", "subject_sha256": "a" * 64, "verdict": "UNDO",
          "reference": "PI-0", "actor": "A. Nau", "at": "2026-09-02T10:00:00+00:00"},
         None),
        # Modell-Beleg: fremde kind-Variante mit Zusatzfeldern.
        ("receipt.recorded", "rec-alt",
         {"artifact": "m.txt", "output_sha256": "b" * 64, "inputs": {"t": "c" * 64},
          "code_version": "v9", "kind": "model", "prompt_sha256": "d" * 64,
          "finish_reason": "stop"}, None),
        # Gültige Basis-Entscheidung mit null-Intent.
        ("decision.recorded", "rec-alt",
         {"artifact": "a.txt", "subject_sha256": "a" * 64, "verdict": "ACCEPT",
          "reference": "PI-1", "actor": "A. Nau", "at": "2026-09-03T10:00:00+00:00"},
         None),
    ]
    prev = GENESIS
    with open(path, "w", encoding="utf-8") as fh:
        for seq, (kind, record_id, payload, intent) in enumerate(specs, start=1):
            body = {
                "seq": seq,
                "at": "2026-09-01T00:00:00+00:00",
                "kind": kind,
                "record_id": record_id,
                "payload": payload,
                "prev": prev,
            }
            wire = dict(body)
            if intent is not None:
                body["operation_intent_sha256"] = intent
                wire["operation_intent_sha256"] = intent
            blob = json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
            raw = blob.encode("utf-8")
            digest = (
                hashlib.sha256(raw).hexdigest()
                if key is None
                else hmac_mod.new(key, raw, "sha256").hexdigest()
            )
            fh.write(json.dumps({**wire, "digest": digest}, ensure_ascii=False, sort_keys=True) + "\n")
            prev = digest


def test_keyed_legacy_chain_verifies_intent_preserved(jdir: Path) -> None:
    path = jdir / "alt.jsonl"
    _legacy_chain(path, LEGACY_KEY)
    before = path.read_bytes()
    events = pj.read_events(path, integrity="hmac", key=LEGACY_KEY)
    assert len(events) == 6
    assert events[0].operation_intent_sha256 == INTENT
    assert events[1].operation_intent_sha256 is None
    assert path.read_bytes() == before


def test_unkeyed_legacy_chain_verifies(jdir: Path) -> None:
    path = jdir / "alt.jsonl"
    _legacy_chain(path, None)
    events = pj.read_events(path, integrity="sha256")
    assert len(events) == 6


def test_check_separates_chain_from_profile(jdir: Path) -> None:
    path = jdir / "alt.jsonl"
    _legacy_chain(path, LEGACY_KEY)
    before = path.read_bytes()
    report = pj.check_journal(path, integrity="hmac", key=LEGACY_KEY)
    assert report.chain_ok
    by_seq = {e.seq: e for e in report.events}
    assert by_seq[1].outcome == "invalid"  # fremdes Init-Profil
    assert by_seq[2].outcome == "valid"
    assert by_seq[3].outcome == "unchecked"  # unbekannte Art
    assert by_seq[4].outcome == "unchecked"  # UNDO
    assert by_seq[5].outcome == "unchecked"  # kind=model
    assert by_seq[6].outcome == "valid"
    assert path.read_bytes() == before


def test_legacy_stock_is_read_only(jdir: Path) -> None:
    path = jdir / "alt.jsonl"
    _legacy_chain(path, LEGACY_KEY)
    before = path.read_bytes()
    with pytest.raises((ProfileError, VerificationError)):
        pj.register_record(path, "rec-neu", integrity="hmac", key=LEGACY_KEY)
    with pytest.raises((ProfileError, VerificationError)):
        pj.record_decision(
            path, "rec-alt", artifact="a.txt", subject_sha256="a" * 64,
            verdict="ACCEPT", reference="PI-2", actor="A. Nau",
            at="2026-09-04T10:00:00+00:00", integrity="hmac", key=LEGACY_KEY,
        )
    assert path.read_bytes() == before


def test_legacy_without_config_needs_explicit_mode(jdir: Path) -> None:
    path = jdir / "alt.jsonl"
    _legacy_chain(path, None)
    with pytest.raises(ConfigError):
        pj.read_events(path)
