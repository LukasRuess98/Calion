# L5 OPERATIONAL VALIDATION STRATEGY
## Real-World Heating Grid Verification

**Project**: CALION (L3 MILP Optimization)  
**Date**: March 31, 2026  
**Status**: Strategic Proposal (No Changes to Current Paper)  
**Purpose**: Validate L3 optimization against real grid operational data

---

## Executive Summary

You have real operational heating grid data (heat exchanger data, BHKW, P2H, HP, etc.). This document outlines how to design an **L5 operational validation study** that:

1. **Does NOT modify paper content** (Sections 1–7 remain unchanged)
2. **Builds on L3 framework** (uses existing CALION L3 model as baseline)
3. **Validates key assumptions** (COP tables, loss models, asset performance)
4. **Addresses E4 gap** explicitly (operational validation = future work → becomes current work)
5. **Positions for follow-up publication** (validation results as separate paper or journal extension)

---

## Part 1: Understanding the L1–L4 Hierarchy Context

### Current Framework Position

```
L1 (Copperplate)         L2 (Simplified)         L3 (CALION)              L4 (Full Simulation)
├─ Single node           ├─ 5–10 agg. zones      ├─ 20–30 nodes            ├─ Distributed params
├─ No losses             ├─ PWL losses           ├─ PWL losses             ├─ Full DAE solver
├─ Fixed COP             ├─ Pre-computed COP     ├─ Pre-computed COP       ├─ Dynamic COP
├─ ~2 min solve          ├─ ~8–10 min solve      ├─ ~14–20 min solve       ├─ 8–12 hours solve
└─ UNREALISTIC           └─ GOOD for planning    └─ OPTIMAL for capex      └─ REALITY (slow)


L5 (OPERATIONAL VALIDATION) — PROPOSED NEW TIER
├─ Deploy L3-optimized design on real grid
├─ Measure: asset performance, network temperatures, losses
├─ Compare: L3 predictions vs. actual operations
├─ Outcome: ±5–10% MAPE validation, model refinement roadmap
└─ Timeline: 2–3 years (continuous operational data collection)
```

### What L5 Adds to L3

| Aspect | L3 (CALION) | L5 (Operational) | Why L5 Matters |
|--------|------------|---|---|
| **COP validation** | Pre-computed from manufacturer curves | Real BHKW/HP/P2H measurements (hourly logs) | Identifies systematic bias; weather/aging effects |
| **Network losses** | U = 0.15 W/(m·K) (constant, averaged) | Measured ΔT at each node, actual U-values | Validates spatial discretization accuracy |
| **Storage behavior** | PWL with 8–12 segments (static capacity) | Actual tank logs (temperature stratification, aging) | Reveals loss model inadequacy at low SOC |
| **Asset dispatch** | Optimal hourly decisions | Actual plant logs (ramp rates, part-load efficiency) | Sub-optimal real dispatch vs. optimal L3 dispatch |
| **System integration** | Assumed perfect control | Real hydraulic loops, sensor lags, manual overrides | Practical feasibility of L3 recommendations |
| **Impact quantification** | Simulated €0.35M/yr savings (L1→L3) | Actual €0.30–0.40M/yr (with real ops friction) | Realistic RoI for utilities making investment decisions |

---

## Part 2: Your Data Assets & How to Use Them

### A. What You Have (Heating Grid Data)

From your description:
- **Heat exchanger specifications** (U-values, surface area, effectiveness)
- **BHKW data** (CHP specifications: thermal efficiency, electrical efficiency, part-load curves)
- **P2H data** (Power-to-Heat electrolyzer: rated power, ramping, efficiency)
- **HP data** (Heat pump: rated capacity, COP curve vs. source/sink temps)
- **Network topology** (pipe layout, diameters, insulation)
- **Historical operational logs** (ideally 1+ years of hourly meter data)

### B. Validation Workflow (3-Year Phased Approach)

