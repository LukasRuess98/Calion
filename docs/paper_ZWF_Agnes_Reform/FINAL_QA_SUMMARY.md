# FINAL_QA_SUMMARY.md

**Finaler Paper-Lauf:** `outputs/20260922T203807/`
**Vorheriger, verworfener Lauf:** `outputs/20260922T150335/` (s. `FINAL_RUN_INVALID.md` — fehlendes T13)
**Preflight-/Source-Freeze:** `run_sources/20260922T203247/` (`PRE_RUN_MANIFEST.md`, `SHA256SUMS.txt`)
**Ergebnis:** **GÜLTIG — alle Abnahmekriterien (Section 3) erfüllt.**

## 1. Quellstand-Integrität während des Laufs

Vier Kernartefakte wurden vor Laufstart eingefroren (SHA-256) und nach Abschluss des Laufs erneut gehasht. Alle vier stimmen exakt überein — keine Änderung an Code/Config/Notebook/Paper während der ~1h20min Laufzeit:

| Datei | Hash (Preflight = Post-Run) |
|---|---|
| `agnes_p2h.py` | `d6e18f3784dab3dd02048da711aac13756383a26fe87cda7fb738eb578eafca5` |
| `agnes_p2h.ipynb` | `566581d630b1d4b183b6ab02ea249dbc36d28fce35cd5f02c9b5e72fbb85f54d` |
| `config.yaml` | `0ffd2bbbe432ef741006bafd7c3c8470692c8ebe69007d42d58f40e24e682bfb` |
| `20260922_Bestellkapazitaet_ZWF_lkr.docx` | `9d6aee2df02208c45ee9c4693c17fbcf02175a04a45b2f970b56bff5faff0803` |

Config-Hash (intern, 16-stellig): `0ffd2bbbe432ef74` — identisch in `environment.md` des neuen Laufs und in `PRE_RUN_MANIFEST.md`.

## 2. Selbsttests T01–T13

Alle 13 Tests **bestanden** (`test_report.md`, `qa_report.md` in `outputs/20260922T203807/`):

| Test | Ergebnis |
|---|---|
| T01 Intervallzahl/Lücken/Duplikate | bestanden — 4/4 Standorte ok |
| T02 Einheiten-Sentinel | bestanden — rel. Verschiebung 8839,54% |
| T03 Wärmebilanz | bestanden — max. rel. Residuum 1,15e-16 |
| T04 Strombilanz | bestanden — max. rel. Residuum 2,16e-17 |
| T05 TES zyklisch/Kapazität/Rate | bestanden |
| T06 kein simultanes Laden/Entladen | bestanden — max r_sim = 0,00e+00 |
| T07 AgNes P1=min(P,C) | bestanden |
| T08 Bestellregel trifft Optimum (BASE) | bestanden — max. Abweichung 0,000% |
| T09 StromNEV-Tarifpaar-Konsistenzprüfung | bestanden — 32/64 als ambiguous geflaggt (kein Fallback, s. Abschnitt 4) |
| T10 TES-Dominanz | bestanden — 0/24 Verletzungen |
| T11a Objective-Rekonstruktion | bestanden — max. rel. Fehler 6,91e-14 |
| T11b 15min-Validierung (LCOH_inc) | bestanden — chemistry Δ 0,038%, paper Δ 0,112% |
| T12 Determinismus + Methodenvergleich | bestanden — beide Deltas 0,00e+00 |
| **T13 ETA_GB-Regression (neu)** | **bestanden** — ETA_GB=0,9, q_gb_useful=254,494 MWh, fuel_gas=282,771 MWh, Verhältnis=1,1111 (erwartet 1/ETA_GB=1,1111), recon_ok=True |

## 3. Solver-Diagnostik (alle Kampagnen, `qa_report.md`)

- Gesamt-Solves (S1–S5, S9, 15min-Validierung): **180**, davon nicht-optimal/Fehler: **0**
- `kpi_s1_s4.parquet`: 96/96 Läufe optimal, 0 NaN in `objective_eur`
- S7 Break-even-Ketten: 16 versucht, 9 konvergiert (siehe Abschnitt 4)
- S8 Dekomposition: 4 Standorte
- S10 Rolling Horizon: 4 Regime-Kombinationen, 1460 Fenster gesamt, 0 Fehler

## 4. Break-even-Konvergenz (Detailprüfung wegen "kein converged=False in berichteten Werten")

`breakeven.csv` enthält 16 Ketten (4 Standorte × {gas, co2} × {StromNEV, AgNes}); 7 davon mit `converged=False`, `reason="no_sign_change"` (kein Vorzeichenwechsel im gesuchten Preisintervall [5,150] bzw. [5,400] EUR/MWh — ein strukturelles Ergebnis, keine numerische Störung). Für diese 7 Zeilen ist `breakeven=NaN` — **kein Zahlenwert wird fabriziert**. In den berichteten/aggregierten Markern (`marker_map.csv`, `paper_values.json`) wird dies transparent als Konvergenzquote offengelegt:

- `R-BE-GAS`: "13..32 (über beide Netzregime, **7/8** Ketten konvergiert)"
- `R-BE-CO2`: "11..30 (über beide Netzregime, **2/8** Ketten konvergiert)"

Damit ist das Abnahmekriterium erfüllt: Es gibt keinen Fall, in dem ein nicht-konvergierter Wert als gültiges Ergebnis ausgegeben würde.

## 5. StromNEV-Tarifpaar-Konsistenz

T09 lief ohne Absturz; 32 von 96 Läufen in `kpi_s1_s4.parquet` als `tariff_ambiguous=True` geflaggt (erwartetes, reales Phänomen bei Benutzungsdauern nahe der 2.500h-Schwelle). `best_stromnev_row()` wirft bei Mehrdeutigkeit `InfeasibleRunError` statt eines stillen Fallbacks auf ein unpassendes Tarifpaar (Quellcode-Verifikation, s. `PRE_RUN_MANIFEST.md` Abschnitt 5, Punkt 6) — alle in Aggregaten/Tabellen verwendeten StromNEV-Werte stammen aus konsistent aufgelösten Tarifpaaren.

## 6. Marker-Abdeckung

- Belegt: **48** Marker
- Offen (mit dokumentierter Begründung): **5** (`REG-02`, `REG-03`, `REG-04`, `R-DES-EF`, `BIB-02` — alle in `open_markers.csv`/`open_issues.md` mit Recherche-Stand begründet, keine offenen Zahlenwerte im Kernergebnis)

## 7. Fazit

Alle Abnahmekriterien aus dem Preflight-/Source-Freeze-Protokoll (Section 3) sind erfüllt. `outputs/20260922T203807/` ist der finale, gültige Paper-Lauf. Auf dieser Basis erfolgen: DOCX-Aktualisierung (Zahlen + methodische Korrekturen, s. `PAPER_NUMERIC_UPDATE_LOG.md`), Notebook-Resync, `AUTOREN_REFERENZ.md`-Update und Neuaufbau von `submission_pack/`.
