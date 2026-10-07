# CHANGELOG — Paper 2 Rework v3

Every config/bound/solver change with before→after, reason, source (AGENT_PROMPT rule #1).

## 2026-09-02

### Config cleanup
- `configs/paper_2/Stadtbach_topo.yaml` & `Memmingen_P2_base.yaml`, `emissions.ef_el_kg_per_mwh`:
  value **unchanged (400.0)** but comment rewritten to flag it **UNUSED**. Reason: verified the
  model reads the hourly `grid_co2_kg_MWh` (electricitymaps) column in both objective
  (`system_builder.py:292`→`emissions_calculator.py:113`) and reporting
  (`result_collector.py:836,861`); `ef_el_kg_per_mwh` is never read in code (`grep` empty). The
  bare `400` misled an external reviewer (real grid-series annual mean ≈278). Kept the key (no
  schema requires it, but removing risks a legacy loader) — annotation only. Source: WP0_BEFUND §5.

### Tooling (no model effect)
- `scripts/paper_2/value_saturation_probe.py`: added `--out-tag`, `--time-limit`, `--threads`,
  `--mip-gap` (parallel single-point runs); `--relax-commitment` (sets generator `min_load=0` →
  drops UC binaries → LP, via `_detect_commitment_gens`); disables the unused investable EK
  (`EK_ASSET`, 0% share in both seeds); default solver opts `MIPFocus=1, Heuristics=0.5`.
- `scripts/paper_2/value_probe_parallel.py`: new pooled subprocess driver (one solve per energy,
  per-tag CSVs merged at end); `--no-relax-commitment` for Memmingen (keeps full UC MILP).
- Rationale: Stadtbach full-mesh MILP needs ~2h/point; `concurrency=6, threads=10, TimeLimit=24h`
  converged all 6 SB points to **optimal** in ~2.3h wall. No model semantics changed.

### Phase 1 — geometry module (APPLIED, behind opt-in flag `CALION_ATMOSPHERIC_TES=1`)
- `calion/models/blocks/geometric_storage.py`: added `surface_factor(AR)` and
  `standing_loss_fraction_per_h()` helpers; constructor gains `loss_model`, `cost_model`,
  `eta_strat`, `u_value_w_m2k`, `t_amb_c`, `t_return_c`, `t_store_max_c`, `c0_eur`, `v0_m3`,
  `exponent_b` — ALL default to legacy (proportional loss, linear cost, η=1, no ceiling), so
  the block is bit-for-bit unchanged unless params are passed. Applied: η_strat scales
  `energy_coeff`; atmospheric ceiling clips ΔT (T_hot=t_return+ΔT > t_store_max → ΔT=ceiling−t_return);
  surface loss (fractional λ ∝ V^(−1/3)) for FIXED-V tanks (sizing study G), proportional
  fallback for endogenous V; degressive CAPEX built PER LADDER RUNG (linear, no PWL) as
  `capex_raw_expr`.
- `calion/models/component_assembler.py`: reads the new params from asset config, passes to the
  block; CAPEX now uses `fs["capex_raw_expr"]` (degressive or legacy `α·V+β·N` — identical when off).
- `scripts/paper_2/scenario_runner.py`: `_load_storage_geometry()` — OPT-IN via
  `CALION_ATMOSPHERIC_TES=1`; injects storage_geometry.yaml params + `t_return_c` into each TES
  asset (setdefault → asset config wins). Returns {} when disabled → existing campaign UNCHANGED.
- `configs/paper_2/storage_geometry.yaml`: new (params + sources).
- **Verified:** block unit checks pass (surface_factor min@AR=1, k(2)/k(1)=1.050; loss ∝ V^(−1/3);
  η_strat scaling; ceiling clip); opt-in flag gating (off→{}, on→atmospheric); legacy path
  bit-for-bit by construction. FULL-SOLVE legacy regression still TODO (deferred — MM refine using box).

### Code hardening (2026-09-02)
- `geometric_storage.py`: **defensive warning** when the multi-tank mechanism is silently
  disabled — `V_max_m3 ≈ unit_tank_m3` AND the ladder tops out at ~one vessel. This is the exact
  Stadtbach artefact (`V_max = unit_tank = 5000 m³`, ladder ending at 84.5 MWh) that made
  "TES = boundary solution" look physical when it was a config cap. Condition is narrow (cap ≈ unit
  AND ladder ≥ 0.8·unit) so it does NOT fire on a legitimate single large pit (V_max ≠ unit) or a
  small buffer whose ladder sits well below the cap. Verified: fires only on the legacy SB config.
- **Surface loss in the investment MILP — deliberately kept proportional (documented, not exact).**
  Investigated per-rung exactness: it needs either McCormick E·y linearisation (~hundreds of k
  vars — the blow-up we avoid, and it would hurt the already-tight SB MILP) or an additive
  constant-loss SoC recursion (which would change the fixed-V surface loss too and thus invalidate
  the running Study G). The effect is ~0.1 %/h and the investment MILP is NOT the sizing source —
  F2 comes from the fixed-V dispatch study where surface loss IS exact. So proportional fallback
  stays by design; the block logs this reasoning. Revisit only if the investment MILP's own sizing
  must be exact.

## Pending (Phase 1 — will be logged here as applied)
- `geometric_storage.py`: atmospheric envelope (replace pressurized `p_max_bar=10`/5000 m³ cap),
  ~95 °C store-temperature ceiling, surface-area standing loss `U·k(AR)·V^(2/3)·ΔT`, degressive
  CAPEX `C₀·(V/V₀)^b` on the discrete ladder, `η_strat`. Behind `storage.loss_model` /
  `storage.cost_model` flags with `legacy` reproducing current results bit-for-bit.
- New `configs/paper_2/storage_geometry.yaml` (U, AR, b, V₀, C₀, η_strat, T_store_max) with
  per-value source (DEA/IEA-DHC — see PHASE1_STORAGE_COST_PARAMS.md).
- HK-matched dispatch-optimized no-investment baselines (BC-*-HK0/1/2) — B3.
