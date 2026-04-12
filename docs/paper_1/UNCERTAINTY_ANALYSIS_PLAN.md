# Uncertainty Analysis Plan for the Paper

## Purpose

This note translates the current framework capabilities into a publication-ready uncertainty strategy for the paper. The goal is to support a strong deterministic planning paper for *Energy Conversion and Management* without over-claiming stochastic rigor that is not yet implemented in the model.

The current codebase already supports:

- One-at-a-time sensitivity analysis via `calion.analysis.sensitivity`
- Publication-oriented batch execution via `calion.analysis.sensitivity_runner`
- CO2 temporal-resolution analysis via `calion.analysis.co2_resolution_analysis`

The current codebase does **not** yet support:

- Two-stage stochastic programming
- Multi-stage stochastic programming
- Non-anticipativity constraints
- Robust optimization with uncertainty sets
- CVaR or other risk-aversion objectives
- Scenario reduction embedded in the optimization model

Accordingly, the recommended strategy is:

1. present the optimization model as deterministic,
2. quantify robustness through structured sensitivity and scenario analysis,
3. explicitly define future work toward stochastic or robust planning.

## Recommendation

For the present paper, the minimum credible uncertainty package should contain four elements:

1. A one-at-a-time sensitivity study on major techno-economic assumptions.
2. A named scenario matrix capturing combined market and demand uncertainty.
3. A CO2 temporal-resolution analysis for electrified operation.
4. A short limitations subsection explaining why the current model is deterministic.

This is sufficient for a strong methodology/results paper if the main novelty is the framework, the multi-level representation, or the nodal planning formulation.

## Why This Is Needed

District-heating planning papers are usually exposed to uncertainty in:

- demand levels and demand timing,
- fuel and electricity prices,
- CO2 prices,
- technology performance,
- CAPEX assumptions,
- network losses and temperature assumptions,
- emissions-accounting resolution.

If these are not tested, reviewers can reasonably ask whether the selected design is only an artifact of one input year or one cost assumption. Sensitivity and scenario analysis are therefore not optional polish; they are part of the model-validation story.

## Uncertainty Taxonomy

### 1. Demand uncertainty

Main sources:

- annual demand level,
- cold vs. mild weather,
- intraday shape,
- spatial distribution of demand among zones.

Recommended treatment:

- scalar demand multipliers,
- one cold-year and one mild-year scenario if data are available,
- optional node-level perturbation for zonal cases.

Suggested ranges:

- annual heat demand: `-10% / base / +10%`
- peak demand timing or intensity: `-10% / base / +10%`

### 2. Market uncertainty

Main sources:

- electricity spot price,
- gas price,
- CO2 certificate price,
- demand charge / network tariffs.

Recommended treatment:

- one-at-a-time sensitivity,
- combined named scenarios.

Suggested ranges:

- electricity price: `-20% / base / +20%`
- gas price: `-20% / base / +20%`
- CO2 price: `-50% / base / +50%`
- demand charge: `-25% / base / +25%`

### 3. Techno-economic uncertainty

Main sources:

- heat-pump COP or Carnot factor,
- storage losses and efficiencies,
- heat-pump CAPEX,
- storage CAPEX,
- optional boiler efficiency.

Recommended treatment:

- one-at-a-time sensitivity,
- optimistic and pessimistic technology scenarios.

Suggested ranges:

- HP Carnot factor / effective COP driver: `-10% / base / +10%`
- storage loss rate: `0.5x / base / 1.5x`
- storage efficiency: `-3% / base / +3%`
- HP CAPEX: `-20% / base / +20%`
- storage CAPEX: `-20% / base / +20%`

### 4. Network and physical-model uncertainty

Main sources:

- pipe U-values / heat-loss coefficients,
- nominal supply temperature,
- nominal return temperature,
- network configuration assumptions.

Recommended treatment:

- sensitivity runs on heat-loss coefficients,
- temperature-parameter scenarios,
- discussion of model-structure uncertainty between L1, L2, and L3.

Suggested ranges:

- pipe U-value / heat-loss coefficient: `-20% / base / +20%`
- supply temperature: `base +/- 5 K`
- return temperature: `base +/- 5 K`

