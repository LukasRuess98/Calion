# Paper 2 — Critical QC Review (ECM readiness)

Date 2026-08-30. Verdict: **method & parameterization sound; not yet
submission-ready** — blockers are reproducibility/reporting, not modelling validity.

## ✅ Solid
- **Parameter parity**: both configs harmonized — electricity = spot timeseries +
  grid 61.6 €/MWh + demand charge 127.2 k€/MW·a; CO₂ 100 €/t; ef_el 400 kg/MWh;
  gas 58.6; biomass 20; HP 700 €/kW; EK 150 €/kW; TES 1200 €/m³ + 100 k€; discount
  5%; lifetimes 20/25/30 y. All literature-referenced (VDI 2067, DEA). Network-
  specific differences (real generator efficiencies, Stadtbach AVA source) legitimate.
- **Solver**: MIPGap 0.5%, Cuts=2/MIPFocus=2, pressure_drop + milp_linearize on,
  max_velocity 3 m/s — consistent across networks.
- **Core figures** F1/F2/F4/F5/F6/F9 + T1–T4 built, mutually consistent, on-design.
  COP range 2.75–3.77 plausible.

## 🔴 Critical
1. **Reproducibility — current code ≠ campaign code.** Frozen campaign = commit
   `e8e445e` (07-22); `a503bb9` (07-26) + Aug commits added lateral losses +
   pressure physics. Current `main` gives MM-S4 = 493k vs 299k frozen (verified
   twice). **ACTION:** tag/archive `e8e445e` + config as the reproduction artifact,
   or re-run the whole campaign on current code. *This is the one open decision.*
2. **Energy-balance closure — DIAGNOSED as a reporting bug (downgraded, partially fixed).**
   T5's 25–53% closure error is because the validation counts `hp_main_MW` / `hp_sb_MW`
   (HP **electricity** input) as heat generation instead of P_el × COP. A post-hoc
   ×COP correction (written as `closure_error_pct_heat` in each `validation.json`)
   cuts the median closure from ~25% to **~11%** (MM-S5-HK0 52.8%→4.1%), confirming
   it is an *extraction* artifact, not a dispatch imbalance (the MILP enforces nodal
   balance). It does **not** reach the ≤2% gate post-hoc: annual-mean COP (vs hourly),
   per-generator el-vs-heat semantics (CHP), and baseline handling leave a residual;
   a few runs (e.g. SB-S6-HK0, a known-broken 07-14 base) are spurious. **ACTION:**
   fix at source — export HP/WP **heat output** (Σ hourly P_el×COP) in the extractor
   when the campaign is re-run on the canonical code; then T5 closure should be ≤~2%.
3. **P1↔P2 OPEX 117% — DIAGNOSED as price harmonization (downgraded).** P2 MM-P1REF
   OPEX 489,996 vs P1 225,717 largely from the deliberate 2026 price update
   (gas 45→58.6, gridcost 25→61.6 €/MWh). **ACTION:** disclose explicitly; close the
   residual with a line-item OPEX decomposition vs Paper 1.
4. **KPI baseline bug — FIXED.** Memmingen baseline was a January diagnostic →
   −289% instead of +44.8%. Fixed in `kpi_calculator.py`. All Memmingen numbers
   and the old 07-19 T4 must be regenerated (done) and prose rewritten.

## 🟡 Moderate — resolve or disclose
- **Narrative shifts vs draft**: Memmingen electrification now economic (+44.8%);
  Stadtbach best-fixed SB-S2→SB-S4; endogenous beats fixed in **both** networks
  (MM −13.2%, SB −3.2%) — draft says SB doesn't → asymmetry is now magnitude.
  Rewrite §4.4/§5.
- **New F4 finding (figure round 2026-08-30)**: the heat-curve's economic benefit is
  **electrification-dependent**, not universal — lowering the curve always raises COP,
  but only cuts cost where the HP carries real load (Memmingen −4.4%; Stadtbach ≈flat,
  its HP is <1% of supply). The old "HK jointly sets storage volume/COP/cost" framing
  was **not supported** (TES volume was solver noise / capped) — F4 redesigned around
  the true effect. §2/§4 coupling prose needs updating to this.
- **Figures rebuilt this round**: F1 dropped→§2 equations; F4/F6/F9 redesigned;
  F5 Paper-1 colours; F7 professionalised; F8 temp red (+ pressure-ceiling caveat).
  See PROVENANCE.md. Only F3 still pending (sweep).
- **F3, F7** — resolved via the campaign-era worktree (`e8e445e`, validated to reproduce
  the campaign model). **F7 built** (tier-1 fixed-design tornado). **F3 sweep re-running**
  in the worktree (approximate surface). The *full* MILP-reoptimization tornado is
  infeasible/inappropriate (days + swamped by ~9% incumbent variance); the fixed-design
  tornado is the correct, tractable form.
- **13/38 runs at maxTimeLimit**; MIP gaps not extracted (parse Gurobi logs for T5).
- **Stadtbach TES pins at 5,000 m³ cap** in every scenario (F4) — storage binding;
  discuss explicitly.
- **Sweep–MILP cross-validation "borderline"** (optimum 2–3 grid steps off) — partly
  because the sweep is stale.

## Priority order to submission
1. Decide reproducibility strategy (#1) — gates F3/F7 and everything downstream.
2. Fix the closure-metric reporting (#2) so T5 shows the true ~≤5% balance.
3. Disclose/close the P1↔P2 gap (#3).
4. Rewrite Memmingen + siting narrative to corrected numbers.
5. Rebuild F3/F7 on the chosen canonical code.
