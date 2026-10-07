# Submission Pack — agnes_p2h / ZWF-Beitrag "Bestellkapazität statt Jahreshöchstlast"

Stand: Lauf `20260922T203807` (finaler, per `FINAL_QA_SUMMARY.md` abgenommener
Lauf; T01–T13 bestanden, 96/96 optimal, 48 Marker belegt/5 offen; ersetzt den
zuvor verworfenen Lauf `20260922T150335`, dem T13 fehlte, sowie den
ursprünglichen Stand `20260915T195641` vor dem ETA_GB-Fix). Diese Mappe
enthält alles, was gebraucht wird, um den Paper-Draft fertigzustellen —
nichts hier muss neu gerechnet werden.

**Maßgebliches Manuskript ist `20260922_Bestellkapazitaet_ZWF_lkr.docx`**
(liegt jetzt direkt in dieser Mappe, s. Ordnerstruktur unten — diese Mappe ist
seit der Korrekturrunde 2 (2026-09-22) selbstständig/vollständig, unabhängig
vom übergeordneten Projektordner). Dort wurden alle Zahlen UND die
vollständigen methodischen Textkorrekturen (1h-Kernmodell statt 15-min, ein
generisches Prozesswärmeband statt LT/HT/VHT-Split, ETA_GB-Klarstellung,
Tabellennummerierung, Interaktionsterm-Neuformulierung u.a.) von Hand
eingearbeitet, s. `PAPER_NUMERIC_UPDATE_LOG.md` (Abschnitte A–F).
`00_draft/draft_filled.md` unten ist der ältere, separate
Markdown-Pipeline-Draft (`20260915_Paper_ZWF_Agnes_Reform_Draft.md`) mit
automatisch eingesetzten Zahlen — die Zahlen darin sind aktuell, die
methodischen Formulierungen wurden dort **nicht** manuell nachgezogen.

## Womit anfangen

1. **`20260922_Bestellkapazitaet_ZWF_lkr.docx`** (in dieser Mappe) — das
   aktuelle, vollständig korrigierte Manuskript. Das ist die
   Einreichungsgrundlage.
2. **`00_draft/AUTOREN_REFERENZ.md`** — Übersicht aller 5 Abbildungen (mit
   Bildunterschrift-Vorschlag), aller 3 Tabellen (voller Inhalt) und aller
   Kernzahlen, sortiert nach Draft-Abschnitt. Zum Nachschlagen/Gegenchecken
   beim Redigieren.
3. **`00_draft/draft_filled.md`** — der ältere Markdown-Draft mit allen
   belegten Zahlen automatisch eingesetzt (s. Hinweis oben zu den
   methodischen Formulierungen).
4. **`00_draft/draft_original.md`** — der unveränderte Ausgangs-Draft
   (Referenz, falls man vergleichen will, was automatisch ersetzt wurde).
5. **`00_draft/paper_patch_ersetzungsliste.md`** — Liste aller im
   Markdown-Draft gefundenen `[[MARKER]]`-Platzhalter mit Status
   (belegt/offen/unbekannt).

## Ordnerstruktur

| Datei/Ordner | Inhalt |
|---|---|
| `20260922_Bestellkapazitaet_ZWF_lkr.docx` | Finales, korrigiertes Manuskript (Einreichungsgrundlage) |
| `agnes_p2h.py` | Führende Quelle des Modells/der Pipeline (Stand nach Korrekturrunde 2) |
| `agnes_p2h.ipynb` | Aus `agnes_p2h.py` synchronisiertes Notebook |
| `config.yaml` | Modellkonfiguration des finalen Laufs |
| `FINAL_QA_SUMMARY.md` | Abnahmeprotokoll des finalen Laufs (Section-3-Kriterien) |
| `PAPER_NUMERIC_UPDATE_LOG.md` | Vollständiges Änderungsprotokoll aller DOCX-Korrekturen (2 Runden) |
| `FINAL_RESULT_TRACEABILITY.csv` | Jede Zahl im Paper → Marker → Quelldatei → Run-ID → Config-Hash |
| `CHECKSUMS.sha256` | SHA-256 aller Dateien dieser Mappe |
| `00_draft/` | Markdown-Pipeline-Draft-Dateien, s. oben |
| `01_figures/` | Abb. 1–5, je als `.pdf` (Vektor, für den Satz) und `.png` (Vorschau) |
| `02_tables/` | Tab. 1–3 (als `.md` zum Copy-Paste und `.csv` als Rohdaten) + 6 Supplement-CSVs (volle Sweep-/Testergebnisse) |
| `03_methodik_und_daten/` | Kopie von `config.yaml` (mit Quelle/Status je Parameter — Grundlage für Methodik-/Parameter-Appendix), `open_issues.md` (Limitations-Abschnitt), `unverified_parameters.csv`, `qa_report.md` + `test_report.md` (Validierungsabschnitt/Reproduzierbarkeit), `environment.md`, `data_audit.md`, `tariff_resolved.md` |
| `04_kpi_rohdaten/` | Einzelne KPI-CSVs (LCOH, Interaktion, Dekomposition, Regelgüte, Break-even, Auslegungs-Deltas) — Rückverfolgbarkeit für jede Zahl in `AUTOREN_REFERENZ.md` |

