# Forecast Methods Comparison Plan
**Framework:** EnerGIS Planning Framework for Heat
**Target:** Applied Energy Journal Submission
**Proposed Title:** "Comparing Planning Approaches for District Heat Systems under Uncertainty: From Perfect Foresight to Stochastic Optimization"
**Date:** 2025-11-18

---

## Executive Summary

This document outlines a systematic plan to extend the current PF/RH framework with additional forecast and uncertainty modeling approaches, creating a comprehensive comparison study suitable for publication in Applied Energy.

**Current State:**
- ✅ Perfect Forecast (PF) - full foresight baseline
- ✅ Rolling Horizon (RH) - limited foresight simulation
- ✅ PF→RH - strategic design + operational simulation

**Proposed Extensions:**
- 🔄 Model Predictive Control (MPC) with forecast updates
- 🔄 Scenario-Based Rolling Horizon (SB-RH)
- 🔄 Two-Stage Stochastic Programming (SP)
- 🔄 Robust Optimization (RO) - optional

**Key Research Question:**
*"How do different planning approaches perform when faced with realistic forecast uncertainties in district heat system design and operation?"*

---

## 1. Why This Is Excellent for Applied Energy

### 1.1 Novelty and Contribution

**Gap in Literature:**
- Most studies use EITHER perfect foresight OR simple rolling horizon
- Few systematically compare multiple approaches on the same system
- Limited analysis of forecast quality impact on design decisions
- No comprehensive benchmark for district heat planning under uncertainty

**Our Contribution:**
1. **Systematic comparison** of 6+ planning approaches on identical system
2. **Realistic forecast modeling** with actual weather/price prediction errors
3. **Design vs. operation trade-offs** - which approach for which decision?
4. **Open-source benchmark** - reproducible results with full code

**Why Applied Energy Will Love This:**
- High impact: Practical guidance for district heat planners
- Methodological rigor: Fair comparison with identical cost functions
- Reproducibility: Open-source framework with complete documentation
- Novelty: First comprehensive benchmark for heat system planning approaches

### 1.2 Target Journal Fit

**Applied Energy Focus Areas:**
- ✅ Optimization of energy systems
- ✅ District heating and cooling
- ✅ Renewable energy integration
- ✅ Uncertainty and risk management
- ✅ Decision support tools

**Expected Impact:**
- 50-100 citations within 3 years (district heat planning is active field)
- High practical relevance (tool is open-source and usable)
- Methodological reference for future studies

---

## 2. Proposed Forecast Methods

### 2.1 Overview Matrix

| Method | Foresight | Uncertainty | Design | Operation | Complexity | Realism |
|--------|-----------|-------------|--------|-----------|------------|---------|
| **PF** | Full year | None | Optimal | Optimal | Low | Theoretical |
| **RH** | 1 week | None | Suboptimal | Suboptimal | Low | Pessimistic |
| **PF→RH** | Full + 1 week | None | Optimal | Suboptimal | Low | Current practice |
| **MPC** | 1 week (updated) | Implicit | Suboptimal | Better | Medium | Realistic |
| **SB-RH** | 1 week + scenarios | Explicit | Suboptimal | Robust | Medium | Robust practice |
| **SP** | Full year + scenarios | Explicit | Robust | Robust | High | Theoretical ideal |
| **RO** | Full year + worst-case | Conservative | Robust | Conservative | High | Risk-averse |

### 2.2 Detailed Method Descriptions

#### Method 1: Perfect Forecast (PF) - BASELINE
**Status:** ✅ Implemented

**Description:**
- Single optimization over full horizon (8760 hours)
- Perfect knowledge of all time series
- Theoretical upper bound on performance

**Use Case:** Benchmark for "best possible" solution

---

#### Method 2: Rolling Horizon (RH) - BASELINE
**Status:** ✅ Implemented

**Description:**
- Fixed 168h forecast windows, 24h commitment
- Static forecast (no updates)
- Myopic decision-making

**Use Case:** Simple operational model, lower bound on performance

---

#### Method 3: PF→RH Workflow - BASELINE
**Status:** ✅ Implemented

