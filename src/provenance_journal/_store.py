"""Append-only Dateispeicher mit Hashverkettung, Sperre und sicherem POSIX-Zugriff.

Übernommen aus ``src/ohpipe/journal.py`` (Commit 3cff6f6). Dieses Modul ist
bewusst privat: Es kennt die Mechanik (Sperre, Kette, Digest), aber keine
Fachprofile. Der einzige Schreibweg ist die verifizierte Transaktion, die
``api`` mit Profil- und Nutzlastprüfung verwendet. Die ungeprüfte
öffentliche ``append``-Methode des Ausgangsstands ist nicht portiert; die
Transaktion hat zusätzlich zum übernommenen ``append_once`` ein normales
``append`` erhalten.

Änderungen gegenüber dem Ausgangsstand (begründet in docs/UEBERNAHME.md):

* Vollständiges Schreiben: Kurze ``os.write``-Rückgaben werden durch
  Nachschreiben der Restbytes behandelt; Erfolg erst nach vollständigem
  Write und erfolgreichem fsync. Fehler melden ``UnconfirmedWrite``.
* Alle Leserückgaben sind tiefe Kopien; nachträglich veränderte Payloads
  können nicht als verifiziert ausgegeben werden.
* Schlüsselverwaltung liegt in ``config`` (PROVJOURNAL_KEY statt
  OHPIPE_JOURNAL_KEY); Fehlerklassen liegen in ``errors``.
"""

from __future__ import annotations

import copy
import errno
import fcntl
import json
import os
import stat as statmodul
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .envelope import GENESIS, Event
from .errors import ChainError, DigestMismatch, JournalIOError, JournalUnsafe, UnconfirmedWrite

