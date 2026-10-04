"""Kommandozeile `provjournal` für Fachkollegen.

Alle Schreibbefehle rufen die vorhandene öffentliche Bibliothek auf; es
gibt keine zweite Append-Implementierung. Die CLI führt keine Programme
aus: Eine Verarbeitung wird mit `receipt` erklärt. Hash und Größe stammen
aus denselben am Handle gelesenen Rohbytes; frei eingegebene Hashes gibt
es für diese Schreibbefehle nicht.

Ausgaben: Terminal kurz und verständlich; `--json` schreibt genau ein
gültiges JSON-Objekt nach stdout (abgeleitete Ansicht mit Prüfreichweite),
Diagnosen gehören nach stderr. Kettenbefund, Basisbefund und ungeprüfte
Fachsemantik stehen getrennt; keine READY- oder Freigabeaussage.

Exits: 0 = technisch erfolgreich (auch echte Registrierungsduplikate);
2 = Konfiguration fehlt/unbrauchbar, ungültige Argumente oder neue
Nutzlast; 1 = Kette/Digest oder Basisvertrag ungültig, Journal-/Datei-I/O,
unbestätigter Schreibzustand oder nicht zugeordnete `check-artifact`-Bytes.
"""

from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from pathlib import Path
from typing import Any

from . import api as _api
from ._store import now_iso
from .config import HMAC, SHA256
from .errors import (
    ConfigError,
    FileReadError,
    JournalIOError,
    PayloadRejected,
    VerificationError,
)
from .files import read_file_bytes, read_json_object
from .history import (
    ArtifactCheck,
    History,
    Snapshot,
    basis_findings,
    build_history,
    check_artifact,
    filter_history,
    load_snapshot,
)

__all__ = ["build_parser", "main"]


def q(value: Any) -> str:
    """Sichere Anzeige von Terminalwerten (JSON-Quoting)."""
    return json.dumps(value, ensure_ascii=False)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="provjournal",
        description="Eigenes DH-Provenienzjournal: schreiben, prüfen, lesen.",
    )
    parser.add_argument(
        "--journal",
        default="./journal.jsonl",
        help="Pfad der Journaldatei (Standard: ./journal.jsonl)",
    )
    parser.add_argument("--integrity", choices=(SHA256, HMAC), default=None)
    parser.add_argument("--key-file", default=None, help="Pfad der Schlüsseldatei")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="Basisprofil initialisieren")
    reg = sub.add_parser("register", help="Eigenen Record registrieren")
    reg.add_argument("--record", required=True)

    ing = sub.add_parser("ingest", help="Quelle erfassen (Hash/Größe selbst berechnet)")
    ing.add_argument("--record", required=True)
    ing.add_argument("--file", required=True)
    ing.add_argument("--media-type", required=True)

    art = sub.add_parser("artifact", help="Ergebnisfassung registrieren")
    art.add_argument("--record", required=True)
    art.add_argument("--artifact", required=True)
    art.add_argument("--file", required=True)

    rec = sub.add_parser("receipt", help="Erklärten Verarbeitungslauf dokumentieren")
    rec.add_argument("--record", required=True)
    rec.add_argument("--artifact", required=True)
    rec.add_argument("--output", required=True)
    rec.add_argument("--input", action="append", default=[], metavar="ROLE=PATH")
    rec.add_argument("--step", required=True)
    rec.add_argument("--code-version", required=True)
    rec.add_argument("--params-file", default=None)

    dec = sub.add_parser("decide", help="Entscheidung über konkrete Bytes festhalten")
    dec.add_argument("--record", required=True)
    dec.add_argument("--artifact", required=True)
    dec.add_argument("--file", required=True)
    dec.add_argument("--verdict", required=True, choices=("ACCEPT", "REJECT", "WITHDRAW"))
    dec.add_argument("--reference", required=True)
    dec.add_argument("--actor", required=True)
    dec.add_argument("--at", default=None, help="Zeitzonenbehafteter Zeitpunkt (Standard: jetzt, UTC)")
    dec.add_argument("--note", default=None)

    ver = sub.add_parser("verify", help="Ketten- und Basisprüfung mit Prüfreichweite")
    ver.add_argument("--json", action="store_true")

    his = sub.add_parser("history", help="Ereignisse und Fassungen in Sequenzfolge")
    his.add_argument("--record", default=None)
    his.add_argument("--artifact", default=None)
    his.add_argument("--sha256", default=None)
    his.add_argument("--json", action="store_true")

    chk = sub.add_parser("check-artifact", help="Bereitgestellte Bytes zuordnen")
    chk.add_argument("--record", required=True)
    chk.add_argument("--artifact", required=True)
    chk.add_argument("--file", required=True)
    chk.add_argument("--json", action="store_true")
    return parser


