# Herkunftshinweise

Der Journalkern (`provenance_journal`) ist aus dem OHPIPE-Public-Stand,
Commit **3cff6f6f96f49ce7fbb5774a522a2432a845acc6**, übernommen und für das
Basisprofil research-basic-v1 isoliert.

Übernommen sind die Ereignishülle mit Hashverkettung, die
Digestberechnung (SHA-256 bzw. HMAC-SHA-256 über dieselben kanonischen
Bytes), die exklusive Dateisperre, die sicheren POSIX-Zugriffe
(`O_NOFOLLOW`, `O_NONBLOCK`, `S_ISREG` am geöffneten Deskriptor) sowie
die Schlüssel-Lageprüfung. Isoliert und neu gefasst sind das schreibbare
Basisprofil research-basic-v1 mit seinen Validatoren, die Bibliothek mit
sechs Schreibfunktionen, die Historienauswertung und die CLI
`provjournal`. Originaljournale werden nicht migriert oder umgeschrieben.

OHPIPE-Quellcode ist Copyright 2026 Klaus Behnam Shad und steht unter der
[MIT-Lizenz](LICENSE). Der Urhebervermerk und der Lizenztext bleiben in allen
Kopien erhalten.

Die gebündelten IMM-Core-Ressourcen des Ausgangsprojekts (CC-BY-4.0,
`src/ohpipe/schemas/metadata/`) werden in diesem Paket **nicht**
mitgeliefert. Es gibt keine weiteren Drittinhalte; die einzige
Laufzeitabhängigkeit ist die Python-Standardbibliothek (erfordert Python
3.11 oder neuer). Entwicklungsabhängigkeit: pytest.
