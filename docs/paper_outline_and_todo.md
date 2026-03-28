# Paper Outline: Spatial Resolution in District Heating Optimization
## Comparing 1-Node, 5-Node, and 30-Node MILP Models Under Perfect Forecast

---

## Proposed Title (options)

1. *"Does Network Detail Matter? Comparing Copperplate, Reduced, and Full-Resolution MILP Models for District Heating Planning"*
2. *"Spatial Resolution Trade-offs in Mixed-Integer Linear Programming for District Heating Capacity Expansion"*
3. *"From Copperplate to 30-Node: The Impact of Network Granularity on District Heating Optimization"*

**Target Journal (suggestions):**
- *Applied Energy* (Elsevier) — Impact Factor ~11
- *Energy* (Elsevier) — Impact Factor ~9
- *Energy Conversion and Management* (Elsevier) — Impact Factor ~9
- *Applied Thermal Engineering* (Elsevier) — Impact Factor ~6.4
- *International Journal of Energy Research* (Wiley)

---

## Core Research Question

> **How much does the level of spatial network resolution affect investment decisions, dispatch results, and cost estimates in MILP-based district heating optimization — and when is a simplified copperplate model sufficient?**

### Sub-questions

| # | Research Question | Hypothesis |
|---|-------------------|-----------|
| RQ1 | Does ignoring network losses (1-node) systematically under-/over-estimate total cost? | Copperplate *underestimates* cost by neglecting pipe losses |
| RQ2 | Are investment decisions (HP capacity, storage size) robust across resolution levels? | High resolution changes optimal HP sizing near network bottlenecks |
| RQ3 | Is there a "sweet spot" where 5-node captures most 30-node accuracy at lower complexity? | 5-node captures ≥ 90% of cost accuracy at ~20% of the binary variable count |
| RQ4 | How does solve time scale with spatial resolution? | Super-linear scaling in binary variables |

---

## Paper Structure

### 1. Abstract (~250 words)
- Problem: DH planning models range from single-node (copperplate) to full network — no systematic comparison
- Method: MILP framework, three model variants, same case study, perfect forecast
- Results: [fill after runs] cost deviation, investment difference, solve time
- Conclusion: guideline for when to use each resolution

---

### 2. Introduction (~1,000 words)

**Topics to cover:**
- District heating role in decarbonization (EU 2050 targets, Directive 2018/2001)
- MILP as standard planning tool [Ref: 1, 2, 3]
- The copperplate assumption: ubiquitous but unvalidated [Ref: 4, 5]
- Research gap: no systematic comparison across resolution levels for the same case
- Contributions:
  1. A unified MILP framework (EnerGIS) that solves the same problem at three spatial resolutions
  2. Quantification of copperplate error for investment and operational decisions
  3. Guidelines for practitioners: when is a simplified model sufficient?
- Paper outline

**Key intro references:** Lund et al. [2014], Connolly et al. [2014], Vesterlund et al. [2017]

---

### 3. Literature Review (~1,500 words)

#### 3.1 MILP Models for District Heating
- Capacity expansion: Morvaj et al. [2016], Mesfun & Toffolo [2015]
- Dispatch optimization: Streckienė et al. [2009], Lund & Persson [2016]
- Combined design + operation: Vesterlund et al. [2017]

#### 3.2 Network Resolution in Energy Models
- Copperplate assumption in national energy models: Henning & Palzer [2014]
- Transmission constraints impact: Hirth [2013]
- Nodal vs. zonal in electricity: Morales et al. [2014]
- DH-specific: few studies exist — **this is the research gap**

#### 3.3 Pipe Heat Loss Modeling
- Steady-state: EN 13941 [2019], Frederiksen & Werner [2013]
- Dynamic: Benonysson et al. [1995], Schweiger et al. [2017]

#### 3.4 Heat Pump COP Modeling
- Analytical: Staffell et al. [2012], Ruhnau et al. [2019]
- Empirical lookup: EN 14825:2022

#### 3.5 Identification of the Gap
Summary table of existing studies and which spatial resolution they use → gap = no systematic comparison

---

### 4. Methodology (~2,000 words)

#### 4.1 MILP Problem Formulation
- Point to `docs/model_equations_and_sources.md` for full equations
- Summarize key equations inline:
  - Objective function (Eq. 2.1)
  - Heat bus balance (Eq. 3.1)
  - Storage dynamics (Eq. ST-1)
  - Pipe heat loss (Eq. PH-1)
  - COP model (Eq. COP-1)

#### 4.2 Three Model Variants