```
YEAR 1: PARAMETER EXTRACTION & BASELINE CALIBRATION
├─ Task 1.1: Extract asset performance curves from your data
│  ├─ BHKW: efficiency vs. part-load (percentage of rated capacity)
│  ├─ HP: COP vs. (T_source, T_sink), ramping rates
│  ├─ P2H: efficiency curve, turndown ratio
│  └─ Deliverable: CSV files with piecewise-linear curves
│
├─ Task 1.2: Calibrate network loss model
│  ├─ Use measured T_supply, T_return at multiple nodes
│  ├─ Infer actual U-values per pipe segment
│  ├─ Compare against design U = 0.15 W/(m·K)
│  └─ Deliverable: Updated pipe loss parameters
│
└─ Task 1.3: Run L3 on historical year (2024 or latest available)
   ├─ Configure CALION with YOUR measured asset curves
   ├─ Optimize for 2024 electricity/gas prices
   ├─ Compare L3 dispatch schedule vs. actual 2024 operations
   └─ Deliverable: Baseline mismatch analysis (MAPE ≈ 10–15% expected)

YEAR 2: IMPLEMENT L3-OPTIMIZED DISPATCH (SOFT ROLLOUT)
├─ Task 2.1: Deploy L3 advisory control (read-only feedback)
│  ├─ Feed CALION dispatch to plant operators (e.g., weekly plan)
│  ├─ Operators decide: follow or override (builds trust)
│  ├─ Measure actual vs. L3 recommendation MAPE
│  └─ Log all deviations (identify behavioral patterns)
│
├─ Task 2.2: Collect high-fidelity measurement data
│  ├─ Subcool/superheat at each HP inlet/outlet
│  ├─ Mass flow estimates (ΔP sensors, pump curves)
│  ├─ Storage tank internal temperature (min 3 levels)
│  ├─ All electrical inputs (real-time CHP/HP/P2H power)
│  └─ Deliverable: 1-year granular dataset (commissioning-grade)
│
└─ Task 2.3: Iterative model refinement
   ├─ Update L3 parameters based on Year 1 calibration
   ├─ Rerun L3 forecast vs. Year 2 actuals
   ├─ Measure MAPE progression (target: 10% → 8% → 6%)
   └─ Identify remaining systematic errors

YEAR 3: VALIDATION & PUBLICATION ROADMAP
├─ Task 3.1: Full operational validation study
│  ├─ 36-month continuous operation under L3 guidance
│  ├─ Compare cumulative cost: L3 dispatch vs. actual history
│  ├─ Quantify savings: projected vs. realized
│  └─ Deliverable: Validation report (MAPE <±5%)
│
├─ Task 3.2: Root cause analysis of residual errors
│  ├─ Sensor accuracy limitations (±2–3% typical)
│  ├─ Model approximations (PWL, fixed COP assumption)
│  ├─ Real control delays (sub-hourly dynamics L3 omits)
│  └─ Deliverable: Error budget breakdown
│
└─ Task 3.3: Publication strategy
   ├─ Option A: Journal paper "Operational Validation Study" (separate submission)
   ├─ Option B: Extension to current paper (Section 8 postscript)
   ├─ Option C: Utility case study for practitioner venue
   └─ Deliverable: 3,000–5,000 word validation section
```

---

## Part 3: Technical Validation Checklist

### 3.1 Asset Performance Curves

**BHKW (CHP Unit)**

What you need from your data:
```
| Part-Load (%) | η_thermal (%) | η_electrical (%) | Ramp Rate (MW/min) |
|---|---|---|---|
| 20% | 78 | 32 | 0.5 |
| 40% | 82 | 34 | 0.8 |
| 60% | 85 | 35 | 1.0 |
| 80% | 87 | 35 | 1.2 |
| 100% | 89 | 36 | 1.5 |
```

**Validation Steps**:
1. Extract part-load efficiency curves from BHKW historical logs
2. Compare with L3 assumptions (typically constant η = 85%)
3. Create PWL approximation if variability >5%
4. Update L3 config: `bhkw_efficiency_curve.csv` (or keep constant if negligible)

**Deliverable**: `assets/bhkw_performance_curve.csv`

---

**Heat Pump (HP)**

What you need:
```
COP vs. Temperature Matrix:
           T_source = 15°C  | 20°C  | 25°C  | 30°C  |
T_sink = 60°C:   COP 3.2 | 3.5 | 3.8 | 4.0 |
T_sink = 70°C:   COP 2.8 | 3.1 | 3.4 | 3.6 |
T_sink = 80°C:   COP 2.4 | 2.7 | 3.0 | 3.2 |
```

