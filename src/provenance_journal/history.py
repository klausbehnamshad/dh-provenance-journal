"""Reine Historien- und Zuordnungsauswertung über einem verifizierten Snapshot.

Eine gemeinsame Lesepipeline (`load_snapshot`) liest und verifiziert das
Journal genau einmal; Basisbewertung, Historie, Filter, Artefaktprüfung und
Ausgabe arbeiten anschließend mit genau diesem eigenen stabilen Snapshot.
Ändert sich die Datei danach, gilt weiterhin nur der geprüfte Stand.

Zuordnung nach voller Identität (Record-ID, Artefakt-ID, vollständigem
Hash): Fassungshash aus `artifact.produced.sha256`, Belegbindung aus
`receipt.recorded.output_sha256`, Entscheidungsbindung aus
`decision.recorded.subject_sha256`. Nur gültige Basisereignisse begründen
eine positive Zuordnung; ungültige oder fachlich ungeprüfte Ereignisse
bleiben mit ihrem Befund sichtbar. Die Reihenfolge bestimmt immer `seq`,
niemals ein frei angegebener Zeitstempel. Eine spätere REJECT- oder
WITHDRAW-Entscheidung ersetzt die aktuelle Aussage einer früheren
ACCEPT-Entscheidung, ohne Geschichte zu löschen. Neue Bytes übernehmen
keine Entscheidung einer anderen Fassung — auch nicht bei gleichem Hash
in anderem Record oder unter anderem Artefaktnamen. Ein Laufbeleg
dokumentiert einen erklärten Lauf, keinen Nachweis tatsächlicher
Ausführung. Keine Abhängigkeits- oder Staleness-Berechnung.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import profile as _profile
from .config import resolve_integrity, resolve_key
from ._store import Journal
from .envelope import Event

__all__ = [
    "ArtifactCheck",
    "ArtifactView",
    "BoundDecision",
    "BoundReceipt",
    "Finding",
    "History",
    "HistoryEvent",
    "RecordView",
    "RevisionView",
    "Snapshot",
    "basis_findings",
    "build_history",
    "check_artifact",
    "filter_history",
    "load_snapshot",
    "snapshot_copy",
]


@dataclass(frozen=True)
class Snapshot:
    """Einmal gelesener, verifizierter, stabiler Bestand mit Bewertung.

    Die geprüften Daten sind eingekapselt: Jeder Zugriff auf ``events``
    oder ``outcomes`` gibt tiefe Kopien des unveränderten internen Stands
    zurück — einschließlich verschachtelter Nutzlasten (Receipt-Inputs,
    Params). Wer eine herausgegebene Kopie verändert, verändert nur diese
    Kopie: Spätere Auswertungen arbeiten weiterhin mit dem ursprünglich
    geprüften Stand und seinen ursprünglichen Bewertungen. Ein nie
    aufgezeichneter Hash wird dadurch nie registriert und übernimmt keine
    Entscheidung.
    """

    _events: tuple[Event, ...]
    _outcomes: tuple[_profile.Assessment, ...]

    @property
    def events(self) -> tuple[Event, ...]:
        """Tiefe Kopie der geprüften Ereignisse (kein lebendiger Bestand)."""
        return copy.deepcopy(self._events)

    @property
    def outcomes(self) -> tuple[_profile.Assessment, ...]:
        """Tiefe Kopie der zugehörigen Basisbewertungen."""
        return copy.deepcopy(self._outcomes)


def load_snapshot(
    journal_path: Path | str, integrity: str | None, key: Any = None
) -> Snapshot:
    """Liest und verifiziert das Journal genau einmal.

    Verdrahtet den Lockpfadschutz für Leser, ohne Lockdateien anzulegen.
    Wirft bei Ketten-/Konfigurations-/I-O-Fehlern; leeres/pristines Journal
    ergibt einen leeren Snapshot (die CLI entscheidet über den Befund).
    """
    path = Path(journal_path)
    mode = resolve_integrity(path, integrity)
    journal = Journal(path, resolve_key(mode, path, key))
    journal.pruefe_lockpfad()
    events = journal.verify()
    assessed = [_profile.assess(event) for event in events]
    return Snapshot(_events=tuple(events), _outcomes=tuple(assessed))


@dataclass(frozen=True)
class BoundReceipt:
    seq: int
    step: str
    code_version: str
    output_sha256: str
    inputs: dict[str, str]
    params: dict[str, Any] | None = None


@dataclass(frozen=True)
class BoundDecision:
    seq: int
    verdict: str
    reference: str
    actor: str
    at: str
    note: str | None
    subject_sha256: str


@dataclass(frozen=True)
class Finding:
    seq: int
    kind: str
    outcome: str
    fields: tuple[str, ...] = ()
    detail: str = ""


@dataclass(frozen=True)
class HistoryEvent:
    """Ein ursprüngliches Ereignis mit Bewertung und vollständiger Nutzlast.

    Abgeleitete Ansichtsdaten (eigene tiefe Kopien aus dem Snapshot): Die
    vollständige Nutzlast bleibt einsehbar — Quellenhash, Dateiname, Größe,
    Medientyp; Receipt-Inputs, Schritt, Codeversion, Params; jede einzelne
    Entscheidung mit Verdikt, Referenz, Akteur, Zeitpunkt und Note. Es wird
    nichts erfunden und kein Ereignisbyte geändert.
    """

    seq: int
    kind: str
    record_id: str | None
    outcome: str  # "valid" | "invalid" | "unchecked"
    fields: tuple[str, ...] = ()
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RevisionView:
    """Eine registrierte Fassung mit genau ihren Belegen und ihrer letzten
    unterstützten Entscheidung (höchste `seq` zu diesem Hash)."""

    record_id: str
    artifact: str
    sha256: str
    seq: int
    receipts: tuple[BoundReceipt, ...] = ()
    latest_decision: BoundDecision | None = None


@dataclass(frozen=True)
class ArtifactView:
    record_id: str
    artifact: str
    revisions: tuple[RevisionView, ...] = ()
    current: RevisionView | None = None
    unbound_receipts: tuple[BoundReceipt, ...] = ()
    unbound_decisions: tuple[BoundDecision, ...] = ()


@dataclass(frozen=True)
class RecordView:
    record_id: str
    artifacts: tuple[ArtifactView, ...] = ()


@dataclass(frozen=True)
class History:
    """Abgeleitete Ansicht über dem Snapshot (keine Originalkette)."""

    records: tuple[RecordView, ...] = ()
    findings: tuple[Finding, ...] = ()
    derived: bool = False
    filters: dict[str, str] = field(default_factory=dict)
    events: tuple[HistoryEvent, ...] = ()


def basis_findings(snapshot: Snapshot) -> tuple[Finding, ...]:
    """Gemeinsame Basisbewertung aus demselben Snapshot für alle Lesebefehle.

    Jeder nicht-gültige unterstützte Basisvertrag ergibt einen Befund mit
    Ereignisnummer und Feldnamen. Filter verändern diese globale Bewertung
    nie: Ein vorhandener Basisfehler bleibt in jeder Ansicht sichtbar.
    """
    rows = [
        Finding(
            seq=event.seq,
            kind=event.kind,
            outcome=outcome.outcome,
            fields=tuple(outcome.fields),
            detail=outcome.detail,
        )
        for event, outcome in zip(snapshot.events, snapshot.outcomes)
        if outcome.outcome != "valid"
    ]
    return tuple(sorted(rows, key=lambda f: f.seq))


def _subject_hash(kind: str, payload: Any) -> str | None:
    """Direkter Gegenstandshash je Art — oder None ohne solches Feld.

    Quelle/Artefakt: ``sha256``; Beleg: ``output_sha256``; Entscheidung:
    ``subject_sha256``. Input-Hashes begründen keinen Treffer.
    """
    if not isinstance(payload, dict):
        return None
    if kind == _profile.SOURCE_INGESTED or kind == _profile.ARTIFACT_PRODUCED:
        value = payload.get("sha256")
    elif kind == _profile.RECEIPT_RECORDED:
        value = payload.get("output_sha256")
    elif kind == _profile.DECISION_RECORDED:
        value = payload.get("subject_sha256")
    else:
        return None
    return value if isinstance(value, str) else None


def build_history(snapshot: Snapshot) -> History:
    """Baut die vollständige Historie: Fassungen, Belege, Entscheidungen."""
    revision_seqs: dict[tuple[str, str, str], list[int]] = {}
    receipts: dict[tuple[str, str, str], list[BoundReceipt]] = {}
    decisions: dict[tuple[str, str, str], list[BoundDecision]] = {}
    registered: set[str] = set()
    entries: list[HistoryEvent] = []
    for event, outcome in zip(snapshot.events, snapshot.outcomes):
        entries.append(
            HistoryEvent(
                seq=event.seq,
                kind=event.kind,
                record_id=event.record_id,
                outcome=outcome.outcome,
                fields=tuple(outcome.fields),
                payload=event.payload,
            )
        )
        if outcome.outcome != "valid":
            continue
        payload = event.payload
        record_id = event.record_id or ""
        if event.kind == _profile.RECORD_REGISTERED:
            registered.add(payload["record_id"])
        if event.kind == _profile.ARTIFACT_PRODUCED:
            revision_seqs.setdefault(
                (record_id, payload["artifact"], payload["sha256"]), []
            ).append(event.seq)
        elif event.kind == _profile.RECEIPT_RECORDED:
            receipts.setdefault(
                (record_id, payload["artifact"], payload["output_sha256"]), []
            ).append(
                BoundReceipt(
                    seq=event.seq,
                    step=payload["step"],
                    code_version=payload["code_version"],
                    output_sha256=payload["output_sha256"],
                    inputs=dict(payload["inputs"]),
                    params=copy.deepcopy(payload["params"])
                    if "params" in payload
                    else None,
                )
            )
        elif event.kind == _profile.DECISION_RECORDED:
            decisions.setdefault(
                (record_id, payload["artifact"], payload["subject_sha256"]), []
            ).append(
                BoundDecision(
                    seq=event.seq,
                    verdict=payload["verdict"],
                    reference=payload["reference"],
                    actor=payload["actor"],
                    at=payload["at"],
                    note=payload.get("note"),
                    subject_sha256=payload["subject_sha256"],
                )
            )
    # Jede (Record, Artefakt)-Gruppe erhält je registriertem Hash eine
    # Fassung mit genau ihren Belegen und ihrer letzten Entscheidung
    # (höchste seq zu diesem Hash). Die aktuelle Fassung bestimmt die höchste
    # passende Registrierungs-seq (letzte artifact.produced-seq zu dieser
    # Gruppe) — auch bei wiederholter Registrierung älterer Hashes (A→B→A).
    # Ein Beleg oder eine Entscheidung ist ungebunden, sobald seine volle
    # (Record, Artefakt, Hash)-Identität keine registrierte Fassung besitzt —
    # auch dann, wenn derselbe Artefaktname bereits andere Fassungen hat.
    groups: dict[tuple[str, str], set[str]] = {}
    for record_id, artifact, sha256 in revision_seqs:
        groups.setdefault((record_id, artifact), set()).add(sha256)
    record_views: dict[str, list[ArtifactView]] = {}
    for (record_id, artifact), shas in sorted(groups.items()):
        revision_views: list[RevisionView] = []
        for sha256 in sorted(shas, key=lambda s: revision_seqs[(record_id, artifact, s)][0]):
            seqs = sorted(revision_seqs[(record_id, artifact, sha256)])
            bound = tuple(sorted(receipts.get((record_id, artifact, sha256), []), key=lambda r: r.seq))
            bound_decisions = sorted(
                decisions.get((record_id, artifact, sha256), []), key=lambda d: d.seq
            )
            revision_views.append(
                RevisionView(
                    record_id=record_id,
                    artifact=artifact,
                    sha256=sha256,
                    seq=seqs[-1],
                    receipts=bound,
                    latest_decision=bound_decisions[-1] if bound_decisions else None,
                )
            )
        revisions = tuple(revision_views)
        view = ArtifactView(
            record_id=record_id,
            artifact=artifact,
            revisions=revisions,
            current=max(revisions, key=lambda r: r.seq) if revisions else None,
        )
        record_views.setdefault(record_id, []).append(view)
    unbound: dict[tuple[str, str], dict[str, list]] = {}
    for (record_id, artifact, sha), bound in sorted(receipts.items()):
        if (record_id, artifact, sha) not in revision_seqs:
            slot = _unbound_slot(record_views, unbound, record_id, artifact)
            slot["receipts"].extend(bound)
    for (record_id, artifact, sha), bound in sorted(decisions.items()):
        if (record_id, artifact, sha) not in revision_seqs:
            slot = _unbound_slot(record_views, unbound, record_id, artifact)
            slot["decisions"].extend(bound)
    for views in record_views.values():
        for i, view in enumerate(views):
            slot = unbound.pop((view.record_id, view.artifact), None)
            if slot is None:
                continue
            views[i] = ArtifactView(
                record_id=view.record_id,
                artifact=view.artifact,
                revisions=view.revisions,
                current=view.current,
                unbound_receipts=tuple(sorted(slot["receipts"], key=lambda r: r.seq)),
                unbound_decisions=tuple(sorted(slot["decisions"], key=lambda d: d.seq)),
            )
    for record_id in sorted(registered):
        # Registrierte Records ohne jede Fassung bleiben sichtbar.
        record_views.setdefault(record_id, [])
    ordered = tuple(
        RecordView(record_id=record_id, artifacts=tuple(views))
        for record_id, views in sorted(record_views.items())
    )
    return History(
        records=ordered,
        findings=basis_findings(snapshot),
        derived=False,
        filters={},
        events=tuple(entries),
    )


def _unbound_slot(
    record_views: dict[str, list[ArtifactView]],
    unbound: dict[tuple[str, str], dict[str, list]],
    record_id: str,
    artifact: str,
) -> dict[str, list]:
    """Sammelstelle für Belege/Entscheidungen ohne jede Fassung."""
    slot = unbound.setdefault((record_id, artifact), {"receipts": [], "decisions": []})
    if not any(
        view.record_id == record_id and view.artifact == artifact
        for view in record_views.get(record_id, [])
    ):
        record_views.setdefault(record_id, []).append(
            ArtifactView(record_id=record_id, artifact=artifact)
        )
    return slot


def _event_matches(
    event: HistoryEvent,
    *,
    record_id: str | None,
    artifact: str | None,
    sha256: str | None,
) -> bool:
    """Prüft, ob ein Ereignis zu allen aktiven Filtern passt.

    Einfache Regel: aktive Filter müssen gemeinsam passen. Der Record
    passt über die Hülle, das Artefakt über das direkt vorhandene
    ``artifact``-Feld, der Hash über den direkten Gegenstandshash der
    jeweiligen Art (Quelle/Artefakt ``sha256``, Beleg ``output_sha256``,
    Entscheidung ``subject_sha256``). Input-Hashes begründen keinen
    zusätzlichen Treffer; Ereignisse ohne das gefilterte Feld passen nicht.
    """
    if record_id is not None and event.record_id != record_id:
        return False
    if artifact is not None:
        if not isinstance(event.payload, dict) or event.payload.get("artifact") != artifact:
            return False
    if sha256 is not None and _subject_hash(event.kind, event.payload) != sha256:
        return False
    return True


def filter_history(
    history: History,
    *,
    record_id: str | None = None,
    artifact: str | None = None,
    sha256: str | None = None,
) -> History:
    """Filtert als abgeleitete Ansicht (keine Originalkette).

    Die Auswahl ändert nie den Fassungsstatus: ``current`` zeigt weiterhin
    die aktuelle Fassung des vollständigen Snapshots — auch dann, wenn sie
    selbst nicht zur Auswahl gehört. Die globale Basisbewertung
    (``findings``) bleibt vollständig erhalten; kein Filter verdeckt einen
    vorhandenen Basisfehler.
    """
    kept: list[RecordView] = []
    active = {
        name: value
        for name, value in (("record", record_id), ("artifact", artifact), ("sha256", sha256))
        if value is not None
    }
    for record in history.records:
        if record_id is not None and record.record_id != record_id:
            continue
        views: list[ArtifactView] = []
        for view in record.artifacts:
            if artifact is not None and view.artifact != artifact:
                continue
            if sha256 is not None:
                revisions = tuple(r for r in view.revisions if r.sha256 == sha256)
                unbound_receipts = tuple(
                    r for r in view.unbound_receipts if r.output_sha256 == sha256
                )
                unbound_decisions = tuple(
                    d for d in view.unbound_decisions if d.subject_sha256 == sha256
                )
            else:
                revisions = view.revisions
                unbound_receipts = view.unbound_receipts
                unbound_decisions = view.unbound_decisions
            kept_view = ArtifactView(
                record_id=view.record_id,
                artifact=view.artifact,
                revisions=revisions,
                current=view.current,
                unbound_receipts=unbound_receipts,
                unbound_decisions=unbound_decisions,
            )
            if not kept_view.revisions and not kept_view.unbound_receipts and not kept_view.unbound_decisions:
                continue
            views.append(kept_view)
        if views or (artifact is None and sha256 is None):
            kept.append(RecordView(record_id=record.record_id, artifacts=tuple(views)))
    kept_events = tuple(
        event
        for event in history.events
        if _event_matches(event, record_id=record_id, artifact=artifact, sha256=sha256)
    )
    return History(
        records=tuple(kept),
        findings=history.findings,
        derived=True,
        filters=active,
        events=kept_events,
    )


@dataclass(frozen=True)
class ArtifactCheck:
    """Prüfung bereitgestellter Bytes gegen registrierte Fassungen."""

    record_id: str
    artifact: str
    sha256: str
    registered: bool
    currency: str  # "current" | "historical" | "unregistered"
    revision_seq: int | None
    receipts: tuple[BoundReceipt, ...] = ()
    latest_decision: BoundDecision | None = None


def check_artifact(
    snapshot: Snapshot,
    *,
    record_id: str,
    artifact: str,
    sha256: str,
) -> ArtifactCheck:
    """Vergleicht Bytes (voller Hash) mit registrierten Fassungen.

    Nur gültige Basisereignisse begründen eine Zuordnung. Ein negativer
    Entscheidungswert ist kein Hash-/Kettenfehler.
    """
    history = build_history(snapshot)
    for record in history.records:
        if record.record_id != record_id:
            continue
        for view in record.artifacts:
            if view.artifact != artifact:
                continue
            matching = [r for r in view.revisions if r.sha256 == sha256]
            if not matching:
                return ArtifactCheck(
                    record_id=record_id,
                    artifact=artifact,
                    sha256=sha256,
                    registered=False,
                    currency="unregistered",
                    revision_seq=None,
                )
            revision = matching[-1]
            is_current = view.current is not None and view.current.sha256 == sha256
            return ArtifactCheck(
                record_id=record_id,
                artifact=artifact,
                sha256=sha256,
                registered=True,
                currency="current" if is_current else "historical",
                revision_seq=revision.seq,
                receipts=revision.receipts,
                latest_decision=revision.latest_decision,
            )
    return ArtifactCheck(
        record_id=record_id,
        artifact=artifact,
        sha256=sha256,
        registered=False,
        currency="unregistered",
        revision_seq=None,
    )


def snapshot_copy(snapshot: Snapshot) -> Snapshot:
    """Eigene stabile Kopie des Snapshots für Auswertungen.

    Beide Snapshots teilen den unveränderlichen geprüften Stand; jeder
    Zugriff gibt ohnehin eigene tiefe Kopien heraus.
    """
    return Snapshot(
        _events=snapshot.events,
        _outcomes=snapshot.outcomes,
    )