**Description:**
- PF determines design (capacities)
- RH operates with fixed design
- Current industry practice

**Use Case:** Separates strategic from operational planning

---

#### Method 4: Model Predictive Control (MPC) - NEW ⭐⭐⭐
**Status:** 🔄 To be implemented

**Mathematical Formulation:**
```
For each day t = 1, 2, ..., 365:
    1. Get updated forecast: F_t = forecast(t, horizon=168h)
    2. Solve optimization over F_t
    3. Commit first 24 hours of solution
    4. Update state (storage SOC, etc.)
    5. GOTO step 1 with new forecast
```

**Implementation Details:**
```python
# New workflow step: "MPC"
def _mpc_step(context: WorkflowContext) -> None:
    """MPC with daily forecast updates."""

    forecast_generator = context.cfg.get('mpc', {}).get('forecast_generator')
    # Options: 'persistence', 'perfect', 'weather_model', 'historical_analog'

    results = []
    current_soc = initial_soc

    for day in range(num_days):
        # Update forecast using specified method
        forecast = generate_forecast(
            current_day=day,
            horizon_hours=168,
            method=forecast_generator,
            historical_data=context.table,
        )

        # Solve window with updated forecast
        window = optimize_window(
            forecast=forecast,
            initial_soc=current_soc,
            design=context.design if context.plan.fix_design else None
        )

        # Commit first 24h, update state
        results.append(window.committed_part)
        current_soc = window.final_soc

    context.mpc_result = aggregate_results(results)
```

**Forecast Models to Implement:**
1. **Persistence:** Tomorrow = Today (naive baseline)
2. **Perfect + Noise:** True data + Gaussian noise (synthetic benchmark)
3. **Historical Analog:** Use similar day from past (realistic)
4. **Weather Model:** Actual forecast error statistics from DWD/ECMWF

**Advantages:**
- ✅ Realistic: Uses forecast updates like real systems
- ✅ Medium complexity: Easy to implement
- ✅ Quantifies value of forecast accuracy

**Applied Energy Relevance:** HIGH - This is what real systems do!

---

#### Method 5: Scenario-Based Rolling Horizon (SB-RH) - NEW ⭐⭐⭐
**Status:** 🔄 To be implemented

**Mathematical Formulation:**
```
For each window w:
    Generate S scenarios: {s₁, s₂, ..., sₛ} with probabilities {p₁, p₂, ..., pₛ}

    Minimize: Σₛ pₛ · cost(s)

    Subject to:
        - Operational constraints ∀s
        - Non-anticipativity: First-stage decisions identical ∀s
        - Second-stage decisions adapted per scenario
```

**Implementation Details:**
```python
def _sb_rh_step(context: WorkflowContext) -> None:
    """Scenario-based rolling horizon."""

    scenario_config = context.cfg.get('sb_rh', {})
    num_scenarios = scenario_config.get('num_scenarios', 3)
    scenario_type = scenario_config.get('type', 'demand_uncertainty')

    # Scenario generation
    scenarios = generate_scenarios(
        base_forecast=context.table,
        num_scenarios=num_scenarios,
        uncertainty_type=scenario_type,
        # Options: 'demand', 'price', 'weather', 'combined'
    )

    results = []
    current_soc = initial_soc

    for window_start in rolling_windows:
        # Build scenario tree for this window
        scenario_tree = build_scenario_tree(
            scenarios=scenarios,
            window_start=window_start,
            horizon_hours=168,
        )

        # Solve multi-scenario optimization
        window_result = optimize_scenario_tree(
            scenario_tree=scenario_tree,
            initial_soc=current_soc,
            commit_hours=24,
            design=context.design if context.plan.fix_design else None,
        )

        results.append(window_result)
        current_soc = window_result.final_soc

    context.sb_rh_result = aggregate_results(results)
```

**Scenario Types:**
1. **Demand Uncertainty:** ±10%, ±20%, ±30% variations
2. **Price Uncertainty:** High/Medium/Low price scenarios
3. **Weather Uncertainty:** Cold/Normal/Warm weather
4. **Combined:** 3×3 = 9 scenario tree (demand × price)

