# Prüfstand (v0.1.0-Kandidat)

Geprüft wird der Stand auf `main` des Repositorys
<https://github.com/klausbehnamshad/dh-provenance-journal>.
Echte CI-Läufe: [Alle Workflow-Läufe](https://github.com/klausbehnamshad/dh-provenance-journal/actions)
und [CI-Fluss](https://github.com/klausbehnamshad/dh-provenance-journal/blob/main/.github/workflows/ci.yml)
(Ubuntu/macOS × Python 3.11/3.13). Konkrete Job-URLs jedes
qualifizierenden Laufs stehen im GitHub-Release v0.1.0.

## Geprüfte Kombinationen

| Betriebssystem | Python | Suite | Paketbau | Installierter Ablauf SHA-256 | Installierter Ablauf HMAC |
|---|---|---|---|---|---|
| Ubuntu (CI) | 3.11 | 207 bestanden | Wheel + sdist gebaut | 9 Befehle, 6 Ereignisse, `verify`/`history`/`check-artifact` wie erwartet | 9 Befehle, Schlüssel außerhalb der Datenwurzel, gleiche Erwartungen |
| Ubuntu (CI) | 3.13 | 207 bestanden | Wheel + sdist gebaut | wie oben | wie oben |
| macOS (CI) | 3.11 | 207 bestanden | Wheel + sdist gebaut | wie oben | wie oben |
| macOS (CI) | 3.13 | 207 bestanden | Wheel + sdist gebaut | wie oben | wie oben |

Der installierte Ablauf läuft außerhalb des Quellbaums gegen das
gebaute Wheel (kein Index, keine Abhängigkeiten): sechs
Schreibbefehle (`init`, `register`, `ingest`, `artifact`, `receipt`,
`decide`), danach `verify` (`Kette: gültig (6 Ereignisse)`),
`history` (`aktuelle Fassung`) und `check-artifact`
(`registriert (aktuelle Fassung, seq 4)`).

## Belegte Reichweite

- 207 Tests: Hülle, Hashbytes, feste Vektoren, Profil, sechs
  Schreibfunktionen, neun CLI-Befehle, JSON-Vertrag sowie POSIX-,
  Sperr-, Manipulations-, Fehlertyp- und Kernschutzfälle.
- Das synthetische Beispiel (`examples/run.sh`) läuft auf dem
  installierten Paket; vorhandene Ziele und Git-Metadaten werden
  abgewiesen (Exit 2).
- `CITATION.cff` ist gegen das offizielle CFF-1.2.0-Schema gültig;
  alle Dokumentverweise lösen auf.

## Bekannte Grenzen

- Kein PyPI-Release; Installation aus Wheel/sdist des
  GitHub-Release v0.1.0.
- Ein gültiger verkürzter Journalstand bleibt ohne unabhängig
  verwahrten Vergleichsstand unerkannt; HMAC belegt Schlüsselbesitz,
  keine Personenidentität; ein Laufbeleg dokumentiert einen
  erklärten Lauf, keinen Beweis seiner Ausführung.
- `verify` Exit 0 ist technische Gültigkeit, keine wissenschaftliche
  Freigabe. Ausführlich: `docs/NUTZUNG.md`,
  `docs/WIEDERHERSTELLUNG.md`.
