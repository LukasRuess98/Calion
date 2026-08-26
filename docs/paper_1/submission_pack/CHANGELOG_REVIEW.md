# CHANGELOG — repository audit against AGENT_PROMPT_FINAL (items A–T)

All edits verified against code/outputs where the prompt required it. Build after each batch:
0 undefined refs/citations/control-sequences, 0 overfull > 50 pt, 37 pp.
User-owned content left untouched: the abstract (`front_matter_v2`), `tab_design_grid`, and the
`tab_contrasts` main-text wiring.

## Reconciliation (user's tab_contrasts wiring)
- `tab_contrasts` was in both the main text and the supplement. Removed the supplement
  duplicate; pointed the appendix reference at the main table (`\ref{tab:contrasts}`);
  renumbered the four remaining supplementary refs (S2→S1, S4→S3, S5→S4, S6→S5).

## A. Model-status contradictions
- **L2**: reworded to "not reported as a solved dispatch — forward-evaluated" (removed the
  contradictory "solved to 0.1 %" as a reported result; kept it only as a diagnostic).
- Removed a **duplicated** bound-reporting paragraph in §2.8 (P2).
- "representative weeks" → "72-hour windows" in limitations, nomenclature, NLref comment,
  and the linearisation prose.
- **A3 (verified from `synth_decomp/` outputs)**: `tab_synthetic` corrected — the 135 = 3×5×3×3
  networks are solved through the four decomposition controls only (not the ladder), and all
  use central generation.

## D/E/G/M/N. Claims narrowed
- **E/J (invalid bounds)**: "re-costing the fixed schedule *upper-bounds the regret* / no schedule
  could be more than 1 % better" → measurement of the fixed schedule with an explicit
  re-optimisation caveat; "no lever to re-optimise" → "little scope"; "bounds it rigorously" →
  "quantifies it".
- **N**: "spatial structure worth almost nothing" → "contributes little"; "relaxing assumptions
  can only … never less" → scoped, non-monotonic; loss-dominance magnitude now stated as
  conditional on the tested systems; "exact decomposition" clarified as an exact **algebraic
  identity** on the four optimised costs.
- **D**: added an explicit caveat that regret is measured against the baseline schedule's
  execution cost, **not** the (uncomputed) high-fidelity optimum.

## I. Validation claims vs evidence
- Table 5: far-end supply-temp gate now reads **fail** (applicable, exceeded; the near-pure
  bias is the metering-offset explanation, not a reason for "n/a"); trunk-drop stays **n/a**
  (baseline does not produce it); corridor → **report (no gate)**. Caption rewritten to match.
- Loss claim already hedged ("we do not claim to have measured the loss independently").

## O. Cost accounting + CO₂ convention
- Decision: **kept net** (economic cost = what the operator pays). Added the explicit gross-basis
  robustness (computed from `objective_decomposition.csv`, no re-solve): decomposition
  97.0 % / 3.5 % vs 95.8 % / 4.7 %; copperplate bias −12.2 % vs −15.1 %; loss-dominance
  unchanged (strengthened on gross).

## F. Distributed generation
- Confirmed all runs central-only; the "moderator" subsection retitled "Scope condition: the
  routing null is specific to central generation"; "the moderator" → "a candidate moderator".
  The distributed arm remains an explicit open question (non-root source structurally stranded).

## H. Units & equations (traced to code)
- **H1 storage**: already correct — `(1-α_s)^{Δt}`, α dimensionless per-hour. No change.
- **H2 CO₂**: code stores emissions in **kg** (`total_co2_kg`, price EUR/tonne, /1000). Fixed the
  nomenclature units of `E^{CO2}` from `[t]` to `[kg]`.
- **H3 mass-flow**: added the `10⁶` factor (Q in MW, c_p in J/(kg·K)); matches
  `Q·1000/(cp_kJ·ΔT)` in code.
- **H4 pump-power**: added the `10⁻⁶` factor (ṁΔp/ρ is watts → MW). Added a note documenting both
  conversion factors.
- **H7**: clarified the native pumping term — the `W=Q²` auxiliary keeps it quadratically
  constrained (bilinear `QW`), not cubic; solved globally with `NonConvex=2`.
- **H9 delay**: stated units — τ from Eq (19) is in seconds, hourly step taken as Δt = 3600 s,
  so `k_p` counts whole hours.
