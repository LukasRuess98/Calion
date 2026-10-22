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
| B3 | `tables/B3_bau_entscheidungen.csv` | folgt | per Skript `build_B3_B4.py`, in dieser Lieferung |
| B4 | `tables/B4_konvergenz_provenienz.csv` | folgt | per Skript `build_B3_B4.py`, in dieser Lieferung |
| E1 | `DRAFT_4ck_ff.md` | folgt | nach B4 |

## Nicht geliefert (Tranche 1, bisher)
- B3/B4: zum Zeitpunkt dieses ersten Teil-Commits noch nicht geschrieben (folgt im selben Arbeitsgang).

## Zwei Hintergrund-Agents sind an einem Anthropic-Session-Rate-Limit gescheitert (keine Dateien geschrieben,
kein Datenverlust) — A1/A5 und ein erster B3/B4-Versuch wurden danach direkt von mir übernommen.