def _key_arg(args: argparse.Namespace) -> Path | None:
    return Path(args.key_file) if args.key_file else None


def _parse_inputs(values: list[str]) -> dict[str, Path]:
    """ROLE=PATH, wiederholbar. Doppelte Rollen sind ein Eingabefehler."""
    roles: dict[str, Path] = {}
    for item in values:
        role, sep, path = item.partition("=")
        if not sep or not role:
            raise PayloadRejected("input", detail="erwartet ROLE=PATH")
        if role in roles:
            raise PayloadRejected("input", detail="Rolle mehrfach angegeben")
        roles[role] = Path(path)
    return roles


def _hash_inputs(roles: dict[str, Path]) -> dict[str, str]:
    return {role: read_file_bytes(path).sha256 for role, path in roles.items()}


def _snapshot(args: argparse.Namespace) -> Snapshot:
    return load_snapshot(Path(args.journal), args.integrity, _key_arg(args))


def _is_missing_or_empty(journal: Path) -> bool:
    """Fehlende oder leere reguläre Datei — sonst keine Aussage.

    Links, Verzeichnisse und Spezialdateien fallen ausdrücklich nicht
    darunter: Ihre Befunde (unsafe/Konfiguration) bleiben erhalten.
    """
    try:
        st = os.lstat(journal)
    except FileNotFoundError:
        return True
    except OSError:
        return False
    return stat.S_ISREG(st.st_mode) and st.st_size == 0


def _read_snapshot(args: argparse.Namespace) -> Snapshot | None:
    """Lesepipeline der Prüf-/Historienbefehle.

    Fehlt das Journal oder ist es leer und gibt es keine Moduswahl, ist
    das kein Konfigurationsrätsel, sondern der Befund (None): klarer
    Exit 1, nichts wird angelegt.
    """
    try:
        return _snapshot(args)
    except ConfigError:
        if _is_missing_or_empty(Path(args.journal)):
            return None
        raise


def _emit_json(obj: dict[str, Any]) -> int:
    print(json.dumps(obj, ensure_ascii=False, sort_keys=True))
    return 0


def _cmd_init(args: argparse.Namespace) -> int:
    result = _api.init_journal(
        Path(args.journal), integrity=args.integrity or SHA256, key=_key_arg(args)
    )
    if result.appended:
        print(f"initialisiert (seq {result.event.seq})")
    else:
        print(f"bereits vorhanden (seq {result.event.seq})")
    return 0


def _cmd_register(args: argparse.Namespace) -> int:
    result = _api.register_record(
        Path(args.journal), args.record, integrity=args.integrity, key=_key_arg(args)
    )
    if result.appended:
        print(f"Record {q(args.record)} registriert (seq {result.event.seq})")
    else:
        print(f"Record {q(args.record)} bereits vorhanden (seq {result.event.seq})")
    return 0


def _cmd_ingest(args: argparse.Namespace) -> int:
    measured = read_file_bytes(args.file)
    result = _api.ingest_source(
        Path(args.journal),
        args.record,
        sha256=measured.sha256,
        media_type=args.media_type,
        filename=measured.name,
        num_bytes=measured.size,
        integrity=args.integrity,
        key=_key_arg(args),
    )
    if result.appended:
        print(f"Quelle {q(measured.name)} erfasst (seq {result.event.seq})")
    else:
        print(f"Quelle {q(measured.name)} bereits vorhanden (seq {result.event.seq})")
    return 0


def _cmd_artifact(args: argparse.Namespace) -> int:
    measured = read_file_bytes(args.file)
    result = _api.produce_artifact(
        Path(args.journal),
        args.record,
        artifact=args.artifact,
        sha256=measured.sha256,
        integrity=args.integrity,
        key=_key_arg(args),
    )
    if result.appended:
        print(f"Fassung {q(args.artifact)} registriert (seq {result.event.seq})")
    else:
        print(f"Fassung {q(args.artifact)} bereits vorhanden (seq {result.event.seq})")
    return 0