**Advantages:**
- ✅ Explicit uncertainty modeling
- ✅ Robust to forecast errors
- ✅ Computationally tractable (3-9 scenarios per window)

**Applied Energy Relevance:** HIGH - Practical robustness

---

#### Method 6: Two-Stage Stochastic Programming (SP) - NEW ⭐⭐⭐
**Status:** 🔄 To be implemented

**Mathematical Formulation:**
```
Stage 1 (Here-and-Now): Design decisions x (capacities)
Stage 2 (Wait-and-See): Operational decisions y(s) for each scenario s

Minimize: c₁ᵀx + Σₛ pₛ · c₂ᵀy(s)

Subject to:
    A₁x ≥ b₁                    (design constraints)
    A₂(s)y(s) ≥ b₂(s) - B(s)x   (operational constraints ∀s)
    x ∈ {0,1}ⁿ × ℝ₊ᵐ           (MILP first stage)
    y(s) ∈ ℝ₊ᵏ                   (LP second stage)
```

**Implementation Details:**
```python
def _sp_step(context: WorkflowContext) -> None:
    """Two-stage stochastic programming."""

    sp_config = context.cfg.get('sp', {})
    num_scenarios = sp_config.get('num_scenarios', 5)
    scenario_method = sp_config.get('scenario_method', 'latin_hypercube')

    # Generate full-year scenarios
    scenarios = generate_full_year_scenarios(
        base_data=context.table,
        num_scenarios=num_scenarios,
        method=scenario_method,
        # Options: 'monte_carlo', 'latin_hypercube', 'moment_matching'
        correlations=sp_config.get('correlations', None),
    )

    # Build and solve two-stage model
    model = build_two_stage_model(
        scenarios=scenarios,
        probabilities=[1/num_scenarios] * num_scenarios,
        dt_h=context.dt_h,
        config=context.cfg,
    )

    result = solve_two_stage(model, context.solver_name)

    # Extract design and expected operational costs
    context.sp_result = result
    context.design = extract_design_from_sp(result)
```

**Scenario Generation Methods:**
1. **Monte Carlo:** Random sampling from distributions
2. **Latin Hypercube:** Stratified sampling (better coverage)
3. **Moment Matching:** Match first 2-4 statistical moments
4. **K-Means Clustering:** Reduce historical data to K representative scenarios

**Key Features:**
- Simultaneous design + operation optimization
- Accounts for correlation between uncertainties
- Produces robust designs

**Computational Challenge:**
- Large problem size: (8760 hours) × (5-10 scenarios) = 43,800-87,600 time steps
- Solution: Use temporal aggregation or scenario reduction

**Applied Energy Relevance:** HIGH - Academically rigorous

---

#### Method 7: Robust Optimization (RO) - OPTIONAL ⭐
**Status:** 🔄 Optional extension

**Mathematical Formulation:**
```
Minimize: c₁ᵀx

Subject to:
    A₁x ≥ b₁                               (nominal constraints)
    A₂(ξ)y ≥ b₂(ξ) - B(ξ)x   ∀ξ ∈ Ξ       (worst-case scenarios)

Where Ξ is uncertainty set (box, ellipsoid, or polyhedral)
```

**Use Case:** Risk-averse planning for critical infrastructure

**Applied Energy Relevance:** MEDIUM - Interesting for sensitivity

---

## 3. Fair Comparison Framework

### 3.1 Identical Cost Functions

**Critical for Fair Comparison:**
All methods must use IDENTICAL cost accounting:

```python
class UnifiedCostAccounting:
    """Ensures all methods use same cost calculation."""

    def __init__(self, config):
        self.capex_annualization_years = 20
        self.discount_rate = 0.05
        self.include_demand_charge = True
        self.include_co2 = True

    def calculate_total_cost(self, result):
        """Unified cost calculation for all methods."""
        return {
            'capex_annualized': self.annualize_capex(result.capacities),
            'opex_energy': sum(result.energy_costs),
            'opex_demand_charge': max(result.peak_demand) * self.demand_charge_rate,
            'opex_co2': sum(result.co2_emissions) * self.co2_price,
            'total': sum(above),
        }
```