## Abbildungen im Überblick

| # | Datei | Zeigt |
|---|---|---|
| Abb. 1 | `fig01_superstructure` | Systemgrenze/Superstruktur (statisch) |
| Abb. 2 | `fig02_analytics` | σ(h)-Vergleich StromNEV/AgNes + θ(α,f)-Heatmap |
| Abb. 3 | `fig03_core_results` | LCOH^inc je Regime, Anlagenauslegung, Speicherkapazität |
| Abb. 4 | `fig04_load_duration` | Jahresdauerlinien mit C, P_max, E2-Fläche, h* |
| Abb. 5 | `fig05_breakeven` | Fossiler Break-even je Standort × Netzregime |

## Noch offene Punkte (5, s. `AUTOREN_REFERENZ.md` Abschnitt 4 für Details)

`REG-02`, `REG-03`, `REG-04`, `R-DES-EF`, `BIB-02` — alle mit Begründung,
warum sie nicht automatisiert befüllbar sind (2× echte Regulatorik-Offenheit
im AgNes-Entwurf selbst, 1× fehlende amtliche Quelle, 1× strukturell n/a).

## Provenienz / Integrität

- Quell-Lauf: `outputs/20260922T203807/` (im übergeordneten Projektordner, nicht Teil dieser Mappe)
- Config-Hash: `0ffd2bbbe432ef74`
- Quellstand-Freeze vor dem Lauf (SHA-256 von `agnes_p2h.py`/`agnes_p2h.ipynb`/`config.yaml`/DOCX): im übergeordneten Projektordner unter `run_sources/20260922T203247/PRE_RUN_MANIFEST.md`
- Abnahmeprotokoll: `FINAL_QA_SUMMARY.md` (in dieser Mappe)
- Vollständige Rückverfolgbarkeit jeder Zahl (Marker → Paper-Stelle → Quelldatei → Run-ID → Config-Hash): `FINAL_RESULT_TRACEABILITY.csv` (in dieser Mappe)
- Änderungsprotokoll (2 Korrekturrunden, inkl. Interaktionsterm-Neuformulierung): `PAPER_NUMERIC_UPDATE_LOG.md` (in dieser Mappe)
- Dateiintegrität dieser Mappe: `CHECKSUMS.sha256` (in diesem Ordner — 57 Dateien, per `sha256sum -c` verifiziert)
- DOCX-Hash (finaler Stand nach Korrekturrunde 2): `bfcec7f8daf58fd8538263d7a4ac8e7a1067f23a8c850f9790e144f8960e6209`
- `agnes_p2h.py`/`agnes_p2h.ipynb` in dieser Mappe sind der Stand **nach**
  Korrekturrunde 2 (R-INT-01-Klassifikationsfix); der Stand, mit dem
  `outputs/20260922T203807/` tatsächlich gerechnet wurde, ist unverändert in
  `run_sources/20260922T203247/` (übergeordneter Ordner) eingefroren — die
  Zahlenwerte in dieser Mappe sind von der Code-Änderung nicht betroffen
  (reine Text-/Klassifikationslogik für künftige Läufe), s.
  `PAPER_NUMERIC_UPDATE_LOG.md` Abschnitt F.

## Falls doch neu gerechnet werden muss

Quelle ist `agnes_p2h.py` (in dieser Mappe, identisch zum übergeordneten
Projektordner). Nach einem neuen Lauf: `AUTOREN_REFERENZ.md` mit
`python build_author_reference.py <neuer_run_ts>` neu erzeugen und diese
Mappe manuell aktualisieren (Skript dafür bisher nicht vorhanden).
