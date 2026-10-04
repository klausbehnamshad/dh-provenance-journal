"""CLI-Schutzproben als Subprozess (Abnahme 5–7).

Manipulierte Kette, ungültige Basisnutzlast, F1–F5-Stellen, Schlüssel- und
Modusfälle, Symlinks, FIFO/Verzeichnis, unlesbare Eingaben, fehlerhafte
Parameterdatei und Steuerzeichen — keine Hänger, keine falsche
Erfolgsausgabe, unveränderte Journalbytes bei Abweisung. Altbestand mit
Intent und Fachereignissen bleibt lesbar und unverändert.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest

from .test_cli_e2e import AT, run_cli


@pytest.fixture
def shop(tmp_path: Path) -> Path:
    work = tmp_path / "laden"
    work.mkdir()
    (work / "quelle.txt").write_bytes(b"Quelle\n")
    (work / "ergebnis.txt").write_bytes(b"Ergebnis\n")
    assert run_cli(work, "--journal", "journal.jsonl", "init").returncode == 0
    assert run_cli(work, "--journal", "journal.jsonl", "register",
                   "--record", "rec-01").returncode == 0
    return work


def cli(work: Path, *argv: str) -> subprocess.CompletedProcess:
    return run_cli(work, "--journal", "journal.jsonl", *argv)


def test_tampered_chain_verify_history_check_refuse(shop: Path) -> None:
    before = (shop / "journal.jsonl").read_bytes()
    lines = before.split(b"\n")
    idx = lines[1].index(b"rec-01")
    lines[1] = lines[1][:idx] + b"X" + lines[1][idx + 1:]
    (shop / "journal.jsonl").write_bytes(b"\n".join(lines))
    tampered = (shop / "journal.jsonl").read_bytes()
    assert cli(shop, "verify").returncode == 1
    assert cli(shop, "history").returncode == 1
    assert cli(shop, "check-artifact", "--record", "rec-01", "--artifact", "e",
               "--file", "quelle.txt").returncode == 1
    assert cli(shop, "register", "--record", "rec-neu").returncode == 1
    assert (shop / "journal.jsonl").read_bytes() == tampered


def test_no_trailing_lf_refuses_append_but_reads(shop: Path) -> None:
    raw = (shop / "journal.jsonl").read_bytes()
    (shop / "journal.jsonl").write_bytes(raw.removesuffix(b"\n"))
    stripped = (shop / "journal.jsonl").read_bytes()
    assert cli(shop, "verify").returncode == 0
    assert cli(shop, "register", "--record", "rec-neu").returncode == 1
    assert (shop / "journal.jsonl").read_bytes() == stripped


def test_invalid_utf8_refuses(shop: Path) -> None:
    (shop / "journal.jsonl").write_bytes(b"\xff\n")
    assert cli(shop, "verify").returncode == 1
    assert cli(shop, "register", "--record", "rec-neu").returncode == 1
    assert (shop / "journal.jsonl").read_bytes() == b"\xff\n"


def test_symlinked_journal_and_lock_refuse(shop: Path) -> None:
    real = shop / "journal.jsonl"
    before = real.read_bytes()
    link = shop / "alias.jsonl"
    os.symlink(real, link)
    # Mit expliziter Moduswahl greift der Pfadbefund (ohne sie erst die
    # Moduswahl — beides verweigert, nichts wird angelegt).
    assert run_cli(shop, "--journal", "alias.jsonl", "--integrity", "sha256",
                   "verify").returncode == 1
    assert run_cli(shop, "--journal", "alias.jsonl", "--integrity", "sha256",
                   "register", "--record", "x").returncode == 1
    assert real.read_bytes() == before
    (shop / "journal.jsonl.lock").unlink()
    os.symlink(shop / "fremd.lock", shop / "journal.jsonl.lock")
    assert cli(shop, "register", "--record", "x").returncode == 1
    assert real.read_bytes() == before
    # Auch Leser legen keine neue Lockdatei an.
    assert run_cli(shop, "--journal", "neu.jsonl", "--integrity", "sha256",
                   "verify").returncode == 1
    assert not (shop / "neu.jsonl.lock").exists()


def test_fifo_dir_unreadable_inputs_refuse(shop: Path) -> None:
    fifo = shop / "rohr.txt"
    os.mkfifo(fifo)
    assert cli(shop, "ingest", "--record", "rec-01", "--file", "rohr.txt",
               "--media-type", "text/plain").returncode == 1
    (shop / "ordner.txt").mkdir()
    assert cli(shop, "ingest", "--record", "rec-01", "--file", "ordner.txt",
               "--media-type", "text/plain").returncode == 1
    geheim = shop / "geheim.txt"
    geheim.write_bytes(b"x")
    if os.geteuid() != 0:
        geheim.chmod(0o000)
        try:
            assert cli(shop, "ingest", "--record", "rec-01", "--file", "geheim.txt",
                       "--media-type", "text/plain").returncode == 1
        finally:
            geheim.chmod(0o600)
    assert cli(shop, "ingest", "--record", "rec-01", "--file", "fehlt.txt",
               "--media-type", "text/plain").returncode == 1


@pytest.mark.parametrize("content", ['[1, 2]', 'null', '"text"', '{ungültig'])
def test_bad_params_file_rejected_before_append(shop: Path, content: str) -> None:
    (shop / "params.json").write_text(content, encoding="utf-8")
    before = (shop / "journal.jsonl").read_bytes()
    proc = cli(shop, "receipt", "--record", "rec-01", "--artifact", "e",
               "--output", "ergebnis.txt", "--input", "q=quelle.txt",
               "--step", "s", "--code-version", "v", "--params-file", "params.json")
    assert proc.returncode == 2
    assert (shop / "journal.jsonl").read_bytes() == before


def test_control_chars_stay_on_their_line(shop: Path) -> None:
    proc = cli(shop, "decide", "--record", "rec-01", "--artifact", "e.txt",
               "--file", "ergebnis.txt", "--verdict", "ACCEPT",
               "--reference", "PI-1", "--actor", "Bös\nartig", "--at", AT)
    assert proc.returncode == 0, proc.stderr
    history = cli(shop, "history")
    assert history.returncode == 0
    assert "Bös\\nartig" in history.stdout
    for line in history.stdout.split("\n"):
        assert "artig" not in line or "Bös" in line


def test_missing_journal_gives_finding_without_creating(shop: Path) -> None:
    assert run_cli(shop, "--journal", "leer.jsonl", "verify").returncode == 1
    assert run_cli(shop, "--journal", "leer.jsonl", "history").returncode == 1
    assert run_cli(shop, "--journal", "leer.jsonl", "check-artifact",
                   "--record", "r", "--artifact", "a", "--file", "quelle.txt").returncode == 1
    assert not (shop / "leer.jsonl").exists()
    assert not (shop / "leer.jsonl.lock").exists()
    assert not (shop / "leer.jsonl.config.json").exists()


def test_legacy_with_intent_stays_readable_and_unchanged(tmp_path: Path) -> None:
    work = tmp_path / "alt"
    work.mkdir()
    genesis = "0" * 64
    intent = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    specs = [
        ("workspace.initialised", None,
         {"profile": "research-basic-v1", "root": ".", "version": "v0.1"}),
        ("record.registered", "rec-a",
         {"record_id": "rec-a", "profile": "research-basic-v1"}),
        ("p4c.prepared", "rec-a", {"v": 1}),
        ("decision.recorded", "rec-a",
         {"artifact": "a.txt", "subject_sha256": "a" * 64, "verdict": "UNDO",
          "reference": "PI-0", "actor": "A. Nau", "at": AT}),
    ]
    prev = genesis
    with open(work / "alt.jsonl", "w", encoding="utf-8") as fh:
        for seq, (kind, record_id, payload) in enumerate(specs, start=1):
            body = {"seq": seq, "at": AT, "kind": kind, "record_id": record_id,
                    "payload": payload, "prev": prev}
            wire = dict(body)
            if seq == 1:
                body["operation_intent_sha256"] = intent
                wire["operation_intent_sha256"] = intent
            blob = json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
            prev = hashlib.sha256(blob.encode()).hexdigest()
            fh.write(json.dumps({**wire, "digest": prev}, sort_keys=True) + "\n")
    before = (work / "alt.jsonl").read_bytes()
    verify = run_cli(work, "--journal", "alt.jsonl", "--integrity", "sha256",
                     "verify", "--json")
    assert verify.returncode == 0, verify.stderr
    payload = json.loads(verify.stdout)
    assert payload["chain"] == {"ok": True, "events": 4}
    assert payload["summary"] == {"valid": 2, "invalid": 0, "unchecked": 2}
    history = run_cli(work, "--journal", "alt.jsonl", "--integrity", "sha256", "history")
    assert history.returncode == 0
    refused = run_cli(work, "--journal", "alt.jsonl", "--integrity", "sha256",
                      "register", "--record", "neu")
    assert refused.returncode == 1
    assert (work / "alt.jsonl").read_bytes() == before


def test_key_and_mode_cases(tmp_path: Path) -> None:
    work = tmp_path / "hmac"
    work.mkdir()
    key = tmp_path / "gut.key"
    key.write_bytes(b"schluessel-02-mindestlaenge-xx")
    base = ["--journal", "journal.jsonl", "--integrity", "hmac", "--key-file", str(key)]
    assert run_cli(work, *base, "init").returncode == 0
    # Falscher Schlüssel: Exit 1 mit vorsichtiger Diagnose.
    falsch = tmp_path / "falsch.key"
    falsch.write_bytes(b"falscher-schluessel-02-xxxxxx")
    wrong = run_cli(work, "--journal", "journal.jsonl", "--integrity", "hmac",
                    "--key-file", str(falsch), "verify")
    assert wrong.returncode == 1
    assert "möglicher falscher Schlüssel oder veränderte Daten" in wrong.stderr
    # Fehlender Schlüssel: Exit 2. Kurzer/falsch gelegener Schlüssel: Exit 2.
    assert run_cli(work, "--journal", "journal.jsonl", "--integrity", "hmac",
                    "verify").returncode == 2
    kurz = tmp_path / "kurz.key"
    kurz.write_bytes(b"kurz")
    assert run_cli(work, *base[:-1], str(kurz), "verify").returncode == 2
    innen = work / "innen.key"
    innen.write_bytes(b"schluessel-in-der-datenwurzel-02")
    assert run_cli(work, "--journal", "journal.jsonl", "--integrity", "hmac",
                    "--key-file", str(innen), "verify").returncode == 2
    # Moduswiderspruch: Exit 2.
    assert run_cli(work, "--journal", "journal.jsonl", "--integrity", "sha256",
                    "verify").returncode == 2