**Key Principle:** Same physical system, same costs, only forecast method differs!

### 3.2 Performance Metrics

```python
@dataclass
class BenchmarkMetrics:
    """Standardized metrics for all methods."""

    # Economic
    total_cost_eur: float
    capex_eur: float
    opex_eur: float
    cost_vs_pf_percent: float  # Optimality gap vs. PF

    # Design
    hp_capacity_mw: Dict[str, float]
    storage_capacity_mwh: float
    storage_power_mw: float

    # Operation
    grid_import_mwh: float
    grid_export_mwh: float
    self_sufficiency_percent: float
    storage_cycles_per_year: float

    # Environmental
    co2_emissions_t: float
    renewable_share_percent: float

    # Computational
    solve_time_seconds: float
    mip_gap_percent: float
    num_variables: int
    num_constraints: int

    # Robustness (for stochastic methods)
    expected_cost_eur: float
    cost_std_dev_eur: float
    cost_95_percentile_eur: float
    worst_case_cost_eur: float
```

### 3.3 Test Cases

**Three Complexity Levels:**

1. **Simple:** Single site, 2 heat pumps, 1 storage, 1 week
   - Purpose: Method validation, quick iterations
   - Solve time: <1 minute per method

2. **Medium:** Single site, 4 heat pumps, 1 storage, full year
   - Purpose: Main comparison study
   - Solve time: 1-10 minutes per method

3. **Complex:** Multi-site network, 10 components, full year
   - Purpose: Scalability analysis
   - Solve time: 10-60 minutes per method

**Uncertainty Scenarios:**
- Low uncertainty: ±5% demand, ±10% price
- Medium uncertainty: ±10% demand, ±20% price
- High uncertainty: ±20% demand, ±30% price

### 3.4 Computational Environment

**Reproducibility Requirements:**
```yaml
# benchmark_config.yaml
solver:
  name: gurobi
  version: "11.0"
  threads: 4
  mip_gap: 0.01
  time_limit: 3600

hardware:
  cpu: "Intel Xeon Gold 6248R @ 3.0GHz"
  ram_gb: 64
  os: "Ubuntu 22.04"

random_seed: 42  # For stochastic methods
```

---

## 4. Implementation Roadmap

### Phase 1: Architecture Extension (Week 1)
**Goal:** Prepare framework for new methods

**Tasks:**
1. ✅ Create `WorkflowContext` extensions for new methods
2. ✅ Implement unified cost accounting module
3. ✅ Design benchmark metrics dataclass
4. ✅ Create scenario generation utilities
5. ✅ Add forecast error modeling framework

**Deliverable:** `energis/comparison/` module with base classes

**Files to Create:**
```
energis/comparison/
├── __init__.py
├── cost_accounting.py      # Unified cost calculation
├── metrics.py              # BenchmarkMetrics class
├── scenarios.py            # Scenario generation
├── forecasts.py            # Forecast models (persistence, etc.)
└── benchmark.py            # Main comparison runner
```

---

### Phase 2: MPC Implementation (Week 2)
**Goal:** Add MPC with forecast updates

**Tasks:**
1. Implement forecast generators (persistence, perfect+noise, analog)
2. Create `_mpc_step()` workflow handler
3. Add MPC configuration schema
4. Register workflow step: `register_workflow_step("MPC", _mpc_step)`
5. Create test scenarios
6. Validate against RH baseline

**Deliverable:** Working MPC method

**Config Example:**
```yaml
scenario:
  workflow: ["MPC"]
  mpc:
    forecast_method: "persistence"  # or "perfect_with_noise", "analog"
    forecast_horizon_hours: 168
    update_frequency_hours: 24
    noise_std_dev: 0.1  # for perfect_with_noise
```

**Tests:**
```python
def test_mpc_with_persistence_forecast():
    """MPC with naive persistence forecast."""
    assert mpc_cost > rh_cost  # Should be better than RH
    assert mpc_cost < pf_cost * 1.15  # Within 15% of PF

def test_mpc_with_perfect_forecast_equals_rh():
    """MPC with perfect forecast = RH."""
    assert abs(mpc_cost - rh_cost) < 0.01
```

