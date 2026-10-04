"""R5: Moduskonfiguration wird sicher gelesen — ohne Hänger, ohne Folgen.

FIFO, Verzeichnis, intakter wie gebrochener Link und unlesbare
Konfiguration sind Konfigurationsfehler (Exit 2); vorhandene Journal-
und Konfigurationsbytes bleiben unverändert. Fehlende Konfiguration
bleibt der vorhandene Fall „explizite Moduswahl nötig“. Schreibbefehle
prüfen denselben Vertrag vor jedem Anhang. Alle Proben laufen als
Subprozess mit Timeout.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from .test_cli_e2e import SRC

import sys as _sys


def _begrenzt(arbeit: Path, argv: list, timeout: int = 10) -> subprocess.CompletedProcess:
    """CLI als Subprozess mit kurzem Timeout — ein Hänger scheitert hier."""
    import os as _os

    env = dict(_os.environ)
    env["PYTHONPATH"] = str(SRC)
    try:
        return subprocess.run(
            [_sys.executable, "-m", "provenance_journal", *argv],
            cwd=arbeit, env=env, capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:  # pragma: no cover
        raise AssertionError(f"CLI hängt bei {argv}") from exc


def _cli(arbeit: Path, *argv: str):
    return _begrenzt(arbeit, ["--journal", "j.jsonl", *argv])


def _laden(arbeit: Path) -> bytes:
    assert _cli(arbeit, "init").returncode == 0
    assert _cli(arbeit, "register", "--record", "r1").returncode == 0
    return (arbeit / "j.jsonl").read_bytes()


def _config_ersetzen(arbeit: Path, bauart: str) -> None:
    cfg = arbeit / "j.jsonl.config.json"
    cfg.unlink()
    if bauart == "fifo":
        os.mkfifo(cfg)
    elif bauart == "verzeichnis":
        cfg.mkdir()
    elif bauart == "intakter-link":
        ziel = arbeit / "echt.json"
        ziel.write_text('{"integrity": "sha256"}\n', encoding="utf-8")
        os.symlink(ziel, cfg)
    elif bauart == "gebrochener-link":
        os.symlink(arbeit / "fehlt.json", cfg)
    else:  # pragma: no cover
        raise AssertionError(bauart)


@pytest.mark.parametrize("bauart", ["fifo", "verzeichnis", "intakter-link", "gebrochener-link"])
@pytest.mark.parametrize("modus", [[], ["--integrity", "sha256"]])
def test_unbrauchbare_konfiguration_ergibt_exit_2(tmp_path: Path, bauart: str, modus: list) -> None:
    arbeit = tmp_path / f"konfig-{bauart}-{len(modus)}"
    arbeit.mkdir()
    stand = _laden(arbeit)
    _config_ersetzen(arbeit, bauart)
    for befehl in (["verify"], ["history"]):
        proc = _begrenzt(arbeit, ["--journal", "j.jsonl", *modus, *befehl])
        assert proc.returncode == 2, (bauart, modus, befehl)
    assert (arbeit / "j.jsonl").read_bytes() == stand


def test_unlesbare_konfiguration_ergibt_exit_2(tmp_path: Path) -> None:
    if os.geteuid() == 0:  # pragma: no cover
        pytest.skip("root umgeht Dateirechte")
    arbeit = tmp_path / "konfig-rechte"
    arbeit.mkdir()
    stand = _laden(arbeit)
    cfg = arbeit / "j.jsonl.config.json"
    cfg.chmod(0o000)
    try:
        assert _cli(arbeit, "verify").returncode == 2
    finally:
        cfg.chmod(0o600)
    assert (arbeit / "j.jsonl").read_bytes() == stand


def test_fehlende_und_gueltige_konfiguration(tmp_path: Path) -> None:
    arbeit = tmp_path / "konfig-ok"
    arbeit.mkdir()
    (arbeit / "j.jsonl").write_bytes(b"")
    assert _cli(arbeit, "verify").returncode == 1  # keine Moduswahl
    assert _cli(arbeit, "--integrity", "sha256", "verify").returncode == 1
    assert _laden(arbeit)
    assert _cli(arbeit, "verify").returncode == 0
    assert _cli(arbeit, "--integrity", "sha256", "verify").returncode == 0


def test_schreibbefehle_weisen_fifo_konfiguration_vor_anhang_ab(tmp_path: Path) -> None:
    arbeit = tmp_path / "konfig-schreiben"
    arbeit.mkdir()
    stand = _laden(arbeit)
    _config_ersetzen(arbeit, "fifo")
    assert _begrenzt(arbeit, ["--journal", "j.jsonl", "--integrity", "sha256",
                             "init"]).returncode == 2
    assert _begrenzt(arbeit, ["--journal", "j.jsonl", "register",
                             "--record", "neu"]).returncode == 2
    assert (arbeit / "j.jsonl").read_bytes() == stand