- **H10**: framing already honest (`k_p=0`, "structurally inactive"; not "physically zero").
- **H5/H6 (traced to code)**: the pressure PWL uses **binary** segment selection
  (`pwl_seg = Var(..., Binary)`, `Σ = 1`), not native SOS2. Reworded "SOS2 weights" → binary
  multiple-choice PWL; the "368 thousand binary variables" claim is accurate
  (8760 h × 14 pipes × 3 segments) and now consistent with the description.

## B. NL exponential-vs-PWL
- Corrected the appendix: the exponential decay is PWL-approximated **only** in the solved level
  (L2); the nonlinear reference re-solves it **natively**, so the −0.15/−0.33 % linearisation gap
  is the **combined** PWL-vs-native gap, not an isolated one that "cancels". Now consistent with
  §2.4 (evaluator "contains no piecewise linearisation").

## P. Editorial
- "The five formulations" → "The individual formulations" (the ladder has ~10 levels).
- No ligature/encoding artifacts in the manuscript source; no compiled placeholder text; no `??`
  refs. Counts (15 junctions / 27 substations / 174 stations) consistent.

## Reviewer-response pass (23-item list)
- #1 storage Eq(11): already correct in source (exponential (1-a)^dt + eta terms). No change.
- #2 synthetic 2.9.1/2.9.2: removed "controls and ladder" + "generation-topology moderator /
  station level" claims; now four decomposition controls, central-only, matching Table 6.
- #3 network-loss: swept "matches measurement"/"measurements resolve loss"/"anchored to loss" ->
  delivered-energy validated (1.23%), loss **model-implied**; Table 3 label "Model-implied
  annual network loss".
- #4 temperature: "displaced not wrong"/"identifies as offset" -> "consistent with a metering
  offset; instrumentation cannot distinguish sensor bias from model error; field not validated".
- #5 gates: far-end scored against the worst-node 2.5 K gate (was 1.5 K mean gate); trunk-drop is
  a diagnostic with no ex-ante gate (removed the 1.0 K gate absent from Table 4).
- #6 NL exp/PWL: extended_physics "shared PWL cancels" -> L2 PWL, NL native, reported gap combines
  both (now consistent with App B.4).
- #7 ladder: L6 = L3 + integer-step delay; does NOT inherit forward-only L4/L5.
- #8 one-phenomenon claim scoped to the four decomposition controls; rest = extended-physics
  evaluation framework (prose + tab_contrasts + conclusions).
- #9 recourse: the three schemes named **shortfall-valuation policies** (cost overlays, not
  executable recourse; no commitment/capacity/grid/CHP re-balancing).
- #10 "true cost" -> forward-evaluated (policy-dependent) cost; #10b first use defined as
  "L1-relative execution-cost gap, so termed here".
- #11 full multiple-choice PWL formulation (breakpoints, segment binaries z, disaggregated flow,
  exactly-one-segment, slope+intercept); nomenclature updated; "SOS2 machinery" removed.
- #12 pumping: reconciled 1.4% (~1,900 EUR) = ~780 EUR pump electricity + ~1,100 EUR
  demand-charge/redispatch response; mostly dispatch response, not pump energy.
- #13 NL 0.03%: "within 0.03% of global optimum" -> "0.03% gap reported by the global solver
  (Gurobi NonConvex=2, valid global bound)".
- #14 summer infeasibility: reported as a solver outcome; physical-vs-numerical cause not
  established (IIS deferred).
- #15 screening rule: "first-principles bound" -> first-order screening heuristic + explicit
  assumptions; "resolve nodes" softened; Fig 6 bands labelled illustrative/judgmental.
- #16 "only quantity a dispatch changes" -> primary operator-cost basis.
- #17 "can only... never less"/"lower bounds"/"does not depend" -> scoped/non-monotonic;
  identity vs conditional-magnitude distinction.
- #18 tau_p nomenclature [h]->[s] with k_p=floor(tau/3600); "exactly zero" -> "represented
  integer-step effect is zero at hourly resolution".
- #19 supply-temp "optimum" -> lowest-cost tested point; 20 K = first infeasible tested point.
- #20 "entire saving is a loss effect" -> gross benefit lower loss, partly offset by pumping.
- #21 Table 14 "L2 free-variable temperature MILP" -> "non-convex mixed-integer bilinear program".
- #22 ligature ToUnicode (glyphtounicode) — partial; residual flagged in REVIEW_BLOCKERS.
- #23 Opus-5 / Gurobi-13 / 2026-refs — flagged for author verification.

