# Formatvertrag v0.1 (research-basic-v1)

Stand 3. Oktober 2026. Dieser Vertrag beschreibt Hülle, Hashbytes,
Integritätsmodus und Kompatibilitätsgrenzen des eigenständigen Journals.
Originaljournale werden nicht migriert oder umgeschrieben.

## Hülle

Die Journaldatei ist JSONL: eine Zeile je Ereignis, UTF-8, Schlüssel
sortiert (`sort_keys`, `ensure_ascii=False`). Jede Zeile enthält genau die
Hüllenfelder:

| Feld | Typ | Bedeutung |
|---|---|---|
| `seq` | int (kein bool) | Folgenummer ab 1, lückenlos |
| `at` | str | Erzeugungszeitpunkt des Eintrags (ISO-8601) |
| `kind` | str | Ereignisart |
| `record_id` | str oder null | Hülle bestimmt die Record-Zuordnung |
| `payload` | Objekt | Ereignisnutzlast (siehe Basisprofil) |
| `prev` | str | Digest des Vorgängers (`GENESIS` = 64 Nullen bei seq 1) |
| `digest` | str | Hash über die Zeile (siehe Hashbytes) |
| `operation_intent_sha256` | optional, voller Hex-sha256 | Intent-Bindung; wird beim Lesen und Hashprüfen unterstützt, eigene v0.1-Ereignisse benötigen es nicht |

Fremde Hüllenfelder werden abgewiesen. Fehlendes und `null`-gesetztes
Intent-Feld ergeben dieselben Hashbytes (kein Feld im Body); ein belegtes
Feld ändert sie (Vektoren `sha256-intent-missing/null/set` in
`tests/fixtures/digest_vectors.json`).

## Hashbytes

Der Digest läuft über den Body
`{seq, at, kind, record_id, payload, prev}` plus — nur wenn belegt —
`operation_intent_sha256`. Kanonische Byteform:

```
json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
```

* Modus `sha256`: `SHA-256(canonical_bytes)`, Hex.
* Modus `hmac`: `HMAC-SHA-256(schlüssel, canonical_bytes)`, Hex.

SHA-256 und HMAC lassen sich nicht am Digestformat unterscheiden; der Modus
steht deshalb in der Beistelldatei (siehe unten), nie in den Ereignisbytes.
Referenzvektoren (SHA-256/HMAC, Unicode, `record_id=null`, Intent-Varianten)
stehen fest in `tests/fixtures/digest_vectors.json` — mit Eingaben, Bytes
und erwarteten Digests. Nachrechenbar pro Vektor, z. B.:

```
printf '%s' "$blob" | sha256sum   # blob aus dem Fixture, UTF-8
```

## Basisprofil research-basic-v1

Eigene Schreibvorgänge erzeugen nur diese Nutzlasten:

| Ereignis | Nutzlast |
|---|---|
| `workspace.initialised` | `profile`, `root`, `version`; `root="."`; Hülle ohne Record |
| `record.registered` | `record_id`, `profile` |
| `source.ingested` | `record_id`, `sha256`, `media_type`, `filename`, `bytes` |
| `artifact.produced` | `artifact`, `sha256` |
| `receipt.recorded` | `artifact`, `output_sha256`, `inputs`, `code_version`, `kind=deterministic`, `step`; optional `params` |
| `decision.recorded` | `artifact`, `subject_sha256`, `verdict`, `reference`, `actor`, `at`; optional `note` |

Feste Werte: `profile="research-basic-v1"`, `root="."`, `version="v0.1"`.
Geprüft werden Feldsätze und Typen, Record-Konsistenz, vollständige
SHA-256-Werte, nichtleere logische Bezeichner, Referenz (vollständiger
Tokenabgleich `^[\w.:@/+-]{3,64}$`, kein Whitespace — auch kein LF) und
zeitzonenbehaftete Entscheidungszeit. `bytes` ist eine nichtnegative
Ganzzahl (`bool` gilt nicht als Ganzzahl). `inputs` ist eine nichtleere
Rollen-zu-Hash-Zuordnung. `params` fehlt oder ist ein JSON-Objekt: Ein
vorhandenes Feld — einschließlich `null` — muss ein Objekt sein;
`record_receipt(..., params=None)` schreibt das Feld gar nicht.
`verdict` wird erst als String geprüft, dann mit den erlaubten Werten
verglichen. Entscheidungen: `ACCEPT`, `REJECT`, `WITHDRAW` (`UNDO` bleibt
Lesefall). `filename` ist ein Basename (kein Pfad). Alle Nutzlasten müssen
JSON-serialisierbar sein.

