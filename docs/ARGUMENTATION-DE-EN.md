# Explaining the journal / Das Journal erklären

## Short statements to remember / Kurze Merksätze

| Deutsch | English |
|---|---|
| Wir dokumentieren erfasste Dateien und Arbeitsschritte. | **We document registered files and recorded work.** |
| Das Journal macht erfasste Abläufe nachvollziehbar. | **The journal makes recorded workflows inspectable.** |
| Eine Zustimmung bleibt bei ihrer konkreten Fassung. | **Approval stays with its specific revision.** |
| Die Prüfung kontrolliert die gespeicherte Ereigniskette. | **Verification checks the recorded event chain.** |
| Technische Gültigkeit beweist keine wissenschaftliche Wahrheit. | **Technical validity does not establish scholarly truth.** |
| Ein Beleg dokumentiert einen erklärten Arbeitsschritt. | **A receipt records a reported processing step.** |
| Vollständigkeit braucht verbindliche Erfassungsregeln. | **Completeness needs explicit workflow rules.** |
| Bewahre unabhängig geschützte Journalstände auf. | **Keep independently protected journal snapshots.** |
| Personenidentität braucht zusätzliche Nachweise. | **Personal identity needs additional evidence.** |
| Die Forschungsdateien müssen separat erhalten bleiben. | **Keep the research files as well as the journal.** |

## The central claim / Die zentrale Aussage

**English:** The journal links registered sources, result revisions, reported
processing steps, and decisions. It checks the recorded chain and binds decisions
to a record, an artifact, and a file hash. Researchers can inspect which decision
applies to which revision. Complete coverage, authentic authorship, and scholarly
quality require additional procedures and evidence.

**Deutsch:** Das Journal verknüpft registrierte Quellen, Ergebnisfassungen,
erklärte Verarbeitungsschritte und Entscheidungen. Es prüft die gespeicherte
Ereigniskette und bindet Entscheidungen an Record, Artefakt und Dateihash.
Forschende können nachvollziehen, welche Entscheidung zu welcher Fassung gehört.
Vollständige Erfassung, nachgewiesene Urheberschaft und wissenschaftliche Qualität
brauchen zusätzliche Verfahren und Nachweise.

## A defensible argument for DH / Eine belastbare DH-Argumentation

### 1. Its contribution is a specific, inspectable relationship

A filename such as `transcript-final.txt` does not tell a reviewer which bytes
were approved. This journal uses the combination of record identifier, artifact
identifier, and SHA-256 hash. A changed result does not inherit another revision's
decision. Registering matching bytes in another record or under another artifact
name does not transfer the decision either.

The benefit is a concrete answer to “Which revision was reviewed?” It supports
review and handover by making recorded relationships explicit. It does not itself
judge whether a transcript accurately represents an interview.

**Deutsch:** Der Mehrwert ist die überprüfbare Zuordnung, nicht das Wort „final“
im Dateinamen. Die Entscheidung bleibt beim richtigen Arbeitsgegenstand,
Ergebnis und Dateihash. Wissenschaftliche Interpretation bleibt eine fachliche Aufgabe.

**Say:** “We can identify the exact revision to which a recorded decision applies.”

### 2. Algorithmic recording has a defined scope

The standalone tool records events explicitly submitted through its API or CLI.
An integration can submit those events during processing. The tool does not
independently discover every interview or every action. `verify` checks the stored
chain and supported event payloads; it does not search the project for omissions
or re-read all original research files.

Sequence numbers describe the order of recording. They do not independently
prove when an interview or processing step actually happened. The current revision
is the latest registered one, not necessarily the most accurate or approved one.
Hashes compare bytes, not meaning: a format change may change the hash even when
the wording stays the same.

**Deutsch:** Algorithmisch geprüft wird die vorliegende Dokumentation. Nicht
erfasste Interviews und ausgelassene Schritte erkennt die Kettenprüfung nicht.
Auch Aussagen über den tatsächlichen Zeitpunkt und die inhaltlich beste Fassung
folgen nicht automatisch aus den Einträgen.

**Say:** “It checks what was recorded. It cannot certify what was never recorded.”

### 3. Integrity needs a reference that the same writer cannot silently replace

The application appends events and checks existing data before each write.
That protects the normal application workflow. It is not a filesystem barrier
against someone who can directly replace the journal.

In SHA-256 mode, a person with write access can rewrite entries and recompute the
chain. HMAC makes recomputation depend on the secret key; anyone with that key
can still produce valid entries. Removing trailing events or restoring an older
valid journal can pass verification in either mode.

Preserve verified snapshots independently, with access controls that prevent the
journal writer from silently replacing them. At a review milestone, retain the
journal, configuration, final sequence number, and final event digest. A later
comparison must check that the previously recorded prefix is still present and
unchanged, then verify the later chain. A saved full-file hash describes its
snapshot; legitimate later appends change that full-file hash.

Snapshots establish a comparison point, not evidence about unrecorded actions
between snapshots. v0.1.0 has no built-in checkpoint service, automatic comparison
against external snapshots, or digital signatures.

**Deutsch:** Die Software schreibt anhängend. Historische Unverändertheit wird
stärker belegbar, wenn ein früherer Vergleichsstand unabhängig geschützt erhalten
bleibt. Eine weitere Datei im selben veränderbaren Ordner genügt dafür nicht.

