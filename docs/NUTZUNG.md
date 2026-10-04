# Nutzung: Ausgaben lesen und Grenzen beachten

Ergänzt `CLI.md` (Befehle, Exits, JSON) und `FORMAT.md` (Formatvertrag)
um Deutung und Grenzen für Fachkolleginnen und -kollegen.

## Drei Prüfungen, getrennt lesen

- **Kette/Digest** (`verify`, `chain`): Folgenummern lückenlos, Verkettung
  geschlossen, Digests nachgerechnet (SHA-256 oder HMAC). Gültig heißt:
  Der vorliegende Bestand ist in sich konsistent — nicht mehr. Wer Zeilen
  ändert und sämtliche Digests neu berechnet, erhält einen anderen, ebenso
  gültigen Bestand; ohne unabhängig aufbewahrten Vergleichsstand erkennt
  die Prüfung das nicht. HMAC verlangt für eine solche Neuberechnung den
  passenden Schlüssel und belegt damit Schlüsselbesitz — keine
  Personenidentität.
- **Basisbewertung** (`basis`, `findings`): Jede gespeicherte Nutzlast
  einzeln gegen das Basisprofil geprüft. `valid` = vertragskonform;
  `invalid` = unterstützte Art mit verletztem Feldvertrag (Exit 1, mit
  Ereignisnummer und Feldnamen); `unchecked` = Kette prüfbar, Fachsemantik
  nicht geprüft (fremde Art, nicht-deterministischer Beleg, `UNDO`).
- **Ergebniszuordnung** (`history`, `check-artifact`): volle Identität aus
  Record-ID, Artefaktname und vollständigem Hash; letzte Registrierung und
  letzte Entscheidung nach `seq`, niemals nach Zeitstempel.

Technischer Erfolg und `ACCEPT` ergeben **keine wissenschaftliche
Freigabe** des Projekts. Das Journal dokumentiert erfasste Beziehungen
und die Reihenfolge der Einträge. Es beweist weder die Vollständigkeit
der Interviewgeschichte noch die tatsächliche Ausführung eines Schritts
oder den realen Zeitpunkt. Dateiinhalt und wissenschaftliche Richtigkeit
werden dadurch nicht bestätigt; Dateien werden nicht archiviert.
Die letzte registrierte Fassung ist nicht automatisch die beste oder
freigegebene Fassung. Praktische Gegenmaßnahmen und kurze Merksätze stehen
in der [Argumentation auf Deutsch und Englisch](ARGUMENTATION-DE-EN.md).

## Identität, Fassungen, Filter, ungebundene Akte

- Eine Fassung ist genau ein (Record, Artefaktname, Hash)-Tripel. Neue
  Bytes übernehmen keine Entscheidung einer anderen Fassung — auch nicht
  bei gleichem Hash in anderem Record oder unter anderem Namen.
- Aktuell ist die Fassung mit der höchsten passenden
  Registrierungs-`seq`; alle anderen sind historisch, bleiben aber mit
  ihren eigenen Belegen und Entscheidungen prüfbar.
- Filter wählen aus und ändern nie den Status. Mehrere Filter müssen
  gemeinsam passen (Record über Hülle, Artefakt über das direkte Feld,
  Hash über den direkten Gegenstandshash); Input-Hashes zählen nicht.
- Belege/Entscheidungen ohne registrierte Fassung zu genau ihrer
  Identität erscheinen als **ungebundene Akte** mit vollem Hash — kein
  Verlust, keine automatische Zuordnung.
- Die JSON-Ansicht ist abgeleitet: kein eigenständig prüfbarer
  Originalkettenauszug. Wer Kette prüfen will, prüft die Datei. Ein
  JSON-Objekt entsteht nur bei erfolgreich gelesener Ansicht; frühe
  Konfigurations-, I/O- oder Kettenfehler brechen mit Diagnose auf stderr
  und ohne JSON-Ansicht ab.

## Bytes, Archivierung, Felder

- Gehasht werden unveränderte Dateibytes (keine Normalisierung). Das
  Journal enthält Metadaten und Hashes; **Dateien werden nicht
  archiviert**. Wer Fassungen braucht, bewahrt die Dateien selbst auf.
- Verbotene Nutzlastfelder (`name`, `text`, `value`, …) sind eine
  Feldbeschränkung, **kein Nachweis unbedenklicher Inhalte**: Notizen,
  Dateinamen, Akteure und Parameter können sensible Angaben tragen.

## Modus, Schlüssel, Exits

- Der Modus steht in `<journal>.config.json` neben dem Journal.
  Bestehende Journale ohne Konfiguration verlangen eine explizite
  Moduswahl; es gibt kein Ausprobieren und keinen Fallback (Exit 2 bei
  Widerspruch oder unbrauchbarer Konfiguration).
- `PROVJOURNAL_KEY` und `--key-file` nennen Dateipfade; der Schlüssel
  liegt außerhalb der Datenwurzel (mindestens 16 Bytes). HMAC belegt
  Schlüsselbesitz, **keine Personenidentität**.
- Exits: 0 Erfolg (auch Duplikate), 2 Konfiguration/Argumente/neue
  Nutzlast, 1 Kette/Basis/I-O/unbestätigt/nicht zugeordnet. Diagnosen
  kommen ohne Traceback nach stderr; `--json` liefert genau ein Objekt.
- Eine gültige Verkürzung (fehlende Endzeilen bei sonst gültiger Kette)
  bleibt ohne externen Vergleichsstand unentdeckt; Checkpoints folgen in
  einer späteren Ausbaustufe.
