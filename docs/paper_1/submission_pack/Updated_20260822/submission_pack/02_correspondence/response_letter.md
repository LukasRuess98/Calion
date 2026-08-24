# Response to reviewers — skeleton (pack v2)

Fill after P7. Rules: quote the comment, then respond. Every response names what
changed **and where**. Where a reviewer was right and a conclusion changed, that
is the **first sentence**. Never write "we have clarified this" without a pointer.

---

## Opening

> We thank both reviewers and the editor for reviews that identified genuine
> structural weaknesses. Two comments in particular — Reviewer 2's first and
> second, and Reviewer 1's third — led us to conclude that an incremental
> revision would not be adequate. We have therefore made three substantive
> changes. First, we added a decision-regret evaluation: each model's dispatch
> schedule is re-simulated under a common high-fidelity forward model, so that we
> now report not only how much the objective values differ but what it costs to
> have decided with the simpler model. Second, we added two formulations that
> isolate effects the original design confounded, including the copperplate model
> with calibrated aggregate losses that Reviewer 2 specifically requested. Third,
> we strengthened the hydraulic validation with real component data — manufacturer
> pump characteristics, a demand-side reconstruction down to the individual
> transmission stations and their service laterals from the network DXF plans, and
> an independent cross-check against a nonlinear pipe-flow solver — and we replaced
> the scope restrictions Reviewer 1 identified with experimental factors in a
> balanced synthetic factorial. These changes altered one of our headline
> conclusions, which we now state differently.

---


## Level nomenclature bridge (v1 → v2)

The reviewers hold the original submission, in which the level names mean different things.
All three of `L1`, `L2`, `L3` were reassigned in the revision; the point-by-point responses
below use the v2 names.

| v1 | v1 meaning | v2 |
|---|---|---|
| L1 | copperplate, no loss | **CP** |
| L2 | 7 aggregated zones | **ZN** |
| L1_topo | routing, no loss (synthetic auxiliary) | **ND⁰** |
| L3 | 15 nodes + trunk loss | **L1** (baseline) |
| L3⁺ | + pressure, temperature, delay bundled | split into **L2**, **L3** |
| L3ᴺᴸ | native nonlinear, delay active | split into **L6**, **NL** |

