"""Fehlertaxonomie des Journals.

Die Klassen sind der CLI eindeutig zuordenbar:

* ConfigError — fehlende oder unbrauchbare Modus-/Schlüsselkonfiguration.
  Der Bestand wurde nicht geprüft (Auswertung steht aus), nie als
  Verifikationsfehler zu melden.
* VerificationError — der vorhandene Bestand hat die Prüfung nicht
  bestanden (Kette, Digest, Profil oder Basisnutzlast).
* PayloadRejected — die NEUE Nutzlast eines Schreibaufrufs ist ungültig.
  Das ist ein Aufruferfehler; geschrieben wurde nichts.
* JournalIOError — Ein-/Ausgabefehler am Journalpfad.
* UnconfirmedWrite — ein write- oder fsync-Fehler: Es kann ein teilweise
  oder vollständig geschriebenes, aber unbestätigtes Ereignis vorhanden
  sein. Kein Erfolg, keine automatische Wiederholung; ein neuer Versuch
  beginnt mit erneuter Prüfung.
* JournalUnsafe — der Pfad ist belegt, aber nicht durch eine reguläre
  Journaldatei (Symlink, Verzeichnis, FIFO, fehlendes Elternverzeichnis
  beim Schreiben). Fail-closed: Unterklasse von JournalIOError, damit
  jeder Aufrufer, der I/O-Fehler behandelt, hier ebenfalls anhält.
"""

from __future__ import annotations

from pathlib import Path

__all__ = [
    "ProvenanceError",
    "ConfigError",
    "VerificationError",
    "ChainError",
    "DigestMismatch",
    "ProfileError",
    "PayloadError",
    "PayloadRejected",
    "FileReadError",
    "JournalIOError",
    "UnconfirmedWrite",
    "JournalUnsafe",
]


class ProvenanceError(Exception):
    """Basis aller Bibliotheksfehler."""


class ConfigError(ProvenanceError):
    """Modus- oder Schlüsselkonfiguration fehlt oder ist unbrauchbar."""


class VerificationError(ProvenanceError):
    """Der vorhandene Bestand hat die Prüfung nicht bestanden."""


class ChainError(VerificationError):
    """Sequenz-, Verkettungs- oder Hüllenfehler im vorhandenen Bestand."""


class DigestMismatch(ChainError):
    """Ein gespeicherter Digest stimmt nicht mit der Neuberechnung überein.

    Das kann ein falscher Schlüssel oder veränderte Bytes bedeuten. Es wird
    bewusst keine eindeutig festgestellte Manipulationsursache behauptet.
    """


class ProfileError(VerificationError):
    """Der Bestand folgt nicht dem schreibbaren Basisprofil
    (falsches/fehlendes Profil, fehlende Registrierung, Duplikatkonflikt,
    fachlicher Altbestand)."""


class PayloadError(VerificationError):
    """Eine vorhandene Basisnutzlast ist ungültig.

    ``seq`` nennt die betroffene Ereignisnummer, ``fields`` die beanstandeten
    Feldnamen. Abgelehnte Werte werden nie in die Meldung übernommen.
    """

    def __init__(self, seq: int, fields: list[str], detail: str = "") -> None:
        self.seq = seq
        self.fields = list(fields)
        text = f"Basisnutzlast ungültig bei seq={seq}: Felder {self.fields}"
        if detail:
            text += f" ({detail})"
        super().__init__(text)


class PayloadRejected(ProvenanceError):
    """Die neue Nutzlast eines Schreibaufrufs passt nicht zur Ereignisart.

    Meldungen nennen Feldnamen, niemals abgelehnte Werte.
    """

    def __init__(self, fields: list[str] | str, detail: str = "") -> None:
        self.fields = [fields] if isinstance(fields, str) else list(fields)
        text = f"Nutzlast abgewiesen: Felder {self.fields}"
        if detail:
            text += f" ({detail})"
        super().__init__(text)


class JournalIOError(ProvenanceError):
    """Ein-/Ausgabefehler am Journalpfad."""


class FileReadError(JournalIOError):
    """Eine Eingabe-, Parameter- oder Schlüsseldatei ist nicht lesbar.

    Der Pfad steht als Attribut bereit, nicht in der Meldung: Aufrufer
    zeigen ihn kontrolliert (z. B. JSON-quotiert) an.
    """

    def __init__(self, pfad: Path, grund: str) -> None:
        super().__init__(f"Datei nicht lesbar: {grund}")
        self.pfad = Path(pfad)
        self.grund = grund


class UnconfirmedWrite(JournalIOError):
    """Schreiben oder fsync ist fehlgeschlagen; der Zustand ist unbestätigt.

    Es kann ein teilweise oder vollständig geschriebenes, aber nicht
    bestätigtes Ereignis vorhanden sein. Der fachliche Vorgang wird nicht
    automatisch wiederholt; ein neuer Versuch beginnt mit erneuter Prüfung.
    """


#: Der Wortlaut des Befunds. Einzeilig und pfadfrei — der Pfad steht in
#: ``pfad``, nicht im Fliesstext.
UNSAFE_REASON = (
    "Der Journalpfad ist belegt, aber nicht durch eine reguläre Journaldatei. "
    "Es wurde nichts gelesen und nichts geschrieben."
)


class JournalUnsafe(JournalIOError):
    """Der Pfad ist belegt — nur nicht durch ein reguläres Journal."""

    def __init__(self, pfad: Path, ursache: str = "") -> None:
        super().__init__(UNSAFE_REASON)
        self.pfad = Path(pfad)
        #: Symbolischer Fehlername (``ELOOP``, ``EISDIR``, ``nicht-S_ISREG`` …).
        #: Nur für Diagnose, nie Teil des Befundsatzes.
        self.ursache = ursache