### 5. Accounting uncertainty

Main sources:

- temporal resolution of grid CO2 intensity,
- accounting convention for CHP emissions,
- cost aggregation choices.

Recommended treatment:

- run the existing CO2 resolution analysis,
- report deviation between annual, monthly, daily, and hourly factors.

## Recommended Study Design

### Stage A. Deterministic baseline

Run the main case study and report:

- total cost,
- cost breakdown,
- CO2 emissions,
- peak grid import,
- technology utilization,
- selected capacities.

### Stage B. One-at-a-time sensitivity

Run a tornado-style sensitivity study on:

- `fuels.gas.price_eur_mwh`
- electricity price series scaling
- `costs.co2_price_eur_per_t`
- `grid.demand_charge_eur_per_mw_y`
- HP performance parameter
- HP CAPEX
- storage CAPEX
- storage loss rate
- demand scaling

Core outputs:

- tornado diagram,
- ranked parameter sensitivity index,
- table of cost and CO2 deviations,
- short interpretation of the most critical assumptions.

### Stage C. Combined scenario matrix

Run a compact set of named scenarios:

- `baseline`
- `market_low`
- `market_high`
- `tech_optimistic`
- `tech_pessimistic`
- `cold_year`
- `warm_year`
- `electrification_favorable`
- `electrification_unfavorable`

Core outputs:

- scenario comparison table,
- ranking stability of the preferred design,
- variation band for total cost and CO2,
- explanation of which assumptions change dispatch only and which change structural conclusions.

### Stage D. CO2 resolution analysis

Run the baseline scenario through the CO2 resolution analysis and report:

- annual-average result,
- monthly-average result,
- daily-average result,
- hourly result,
- deviation relative to the finest available resolution.

This is particularly important for electrified systems with heat pumps because operational correlation between grid intensity and electricity consumption can materially change emissions.

## What Is Enough for This Paper

The following package is recommended as the target submission scope:

- Deterministic optimization model
- One-at-a-time sensitivity analysis
- Combined scenario analysis
- CO2 resolution analysis
- Limitations paragraph on missing stochastic optimization

This is likely enough unless the paper explicitly claims uncertainty-aware optimization as a novel contribution.

## When Full Stochastic Optimization Would Become Necessary

You should consider extending the model toward stochastic or robust optimization only if one or more of the following happens:

- the preferred design flips frequently across plausible scenarios,
- cost ranking between alternatives is unstable,
- reviewers focus strongly on long-term uncertainty treatment,
- the central research question becomes decision-making under uncertainty rather than deterministic framework design.

In that case, the next methods to consider are:

1. Two-stage stochastic programming
   First-stage: capacity/investment.
   Second-stage: operation under multiple scenarios.

2. Robust optimization
   Capacities chosen to remain feasible under bounded uncertainty sets.

3. Risk-aware stochastic optimization
   Add CVaR or downside-risk terms if very unfavorable cases matter.

## Paper Language You Can Use

Suggested wording:

> The optimization model is deterministic. Uncertainty is quantified through structured sensitivity analysis, combined scenario analysis, and temporal-resolution analysis of carbon-intensity factors. This approach was selected to preserve model transparency and tractability while still assessing the robustness of the principal techno-economic conclusions.

Suggested limitations statement:

> The present framework does not yet include stochastic or robust optimization with non-anticipativity constraints. Accordingly, uncertainty is treated ex post rather than endogenously within the optimization problem. Extending the model toward stochastic and risk-aware planning is a relevant avenue for future work.

## Immediate Next Steps

1. Run the baseline paper case and freeze the reference KPI set.
2. Execute the one-at-a-time sensitivity study for the selected paper configuration.
3. Execute the named scenario matrix with combined overrides.
4. Run CO2 resolution analysis for the baseline and one electrification-favorable case.
5. Add one table and one figure for sensitivity, one table for scenarios, and one short paragraph on uncertainty limitations.

## Repo Support Added

The paper workflow is complemented by:

- `scripts/paper/run_uncertainty_study.py`

This script is intended to:

- run the publication sensitivity study,
- run a paper-specific scenario matrix,
- export machine-readable summaries,
- optionally perform CO2 resolution analysis.
