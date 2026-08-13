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

**L4/L5 computation (decided 2026-08-10):** the station code (lateral PWL,
`n_transfer_stations`, dynamic station Δp) is Paper-2-era and depends on ~368 lines of
changes absent from the c19d690 worktree; porting it would risk baseline fidelity.
Therefore **L4/L5 are evaluated by the validated forward pressure-study module**
(real component data — Wilo datasheets, DXF laterals, 174 stations — + pandapipes
cross-check), NOT a dispatch re-solve on the baseline. They remain levels in Table 2;
their numbers come from forward evaluation. Result: station+lateral pump ≈3 kW vs
110.8 kW installed; worst node 1.32 bar / 2.7 bar margin; pump share ~0.03 % of
thermal → station hydraulics move cost <1 %, decisions ≈0. This is the R2.4 answer
(substations, laterals, pressure requirements, pump characteristics — all real data)
and reinforces the thesis (finest detail still below decision-relevance).

**Loss-placement rule (important, `08` critical review):** L1–L3 use **defensible
trunk U-values** (NO ×4.7 multiplier). Last-mile **service-lateral losses enter only
at L4**. Coarse levels therefore honestly *undercount* real loss (can't see the last
mile); total loss ≈ measured only at L4. This removes the multiplier R2.4 attacked and
is itself a result. Decomposition controls' exogenous loss (CP+L) matches L1's trunk
loss.

## 4. Results so far (v2)

