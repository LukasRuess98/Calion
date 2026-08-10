# P6 — Robustness: clustering, calibration, holdout

**Depends on:** P1, P2, P11 · **Blocks:** P7
**Output:** `results/v2/robustness/…`, `revision/audit/P6_robustness.md`

## Part A — Alternative zone aggregations (R1.6)

"Alternative clustering methods could yield different spatial routing and loss
distributions even when total annual losses are preserved."

For Memmingen, three named clusterings plus a null distribution, all preserving
ΣU·L = 1011 W/K:
1. `T1_branch` — current (adjacent nodes sharing a branch segment)
2. `T1_distance` — k-medoids on path distance from source
3. `T1_demand` — balanced annual demand per zone
4. `T1_random` × 10 — contiguous random partitions

Run `T1P1` for each (and `T1P0` for 1–3). Report `cost(T2P1) − cost(T1P1)` and
the spread across the random partitions (Figure F12), with the `loss_main`
magnitude drawn as a reference line so the reader sees the scale immediately.

For **Stadtbach**, `T1` is fixed by the shaft resolution and is not a free choice
— note this in the paper: the aggregation is dictated by the metering, which is
the argument in `04_NOVELTY_STATEMENT.md` §4.

Re-check the warm-year sign reversal (v1: L2−L3 = −2.2 %) across all clusterings.
If it appears in all, it is structural; if in one, v1's explanation
("loss-aggregation artefact of L2's zone approximation") needs revising.

## Part B — Calibration robustness and out-of-sample validation (R2.4)

**A problem v1 shipped with:** the BCM cross-check calibrates the ×1.330
multiplier on the Oct–Feb subset and then reports MAE 1.56 °C, RMSE 2.15 °C **on
that same subset** (n = 3173). That is in-sample error presented as validation.
R2 asked for "additional out-of-sample validation where possible" and may well
have seen this.

**Required:**
1. **Temporal holdout** — calibrate on heating season 1, validate on season 2.
   Report both, side by side, and state the degradation.
2. **Spatial holdout** — apply the same calibration/validation node discipline
   already used for the MIQCP to the BCM.
3. Report in-sample and out-of-sample metrics together everywhere. A stated
   degradation is safe; an unstated in-sample number is not.

**Multiplier plausibility — DECIDED APPROACH: Option A (2026-08-09).** v1 has two
calibrations that disagree badly: BCM global ×1.330 versus branch-sequential
**terminal-pipe** at ×4.7 nominal. A ×4.7 multiplier on nominal EN 253 U-values is
not defensible as insulation ageing — and it sits on the *terminal* pipes, exactly
where the 174 real service laterals + substations connect. It is the trunk-only
model compensating for the loss pathway it never modelled.

The A-vs-B decision (see `05_PRESSURE_AND_NOVELTY.md` and the R2-by-comment analysis)
resolved to **Option A**: replace the fudge with a physical, real-data loss term.
R2.4 explicitly named this multiplier *and* substations, so the answer must remove
the multiplier physically, not reframe it. The same DXF-lateral data also fixes the
"exceptionally low pumping-energy" half of R2.4 — one real-data fix closes both.

4. **Bound + explicit term (Option A).** Re-run the branch-sequential calibration
   with the trunk multiplier bounded to a defensible EN 253 ageing band
   (`[0.8, 2.0]`), and add an **explicit service-lateral + substation heat-loss
   term** derived from the real data (DXF trace lengths + the 174-station counts,
   `configs/pressure/`). Prefer **per-consumer-node** where DXF connectivity
   supports it; **fall back to a demand-distributed aggregate** service-loss term
   where it does not (~80 % connectivity) — still Option A, robust to the
   reconstruction uncertainty. Report the residual after bound+term.
5. Run `T2P1` and `T2P2` under the bounded+explicit calibration and (for contrast)
   the old permissive one; report the decomposition under each. **The point:** the
   conclusion is not an artefact of a permissive multiplier, and with the physical
   term the trunk multiplier lands in the defensible band. Expect `loss_main` to
   rise vs `topo_main` — state plainly the added loss is measured/DXF-derived, not
   tuned, so it does not read as self-serving.
6. Write `GAP:CALIB-RECONCILE`: why the BCM forward-physics and dispatch-model
   calibrations differed (the dispatch model absorbed unmodelled last-mile loss into
   terminal U-values), what each is fitted to, and how the explicit lateral term
   reconciles them. **Layer B's insight as a rider (novelty):** trunk-only models
   *require* indefensible multipliers precisely because they omit service-lateral +
   substation losses — a generalizable finding, now evidence-backed rather than
   asserted. A model resolved coarser than the real 174 connections cannot capture
   their loss without fudging U-values.

## Part C — Flow error decomposition

v1 reports 36 % flow MAPE against a ±15 % instrument error and sets no gate.
Decompose: systematic bias vs dispersion, by load band, and energy-weighted
versus unweighted. A 36 % number with no gate reads as an unexamined failure;
explained, it is fine.

## Report

`revision/audit/P6_robustness.md`: clustering table and spread; calibration
comparison with in-sample and out-of-sample metrics; flow-error decomposition;
the reconciliation paragraph.