Hüllenregeln gelten beim Lesen/Bewerten wie beim Erzeugen: Nur
`workspace.initialised` trägt Hüllen-Record `null`; alle anderen
Basisarten brauchen eine nichtleere Hüllen-Record-ID (`null` und `""`
ungültig). Trägt die Nutzlast `record_id`, muss sie exakt der Hülle
gleichen — ohne Ausnahme für `null`. `assess` bewertet das einzelne
Ereignis (`valid`/`invalid`/`unchecked`); die Gesamtprüfung der
Schreibbarkeit (`check_stock_writable`, unter der Sperre) verlangt darüber
hinaus: genau ein Workspace am Anfang, jeder Record genau einmal
registriert und erst danach benutzt. Ein lokal gültiges zweites
Workspace-/Record-Ereignis bleibt lesbar, macht den Bestand aber nicht
schreibbar.

Reservierte Namen auf der obersten Nutzlastebene (kein Beweis für
Personenbezugsfreiheit — Notizen, Dateinamen, Akteure und Parameter können
sensible Angaben tragen):

```
name, text, value, original, quote, context, replacement, surface
```

Sie werden abgewiesen, nicht still verworfen.

## Integritätsmodus

`<journal>.config.json` hält `{"integrity": "sha256"|"hmac"}` — lokale
Konfiguration außerhalb der Ereignisbytes. Bei der Anlage ist `sha256` der
Standard; `hmac` wird ausdrücklich gewählt. Für bestehende Journale ohne
Konfiguration verlangt die lesende API eine explizite Moduswahl
(`integrity=...`): kein Ausprobieren, kein automatischer HMAC-Fallback.
Widerspruch zwischen Angabe und Konfiguration ist ein Konfigurationsfehler.

`PROVJOURNAL_KEY` bezeichnet den Pfad einer Schlüsseldatei, niemals den
Schlüsseltext. Mindestlänge 16 Bytes; der Schlüssel muss außerhalb der
Datenwurzel (Elternverzeichnis des Journals) liegen. Die alte Variable
`OHPIPE_JOURNAL_KEY` wird nie gelesen. Die Beistelldatei wird mit
denselben sicheren Lesehilfen geöffnet wie Eingabe-, Parameter- und
Schlüsseldateien (`O_NOFOLLOW`, `O_NONBLOCK`, `S_ISREG` am geöffneten
Deskriptor): FIFO, Verzeichnis, Link und unlesbare Konfiguration sind
Konfigurationsfehler — ohne Hänger, ohne Moduswechsel, ohne stilles
Umschreiben. Fehlende Datei bleibt der Fall „explizite Moduswahl nötig“.

Diagnosen: fehlender/unbrauchbarer Schlüssel oder Modus → Konfiguration
unvollständig, Journal nicht verifiziert. HMAC-Digestabweichung →
Verifikation fehlgeschlagen; möglicher falscher Schlüssel oder veränderte
Daten (keine festgestellte Manipulationsursache). SHA-256-Abweichung →
Verifikation fehlgeschlagen im SHA-256-Modus. Ungültige Basisnutzlast →
Ereignisnummer und Feldnamen. Fachliche Spezialvariante → Kette prüfbar,
Fachsemantik nicht geprüft. Ungültige UTF-8-Bytes beim Stream-Lesen →
Kettenfehler; echte Stream-I/O-Fehler → I/O-Fehler (ohne
Forschungsbytes in den Meldungen).

## Schreibregeln (kurz)

Jeder öffentliche Schreibweg nimmt die Journalsperre, prüft den Bestand
(Sequenz, Verkettung, Digest, Basisprofil, vorhandene Basisnutzlasten) und
hängt erst danach unter derselben Sperre an. Nur die Initialisierung darf
mit leerem Journal beginnen; danach ist ein gültiger
`workspace.initialised`-Eintrag mit dem Profil Pflicht; Record-Ereignisse
brauchen einen registrierten Record. Vor jedem Anhang wird am bereits
geöffneten Deskriptor die sichere Zeilengrenze geprüft: Ein nichtleeres
Journal ohne abschließenden LF wird abgewiesen (Verifikationsfehler),
unverändert, ohne automatische LF-Ergänzung, Kürzung oder Reparatur. Die
reine lesende Digestprüfung akzeptiert einen solchen Bestand weiterhin —
Schreibbarkeit und Digestgültigkeit sind verschieden. Erfolg erst nach
vollständigem Schreiben und `fsync`; Fehler melden den unbestätigten
Zustand ohne automatische Wiederholung. Keine Kürzung, Reparatur oder
Neuverkettung. Duplikate:
Workspace/Record einmalig (Widerspruch abgewiesen); Quelle bei gleichem
Record und Hash bereits registriert; Ergebnis bei gleichem Record,
Artefaktname und Hash dieselbe Fassung, sonst neue Fassung; Laufbelege und
Entscheidungen werden regulär angehängt.