**Say:** “Historical integrity needs an independently protected reference.”

### 4. Trust in statements needs people and procedures

A receipt describes a reported processing step. It is not execution attestation.
An actor field is a stated identity, and a timestamp is recorded information.
HMAC provides key-based integrity; it does not identify an individual person.
A valid schema does not make a claim true.

For stronger evidence, an integration should record actual inputs and outputs,
software versions and parameters, with references to retained execution logs
that report success or failure. Failed runs and missing journal entries must also
be documented in the project workflow; v0.1.0 has no dedicated failure event type. Require review before a project treats an output as approved. Stronger
identity evidence would require controlled personal credentials and reliable key
attribution; signatures and trusted timestamps remain future extensions.

**Deutsch:** Gute Belege entstehen zeitnah aus realen Abläufen und werden fachlich
kontrolliert. Eine Signatur würde Herkunft absichern helfen, aber keine richtige
Transkription oder korrekte Interpretation garantieren.

**Say:** “Technical checks support accountable review. They do not replace it.”

### 5. Preservation and confidentiality remain project responsibilities

Hashes cannot reconstruct lost audio, transcripts, or annotations. Preserve all
required source and revision files with the journal and its configuration. Backups
need a tested recovery procedure. Keep an HMAC key separately protected and
recoverable for authorised verification.

Metadata can also be sensitive: filenames, notes, actors, and parameters may
identify people. Use appropriate identifiers, minimise such details, and restrict
access. The public software repository contains code, documentation, and synthetic
examples; real research journals belong in the project's protected storage.

**Deutsch:** Nachvollziehbarkeit, Aufbewahrung und Zugriffsschutz gehören zusammen.
Das Journal ersetzt weder das Forschungsarchiv noch seine Zugriffsregeln.

**Say:** “The journal supports preservation. It is not the archive.”

## Questions from colleagues / Fragen von Fachkollegen

| Question | Short answer in English | Antwort auf Deutsch |
|---|---|---|
| Does it capture every interview? | It records the interviews and actions you register. Coverage must be checked against a project inventory. | Es erfasst registrierte Interviews und Schritte. Vollständigkeit wird gegen eine Projektbestandsliste geprüft. |
| Is it tamper-proof? | The application appends events. Stronger historical evidence needs protected external snapshots. | Die Anwendung hängt Ereignisse an. Für stärkere historische Nachweise braucht es geschützte externe Vergleichsstände. |
| Can a receipt be false? | Yes. It records a statement. Retained run evidence and review strengthen that statement. | Ja. Der Beleg ist zunächst eine Erklärung. Aufbewahrte Laufnachweise und Prüfung stärken sie. |
| Does ACCEPT mean the interview is true? | It records approval of a specific revision. It does not certify historical truth. | Es dokumentiert Zustimmung zu einer konkreten Fassung, keine historische Wahrheit. |
| Does it guarantee reproducibility? | It records useful provenance. Reproduction also needs the files, software, parameters, and environment. | Es liefert nützliche Herkunftsinformationen. Wiederholung braucht auch Dateien, Software, Parameter und Umgebung. |
| Why not just use Git? | Git can preserve file history. The journal adds explicit source, receipt, and decision relationships. | Git kann Dateigeschichte erhalten. Das Journal ergänzt ausdrückliche Quellen-, Beleg- und Entscheidungsbeziehungen. |
| Is it PROV-O compliant? | Not currently. A PROV-O export is planned. | Derzeit nicht. Ein PROV-O-Export ist geplant. |

## Operating checklist / Praktische Absicherung

These are project procedures, not additional features already implemented in v0.1.0.

1. Maintain an interview inventory and stable record identifiers. Compare expected
   interviews with registrations; define which steps must be documented.
2. Record work close to its execution. Retain inputs, outputs, code versions,
   parameters, and run evidence. Explicitly document gaps or failed logging.
3. Before delivery, check the actual output file against the journal and review
   its decision. A valid chain alone is not a release gate.
4. Preserve verified snapshots at milestones in independently protected storage.
   Compare the preserved prefix with later journal states; investigate differences.
5. Back up research files and journal configuration. Protect any HMAC key separately.
   Test recovery according to the [recovery guide](WIEDERHERSTELLUNG.md).
6. Minimise identifying metadata and control access. Publish synthetic demonstrations
   with the software, not research journals.

Built-in checkpoints, signatures, provenance graphs, staleness checks, and PROV-O
export remain on the [development roadmap](AUSBAU.md). Existing
[usage notes](NUTZUNG.md), [CLI contract](CLI.md), and [format contract](FORMAT.md)
describe the implemented behaviour.

## Background sources

The argument distinguishes provenance information from the assessment made using
it. This follows the conceptual role described in the
[W3C PROV overview](https://www.w3.org/TR/prov-overview/): information about objects,
activities, and involved agents can support an assessment of trustworthiness.
This conceptual reference does not claim PROV compliance for this package.

Effective log management includes organisational processes as well as technical
infrastructure. See [NIST SP 800-92](https://csrc.nist.gov/pubs/sp/800/92/final).
Digital signatures can provide integrity and origin authentication when keys are
reliably attributed and controlled; see
[NIST FIPS 186-5](https://csrc.nist.gov/pubs/fips/186-5/final).
Neither reference constitutes certification or endorsement of this tool.
