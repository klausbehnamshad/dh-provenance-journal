# Mein erstes Provenienzjournal

Diese Anleitung führt dich vom heruntergeladenen GitHub-Repo bis zu einem Journal
mit zwei Dateifassungen. Du brauchst keine Python-Programmierkenntnisse.
Die Befehle sind für die macOS-App **Terminal** geschrieben.

Wir verwenden den öffentlichen Stand von Version **0.1.0**
(Commit `3f434c19fb5808a229f6d914570045559e898371`). Die ZIP-Datei enthält den
Quellcode dieses Stands. Ein veröffentlichter GitHub-Release ist dafür nicht nötig.
Repo: [dh-provenance-journal](https://github.com/klausbehnamshad/dh-provenance-journal).

**So arbeitest du:** Führe die Blöcke nacheinander im selben Terminal aus.
Kopiere nur den Inhalt eines Befehlsblocks, keine Terminal-Prompts wie `$` oder
`(.venv)`. Prüfe nach jedem Schritt die angegebene Erwartung. Bei einem unerwarteten
Fehler hier bleiben und die Meldung notieren, statt die nächsten Schritte auszuführen.

## 1. Einen leeren Installationsordner öffnen

Öffne **Terminal** über Spotlight: **Cmd+Leertaste**, „Terminal“ eingeben, Enter.

```bash
mkdir -p ~/provjournal-install && cd ~/provjournal-install
ls -A
```

`~` bedeutet dein Benutzerordner. `mkdir` legt einen Ordner an, `cd` wechselt hinein.
**Damit ist noch nichts heruntergeladen oder installiert.**

Erwartung: `ls -A` zeigt nichts, der Ordner ist leer. Falls dort schon Dateien liegen,
verwende für diesen neuen Versuch einen anderen, leeren Ordner:

```bash
mkdir -p ~/provjournal-install-2 && cd ~/provjournal-install-2
ls -A
```

Ist auch dieser Ordner belegt, wähle entsprechend `provjournal-install-3` usw.
Die weiteren Befehle arbeiten relativ zum jetzt geöffneten Ordner und bleiben gleich.

## 2. Python prüfen

```bash
python3 --version
```

Erwartung: `Python 3.11…` oder neuer, zum Beispiel `Python 3.13.9`.
Bei `command not found` oder einer älteren Version zuerst Python 3.11 oder neuer
installieren und Terminal neu öffnen. Ein vorhandenes `(base)` im Terminal ist
kein Fehler; für das Tool richten wir gleich eine eigene Umgebung ein.

## 3. Das Repo herunterladen und entpacken

Du brauchst weder ein GitHub-Konto noch Git. Dieser Download ist ein festgelegter
Repo-Stand, damit du genau den hier beschriebenen Ablauf nachvollziehen kannst.

```bash
curl -fL https://github.com/klausbehnamshad/dh-provenance-journal/archive/3f434c19fb5808a229f6d914570045559e898371.zip -o repo.zip
```

Erwartung: Der Download endet ohne Fehlermeldung. Jetzt entpacken und den langen
Ordnernamen für die folgenden Schritte verkürzen:

```bash
unzip -q repo.zip
```

```bash
mv dh-provenance-journal-3f434c19fb5808a229f6d914570045559e898371 quellcode
ls quellcode
```

Erwartung: Du siehst unter anderem `README.md`, `pyproject.toml`, `src` und `docs`.
`quellcode` ist das heruntergeladene Programm. Deine Testdateien kommen später
in einen eigenen Ordner.

## 4. Eine eigene Python-Umgebung anlegen

```bash
python3 -m venv .venv
```

Erwartung: Der Befehl kehrt ohne Fehlermeldung zur Eingabe zurück.
Jetzt aktivieren:

```bash
source .venv/bin/activate
```

Erwartung: Am Anfang deiner Eingabezeile steht normalerweise `(.venv)`.
Die Umgebung liegt in diesem Installationsordner; das Tool wird dort installiert.

## 5. Das Tool aus dem heruntergeladenen Repo installieren

```bash
python -m pip install ./quellcode
```

Hierfür bleibt eine Internetverbindung nötig: `pip` kann Werkzeuge für den
Paketbau herunterladen. Das Journal selbst hat keine zusätzlichen
Laufzeitabhängigkeiten. Der Befehl installiert eine reguläre Kopie des Pakets;
der Quellcodeordner muss für spätere Journalaufrufe nicht dein Arbeitsordner sein.

Erwartung: Die Installation endet erfolgreich mit `dh-provenance-journal-0.1.0`.
Teste den neuen Befehl:

```bash
provjournal --help
```

Erwartung: Die Hilfe nennt neun Befehle: `init`, `register`, `ingest`, `artifact`,
`receipt`, `decide`, `verify`, `history`, `check-artifact`.

**Damit ist die Installation fertig.**

## 6. Einen eigenen Versuch beginnen

```bash
mkdir erster-versuch && cd erster-versuch
```

Falls `File exists` erscheint, einen neuen Namen wie `zweiter-versuch` verwenden.
Der Befehl wechselt nur dann hinein, wenn das Anlegen erfolgreich war.

Für eine Zeitmessung ab Beginn des eigentlichen Journalablaufs:

```bash
date -u +%Y-%m-%dT%H:%M:%SZ | tee START.txt
```

Die Zeit ist in UTC. Sie umfasst anschließend auch dein Lesen und Nachdenken.

### Die Begriffe in diesem Versuch

| Begriff | Bedeutung hier |
|---|---|
| Journal | `journal.jsonl`: fortlaufende Ereignisliste mit Hashverkettung |
| Record | `r1`: Kennung für deinen Arbeitsgegenstand, etwa ein Interview |
| Quelle | `quelle.txt`: Ausgangsdatei |
| Artefakt | `memo`: gleichbleibender Name für ein Ergebnis, das mehrere Fassungen haben kann |
| Fassung | Konkrete Dateibytes; hier `memo-v1.txt` und später `memo-v2.txt` |
| Beleg (`receipt`) | Deine Erklärung, wie eine Ergebnisfassung entstanden ist |
| Entscheidung | Deine Zustimmung oder Ablehnung zu genau einer Fassung |

`r1` und `memo` sind frei gewählte Kennungen, keine Pfade. Wir verwenden sie in
allen Befehlen gleich. Unterschiedliche Fassungsdateien gehören zum selben `memo`.

## 7. Eine Quelle schreiben und die erste Fassung erstellen

```bash
cat > quelle.txt
```

Jetzt wartet Terminal auf Text. Schreibe zwei eigene, unverfängliche Testsätze,
jeweils eine Zeile. Nach der letzten Zeile **Enter**, dann **Ctrl+D** drücken.
Dadurch endet die Texteingabe und die normale Eingabezeile erscheint wieder.

Deine Quelle ansehen:

```bash
cat quelle.txt
```

Nun eine unveränderte Kopie als erste Ergebnisfassung herstellen:

```bash
cp quelle.txt memo-v1.txt
```

Das Kopieren ist unser erster tatsächlich ausgeführter Arbeitsschritt.
Das Journal erstellt oder verarbeitet keine Dateien für dich.

## 8. Journal, Record und Quelle erfassen

Die globale Option `--journal journal.jsonl` steht immer **vor** dem jeweiligen
Befehl. Führe die Befehle einzeln aus:

```bash
provjournal --journal journal.jsonl init
```

Erwartung: initialisiert, `seq 1`. `seq` ist die laufende Ereignisnummer.

```bash
provjournal --journal journal.jsonl register --record r1
```

Erwartung: Record registriert, `seq 2`.

```bash
provjournal --journal journal.jsonl ingest --record r1 --file quelle.txt --media-type text/plain
```

Erwartung: Quelle erfasst, `seq 3`. Hash und Dateigröße berechnet das Tool selbst.
Der Journal-Eintrag enthält Metadaten und Hash, nicht den Inhalt der Datei.

## 9. Erste Fassung und Arbeitsschritt dokumentieren

```bash
provjournal --journal journal.jsonl artifact --record r1 --artifact memo --file memo-v1.txt
```

Erwartung: Fassung registriert, `seq 4`.

```bash
provjournal --journal journal.jsonl receipt --record r1 --artifact memo --output memo-v1.txt --input quelle=quelle.txt --step 'unveraenderte Kopie' --code-version manuell-v1
```

Erwartung: Laufbeleg angehängt, `seq 5`.

`--input quelle=quelle.txt` sagt: Die Eingabe mit der Rolle „quelle“ ist diese Datei.
`--output` ist deine Ergebnisdatei. `--step` beschreibt die von dir ausgeführte
Kopie. `manuell-v1` bezeichnet hier den manuellen Arbeitsschritt; das Tool führt
kein Programm dieses Namens aus. Der Beleg hält deine Erklärung fest, beweist
aber nicht selbst, dass die Verarbeitung stattgefunden hat.

## 10. Eine Entscheidung über die erste Fassung festhalten

```bash
provjournal --journal journal.jsonl decide --record r1 --artifact memo --file memo-v1.txt --verdict ACCEPT --reference TEST-01 --actor 'Testperson'
```

Erwartung: Entscheidung `ACCEPT` angehängt, `seq 6`.

`ACCEPT` bedeutet: Du erklärst deine Zustimmung zu genau diesen Dateibytes.
`TEST-01` ist deine Entscheidungsreferenz, `Testperson` der angegebene Akteur.
Im echten Gebrauch wählst du eine passende Referenz und deinen eigenen Namen.
Das Tool prüft nicht, ob eine wissenschaftliche Aussage richtig ist.

## 11. Prüfen und die Ausgabe lesen

```bash
provjournal --journal journal.jsonl verify
```

Erwartung:

```text
Kette: gültig (6 Ereignisse)
Basis: 6 gültig, 0 ungültig, 0 fachlich ungeprüft
```

Das bestätigt die innere Konsistenz des vorliegenden Journals und seines
Basisprofils. Es ist keine wissenschaftliche Begutachtung.

```bash
provjournal --journal journal.jsonl history
```

Erwartung: Die sechs Ereignisse erscheinen in Reihenfolge. Darunter steht
`memo` als aktuelle Fassung mit Beleg `seq 5` und Entscheidung `ACCEPT`, `seq 6`.
Quelle und Kopie haben denselben Hash, weil ihre Bytes identisch sind.

```bash
provjournal --journal journal.jsonl check-artifact --record r1 --artifact memo --file memo-v1.txt
```

Erwartung: registriert, aktuelle Fassung `seq 4`, Beleg `seq 5`, Zustimmung `seq 6`.
Dieser Befehl ordnet die tatsächlich vorliegende Datei ihrer Journalfassung zu.

## 12. Eine zweite Fassung anlegen und verändern

```bash
cp memo-v1.txt memo-v2.txt
cat >> memo-v2.txt
```

Schreibe einen zusätzlichen Testsatz. Danach **Enter**, dann **Ctrl+D**.
`>>` hängt Text an; die erste Fassung bleibt als eigene Datei erhalten.

```bash
provjournal --journal journal.jsonl verify
```

Erwartung: weiterhin sechs gültige Ereignisse. Eine Dateiänderung erzeugt nicht
automatisch einen Journal-Eintrag.

```bash
provjournal --journal journal.jsonl check-artifact --record r1 --artifact memo --file memo-v2.txt
echo $?
```

Erwartung: **nicht registriert** und darunter **1**.
Das ist der gewünschte Befund: Der neue Hash gehört noch zu keiner registrierten
Fassung. `echo $?` zeigt den Rückgabecode des unmittelbar davor ausgeführten
Befehls. Führe dazwischen keinen anderen Befehl aus.

## 13. Die zweite Fassung registrieren, zunächst ohne Zustimmung

```bash
provjournal --journal journal.jsonl artifact --record r1 --artifact memo --file memo-v2.txt
```

Erwartung: Fassung registriert, `seq 7`.

```bash
provjournal --journal journal.jsonl check-artifact --record r1 --artifact memo --file memo-v2.txt
```

Erwartung: aktuelle Fassung `seq 7`, **keine unterstützte Entscheidung zu dieser
Fassung**. Deine frühere Zustimmung galt für die erste Fassung und wird nicht
auf die veränderte Datei übertragen. Auch ein passender Laufbeleg fehlt noch.

## 14. Ergänzung und neue Zustimmung dokumentieren

```bash
provjournal --journal journal.jsonl receipt --record r1 --artifact memo --output memo-v2.txt --input vorfassung=memo-v1.txt --step 'manuelle Ergaenzung' --code-version manuell-v2
```

Erwartung: Laufbeleg `seq 8`. Er erklärt die Ergänzung, die du selbst vorgenommen hast.

```bash
provjournal --journal journal.jsonl decide --record r1 --artifact memo --file memo-v2.txt --verdict ACCEPT --reference TEST-02 --actor 'Testperson'
```

Erwartung: eigene Zustimmung zur zweiten Fassung, `seq 9`.

## 15. Beide Fassungen vergleichen und abschließen

```bash
provjournal --journal journal.jsonl history
provjournal --journal journal.jsonl check-artifact --record r1 --artifact memo --file memo-v1.txt
provjournal --journal journal.jsonl check-artifact --record r1 --artifact memo --file memo-v2.txt
provjournal --journal journal.jsonl verify
```

Erwartung:

| Datei | Status | Fassung | Beleg | Eigene Zustimmung |
|---|---|---|---|---|
| `memo-v1.txt` | historisch / frühere Fassung | `seq 4` | `seq 5` | `seq 6`, `TEST-01` |
| `memo-v2.txt` | aktuell | `seq 7` | `seq 8` | `seq 9`, `TEST-02` |

Kette und Basis melden jetzt **neun gültige Ereignisse**.
Die erste Zustimmung ist weiterhin bei der ersten Fassung einsehbar.

```bash
date -u +%Y-%m-%dT%H:%M:%SZ | tee ENDE.txt
```

Halte für deine zweite Erprobung kurz fest: Dauer zwischen `START.txt` und
`ENDE.txt`, unklare Begriffe, Fehlermeldungen und benötigte Hilfe. Eine erfolgreiche
Befehlsausführung und die Verständlichkeit der Anleitung sind getrennte Beobachtungen.

Zum Beenden der Python-Umgebung:

```bash
deactivate
```

Alle Dateien bleiben erhalten. Das Journal archiviert deine Arbeitsdateien nicht;
bewahre Quelle, Fassungen, `journal.jsonl` und `journal.jsonl.config.json` gemeinsam auf.

## Später wieder einsteigen

Für den ersten Installationsordner aus Schritt 1:

```bash
cd ~/provjournal-install
source .venv/bin/activate
cd erster-versuch
provjournal --journal journal.jsonl history
```

Wenn du einen anderen Installations- oder Versuchsnamen gewählt hast, passe nur
diese Ordnernamen an. Zum Weiterlesen reichen `history`, `verify` und
`check-artifact`; du musst nicht erneut installieren oder initialisieren.

Für einen **neuen, unabhängigen Versuch** aktivierst du dieselbe Umgebung,
wechselst in den Installationsordner und wiederholst Schritt 6 mit einem neuen
Versuchsordnernamen. Danach geht es bei Schritt 7 weiter. Verwende das bestehende
Journal nicht als leere Übung, sonst stimmen die hier erwarteten Ereignisnummern
nicht mehr.

## Wenn etwas nicht klappt

| Meldung oder Situation | Nächster Schritt |
|---|---|
| `python3: command not found` oder Python älter als 3.11 | Passendes Python installieren; dann bei Schritt 1 beginnen. |
| `provjournal: command not found` | Im Installationsordner `source .venv/bin/activate` ausführen; Installation aus Schritt 5 prüfen. |
| Download scheitert | Internetverbindung und vollständige URL prüfen; erst nach erfolgreichem Download entpacken. |
| `File exists` bei `mkdir` | Einen neuen Versuchsnamen wählen; bestehende Dateien erhalten. |
| `nicht registriert`, Exit 1 in Schritt 12 | Erwartet; danach bei Schritt 13 weitergehen. |
| `Kette` oder `Basis` ungültig | Originaldateien erhalten, Fehlermeldung notieren und Unterstützung holen. Journal nicht manuell bearbeiten. |

Bei einer Frage den ausgeführten Befehl und seine vollständige Ausgabe nennen.
Die vertiefenden Unterlagen liegen im heruntergeladenen Repo unter
`quellcode/docs/CLI.md`, `quellcode/docs/NUTZUNG.md` und
`quellcode/docs/WIEDERHERSTELLUNG.md`.
