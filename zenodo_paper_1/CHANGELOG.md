# CHANGELOG — corrected version (2026-07-27)

This is a **corrected re-release** of the Paper-1 data & code package. Four model
fixes were applied to `calion/`; the primary, sensitivity and synthetic runs were
re-solved from the paper's exact commit baseline (`c19d690`), which reproduces the
originally-submitted numbers to the cent *before* the fixes.

## What changed in the code (`calion/`)
1. **Pump-power attribution** (`models/network_manager.py::_link_pump_head`) — pump
   power now aggregates *every* pipe downstream of a producer (nearest-path BFS), not
   only the producer's immediately-outgoing pipe. The radial primary plant has one
   outgoing pipe, so 13/14 pipes' pumping work were previously dropped from the objective.
2. **`demand_fraction²`** (`models/blocks/thermal_node.py`) — node demand was multiplied
   by `demand_fraction` twice (once in `system_builder`, again here), so fractional-consumer
   configs served ~20 % of demand. Fixed to apply once. (Primary case unaffected — its
   consumers have `demand_fraction` removed; this restores the *synthetic* runs' fidelity.)
3. **Fine-PWL pump friction** (`models/blocks/pipe_pair.py`) — the pump-power PWL
   breakpoints were moved to `[0, 0.12, 0.35, 1.0]·ṁ_max` (low-flow-dense), cutting the
   cubic-secant over-estimation at part-load ~16×→~2× while keeping the pinned equality.
4. **Transfer-station Δp** (`models/network_manager.py::_link_pump_head`) — the pump now
   also pays the 0.6 bar differential pressure maintained at each consumer transfer
   station (`delta_p_min_consumer_bar`), the dominant real-DH pump term. Friction-only
   pumping was ~0.006 % of heat (1–2 orders of magnitude below real DH); this raises it
   to ~0.11 %.

Patches for (1)/(4), (2), (3) are the three files above; `git diff` vs `c19d690`.

## What changed in the numbers
| Quantity | Submitted | Corrected |
|---|---|---|
| Primary L1→L3 | 13.0 % | 13.03 % (reproduces) |
| Primary L2→L3 | 2.6 % | 2.54 % (reproduces) |
| **Primary L3→L3⁺** | +0.11 % (+255 EUR) | **+0.33 % (+735 EUR)** |
| Pump electricity | 2.4 MWh | 10.6 MWh (0.11 % of heat) |
| Sensitivity L3–L3⁺ | 0.0–0.2 % | −0.14 % … +0.54 % |
| Synth topology (L1cp→L3, n=36) | 20.0 % | +20.2 % (reproduces) |
| **Synth pressure-drop (L2→L3)** | +0.02 % | **+0.165 % (median)** |
| Synth delay (L3→L3⁺) | ~0 | +0.000 % (reproduces) |

**Conclusion unchanged:** topology dominates pumping ~40×; pressure/pump physics remain
marginal for planning. Only the specific pump/pressure-drop magnitudes move.

## Results in this package
- `results/L1..L3plus/` — corrected primary economics/dispatch/meta/pipes/nodes.
- `results/sensitivity_gap_stability.csv` — corrected L3–L3⁺ across 11 scenarios (NEW).
- `results/synth_gap_summary.csv` — corrected 36-config synth gaps.
- `results/figures/` — regenerated (see caveats below).
- `results/level_consistency.json` — corrected hierarchy check.
- `results/pump_linearization_error.json` + `L3NL_LINEARIZATION_ANALYSIS.md` — exact
  pump-friction L3⁺→L3NL linearisation error by decomposition (NEW; L3NL global re-solve
  is intractable with the corrected pump physics — see caveat).

## Caveats
- **`cost_pump_eur` reporting is not wired at `c19d690`** (a separate reporting bug we
  did not port — only the *objective* was corrected). The pump cost is real but appears
  inside `cost_energy_buy` / `cost_total`, and the "Pump" bar in `fig_cost_extended` reads 0.
- **L3NL (nonlinear reference) was NOT globally re-solved** with the new pump model — it is
  now intractable (the BFS pump-attribution fix multiplies the exact model's bilinear
  constraints ~14× to 58,774; a 24 h/window NonConvex solve found no incumbent). Instead the
  pump contribution to the L3⁺→L3NL linearisation error was quantified by **exact decomposition**
  on the L3⁺ optimal dispatch (`results/pump_linearization_error.json`,
  `L3NL_LINEARIZATION_ANALYSIS.md`): pipe-friction PWL-vs-cubic error = **+0.031 % (Jan) /
  +0.027 % (Feb)** of cost, and the 0.6 bar station Δp is linear and cancels in the gap. The
  submitted linearisation gaps (+0.35 %/+0.50 %, temperature-dominated) therefore stand,
  shifting by ≈ −0.03 % to ≈ +0.32 %/+0.47 %. `fig_pump_pwl_vs_quad` and `fig_synth_lin_error`
  still depend on a full L3NL solve and remain as submitted (see caveats).
- **`results/tables/*.tex`** are placeholder *templates* (they carry `\placeholder{…}`,
  not baked-in numbers). Running `tools/fill_paper.py` against the corrected `results/`
  fills them with the corrected values automatically — no manual table editing needed
  for reproduction. (The L3NL-dependent cells stay as placeholders until L3NL is re-solved.)
