# Data and Code Package
## "Estimation Bias versus Decision Regret in District-Heating Dispatch Optimisation: Loss Visibility, not Network Topology, Sets the Fidelity Requirement"

**Authors:** Lukas [Nachname], [Betreuer], [Industriepartner]  
**Journal:** Applied Energy (APEN-D-26-15734, major revision)  
**DOI (this dataset):** https://doi.org/10.5281/zenodo.XXXXXXX

> **v1.2.0 — APEN REVISION (2026-08-12).** This release adds the revision's new analyses on top
> of the v1.1.0 corrected model (`calion/`, commit `c19d690`, unchanged): estimation **bias vs
> decision regret**, an exact **loss/topology/interaction decomposition**, an a-priori **fidelity
> design rule** `b = λ/(1+λ)` (R²=0.86), and a **directly solved** temperature-linearisation
> reference on representative windows (−0.15 % / −0.33 %). The last **updates** the earlier
> "bounded-only" statement — see [`SOLVED_LINEARISATION_ANALYSIS.md`](SOLVED_LINEARISATION_ANALYSIS.md).
> New artefacts live in `results/analysis/`, new figures `results/figures/F_*`, generators in
> `tools/` (`fidelity_rule.py`, `linearisation_solved.py`, `figgen_p1_v2.py`, `tablegen_p1.py`).
> **See [`CHANGELOG.md`](CHANGELOG.md).**
>
> The v1.1.0 correction (2026-07-27, four model fixes) remains documented below and in the
> CHANGELOG; the corrected model is the basis of this release.

---

## Contents

```
zenodo_paper_1/               (v1.2.0 — APEN revision; built on v1.1.0 corrected model)
├── CHANGELOG.md              v1.2.0 additions + the v1.1.0 correction (old→new numbers)
├── CITATION.cff              Citation metadata (v1.2.0, 2026-08-12)
├── SOLVED_LINEARISATION_ANALYSIS.md  NEW: fix-and-relax native reference (−0.15/−0.33 %)
├── L3NL_LINEARIZATION_ANALYSIS.md    Why the global re-solve is intractable (v1.1.0)
├── patches/                  The v1.1.0 code-fix diffs vs commit c19d690
├── calion/                   Python optimization framework (Pyomo/Gurobi) — unchanged
├── configs/memmingen/        Primary-case configs (L1–L3NL) + NEW Memmingen_T2P3_native.yaml
│                             and _w3_winter/_w3_autumn_native.yaml (solved-lin. reproducers)
├── synth_configs/            Synthetic network configurations
├── scripts/paper/            Scripts to reproduce paper runs and figures
├── tools/                    fill_paper.py, and NEW: fidelity_rule.py, linearisation_solved.py,
│                             figgen_p1_v2.py, tablegen_p1.py
├── data/synthetic_site/      Synthetic input timeseries (demand, prices, weather) — NDA-safe
├── results/
│   ├── L1/ L2/ L3/ L3plus/   Per-level economics, dispatch, meta
│   ├── analysis/             NEW: fidelity_rule.csv, linearisation_solved.csv,
│   │                         decomposition_live.csv, regret_decomp*.csv, bias_regret.csv,
│   │                         synth_factorial_decomposition.csv, frozen_adder_drift.csv,
│   │                         tsup_sensitivity.csv, prediction_oos*.csv
│   ├── figures/              paper figures (PDF+PNG) incl. NEW F_rule/F_decomp/F_regret/
│   │                         F_drift/F_tsup
│   └── tables/               paper tables (LaTeX source)
├── requirements.txt
├── pyproject.toml
└── LICENSE (MIT)
```

**Not included:** Raw operational data for the primary case cannot be shared
publicly due to a non-disclosure agreement. Anonymized results sufficient to
reproduce all paper figures and tables are included in results/.

---

## Requirements

- Python 3.10+
- Gurobi 10.0+ with valid license (NonConvex=2 required for L3NL)
- Install: pip install -r requirements.txt

---

## Reproducing the paper runs

Full pipeline (L1/L2/L3/L3plus, ~1h, no L3NL):
  python scripts/paper/run_paper_full.py --phases 1 2 3 4 5 6 7 --skip-nl --skip-consistency

Regenerate figures and tables from pre-computed results only:
  python scripts/paper/run_paper_full.py --phases 5 6 7

Linearization comparison (L3plus vs L3NL, 744h January window):
  python scripts/paper/run_paper_full.py --phases 4
  NOTE: a full global L3NL solve is intractable with the corrected pump physics (see
  CHANGELOG / L3NL_LINEARIZATION_ANALYSIS.md). The pump-friction linearization error was
  therefore obtained exactly by decomposition on the windowed L3plus dispatch; the result
  is provided in results/pump_linearization_error.json and the method is
  scripts/paper/_pump_linearization_error.py (run it on a windowed L3plus reproduction).

Synthetic network analysis (36 configs):
  python scripts/paper/run_paper_full.py --phases 3

---

## Result file descriptions

economics.csv          Annual cost breakdown: fuel, electricity, CO2, pump, total
dispatch_hourly.csv    Hourly dispatch for all assets (8760 rows)
meta.json              Solver stats: solve time, MIP gap, variable/constraint counts
pipes.csv              Per-pipe annual loss energy (MWh)
nodes_summary.csv      Per-node annual demand and loss summary
level_consistency.json Cost hierarchy (L1≤L2≤L3≤L3plus) + L3plus→L3NL linearization error
                       (from decomposition; see pump_linearization_error.json)
pump_linearization_error.json  Exact pump-friction PWL-vs-cubic error, Jan & Feb windows

---

## Citation

[Nachname] et al. (2025). Topology Abstraction and Physics Fidelity Effects on
Dispatch Optimization of Electrified District Heating Networks. Applied Energy.
https://doi.org/[journal DOI]

Dataset: https://doi.org/10.5281/zenodo.XXXXXXX