| Feature | Level 1 (1-node) | Level 2 (5-node) | Level 3 (30-node) |
|---------|-----------------|-----------------|------------------|
| Nodes | 1 (virtual) | 5 | 30 |
| Pipes | 0 | 4 | 22 |
| Heat loss modeled | ✗ | ✓ | ✓ |
| Pressure drop | ✗ | ✓ | ✓ |
| Per-node demand | ✗ | ✓ | ✓ |
| Transport delay | ✗ | ✗ | ✗ |
| Demand aggregation | Lumped | 4 zones | 23 zones |
| Pipe diameter range | — | 350–500 mm | 150–600 mm |

**Level 1 (Copperplate):** Single heat bus, no network. All generators and loads connected
to the same node. Pipe losses absent. Standard for national/regional energy models.

**Level 2 (5-node):** One producer node (plant) + four consumer zones (North 30%, South 40%,
Industrial 30%) + one junction. Pipes modeled with steady-state heat loss (Eq. PH-1).
Represents a district with clear spatial structure.

**Level 3 (30-node):** Star-of-stars topology: main plant → 5 junction nodes →
23 consumer zones. Full pipe network with heterogeneous diameters (150–600 mm).
Represents a realistic large district heating network.

#### 4.3 Perfect Forecast Assumption
All three models use Perfect Foresight (PF): the optimizer has access to the full time
series of demand, electricity prices, and temperatures at the time of solving. This
isolates the effect of spatial resolution from forecast uncertainty.

**Justification:** Perfect forecast is the standard for investment planning studies [5, 7, 15].

#### 4.4 Solver and Implementation
- Framework: EnerGIS (Python, Pyomo)
- Solver: Gurobi [or HiGHS if open-source] with MIP gap ≤ 1%
- Hardware: [fill in — CPU, RAM]
- Time horizon: 8,760 hours (full year 2023)
- Timestep: 1 hour

---

### 5. Case Study Description (~800 words)

#### 5.1 System Overview
- Name: [Stadtbach District Heating System — or anonymize as "Case Study City A"]
- Location: Central Europe (Germany/Austria)
- Heat demand: ~[X] GWh/yr
- Peak demand: ~[X] MW
- Temperature levels: supply 90°C, return 55°C
- Assets: Gas boiler (baseload), Heat pump (waste heat), Thermal storage

#### 5.2 Input Data
Table of timeseries data used:

| Data Series | Source | Resolution | Unit |
|------------|--------|-----------|------|
| Heat demand | Synthetic (hourly, annual) | 1 h | MW |
| Electricity spot price | ENTSO-E / synthetic | 1 h | EUR/MWh |
| Grid CO₂ intensity | UBA / synthetic | 1 h | kg CO₂/MWh |
| Ambient temperature | DWD / synthetic | 1 h | °C |
| Ground temperature | Fixed (10°C) | constant | °C |
| Waste heat (4 sources) | Synthetic | 1 h | MW + K |

**[TODO: Describe the actual `data/Import_Data.csv` dataset in detail — source, year, units]**

#### 5.3 Asset Parameters
Table of all components and their parameters — pulled from `level1_copperplate.yaml` etc.:

| Component | Level 1 | Level 2 | Level 3 |
|-----------|---------|---------|---------|
| Gas boiler capacity [MW] | 150 | 200 | 200 |
| Heat pump capacity [MW] | 80 | 150 + 40 | 100 |
| Storage energy [MWh] | — | 500 | 1,000 |
| Storage power [MW] | — | 50 | 100 |
| Total pipe length [m] | 0 | ~4,800 | ~[X] |

**[TODO: Ensure all three configs use comparable/scaled parameters for fair comparison]**

#### 5.4 Economic Parameters

| Parameter | Value | Unit | Source |
|-----------|-------|------|--------|
| Gas price | 58.6 | EUR/MWh | Eurostat 2023 |
| HP CAPEX | [X] | EUR/MW | [Ref] |
| Storage CAPEX | [X] | EUR/MWh | [Ref] |
| Boiler CAPEX | [X] | EUR/MW | [Ref] |
| Asset lifetimes | 20–25 | years | VDI 2067 |
| Carbon price | 65 | EUR/tCO₂ | EU ETS 2023 |

**[TODO: Fill in CAPEX values from config files]**

---

### 6. Results (~2,500 words)

#### 6.1 Baseline Dispatch Comparison (all 3 levels, 1 representative week)
**Figures needed:**
- Fig. 1: Heat dispatch stack (boiler, HP, storage) for 1 representative winter week — 3 panels (one per level)
- Fig. 2: Storage state-of-charge comparison across levels

