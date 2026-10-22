# INDEX — Agent-Auftrag v5 "Lieferpaket für Abschnitt 4-5" (Lukas-Session)

Stand 2026-10-22. Tranche 1 = A1-A5, B1-B4, E1. Dieser Index wird bei jedem Teil-Commit aktualisiert.

| Punkt | Datei(en) | Status | Hinweis |
|---|---|---|---|
| A1 | `A1_A5_findings.md` | geliefert | MONTHLY strukturell real, aber Solution count 1 (stuck warmstart) |
| A2 | `A2_A3_findings.md` | geliefert | j_man-Pipe-Kapazität präzisiert; 2 neue Meldepflichten (A2-M2 solution_count) |
| A3 | `A2_A3_findings.md` | geliefert | c0-Sweep-Konsistenz + Repricing; §4ck-Vorbehalt bestätigt (nicht neu entdeckt) |
| A4 | `A4_geometry_findings.md`, `tables/A4_geometry_offline_calc.csv` | geliefert | von Recherche-Agent erstellt, vor Rate-Limit fertig |
| A5 | `A1_A5_findings.md` | geliefert | Logging-Bug lokalisiert (result_collector.py:1296-1299) |
| B1 | `tables/B1_kostenzerlegung.csv`, `scripts/build_b1_kostenzerlegung.py` | geliefert | 7 Lauf-Paare |
| B2 | `B2_speicherbetrieb_findings.md`, `tables/B2_speicherbetrieb_summary.csv`, `tables/B2_speicherbetrieb_monatsprofil.csv`, `scripts/build_b2_speicherbetrieb.py` | geliefert | Mechanismus: KWK-Glättung + Gasboiler/EK-Verdrängung, nicht Preisarbitrage |
| B3 | `tables/B3_bau_entscheidungen.csv`, `scripts/build_B3_B4.py` | geliefert | 36 Laeufe, Quelle geometry.csv/cost_breakdown.json |
| B4 | `tables/B4_konvergenz_provenienz.csv`, `scripts/build_B3_B4.py` | geliefert | 36 Laeufe; Stichprobe gg. Referenztabelle verifiziert (alle 6 Punkte exakt); Fix eines Parsing-Bugs (kumulatives Logfile `output/logs/`, siehe unten) vor Auslieferung |
| E1 | `DRAFT_4ck_ff.md` | geliefert | Faktensammlung 06.-22.10., referenziert §4ck/§4cr |
| §4cr-Fragen + Defekte 14/15 | `C4CR_FRAGEN_UND_DEFEKTLISTE.md` | geliefert | alle genannten Hauptergebnisse "unveraendert"; Tag-Vorschlag NICHT ausgefuehrt (wartet auf Freigabe) |

**Tranche 1 VOLLSTAENDIG (A1-A5, B1-B4, E1).** STOPP, wartet auf Rueckmeldung (Agent-Auftrag v5.1 §7).

## Speicherbudget (Regel 7, ≤150 KB)
Eigene Lieferung (ohne `REPORT_AC_Rueckgabe_2026-10-22.md`, das ist eine andere Session): ca. 99 KB. Einzelne CSVs
alle < 20 KB (B4 mit 15,8 KB am groessten).

## Wichtiger methodischer Fund waehrend B3/B4-Erstellung
`output/logs/gurobi_<scenario_id>.log` ist fuer v7_final-Laeufe (und teilweise andere) ein GEMEINSAMES,
kampagnenuebergreifendes Logfile (bis zu 19 aufeinanderfolgende Solve-Sessions desselben scenario_id über die ganze
Projekthistorie) — selbst "letzter Treffer gewinnt" ist dort NICHT zuverlaessig, da auch SPAETERE, unverwandte
Laeufe weiter in dieselbe Datei schreiben. Das Skript nutzt fuer diese Faelle `meta.json` als massgeblich (gegen die
Referenztabelle verifiziert), nur fuer Laeufe mit eigenem, job-isoliertem Logfile (`_z3`,`_z3b`,`_parallel_aa3`,
`_s2`-Konvention) wird das Log als massgeblich verwendet. In `B4_konvergenz_provenienz.csv` als `log_is_cumulative`/
`meta_vs_log` je Zeile dokumentiert.

## Zwei Hintergrund-Agents sind an einem Anthropic-Session-Rate-Limit gescheitert (keine Dateien geschrieben,
kein Datenverlust) — A1/A5 und B3/B4 wurden danach direkt von mir übernommen (B3/B4 als Skript, wie vom
Auftraggeber in v5.1 gefordert).
