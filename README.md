# dh-provenance-journal

**A small provenance journal for registered research files, processing records, and revision-specific decisions.**

Which source file was registered? Which result revision was reviewed?
Which recorded decision applies to the file you have now?
The journal makes these recorded relationships inspectable for interview
material, transcripts, annotations, and data exports in the digital humanities.

It records events submitted through its API or command line. It does not
automatically discover every interview or certify a complete project history.
Its practical contribution is precise file and decision attribution, together
with verification of the recorded event chain.

The principle comes from the OHPIPE journal. The tool works on its own:
through the terminal command `provjournal`, or from Python with the package
`provenance_journal`. You need no programming skills to try it;
just run the commands shown below.

**Please note: the command-line help and human-readable terminal output are currently in German.**
Your terminal will show German words; this guide explains them in English
and quotes the actual German terminal output unchanged. JSON field names are in English.
The detailed step-by-step guide is likewise in German
(see [Deutsche Kurzfassung](#deutsche-kurzfassung) below).

## Deutsche Kurzfassung

Das Werkzeug verknüpft registrierte Quellen, Ergebnisfassungen, erklärte
Arbeitsschritte und Entscheidungen. Entscheidungen werden einem Arbeitsgegenstand,
einem Artefakt und einem Dateihash zugeordnet; veränderte Bytes übernehmen keine
frühere Zustimmung. Die algorithmische Prüfung kontrolliert die vorliegende
Ereigniskette und das Basisprofil, nicht die vollständige Geschichte oder die
wissenschaftliche Wahrheit eines Interviews. Vollständige Erfassung, geschützte
Vergleichsstände und Aufbewahrung der Forschungsdateien brauchen zusätzliche
Projektverfahren. Der [deutsche Einsteiger-Guide](https://github.com/klausbehnamshad/dh-provenance-journal/blob/main/docs/EINSTIEG-SCHRITT-FUER-SCHRITT.md)
erklärt den Ablauf; [kurze Merksätze und die ausführliche Argumentation auf Deutsch
und Englisch](https://github.com/klausbehnamshad/dh-provenance-journal/blob/main/docs/ARGUMENTATION-DE-EN.md)
helfen bei der Vorstellung gegenüber Fachkollegen.

## What you can document in everyday research

A typical flow in an oral-history project:

1. A source file is assigned to an interview.
2. A transcript or annotation revision is registered.
3. A receipt describes the inputs, the result, and the work step carried out.
4. A person records their approval or rejection of this revision.
5. A reworked version gets its own entry and its own decision.

The decision on the first revision stays visible with that revision.
Changed file bytes do not inherit that decision.

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
| **Journal** | The continuous file `journal.jsonl`. The application appends events and checks the existing chain before writing. Direct file replacement requires external safeguards. |

An artifact can have several concrete revisions. A decision is bound to the
combination of record ID, artifact ID, and file hash. Matching bytes in another
record or under another artifact name do not transfer the decision.
The current revision follows the order in which revisions were registered in the
journal. File names like `v1` and `v2` help orientation but do not set the status
by themselves.

## What you can rely on

- **Revision-specific review:** recorded decisions belong to a record, artifact,
  and hash. A changed output does not inherit another revision's approval.
- **Inspectable records:** sources, declared processing inputs and outputs, and
  decisions remain visible in the history. The current revision means the latest
  registered one, not necessarily the best or approved one.
- **Technical verification:** `verify` checks the stored chain and supported payloads.
  It does not check for omitted interviews, prove that a processing step ran, or
  re-read all original research files.

Short phrases for explaining the tool:

> The journal makes recorded workflows inspectable.
>
> Approval stays with its specific revision.
>
> Verification checks the recorded event chain.
>
> Technical validity does not establish scholarly truth.

See [the bilingual argument and operating checklist](https://github.com/klausbehnamshad/dh-provenance-journal/blob/main/docs/ARGUMENTATION-DE-EN.md)
for what these statements mean and how to strengthen the evidence.

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
its cause first; the [guide](https://github.com/klausbehnamshad/dh-provenance-journal/blob/main/docs/EINSTIEG-SCHRITT-FUER-SCHRITT.md) (in German)
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
0 substantively unchecked". It confirms internal consistency, not scholarly
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
is shown by the [guide from step 14 onward](https://github.com/klausbehnamshad/dh-provenance-journal/blob/main/docs/EINSTIEG-SCHRITT-FUER-SCHRITT.md#14-ergänzung-und-neue-zustimmung-dokumentieren) (in German).

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

## Evidence, safeguards, and limits

The application checks the existing journal before appending an event. This
protects the normal writing workflow; it does not make the file impossible to
replace outside the application.

| What matters | Implemented in v0.1.0 | Additional project safeguard |
|---|---|---|
| Which revision a decision applies to | Matching by record ID, artifact ID, and hash | Check the actual deliverable with `check-artifact` and review its decision. |
| Consistency of recorded events | Sequence, hash-chain, and supported payload checks | Compare against independently protected earlier snapshots. |
| Coverage of interviews and required steps | Explicit registration through the API or CLI | Maintain a project inventory and check required steps for each record. |
| Whether processing really happened | Receipts store declared inputs, outputs, step, and version | Retain actual execution logs, parameters, software, and files; review them. |
| Identity and time | Actor and time are stored information; HMAC adds key-based integrity | Use controlled access and additional identity/time evidence when required. |
| Availability and confidentiality | Hashes and metadata are stored; file contents are not archived | Preserve sources, revisions, journal, and configuration; protect keys and sensitive metadata. |

**A valid chain is not proof of an unchanged complete history.** In SHA-256 mode,
a person with write access can rewrite entries and recompute the chain. HMAC
requires the secret key for recomputation, but does not prevent removing trailing
events or restoring an older valid journal. Preserve verified snapshots where
the journal writer cannot silently replace them. Compare the earlier recorded
prefix with later states; a full-file hash changes after legitimate appends.
Built-in external checkpoints and digital signatures are not provided in v0.1.0.

A receipt is a reported processing step, not execution attestation. An actor name
is a stated identity; HMAC does not prove a particular person's authorship.
Sequence numbers establish the order of recording, not independently confirmed
real-world dates. A valid payload does not establish scholarly correctness.

Keep the research files, `journal.jsonl`, and `journal.jsonl.config.json`, and test
recovery from backups. Hashes cannot reconstruct lost interviews or transcripts.
Filenames, notes, actors, and parameters may contain identifying information;
use suitable identifiers and access controls. Research journals belong in protected
project storage, not in the public software repository.

The [bilingual argument and operating checklist](https://github.com/klausbehnamshad/dh-provenance-journal/blob/main/docs/ARGUMENTATION-DE-EN.md)
explains the safeguards and separates existing features from planned extensions.

Exit codes: **0** technically successful; **1** check/read error, or, for
`check-artifact`, unassigned bytes; **2** invalid arguments or configuration.
A rejection on scholarly grounds (`REJECT`) is by itself no technical error.

## Further reading

These are direct links to the documents in the public repository.
The practical guide and technical references are in German; the argument is bilingual.

- [Step-by-step guide (German)](https://github.com/klausbehnamshad/dh-provenance-journal/blob/main/docs/EINSTIEG-SCHRITT-FUER-SCHRITT.md): download, installation, and every step with expected output.
- [Argument and memorable phrases (German / English)](https://github.com/klausbehnamshad/dh-provenance-journal/blob/main/docs/ARGUMENTATION-DE-EN.md): benefits, limits, questions from colleagues, and safeguards.
- [Usage notes (German)](https://github.com/klausbehnamshad/dh-provenance-journal/blob/main/docs/NUTZUNG.md): how to interpret the results.
- [CLI reference (German)](https://github.com/klausbehnamshad/dh-provenance-journal/blob/main/docs/CLI.md): commands, exit codes, and JSON output.
- [Recovery guide (German)](https://github.com/klausbehnamshad/dh-provenance-journal/blob/main/docs/WIEDERHERSTELLUNG.md): handling damaged journals and resuming from suitable backups.
- [Synthetic example (German)](https://github.com/klausbehnamshad/dh-provenance-journal/blob/main/examples/BEISPIEL.md): a prepared demonstration with invented data.
- [Validation status (German)](https://github.com/klausbehnamshad/dh-provenance-journal/blob/main/docs/PRUEFSTAND.md): tested combinations and known limits.
- [Journal format (German)](https://github.com/klausbehnamshad/dh-provenance-journal/blob/main/docs/FORMAT.md): event structure and hash chaining.
- [Development roadmap (German)](https://github.com/klausbehnamshad/dh-provenance-journal/blob/main/docs/AUSBAU.md): planned extensions.

For development: [CONTRIBUTING.md](https://github.com/klausbehnamshad/dh-provenance-journal/blob/main/CONTRIBUTING.md).
License: [MIT](https://github.com/klausbehnamshad/dh-provenance-journal/blob/main/LICENSE).
Code provenance: [NOTICE.md](https://github.com/klausbehnamshad/dh-provenance-journal/blob/main/NOTICE.md).
Citing the software: [CITATION.cff](https://github.com/klausbehnamshad/dh-provenance-journal/blob/main/CITATION.cff).