**Key questions to answer:**
- Do dispatch patterns change when network constraints are active?
- Does HP dispatch near network-constrained nodes differ in Level 3?

#### 6.2 Annual Cost Comparison
**Figure 3:** Stacked bar chart: CAPEX + OPEX by component — 3 bars (one per level)

**Table 1: Cost breakdown**

| Cost Component | Level 1 (1-node) | Level 2 (5-node) | Level 3 (30-node) |
|----------------|---------|---------|---------|
| Energy cost [EUR] | | | |
| Fuel cost [EUR] | | | |
| CO₂ cost [EUR] | | | |
| Demand charge [EUR] | | | |
| HP CAPEX [EUR] | | | |
| Storage CAPEX [EUR] | | | |
| **Total [EUR]** | | | |
| **Δ vs. Level 3 [%]** | | | — |

#### 6.3 Investment Decisions
**Table 2: Optimal capacity decisions**

| Decision Variable | Level 1 | Level 2 | Level 3 |
|------------------|---------|---------|---------|
| HP capacity built [MW] | | | |
| Storage energy [MWh] | | | |
| Storage power [MW] | | | |
| Boiler utilization [%] | | | |

**Key finding:** Does the copperplate model over/under-invest in HP?

#### 6.4 Network Loss Analysis (Levels 2 and 3 only)
**Table 3: Pipe heat losses**

| Metric | Level 2 | Level 3 |
|--------|---------|---------|
| Annual supply pipe loss [MWh] | | |
| Annual return pipe loss [MWh] | | |
| Total loss as % of demand | | |
| Max hourly loss [MW] | | |

**Figure 4:** Spatial heat loss map (Level 3) — node temperatures / pipe loss heatmap

#### 6.5 Computational Performance
**Table 4: Solver statistics**

| Metric | Level 1 | Level 2 | Level 3 |
|--------|---------|---------|---------|
| Binary variables | | | |
| Continuous variables | | | |
| Constraints | | | |
| Solve time [s] | | | |
| MIP gap achieved [%] | | | |

#### 6.6 Sensitivity of Key Results
Run sensitivity analysis (Section 14 of equations doc) for each level:
- Are cost rankings stable across gas price / electricity price scenarios?
- Does the investment recommendation change?

**Figure 5:** Tornado chart — sensitivity indices for 7 parameters across 3 levels

---

### 7. Discussion (~1,000 words)

#### 7.1 When Does the Copperplate Assumption Fail?
- Threshold network loss fraction (e.g., > 5% → spatial model needed)
- Network bottlenecks that change optimal HP placement
- Asset sitting problems that 1-node cannot capture

#### 7.2 Is 5-Node a Sufficient Approximation of 30-Node?
- Cost deviation Level 2 vs. Level 3
- Investment decision alignment
- Computational savings

#### 7.3 Practical Guidelines for Practitioners

| System type | Recommended model |
|-------------|------------------|
| Planning study (national/regional) | Level 1 (copperplate) |
| Single-district capacity planning | Level 2 (5-node zone model) |
| Network design + asset siting | Level 3 (full network) |
| Operational dispatch only | Level 1 |

#### 7.4 Limitations
- Perfect forecast assumption (real systems need rolling horizon or MPC)
- Static temperature levels (fixed 90°C/55°C supply)
- No transport delay modeled
- Synthetic demand data
- Single case study — generalizability?

---

### 8. Conclusions (~500 words)
- Summarize RQ1–RQ4 answers with numbers
- Main contribution: quantified copperplate error
- Practical recommendation
- Future work: (a) imperfect forecast comparison, (b) 4th Gen DH (lower temperatures), (c) multi-year investment planning

---

## What Still Needs to Be Done

### Phase 1: Case Study Setup (CRITICAL — before results)

- [ ] **Align the three configs to the same physical system**
  - Same total demand, same available assets
  - Level 2/3 = Level 1 demand distributed spatially
  - Verify configs: `configs/templates/level1_copperplate.yaml`, `level2_5node.yaml`, `level3_30node_template.yaml`
  - *Issue:* Currently Level 1 has 150 MW boiler + 80 MW HP, Level 2 has 200 MW boiler + 150 MW HP — **these are not the same system. Need to normalize.**

- [ ] **Prepare a common annual dataset** (8,760 h, 2023)
  - Check `data/Import_Data.csv` is full-year
  - Verify all required columns present
  - Document data sources and any synthetic generation method

- [ ] **Define pipe parameters for Level 2 and 3**
  - U-values, pipe lengths, diameters from real or representative network
  - Calculate expected annual heat loss (target: verify ~3–8% of demand, typical DH range)

