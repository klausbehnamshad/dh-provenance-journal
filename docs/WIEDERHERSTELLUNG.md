# Wiederherstellung: nach Fehlern und bei beschädigter Kette

Kurzer Leitfaden für den Störungsfall. Es gibt **keine
Reparaturfunktion**: Das Journal wird nie gekürzt, neu verkettet oder
still ergänzt. Jede Wiederaufnahme beginnt mit Prüfung und Dokumentation.

## Unbestätigter Schreibzustand (Schreib-/fsync-Fehler)

Die CLI meldet den unbestätigten Zustand (Exit 1); es kann ein teilweise
oder vollständig geschriebenes, aber unbestätigtes Ereignis vorhanden
sein.

1. Schreiber stoppen. Keinen automatischen fachlichen Wiederholversuch
   starten.
2. Das Original (Journal, Beistell- und Lockdatei) unverändert sichern,
   z. B. in ein separates Verzeichnis kopieren.
3. Mit passendem Modus und Schlüssel prüfen:
   `provjournal --journal PFAD verify` (bei Altbestand zusätzlich
   `--integrity sha256|hmac` mit Schlüsseldatei).
4. Ist die Kette gültig, anhand von `history` klären, ob der fragliche
   Vorgang bereits als Ereignis vorhanden ist. Nur was fehlt, darf
   erneut angehängt werden — mit erneuter Prüfung vorher.

## Beschädigte Kette (Bruch, Digestfehler, ungültige Bytes)

1. Befund festhalten: vollständige Diagnose, betroffene `seq`,
   Dateigröße und -zeit des Originals.
2. Einen vorhandenen Backupstand in einem **neuen** Arbeitsverzeichnis
   wiederherstellen (nicht über das Original kopieren), passend
   konfigurieren (Modus, Schlüssel) und erneut prüfen (`verify`, Exit 0
   abwarten).
3. Original, Befund und möglichen Rückstand (Ereignisse nach dem Backup)
   dokumentieren; Rückstand fachlich neu bewerten, nicht aus dem
   beschädigten Stand übernehmen.
4. Ohne gültiges Backup: Arbeit anhalten. Keine Zeilen abschneiden, keine
   Digests neu berechnen, keine Kette neu knüpfen.

## Für Fortsetzung geeigneter Backupstand

Verifizierbar ist nicht fortsetzbar: Für Weiterarbeit braucht der
Backupstand zusätzlich ein gültiges Basisprofil, eine vollständige
letzte Zeile mit LF sowie passende Konfiguration und Schlüssel. Erst
wenn `verify` Exit 0 meldet **und** ein Anhang gelingt, ist die
Fortsetzung im neuen Verzeichnis dokumentiert aufgenommen.

Liegt ausschließlich ein LF-loser (sonst digestgültiger) oder anderweitig
nicht fortsetzbarer Backupstand vor, bleibt Schreiben angehalten: Er
liefert `verify`/`history` mit Exit 0, verweigert jeden Anhang ohne
Byteänderung und gilt nicht als erfolgreiche Fortsetzung. Keine
Probeereignisse zur Feststellung der Schreibbarkeit eintragen, kein LF
heimlich ergänzen oder kürzen.

## Lesbar, aber nicht schreibbar (fehlender Zeilenumbruch am Ende)

Ein digestgültiger Bestand ohne abschließenden LF meldet bei `verify`
und `history` Erfolg, verweigert aber jeden Anhang (Exit 1, Bestand
unverändert). Das ist kein normaler Wiederholungsfall: kein LF heimlich
ergänzen. Für Weiterarbeit gilt der geeignete Backupstand oben — sonst
bleibt die Arbeit angehalten.

## Fehlendes oder leeres Journal

Die Prüf-/Historienbefehle melden einen Befund mit Exit 1 und legen
nichts an. Neu beginnen heißt: `init` in einem dafür vorgesehenen
Verzeichnis — niemals „zur Reparatur“ über einen beschädigten Stand.

## Merksätze

- Prüfen vor Wiederholen; dokumentieren vor Wiederherstellen.
- Ein Backup zählt nur geprüft (`verify`, Exit 0, mit Modus/Schlüssel).
- Was das Journal nicht enthält (Dateiinhalte), stellt kein Wiederher-
  stellungsverfahren wieder her — Fassungsdateien separat sichern.