**Validation Steps**:
1. Extract from your HP performance data (hourly T_source, T_sink → measured COP[t])
2. Compare against CALION's analytical LMTD formula: $\text{COP}[t] = \eta_{\text{rel}} \times \frac{T_{\text{sink}}}{T_{\text{sink}} - T_{\text{source}}[t]}$
3. Calculate residual error: $(COP_{\text{measured}} - COP_{\text{LMTD}}) / COP_{\text{measured}}$
4. If |error| > 3%, update η_rel parameter (currently 0.6; may need tuning to 0.55–0.65)

**Deliverable**: 
- `assets/hp_cop_matrix.csv` (measured 2D table)
- `assets/hp_validation_report.txt` (residuals, recommended η_rel value)

---

**P2H (Power-to-Heat)**

What you need:
```
| Input Power (%) | Thermal Output (%) | Response Time (s) |
|---|---|---|
| 10% | 8 | <5 |
| 50% | 48 | <2 |
| 100% | 100 | <1 |
```

**Validation Steps**:
1. Verify linear power→heat relationship (typical: 95–98% efficient all operating points)
2. Check dynamic response: Does L3's hourly discretization miss rapid ramps?
3. Document minimum turndown ratio (e.g., 20% of rated = minimum operating point)

**Deliverable**: `assets/p2h_performance_curve.csv`

---

### 3.2 Network Loss Model Validation

**Current L3 Model**:
- Line loss: $Q_{\text{loss}} = U \times L \times (T_{\text{supply}} - T_{\text{return}})$
- Assumption: U = 0.15 W/(m·K), constant for all pipes
- Validation method: Measure actual ΔT across long pipes, back-calculate U

**Procedure**:

1. **Identify 3–5 longest pipes** (highest impact on losses)
   - Example: Main trunk from substation to industrial area (2,000 m)

2. **Install temperature sensors** (if not already present; or use existing logs):
   - T_supply at pipe inlet
   - T_return at pipe outlet
   - Ambient T at multiple points along route

3. **Calculate pipe-specific U-value**:
   $$U_{\text{actual}} = \frac{Q_{\text{loss}} / (L \times \Delta t)}{T_{\text{supply}} - T_{\text{return}}}$$
   where $Q_{\text{loss}} = (\text{mass flow}) \times c_p \times (T_{\text{in}} - T_{\text{out}})$

4. **Compare L3 assumption (U=0.15) vs. measured**:
   - If U_measured ≈ 0.12–0.18: ✅ Model is good (±20% tolerance acceptable)
   - If U_measured < 0.10: Network is **better insulated** than assumed (saves cost)
   - If U_measured > 0.25: Network is **worse** (model underestimates losses by 2–3%)

5. **Update L3 config** if deviation >20%:
   ```yaml
   network:
     pipe_loss:
       u_value_w_per_m_k: 0.15  # Update to measured value
       u_value_distribution: global  # or pipe-specific if needed
   ```

**Deliverable**: `validation/network_loss_calibration.csv` (measured U-values per pipe segment)

---

### 3.3 Storage Model Validation

**Current L3 Model**:
- PWL approximation with 8–12 segments
- Assumption: Loss rate ∝ SOC (linear PWL)
- Validation: Compare thermal stratification vs. bulk loss estimate

**Procedure**:

1. **Measure tank stratification** (if available; multi-level thermometers):
   - Typical 500 MWh tank: 3 temperature levels (top, middle, bottom)
   - Measure hourly over 1 month

2. **Calculate actual standby losses**:
   - Select days with **no charging/discharging** (standby only)
   - Measure ΔT_tank over 24 hours
   - Infer loss power: $P_{\text{loss}} = m \times c_p \times \Delta T / \Delta t$

3. **Compare against L3 PWL model**:
   - L3 assumes: $P_{\text{loss}} = a \times SOC + b$ (linear)
   - Measure: Is actual loss constant, or strongly dependent on SOC?
   - Calculate MAPE: $\frac{1}{n} \sum \frac{|P_{\text{loss,model}} - P_{\text{loss,measured}}|}{P_{\text{loss,measured}}}$

4. **Validation acceptance criteria**:
   - MAPE < 10%: ✅ Model is adequate
   - MAPE 10–20%: ⚠️ Acceptable with caveats (document in paper)
   - MAPE > 20%: ❌ Requires PWL refinement (add more segments or temperature-dependent terms)

**Deliverable**: `validation/storage_loss_analysis.csv`

---

## Part 4: Operational Comparison Methodology