## Einstiegspunkte (Bibliothek und CLI)

Python (`provenance_journal.api`): `init_journal`, `register_record`,
`ingest_source`, `produce_artifact`, `record_receipt`, `record_decision`
→ `WriteResult(event, appended)`; veränderliche Aufrufdaten (`inputs`,
verschachtelte `params`) werden vor jeder Prüfung in eigene tiefe Kopien
übernommen, sodass Validierung, Digest und gespeicherte Nutzlast dieselben
stabilen Daten verwenden. `read_events` und `verify_journal` liefern eine
Liste geprüfter `Event`-Kopien. `check_journal` liefert
`CheckReport(chain_ok, chain_error, events)` mit
`EventAssessment(seq, kind, outcome, fields, detail)` je Ereignis
(`outcome`: `valid` | `invalid` | `unchecked`). Fehler siehe
`provenance_journal.errors`: `ConfigError`, `VerificationError`
(`ChainError`, `DigestMismatch`, `ProfileError`, `PayloadError`),
`PayloadRejected` (neue Nutzlast, nichts geschrieben), `JournalIOError`
(`UnconfirmedWrite`, `JournalUnsafe`).

## Abgeleitete Ausgaben

`verify --json`, `history --json` und `check-artifact --json` sind
dokumentierte abgeleitete Ansichten mit Prüfreichweite, Ereignisfolge und
vollständigen Hashes (Strukturen: `docs/CLI.md`). Ein gefiltertes
Ereignisarray ist keine eigenständig prüfbare Originalkette. Jeder
Lesebefehl lädt genau einen Snapshot; Bericht und Auswertung verwenden
diesen Stand ohne erneute Dateilesung. Die Snapshot-Daten sind gegen
nachträgliche Mutation geschützt (Zugriffe geben eigene tiefe Kopien des
geprüften Stands zurück). Zuordnung nach voller Identität (Record,
Artefakt, Hash): Akte ohne registrierte Fassung zu genau dieser Identität
bleiben als ungebundene Akte mit vollem Gegenstandshash sichtbar. Die
aktuelle Fassung bestimmt die höchste passende `artifact.produced`-`seq`
im vollständigen Snapshot; Filter wählen nur aus und ändern nie den
Status. Aktive Filter müssen gemeinsam passen (Record über Hülle, Artefakt
über das direkte `artifact`-Feld, Hash über den direkten Gegenstandshash
der jeweiligen Art); Ereignisse ohne das gefilterte Feld passen nicht.
Jedes ursprüngliche Ereignis bleibt mit seiner vollständigen Nutzlast
einsehbar; die kompakte Fassung zeigt daneben die letzte unterstützte
Entscheidung nach `seq`. Ein ungültiges unterstütztes Basisereignis
ergibt bei allen drei Lesebefehlen Exit 1 mit Befund (`seq`, Feldnamen);
`unchecked`, `REJECT` und `WITHDRAW` sind keine Integritätsfehler. Alle
aus Journal oder Argumenten stammenden Terminalwerte erscheinen
JSON-quotiert. Gewöhnliche Öffnungs-, Lese- und Sperrfehler fallen in die
I/O-Fehlerdomäne (Exit 1, Diagnose ohne Traceback).

## Kompatibilitätsgrenzen

* Eigene v0.1-Bestände: voll les- und schreibbar.
* OHPIPE-Altbestände: lesbar mit explizitem Modus (Kette prüfbar,
  Spezialereignisse als fachlich nicht geprüft ausgewiesen),
  ausschließlich lesbar — keine Migration, keine Umschreibung.
* Der alte Root-Leser kann eine belegte Intent-Bindung nicht verifizieren;
  allgemeine beidseitige Alt-/Neu-Kompatibilität wird nicht zugesagt.
* Plattformen: Linux und macOS (POSIX-Sperren und -Öffnungen). Native
  Windows-Unterstützung folgt später. Geprüfte Kombinationen stehen im
  jeweiligen Prüfbericht der Lieferung.
