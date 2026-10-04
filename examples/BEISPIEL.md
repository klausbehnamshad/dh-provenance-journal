# Deutsches Anwendungsbeispiel: Interview-Transkript (synthetisch)

Alle Inhalte sind erfunden; keine echte Person, kein echtes Interview.
Die Dateien liegen unter `examples/`:

| Datei | Rolle |
|---|---|
| `quelle-interview.txt` | Transkriptquelle (erfundener Interviewausschnitt) |
| `transkript-v1.txt` | Abgeleitetes Ergebnis, Fassung 1 |
| `transkript-v2.txt` | Abgeleitetes Ergebnis, Fassung 2 (präzisiert) |
| `params.json` | Verwendete Leitfaden-Parameter |
| `run.sh` | Ausführbarer Ablauf über die installierte CLI |

## Start

Vom Repository-Root aus (oder nach `cd examples` mit angepasstem Ziel):

```bash
examples/run.sh ./mein-versuch
```

`run.sh` ruft alle neun Befehle auf (`init`, `register`, `ingest`,
`artifact`, `receipt`, `decide`, `verify`, `history`, `check-artifact`)
und zeigt danach vier Situationen. Das Ziel muss neu sein: Ein bereits
vorhandener Zielpfad wird vor jedem Kopieren und vor jeder Journalanlage
abgewiesen (Exit 2) — vorhandene Dateien, etwa eigene Notizen, bleiben
unverändert. Für einen neuen Durchlauf ein neues Verzeichnis angeben.

## Was das Beispiel zeigt

1. **Laufbeleg statt Ausführung.** `receipt` erklärt den Transkriptionslauf
   (Eingabe als Rolle-zu-Hash `quelle=...`, Schritt `transkription`,
   Code-Version `leitfaden-v2`, Params aus `params.json`). Die Verarbeitung
   selbst geschieht außerhalb von `provjournal`; der Beleg dokumentiert die
   erklärte Ausführung — keinen Nachweis tatsächlicher Ausführung.
2. **Menschliche Entscheidung.** `decide` bindet `ACCEPT`
   (Referenz `TR-2026-014`, Akteurin `M. Beispiel`, zeitzonenbehaftete Zeit,
   Note) an genau die Bytes von Fassung 1.
3. **Zweite Fassung.** `artifact` registriert Fassung 2; Fassung 1 bleibt
   historisch und mit ihren eigenen Akten sichtbar (`check-artifact`
   meldet „historische Fassung“ mit `seq`).
4. **Späterer REJECT zur gleichen Identität.**
   `TR-2026-015` (`R. Zweitprüfung`) entscheidet über dieselben Bytes wie
   zuvor `ACCEPT`. Die kompakte Ansicht zeigt den letzten Akt nach `seq`;
   die vollständige Historie löscht den früheren nicht.
5. **Veränderte Datei.** Eine lokal ergänzte, noch nicht registrierte Datei
   ergibt bei `check-artifact` genau Exit 1 mit „nicht registriert“ —
   jeder andere Ausgang lässt den Beispieldurchlauf scheitern.
6. **Gefilterte Historie.** `history --artifact transkript --sha256 …`
   zeigt Fassung 1 als „frühere Fassung“ — der Filter wählt aus, macht die
   alte Fassung aber nie zur aktuellen. Abschließend prüft das Skript alle
   zugesagten Aussagen maschinell über die JSON-Ansicht (v2 aktuell mit
   seq 7, v1 historisch mit seq 4 und REJECT seq 8, früheres ACCEPT weiter
   einsehbar, keine offenen Akte, Filter ohne Statuswechsel).

## Eigene Fassungen aufbewahren

Das Journal archiviert keine Inhalte, nur Hashes und Metadaten. Wer mit
Fassung 1 weiterarbeiten will, bewahrt die Datei `transkript-v1.txt`
selbst auf — im Beispiel bleibt sie neben Fassung 2 im
Arbeitsverzeichnis liegen.