def _cmd_receipt(args: argparse.Namespace) -> int:
    roles = _parse_inputs(args.input)
    if not roles:
        raise PayloadRejected("input", detail="mindestens eine ROLE=PATH angeben")
    output = read_file_bytes(args.output)
    params = read_json_object(args.params_file) if args.params_file else None
    result = _api.record_receipt(
        Path(args.journal),
        args.record,
        artifact=args.artifact,
        output_sha256=output.sha256,
        inputs=_hash_inputs(roles),
        code_version=args.code_version,
        step=args.step,
        params=params,
        integrity=args.integrity,
        key=_key_arg(args),
    )
    print(f"Laufbeleg angehängt (seq {result.event.seq})")
    return 0


def _cmd_decide(args: argparse.Namespace) -> int:
    measured = read_file_bytes(args.file)
    result = _api.record_decision(
        Path(args.journal),
        args.record,
        artifact=args.artifact,
        subject_sha256=measured.sha256,
        verdict=args.verdict,
        reference=args.reference,
        actor=args.actor,
        at=args.at or now_iso(),
        note=args.note,
        integrity=args.integrity,
        key=_key_arg(args),
    )
    print(f"Entscheidung {q(args.verdict)} angehängt (seq {result.event.seq})")
    return 0


def _verify_report(snapshot: Snapshot, args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    """Berichtsaufbau über dem bereits geprüften Snapshot.

    Es erfolgt keine erneute Dateilesung: Der Bericht verwendet
    ausschließlich den einmalig geladenen, verifizierten Stand.
    """
    basis = [
        {
            "seq": event.seq,
            "kind": event.kind,
            "outcome": outcome.outcome,
            "fields": list(outcome.fields),
            "detail": outcome.detail,
        }
        for event, outcome in zip(snapshot.events, snapshot.outcomes)
    ]
    invalid = sum(1 for row in basis if row["outcome"] == "invalid")
    unchecked = sum(1 for row in basis if row["outcome"] == "unchecked")
    report = {
        "command": "verify",
        "journal": str(args.journal),
        "chain": {"ok": True, "events": len(snapshot.events)},
        "basis": basis,
        "summary": {
            "valid": len(basis) - invalid - unchecked,
            "invalid": invalid,
            "unchecked": unchecked,
        },
        "scope_note": (
            "Kette geprüft; Basisnutzlasten einzeln bewertet; "
            "fachlich ungeprüfte Ereignisse sind als unchecked ausgewiesen. "
            "Keine Freigabeaussage."
        ),
    }
    return report, (1 if invalid else 0)


def _cmd_verify(args: argparse.Namespace) -> int:
    snapshot = _read_snapshot(args)
    if snapshot is None or not snapshot.events:
        print("provjournal: kein Journal oder keine Ereignisse", file=sys.stderr)
        return 1
    report, code = _verify_report(snapshot, args)
    if args.json:
        return _emit_json(report) or code
    summary = report["summary"]
    print(f"Kette: gültig ({report['chain']['events']} Ereignisse)")
    print(
        f"Basis: {summary['valid']} gültig, {summary['invalid']} ungültig, "
        f"{summary['unchecked']} fachlich ungeprüft"
    )
    for row in report["basis"]:
        if row["outcome"] == "valid":
            continue
        print(f"seq {row['seq']} {q(row['kind'])}: {row['outcome']} {q(row['fields'])}")
    return code


def _receipt_json(receipt: Any) -> dict[str, Any]:
    return {
        "seq": receipt.seq,
        "step": receipt.step,
        "code_version": receipt.code_version,
        "output_sha256": receipt.output_sha256,
        "inputs": dict(receipt.inputs),
        "params": receipt.params,
    }


def _decision_json(decision: Any) -> dict[str, Any]:
    return {
        "seq": decision.seq,
        "verdict": decision.verdict,
        "reference": decision.reference,
        "actor": decision.actor,
        "at": decision.at,
        "note": decision.note,
        "subject_sha256": decision.subject_sha256,
    }


def _history_json(history: History, args: argparse.Namespace) -> dict[str, Any]:
    return {
        "command": "history",
        "journal": str(args.journal),
        "view": "derived" if history.derived else "full",
        "filters": history.filters,
        "events": [
            {
                "seq": event.seq,
                "kind": event.kind,
                "record_id": event.record_id,
                "outcome": event.outcome,
                "fields": list(event.fields),
                "payload": event.payload,
            }
            for event in history.events
        ],
        "records": [
            {
                "record_id": record.record_id,
                "artifacts": [
                    {
                        "artifact": view.artifact,
                        "revisions": [
                            {
                                "sha256": rev.sha256,
                                "seq": rev.seq,
                                "current": view.current is not None
                                and view.current.sha256 == rev.sha256,
                                "receipts": [_receipt_json(r) for r in rev.receipts],
                                "latest_decision": (
                                    _decision_json(rev.latest_decision)
                                    if rev.latest_decision
                                    else None
                                ),
                            }
                            for rev in view.revisions
                        ],
                        "unbound_receipts": [
                            _receipt_json(r) for r in view.unbound_receipts
                        ],
                        "unbound_decisions": [
                            _decision_json(d) for d in view.unbound_decisions
                        ],
                    }
                    for view in record.artifacts
                ],
            }
            for record in history.records
        ],
        "findings": [
            {
                "seq": f.seq,
                "kind": f.kind,
                "outcome": f.outcome,
                "fields": list(f.fields),
                "detail": f.detail,
            }
            for f in history.findings
        ],
        "scope_note": (
            "Abgeleitete Ansicht aus einem verifizierten Snapshot "
            "(Filter eingeschlossen); kein eigenständig prüfbarer "
            "Originalkettenauszug. Volle Hashes zum Zuordnen."
        ),
    }


def _event_suffix(event: Any) -> str:
    """Knappe Terminalangaben zum Ereignis aus der Originalnutzlast.

    Nur vorhandene Felder erscheinen; nichts wird erfunden. Alle Werte aus
    dem Journal sind JSON-quotiert, damit Steuerzeichen keine zusätzlichen
    Zeilen oder Terminalsteuerung erzeugen.
    """
    payload = event.payload if isinstance(event.payload, dict) else {}
    if event.kind == "source.ingested" and "filename" in payload:
        return f" quelle {q(payload.get('filename'))} {q(payload.get('sha256'))}"
    if event.kind == "artifact.produced" and "artifact" in payload:
        return f" fassung {q(payload.get('artifact'))} {q(payload.get('sha256'))}"
    if event.kind == "receipt.recorded" and "artifact" in payload:
        return (
            f" beleg {q(payload.get('artifact'))} "
            f"{q(payload.get('output_sha256'))} schritt {q(payload.get('step'))}"
        )
    if event.kind == "decision.recorded" and "artifact" in payload:
        text = (
            f" entscheidung {q(payload.get('artifact'))} "
            f"{q(payload.get('verdict'))} {q(payload.get('reference'))} "
            f"{q(payload.get('actor'))}"
        )
        if "at" in payload:
            text += f" {q(payload.get('at'))}"
        if "note" in payload:
            text += f" {q(payload.get('note'))}"
        return text
    return ""


def _print_finding(finding: Any) -> None:
    print(f"  Befund seq {finding.seq} {q(finding.kind)}: {finding.outcome} {q(list(finding.fields))}")


def _cmd_history(args: argparse.Namespace) -> int:
    snapshot = _read_snapshot(args)
    if snapshot is None or not snapshot.events:
        print("provjournal: kein Journal oder keine Ereignisse", file=sys.stderr)
        return 1
    full = build_history(snapshot)
    if args.record is None and args.artifact is None and args.sha256 is None:
        history = full
    else:
        history = filter_history(
            full, record_id=args.record, artifact=args.artifact, sha256=args.sha256
        )
    code = 1 if any(f.outcome == "invalid" for f in full.findings) else 0
    if args.json:
        return _emit_json(_history_json(history, args)) or code
    if history.derived:
        print(f"abgeleitete Ansicht (Filter {q(history.filters)})")
    print("Ereignisse in Sequenzfolge:")
    for event in history.events:
        print(f"  seq {event.seq} {q(event.kind)} {q(event.record_id)}{_event_suffix(event)}")
    for record in history.records:
        print(f"{q(record.record_id)}")
        for view in record.artifacts:
            for rev in view.revisions:
                mark = "aktuelle Fassung" if view.current is not None and view.current.sha256 == rev.sha256 else "frühere Fassung"
                print(f"  {q(view.artifact)} {rev.sha256} (seq {rev.seq}, {mark})")
                for receipt in rev.receipts:
                    print(f"    Beleg seq {receipt.seq} Schritt {q(receipt.step)}")
                if rev.latest_decision is not None:
                    dec = rev.latest_decision
                    print(
                        f"    Entscheidung seq {dec.seq} {q(dec.verdict)} "
                        f"({q(dec.reference)}, {q(dec.actor)})"
                    )
            for receipt in view.unbound_receipts:
                print(
                    f"  ungebundener Beleg seq {receipt.seq} {receipt.output_sha256} "
                    f"Schritt {q(receipt.step)}"
                )
            for dec in view.unbound_decisions:
                print(
                    f"  ungebundene Entscheidung seq {dec.seq} {dec.subject_sha256} "
                    f"{q(dec.verdict)} ({q(dec.reference)}, {q(dec.actor)})"
                )
    for finding in history.findings:
        _print_finding(finding)
    return code


def _check_json(
    result: ArtifactCheck, findings: Any, args: argparse.Namespace
) -> dict[str, Any]:
    invalid = sum(1 for f in findings if f.outcome == "invalid")
    unchecked = sum(1 for f in findings if f.outcome == "unchecked")
    return {
        "command": "check-artifact",
        "journal": str(args.journal),
        "record_id": result.record_id,
        "artifact": result.artifact,
        "sha256": result.sha256,
        "registered": result.registered,
        "currency": result.currency,
        "revision_seq": result.revision_seq,
        "receipts": [_receipt_json(r) for r in result.receipts],
        "latest_decision": (
            _decision_json(result.latest_decision) if result.latest_decision else None
        ),
        "findings": [
            {
                "seq": f.seq,
                "kind": f.kind,
                "outcome": f.outcome,
                "fields": list(f.fields),
                "detail": f.detail,
            }
            for f in findings
        ],
        "basis_summary": {
            "invalid": invalid,
            "unchecked": unchecked,
        },
        "scope_note": (
            "Zuordnung nach voller Identität aus verifiziertem Snapshot. "
            "Bei ungültigen Basisereignissen ist die Fachzuordnung begrenzt; "
            "Befunde siehe findings. Keine Freigabeaussage."
        ),
    }


def _cmd_check_artifact(args: argparse.Namespace) -> int:
    measured = read_file_bytes(args.file)
    snapshot = _read_snapshot(args)
    if snapshot is None or not snapshot.events:
        print("provjournal: kein Journal oder keine Ereignisse", file=sys.stderr)
        return 1
    result = check_artifact(
        snapshot,
        record_id=args.record,
        artifact=args.artifact,
        sha256=measured.sha256,
    )
    findings = basis_findings(snapshot)
    invalid = any(f.outcome == "invalid" for f in findings)
    code = 1 if (invalid or not result.registered) else 0
    if args.json:
        return _emit_json(_check_json(result, findings, args)) or code
    print(f"Bytes: {result.sha256}")
    if not result.registered:
        print(f"{q(args.record)}/{q(args.artifact)}: nicht registriert")
    else:
        stand = "aktuelle Fassung" if result.currency == "current" else "historische Fassung"
        print(f"{q(args.record)}/{q(args.artifact)}: registriert ({stand}, seq {result.revision_seq})")
        for receipt in result.receipts:
            print(f"  Beleg seq {receipt.seq} Schritt {q(receipt.step)}")
        if result.latest_decision is not None:
            dec = result.latest_decision
            print(f"  letzte Entscheidung seq {dec.seq} {q(dec.verdict)} ({q(dec.reference)})")
        else:
            print("  keine unterstützte Entscheidung zu dieser Fassung")
    for finding in findings:
        _print_finding(finding)
    return code


def run(args: argparse.Namespace) -> int:
    if args.command == "init":
        return _cmd_init(args)
    if args.command == "register":
        return _cmd_register(args)
    if args.command == "ingest":
        return _cmd_ingest(args)
    if args.command == "artifact":
        return _cmd_artifact(args)
    if args.command == "receipt":
        return _cmd_receipt(args)
    if args.command == "decide":
        return _cmd_decide(args)
    if args.command == "verify":
        return _cmd_verify(args)
    if args.command == "history":
        return _cmd_history(args)
    if args.command == "check-artifact":
        return _cmd_check_artifact(args)
    raise AssertionError(f"unbekannter Befehl: {args.command}")


def main(argv: list[str] | None = None) -> int:
    """Einsprung für `provjournal` und `python -m provenance_journal`."""
    args = build_parser().parse_args(argv)
    try:
        return run(args)
    except ConfigError as exc:
        print(f"provjournal: Konfiguration: {exc}", file=sys.stderr)
        return 2
    except PayloadRejected as exc:
        print(f"provjournal: Eingabe abgewiesen: {exc}", file=sys.stderr)
        return 2
    except VerificationError as exc:
        print(f"provjournal: Prüfung: {exc}", file=sys.stderr)
        return 1
    except FileReadError as exc:
        print(f"provjournal: Datei: {exc} ({q(str(exc.pfad))})", file=sys.stderr)
        return 1
    except JournalIOError as exc:
        print(f"provjournal: Ein-/Ausgabe: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"provjournal: Ein-/Ausgabe: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
