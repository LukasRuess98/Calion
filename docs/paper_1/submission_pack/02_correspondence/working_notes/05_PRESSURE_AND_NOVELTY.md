# Supplement — Novelty strategy (R2.1) and pressure-study integration

Supersedes parts of `04_NOVELTY_STATEMENT.md` §4 and `P1_hydraulics_validate_transfer.md`
after auditing the parallel-session pressure work. Written 2026-08-09.

---

## Part 1 — The pressure study changes the R2.4 answer (and the pack's premise)

The revision pack (P1) assumes the low pumping figure is an **error** that will
**grow toward the 1–5 % literature** once fixed. The parallel-session pressure work
(memory `project_memmingen_pump_pressure_study`,
`project_memmingen_pandapipes_crosscheck`; code on `main`:
`model_finalizer.py` pressure whitelist + `thermal_node.py` lateral-loss PWL +
`configs/pressure/`) shows the opposite, and does so **with real data**:

- **Real installed pump capacity:** 5 × Wilo IL-E pumps, **110.8 kW** total, at the
  real Energiezentrale (`j_9`). Manufacturer datasheet in
  `configs/pressure/Memmingen_componenets_spec/`.
- **Real hydraulic pumping *need*:** peak total electrical pump draw (producer pipe
  friction + all transfer-station Δp + service-lateral losses) ≈ **3–3.2 kW**.
  Margin ≈ 108 kW. The pumps are massively oversized relative to the actual need.
- **Independent nonlinear cross-check:** pandapipes (Newton–Raphson, Colebrook–White)
  agrees with the MILP's linearised trunk pressures to **< 0.007 bar** on 13/14 pipes;
  the constant f = 0.02 assumption is validated at the network's real Reynolds numbers.
- **Real network detail added:** 174 DXF-confirmed transfer stations (120 residential
  + 54 industrial) vs the paper's 15 aggregated nodes; real service-lateral pipe runs.

**Conclusion for R2.4:** the low pumping figure is **largely physically correct for
this network**, not a bug. The paper's actual error was rhetorical — it *cited* the
1–5 % range as if it applied, then reported a figure two orders lower **without
explaining why**. The fix is to **explain and validate**, not inflate:

> A compact (~3.3 km) industrial distribution network with oversized installed pumps
> sits well below the 1–5 % transmission-dominated literature range. We show this with
> manufacturer pump data (110.8 kW installed, ~3 kW needed) and an independent
> pandapipes nonlinear solve.

There is one genuine magnitude correction to carry over: Paper 1 counted **pipe
friction only** and omitted the transfer-station and service-lateral pump work
(≈ 5× understatement per `get_total_pump_power()`), plus the already-fixed
pump-attribution bug (13/14 radial pipes dropped, 2.4→10.6 MWh). Both raise the
number but leave it far below 1–5 % — and now it is *defended*, not asserted.

**Two caveats to state precisely, not hide:**
1. The pressure study runs on a more realistic topology (`primary_producer: j_9`,
   real per-node stations) than Paper 1's all-assets-at-`j_1` aggregation. It
   validates the hydraulic **magnitude and the linearisation accuracy**, and the
   **sufficiency conclusion**; the exact per-node pressures are from the pressure
   config, not the paper's dispatch config. Frame it as a real-component hydraulic
   validation module, not as the paper's dispatch numbers.
2. The lateral-loss PWL has a documented solver artifact at loose MIP gaps
   (non-adjacent breakpoint weight-spreading); the deliverable uses the closed-form
   post-processing recompute, which is exactly the P11-evaluator pattern.

---

## Part 2 — Novelty (R2.1): the honest diagnosis, then the claims

### 2.1 Concede both prongs first — the reviewer is right

R2.1 has two prongs and both land:
- *Novelty:* v1 genuinely was "assemble established formulations, compare them." That
  is comparative application.
- *Central claim:* "topology dominates" is **un-attributable** because L1→L2 changes
  topology **and** loss visibility together. The frozen v1 numbers already hint the
  driver is loss, not routing: L1→L2 = +12.07 % (losses become visible) vs the small
  incremental L3 pressure/routing terms. Until the `T0P1` control exists we cannot say
  which — so the current title asserts more than the design can support.

Say this plainly in §1 and the response letter. Conceding is what buys the claims.

### 2.2 What is genuinely new — ranked, each tied to a concrete artifact

| # | Claim | The new artifact / result | Why it is not "comparative application" |
|---|---|---|---|
| 1 | **Decision regret + physical-deliverability of schedules** | `tools/evaluator.py`: re-simulate each model's dispatch under native-exponential physics; report cost regret **and constraint violations** (velocity, Δp_min, unmet demand). | No prior DH fidelity study reports that a *cheaper-looking low-fidelity schedule can be physically undeliverable*. This is a new evaluation object, not a new formulation. |
| 2 | **Copperplate + calibrated aggregate losses control** | `T0P1` + exact identity `total = loss_main + topo_main + interaction` (machine-precision). | A designed experiment that isolates loss visibility from routing — the exact model R2.2 requested. Turns a comparison into a controlled decomposition. |
| 3 | **Empirically-validated hydraulic-below-threshold result** | 174-station DXF reconstruction, service-lateral losses, Wilo-datasheet pump budget, pandapipes nonlinear cross-check. | Converts the paper's weakest asserted component into a *validated* one, and reconciles the 1–5 % literature via physical scale. New empirical knowledge, not a re-run. |
| 4 | **Conditional map / generation-topology moderator** | Synthetic central-vs-distributed factor (P5 §5), corroborated by the Memmingen/Stadtbach contrast. | The finding "routing matters only when generation is distributed" is new knowledge beyond "objective values differ." |
| 5 | **Out-of-sample prediction** | Estimator fitted on Memmingen + synthetic, predicting Stadtbach (beyond fitted range) without refit. | Prediction, not description — a falsifiable, pre-registered test. |

