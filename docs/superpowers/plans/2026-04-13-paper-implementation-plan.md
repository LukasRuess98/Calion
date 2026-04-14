# Paper Implementation Plan
**Date:** 2026-04-13
**Branch:** feature/refactoring-framework-cleanup
**Target journals:** Energy Conversion and Management / Applied Energy

---

## Paper Structure (Approved)

**Title:** *Topology Abstraction Effects on Dispatch Optimization of Electrified District
Heating Networks: A Controlled MILP Comparison*

**Sections:**
1. Introduction (~1,000 w)
2. Related Work (~1,200 w) — incl. tool positioning table (CALION vs oemof/PyPSA/TIMES)
3. Model Formulation (~2,000 w) — L1/L2/L3 definitions, MILP, physics loss model, COP
   linearisation, storage, CO2 accounting, CALION implementation
4. Case Studies (~1,400 w) — Stadtbach primary + synthetic parametric network
5. Results: Stadtbach (~2,200 w) — validation, cost, CO2, dispatch, storage dispatch,
   network losses, computational performance
6. Generalisability: Synthetic Parametric Analysis (~1,000 w)
7. Sensitivity and Robustness Analysis (~1,500 w) — tornado L3, sensitivity index heatmap
   L1/L2/L3, scenario matrix, CO2 temporal resolution
8. Discussion (~1,200 w)
9. Conclusion (~400 w)
+ Appendix A.1–A.5

**Estimated total:** ~12,500 words (within ECM 8,000–18,000 range)

---

## Code Implementation Steps

### Step 1 — Fix MIP Gap Bug ✅ DONE
**Files:** `configs/paper/L1_copperplate_dispatch.yaml`,
           `configs/paper/L2_simplified_dispatch.yaml`,
           `configs/paper/L3_detailed_dispatch.yaml`
**Change:** `mip_gap: 0.01` (1%) → `mip_gap: 0.0001` (0.01%)
**Why:** Paper claims 0.01% gap; at 1% gap a 2.5% cost difference is not statistically
         meaningful above solver noise.

### Step 2 — Verify and Re-enable L3 ✅ DONE
**File:** `scripts/paper/run_all_levels.py`
**Change:** Uncomment L3 entry in CONFIGS list
**Note:** L3 config already has 600mm trunk pipe fix applied.
          Verify feasibility with short test run before full 8,760h run.

### Step 3 — Build Validation Script ✅ DONE (awaiting measured data to run)
**File:** `scripts/paper/validate_against_measured.py`
**Inputs:**
- `data/stadtbach_measured_2023.csv` ← **(in progress — not yet available)**
  Expected columns:
  ```
  month,gas_consumption_MWh,electricity_purchase_MWh,
  hp_operating_hours,storage_cycles_count
  ```
  12 rows (one per month, Jan–Dec 2023).
  Script handles missing file gracefully — prints format instructions and exits 1.
- `outputs/paper/L3/pf_timeseries.csv` (from pipeline run)
**Logic:** Aggregate L3 hourly outputs to monthly totals, MAPE + bias + max-dev per variable
**Outputs:**
- `outputs/paper/validation/validation_table.csv`
- `outputs/paper/validation/validation_summary.csv`
- `outputs/paper/validation/validation_results.tex` (booktabs LaTeX table fragment)

### Step 4 — Build Synthetic Parametric Network ✅ DONE (619 lines)
**File:** `scripts/paper/run_synthetic_parametric.py`
**Design:** Idealised ring network, parameterised by:
- pipe_length: [3, 8, 15] km
- demand_heterogeneity: [uniform, moderate, concentrated]
- storage_ratio: [small=0.1, medium=0.3, large=0.6] (fraction of peak demand)
- node_count: [5, 15, 30]
- 36 combinations × 3 levels = 108 MILP solves
- `--dry-run` flag available to preview configs without running
**Outputs:**
- `outputs/paper/synthetic/gap_matrix.csv`
- `outputs/paper/synthetic/run_log.csv`
- Open data → Zenodo upload (no Stadtbach-specific data used)

### Step 5 — Build Sensitivity All-Levels Runner ✅ DONE (511 lines)
**File:** `scripts/paper/run_sensitivity_all_levels.py`
**Logic:** For each of L1/L2/L3 configs: run OAT sensitivity (7 params × 3 values = 21
           runs per level = 63 total). Compute sensitivity index per param per level.
**Parameters with literature-justified ranges:**
- Gas price ±20% (ENTSO-G volatility)
- Electricity price ±20% (EPEX Austria historical)
- CO2 price ±50% (EU ETS range)
- HP Carnot factor ±10% (manufacturer uncertainty)
- Storage loss rate 0.5–1.5× (insulation quality)
- Storage efficiency ±3%
- Annual heat demand ±10% (weather year variability)
**Outputs:**
- `outputs/paper/sensitivity/sensitivity_indices_by_level.csv`
- `outputs/paper/sensitivity/sensitivity_run_log.json`

