# `provjournal` — Befehle, Exits, JSON und Prüfreichweite

Stand 3. Oktober 2026 (Aufträge 02/02A). Die CLI schreibt ausschließlich über
die öffentliche Bibliothek; sie führt keine Programme aus und archiviert
keine Dateien. Hash und Größe stammen aus denselben am Handle gelesenen
Rohbytes. Installierbar als `provjournal` (`[project.scripts]`) sowie
`python -m provenance_journal`. Keine Laufzeitabhängigkeiten.

## Aufrufform

```
provjournal --journal PATH [--integrity sha256|hmac] [--key-file PATH] BEFEHL ...
```

`--journal` ist auf `./journal.jsonl` vorbelegt; das Elternverzeichnis
muss vorhanden sein (der Schreibpfad legt nichts an). SHA-256 ist nur bei
neuer Initialisierung der Standard; für bestehende Journale gelten
Konfiguration und explizite Moduswahl. `--key-file` und `PROVJOURNAL_KEY`
enthalten Dateipfade, keine Schlüsseltexte (Lage- und Mindestlängenprüfung
wie im Kern; Schlüssel außerhalb der Datenwurzel).

## Befehle

| Befehl | Wirkung |
|---|---|
| `init` | Basisprofil initialisieren; identische Wiederholung meldet bereits vorhanden |
| `register --record ID` | Eigenen Record registrieren |
| `ingest --record ID --file PATH --media-type TYPE` | Quelle erfassen (SHA-256, Größe, Basename selbst berechnet) |
| `artifact --record ID --artifact ID --file PATH` | Ergebnisfassung mit selbst berechnetem Dateihash |
| `receipt --record ID --artifact ID --output PATH --input ROLE=PATH ... --step TEXT --code-version TEXT [--params-file PATH]` | Deterministischen Laufbeleg erklären (`--input` wiederholbar, Rollen eindeutig; Params-Datei muss JSON-Objekt enthalten) |
| `decide --record ID --artifact ID --file PATH --verdict ACCEPT\|REJECT\|WITHDRAW --reference TOKEN --actor TEXT [--at ZEIT] [--note TEXT]` | Entscheidung an die Bytes der Datei binden (`--at` zeitzonenbehaftet, Standard: jetzt in UTC) |
| `verify [--json]` | Ketten- und Basisprüfung mit Prüfreichweite |
| `history [--record ID] [--artifact ID] [--sha256 HASH] [--json]` | Ereignisse mit Details, Fassungen mit Belegen/Entscheidungen; Filter erzeugen eine abgeleitete Auswahl, ändern aber nie den Fassungsstatus |
| `check-artifact --record ID --artifact ID --file PATH [--json]` | Bereitgestellte Bytes zuordnen: voller Hash, registriert ja/nein, aktuelle/historische Fassung, passende Belege, letzte unterstützte Entscheidung mit `seq`, dazu Ketten-/Basisbefunde |

## Exits

| Fall | Exit |
|---|---|
| Technisch erfolgreich, auch echte Registrierungsduplikate | 0 |
| Konfiguration fehlt/unbrauchbar; ungültige Argumente oder neue Nutzlast | 2 |
| Kette/Digest oder Basisvertrag ungültig; Journal-/Datei-I/O; unbestätigter Schreibzustand; `check-artifact` ohne zugeordnete Bytes | 1 |

Ein ungültiges unterstütztes Basisereignis ergibt bei `verify`,
`history` und `check-artifact` Exit 1 mit sichtbarem Befund (`seq`,
Feldnamen) — in Terminal- und JSON-Ausgabe. Gültige Einzelzuordnungen
bleiben daneben sichtbar; kein Filter verdeckt den globalen Prüfbefund.
Fachlich ungeprüfte Spezialereignisse (`unchecked`) sowie `REJECT` und
`WITHDRAW` sind keine Integritätsfehler. Fehlt das Journal oder ist es
leer, melden die Prüf-/Historienbefehle einen Befund mit Exit 1 und legen
nichts an. Benutzerfehler kommen ohne Traceback; ein brauchbarer falscher
HMAC-Schlüssel bleibt Exit 1 mit vorsichtiger Diagnose. Alle aus Journal
oder Argumenten stammenden Terminalwerte erscheinen JSON-quotiert —
insbesondere unbekannte Ereignisarten in Ereignis- und Befundzeilen.

