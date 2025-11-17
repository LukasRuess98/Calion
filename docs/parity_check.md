# Parity review vs. original Stadtbach script

This checklist captures the remaining gaps between the current EnerGIS framework implementation and the behaviour of the original monolithic Pyomo script. A compact Überblick über Variablen, Constraints und Objective-Teile findet sich in [`docs/methodology.md`](./methodology.md).

## Objective terms and cost toggles
- **CapEx/installation switches available in RH**: Investment-related terms now honour `costs.include_investment_in_rh` (default: off when a PF design is fixed), `costs.amortise_investment_once_in_rh` and the granular `include_*` flags per cost component. Rolling-horizon windows disable CapEx/activation/tie-breaker/installation after the first window when amortisation is enabled, and the Pyomo objective omits terms when the flags are false. 【F:energis/run/rolling_horizon.py†L109-L182】【F:energis/models/system_builder.py†L205-L243】【F:energis/models/system_builder.py†L300-L337】【F:energis/models/system_builder.py†L470-L515】
- **Rolling-horizon cost aggregation clarified**: `_accumulate_costs` scales objective terms by the committed window fraction, skips double-counting of investment entries when amortised once, and recomputes the aggregated objective to keep PF and RH totals comparable despite overlaps. Remaining open point: aggregation still sums non-objective summary metrics across windows without overlap weighting. 【F:energis/run/rolling_horizon.py†L414-L479】

## Storage behaviour
- **Configurable terminal state**: `storage.terminal.state` (or legacy `terminal_state`) accepts `free`, `cyclic`, or `target`. Defaults honour the horizon setting: `free` when `scenario.horizon.enforce` is disabled, otherwise `cyclic` with the initial SOC as the target; `target` uses `storage.terminal.target_mwh`/`target` (falling back to the initial SOC) and supports `policy` values `equal`/`geq`. Invalid states or policies are rejected during config load. 【F:energis/models/system_builder.py†L370-L416】
- **Optional power/energy coupling**: `storage.power_energy_coupling` (or catalog default) enforces `cap_power <= factor * cap_energy` whenever provided, keeping the legacy uncoupled behaviour when omitted and validating that the factor is positive. 【F:energis/models/system_builder.py†L418-L432】【F:energis/models/blocks/storage.py†L152-L169】

## Grid modelling
- **Grid flow caps implemented**: `P_buy` and `P_sell` are limited by `max_import_mw` / `max_export_mw` (falling back to `M_GRID` when unset) alongside the buy/sell gate. This mirrors the original 300 MW cap when configured accordingly. 【F:energis/models/system_builder.py†L214-L237】

## Recommendations
1. Add cost switches for CapEx/installation (and tie-breaker suppression) that mirror the original `include_capex_in_rh` and `include_install_in_rh` flags, and omit these terms during RH aggregation.
2. When running RH, amortise investments once (PF step or a single annualised term) instead of per window, or reuse PF design data to avoid double counting.
3. Default the storage terminal policy to `free` when enforcement is disabled or no target is given, matching the monolithic script’s flexibility.
4. Introduce an optional `storage_power_rate` that ties charging/ discharging bounds to installed energy capacity, while keeping the current uncoupled behaviour available via configuration.
5. Add configurable grid flow bounds (e.g., `P_FLOW_CAP`) so buy/sell capacities match the original 300 MW limits when desired.