### 4.1 Historical Hindcast (Year 1 Baseline)

**Goal**: Run L3 on past year to establish baseline prediction accuracy

**Steps**:

1. **Collect historical data**:
   - Full year of operational logs (2024 or latest): hourly demand, asset status, dispatch decisions
   - Historical electricity prices, gas prices, CO2 factors
   - Weather data (ambient temperature if affecting heat sources)

2. **Configure L3 for historical year**:
   ```yaml
   settings:
     horizon: annual  # 8,760 hours
     mode: perfect_foresight  # Assumes perfect wind/demand forecast (best case)
     start_date: 2024-01-01
     end_date: 2024-12-31
   
   # Use YOUR measured parameters (from Part 3)
   assets:
     bhkw:
       eta_thermal: 0.87  # Updated from your data
       eta_electrical: 0.35
     hp:
       eta_rel: 0.60  # Or your calibrated value
     storage:
       pwl_segments: 10
       loss_file: measured_loss_curve.csv
   
   network:
     pipe_u_value: 0.15  # Or your measured value
   ```

3. **Run L3 optimization**:
   - Output: Optimal dispatch schedule (hourly BHKW/HP/P2H/Storage dispatch)
   - Compare to actual 2024 operations (did operators follow similar patterns?)

4. **Calculate metrics**:

   **Dispatch Alignment** (do L3 and actual dispatch agree?):
   $$\text{MAPE}_{\text{dispatch}} = \frac{1}{n} \sum_{t=1}^{n} \frac{|Q_{\text{L3}}[t] - Q_{\text{actual}}[t]|}{|Q_{\text{actual}}[t] + 0.1|}$$
   
   (Add 0.1 MW denominator floor to avoid division errors during low-load periods)
   
   Expected: MAPE ≈ 15–25% (L3 optimal vs. manual/rule-based actual operations)

   **Energy Balance Closure** (does energy balance hold?):
   $$\text{Closure} = \frac{\sum_t Q_{\text{supply}}[t]}{\sum_t (Q_{\text{demand}}[t] + Q_{\text{loss}}[t])}$$
   
   Expected: ±2% (accounting for measurement noise, rounding)

   **Cost Accuracy**:
   $$\text{Cost}_{\text{L3}} \text{ vs. } \text{Cost}_{\text{actual}} = \frac{\text{Cost}_{\text{L3}} - \text{Cost}_{\text{actual}}}{\text{Cost}_{\text{actual}}}$$
   
   Expected: L3 should be 5–15% lower (optimal dispatch cost reduction).

**Deliverable**: `validation/year1_hindcast_report.md`
```markdown
# Year 1 Hindcast Report

## Summary
- Dispatch MAPE: 18%
- Energy balance closure: ±1.5%
- L3 cost prediction: -12% vs. actual 2024
- Conclusion: Model predictions align with operations within ±20%

## Detailed Results
[Graphs, tables, residual analysis]
```

---

### 4.2 Performance Curves: Prediction vs. Reality

**For each major asset, create a scatter plot** comparing L3 predicted performance vs. measured.

**Heat Pump COP Validation**:
```
Y-axis: Measured COP (from operational logs)
X-axis: L3 Predicted COP (from LMTD formula)

Scatter points: 8,760 hourly COP samples throughout year
Diagonal line: Perfect prediction (measured = predicted)
Color: Time of year (summer → orange, winter → blue)

Metrics:
- MAPE: |(measured - predicted) / measured| average
- Bias: mean(measured - predicted) [systematic over/under-prediction?]
- R²: correlation coefficient [do temps explain COP well?]
- Outlier count: Points >±10% from diagonal [sensor errors? model gaps?]
```

**Expected plot characteristics**:
- ✅ Points densely clustered around diagonal: Model is good (MAPE < 5%)
- ⚠️ Points scattered but balanced (equal above/below): Unbiased but uncertain (MAPE 5–10%)
- ❌ Systematic bias (all points above/below diagonal): Model has systematic error (requires η_rel adjustment)
- ❌ Cone shape (scatter increases with COP): Model accuracy depends on operating point

**Deliverable**: `validation/hp_cop_validation_scatter.png` + statistics

---

### 4.3 Network Loss Validation

**Calculate network losses two ways**:

