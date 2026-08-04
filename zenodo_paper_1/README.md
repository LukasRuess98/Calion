# Data and Code Package
## "Topology Abstraction and Physics Fidelity Effects on Dispatch Optimization of Electrified District Heating Networks"

**Authors:** Lukas [Nachname], [Betreuer], [Industriepartner]  
**Journal:** Applied Energy (submitted 2025)  
**DOI (this dataset):** https://doi.org/10.5281/zenodo.XXXXXXX

> ⚠️ **CORRECTED VERSION (2026-07-27).** Four model fixes were applied and all runs
> re-solved (pump-power attribution, `demand_fraction²`, fine-PWL pump friction, and a
> 0.6 bar transfer-station Δp pump term). The paper's conclusions are unchanged; the
> pump/pressure-drop magnitudes are corrected. **See [`CHANGELOG.md`](CHANGELOG.md)** for
> exactly what changed, the old→new numbers, and caveats. The L3NL nonlinear reference is now
> intractable to re-solve globally with the corrected pump physics; its linearisation error
> was instead obtained by exact decomposition — see
> [`L3NL_LINEARIZATION_ANALYSIS.md`](L3NL_LINEARIZATION_ANALYSIS.md)
> (`results/pump_linearization_error.json`). `results/tables/*.tex` still hold the submitted numbers.

---

## Contents

```
zenodo_paper_1/               (corrected re-release v1.1.0 — see CHANGELOG.md)
├── CHANGELOG.md              What the correction changed + old→new numbers + caveats
├── CITATION.cff              Citation metadata (v1.1.0, 2026-07-28)
├── L3NL_LINEARIZATION_ANALYSIS.md  Why L3NL re-solve is intractable + decomposition result
├── patches/                  The 3 code-fix diffs vs commit c19d690
├── calion/                   Python optimization framework (Pyomo/Gurobi)
├── configs/memmingen/        5 YAML configs for primary case (L1-L3NL)
├── synth_configs/            36 synthetic network configurations
├── scripts/paper/            Scripts to reproduce all paper runs and figures
│   └── _pump_linearization_error.py  Pump-friction linearization-error post-processor
├── tools/fill_paper.py       Auto-fills LaTeX placeholders from result artefacts
├── data/synthetic_site/      Synthetic input timeseries (demand, prices, weather)
├── results/
│   ├── L1/                   Copperplate: economics, dispatch, meta
│   ├── L2/                   7-zone multi-node results
│   ├── L3/                   15-node basic MILP results
│   ├── L3plus/               15-node extended MILP results
│   ├── level_consistency.json  Cost hierarchy + L3⁺→L3NL linearization error (decomposition)
│   ├── pump_linearization_error.json  Exact pump-friction PWL-vs-cubic error (Jan/Feb)
│   ├── figures/              All paper figures (PDF + PNG)
│   └── tables/               All paper tables (LaTeX source)
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
