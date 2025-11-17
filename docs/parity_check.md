# Parity review vs. original Stadtbach script

This checklist captures the remaining gaps between the current EnerGIS framework implementation and the behaviour of the original monolithic Pyomo script. A compact Überblick über Variablen, Constraints und Objective-Teile findet sich in [`docs/methodology.md`](./methodology.md).

## Objective terms and cost toggles
- **CapEx/installation switches missing in RH**: The objective always adds capacity, activation, tie-breaker and installation terms for heat pumps and storage, even when running rolling-horizon windows. There are no `include_capex_in_rh` / `include_install_in_rh` style flags, so RH runs still charge investment components that should only appear in the PF step. The tie-breaker is also always active, instead of being suppressed when CapEx is present. 【F:energis/models/system_builder.py†L590-L613】
- **Rolling-horizon double counting**: Each RH window rebuilds `_solve_scenario` with the full objective (including CapEx) and `_accumulate_costs` sums the per-window costs, so one-time investment terms are added once per window instead of once per design. 【F:energis/run/rolling_horizon.py†L419-L460】【F:energis/models/system_builder.py†L590-L613】

## Storage behaviour
- **Terminal policy defaults to equality**: When `scenario.horizon.enforce` is false or no policy is provided, the terminal policy is still forced to `equal` with a target of the initial SOC. The original script allowed a free terminal unless a target was specified. 【F:energis/models/system_builder.py†L389-L415】
- **Power/energy coupling absent**: Storage charging/ discharging power is independent of energy capacity (no `storage_power_rate` equivalent), so power can exceed a reasonable fraction of installed energy, unlike the original rate-bound formulation. 【F:energis/models/blocks/storage.py†L88-L166】

## Grid modelling
- **No explicit grid flow cap**: `P_buy` and `P_sell` are unbounded continuous variables gated only by a large `M_GRID` (default 10,000 MW). The original model limited each to 300 MW via variable bounds plus the buy/sell mode binary. 【F:energis/models/system_builder.py†L240-L243】【F:energis/models/system_builder.py†L221-L230】

## Recommendations
1. Add cost switches for CapEx/installation (and tie-breaker suppression) that mirror the original `include_capex_in_rh` and `include_install_in_rh` flags, and omit these terms during RH aggregation.
2. When running RH, amortise investments once (PF step or a single annualised term) instead of per window, or reuse PF design data to avoid double counting.
3. Default the storage terminal policy to `free` when enforcement is disabled or no target is given, matching the monolithic script’s flexibility.
4. Introduce an optional `storage_power_rate` that ties charging/ discharging bounds to installed energy capacity, while keeping the current uncoupled behaviour available via configuration.
5. Add configurable grid flow bounds (e.g., `P_FLOW_CAP`) so buy/sell capacities match the original 300 MW limits when desired.