__all__ = ["Journal", "now_iso"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


#: Fehlerdomäne für J1 — **symbolisch, nie gegen Zahlen.**
#: ``errno.ELOOP`` ist auf Linux und Darwin dieselbe Konstante, aber nicht
#: dieselbe Zahl (40 gegen 62). ``EMLINK`` steht als Netz für BSD-Varianten,
#: die ein ``O_NOFOLLOW`` so quittieren.
UNSICHER_ERRNO = frozenset({errno.ELOOP, errno.EMLINK, errno.ENOTDIR, errno.ENXIO, errno.EISDIR})


def _write_all(fd: int, data: bytes) -> None:
    """Schreibt alle Bytes oder meldet den unbestätigten Zustand.

    Kurze ``os.write``-Rückgaben werden durch Nachschreiben behandelt. Eine
    ``0``-Rückgabe oder eine ``OSError`` bedeutet: Es kann ein teilweise oder
    vollständig geschriebenes, aber unbestätigtes Ereignis vorhanden sein.
    Es gibt keine automatische Wiederholung; ein neuer Versuch beginnt mit
    erneuter Prüfung.
    """
    view = memoryview(data)
    while view:
        try:
            n = os.write(fd, view)
        except OSError as exc:
            raise UnconfirmedWrite(
                "Schreiben fehlgeschlagen; Zustand unbestätigt — "
                "erneut prüfen, bevor der Vorgang wiederholt wird."
            ) from exc
        if n == 0:
            raise UnconfirmedWrite(
                "Schreiben lieferte 0 Bytes; Zustand unbestätigt — "
                "erneut prüfen, bevor der Vorgang wiederholt wird."
            )
        view = view[n:]


class Journal:
    """Append-only, hash-verkettet, ein Schreiber je Sperre.

    Bewusst KEIN Lösch- oder Update-Pfad und keine Kürzung, Reparatur oder
    Neuverkettung. Nur innerhalb dieses Pakets über ``api`` verwendbar.
    """

    def __init__(self, path: Path, key: bytes | None = None) -> None:
        self.path = Path(path)
        self.key = key
        #: Gemerkter Kopf (seq, prev) — NUR gültig, solange dieses Objekt der
        #: letzte Schreiber war. Siehe ``_head_locked``.
        self._kopf: tuple[int, str] | None = None

    @property
    def integrity(self) -> str:
        """``keyed`` oder ``unkeyed`` — der Unterschied ist kein Detail."""
        return "keyed" if self.key else "unkeyed"

    # -- Die eine Oeffnung ------------------------------------------------

    @property
    def _lockpfad(self) -> Path:
        return self.path.with_suffix(self.path.suffix + ".lock")

    @contextmanager
    def _elternverzeichnis(self, *, pflicht: bool) -> Iterator[int | None]:
        """Der Deskriptor des Elternverzeichnisses. ``O_DIRECTORY | O_NOFOLLOW``.

        ``pflicht`` trennt die beiden Bedeutungen von ``ENOENT``: beim
        **Lesen** ist ein fehlendes Elternverzeichnis *pristine* — es gibt
        schlicht kein Journal. Beim **Schreiben** ist es ein Befund, denn der
        Schreibpfad legt nichts mehr an.
        """
        eltern = self.path.parent
        try:
            fd = os.open(eltern, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        except FileNotFoundError as exc:
            if pflicht:
                raise JournalUnsafe(eltern, "ENOENT") from exc
            yield None
            return
        except OSError as exc:
            if exc.errno in UNSICHER_ERRNO:
                raise JournalUnsafe(eltern, errno.errorcode.get(exc.errno, "")) from exc
            raise JournalIOError(f"Verzeichnis nicht lesbar: {exc}") from exc
        try:
            yield fd
        finally:
            os.close(fd)

    def _roh_oeffne(self, dir_fd: int, name: str, flags: int, *, pfad: Path) -> int:
        """Die rohe Öffnung samt Abbildung der Fehlerdomäne — **ohne** Retry."""
        try:
            return os.open(name, flags | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=dir_fd)
        except FileNotFoundError:
            raise
        except OSError as exc:
            if exc.errno in UNSICHER_ERRNO:
                raise JournalUnsafe(pfad, errno.errorcode.get(exc.errno, "")) from exc
            raise

    def _oeffne(self, dir_fd: int, name: str, flags: int, *, pfad: Path) -> int:
        """Die **eine** Stelle, an der ein Endpunkt geöffnet wird.

        ``O_NOFOLLOW`` (kein Link wird verfolgt), ``O_NONBLOCK`` (eine FIFO
        ohne Gegenstelle quittiert statt zu blockieren) und ``fstat`` +
        ``S_ISREG`` am geöffneten Objekt, nie am Pfad. Der Name wird relativ
        zu ``dir_fd`` geöffnet, nicht absolut.

        **Der eine Wiederholversuch:** Auf Darwin scheitert die gleichzeitige
        *Erstanlage* desselben Namens über ``openat``/``dir_fd`` mit
        ``ENOENT``. Deshalb darf eine **erzeugende** Öffnung ihren ersten
        ``ENOENT`` genau einmal wiederholen — mit demselben Namen, denselben
        Flags, demselben Modus und demselben bereits geprüften ``dir_fd``.
        Nur mit ``O_CREAT``, genau einmal, kein Sleep, kein Backoff.
        """
        try:
            fd = self._roh_oeffne(dir_fd, name, flags, pfad=pfad)
        except FileNotFoundError:
            if not flags & os.O_CREAT:
                raise
            try:
                os.stat(".", dir_fd=dir_fd)
            except OSError as wurzel:
                raise JournalUnsafe(pfad, "ENOENT") from wurzel
            try:
                fd = self._roh_oeffne(dir_fd, name, flags, pfad=pfad)
            except FileNotFoundError as zweiter:
                raise JournalUnsafe(pfad, "ENOENT") from zweiter
        try:
            if not statmodul.S_ISREG(os.fstat(fd).st_mode):
                raise JournalUnsafe(pfad, "nicht-S_ISREG")
        except BaseException:
            os.close(fd)
            raise
        return fd

    # -- Lesen ------------------------------------------------------------

    @staticmethod
    def _zeilen(fh: Any) -> Iterator[str]:
        """Zeilen des bereits geöffneten Streams.

        Die UTF-8-Dekodierung scheitert beim Iterieren, nicht in
        ``json.loads``: Dekodierungsfehler werden hier als ``ChainError``
        (ungültige Journalbytes), echte Stream-I/O-Fehler als
        ``JournalIOError`` eingeordnet. Keine Zeileninhalte in Diagnosen.
        """
        n = 0
        try:
            for line in fh:
                n += 1
                yield line
        except UnicodeDecodeError as exc:
            raise ChainError(f"ungültige UTF-8-Bytes ab Zeile {n + 1}") from exc
        except OSError as exc:
            raise JournalIOError(f"Lesefehler ab Zeile {n + 1}: {exc}") from exc

    @staticmethod
    def _aus_datei(fh: Any) -> Iterator[Event]:
        """Jeder Lese-, Parse- oder Schemafehler wird zu ``ChainError``."""
        for n, line in enumerate(Journal._zeilen(fh), start=1):
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                raise ChainError(f"Zeile {n} ist kein gültiges JSON: {exc}") from exc
            except OSError as exc:
                raise JournalIOError(f"Lesefehler in Zeile {n}: {exc}") from exc
            if not isinstance(raw, dict):
                raise ChainError(f"Zeile {n} ist kein Objekt, sondern {type(raw).__name__}")
            try:
                yield Event.from_json(raw)
            except (KeyError, TypeError, ValueError) as exc:
                raise ChainError(
                    f"Zeile {n}: Pflichtfeld fehlt oder passt nicht ({exc})"
                ) from exc

    def __iter__(self) -> Iterator[Event]:
        """Lesen über die Primitive. Fehlt das Journal, ist das kein Befund."""
        with self._elternverzeichnis(pflicht=False) as dfd:
            if dfd is None:
                return
            try:
                fd = self._oeffne(dfd, self.path.name, os.O_RDONLY, pfad=self.path)
            except FileNotFoundError:
                return
            except JournalUnsafe:
                raise
            except OSError as exc:
                raise JournalIOError(f"Journal nicht lesbar: {exc}") from exc
        with os.fdopen(fd, "r", encoding="utf-8") as fh:
            yield from self._aus_datei(fh)

    def _am_deskriptor(self, fd: int) -> Iterator[Event]:
        """Vollständig lesen, **ohne den Pfad noch einmal anzufassen**."""
        try:
            kopie = os.dup(fd)
            os.lseek(kopie, 0, os.SEEK_SET)
        except OSError as exc:
            raise JournalIOError(f"Journal nicht lesbar: {exc}") from exc
        with os.fdopen(kopie, "r", encoding="utf-8") as fh:
            yield from self._aus_datei(fh)

    def events(self) -> list[Event]:
        """Tiefe Kopien des Bestands — ungelesen bleibt nichts verifiziert."""
        return copy.deepcopy(list(self))

    def head(self) -> tuple[int, str]:
        """Liest die ganze Datei. Read-only und immer korrekt."""
        seq, prev = 0, GENESIS
        for e in self:
            seq, prev = e.seq, e.digest
        return seq, prev

    def _head_locked(self, fd: int) -> tuple[int, str]:
        """Der Kopf unter gehaltener Sperre — mit gemerktem Wert.

        Der gemerkte Wert ist **nur** gültig, wenn seit dem letzten eigenen
        Schreiben niemand sonst angehängt hat (Dateigröße, monoton wachsend).
        **Die Größe kommt vom geöffneten Deskriptor, nicht vom Pfad**
        (``fstat(fd)`` statt ``path.stat()``): Zwischen beiden läge ein
        Fenster, in dem der Pfad ein anderer werden kann.
        """
        groesse = os.fstat(fd).st_size
        if self._kopf is not None and groesse == self._groesse_nach_schreiben:
            return self._kopf
        seq, prev = 0, GENESIS
        for e in self._am_deskriptor(fd):
            seq, prev = e.seq, e.digest
        self._kopf = (seq, prev)
        self._groesse_nach_schreiben = groesse
        return self._kopf

    #: Dateigröße unmittelbar nach dem letzten eigenen Schreiben.
    _groesse_nach_schreiben: int = -1

    def pruefe_lockpfad(self) -> None:
        """Prüft den Lockpfad, **ohne zu sperren und ohne anzulegen**.

        Ein Link am Lockpfad verschiebt die Sperre auf einen fremden Inode
        und hebt lautlos die Serialisierung auf. ``O_CREAT`` steht hier
        ausdrücklich **nicht**: Fehlt die Lockdatei, ist das kein Befund; sie
        entsteht beim ersten Schreiben.
        """
        with self._elternverzeichnis(pflicht=False) as dfd:
            if dfd is None:
                return
            try:
                fd = self._oeffne(dfd, self._lockpfad.name, os.O_RDONLY, pfad=self._lockpfad)
            except FileNotFoundError:
                return
            except OSError as exc:
                raise JournalIOError(f"Sperrpfad nicht lesbar: {exc}") from exc
            os.close(fd)

    def verify(self, events: list[Event] | None = None) -> list[Event]:
        """Prüft Kette vollständig (Seq, prev, Digest). Gibt den geprüften
        Snapshot als tiefe Kopie zurück — Verifikation und spätere Auswertung
        benutzen dieselben geprüften Daten."""
        snapshot = copy.deepcopy(events) if events is not None else list(self)
        expected_seq, prev = 1, GENESIS
        for e in snapshot:
            if e.seq != expected_seq:
                raise ChainError(f"Sequenzlücke: erwartet {expected_seq}, gefunden {e.seq}")
            if e.prev != prev:
                raise ChainError(f"Kettenbruch bei seq={e.seq}: prev passt nicht")
            want = Event.compute_digest(
                e.seq,
                e.at,
                e.kind,
                e.record_id,
                e.payload,
                e.prev,
                self.key,
                e.operation_intent_sha256,
            )
            if want != e.digest:
                if self.key is not None:
                    raise DigestMismatch(
                        f"Verifikation fehlgeschlagen bei seq={e.seq}: "
                        "möglicher falscher Schlüssel oder veränderte Daten"
                    )
                raise DigestMismatch(
                    f"Verifikation fehlgeschlagen im SHA-256-Modus bei seq={e.seq}"
                )
            expected_seq, prev = e.seq + 1, e.digest
        return copy.deepcopy(snapshot)

    # -- Schreiben --------------------------------------------------------

    @contextmanager
    def _exclusive(self, *, blocking: bool = True):
        """Sperrt das Journal für Lesen-des-Kopfes UND Anhängen.

        ``O_APPEND`` allein genügt NICHT: Es macht das Schreiben atomar, aber
        nicht die Vergabe der Sequenznummer. Die Sperre liegt auf einer
        eigenen Datei und geht durch **dieselbe** Primitive wie der Endpunkt.
        Herausgereicht wird der Deskriptor des Journals: Alles unter der
        Sperre arbeitet an diesem einen Objekt, ohne den Pfad erneut
        aufzulösen. Angelegt wird hier **nichts** — ein fehlendes
        Elternverzeichnis ist beim Schreiben ein Befund.
        """
        with self._elternverzeichnis(pflicht=True) as dfd:
            try:
                lock_fd = self._oeffne(
                    dfd, self._lockpfad.name, os.O_WRONLY | os.O_CREAT, pfad=self._lockpfad
                )
            except OSError as exc:
                raise JournalIOError(f"Sperrdatei nicht öffnbar: {exc}") from exc
            try:
                try:
                    fcntl.flock(lock_fd, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
                except OSError as exc:
                    raise JournalIOError(f"Journal nicht sperrbar: {exc}") from exc
                try:
                    fd = self._oeffne(
                        dfd,
                        self.path.name,
                        os.O_RDWR | os.O_CREAT | os.O_APPEND,
                        pfad=self.path,
                    )
                except OSError as exc:
                    raise JournalIOError(f"Journal nicht öffnbar: {exc}") from exc
                try:
                    yield fd
                finally:
                    os.close(fd)
            finally:
                try:
                    fcntl.flock(lock_fd, fcntl.LOCK_UN)
                except OSError:
                    # Aufräumen: Das Schließen gibt die Sperre ohnehin frei.
                    pass
                os.close(lock_fd)

    @contextmanager
    def transaction(self, *, blocking: bool = True):
        """Verifizierter Snapshot unter derselben Sperre.

        Die Transaktion bedeutet Sperre und verifizierten Snapshot, keine
        rückrollbare Mehrereignis-Transaktion: Ein Vorgang mit mehreren
        Ereignissen kann bei einem späteren Fehler bereits geschriebene
        Ereignisse hinterlassen. Keine Terminalwartezeit, Modellarbeit oder
        Ableitung im Kontext.
        """
        with self._exclusive(blocking=blocking) as fd:
            events = list(self._am_deskriptor(fd))
            snapshot = self.verify(events)
            self._pruefe_anhanggrenze(fd)
            transaction = _JournalTransaction(self, fd, snapshot)
            try:
                yield transaction
            finally:
                transaction.close()

    @staticmethod
    def _pruefe_anhanggrenze(fd: int) -> None:
        """Sichere Zeilengrenze am bereits geöffneten Deskriptor.

        Ein nichtleeres Journal ohne abschließenden LF darf nicht verändert
        werden: Das nächste Ereignis stünde ohne Trennzeichen auf derselben
        Zeile und würde den lesbaren Bestand beschädigen. Weder LF ergänzen
        noch kürzen/reparieren — abweisen als Verifikationsfehler. Die reine
        lesende Digestprüfung akzeptiert einen solchen Bestand weiterhin;
        Schreibbarkeit und Digestgültigkeit sind verschieden.
        """
        try:
            size = os.fstat(fd).st_size
            tail = os.pread(fd, 1, size - 1) if size > 0 else b""
        except OSError as exc:
            raise JournalIOError(f"Anhanggrenze nicht prüfbar: {exc}") from exc
        if size > 0 and tail != b"\n":
            raise ChainError(
                "Journal endet ohne Zeilenumbruch; Anhang abgewiesen, "
                "Bestand unverändert"
            )

    def _append_locked(
        self,
        fd: int,
        kind: str,
        payload: dict[str, Any],
        *,
        record_id: str | None = None,
        operation_intent_sha256: str | None = None,
    ) -> Event:
        seq, prev = self._head_locked(fd)
        at = now_iso()
        seq += 1
        digest = Event.compute_digest(
            seq,
            at,
            kind,
            record_id,
            payload,
            prev,
            self.key,
            operation_intent_sha256,
        )
        ev = Event(
            seq=seq,
            at=at,
            kind=kind,
            record_id=record_id,
            payload=copy.deepcopy(payload),
            prev=prev,
            operation_intent_sha256=operation_intent_sha256,
            digest=digest,
        )
        line = json.dumps(ev.to_json(), ensure_ascii=False, sort_keys=True) + "\n"
        # O_APPEND + vollständiges Schreiben + fsync: Erst NACH fsync wird der
        # gemerkte Kopf aktualisiert und Erfolg gemeldet.
        _write_all(fd, line.encode("utf-8"))
        try:
            os.fsync(fd)
        except OSError as exc:
            raise UnconfirmedWrite(
                "fsync fehlgeschlagen; Ereignis unbestätigt — "
                "erneut prüfen, bevor der Vorgang wiederholt wird."
            ) from exc
        self._kopf = (ev.seq, ev.digest)
        self._groesse_nach_schreiben = os.fstat(fd).st_size
        return copy.deepcopy(ev)


class _JournalTransaction:
    """Nur innerhalb Journal.transaction verwendbarer Schreiber ohne erneutes flock."""

    def __init__(self, journal: Journal, fd: int, events: list[Event]) -> None:
        self._journal = journal
        self._fd = fd
        self._events = events
        self.path = journal.path
        self.key = journal.key

    def close(self) -> None:
        self._fd = None  # type: ignore[assignment]

    def _require_open(self) -> None:
        if self._fd is None:
            raise RuntimeError("Journaltransaktion ist geschlossen")

    @property
    def snapshot(self) -> list[Event]:
        """Der verifizierte Snapshot als tiefe Kopie."""
        self._require_open()
        return copy.deepcopy(self._events)

    def append(
        self,
        kind: str,
        payload: dict[str, Any],
        *,
        record_id: str | None = None,
        operation_intent_sha256: str | None = None,
    ) -> Event:
        """Normales Anhängen an den verifizierten Snapshot (neu in v0.1;
        der Ausgangsstand bot hier nur ``append_once``)."""
        self._require_open()
        event = self._journal._append_locked(
            self._fd,
            kind,
            payload,
            record_id=record_id,
            operation_intent_sha256=operation_intent_sha256,
        )
        self._events.append(event)
        return copy.deepcopy(event)

    def append_once(
        self,
        kind: str,
        payload: dict[str, Any],
        *,
        record_id: str | None = None,
        duplikat: Callable[[Event], bool] | None = None,
        operation_intent_sha256: str | None = None,
    ) -> Event | None:
        """Idempotentes Anhängen: Prüfung UND Schreiben in derselben Sperre."""
        self._require_open()
        for event in self._events:
            if event.kind != kind or event.record_id != record_id:
                continue
            if duplikat is None or duplikat(event):
                return None
        event = self._journal._append_locked(
            self._fd,
            kind,
            payload,
            record_id=record_id,
            operation_intent_sha256=operation_intent_sha256,
        )
        self._events.append(event)
        return copy.deepcopy(event)
