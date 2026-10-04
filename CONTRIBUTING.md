# Contributing to dh-provenance-journal

## Setup

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
pip install build
```

Requires Python 3.11 or newer. The only runtime dependency is the
standard library; `pytest` is the development dependency, `build` the
packaging tool used below.

## Checks before any change

```bash
python -m pytest tests/
python -m build
```

The full suite must pass. Behaviour changes need a focused regression
test in `tests/` that fails without the fix.

## Compatibility duty

The envelope fields, digest bytes, reference vectors in
`tests/fixtures/digest_vectors.json`, the `research-basic-v1` profile,
package and CLI names, exit contracts and JSON shapes are the stable
contract (see `docs/FORMAT.md`, `docs/CLI.md`). Any change touching them
must prove compatibility: existing vectors green, `verify`/`history`/
`check-artifact` behaviour unchanged for old journals. Never migrate or
rewrite existing journals; never repair, trim or re-chain.

## What stays out

Research data, real journals, keys, caches and internal review files do
not enter version control (see `.gitignore`) and are never published.
Synthetic fixtures only.
