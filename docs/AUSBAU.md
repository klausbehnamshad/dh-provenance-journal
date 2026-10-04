# Ausbauübersicht (nach v0.1)

v0.1 enthält Schreibfunktionen, Verifikation, Terminalhistorie und
JSON-Ausgabe sowie ein synthetisches Beispiel. Die folgenden Stufen
werden anhand der Nutzung priorisiert und können bei konkretem Bedarf
vorgezogen werden. Jede Erweiterung erhält eigene Abnahmen.

| Stufe | Inhalt | Ziel |
|---|---|---|
| A1 Bedienung | Lokaler HTML-Viewer, bequemere Eingabe, bessere Diagnosen, erste Pilotbeobachtungen | Quellenfassung, Laufbeleg und Entscheidung werden ohne Kenntnis des Codes gefunden |
| A2 Herkunft und Projektpolicy | Herkunftsgraph, Abhängigkeiten, Staleness-Berechnung, explizite Profile, geprüfter Anschluss | Änderungen werden entlang erfasster Beziehungen sichtbar |
| A3 Format und Verifikation | Versionierte Ereignisschemas, Journal-ID, Kompatibilitätsvertrag, externe Checkpoints, kontrollierte Wiederherstellung | Alte Journale bleiben lesbar; verkürzte Stände werden erkannt |
| A4 Mündliche Quellen | Lesender TEI-Adapter mit Quellen-URI, Fassungsidentität und Segmentankern | Segment- und Timecode-Bezüge bleiben zuordenbar |
| A5 Standards und Nachweise | PROV-O-Export, anschließend RO-Crate; ausdrückliche Metadaten-Auswahl | IDs, Herkunft und Entscheidungsbindung bleiben erhalten |
| A6 Weitere Betriebsformen | Befehlsprotokollierung, Signaturen, Schlüsselrotation, weitere Plattformen, gemessene Optimierung | Jede Erweiterung mit eigenen Abnahmen |

Nicht in v0.1: Datenbankindex (erst bei gemessenem Bedarf), Windows-
Unterstützung, Graphoberflächen, Fachadapter, Signaturen.