**Method 1: Energy balance** (L3 model approach)
$$Q_{\text{loss}} = \sum_t Q_{\text{supply}}[t] - \sum_t (Q_{\text{demand}}[t] + Q_{\text{stored}}[t])$$

**Method 2: Temperature drop** (measured pipe-by-pipe)
$$Q_{\text{loss}} = \sum_{\text{pipes}} U \times L \times (T_{\text{supply}} - T_{\text{return}})$$

**Compare**:
```
| Method | Total Loss (GWh/yr) | Uncertainty |
|---|---|---|
| Energy balance | 26.5 | ±1.0 (measurement error) |
| Temp measure | 26.1 | ±2.0 (sensor errors, insulation variation) |
| L3 model (U=0.15) | 26.8 | ±0.5 (deterministic) |
| Difference | -1.1% | Excellent agreement |
```

**Validation pass criteria**:
- All three methods agree within ±5%: ✅ Model is validated
- Energy vs. temp differ by >10%: ⚠️ Check for unmeasured losses (unknown demand sinks)

---

## Part 5: Design of Validation Publication

### Option A: Standalone Journal Paper (Recommended for Your Case)

**Title**: "Operational Validation of Joint Investment-Operation MILP Optimization for Industrial Heat Networks: A 2-Year Case Study"

**Structure**:
```
1. Introduction (700 words)
   - Recap L3 framework from original paper
   - Motivation for operational validation
   - Research questions: Does L3 generalize to real grids?

2. Methodology (1,500 words)
   - Your grid description (anonymized if needed)
   - Data collection protocol
   - Calibration procedure for asset curves
   - Comparison metrics (MAPE, energy balance, cost)

3. Results (2,000 words)
   - Year 1 hindcast accuracy (MAPE, residual analysis)
   - Year 2 model refinement (parameter updates)
   - Year 3 full operational validation (vs actual dispatch)
   - Asset-specific curves (BHKW, HP, P2H, storage)
   - Network loss calibration

4. Discussion (1,500 words)
   - Error sources: measurement uncertainty, model approximations
   - Practical implications: Can utilities trust L3 recommendations?
   - Edge cases: Failure modes, model limitations revealed
   - Extensions: Sub-hourly validation needed? Storage stratification?

5. Conclusion (700 words)
   - Validates E4 gap (operational validation)
   - Confirms ±5% prediction accuracy
   - Recommendations for future L3 deployments

Appendix:
   - Detailed sensor specifications
   - Calibration procedures (PWL approximation, COP curve fitting)
   - Full results tables (MAPE by month, quarterly trends)
   - Data availability statement (your grid anonymized, data archived)
```

**Target journal**: Energy Conversion and Management (same as original paper, validates methodology)  
**Expected timeline**: 6–9 months (after 3 years of data collection)  
**Word count**: 8,000–10,000 words

---

### Option B: Extension to Current Paper (Risky, Not Recommended)

**Current paper Section 7: Conclusion**
```markdown
### 7.3 Operational Validation (New Subsection)

We validated L3 predictions against 36 months of real operational data 
from a 400 MW heating network...

[2,000-word summary of results]

#### Key Findings:
- COP prediction MAPE: ±4.2% (vs. measured hourly COP)
- Network loss model: U = 0.146 W/(m·K) (vs. assumed 0.15)
- Dispatch feasibility: All L3-recommended dispatch achievable
- Cost accuracy: L3 predictions within ±8% of actual 2024 cost

#### Implications:
- CALION L3 is operationally validated for real deployments
- Recommended for utilities seeking ±10% planning accuracy
```

**Pros**: Strengthens current paper (addresses E4 gap directly)  
**Cons**: Delays current paper submission by 3 years (unacceptable for journal pressure)

**Verdict**: NOT RECOMMENDED — Proceed with Option A instead.

---

### Option C: Conference Presentation & Practitioner Venue

**Format**: 
- 20-minute talk at heat network conference (e.g., DHC+ Technology Platform, European Heating Association)
- Emphasis: "L3 MILP Works in Practice—A 2-Year Real-World Case Study"
- Audience: Utilities, DNO operators, consultants (more interested in business case than academic novelty)

**Publication venue**: Trade journal (e.g., DHC+, Energy Studies Review, Euroheat & Power Magazine)  
**Timeline**: 2–3 years after data collection  
**Format**: 3,000-word case study with conclusions

---

## Part 6: Implementation Roadmap (For Your Team)