- [ ] **Align CAPEX/OPEX parameters** across all three configs
  - Same economic lifetime, same CAPEX per MW, same fuel prices

### Phase 2: Numerical Experiments (RUN THE MODELS)

- [ ] **Run all 3 levels on full 1-year horizon** with PF mode
  - Record: total cost, cost breakdown, investment decisions, solve time
  - Use: `python -m energis run --config configs/templates/levelX.yaml --output outputs/runs/levelX/`

- [ ] **Extract and compare KPIs** using BenchmarkSuite
  - Script: use `energis/comparison/benchmark.py`
  - Export: `outputs/comparison/level_comparison.csv`

- [ ] **Run sensitivity analysis** for all 3 levels
  - Use `energis/analysis/sensitivity.py` → `create_standard_sensitivity_study()`
  - 7 parameters × 3 levels × 3 variations = 63 model runs

- [ ] **Generate network loss timeseries** for Level 2 and 3
  - From `thermal_network/pipes_timeseries.csv`
  - Calculate: annual loss, peak hourly loss, seasonal pattern

### Phase 3: Figures and Tables

- [ ] **Fig 1:** 3-panel dispatch stack (1 winter week) → from `pf_timeseries.csv`
- [ ] **Fig 2:** Annual storage SOC comparison
- [ ] **Fig 3:** Cost breakdown bar chart (3 bars, stacked CAPEX/OPEX)
- [ ] **Fig 4:** Network heat loss map (Level 3) — spatial visualization
- [ ] **Fig 5:** Tornado chart — sensitivity indices
- [ ] **Table 1:** Annual cost breakdown (fill template above)
- [ ] **Table 2:** Investment decisions
- [ ] **Table 3:** Network losses
- [ ] **Table 4:** Solver statistics

### Phase 4: Paper Writing

- [ ] **Abstract** (write last, after results known)
- [ ] **Introduction:** Add 2–3 paragraphs on EU energy policy context
- [ ] **Literature review:** 10–15 papers, position against existing work
- [ ] **Case study:** Describe dataset origin (real or synthetic? disclose)
- [ ] **Results:** Fill all tables and figure captions
- [ ] **Discussion:** Compare to other papers' copperplate findings
- [ ] **References:** Format for target journal (check author guidelines)

### Phase 5: Compliance and Quality

- [ ] **Check journal requirements** (figure format, reference style, word count)
- [ ] **Ethics/data statement:** Synthetic data → no issues; real data → check permissions
- [ ] **Code/data availability statement:** EnerGIS as open-source? Zenodo DOI?
- [ ] **Nomenclature table** — use `docs/model_equations_and_sources.md` §15
- [ ] **Proofread equations** — verify all equation labels in paper match equations doc

---

## Key Design Decision: How to Make 3 Levels Comparable

The 3 configs must represent the **same physical system** at different spatial resolutions.
This means:

```
Level 1:  Aggregate demand = 100%
          All assets at one virtual node
          No pipe losses

Level 2:  Node "plant" has all generators
          Demand split: North 30%, South 40%, Industrial 30%
          Pipe losses added (typically +3–6% more generation needed)
          → Total cost should be HIGHER than Level 1 by the loss fraction

Level 3:  Same total demand, split across 23 zones
          More detailed pipe network → more losses captured
          → Total cost should be HIGHER than Level 2 if more losses are resolved
```

**This is the core finding of the paper:** The copperplate model systematically
underestimates total cost by the fraction of heat losses it ignores.

**Expected result structure:**
```
Cost(Level 1) < Cost(Level 2) ≈ Cost(Level 3)
              ↑
        This gap = value of spatial modeling
              ~3–8% of total cost (typical DH pipe losses)
```

---

## Suggested Run Commands

```bash
# Run all three levels
python -m energis run --config configs/templates/level1_copperplate.yaml \
    --output outputs/runs/level1/ --horizon 8760

python -m energis run --config configs/templates/level2_5node.yaml \
    --output outputs/runs/level2/ --horizon 8760

python -m energis run --config configs/templates/level3_30node_template.yaml \
    --output outputs/runs/level3/ --horizon 8760

# Compare results
python -m energis compare \
    outputs/runs/level1/ outputs/runs/level2/ outputs/runs/level3/ \
    --labels "1-node" "5-node" "30-node" \
    --output outputs/comparison/

# Sensitivity analysis
python -m energis sensitivity --config configs/templates/level1_copperplate.yaml \
    --output outputs/sensitivity/level1/
```

---

*Last updated: 2026-03-28 | Status: Phase 1 (Case Study Setup) in progress*
