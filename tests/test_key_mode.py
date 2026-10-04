"""Schlüssel und Modus (Abnahme).

Fehlende/unbrauchbare Konfiguration wird getrennt von Digestabweichungen
diagnostiziert; es gibt keinen Fallback und kein Ausprobieren von Modi.
Eine HMAC-Digestabweichung bedeutet möglicher falscher Schlüssel oder
veränderte Bytes — keine festgestellte Manipulationsursache.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

import provenance_journal as pj
from provenance_journal.errors import ConfigError, DigestMismatch, VerificationError

from .conftest import H1, full_journal


@pytest.fixture
def hmac_journal(jpath: Path, keyfile: Path) -> tuple[Path, Path]:
    full_journal(jpath, integrity="hmac", key=keyfile)
    return jpath, keyfile


def test_hmac_roundtrip_with_keyfile(hmac_journal: tuple[Path, Path]) -> None:
    path, key = hmac_journal
    events = pj.read_events(path, integrity="hmac", key=key)
    assert len(events) == 6
    report = pj.check_journal(path, integrity="hmac", key=key)
    assert report.chain_ok
    assert all(e.outcome == "valid" for e in report.events)


def test_env_key_is_used(jpath: Path, keyfile: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROVJOURNAL_KEY", str(keyfile))
    full_journal(jpath, integrity="hmac")
    assert len(pj.read_events(jpath, integrity="hmac")) == 6


def test_missing_key_is_config_error_not_verification_error(
    hmac_journal: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    path, _ = hmac_journal
    monkeypatch.delenv("PROVJOURNAL_KEY", raising=False)
    with pytest.raises(ConfigError, match="nicht verifiziert"):
        pj.read_events(path, integrity="hmac")
    with pytest.raises(ConfigError, match="nicht verifiziert"):
        pj.read_events(path)  # Modus aus Konfiguration, Schlüssel fehlt


def test_short_key_rejected(jdir: Path, tmp_path: Path) -> None:
    kurz = tmp_path / "kurz.key"
    kurz.write_bytes(b"zu-kurz")
    with pytest.raises(ConfigError, match="zu kurz"):
        pj.init_journal(jdir / "journal.jsonl", integrity="hmac", key=kurz)


def test_key_inside_data_root_rejected(jdir: Path) -> None:
    innen = jdir / "journal.key"
    innen.write_bytes(b"schluessel-der-in-der-datenwurzel-liegt-x")
    with pytest.raises(ConfigError, match="Datenwurzel"):
        pj.init_journal(jdir / "journal.jsonl", integrity="hmac", key=innen)


def test_key_is_directory_rejected(jdir: Path, tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        pj.init_journal(jdir / "journal.jsonl", integrity="hmac", key=tmp_path)


def test_unreadable_key_is_config_error(jdir: Path, tmp_path: Path) -> None:
    geheim = tmp_path / "geheim.key"
    geheim.write_bytes(b"geheimer-schluessel-mit-laenge-01")
    if os.geteuid() == 0:
        pytest.skip("root umgeht Dateirechte; Fall nicht prüfbar")
    geheim.chmod(0o000)
    try:
        with pytest.raises(ConfigError, match="nicht verifiziert"):
            pj.init_journal(jdir / "journal.jsonl", integrity="hmac", key=geheim)
    finally:
        geheim.chmod(0o600)


def test_wrong_key_is_digest_mismatch(hmac_journal: tuple[Path, Path], tmp_path: Path) -> None:
    path, _ = hmac_journal
    falsch = tmp_path / "falsch.key"
    falsch.write_bytes(b"vorausgesetzt-falscher-schluessel-01")
    with pytest.raises(DigestMismatch) as info:
        pj.read_events(path, integrity="hmac", key=falsch)
    assert "möglicher falscher Schlüssel oder veränderte Daten" in str(info.value)
    assert "Manipulation" not in str(info.value)


def test_no_fallback_from_hmac_to_sha256(hmac_journal: tuple[Path, Path]) -> None:
    path, _ = hmac_journal
    # Widerspruch zur Konfiguration ist ein Konfigurationsfehler ...
    with pytest.raises(ConfigError, match="widerspricht"):
        pj.read_events(path, integrity="sha256")
    # ... und ohne Konfiguration ist der fremde Modus eine
    # Digestabweichung — niemals ein stiller Erfolg.
    (path.parent / (path.name + ".config.json")).unlink()
    with pytest.raises(VerificationError):
        pj.read_events(path, integrity="sha256")


def test_explicit_mode_required_without_config(jpath: Path) -> None:
    full_journal(jpath)
    (jpath.parent / (jpath.name + ".config.json")).unlink()
    with pytest.raises(ConfigError, match="explizite Moduswahl"):
        pj.read_events(jpath)
    assert len(pj.read_events(jpath, integrity="sha256")) == 6


def test_mode_conflict_rejected(jpath: Path, keyfile: Path) -> None:
    full_journal(jpath)  # sha256 konfiguriert
    with pytest.raises(ConfigError, match="widerspricht"):
        pj.read_events(jpath, integrity="hmac", key=keyfile)
    with pytest.raises(ConfigError, match="widerspricht"):
        pj.register_record(jpath, "rec-01", integrity="hmac", key=keyfile)


def test_unknown_mode_rejected(jdir: Path) -> None:
    with pytest.raises(ConfigError):
        pj.init_journal(jdir / "journal.jsonl", integrity="md5")


def test_legacy_env_key_has_no_effect(
    hmac_journal: tuple[Path, Path], keyfile: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, _ = hmac_journal
    monkeypatch.setenv("OHPIPE_JOURNAL_KEY", str(keyfile))
    monkeypatch.delenv("PROVJOURNAL_KEY", raising=False)
    with pytest.raises(ConfigError):
        pj.read_events(path, integrity="hmac")


def test_raw_key_bytes_accepted(jpath: Path) -> None:
    full_journal(jpath, integrity="hmac", key=b"direkter-schluessel-0123456789")
    events = pj.read_events(
        jpath, integrity="hmac", key=b"direkter-schluessel-0123456789"
    )
    assert len(events) == 6


def test_sha256_journal_ignores_env_key(
    jpath: Path, keyfile: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PROVJOURNAL_KEY", str(keyfile))
    full_journal(jpath)
    assert len(pj.read_events(jpath)) == 6