### Phase 0: Pre-Validation (Next 1–2 Months)

**Tasks** (before year 1 starts):

- [ ] **Inventory your data**
  - What sensors do you have? (temperature, power, flow, pressure)
  - What's logged hourly? 15-minute? Sub-minute?
  - How much historical data is already available? (≥1 year required)

- [ ] **Set up data pipeline**
  - Extract BHKW performance curve from logs (part-load efficiency)
  - Extract HP COP vs. temperature matrix
  - Extract P2H efficiency curve
  - Create standardized CSV files

- [ ] **Identify measurement gaps**
  - Do you have node-level temperatures for network loss calibration?
  - Do you have tank stratification sensors?
  - Can you derive mass flow from ΔP + pump curves?
  - (Add sensors if critical data is missing)

- [ ] **Prepare CALION input**
  - Extract your grid topology (nodes, pipes, demand zones)
  - Create YAML config file with measured parameters
  - Test L3 optimization run on 1 month of historical data

**Deliverable**: `validation/data_inventory.md` (lists available/missing data)

---

### Phase 1: Year 1 Calibration (Months 1–12)

**Primary goal**: Extract asset performance curves, validate network loss model

**Monthly milestones**:
- Month 1–3: Data extraction + BHKW/HP/P2H curve generation
- Month 3–6: Network loss calibration (identify longest pipe losses)
- Month 6–9: Storage model validation (if applicable)
- Month 9–12: L3 hindcast vs. first year's actuals

**Deliverables**:
- `assets/bhkw_performance_curve.csv`
- `assets/hp_cop_matrix.csv`
- `assets/p2h_efficiency_curve.csv`
- `validation/network_loss_report.md` (measured U-value vs. L3 assumption)
- `validation/year1_hindcast.md` (MAPE ≈ 15–25% expected)

**Success metric**: ✅ MAPE < 25% (model predicts within 1/4 of actual operations)

---

### Phase 2: Year 2 Advisory Deployment (Months 13–24)

**Primary goal**: Operator feedback, soft rollout, data quality improvement

**Activities**:
- Deploy L3 as "advisory only" to operators (read-only feedback, no forced dispatch changes)
- Collect feedback: Do recommendations make sense? Are any clearly sub-optimal?
- Log all operator deviations: "Recommended HP dispatch 50 MW, but ran at 30 MW" → Why?
- Improve sensor network: Add missing instrumentation

**Monthly milestones**:
- Months 13–15: Advisory rollout, operator training
- Months 16–20: Continuous ops data collection, feedback logging
- Months 21–24: Model refinement based on Year 1 hindcast results

**Deliverables**:
- `validation/operator_feedback_log.csv` (deviations, reasons, counts)
- `validation/year2_model_refinement.md` (updated asset curves, loss params, etc.)
- Updated L3 config YAML (with refined parameters)

**Success metric**: ✅ MAPE improves from 20% → 12% (model learning)

---

### Phase 3: Year 3 Full Validation (Months 25–36)

**Primary goal**: Comprehensive validation across entire operational year

**Activities**:
- Run L3 on Year 3 scenarios (both past-year hindcast + real-time dispatch)
- Compare cumulative cost: L3 recommendations vs. actual ops
- Quantify energy savings: How much money did L3 identify?
- Perform sensitivity: What if operators had followed L3 100%? (counterfactual analysis)

**Monthly milestones**:
- Months 25–27: Year 3 hindcast execution
- Months 28–30: Performance curve analysis (BHKW, HP, storage, network)
- Months 31–33: Root cause analysis of residual errors
- Months 34–36: Publication preparation, manuscript writing

**Deliverables**:
- `validation/year3_full_validation_report.md` (comprehensive MAPE, cost analysis)
- `validation/counterfactual_analysis.md` ("If we'd followed L3, savings would be €X")
- `validation/model_limitations_discovered.md` (unexpected challenges, recommendations for L4/L5)
- Draft journal paper (3,000–5,000 words)

**Success metric**: ✅ MAPE < ±5%, cost accuracy within ±10% (model validated for deployment)

---

## Part 7: Key Validation Metrics (Summary Table)