**SOLVER-GAP HARDENING (2026-08-10, per author "aim at ~0.01 % gaps, un-attackable").**
The original decomposition solves stopped at the config MIPGap=0.5 % tolerance, with
*actual* terminal gaps of 0.08–0.16 % (T0P0 0.155 %, T0P1a 0.100 %, T2P0 0.078 %). That is
the **same order as `topo_main` (813 €, 3.9 %) and larger than `interaction` (123 €, 0.6 %)**
— i.e. those two terms sat within solver noise and were attackable. Fixed: all four
decomposition configs (T0P0/T0P1a/T2P0/T2P1_defU) re-solved at **MIPGap=1e-4 (0.01 %) +
MIPFocus=2**, so every reported term is well above the gap. **DONE 2026-08-10** — achieved
gaps: T0P0 0.0003 %, T0P1a 0.0006 %, T2P0 0.0089 %, T2P1_defU 0.0053 %. Impact: T0P0's cost
moved −284 € (−0.245 %) vs the loose solve — *larger than the interaction term* — and the
interaction flipped +0.60→−0.52 % (it was a gap artifact). loss-dominance (95.85 %) unmoved.
The exact identity closes to **0.000e+00 €** (`decomposition_live.py` → `decomposition_live.csv`).
Two Windows gotchas hit + fixed en route: cp1252 `→` crash in extract (use PYTHONIOENCODING=utf-8,
see [[feedback_pythonioencoding_utf8]]) and `_dump_yaml` wrapping a long description string
(broke calion's simple_yaml) — prefer targeted one-line Edits over full round-trip dumps for
config tweaks.

- **Decomposition (Memmingen, exact identity, HARDENED to 0.01 % gap 2026-08-10):**
  `decomposition_live.py` → `decomposition_live.csv`, from the four re-solved runs (all
  MIPGap ≤0.0089 %). **loss 95.85 % / topo 4.67 % / interaction −0.52 %, total gap 15.12 %
  of L1; closure residual 0.000e+00 € (exact, not fitted).** The tightening mattered: at the
  old 0.5 % tolerance the split read 95.45/3.95/**+0.60** %; the interaction **flipped sign**
  (+0.60→−0.52 %), confirming it was a solver-gap artifact — it is now resolved as negligibly
  small (|0.5 %|, ~3× the combined gap noise), i.e. loss and topology are near-separable.
  loss-dominance (95.85 %) is orders above any gap and un-attackable. (v1 inflated-U was
  loss 96 %/topo 4 %; de-inflating the ×4.7 j13_to_j15 multiplier R2.4 attacked leaves the
  conclusion unchanged.) NOTE the stale `decomposition_defensibleU.csv` (95.45/3.95/0.60)
  is superseded by the hardened `decomposition_live.csv`.
- **Synthetic factorial (42 nets, `synth_factorial_decomposition.csv`, HARDENED to
  ≤0.1 % gap 2026-08-11, `synth_decomp.py`):** loss **99.4–100.7 % of gap (median 100.0 %)**;
  **topology within ±0.72 % for EVERY net** (min −0.72, max +0.57); burden 3.4–67.4 % of
  cost (rises with pipe length). The tightening removed real noise: at the old 1 % gap loss
  ranged 99–**118 %** and topo −18…+0.6 % (a 118 % loss outlier and −18 % topo values —
  attackable artifacts, now gone). Loss dominance generalises across node count, pipe length,
  demand heterogeneity, storage. (37 cells solved at 1e-4, 89 at 1e-3 → all ≤0.1 %.)
- **Regret (evaluator) — LIVE defensible-U lineage, `regret_decomp.py` →
  `regret_decomp.csv`/`regret_decomp_pricing.csv` (2026-08-10, HARDENED to 0.01 % gap):** ref = L1.
  **CP: bias −15.12 %, regret +46.10 %** (at marginal 72.2; +27–29 % at marginal 50 — the
  earlier figure). **ND⁰: bias −14.42 %, regret +46.81 %** (topology-without-loss ≈ copperplate).
  **CP+L (T0P1a): bias −0.63 %, regret −0.54 %** — BOTH tiny, so on a single fixed network the
  loss-corrected copperplate IS a near-perfect substitute for the ladder (the reviewer's
  "CP+L tension", now empirically confirmed). This is *rescued only by the DRIFT result*: the
  adder that makes CP+L work is calibrated ex-post on this network's realised loss and drifts
  by 23–42 pts of cost across scenarios (mean 23.5, max 40.1 pts for the best adder; short→long
  transfer under-provisions up to 95 % of the true loss), so it cannot be known a priori. **#4 shortfall-pricing: CP regret
  sign-invariant and strongly positive across all three schemes** — marginal +46.10 %, peak
  +61.17 %, unmet-penalty(1000 €/MWh dump) +831.7 %; CP+L pricing-invariant (−0.54 %) because it
  provisioned the loss (extra_loss=0, nothing to top up). **Asymmetry |regret|>|bias|** (15→46):
  the copperplate omits loss (bias −15 %, thinks it needs less), so under execution the loss is
  covered by top-up at the marginal/peak unit at the winter hours it never planned for — dearer
  than optimal pre-planning; the finer the shortfall price the larger the regret, never a sign flip.
  **Deliverability violations = 0** for every level (velocity/Δp/unmet all zero): the evaluator
  prices ignored loss as top-up COST (the regret), so CP is never "undeliverable," just dearer —
  regret+drift, not violations, carry the paper. NOTE: earlier −15.1 %/+27.2 % figure superseded
  by this live run; `regret_sensitivity.csv`/`bias_regret.csv` were STALE (deleted source runs).
  CP+Lb (T0P1b heating-curve adder) excluded — its run has a broken temperature export
  (T_sup/T_ret NaN 8016/8760 h); re-solve to include.
- **Station hydraulics (L4/L5):** evaluated by the validated forward pressure-study
  module (see §3 note) — cost <1 %, decisions ≈0; forward evaluation upper-bounds the
  regret, so this is rigorous, not asserted.
- **Supply-temperature flexibility (Pillar-2 robustness, forward-evaluated 2026-08-11,
  `tsup_sensitivity.py` → `tsup_sensitivity.csv`):** the interesting free-T_sup form is
  bilinear (MIQP-intractable, same as NL-ref), so tested FORWARD not re-solved — hold demand
  + T_return, lower plant T_sup, let loss fall but ΔT shrink → flow/pumping rise. Result on L1:
  cost-optimal reduction **17.5 K worth 6 220 €/yr ≈ 4.6 % of operating cost** (loss valued at
  marginal 72.2 → upper bound; less if baseload-covered). **The saving is entirely a LOSS
  effect** (loss cost −8 645 €, pump +2 425 €) → **loss-dominance survives T-flexibility**.
  **Hydraulics flip negligible→binding:** pump energy 7.9→32.3 MWh (4.1×), **velocity limit
  binds at 20 K** — so under free T_sup hydraulics are the binding CONSTRAINT (not a material
  cost), precisely qualifying Pillar 2. Turns the fixed-heating-curve *limitation* into a
  *result*. CAVEAT: the evaluator's demand-share flow model understates circulation → absolute
  node temps unreliable (validated to ~2 % on TOTAL loss only); velocity (mdot+geometry) is the
  rigorous binding constraint, delivered-T is a caveated diagnostic. IDEA 1 (distributed-gen
  moderator on Memmingen) needs model surgery, deferred — see [[project_paper1_idea1_idea2]].
- **THE DECIDER — frozen-adder DRIFT (resolves the CP+L tension, `frozen_adder_drift.py`
  → `frozen_adder_drift.csv`, 2026-08-10):** CP+L supplies the copperplate an *exogenous
  calibrated* loss; if one frozen adder transferred, CP+L would be low-bias AND low-regret
  and the resolved ladder would be moot. It does NOT transfer. Across the 42-net factorial
  (HARDENED ≤0.1 % gap) the loss burden (the quantity the adder must reproduce) spans
  **3.4 %→67.4 % of cost (64.0 pts)**. Even the **single most-transferable** frozen adder
  still mean-drifts **17.2 pts (max 32.3 pts)**; the median net's adder drifts 20.1 pts.
  Transferred from a short to a long network it **under-provisions the true loss by 53–94 %**;
  and at **fixed 15 km length**, varying storage/heterogeneity alone still moves the burden ~16 pts.
  → CP+L is a diagnostic *control*, not a substitute for spatial resolution; the ladder is
  load-bearing because it computes loss **endogenously**. This is the paper. (No new solves.)
- **Synthetic generalisation:** decomposition PoC on 1 net → loss 99 % / topo 0.6 %
  (longer pipes → loss dominates more). Full 42-net factorial (T0P0/T2P0/T2P1) running.
- **Hydraulics (pressure study, `05_PRESSURE_AND_NOVELTY.md`):** low pumping is
  physically correct & validated (Wilo 110.8 kW installed vs ~3 kW need; pandapipes
  <0.007 bar trunk agreement) — R2.4 answered by explanation, not inflation.

## 5. Title (decided, `02_STUDY_REDESIGN.md`)

> **Estimation bias versus decision regret in district-heating dispatch optimisation:
> loss visibility, not network topology, sets the fidelity requirement**

## 5b. MODERATOR PROBLEM (found 2026-08-10) — needs an author decision

The generation-topology moderator (novelty claim #3: does topology matter under
DISTRIBUTED generation?) **cannot be tested on the synthetic factorial.** PoC
(`_run_moderator_poc.py`, output/paper1_v2/moderator/): placing a generator at any
non-root node (tried leaf j_5 and mid-node j_2) leaves it **stranded — 0 output** —
because the synth radial model only wires generation into the primary producer (j_1);
other-node generators are not connected to their node's heat balance. Central gen:
topo ≈ 0 (proven, 42 nets). Distributed gen: **untestable on radial synth without
model changes.** This is exactly the meshed/bidirectional, multi-real-producer regime
that **Stadtbach** covered — which Shape A CUT. So under Shape A the moderator is not
demonstrable. **Options (author call):**
  (a) SOFTEN claim #3 to a scope limitation/open question: central gen → routing ≈ 0
      (shown); distributed gen requires meshed networks (future / companion study).
  (b) Extend the synth model for multi-node source injection + bidirectional flow
      (real model work).
  (c) Reinstate Stadtbach for the moderator only (partial reversal of Shape A) — it is
      the natural distributed-generation test case.
Recommendation: (a) is honest and cheap and keeps Shape A; the moderator becomes a
motivated open question rather than a delivered result. Revisit if (c) is wanted.

**IMPLEMENTING (b) — findings after 6 config attempts (2026-08-10).** Chose (b) per
author. Non-primary generation stays stranded (HP/gas = 0) across: leaf j_5, mid-node
j_2, dedicated producer node j_hp2, `bidirectional:true` pipes, explicit
`primary_producer`, and `pressure_drop:true`. Decisive diagnostic: generation ONLY at
a non-primary node is **INFEASIBLE** → the synth flow model roots at the primary
producer; other nodes are pure sinks. This is STRUCTURAL, not a config flag. Stadtbach
works because its secondary producers feed **pure junction nodes via OUTGOING pipes**
(`from: j_gtost, to: j_ost`) with the `_link_pressure_propagation` multi-feed handling
— a topology PATTERN the radial synth tree (single root, mixed nodes) lacks.
**Correct path for (b):** rebuild the synth moderator net in the Stadtbach pattern —
2+ producer nodes, each with an outgoing pipe into a shared pure-junction hub, the hub
distributing to consumer nodes, bidirectional trunk + pressure on. This is a topology
redesign (a real sub-project), NOT a tweak of the existing radial configs. Best started
fresh by first extracting the minimal working pattern from a solved Stadtbach run
(confirm its secondary producers actually generate >0), then templating a synthetic
version. Config-tweak attempts are exhausted; `_run_moderator_poc.py` documents them.

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
- Extension request drafted (`extension_request.md`); **record RESOLVED 2026-08-11 =
  APEN-D-26-15734** (live in Editorial Manager; APEN-S-26-20346 stray disregarded). Still
  owed: confirm the requested new deadline date.
- **DECIDER route chosen = DRIFT, not deliverability-violations (2026-08-10 audit).** The
  reviewer suggested leading with CP/CP+L *deliverability violations* from `bias_regret.csv`.
  On audit that route is NOT currently available: (i) `bias_regret.csv` contains only
  L1–L3plus, never CP/CP+L; (ii) the evaluator's violation machinery is half-built — only
  `velocity` is live, while `dp_consumer` and `unmet_demand` are initialised but never
  incremented (evaluator.py ~L369, L299); (iii) by design the evaluator converts a coarse
  model's ignored loss into a *top-up cost* (the regret), so CP/CP+L are never "undeliverable,"
  just dearer. Making the violation route real needs a physical adequacy criterion
  (min consumer supply-T / available head) added to the evaluator — a **modelling choice
  that needs author sign-off** (per `feedback_no_unprompted_config_changes`). The DRIFT
  result above settles the DECIDER without it, so this is optional, not blocking.
- **STALE regret artifacts — needs a clean recompute.** `regret_sensitivity.csv` /
  `bias_regret.csv` were produced from `output/paper1_corrected/L1..L3`, which **no longer
  exist on disk** (output/ git-ignored). `bias_regret.csv` still shows the pre-U-leak-fix
  L1 regret (23.4 %, superseded by 29.4 %). The defensible-U lineage (`output/paper1_v2/`)
  currently has only CP+L (T0P1a/b), ND⁰ (T2P0), L1 (T2P1_defU) — **no T0P0 (CP) and no
  L2/L3**. A CP+L *regret* number (as opposed to bias) therefore needs a T0P0 solve + an
  L2/L3 re-solve on the defensible-U configs. Recommend confirming before launching
  (`check everything double before running`).

## 9. Doc map

**Current (authoritative):** this file · `05_PRESSURE_AND_NOVELTY` · `06_SCOPE_REEVALUATION`
· `07_PAPER1_WORKFLOW` · `08_LEVEL_REDESIGN` · `DATA_REQUESTS`.
**Being aligned to the above:** `README`, `00_CONTEXT`, `01_REVISION_PLAN`,
`02_STUDY_REDESIGN`, `03_FIGURE_SPEC`, `04_NOVELTY_STATEMENT`, `P0…P12`,
`acceptance_criteria`.