## Filterregel

Aktive Filter müssen gemeinsam passen. Der Record passt über die Hülle,
das Artefakt über das direkt vorhandene `artifact`-Feld, der Hash über den
direkten Gegenstandshash der jeweiligen Art (Quelle/Artefakt `sha256`,
Beleg `output_sha256`, Entscheidung `subject_sha256`). Input-Hashes
begründen keinen zusätzlichen Treffer; Ereignisse ohne das gefilterte Feld
passen nicht. Die Regel gilt einheitlich für Fassungen, ungebundene Akte
sowie Terminal- und JSON-Ereignislisten. Die aktuelle Fassung bestimmt die
höchste passende `artifact.produced`-`seq` im vollständigen Snapshot —
auch bei wiederholter Registrierung älterer Hashes (A→B→A); sie muss in
einer gefilterten Auswahl nicht selbst erscheinen.

## JSON-Strukturen (abgeleitete Ansichten)

`verify --json`: `{"command","journal","chain":{"ok","events"},"basis":[{"seq","kind","outcome","fields","detail"}],"summary":{"valid","invalid","unchecked"},"scope_note"}`.
`history --json`: `{"command","journal","view":"full"|"derived","filters","events":[{"seq","kind","record_id","outcome","fields","payload"}],"records":[{"record_id","artifacts":[{"artifact","revisions":[{"sha256","seq","current","receipts":[{"seq","step","code_version","output_sha256","inputs","params"}],"latest_decision":{"seq","verdict","reference","actor","at","note","subject_sha256"}|null}],"unbound_receipts":[...],"unbound_decisions":[...]}]}],"findings":[...],"scope_note"}`.
`check-artifact --json`: `{"command","journal","record_id","artifact","sha256","registered","currency":"current"|"historical"|"unregistered","revision_seq","receipts","latest_decision","findings","basis_summary":{"invalid","unchecked"},"scope_note"}`.
Die Ereignisliste trägt je Ereignis die vollständige Originalnutzlast
(Quellenhash, Dateiname, Größe, Medientyp; Receipt-Inputs, Schritt,
Codeversion, Params; jede Entscheidung mit Verdikt, Referenz, Akteur,
Zeitpunkt, Note); die kompakte Fassung daneben nur die letzte
unterstützte Entscheidung nach `seq`. Alle Hashes sind vollständig; ein
gefiltertes Ereignisarray ist keine eigenständig prüfbare Originalkette.
`--json` schreibt bei erfolgreich gelesener Ansicht genau ein Objekt
nach stdout; Diagnosen gehören nach stderr. Frühe Konfigurations-,
I/O- oder Kettenfehler brechen mit Diagnose und ohne JSON-Ansicht ab.
Bei Kettenfehler keine Historie als verifiziert ausgeben.

## Prüfreichweite

Jeder Lesebefehl lädt genau einen Snapshot: einmal lesen und verifizieren
(mit Lockpfadschutz, ohne Lockdatei anzulegen); Bericht und Auswertung
verwenden diesen Stand ohne erneute Dateilesung. Die Snapshot-Daten sind
gegen nachträgliche Mutation geschützt — jeder Zugriff gibt eigene tiefe
Kopien des geprüften Stands zurück; veränderte Kopien tragen keine alten
Bewertungen weiter. Zuordnung nach voller Identität (Record, Artefakt,
Hash): Ein Beleg oder eine Entscheidung ohne registrierte Fassung zu
genau dieser Identität bleibt als ungebundener Akt mit vollem
Gegenstandshash sichtbar — auch bei vorhandenem Artefaktnamen mit anderen
Fassungen. Letzte Entscheidung nach `seq`. Neue Bytes übernehmen keine
fremde Entscheidung; Belege belegen keine Ausführung; keine
Staleness-Berechnung. Ein digestgültiger LF-loser Bestand bleibt lesbar
und verbietet Anhang; Einzelpayload-gültig heißt nicht gesamt-schreibbar.
Die Beistelldatei wird mit denselben sicheren Lesehilfen geöffnet wie
Eingabedateien (`O_NOFOLLOW`, `O_NONBLOCK`, `S_ISREG` am geöffneten
Deskriptor): FIFO, Verzeichnis, Link und unlesbare Konfiguration sind
Konfigurationsfehler (Exit 2), ohne Hänger.