| Metric | Target | Meaning | How to Measure |
|--------|--------|---------|---|
| **COP MAPE** | < ±4% | Heat pump prediction accuracy | Hourly measured vs. L3 LMTD formula |
| **Dispatch MAPE** | < ±20% | Operational similarity | Actual vs. L3-recommended component dispatch |
| **Energy balance closure** | ±2% | No unexplained energy loss | ∑(supply) = ∑(demand + loss + storage) |
| **Network loss error** | ±10% | Loss model accuracy | Measured U-value vs. L3 assumed U=0.15 |
| **Storage loss MAPE** | < ±15% | Storage model prediction | Measured tank cooling vs. L3 PWL model |
| **Cost prediction error** | ±8% | Overall economic feasibility | L3 predicted cost vs. actual 2024 cost |
| **Forecast vs. reality** | < ±25% Month 1, < ±5% Month 36 | Progressive model improvement | MAPE decay from Year 1 → Year 3 |

---

## Part 8: Connection to Paper Strategy

### Current Paper Status

**What paper currently says about operational validation** (E4 gap):
- Section 6.4 Limitations: "Real operational validation requires 2+ year deployment (future work)"
- Section 7 Future Work: "Recommended: Deploy on 2–3 real systems; compare CALION-optimized capacity sizing vs. historical/design performance"

### Your L5 Validation Study

**How it addresses E4**:
- ✅ **Moves E4 from "future" → "current"**: You're doing the 2-year study NOW
- ✅ **Provides empirical evidence**: COP tables validated, loss models verified
- ✅ **Strengthens original paper**: "E4 gap has been addressed via separate validation study"
- ✅ **Positions for follow-up publication**: Validation results as Journal Paper (Option A)

**Does NOT require paper changes**:
- Current Sections 1–7 remain UNCHANGED
- No need to wait for validation data before publishing original paper
- Original paper remains scientifically sound (L3 framework + case study valid)
- Validation paper stands independently: "Building on CALION framework from [Reference], we now validate..."

### Publication Sequence Recommendation

```
TIMELINE:

March 2026 (NOW)
└─ Submit current paper to Energy Conversion and Management
   ├─ 7 sections + appendix
   ├─ L1–L4 framework, L3 detailed (CALION), E4 gap acknowledged
   └─ Expected decision: 5–7 months

Aug 2026
└─ If accept/minor revisions → Publish v1 (your current work)

Sept 2026–Aug 2029
└─ Conduct your L5 operational validation study
   ├─ Months 1–12: Data extraction, hindcast
   ├─ Months 13–24: Advisory deployment, feedback
   ├─ Months 25–36: Full validation, manuscript preparation

Sept 2029
└─ Submit follow-up validation paper to Energy Conversion and Management
   ├─ Cites original paper: "Extending the L3 framework validation from [Ref v1]"
   ├─ 8,000–10,000 words, addresses E4 gap explicitly
   ├─ Expected decision: 5–7 months

March 2030
└─ Validation paper accepted & published
   ├─ Original paper (2026) now + extended by validation (2029)
   ├─ Rare achievement: Same first author, same journal, 3-year research arc
   └─ Demonstrates commitment to rigorous validation

KEY BENEFIT: Your current paper is COMPLETE and PUBLISHABLE NOW.
Validation study is BONUS, separate publication (not requirement).
```

---

## Part 9: Implementation Checklist

### Before Starting Validation Study

- [ ] **Confirm data availability**
  - Do you have ≥1 year historical operational logs? (hourly minimum)
  - Can you extract BHKW/HP/P2H performance curves?
  - Do you have node temperatures or can you derive them from ΔP+flow?

- [ ] **Identify missing sensors**
  - List critical gaps (e.g., needed for network loss calibration)
  - Budget for installation if needed

- [ ] **Prepare CALION infrastructure**
  - Extract grid topology (nodes, pipes, demand zones)
  - Create L3 config YAML with measured parameters
  - Test optimization run on 1 month historical data

- [ ] **Set project timeline**
  - Start Month 1: Data extraction (months 1–3)
  - Months 4–6: Calibration + hindcast
  - Months 7–12: Model refinement
  - Decision point: Continue to Phase 2 (advisory deployment)?

- [ ] **Plan dataset governance**
  - Define what data is sensitive (anonymize if needed)
  - Plan for future publication: Can you share data? (Zenodo, Figshare)
  - Document data processing pipeline (reproducibility)

- [ ] **Coordinate with plant operations**
  - Inform operators of monitoring plan
  - Establish data access procedures
  - Plan for advisory deployment (Phase 2)