---

### Phase 3: Scenario-Based RH (Week 3)
**Goal:** Add robust rolling horizon

**Tasks:**
1. Implement scenario tree builder
2. Create multi-scenario window optimizer
3. Add non-anticipativity constraints
4. Create `_sb_rh_step()` workflow handler
5. Test with 3, 5, 9 scenario trees
6. Compare to deterministic RH

**Deliverable:** Working SB-RH method

**Config Example:**
```yaml
scenario:
  workflow: ["SB_RH"]
  sb_rh:
    num_scenarios: 3
    scenario_type: "demand"  # or "price", "weather", "combined"
    demand_std_dev: 0.10     # ±10% uncertainty
    price_std_dev: 0.20      # ±20% uncertainty
```

**Key Challenge:** Ensure first-stage decisions are scenario-independent

---

### Phase 4: Stochastic Programming (Week 4)
**Goal:** Add two-stage SP

**Tasks:**
1. Implement scenario generation (Monte Carlo, LHS)
2. Build two-stage Pyomo model
3. Add scenario reduction techniques
4. Create `_sp_step()` workflow handler
5. Validate against PF baseline
6. Test scalability (5, 10, 20 scenarios)

**Deliverable:** Working SP method

**Config Example:**
```yaml
scenario:
  workflow: ["SP"]
  sp:
    num_scenarios: 10
    scenario_method: "latin_hypercube"
    uncertainties:
      - variable: "demand"
        distribution: "normal"
        std_dev: 0.10
      - variable: "price_elec"
        distribution: "lognormal"
        std_dev: 0.20
    correlations:
      demand_price: -0.3  # Negative correlation
```

**Computational Optimization:**
- Use Benders decomposition for large scenario counts
- Implement progressive hedging algorithm
- Add warm-start from deterministic solution

---

### Phase 5: Benchmark Suite (Week 5)
**Goal:** Create comprehensive comparison framework

**Tasks:**
1. Implement unified benchmark runner
2. Create automated comparison pipeline
3. Add statistical significance tests
4. Generate comparison tables and plots
5. Create sensitivity analysis framework

**Deliverable:** Complete benchmark system

**Benchmark Runner:**
```python
from energis.comparison import BenchmarkSuite

# Define methods to compare
methods = [
    ("PF", {"workflow": ["PF"]}),
    ("RH", {"workflow": ["RH"]}),
    ("PF→RH", {"workflow": ["PF", "RH"], "fix_design": True}),
    ("MPC", {"workflow": ["MPC"], "mpc": {"forecast_method": "persistence"}}),
    ("SB-RH", {"workflow": ["SB_RH"], "sb_rh": {"num_scenarios": 3}}),
    ("SP", {"workflow": ["SP"], "sp": {"num_scenarios": 10}}),
]

# Run benchmark
suite = BenchmarkSuite(
    base_config=load_config("configs/base.yaml"),
    test_cases=["simple", "medium", "complex"],
    uncertainty_levels=["low", "medium", "high"],
)

results = suite.run(methods, num_runs=5, random_seed=42)

# Generate comparison
comparison = suite.compare(
    results,
    metrics=["total_cost", "co2_emissions", "solve_time"],
    baseline="PF",
)

# Export for publication
comparison.to_latex("tables/method_comparison.tex")
comparison.to_csv("exports/benchmark_results.csv")
suite.plot_tornado_diagram("figures/sensitivity.pdf")
```

---

### Phase 6: Analysis & Metrics (Week 6)
**Goal:** Define evaluation framework

**Tasks:**
1. Implement cost decomposition analysis
2. Add design decision comparison tools
3. Create operational profile visualization
4. Implement statistical tests (ANOVA, post-hoc)
5. Add value-of-perfect-information calculation

**Key Metrics:**

**1. Economic Performance:**
- Total cost vs. PF (optimality gap)
- CAPEX vs. OPEX trade-off
- Cost breakdown by component

**2. Design Quality:**
- Capacity utilization
- Over/under-sizing analysis
- Design stability across scenarios

