# dh-provenance-journal

**A small tool for tracing how digital research files came about and how they were assessed.**

Which file was the original source? How did a particular result revision come about?
Which revision was reviewed, and which decision belongs to it?
The journal keeps these connections in a continuous event list.
It is useful, for example, for interview material, transcripts, annotations,
or data exports in the digital humanities.

The principle comes from the OHPIPE journal. The tool works on its own:
through the terminal command `provjournal`, or from Python with the package
`provenance_journal`. You need no programming skills to try it;
just run the commands shown below.

**Please note: the command-line help and all tool output are currently in German.**
Your terminal will show German words; this guide explains them in English
and always quotes the actual German output unchanged.
The detailed step-by-step guide is likewise in German
(see [Deutsche Kurzfassung](#deutsche-kurzfassung) below).

## Deutsche Kurzfassung

Dieses Werkzeug dokumentiert Entstehung und Beurteilung digitaler Forschungsdateien
in einem fortlaufenden Journal. Eine typische Anwendung ist ein Oral-History-Projekt,
in dem Quellen, Transkriptfassungen, Belege sowie Zustimmung oder Ablehnung festgehalten
werden. Eine Entscheidung gilt dabei stets für eine konkrete Dateifassung mit ihrem
Dateihash, nicht pauschal für einen Dateinamen. Der ausführliche
[Schritt-für-Schritt-Guide](docs/EINSTIEG-SCHRITT-FUER-SCHRITT.md) erklärt auf Deutsch
Download, Installation, jeden Journalbefehl und die erwarteten Ausgaben.

## What you can document in everyday research

A typical flow in an oral-history project:

1. A source file is assigned to an interview.
2. A transcript or annotation revision is registered.
3. A receipt describes the inputs, the result, and the work step carried out.
4. A person records their approval or rejection of this revision.
5. A reworked version gets its own entry and its own decision.

The decision on the first revision stays visible with that revision.
Changed file bytes do not take it over automatically.

The journal recognises files by their **hash**, a digital fingerprint computed
from the file bytes. The file name alone is not enough to assign a decision.
You never have to compute hashes yourself.

## Key terms

| Term | Meaning |
|---|---|
| **Record** | A unit of work with a freely chosen identifier, for example an interview `r1`. |
| **Source** | A registered starting file, for example a recording or a text file. Called *Quelle* in the German output. |
| **Artifact** | A named result, for example `memo` or `transcript`, which can have several revisions. |
| **Revision** | The actual bytes of a result file; a change produces a different hash. Called *Fassung* in the German output. |
| **Receipt** | Your explanation of which inputs and which step produced a revision. Called *Beleg* in the German output. |
| **Decision** | `ACCEPT` (approval), `REJECT` (rejection), or `WITHDRAW` (withdrawal), each applying to one specific revision. |
| **Journal** | The continuous file `journal.jsonl`. New events are appended; existing entries are never edited. |

An artifact has several concrete revisions, and a decision always belongs to the
file hash of its revision — never broadly to the file name.
The current revision follows the order in which revisions were registered in the
journal. File names like `v1` and `v2` help orientation but do not set the status
by themselves.

## Installation

You need **Python 3.11 or newer** and, for the repository installation, an
internet connection. The commands below are written for macOS and Linux;
the detailed guide (in German) walks through the start on macOS. The journal has
no extra runtime dependencies. `pip` may fetch tools for building the package.

### From the public repository

This path needs neither Git nor a GitHub account. It uses a fixed, tested
source snapshot of version 0.1.0. Repository:
[github.com/klausbehnamshad/dh-provenance-journal](https://github.com/klausbehnamshad/dh-provenance-journal).

Start in an **empty** installation folder. If the name is already taken,
pick a new one, for example `provjournal-install-2`.

```bash
mkdir -p ~/provjournal-install && cd ~/provjournal-install
python3 --version
```

Check that Python is at least version 3.11. Creating the folder and entering it
downloads nothing yet. This command does that:

```bash
curl -fL https://github.com/klausbehnamshad/dh-provenance-journal/archive/3f434c19fb5808a229f6d914570045559e898371.zip -o repo.zip
```

After a successful download, unpack, set up your own Python environment,
and install the package:

```bash
unzip -q repo.zip &&
mv dh-provenance-journal-3f434c19fb5808a229f6d914570045559e898371 quellcode &&
python3 -m venv .venv &&
source .venv/bin/activate &&
python -m pip install ./quellcode &&
provjournal --help
```

Expectation: a successful installation of `dh-provenance-journal-0.1.0` and
help text listing nine commands. `(.venv)` at the start of the terminal line
usually shows that your own environment is active. If an error appears, find
its cause first; the [guide](docs/EINSTIEG-SCHRITT-FUER-SCHRITT.md) (in German)
explains each step individually.

### From a provided release package

If you have a wheel file with its `SHA256SUMS`, you can install it instead
in an empty installation folder. Compare the checksum first, then run there:

```bash
python3 -m venv .venv &&
source .venv/bin/activate &&
python -m pip install ./dh_provenance_journal-0.1.0-py3-none-any.whl &&
provjournal --help
```

Alternatively, install a provided source package with
`python -m pip install ./dh_provenance_journal-0.1.0.tar.gz`.
The project is currently not offered on PyPI. The repository installation above
needs no published release.

## Your first run

Installation is done and the environment is active. This short trial uses
**made-up text data**. We copy a source file and document this copy that was
actually carried out. The commands stay in the same terminal.

### 1. Create the working files

```bash
mkdir erster-versuch && cd erster-versuch
```

If the trial folder already exists, choose a new name and complete this step
successfully first. Then create the working files:

```bash
printf '%s\n' 'Eine Testperson beschreibt einen Spaziergang.' 'Diese Notiz dient nur der Erprobung.' > quelle.txt
cp quelle.txt memo-v1.txt
```

`quelle.txt` (German for "source file") is the source; `memo-v1.txt` is our
first result revision.

### 2. Record the source and the revision

```bash
provjournal --journal journal.jsonl init
provjournal --journal journal.jsonl register --record r1
provjournal --journal journal.jsonl ingest --record r1 --file quelle.txt --media-type text/plain
provjournal --journal journal.jsonl artifact --record r1 --artifact memo --file memo-v1.txt
```

These are events 1 to 4. `r1` names the unit of work, `memo` the result.
Global options such as `--journal` come **before** each command.

### 3. Document the work step and the approval

```bash
provjournal --journal journal.jsonl receipt --record r1 --artifact memo --output memo-v1.txt --input quelle=quelle.txt --step 'unveraenderte Kopie' --code-version manuell-v1
provjournal --journal journal.jsonl decide --record r1 --artifact memo --file memo-v1.txt --verdict ACCEPT --reference TEST-01 --actor 'Testperson'
```

The receipt explains the copy you carried out (`unveraenderte Kopie` is German
for "unchanged copy"). `manuell-v1` is here the label of the manual work step.
`TEST-01` is a freely chosen decision reference; `Testperson` ("test person")
is the stated actor. Later, replace these example values with details of your
own work.

### 4. Check and review

```bash
provjournal --journal journal.jsonl verify
provjournal --journal journal.jsonl history
provjournal --journal journal.jsonl check-artifact --record r1 --artifact memo --file memo-v1.txt
```

Expectation: **six valid events**, revision `seq 4` current, receipt `seq 5`,
approval `ACCEPT` at `seq 6`. `seq` is the running event number.
`verify` prints this actual German output:

```text
Kette: gültig (6 Ereignisse)
Basis: 6 gültig, 0 ungültig, 0 fachlich ungeprüft
```

That is: "chain: valid (6 events)"; "base profile: 6 valid, 0 invalid,
0 substantively unchecked". It confirms inner consistency, not scholarly
correctness.

| Command | What it tells you |
|---|---|
| `verify` | Is the event chain at hand internally valid, and do the entries satisfy the base profile? |
| `history` | Which sources, revisions, receipts, and decisions were recorded, and in which order? |
| `check-artifact` | Which registered revision matches the bytes of this file, and which decision belongs to it? |

### 5. Recognise a reworked version

```bash
cp memo-v1.txt memo-v2.txt
printf '%s\n' 'Die zweite Fassung ergänzt eine Beobachtung.' >> memo-v2.txt
provjournal --journal journal.jsonl check-artifact --record r1 --artifact memo --file memo-v2.txt
echo $?
```

Expectation: **not registered** (`nicht registriert`), exit code **1**. This is
the intended negative check: the new file has different bytes and has not been
recorded yet.

```bash
provjournal --journal journal.jsonl artifact --record r1 --artifact memo --file memo-v2.txt
provjournal --journal journal.jsonl check-artifact --record r1 --artifact memo --file memo-v2.txt
```

Now the second revision is current (`seq 7`), but it still has **no supported
decision** (`keine unterstützte Entscheidung zu dieser Fassung` — "no supported
decision for this revision"). The earlier approval was not carried over.
How to enter the new receipt and the new approval and compare both revisions
is shown by the [guide from step 14 onward](docs/EINSTIEG-SCHRITT-FUER-SCHRITT.md#14-ergänzung-und-neue-zustimmung-dokumentieren) (in German).

## Continuing later

For the folder names from the example:

```bash
cd ~/provjournal-install
source .venv/bin/activate
cd erster-versuch
provjournal --journal journal.jsonl history
```

No need to install or initialise again. Adjust the folder names if you chose
others. `deactivate` ends the Python environment; your files stay in place.
Start a new trial in a new folder.

## What the journal shows — and what remains your responsibility

- The journal stores **hashes and metadata**, not file contents. Keep the sources,
  revisions, `journal.jsonl`, and `journal.jsonl.config.json`; there is no automatic archiving.
- A run receipt documents your explanation of a processing step. The tool does not
  carry out the step itself and does not prove on its own that it was carried out.
- `verify` checks the inner consistency of the journal at hand. A technically valid
  chain is no scholarly approval. Without an independently kept reference copy,
  a valid but shortened journal file can go unnoticed.
- A decision's actor entry is a stored statement. Even the optional HMAC mode
  confirms key possession, not personal identity.

Exit codes: **0** technically successful; **1** check/read error, or, for
`check-artifact`, unassigned bytes; **2** invalid arguments or configuration.
A rejection on scholarly grounds (`REJECT`) is by itself no technical error.

## Further reading

The guide and the documents below are written in German.

| You want to … | Read here |
|---|---|
| Follow every step with its expected output | [Step-by-step guide (in German)](docs/EINSTIEG-SCHRITT-FUER-SCHRITT.md) |
| Understand use and meaning in everyday research | [Usage notes (in German)](docs/NUTZUNG.md) |
| Look up all commands and JSON output | [CLI reference (in German)](docs/CLI.md) |
| Handle damaged or uncontinuable holdings | [Recovery (in German)](docs/WIEDERHERSTELLUNG.md) |
| Play through a fully prepared example | [Synthetic example (in German)](examples/BEISPIEL.md) |
| See the test stand and known limits | [Test stand (in German)](docs/PRUEFSTAND.md) |
| Study the format and hash chaining | [Journal format (in German)](docs/FORMAT.md) |
| Learn about further development steps | [Extensions (in German)](docs/AUSBAU.md) |

For development: [CONTRIBUTING.md](https://github.com/klausbehnamshad/dh-provenance-journal/blob/main/CONTRIBUTING.md).
License: [MIT](LICENSE). Code provenance: [NOTICE.md](NOTICE.md).
Citing the software: [CITATION.cff](https://github.com/klausbehnamshad/dh-provenance-journal/blob/main/CITATION.cff).