### 2.3 Reframe the significance from "which model wins" to a decision-relevance threshold map

The publishable thesis — one sentence — is a **conditional, validated map of when
network detail changes DECISIONS**, not cost estimates:

> Loss visibility dominates cost-*estimation* bias; spatial routing changes
> *decisions* only under distributed generation; and hydraulic detail is below the
> decision-relevance threshold for compact industrial networks — a result we validate
> against real pump data and an independent nonlinear solver rather than assert.

That is practitioner-actionable (it tells an operator which fidelity they actually
need for scheduling vs cost/CO2 reporting vs tariff design), and it is exactly the
"new knowledge beyond previous model-fidelity studies" R2.1 asked for.

### 2.4 Fix the central claim = fix the title

Drop "Topology Resolution Dominates Dispatch Accuracy." Candidate directions
(finalise after the decomposition + regret numbers exist):
- *Estimation bias without decision regret: when does network abstraction change
  district-heating dispatch decisions?*
- *Loss visibility, not spatial routing, drives cost bias in district-heating
  dispatch — and only distributed generation makes routing matter.*

---

## Part 3 — Concrete plan adjustments

1. **P1 reframed.** Replace "fix bug → grow pumping toward 1–5 %" with:
   (a) confirm the already-applied fixes (pressure whitelist, pump attribution,
   transfer-station count, lateral losses); (b) carry the ≈5× station+lateral pump
   work + attribution fix into the reported figure; (c) **validate** via the Wilo
   pump budget + pandapipes (already done — cite it); (d) write the reconciliation
   paragraph explaining the sub-literature figure by physical scale. Stadtbach
   measured-Δp validation stays as complementary operational evidence.

2. **Memmingen now HAS hydraulic validation.** `04_NOVELTY_STATEMENT.md` §4 must be
   updated: it is no longer "Memmingen = thermal node-validation only, no pressure."
   Memmingen has (thermal node validation) + (real-component + pandapipes hydraulic
   validation); Stadtbach adds measured *operational* pressure. Both networks now
   support the hydraulics — a stronger position.

3. **Pandapipes = evaluator validation, not evaluator.** P11 keeps the native-exponential
   forward evaluator; pandapipes validates its hydraulic sub-model on representative
   hours (one appendix table). Do not confound them.

4. **Baseline discipline (from P0).** The pressure code lives on `main` (Paper-2
   physics). For Paper 1, treat the pressure/pandapipes study as a **standalone
   validated forward module** (it already is — separate `configs/pressure/` configs),
   decoupled from the c19d690 dispatch re-runs. Do NOT try to merge Paper-2 physics
   into the dispatch baseline.

5. **Add two figures/tables** (extends `03_FIGURE_SPEC.md`):
   - Pump budget vs installed capacity (Wilo 110.8 kW vs ~3 kW need) — the direct,
     visual R2.4 answer.
   - Pandapipes-vs-MILP trunk pressure agreement (< 0.007 bar) — validates the
     linearisation independently.

## Part 4 — Service-lateral / substation losses: DECIDED = Option A (2026-08-09)

The question "do we add the 174 transmission stations / service laterals into the
L1→L3 dispatch configs, and where?" resolved as follows (full R2-by-comment analysis
in the session log; implementation in `P6_robustness.md` Part B):

- **Copperplate (L1/T0):** NO station objects — a copperplate has no network by
  definition. Its losses enter via the `T0P1` aggregate adder, with `T0P1c`
  (measurement: annual generated − delivered) carrying the true total incl. laterals.
- **Pump/pressure (L3+ only):** handled by the standalone pressure module (already
  built); station *count* does not change aggregate pump power. Not retrofitted into
  the dispatch configs.
- **Heat loss in L2/L3 → Option A:** replace v1's indefensible ×4.7 terminal-pipe
  multiplier with (i) a bounded defensible trunk multiplier `[0.8, 2.0]` and (ii) an
  **explicit real-data service-lateral + substation heat-loss term** (per-node where
  DXF supports it, else demand-distributed aggregate). This is the direct answer to
  R2.4 (which named both the multiplier and substations) and gives R2.2 a physically
  complete reference. **Option B** (keep trunk resolution, report the measured-vs-
  modelled gap) was rejected as the *primary* choice — it leaves R2.4's named
  multiplier untouched and anchors the decomposition to a reference R2 can call
  deficient — but **B's resolution insight is kept as a novelty rider on A**:
  trunk-only models need indefensible multipliers because they omit last-mile loss.

Why A over B, in one line: R2.4 flagged a *specific* fudge factor; A removes it
physically with real data and simultaneously fixes the low-pumping half of R2.4,
whereas B reframes rather than removes it.

## Part 5 — Erratum check (do, but likely benign)

The pressure-whitelist bug made
   `pressure.setpoint_bar` inert project-wide. Confirmed the submitted
   `Memmingen_L3_{MILP,NLP}.yaml` carry **no** `pressure:` setpoint block, so the
   submitted dispatch numbers used network-level params, not the inert per-node
   setpoint — **no dispatch erratum from this bug**. State this in the response letter
   proactively (disclose the bug + that it did not affect submitted results).
