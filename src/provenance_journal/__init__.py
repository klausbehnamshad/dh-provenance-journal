"""Eigenständiger Journalkern für DH-Provenienz (v0.1).

Öffentlich ist die kleine Schreibschnittstelle in
:mod:`provenance_journal.api`; daneben Hülle, Hashing, Fehler und Profil.
``provenance_journal._store`` ist privat: Es gibt keinen offen verwendbaren
Schreibweg an Profil- und Kettenprüfung vorbei.
"""

from . import api as api
from . import config as config
from . import errors as errors
from . import files as files
from . import hashing as hashing
from . import history as history
from . import profile as profile
from .api import (
    CheckReport,
    EventAssessment,
    WriteResult,
    check_journal,
    ingest_source,
    init_journal,
    produce_artifact,
    read_events,
    record_decision,
    record_receipt,
    register_record,
    verify_journal,
)
from .envelope import ENVELOPE_FIELDS, GENESIS, Event
from .errors import (
    ChainError,
    ConfigError,
    DigestMismatch,
    FileReadError,
    JournalIOError,
    JournalUnsafe,
    PayloadError,
    PayloadRejected,
    ProfileError,
    ProvenanceError,
    UnconfirmedWrite,
    VerificationError,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "api",
    "config",
    "errors",
    "files",
    "hashing",
    "history",
    "profile",
    "ENVELOPE_FIELDS",
    "GENESIS",
    "Event",
    "CheckReport",
    "EventAssessment",
    "WriteResult",
    "check_journal",
    "ingest_source",
    "init_journal",
    "produce_artifact",
    "read_events",
    "record_decision",
    "record_receipt",
    "register_record",
    "verify_journal",
    "ChainError",
    "ConfigError",
    "DigestMismatch",
    "FileReadError",
    "JournalIOError",
    "JournalUnsafe",
    "PayloadError",
    "PayloadRejected",
    "ProfileError",
    "ProvenanceError",
    "UnconfirmedWrite",
    "VerificationError",
]
