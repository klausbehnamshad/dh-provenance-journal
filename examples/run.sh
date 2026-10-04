#!/bin/bash
# Synthetisches Interview-Beispiel für provjournal (erfundene Inhalte).
#
# Ruft die installierte CLI auf (keine neue Schnittstelle, keine
# Abhängigkeit außer provjournal und python3 zum Hashlesen). Alle
# Journale, Lock-/Konfigurationsdateien und Kopien entstehen
# ausschließlich in einem neu angelegten Arbeitsverzeichnis: Ein bereits
# vorhandener Zielpfad wird vor jedem Kopieren und vor jeder Journalanlage
# verständlich abgewiesen. Wiederholung: neues Verzeichnis als erstes
# Argument übergeben.
#
# Die Transkription geschieht AUSSERHALB von provjournal; der Beleg
# dokumentiert nur die erklärte Ausführung.

set -euo pipefail

WORK="${1:-./arbeit-beispiel}"
SRC="$(cd "$(dirname "$0")" && pwd)"

if [ -e "$WORK" ]; then
  echo "FEHLER: $WORK existiert bereits; nichts kopiert, nichts angelegt." >&2
  echo "Neues Verzeichnis angeben: $0 ./mein-versuch" >&2
  exit 2
fi
if ! mkdir "$WORK" 2>/dev/null; then
  echo "FEHLER: $WORK kann nicht neu angelegt werden." >&2
  exit 2
fi
command -v provjournal >/dev/null || { echo "FEHLER: provjournal nicht auf PATH" >&2; exit 2; }

for f in quelle-interview.txt transkript-v1.txt transkript-v2.txt params.json; do
  cp "$SRC/$f" "$WORK/$f"
done
cd "$WORK"

J=(--journal journal.jsonl)
sagt() { echo "### $*"; }

sagt "1/9 init"
provjournal "${J[@]}" init
sagt "2/9 register"
provjournal "${J[@]}" register --record interview-01
sagt "3/9 ingest (Quelle erfassen)"
provjournal "${J[@]}" ingest --record interview-01 \
  --file quelle-interview.txt --media-type text/plain
sagt "4/9 artifact (Fassung 1 registrieren)"
provjournal "${J[@]}" artifact --record interview-01 \
  --artifact transkript --file transkript-v1.txt
sagt "5/9 receipt (Laufbeleg erklären)"
provjournal "${J[@]}" receipt --record interview-01 \
  --artifact transkript --output transkript-v1.txt \
  --input quelle=quelle-interview.txt --step transkription \
  --code-version leitfaden-v2 --params-file params.json
sagt "6/9 decide (ACCEPT zu Fassung 1)"
provjournal "${J[@]}" decide --record interview-01 \
  --artifact transkript --file transkript-v1.txt \
  --verdict ACCEPT --reference TR-2026-014 --actor "M. Beispiel" \
  --at "2026-10-03T12:00:00+00:00" --note "Erstprüfung bestanden"
sagt "7/9 artifact (Fassung 2 registrieren)"
provjournal "${J[@]}" artifact --record interview-01 \
  --artifact transkript --file transkript-v2.txt

sagt "8/9 verify (Kette und Basis getrennt prüfen)"
provjournal "${J[@]}" verify

sagt "9/9a decide (REJECT zu Fassung 1 — spätere Entscheidung, gleiche Identität)"
provjournal "${J[@]}" decide --record interview-01 \
  --artifact transkript --file transkript-v1.txt \
  --verdict REJECT --reference TR-2026-015 --actor "R. Zweitprüfung" \
  --at "2026-10-03T14:00:00+00:00" --note "Durch Fassung 2 ersetzt"

sagt "9/9b history (kompakt: letzter Akt nach seq; vollständig: alle Akte)"
provjournal "${J[@]}" history | grep -E "aktuelle Fassung|frühere Fassung|Entscheidung|Beleg"

sagt "9/9c check-artifact (Fassung 2 ist aktuell)"
provjournal "${J[@]}" check-artifact --record interview-01 \
  --artifact transkript --file transkript-v2.txt | grep "aktuelle Fassung"

sagt "Zusatz: Fassung 1 bleibt historisch mit ihren eigenen Akten sichtbar"
provjournal "${J[@]}" check-artifact --record interview-01 \
  --artifact transkript --file transkript-v1.txt | grep "historische Fassung"

sagt "Zusatz: veränderte, nicht registrierte Datei ergibt Exit 1"
cp transkript-v2.txt veraendert.txt
printf 'Nachtrag: ungültige Zeile.\n' >> veraendert.txt
set +e
negativ_ausgabe="$(provjournal "${J[@]}" check-artifact --record interview-01 \
  --artifact transkript --file veraendert.txt 2>&1)"
negativ_code=$?
set -e
if [ "$negativ_code" -ne 1 ]; then
  echo "FEHLER: veränderte Datei ergab Exit $negativ_code statt 1" >&2
  exit 1
fi
case "$negativ_ausgabe" in
  *"nicht registriert"*) echo "erwartet: Exit 1 (nicht registriert)" ;;
  *) echo "FEHLER: Negativprobe ohne vorgesehene Aussage" >&2; exit 1 ;;
esac

sagt "Zusatz: gefilterte Historie — frühere Fassung bleibt historisch"
V1="$(python3 -c 'import hashlib; print(hashlib.sha256(open("transkript-v1.txt","rb").read()).hexdigest())')"
filter_ausgabe="$(provjournal "${J[@]}" history --artifact transkript --sha256 "$V1")"
echo "$filter_ausgabe" | grep "frühere Fassung" >/dev/null \
  || { echo "FEHLER: gefilterte Fassung nicht historisch" >&2; exit 1; }
if echo "$filter_ausgabe" | grep -q "aktuelle Fassung"; then
  echo "FEHLER: Filter macht alte Fassung aktuell" >&2
  exit 1
fi

sagt "Zusatz: zugesagte Aussagen per JSON prüfen"
provjournal "${J[@]}" history --json > befund-voll.json
provjournal "${J[@]}" history --artifact transkript --sha256 "$V1" --json > befund-filter.json
python3 - befund-voll.json befund-filter.json <<'PY'
import json, sys
voll = json.load(open(sys.argv[1]))
filt = json.load(open(sys.argv[2]))
ansicht = next(a for r in voll["records"] for a in r["artifacts"])
fassungen = {r["sha256"]: r for r in ansicht["revisions"]}
assert len(fassungen) == 2, fassungen.keys()
v2 = next(s for s, r in fassungen.items() if r["current"] is True)
assert fassungen[v2]["seq"] == 7, "v2 seq 7"
v1 = next(s for s in fassungen if s != v2)
assert fassungen[v1]["current"] is False, "v1 historisch"
assert fassungen[v1]["seq"] == 4, "v1 seq 4"
spät = fassungen[v1]["latest_decision"]
assert (spät["verdict"], spät["seq"]) == ("REJECT", 8), spät
früh = [e["payload"].get("verdict") for e in voll["events"]
        if e["kind"] == "decision.recorded"]
assert "ACCEPT" in früh, "früheres ACCEPT weiter einsehbar"
assert ansicht["unbound_receipts"] == [], "keine offenen Akte"
assert ansicht["unbound_decisions"] == [], "keine offenen Akte"
gefiltert = filt["records"][0]["artifacts"][0]
assert [r["sha256"] for r in gefiltert["revisions"]] == [v1]
assert gefiltert["revisions"][0]["current"] is False, "Filter ohne Statuswechsel"
print("zusagen-ok")
PY

echo "BEISPIEL OK: $WORK/journal.jsonl"
