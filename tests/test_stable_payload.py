"""Stabile Nutzlast vor Prüfung und Schreiben (F3-Regression).

Echte Dateisperre verzögert einen Receipt-Anhang; nach erfolgter normaler
Eingabeprüfung verändert der Aufrufer seine Wörterbücher (`inputs` geleert,
verschachtelte `params` verändert). Das neue Ereignis enthält die gültige
kopierte Ausgangsnutzlast — niemals wird ein ungültiger oder
digestinkonsistenter Eintrag gespeichert. Die Tiefkopie der Rückgabewerte
bleibt daneben wirksam.
"""

from __future__ import annotations

import fcntl
import threading
from pathlib import Path

import pytest

import provenance_journal as pj

from .conftest import H1, H2


def test_mutated_caller_dicts_do_not_reach_the_journal(
    jpath: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pj.init_journal(jpath)
    pj.register_record(jpath, "rec-01")
    inputs = {"quelle": H1}
    params = {"stufe": {"schwelle": 3}}
    validated = threading.Event()
    original = pj.profile.validate_new

    def observing(*args, **kwargs):
        original(*args, **kwargs)
        validated.set()

    monkeypatch.setattr(pj.profile, "validate_new", observing)
    outcome: dict = {}

    def writer():
        try:
            result = pj.record_receipt(
                jpath,
                "rec-01",
                artifact="a.txt",
                output_sha256=H2,
                inputs=inputs,
                code_version="v0.1",
                step="ableitung",
                params=params,
            )
            outcome.update(returned=True, appended=result.appended, event=result.event)
        except Exception as exc:  # noqa: BLE001
            outcome.update(exception=type(exc).__name__)

    with open(str(jpath) + ".lock", "rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        thread = threading.Thread(target=writer)
        thread.start()
        assert validated.wait(5), "Validierung wurde nicht beobachtet"
        inputs.clear()
        params["stufe"]["schwelle"] = 999
        params["neu"] = "eingeschmuggelt"
        fcntl.flock(lock, fcntl.LOCK_UN)
    thread.join(5)
    assert not thread.is_alive()
    assert outcome.get("returned") is True
    stored = outcome["event"].payload
    assert stored["inputs"] == {"quelle": H1}
    assert stored["params"] == {"stufe": {"schwelle": 3}}
    events = pj.verify_journal(jpath)
    assert events[-1].payload == stored
    report = pj.check_journal(jpath)
    assert report.chain_ok
    assert all(e.outcome == "valid" for e in report.events)