## Second reviewer-response pass (17-item list, paper_CLEAN_new_2)
- **Title changed** (author-approved) to "Loss Visibility versus Spatial Detail in
  District-Heating Dispatch Optimisation"; shorttitle updated.
- **#2 46.1% reframed** (author-approved) from "costs 46.1% more to execute/operate" to a
  "forward-valued schedule gap" (abstract, 3.3, conclusion, F_regret caption); "incompetent
  controller" -> "under-provisions the loss". "Decision regret" kept as the defined term.
- **#1 storage**: already exponential; added dimensionless exponent (1-a)^{Dt/1h}.
- **#4 Table 9**: added a raw thermal-shortfall column (extra_loss_mwh: CP/ND0 ~1160 MWh,
  loss-aware 0), distinct from the hydraulic Viol. count; caption defines "physically
  deliverable" = both zero.
- **#6 Table 8**: caption states baseline-treatment coding vs CP, oracle constant-adder CP+L,
  exact algebraic identity (not causal), Shapley-invariant.
- **#7 (partial)**: verified from code L1/L3/L6 run in milp_linearize (temps fixed) -> L1->L3 is
  isolated pressure; extended_physics/Table 2/Table 14 made consistent (L6=L3+delay, L2 non-convex
  mixed-integer). Table 3 (tab_design_grid) is user-owned -> flagged.
- **#8 NL class**: "non-convex quadratic programme" -> "non-convex nonlinear programme" (native
  exponential; not a QP).
- **#9 validation reconciled**: the ex-ante supply-temp gates are scored on the validation node
  set / 744-h window (mean 1.32 K, worst 2.27 K -> both PASS); far-end/corridor annual values are
  separate diagnostics (not "fail"); return-temp is a calibration check (not gated); energy
  closure shown as <1e-3 MWh (~0%); trunk-drop relabelled MILP. Tables 4 and 5 both updated.
- **#10 loss language**: "measured total"/"true loss"/"measured annual loss" -> delivered-energy-
  implied / model-derived / full network loss (base_formulation, zone_clustering, §3.4).
- **#11 (abstract)**: station claim -> forward-evaluation wording ("adds <1% to the fixed
  schedule's cost, no hydraulic violation").
- **#12**: "upper bound" -> "highest-priced valuation" (prose + tab_tsup).
- **#14 zone EUR11**: -> at/below solver tolerance (approx 13 EUR on Memmingen), not a measured effect.
- **#15 screening**: lambda now "from geometry, coefficients, temperatures, demand"; "instruction
  to resolve nodes" -> screening indication (a known adder can suffice); "measured error"->"realised".
- **#17 (partial)**: Kelvin stated in the Lorenz COP equation.
- **Editorial**: removed all prose revision-history language ("original submission", "a reviewer",
  "in this revision", "v1", "our earlier submission") across sections + master.

## Flagged-items pass (second-review follow-up)
- #5 CP-vs-ND0: explained the EUR 961 as a real effect (the objective also differs by ~850 EUR,
  so ND0 is genuinely more constrained than CP, not alternative-optimal) - the cost of routing
  heat through the node-resolved flow constraints at zero loss.
- #7 tab_design_grid FIXED (user-authorised): the L6 column now = L3 + delay (removed the
  inherited station-resolution/lateral/dynamic-pressure rows); temperature-propagation row
  corrected (L1/L3/L6 fix temperatures = "--"; L2/L4/L5 = "fwd"); caption explains fwd and the
  non-monotone L6.
- #8 NL-72h documented: mixed-integer schedule (commitment + PWL selectors) fixed, continuous
  vars re-optimised, native gaps 0.009 % / 0.025 %, full-year re-solve returned no incumbent.
- #11 station wording -> forward-evaluation everywhere (physics_null, Section 3.6, conclusion);
  pandapipes stated as a trunk-pressure-calculation check only (not flows/stations/laterals).
- #13 cumulative path delay: the ~2.8 km trunk path travel time is < 1 h, so per-pipe flooring
  erases no cumulative delay here.
- #16 flow-uncertainty: pump energy 2-19 MWh and peak <= 7 kW under +-34 % flow; the capacity
  margin and the ~1.4 % L1->L3 conclusion are unchanged.
- #17: zero-flow exponential limit stated; the CP <= L1 relaxation ordering qualified to the
  economic-cost basis.
- Editorial: distributed/central "arm" -> "case"/"setup"; malformed "(S2.4, S4.7)" -> Section
  ref; reproducibility/NDA statement already correctly separates NDA Memmingen inputs from the
  reproducible synthetic factorial.