**3. Operational Performance:**
- Storage cycling behavior
- Grid interaction patterns
- Component dispatch profiles

**4. Robustness:**
- Cost variance across realizations
- Worst-case performance
- Constraint violation frequency

**5. Computational Efficiency:**
- Solve time scaling
- Memory usage
- Solver convergence statistics

---

### Phase 7: Publication Outputs (Week 7)
**Goal:** Generate all publication materials

**Tasks:**
1. Create publication-quality plots
2. Generate LaTeX tables
3. Write methods section text
4. Create supplementary materials
5. Prepare reproducibility package

**Key Figures:**

**Figure 1: Method Overview Diagram**
- Timeline visualization of each method
- Forecast horizon illustrations
- Decision points highlighted

**Figure 2: Cost Comparison (Box plots)**
- Total cost distribution for each method
- Grouped by uncertainty level
- Statistical significance markers

**Figure 3: Design Comparison (Bar charts)**
- Installed capacities by method
- Grouped by component type
- Error bars for stochastic methods

**Figure 4: Operational Profiles (Line plots)**
- Typical week operation for each method
- Heat pump dispatch, storage SOC, grid interaction
- Highlight differences in behavior

**Figure 5: Sensitivity Tornado Diagram**
- Parameter impact on cost
- Separate panels per method
- Identify critical parameters

**Figure 6: Computational Performance (Scatter)**
- Solve time vs. problem size
- Scaling analysis
- Method complexity comparison

**Tables:**

**Table 1: Method Characteristics**
- Foresight horizon
- Uncertainty handling
- Problem size (variables, constraints)
- Complexity class

**Table 2: Base Case Results**
- Total cost, CAPEX, OPEX
- Installed capacities
- Key operational metrics
- Computational time

**Table 3: Uncertainty Sensitivity**
- Cost variation by uncertainty level
- Robust optimization premium
- Value of perfect information

**Table 4: Statistical Comparison**
- Pairwise t-tests or ANOVA
- Effect sizes
- Confidence intervals

---

## 5. Publication Structure

### Proposed Paper Outline

**Title:** "Comparing Planning Approaches for District Heat Systems under Uncertainty: From Perfect Foresight to Stochastic Optimization"

**Abstract (250 words):**
District heating systems require coordinated investment and operational planning under significant uncertainty in demand, prices, and weather. This study systematically compares six planning approaches ranging from deterministic perfect foresight to two-stage stochastic programming using an open-source optimization framework. We evaluate methods on economic performance, design quality, operational robustness, and computational efficiency across multiple test cases with varying uncertainty levels. Results show that [key findings]. The analysis provides practical guidance for planners on selecting appropriate methods based on system complexity and data availability.

**1. Introduction**
- District heat decarbonization challenges
- Importance of planning under uncertainty
- Gap: Limited systematic comparison of methods
- Research questions and contributions

**2. Literature Review**
- Planning approaches in energy systems
- Uncertainty modeling techniques
- District heat optimization studies
- Position of this work

**3. Methods**
- 3.1 Optimization Framework
  - System description (heat pumps, storage, grid)
  - MILP formulation
  - Cost function

- 3.2 Planning Approaches
  - 3.2.1 Perfect Forecast (PF)
  - 3.2.2 Rolling Horizon (RH)
  - 3.2.3 PF→RH Workflow
  - 3.2.4 Model Predictive Control (MPC)
  - 3.2.5 Scenario-Based RH (SB-RH)
  - 3.2.6 Two-Stage Stochastic Programming (SP)

- 3.3 Uncertainty Modeling
  - Demand uncertainty
  - Price uncertainty
  - Weather uncertainty
  - Correlation structure

- 3.4 Comparison Framework
  - Test cases
  - Performance metrics
  - Statistical analysis

**4. Case Study**
- 4.1 System Description
  - Technology catalog
  - Time series data
  - Cost parameters

- 4.2 Computational Setup
  - Solver configuration
  - Hardware specs
  - Reproducibility

**5. Results**
- 5.1 Base Case Comparison
  - Economic performance
  - Design decisions
  - Operational profiles