Thus R1.2's "13 % between L1 and L3" is the CP→L1 gap in v2 terms, now −11.8 % on the Gurobi
objective and −15.1 % on the economic cost. We note honestly that v1 already contained
`L1_topo` (routing without losses, today's `ND⁰`) as a synthetic-only auxiliary; R2.2's
confound objection stands for the primary results, and we say so rather than leaving R2 to
find it.

---

## Reviewer 2

### R2.1 — novelty
**Response:** we accept that the original submission read as a comparative
application, and we now say so explicitly in the Introduction before making any
claim. The revision adds: (i) decision regret as the evaluation quantity, with a
forward evaluator that contains no linearisation, and its counterpart finding that
low-fidelity schedules can be physically undeliverable; (ii) `T0P1`, a designed
control condition rather than a fidelity level — a copperplate supplied with the
loss information it cannot itself compute, giving an exact loss/topology/interaction
decomposition; (iii) station-resolved hydraulics (L4/L5) validated on real component
data (manufacturer pump characteristics, DXF-reconstructed transmission stations and
service laterals, pandapipes cross-check) — the direct R2.4 answer, and the finding
that even substation-level detail changes decisions by ~0. We further report, as
secondary findings, (iv) a generation-topology moderator — proven null under central
generation across a balanced synthetic factorial, and posed as a controlled open
question for distributed generation — and (v) an a-priori bias estimator tested
out-of-sample on held-out synthetic networks, which we sharpen into a parameter-free
**fidelity design rule**: the cost gap a copperplate misses equals
`b = λ/(1+λ)` with the loss number `λ = annual loss / annual demand` computable from
the pipe inventory before any optimisation (R²=0.87 zero-parameter over 136 networks,
Memmingen on the curve). This converts the paper's central result into an actionable
screening criterion — compute `λ`, read off whether a copperplate, a calibrated adder,
or node resolution is required — which we regard as the strongest answer to the
significance concern: not another comparison, but a transferable a-priori rule.
We position (i) honestly as the Value
of the Stochastic Solution transposed from the uncertainty axis to the resolution
axis, and claim the transfer and the finding rather than the concept.
[§1.2, §2.4, §3.3, §3.9, Fig. rule]

### R2.2 — topology/loss confound  ← decisive
**Response:** **the reviewer is correct.** We implemented the requested
copperplate with calibrated aggregate losses (the `CP+L` control), and the
decomposition is now an exact additive identity (closes to 0 €; all four solves at
≤0.01 % optimality gap): on Memmingen (defensible pipe U-values, no inflation) the
cost gap resolves into **loss 95.9 %, topology 4.7 %, interaction −0.5 %** (the
interaction is negligible), and this holds across the 135-network synthetic factorial
(all solves at ≤0.1 % gap: loss a median 100.0 % of the gap, topology within $\pm$0.6\,% on every network of 5\,km trunk length or more, and never above
2.4\,% even on the 1\,km networks, whose entire cost gap is below 6\,% of cost). The result changed our principal
conclusion, and the title with it. Crucially, we also show **why the control does
not make spatial resolution unnecessary**: on any single network a loss adder can be
back-fitted so that `CP+L` is both low-bias (−0.6 %) and low-regret (−0.5 %) — but
that adder is an ex-post per-network artifact. Frozen and transferred across the
factorial it **drifts by 23–42 pts of cost** (loss burden spans 3.2–81.2 % of cost; even the
single most-transferable adder mis-estimates by a mean 23.5 pts, max 40.1 pts, so no single adder can track it). Because the adder cannot be
known a priori, the node-resolved model — which computes the loss endogenously — is
the transferable requirement. [§2.3, §3.2, decomposition table (tab:decomposition), Figure F6]

**Methods note — we report economic cost, not the solver objective.** The Gurobi
objective differs from the economic operating cost (energy purchase − sales + fuel +
CO₂ + dump + demand charge) by a systematic **38–41 % (≈80–87 k€)** on Memmingen. This
gap is two accounting terms that carry no marginal operator cost, not a distortion of
the dispatch: (i) CO₂ enters the objective on a **gross** basis, whereas the reported
cost applies the standard cogeneration self-use allocation — crediting the CO₂ of
exported CHP electricity (≈55–58 k€, the avoided-emissions convention); and (ii) a
thermal-storage **cycling penalty** (≈24–26 k€). Both are near-constant across levels,
so they inflate every level's absolute cost about equally, *dilute* the percentage gap
between levels, and cancel in every bias and regret *difference*. We report the
economic cost because it is what an operator actually pays; loss-dominance and the sign
of every bias and regret figure are invariant to the CHP-CO₂ allocation; the copperplate's estimation bias reads $-11.8$\,% on the Gurobi objective and $-15.1$\,% on the economic cost, the same finding diluted by a constant. [§2.5, §3.2]

### R2.3 — linearisation not rigorous
**Response:** accepted; we adopted all three remedies the reviewer offered.
(i) Transport delay is isolated in its own level (`L6`·T2P6, added on top of the
PWL levels), so the linearisation effect and the delay effect are no longer
confounded in a single step. (ii) Every mixed-integer comparison now reports a
rigorous bound alongside the point estimate and both solver gaps, and we no longer
assert effects smaller than the attained tolerance; the phrase "statistically
meaningful bound" has been removed. (iii) The forward evaluator provides the
nonlinear reference the reviewer asked for — native exponentials and computed-
friction hydraulics, with no piecewise linearisation — and its thermal predictions
are validated against the measured annual network loss (the quantity the conclusions
depend on); point node temperatures are not quantitatively validatable given the
mixing-valve metering and flow sensitivity (see R2.4). (iv) **In addition, we now
directly *solve* the nonlinear reference on representative windows**, not only evaluate
it. Fixing the mixed-integer schedule from the PWL model and re-solving the continuous
problem with the native heat-loss bilinearities restored (a non-convex QCP) measures the
linearisation error *at the optimum*, not merely in evaluation. On a winter and an autumn
week this converges to within 0.03\,% of the global optimum and gives a cost change of
**−0.15\,% and −0.33\,%** — small, and *negative*: the PWL model slightly over-states
cost, so the true physics is marginally cheaper. This upgrades the answer from a bounded
estimate to a solved one. Two honest limitations remain and are reported as such: the
same re-solve **over the full year does not converge** (the non-convex programme finds no
incumbent within the solver budget), which is why the solved reference is confined to
representative weeks; and a **low-load summer week is infeasible** under native physics
with the PWL schedule fixed — at summer flows the piecewise temperatures cannot be
delivered, the very physical-deliverability failure our decision-regret evaluation was
built to expose. Where only the bound is available (the global optimum) we report the
bound; where we can solve (representative weeks) we report the solved error — and do not
conflate them. Temperature propagation is handled the same way
— as a component of this validated nonlinear reference, not as a separate mixed-integer
level — because freeing the node temperatures is non-convex and, absent a hydraulic
penalty, degenerate (the optimiser floors the temperature uniformly rather than
reproducing the physical decay); its effect (about 2\,% of network loss) and its
linearisation error are therefore quantified forward and isolated by the exact
decomposition. [§2.6, §3.8, linearisation table (tab:linearisation), Figure F13]

### R2.4 — validation and pumping energy
**Response:** this comment led us to explain the pumping-energy magnitude physically
rather than by calibration. We reconstructed the demand side down to the 174
individual transmission stations and their service laterals from the network DXF
plans, and compared the network's actual hydraulic pumping need against the installed
manufacturer pump characteristics (Wilo datasheet: ~3 kW station-plus-lateral need
vs 110.8 kW installed). We cross-checked the linearised trunk hydraulics against an
independent nonlinear pipe-flow solver (pandapipes, agreement <0.007 bar). The
implausibly low pumping energy is therefore correct and physically explained, not a
modelling artefact. We additionally formalise the station hydraulics as fidelity
levels L4 (station count + service laterals) and L5 (dynamic flow-dependent station
Δp); even at this finest resolution the hydraulic detail changes dispatch cost by
<1 % and decisions by ~0. We also constrained the pipe-loss calibration to a
defensible multiplier range and moved the residual last-mile loss into an explicit
service-lateral term that enters only at L4. Supply and return circuits, substation
boundary, pressure requirements and pump characteristics are described in §2.6.

On the **thermal validation** we are now explicit about what the metering can and cannot
test, which both answers the "large flow errors" concern and strengthens the study. The
monitoring system records temperatures at consumer substations that sit \emph{downstream of
three-way mixing valves}, so the metered temperature is systematically 5--15\,°C below the
primary junction temperature and cannot validate intermediate node temperatures directly; the
one place the mixing valve runs near fully open is the network far end, so we validate along
the **source-to-far-end corridor** (j$_1\!\to$j$_{15}$, 2.1 km) rather than claiming
node-by-node validation. We say this plainly, and it is itself the point behind our
"validation resolution bounds claimable fidelity" argument: billing-grade metering limits what
any model can be validated against. Even along the corridor, a point-in-time temperature match
is sensitive to the network flow (which the billing metering does not pin down), so we do **not**
rest the validation on point node temperatures. Instead we validate the model on the quantity the
cost conclusions actually depend on — the **annual network loss**, matched to about 1.2\,\% — and
report the flow-side comparison as a mean-absolute-percentage error by load band. That
decomposition is the substance of the answer: the aggregate flow MAPE ($\approx$34\,\%) is dominated
by the many low-load hours, where the flow denominator is small and the consumer mixing valves
bypass flow — it is **46\,\% below 25\,\% of peak demand (60\,\% of all hours) but 13--17\,\% at mid
load** (50--75\,\% of peak: 12.9\,\%). Crucially the \emph{absolute} flow error is roughly
\emph{constant} across bands ($\approx$12--13\,m³/h), so the large low-load percentage is a small
absolute miss on a tiny flow — which is precisely why the annual delivered energy still closes to
1.2\,\%. (The sparse top band, $>$75\,\% of peak, is 23\,\% but only 56 hours.) A single aggregate
number therefore overstates the disagreement at the operating points that matter. We are
explicit that the intermediate temperature field cannot be quantitatively validated here; that is a
metering limitation, not a modelling one, and it is the substance of the resolution argument. On further examination we found that a held-out node split cannot be constructed on this
network for the same reason the temperature gates cannot be met: with consumer sensors
downstream of mixing valves, no node provides a junction-temperature reference against which
a held-out prediction could be scored. Rather than report a split we cannot defend, we added a
first-difference comparison, which is immune to a fixed valve offset and tests whether the
model reproduces the network's variation: flow level $r=0.91$ and day-to-day change $r=0.80$,
demand $0.93$ and $0.89$. The held-out evidence in the paper is therefore the synthetic
out-of-sample test, reported including its degradation beyond the fitted range (as R2.5 also requests).
[§2.6, §3.1, §3.6, Figures F11, F\_corridor]

### R2.5 — generality
**Response:** accepted on all three points. The synthetic study was rebuilt as a
balanced 135-cell factorial (three node counts x five trunk lengths x three
demand-heterogeneity levels x three storage sizes), replacing the original
81-configuration design of which only 36 cells were retained; the previous filtering
reflected under-sized generation capacity, so we diagnosed each infeasibility and
adopted a stated sizing convention whose influence on the results we report, and all
135 cells are now solved. The taxonomy is unified — the Memmingen case
and the synthetic study use identical level definitions and the previous
physics-scope mapping table is removed. The analysis is a variance decomposition
plus regression with confidence intervals over the balanced design, and the
selection rules are tested out-of-sample on held-out synthetic networks whose pipe
lengths lie beyond the fitted range. Thresholds are presented as observations within
the tested regimes. [§2.9, §3.9]

---

## Reviewer 1

### R1.1 — scope of "dominates"
Accepted; the title no longer uses "dominates". Rather than a second real network, the
**synthetic factorial** converts several of the listed restrictions into experimental
factors -- node count, pipe length, demand heterogeneity, storage, and generation topology
(central vs distributed) -- so loss dominance is shown to generalise rather than asserted.
Central generation is resolved (the routing effect is null across all 135 networks); the
distributed-generation case is posed as a controlled open question, since the radial model
roots generation at the source and a meshed, bidirectional treatment belongs to the companion
study. The remaining restrictions -- radial topology, unidirectional flow, fixed capacities,
fixed heating curve -- are stated as explicit scope, and the fixed-heating-curve one is bounded
by a forward supply-temperature sensitivity (§3.7). We also examined whether ring topologies and
distributed generation could be added to the synthetic study directly, and report the boundary
precisely. The two are separable. Multi-source (distributed) generation on a radial network is
admissible once the pressure model pins only a primary source and lets the remaining sources float
above their setpoint; without that, every source is pinned to the same head and over-constrains
the shared junctions, so a second source sits at zero. Looped topologies are the genuinely harder
regime: with pipe-flow direction fixed by the pipe list, the return-side pressure balance around a
cycle forces the sum of the loop's friction drops to be non-positive, which is infeasible for any
non-zero flow. Resolving it requires directional (signed-flow) hydraulic variables -- a per-pipe
flow-direction selection that reorients each pressure drop and temperature mix -- which is a
distinct formulation absent from the present radial model. We therefore scope looped, distributed
networks to the companion study rather than approximate them here, and state the requirement
concretely rather than as a generic caveat. [Title, §1, §2.9, §3.14]

### R1.2 — accuracy vs sensitivity
Accepted, and addressed structurally rather than terminologically: regret is a
decision quantity, so "accuracy" is now used only where it refers to decisions.
The two reference roles are defined explicitly in §2.1. [§2.1, §2.4]

### R1.3 — confounded comparison
Resolved by isolating each phenomenon in its own ladder step. Transport delay is now its own
level (`L6`), so it is no longer bundled with linearisation; and the linearisation error is
separated from delay and quantified by the exact decomposition together with the forward
evaluator (the nonlinear reference), reported with rigorous optimality bounds rather than raw
objective differences. Every arrow of the ladder changes exactly one phenomenon (Table of
contrasts, §2.1). [§2.1, §2.6, §3.8]

### R1.4 — pre-upgrade validation (new-asset dispatch not measurement-validated)
> "The pipe model is calibrated and validated using data collected before the
> installation of the heat pump, electrode boiler, and thermal storage... evaluated
> through plausibility checks rather than post-upgrade measurements... does not fully
> validate the dispatch interactions that drive the study's cost conclusions."

**Response: the reviewer is correct, and we now state it as an explicit limitation and
explain why the conclusions nonetheless hold.** The measurements predate the heat pump,
electrode boiler and storage, so their dispatch is modelled with standard component
relations (temperature-dependent COP, storage round-trip efficiency and standby loss) and
checked for plausibility, not validated against post-upgrade metering. Three things make the
study's conclusions robust to this. First, the quantity our fidelity levels differ in is the
network's \emph{transport} physics -- pipe losses, temperature propagation and hydraulics --
which is asset-independent: a pipe's loss and pressure drop depend on the flow and
temperatures it carries, not on which unit produced the heat, and that transport physics is
exactly what the pre-upgrade data validate. The new assets enter only through the dispatch
they produce. Second, the paper's conclusions are \emph{comparative and structural} -- the
bias and regret \emph{between} fidelity levels on a fixed portfolio, and which representation
captures the cost gap -- not absolute cost predictions for the Memmingen schedule; they are
invariant to the exact post-upgrade dispatch, because both the biased and the reference
schedule use the same asset models and are evaluated under the same forward physics. Third,
the synthetic factorial, which involves no measured dispatch at all, reproduces the same
loss-dominance and regret findings across 135 networks -- demonstrating that they are
properties of the network-representation choice, not of any single validated or unvalidated
schedule. We add the post-upgrade-dispatch limitation explicitly to the limitations section
and strengthen the transport validation itself (R2.4). [§2.9, §3.14]

### R1.5 — assumptions constrain the physics
Accepted, and answered with a dedicated mechanism subsection (§3.12) that sets out how each
assumption closes a specific channel through which the extended physics could act; opening one
of them (a flexible supply temperature) turns hydraulics from a negligible cost into the binding
constraint. The conditional scope is also stated in the limitations (§3.14). [§3.12, §3.14]

### R1.6 — clustering arbitrariness
Answered as a solved experiment (§3.4): three deliberate alternatives (four, seven and ten
zones) plus a null distribution of twenty random tree-contiguous partitions, all conserving the
total heat-loss capacity $\sum_p U_p L_p$ and solved to a 0.01\,% gap. The deliberate
alternatives differ from the original by at most 0.01\,% of annual cost and the twenty null
draws have a standard deviation of 4\,EUR, so zone-boundary choice is immaterial once the
delivered loss is held fixed; loss, not geometry, carries the cost. For Memmingen the node
aggregation is in any case dictated by the metering (billing-grade, mixing-valve-limited)
rather than chosen, the same point as the validation-resolution argument (§3.1). [§3.4]

### R1.7 — deterministic, hourly, no reserves
Accepted; limitations expanded. [§3.14]

---

## Senior editor
Lumped references removed with a build-time check; abstract merged to one
paragraph; Conclusions subheadings removed; restructured to five sections;
Highlights and a corrected graphical abstract resubmitted.

## Disclosed proactively
Corrections we made that the reviewers did not raise: asset placement in the
graphical abstract, a percentage inconsistency between the graphical abstract and
the text, removal of an orphaned configuration file from the public repository,
and simulation of two piecewise-linearisation settings that were previously
extrapolated.
