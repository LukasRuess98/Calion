# Paper Study: Network Topology Abstraction Impact (Dispatch-Only)

## Overview

Three dispatch-only configuration files supporting the paper:
**"Network Topology Abstraction Impact on Operational Dispatch of Industrial Heat Systems"**

All three represent the **same fixed asset base** optimized for **operational dispatch only** (no capacity decisions). The sole experimental variable is **network topology abstraction level**.

---

## Configuration Files

### L1_copperplate_dispatch.yaml
**Copperplate Model (Single Node)**

- **Nodes**: 1 aggregated
- **Pipes**: NONE  
- **Heat losses**: 0% (theoretical minimum)
- **Expected cost**: Lowest (no network inefficiency)
- **Solve time**: ~2.3 min
- **Use case**: Baseline / lower bound

### L2_simplified_dispatch.yaml  
**Simplified 5-Node Network**

- **Nodes**: 5 (plant + 4 consumer zones)
- **Pipes**: 5 trunks, ~14,250 m total
- **Heat losses**: ~26 GWh/yr (5% of demand)
- **Expected cost**: Medium
- **Solve time**: ~8–10 min
- **Use case**: **Recommended for planning** (95% of L3 value, 40% faster)

### L3_detailed_dispatch.yaml
**Realistic 30-Node Network**

- **Nodes**: 30 (star-of-stars topology)
- **Pipes**: 22 connections, ~14,250 m total
- **Heat losses**: ~26 GWh/yr (5% of demand)
- **Expected cost**: Highest (realistic constraints)
- **Solve time**: ~14–20 min
- **Use case**: Detailed engineering

---

## Unified Principles (All Three Identical)

| Parameter | Value |
|-----------|-------|
| **Gas boiler** | 200 MW, η = 0.90 (FIXED) |
| **CHP** | 20 MW electric (FIXED) |
| **Heat pump** | 100 MW thermal (FIXED) |
| **Storage** | 500 MWh / 50 MW (FIXED) |
| **COP method** | Analytical LMTD (identical across L1/L2/L3) |
| **Loss model (L2/L3)** | Physics-based PWL, U = 0.15 W/(m·K) |
| **No capacity decisions** | Dispatch-only optimization ✓ |
| **Optimization mode** | Perfect foresight |
| **Time horizon** | 8,760 hours (full year 2023) |
| **Supply temp** | 90°C |
| **Return temp** | 55°C |
| **Ground temp** | 10°C |
| **Solver** | HiGHS (1% MIP gap) |
| L1 HP capacity | 80 MW | 100 MW |
| L1 storage | none | 500 MWh / 50 MW |
| L1 WRG sources | WRG1–4 | WRG1, WRG2 |
| L2 HP capacity | 150 MW (plant) + 40 MW (south) | 100 MW (plant only) |
| L2 distributed HP at south node | present | removed |
| L2 temperature key | `supply_temp_nominal_c` | `supply_temp_c` |
| L3 boiler efficiency | 0.92 | 0.90 |
| L3 HP capacity | 100 MW (correct) | unchanged |
| L3 storage | 1 000 MWh / 100 MW | 500 MWh / 50 MW |
| L3 WRG sources | none | WRG1, WRG2 |
| L3 HP min_load | not set | 0.2 |

## Expected result structure

Because L2 and L3 model pipe heat losses that L1 ignores, the optimizer
in L2 and L3 must dispatch **more** generation to cover the same end-user demand.
This means:

```
Total cost L1 ≤ Total cost L2 ≤ Total cost L3
              ↑                 ↑
         copperplate       5-node vs
           error           30-node
                           refinement
```

The magnitude of the gaps is the central result of the paper.

## Running the study

```bash
# Baseline runs (one per level)
 python -m calion.run configs/memmingen/Memmingen_L3.yaml
```

---

## Expected Results (from paper Section 5)

| Metric | L1 | L2 | L3 | Notes |
|--------|----|----|-----|----|
| **Annual fuel [GWh]** | 163.7 | 163.6 | 163.5 | Minimal variation (losses compensated by HP) |
| **Network losses [GWh]** | 0.0 | 26.1 | 26.5 | L2 ≈ L3 (same physics) |
| **Operational cost [€M]** | €5.19 | €5.14 | €5.06 | **L1→L3: −2.5% (€130k)** |
| **Electricity import [GWh]** | 42.3 | 41.8 | 41.5 | L3 uses 1.9% less grid |
| **Storage cycles** | 112 | 112 | 110 | Minimal variation |
| **Solve time [min]** | 2.3 | 8.7 | 14.2 | 6.2× spread |
| **MIP gap [%]** | <0.1 | 0.3 | 0.9 | All gaps <1% |

---

## Key Findings

1. **Topology matters less than expected**: Only 2.5% cost spread L1→L3 despite 30× node difference
2. **Loss model dominates**: L1→L2 (loss introduction) explains 95% of variation; L2→L3 (spatial detail) explains <0.5%
3. **L2 sufficient for planning**: Achieves 99% of L3 value at 40% faster solve
4. **Dispatch patterns similar**: All three optimize fuel/storage similarly; topology affects cost, not strategy

---

## Data Input

Each config expects: `data/Import_Data_yearly.csv` with columns:
- `Datum`: Timestamp (hourly, 8,760 rows)
- `waermebedarf_MWth`: Heat demand [MW]
- `strompreis_EUR_MWh`: Electricity price [€/MWh]
- `grid_co2_kg_MWh`: Grid CO₂ [kg/MWh]
- `T_WRG1_C`, `T_WRG2_C`: Waste heat temps [°C]

---

## Dependencies

- **Framework**: CALION ≥1.5
- **Solver**: HiGHS (or Gurobi/CPLEX)
- **Data**: Import_Data_yearly.csv
- **Python**: ≥3.8

---

## Publication Status

Supporting paper for: **Energy Conversion and Management** (targeted Q4 2026)

See also: `docs/paper 1/PAPER_DRAFT_SECTIONS_4-7.md` for research narrative
python -m calion run --config configs/paper/L1_copperplate_dispatch.yaml