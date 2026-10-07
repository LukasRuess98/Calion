# PRE_RUN_MANIFEST.md

**Preflight-/Source-Freeze-ID:** `20260922T203247`
**Startzeit (geplanter Produktionslauf):** 2026-09-22T20:32:47 (lokale Systemzeit, Format YYYYMMDDTHHMMSS wie Run-ID-Konvention)
**Zweck:** Quellstand-Freeze vor Neustart des vollständigen Produktionslaufs, nachdem `outputs/20260922T150335/` wegen fehlendem T13 als ungültig verworfen wurde (siehe `../../FINAL_RUN_INVALID.md`).

## 1. Quell-Hashes (SHA-256), Stand dieses Freezes

Berechnet aus den tatsächlichen, aktuellen Projektdateien (nicht aus einem Attachment/Export). Identisch zu `SHA256SUMS.txt` in diesem Ordner.

| Datei | SHA-256 |
|---|---|
| `agnes_p2h.py` | `d6e18f3784dab3dd02048da711aac13756383a26fe87cda7fb738eb578eafca5` |
| `agnes_p2h.ipynb` | `566581d630b1d4b183b6ab02ea249dbc36d28fce35cd5f02c9b5e72fbb85f54d` |
| `config.yaml` | `0ffd2bbbe432ef741006bafd7c3c8470692c8ebe69007d42d58f40e24e682bfb` |
| `20260922_Bestellkapazitaet_ZWF_lkr.docx` | `9d6aee2df02208c45ee9c4693c17fbcf02175a04a45b2f970b56bff5faff0803` |

## 2. Config-Hash

- `CONFIG_SHA256` (intern, wie vom Skript berechnet, 16-Zeichen-Kurzform): `0ffd2bbbe432ef74`
- Dies stimmt mit den ersten 16 Hex-Zeichen des vollen `config.yaml`-SHA-256 oben überein und ist identisch zum Config-Hash des vorherigen (ungültigen) Laufs `20260922T150335` — d. h. `config.yaml` wurde zwischen den beiden Läufen **nicht** verändert; nur der Code (`agnes_p2h.py`, T13-Ergänzung) hat sich geändert.

## 3. Erwartete Solver-Einstellungen

- `threads=1` (in `SOLVER_KWARGS`, verifiziert per grep in Preflight Punkt 1.9)
- `MAX_WORKERS = min(12, os.cpu_count() or 12)`, d. h. **MAX_WORKERS ≤ 12** (verifiziert per grep in Preflight Punkt 1.9)
- Solver: `highs` (HiGHS via `highspy`), `output_flag=False`

## 4. Erwartete Selbsttests

Vollständiger Satz **T01–T13** muss in `test_report.md` des neuen Laufs erscheinen und für jeden Eintrag `bestanden=True` zeigen. Insbesondere:

- T01–T12: wie im vorherigen Lauf (`20260922T150335`), inhaltlich unverändert erwartet.
- **T13 (neu):** ETA_GB-Regressionstest — prüft, dass bei `ETA_GB=0.9 < 1.0` der rekonstruierte Brennstoffbedarf (`fuel_gas_mwh_hu`) strikt größer ist als die bereitgestellte Nutzwärme (`q_gb_useful_mwh`), mit Verhältnis exakt `1/ETA_GB ≈ 1.1111` und exakter Rekonstruktion (`recon_ok=True`). Unabhängig bereits per `AGNES_DRY_RUN=1` verifiziert (ETA_GB=0.9, q_gb_useful_mwh=254.494, fuel_gas_mwh_hu=282.771, Verhältnis=1.1111, recon_ok=True); im Vollauf wird derselbe Test gegen den Site `metal`/Config `GAS` erneut ausgeführt.

## 5. Bestätigte methodische Korrekturen (Stand dieses Freezes, alle per Preflight-Grep verifiziert)

1. ETA_GB korrekt in Zielfunktion und KPI-Extraktion berücksichtigt (`fuel_cost = fuel_cost_eur_kwh_fuel / ETA_GB`; `fuel_gas_mwh_hu = q_gb_useful_mwh / ETA_GB`).
2. Negative Grundlast wird nicht mehr stillschweigend verworfen, sondern als `p_export_kw`/`negative_base_intervals`/`negative_base_export_kwh` erfasst; `p_base_kw` auf ≥0 geclippt.
3. DST-Behandlung: Standortlasten via `ambiguous="infer"`; 2024-Preisreihe via `ambiguous="NaT"` + Reindex + `.ffill()` (dokumentiert in `PRICE_QUALITY[2024]["imputation_method"]`).
4. Fixpreis-Methode ist ungewichteter Mittelwert plus Risikoaufschlag (`annual_mean_day_ahead_plus_risk_premium`), nicht lastgewichtet.
5. `MAX_WORKERS ≤ 12`, `threads=1` (siehe Abschnitt 3).
6. Kein stiller StromNEV-Fallback: `best_stromnev_row` wirft `InfeasibleRunError` statt eine unpassende Tarifzeile zu verwenden.
7. Break-even-Bisektion nutzt `config.yaml: design.breakeven` (`max_iter=25`, `tol_rel=0.001`) und liefert `converged`/`reason`/`residual_eur`.
8. T11b vergleicht BASE+ELEC bei 1h vs. 15min über die inkrementelle Kenngröße `LCOH_inc`, nicht über rohe Totex/Nutzwärme.
9. V-04 (KKT-Konsistenzcheck der Bestellregel auf Basis der realisierten LP-Last) ist als separater, ergänzender Test vorhanden (Regelvalidierungs-Kern gemäß Nutzerentscheidung Q2 unverändert erhalten).
10. S10 (Rolling Horizon) chirurgisch gefixt: Kapazitätsterm `P_max * lp` wird nur für `spec.window is None` addiert, nicht pro Fenster.
11. T08 nutzt einen expliziten `dt_h`-Parameter statt der global hartkodierten 15-Minuten-Auflösung.
12. T06-Regularisierung (`CYCLE_PENALTY_EUR_MWH=5.0`) aktiv, inkl. Berücksichtigung in der Objective-Rekonstruktion (T11a).
13. `import re` vorhanden (Draft-Patch-Regex funktionsfähig).
14. T13 wie unter Abschnitt 4 beschrieben vorhanden und DRY_RUN-verifiziert.
15. `config.yaml` enthält `grid_connection_kw`-Proxy-Felder für alle 4 Standorte sowie `design.breakeven.{max_iter,tol_rel}`.

## 6. Status dieses Freezes

- Alle 10 explizite + 5 zusätzliche Preflight-Grep-Prüfungen: **bestanden** (kein Abweichungsbefund zum vom Nutzer beschriebenen möglichen Altstand).
- Frozen-Kopie erstellt unter `run_sources/20260922T203247/` (dieser Ordner), enthält die 4 oben gehashten Dateien plus diese Manifest-Datei.
- Nächster Schritt: Start des Produktionslaufs (`python agnes_p2h.py`, kein `AGNES_DRY_RUN`) ohne weitere Änderung an Code/Config/Notebook/diesem Ordner während der Laufzeit.
