# dh-provenance-journal — append-only provenance journal with CLI

Package `provenance_journal`, CLI `provjournal`. An append-only event
journal with hash chaining (SHA-256 or HMAC), base profile
`research-basic-v1`, verification, terminal history and JSON output.
Standard library only; Python 3.11+. Detailed command and format
contracts are documented in German: `docs/CLI.md`, `docs/FORMAT.md`;
usage guidance in `docs/NUTZUNG.md`, recovery in
`docs/WIEDERHERSTELLUNG.md`. A synthetic German walkthrough lives in
`examples/` ([BEISPIEL.md](examples/BEISPIEL.md)).

## Requirements

Python 3.11 or newer. No runtime dependencies. `pytest` for development
(`pip install "dh-provenance-journal[dev]"` once published, or
`pip install pytest`).

## Installation

No PyPI publication; install from the release archives. Repository:
<https://github.com/klausbehnamshad/dh-provenance-journal>. Wheel, sdist
and SHA256SUMS are attached to the GitHub release v0.1.0 there (a draft
pending final review at the time of writing); until it is published, use
the archives delivered with this candidate. Copy or download both
archives into one install directory first, then run one of the blocks
below inside it:

```bash
mkdir -p ~/provjournal-install && cd ~/provjournal-install
```

From the release wheel, in a fresh virtual environment:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install dh_provenance_journal-0.1.0-py3-none-any.whl
provjournal --help
```

Alternatively from the source archive:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install dh_provenance_journal-0.1.0.tar.gz
provjournal --help
```

For co-development from this tree (separate from plain use above):

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
pip install build
python -m pytest tests/
```

The synthetic walkthrough starts from the repository root:

```bash
examples/run.sh ./mein-versuch
```

(Or `cd examples` first, then `./run.sh ../mein-versuch`.) Details in
[examples/BEISPIEL.md](examples/BEISPIEL.md) (in German).

## First flow (synthetic data only, a few minutes)

Global options (`--journal`, `--integrity`, `--key-file`) come before
the command. `--journal` defaults to `./journal.jsonl`.

```bash
mkdir demo && cd demo
printf 'source one\n' > source.txt
printf 'result one\n' > result.txt
provjournal --journal journal.jsonl init
provjournal --journal journal.jsonl register --record rec-01
provjournal --journal journal.jsonl ingest --record rec-01 \
  --file source.txt --media-type text/plain
provjournal --journal journal.jsonl artifact --record rec-01 \
  --artifact result.txt --file result.txt
provjournal --journal journal.jsonl receipt --record rec-01 \
  --artifact result.txt --output result.txt \
  --input source=source.txt --step derive --code-version v1
provjournal --journal journal.jsonl decide --record rec-01 \
  --artifact result.txt --file result.txt \
  --verdict ACCEPT --reference PI-1 --actor "A. Researcher"
provjournal --journal journal.jsonl verify
provjournal --journal journal.jsonl history
provjournal --journal journal.jsonl check-artifact --record rec-01 \
  --artifact result.txt --file result.txt
```

## Reading the output

- `verify` checks the hash chain and each stored payload separately:
  `Kette: gültig (N Ereignisse)` plus valid/invalid/unchecked counts.
  Exit 0 means technically valid — not scientific approval.
- `history` shows events in sequence, revisions with their receipts and
  the latest decision, plus unbound acts and findings. Filters select;
  they never change which revision is current.
- `check-artifact` matches given bytes by full identity (record, artifact
  name, hash): registered or not, current or historical revision.
- Exit codes: 0 success (including real duplicates), 2 configuration or
  argument errors, 1 chain/basis/I-O problems or unassigned bytes.
  Errors never print a traceback.

## Limits

The journal stores hashes and metadata, never file contents; no
automatic archiving. A receipt documents a declared run, not proof it
happened. `unchecked` events are chain-checked but semantically
unreviewed; `invalid` is an error. See `docs/NUTZUNG.md` and
`docs/WIEDERHERSTELLUNG.md` (in German) before relying on any journal.

License: MIT (`LICENSE`); provenance: `NOTICE.md`.
