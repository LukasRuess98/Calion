# Parity review vs. original Stadtbach script

This checklist captures the remaining gaps between the current EnerGIS framework implementation and the behaviour of the original monolithic Pyomo script.

## Cost toggles and rolling-horizon alignment
- **CapEx/installation switches missing**: The objective always adds capacity, activation, tie-breaker and installation terms for heat pumps and storage, regardless of whether a rolling-horizon (RH) run is intended to be opex-only. There are no `include_capex_in_rh`/`include_install_in_rh` flags like in the original script, so RH windows still charge full investment components. 【F:energis/models/system_builder.py†L589-L613】
- **Double counting in RH windows**: Each RH window builds a full model via `_solve_scenario` with the same objective (including CapEx) and aggregates the window costs without adjustment. The original workflow only charged investments in the PF step. 【F:energis/run/rolling_horizon.py†L395-L460】【F:energis/models/system_builder.py†L589-L613】

## Storage terminal policy
- The terminal policy defaults to `equal` even when `scenario.horizon.enforce` is false, forcing the end SOC to match the start SOC unless the user explicitly sets `terminal.policy: free`. The original script allowed truly free terminals when the policy was “free” or enforcement was disabled. 【F:energis/models/system_builder.py†L389-L407】

## Storage sizing behaviour
- Storage power is unconstrained relative to energy capacity (no `storage_power_rate` equivalent). The original script bound charging/ discharging power to a fraction of energy capacity; here `cap_power` and `cap_energy` are independent, which can produce different designs. 【F:energis/models/system_builder.py†L420-L494】

## Miscellaneous
- The tech catalog contained a typo (`ture`) for default investment enablement; this was corrected to `true` to keep defaults consistent. 【F:configs/tech_catalog.yaml†L15-L40】

## Recommendations
1. Introduce cost toggles for CapEx/installation analogous to `include_capex_in_rh` and `include_install_in_rh`, and suppress these terms when RH is meant to be opex-only.
2. When running RH, strip or amortise CapEx terms so they are not accumulated per window; consider reusing PF design data or applying one-time annualised costs.
3. Respect `scenario.horizon.enforce: false` by defaulting the terminal policy to `free` instead of `equal`, unless a terminal target is explicitly set.
4. Add an optional `storage_power_rate` parameter to link `cap_power` to `cap_energy` when desired, keeping current behaviour as the unrestricted fallback.
