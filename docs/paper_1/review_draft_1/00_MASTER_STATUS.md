# MASTER STATUS — Paper 1 revision (read this first)

Single source of truth for the APEN-D-26-15734 revision. Supersedes any conflicting
statement in the older pack files (00_CONTEXT…04, P0…P12); those are being updated to
match. Last updated 2026-08-10.

---

## 1. Scope — Shape A (LOCKED)

Paper 1 revision = **Memmingen (real) + synthetic factorial ONLY**.
**Stadtbach CUT** (deferred to Paper 2 — avoids NDA + salami-slicing) and **Case C
"Memmingen upgraded" CUT** (belongs in Paper 2). See `06_SCOPE_REEVALUATION.md`.
The central-vs-distributed **moderator** is carried by the synthetic
generation-topology factor, NOT a second real network.

## 2. Baseline & recompute mandate (LOCKED)

- All Paper-1 dispatch runs on the **c19d690 worktree** (`../paper1_faithful_c19d690`),
  not `main` (main has Paper-2 physics → −22 %, cannot reproduce Paper 1).
- **We recompute the whole study from scratch** under the redesigned taxonomy and the
  defensible-U calibration (below). v1 numbers are reference only; v1 frozen at
  `results/v1_frozen/`. New output → `output/paper1_v2/` and `results/v2/`.
- The pressure-study station code (lateral PWL, `n_transfer_stations`, whitelist) will
  be **ported into the worktree** for L4/L5, gated so L1–L3 stay byte-identical
  (verify to the cent before trusting the baseline).
- Paper 2 stays untouched (`main`, `configs/paper_2/`, `scripts/paper_2/`).

## 3. Experimental design — the redesigned levels (LOCKED, `08_LEVEL_REDESIGN.md`)

Two axes; the 174 transmission stations exist at **every** level, only their
aggregation changes. One phenomenon per ladder step (no confounds). Unified Table 2
is in `08_LEVEL_REDESIGN.md`.

| Name | Code | Role / what it adds |
|---|---|---|
| CP | T0P0 | copperplate, no loss (174 stations lumped) — decomposition control |
| CP+L | T0P1 | copperplate + aggregate loss — loss-visibility control |
| ZN | T1P1 | zone-aggregated + loss |
| ND⁰ | T2P0 | full nodes, no loss — topology control |
| **L1** | T2P1 | full nodes + trunk loss — **comparison baseline** |
| **L2** | T2P2 | + temperature propagation (PWL) |
| **L3** | T2P3 | + trunk pressure drop & pumping |
| **L4** | T2P4 | + station resolution + **service laterals** (flat Δp) |
| **L5** | T2P5 | + **dynamic flow-dependent station Δp** & pumping |
| **L6** | T2P6 | + transport delay |
| NL | — | nonlinear reference (exact decomposition, not solved) |

**Loss-placement rule (important, `08` critical review):** L1–L3 use **defensible
trunk U-values** (NO ×4.7 multiplier). Last-mile **service-lateral losses enter only
at L4**. Coarse levels therefore honestly *undercount* real loss (can't see the last
mile); total loss ≈ measured only at L4. This removes the multiplier R2.4 attacked and
is itself a result. Decomposition controls' exogenous loss (CP+L) matches L1's trunk
loss.

## 4. Results so far (v2)

- **Decomposition (Memmingen, exact identity to the cent, `results/v2/analysis/
  decomposition.csv`):** loss 96 % / topology 4 % / interaction 1 %.
  **NOTE:** computed on v1 (possibly inflated) trunk U — **must be recomputed on
  defensible-U configs**; loss expected to stay dominant, exact split will shift.
- **Regret (evaluator, `results/v2/analysis/bias_regret.csv`):** copperplate bias
  −16.6 % but regret **+29 %** (opposite signs — looks cheaper, costs more to execute);
  loss-aware levels regret ≈ bias. Sensitivity: regret sign invariant across marginal
  cost 47–90 €/MWh and disaggregation rule (`regret_sensitivity.csv`).
- **Synthetic generalisation:** decomposition PoC on 1 net → loss 99 % / topo 0.6 %
  (longer pipes → loss dominates more). Full 42-net factorial (T0P0/T2P0/T2P1) running.
- **Hydraulics (pressure study, `05_PRESSURE_AND_NOVELTY.md`):** low pumping is
  physically correct & validated (Wilo 110.8 kW installed vs ~3 kW need; pandapipes
  <0.007 bar trunk agreement) — R2.4 answered by explanation, not inflation.

## 5. Title (decided, `02_STUDY_REDESIGN.md`)

> **Estimation bias versus decision regret in district-heating dispatch optimisation:
> loss visibility, not network topology, sets the fidelity requirement**

## 6. Novelty (R2.1) — `04_NOVELTY_STATEMENT.md`

(1) decision-regret + physical-deliverability of schedules; (2) copperplate+losses
control + exact decomposition; (3) **station-resolved hydraulics (L4/L5) validated on
real component data — the R2.4 answer, and the finding that even station-level detail
doesn't change decisions**; (4) generation-topology moderator (synthetic); (5)
out-of-sample prediction (synthetic + parameterised L4).

## 7. Tooling built (main `tools/`, reads worktree output)

`evaluator.py` (regret), `economic_cost.py`, `regret_sensitivity.py`,
`make_t0p1_data.py`; worktree `scripts/paper/_run_t0p1.py`, `_run_synth_decomp.py`,
`_run_synth_factorial.py`.

## 8. Open items needing the author

- **T0P1c** measured loss: needs 2025 **plant-side heat generation** (Wärmeeinspeisung),
  not in the delivery-side dataset — see `DATA_REQUESTS.md`.
- Extension request drafted (`extension_request.md`); confirm date + APEN-D vs APEN-S.

## 9. Doc map

**Current (authoritative):** this file · `05_PRESSURE_AND_NOVELTY` · `06_SCOPE_REEVALUATION`
· `07_PAPER1_WORKFLOW` · `08_LEVEL_REDESIGN` · `DATA_REQUESTS`.
**Being aligned to the above:** `README`, `00_CONTEXT`, `01_REVISION_PLAN`,
`02_STUDY_REDESIGN`, `03_FIGURE_SPEC`, `04_NOVELTY_STATEMENT`, `P0…P12`,
`acceptance_criteria`.