### Step 6 — Build Sensitivity Heatmap Figure ✅ DONE (renders with placeholder data)
**File:** `scripts/paper/plot_sensitivity_heatmap.py`
**Input:** `outputs/paper/sensitivity/sensitivity_indices_by_level.csv`
  Falls back to placeholder data with warning if file missing — safe to run anytime.
**Output:** `outputs/paper/figures/figX_sensitivity_heatmap.pdf` + `.png`
**Style:** Two-panel: left = heatmap (YlOrRd, cell annotations), right = tornado bar (L3 only)

### Step 7 — Extend Scenario Matrix to 3 Levels ✅ DONE
**File:** `scripts/paper/run_uncertainty_study.py`
**Change:** Added `--all-levels` flag + `run_scenarios_all_levels()` function
**Run:** `python scripts/paper/run_uncertainty_study.py --all-levels`
**Outputs:**
- `outputs/paper/scenarios/scenario_matrix_all_levels.csv`
- `outputs/paper/scenarios/scenario_matrix_all_levels.md`

### Step 8 — Extend Storage Figure for Weekly View ✅ DONE
**File:** `scripts/paper/plot_storage_comparison.py`
**Change:** Added `plot_weekly_soc()` — winter/summer weekly SOC, L1 vs L3 overlay,
           night shading bands, auto-called from main()
**Output:** `outputs/paper/figures/fig_storage_weekly_soc.pdf` + `.png`

---

## Execution Order (run when real data available)

```bash
# 1. Run full pipeline (L1 + L2 + L3, 8760h, MIP gap 0.01%)
python scripts/paper/run_all_levels.py

# 2. Validate L3 against measured data (needs data/stadtbach_measured_2023.csv)
python scripts/paper/validate_against_measured.py \
    --l3 outputs/paper/L3/pf_timeseries.csv \
    --measured data/stadtbach_measured_2023.csv \
    --outdir outputs/paper/validation/

# 3. Run sensitivity across all 3 levels (63 solves)
python scripts/paper/run_sensitivity_all_levels.py

# 4. Run scenario matrix across all 3 levels (9 scenarios × 3 levels = 27 solves)
python scripts/paper/run_uncertainty_study.py --all-levels

# 5. Run synthetic parametric study (108 solves, ~2-3h)
python scripts/paper/run_synthetic_parametric.py

# 6. Generate all figures
python scripts/paper/plot_sensitivity_heatmap.py
python scripts/paper/plot_storage_comparison.py \
    --l1 outputs/paper/L1/pf_timeseries.csv \
    --l2 outputs/paper/L2/pf_timeseries.csv \
    --l3 outputs/paper/L3/pf_timeseries.csv \
    --outdir outputs/paper/figures/
python scripts/paper/plot_co2_comparison.py \
    --l1 outputs/paper/L1/costs.json \
    --l2 outputs/paper/L2/costs.json \
    --l3 outputs/paper/L3/costs.json \
    --outdir outputs/paper/figures/
python scripts/paper/plot_cost_comparison.py \
    --l1 outputs/paper/L1/costs.json \
    --l2 outputs/paper/L2/costs.json \
    --l3 outputs/paper/L3/costs.json \
    --outdir outputs/paper/figures/
python scripts/paper/plot_dispatch_comparison.py \
    --l1 outputs/paper/L1/pf_timeseries.csv \
    --l2 outputs/paper/L2/pf_timeseries.csv \
    --l3 outputs/paper/L3/pf_timeseries.csv \
    --outdir outputs/paper/figures/
```

---

## Data Requirements Summary

| Data | Status | File path |
|------|--------|-----------|
| Measured monthly gas consumption | **IN PROGRESS** | `data/stadtbach_measured_2023.csv` |
| Measured monthly electricity purchase | **IN PROGRESS** | same file |
| Measured HP operating hours (monthly) | **IN PROGRESS** | same file |
| Measured storage cycle count (monthly) | **IN PROGRESS** | same file |

---

## Key Design Decisions (Locked)

- Storage capacity **identical** across L1/L2/L3 (dispatch-only, no sizing)
- Physics model (Q = U·L·ΔT) applied at L2 and L3; absent at L1
- MIP gap: **0.0001** (0.01%) for all paper runs
- Stadtbach data: **confidential** — anonymised parameters in Appendix A.4
- Synthetic network data: **open** — Zenodo DOI to be assigned
- CO2 intensity: **hourly** resolution (justified by Section 7.4)
- Solver: HiGHS (open-source, reproducible without licence)