- 5.2 Uncertainty Sensitivity
  - Low/medium/high uncertainty
  - Cost-uncertainty trade-offs
  - Robust optimization premium

- 5.3 Computational Performance
  - Solve time scaling
  - Method complexity
  - Practical tractability

- 5.4 Value of Information Analysis
  - Value of perfect information (VPI)
  - Value of stochastic solution (VSS)
  - Forecast accuracy requirements

**6. Discussion**
- 6.1 Method Selection Guide
  - When to use each approach
  - Computational budget considerations
  - Data availability requirements

- 6.2 Practical Implications
  - Guidance for district heat planners
  - Tool selection recommendations
  - Open-source availability

- 6.3 Limitations
  - Model simplifications
  - Uncertainty representation
  - Computational constraints

**7. Conclusions**
- Key findings summary
- Practical recommendations
- Future research directions

**Expected Length:** 10,000-12,000 words (Applied Energy standard)

---

## 6. Expected Key Findings (Hypotheses)

Based on energy systems literature, we expect:

**H1: Cost Performance**
- PF provides theoretical lower bound (baseline)
- RH: +5-15% cost vs. PF (myopic decisions)
- PF→RH: +2-8% cost vs. PF (optimal design, suboptimal operation)
- MPC: +3-10% cost vs. PF (better than RH with good forecasts)
- SB-RH: +4-12% cost vs. PF (pays robustness premium)
- SP: +1-5% cost vs. PF (best robust method)

**H2: Design Decisions**
- RH: Tends to under-size components (lacks foresight)
- PF→RH: Optimal sizing from PF
- SB-RH & SP: 5-20% over-sizing for robustness
- Higher uncertainty → larger capacity buffers

**H3: Operational Robustness**
- Deterministic methods (PF, RH): High cost variance
- Stochastic methods (SB-RH, SP): Lower variance, stable performance
- MPC: Intermediate robustness (adaptive but myopic)

**H4: Computational Efficiency**
- PF, RH: <1 minute (single optimization)
- MPC: 5-10 minutes (365 small optimizations)
- SB-RH: 10-30 minutes (scenario trees)
- SP: 30-120 minutes (large-scale MILP)

**H5: Value of Information**
- VPI (value of perfect info): 5-15% of total cost
- VSS (value of stochastic solution): 2-8% of total cost
- Forecast accuracy highly valuable for operational decisions
- Less critical for design decisions (unless severe uncertainty)

**H6: Uncertainty Sensitivity**
- Low uncertainty: All methods perform similarly
- High uncertainty: Stochastic methods show clear advantage
- Critical threshold around ±15% demand uncertainty

---

## 7. Success Criteria

### For Implementation:
- ✅ All 6 methods implemented and tested
- ✅ Unified benchmark framework working
- ✅ Results reproducible with open-source code
- ✅ Computational time acceptable (<2h per full comparison)

### For Publication:
- ✅ Clear performance ranking across test cases
- ✅ Statistical significance of differences
- ✅ Practical guidance for method selection
- ✅ Open-source tool available on GitHub
- ✅ Complete reproducibility package

### Quality Indicators:
- Code coverage >80%
- Documentation complete
- Example notebooks provided
- CI/CD pipeline passing
- Peer review by 2+ domain experts

---

## 8. Timeline and Resources

### Optimistic Timeline: 7 weeks
- Week 1: Architecture extension
- Week 2: MPC implementation
- Week 3: SB-RH implementation
- Week 4: SP implementation
- Week 5: Benchmark framework
- Week 6: Analysis and metrics
- Week 7: Publication outputs

### Realistic Timeline: 10-12 weeks
- Weeks 1-2: Architecture + MPC
- Weeks 3-4: SB-RH implementation + testing
- Weeks 5-7: SP implementation + debugging
- Weeks 8-9: Benchmark suite + analysis
- Weeks 10-12: Publication preparation

### Required Resources:
- **Computation:** Gurobi license (academic) or open-source solvers
- **Hardware:** 64GB RAM recommended for SP with many scenarios
- **Data:** Weather/price time series (available from open sources)
- **Literature:** Access to Applied Energy, Energy journal archives