### Year 1 Monthly Tasks

**Months 1–3: Data Extraction**
- [ ] Export BHKW hourly efficiency logs (if available)
- [ ] Extract HP COP vs. (T_source, T_sink) from sensor data
- [ ] Extract P2H efficiency curve
- [ ] Check data quality: Any missing timesteps, sensor errors?

**Months 4–6: Loss Model Calibration**
- [ ] Identify 3 longest pipes
- [ ] Calculate measured U-values from temperature drops
- [ ] Compare to L3 assumption (U=0.15)
- [ ] Decide: Update L3 config if deviation >20%?

**Months 7–9: Storage/System Validation**
- [ ] If applicable: Measure tank stratification losses
- [ ] Calculate network losses total (energy balance method)
- [ ] Compare hindcast L3 vs. actual 2024 costs

**Months 10–12: Hindcast Report**
- [ ] Run L3 on full 2024 retroactively
- [ ] Calculate MAPE (dispatch, COP, costs)
- [ ] Document: Is MAPE < 25%? (if yes, validation on track)

---

## Summary & Recommendation

### What You Can Do NOW (Without Waiting for 3-Year Validation)

1. **Keep current paper as-is** ✅ (submit to journal in April 2026)
2. **Plan L5 validation as future work** ✅ (separate paper, 2029 publication)
3. **Start data extraction immediately** ✅ (Phase 0: 1–2 months preparation)

### Why This Approach Works

| Aspect | Benefit |
|--------|---------|
| **Paper publication** | NOT delayed by validation study (publish v1 now) |
| **Validation rigor** | Full 3-year dataset (far exceeds 1-year paper baseline) |
| **Scientific credibility** | Operational validation adds enormous weight (rare in literature) |
| **Publication strategy** | Two complementary papers (framework + validation) stronger than one |
| **Practitioner adoption** | Utilities see proof it works in the wild (validation convinces them) |

### Next Steps (This Week)

1. **Inventory your data** — What sensors/logs do you have? (1 hour)
2. **Sketch asset extraction** — Can you get BHKW/HP curves from your logs? (2 hours)
3. **Identify sensor gaps** — What's missing for network loss calibration? (1 hour)
4. **Create Phase 0 task list** — Outline 1–2 months of prep work (2 hours)

**Decision point** (by early April 2026):
- **Option A**: Start Phase 0 prep now, plan 3-year validation in parallel with journal review
- **Option B**: Focus on journal submission first, decide on validation in 6 months (after first paper acceptance feedback)

---

## Questions for You to Answer

To refine this strategy for your specific grid:

1. **Data availability**:
   - How many years of operational logs do you have?
   - What's the temporal resolution? (hourly, 15-min, sub-minute?)
   - Are BHKW/HP power outputs logged separately?

2. **Sensor network**:
   - Do you have node-level temperature measurements (supply/return)?
   - Can you calculate mass flow (from ΔP + pump curves, or direct measurement)?
   - Do you have thermal storage tank sensors (if applicable)?

3. **Asset specifications**:
   - Can you extract BHKW part-load efficiency curves?
   - Do you have HP manufacturer COP tables, or only field data?
   - What's your P2H turndown ratio (min operating point)?

4. **Timeline constraints**:
   - Can you start data extraction immediately (next 2 months)?
   - How much staff time can you dedicate to this project?
   - Do you need validation results by a specific deadline?

5. **Publication goals**:
   - Is a journal paper (Option A) of interest to you?
   - Or do you prefer internal case study/report (Option C)?
   - Any regulatory/political pressure for validation studies?

---

## Conclusion

**You have a unique opportunity**: Real grid + real data + L3 framework = Operational validation possible.

This document outlines how to transform that into:
1. ✅ Strengthened confidence in L3 models
2. ✅ Publishable validation study (Option A: journal paper)
3. ✅ Practitioner case study (Option C: conference/trade journal)
4. ✅ Operational guidelines for future L3 deployments

**Current paper is NOT affected** — Remain on track for April 2026 submission. Validation study is parallel effort, 3-year horizon, second publication 2029.

**Recommendation**: Start Phase 0 prep this month, make full commitment decision after first paper feedback (Aug 2026).

---

**Document Status**: Draft Strategic Proposal (No Paper Changes)  
**Next Review**: After you answer the 5 questions above  
**Contact**: Ready to discuss implementation details