---

## 9. Risk Mitigation

### Technical Risks:

**Risk 1: SP too slow for full-year optimization**
- Mitigation: Implement scenario reduction, temporal aggregation
- Fallback: Use representative periods (12 typical days)

**Risk 2: Scenario generation produces unrealistic cases**
- Mitigation: Validate against historical data
- Fallback: Use empirical bootstrap from historical data

**Risk 3: Stochastic methods don't show clear benefit**
- Mitigation: Test wider uncertainty ranges
- Interpretation: Document conditions where deterministic sufficient

### Publication Risks:

**Risk 4: Reviewers question novelty**
- Mitigation: Emphasize systematic comparison + open-source contribution
- Positioning: "First comprehensive benchmark for district heat planning"

**Risk 5: Computational requirements too high for practitioners**
- Mitigation: Provide "fast" configurations (fewer scenarios)
- Contribution: Show cost-complexity trade-offs

---

## 10. Deliverables Checklist

### Code Deliverables:
- [ ] `energis/comparison/` module
- [ ] MPC workflow step
- [ ] SB-RH workflow step
- [ ] SP workflow step
- [ ] Benchmark runner
- [ ] Example configurations for all methods
- [ ] Jupyter notebooks with examples
- [ ] Unit tests (>80% coverage)
- [ ] Integration tests for all methods
- [ ] CI/CD pipeline updated

### Documentation Deliverables:
- [ ] Method descriptions in docs/
- [ ] Configuration guide
- [ ] Benchmark usage guide
- [ ] API documentation
- [ ] Example case studies

### Publication Deliverables:
- [ ] Main manuscript (LaTeX)
- [ ] All figures (publication quality)
- [ ] All tables (LaTeX format)
- [ ] Supplementary material
- [ ] Code repository (Zenodo DOI)
- [ ] Data repository (if needed)
- [ ] Reproducibility instructions

---

## 11. Next Steps

### Immediate Actions:
1. Review and approve this plan
2. Set up development branch: `feature/forecast-comparison`
3. Create GitHub issues for each implementation phase
4. Schedule weekly progress meetings
5. Start Phase 1: Architecture extension

### Week 1 Kickoff Tasks:
1. Create `energis/comparison/` module structure
2. Implement `UnifiedCostAccounting` class
3. Design `BenchmarkMetrics` dataclass
4. Create scenario generation utilities
5. Write initial tests

---

## 12. References to Review

**Applied Energy - Method Comparison Papers:**
- Wakui et al. (2014): Comparison of stochastic programming and robust optimization
- Morales et al. (2014): Short-term forecasting and uncertainty
- Heymann et al. (2019): Model predictive control for energy systems
- Petkov & Gabrielli (2020): Power-to-hydrogen under uncertainty

**District Heating Optimization:**
- Lund et al. (2014): 4th generation district heating
- Sayegh et al. (2017): District heating systems review
- Blommaert et al. (2021): District energy optimization under uncertainty

**Methodology:**
- Birge & Louveaux (2011): Introduction to Stochastic Programming
- Shapiro et al. (2014): Lectures on stochastic programming
- Powell (2019): A unified framework for optimization under uncertainty

---

## Conclusion

This plan provides a systematic roadmap for extending the EnerGIS framework with advanced forecast and uncertainty modeling methods, creating a comprehensive comparison study suitable for publication in Applied Energy.

**Key Strengths:**
- Builds on existing, validated PF/RH implementation
- Adds 3-4 highly relevant methods (MPC, SB-RH, SP)
- Fair comparison with unified cost accounting
- Practical relevance for district heat planners
- Open-source contribution to research community
- Strong fit with Applied Energy scope and quality standards

**Expected Impact:**
- First comprehensive benchmark for district heat planning methods
- Practical guidance for method selection
- Open-source tool for research community
- 50-100 citations within 3 years
- High reproducibility and transparency

**Recommendation:** Proceed with implementation following 10-12 week timeline.

---

**Document Status:** Ready for review and approval
**Next Update:** After Phase 1 completion
**Contact:** energis-dev@example.org
