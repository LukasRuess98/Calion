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
[§1.2, §2.4, §4.3, §4.4, §4.7, Fig. rule]

### R2.2 — topology/loss confound  ← decisive
**Response:** **the reviewer is correct.** We implemented the requested
copperplate with calibrated aggregate losses (the `CP+L` control), and the
decomposition is now an exact additive identity (closes to 0 €; all four solves at
≤0.01 % optimality gap): on Memmingen (defensible pipe U-values, no inflation) the
cost gap resolves into **loss 95.9 %, topology 4.7 %, interaction −0.5 %** (the
interaction is negligible), and this holds across the 135-network synthetic factorial
(all solves at ≤0.1 % gap: loss a median 100.0 % of the gap, topology within ±0.6 % on
every network of 5 km trunk length or more, and never above 2.4 % even on the 1 km
networks, whose entire cost gap is below 6 % of cost). The result changed our principal
conclusion, and the title with it. Crucially, we also show **why the control does
not make spatial resolution unnecessary**: on any single network a loss adder can be
back-fitted so that `CP+L` is both low-bias (−0.6 %) and low-regret (−0.5 %) — but
that adder is an ex-post per-network artifact. Frozen and transferred across the
factorial it **drifts by 23–42 pts of cost** (the loss burden spans 3.2–81.2 % of cost, so
no single adder can track it; even the most transferable choice mis-estimates by a mean of
23.5 pts and up to 40.1 pts when carried to another network). Because the adder cannot be
known a priori, the node-resolved model — which computes the loss endogenously — is
the transferable requirement. [§2.3, §4.2, decomposition table (tab:decomposition), Figure F6]

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
of every bias and regret figure are invariant to the CHP-CO₂ allocation. Concretely, the
copperplate's estimation bias reads **−11.8 % on the Gurobi objective and −15.1 % on the
economic cost** — the same finding, diluted by a constant. The full per-level split is
released as `objective_decomposition.csv` so the reader can reproduce either figure.
[§2.6, §4.2]

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
decomposition. [§2.4, §4.6, linearisation table (tab:linearisation), Figure F13]

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
boundary, pressure requirements and pump characteristics are described in §2.5.

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
metering limitation, not a modelling one, and it is the substance of the resolution argument. For **additional out-of-sample validation** we (i) split the spatial
validation into fitted and held-out node sets, and (ii) test the a-priori bias estimator on
held-out synthetic networks beyond the fitted pipe-length range, as R2.5 also requests.
[§2.5, §4.1, §4.5, Figures F11, F\_corridor]

### R2.5 — generality
**Response:** accepted on all three points, and the filtering is gone rather than
justified. The synthetic study is now the **complete balanced factorial — all 135
cells** of a 3 (node count) × 5 (trunk length) × 3 (demand heterogeneity) × 3 (storage
horizon) design, with no cell dropped. The original filtering reflected under-sized
generation capacity rather than any property of the networks; we diagnosed each
infeasibility, adopted a stated sizing convention, and report its influence on the
results. Because the design is now balanced and complete, the analysis of variance
has unambiguous sums of squares — trunk pipe length accounts for 95.9 % of the
between-network variance in the loss burden, storage horizon 3.2 %, and demand
heterogeneity and node count essentially none. The taxonomy is unified — the Memmingen case
and the synthetic study use identical level definitions and the previous
physics-scope mapping table is removed. The analysis is a variance decomposition
plus regression with confidence intervals over the balanced design, and the
selection rules are tested out-of-sample on held-out synthetic networks whose pipe
lengths lie beyond the fitted range. Thresholds are presented as observations within
the tested regimes. [§3.2, §4.7]

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
by a forward supply-temperature sensitivity (§4). We also examined whether ring topologies and
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
concretely rather than as a generic caveat. [Title, §1, §3.2, §4 limitations]

### R1.2 — accuracy vs sensitivity
Accepted, and addressed structurally rather than terminologically: regret is a
decision quantity, so "accuracy" is now used only where it refers to decisions.
The two reference roles are defined explicitly in §2.1.

### R1.3 — confounded comparison
Resolved by isolating each phenomenon in its own ladder step. Transport delay is now its own
level (`L6`), so it is no longer bundled with linearisation; and the linearisation error is
separated from delay and quantified by the exact decomposition together with the forward
evaluator (the nonlinear reference), reported with rigorous optimality bounds rather than raw
objective differences. Every arrow of the ladder changes exactly one phenomenon (Table of
contrasts, §2.1). [§2.1, §2.4, §4.6]

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
and strengthen the transport validation itself (R2.4). [§2.5, §4 limitations]

### R1.5 — assumptions constrain the physics
Accepted and stated as a conditional scope in the limitations (§4).

### R1.6 — clustering arbitrariness
**Response: tested directly, and the reviewer's condition turns out to be the whole
story.** We re-aggregated the network under three alternative clusterings (4, 7 and 10
zones) and a null distribution of 20 random tree-contiguous 7-zone partitions, solving all
24 to optimality. The reviewer asked specifically about the case where *total annual losses
are preserved*, and that proved to be the decisive qualifier. When ΣU·L is conserved — which
we now enforce by an assertion in the aggregator, holding the producer node as its own zone
so that no trunk pipe is absorbed into a zone without a feed pipe — the realised annual loss
is identical across all 24 clusterings (1257.8–1257.9 MWh, ΣU·L = 1140.2 W/K throughout) and
the **entire cost spread is 11 €, or 0.008 %**. Against the decomposition's spatial-topology
term of 961 € this routing effect is two orders of magnitude smaller, and three orders below
the loss main effect of 19 737 €. Clustering geometry, at constant loss, does not move
dispatch cost.

The converse is equally informative and we report it: a clustering that does *not* conserve
ΣU·L shifts cost by up to ≈6 %, because it silently discards trunk pipes and with them the
loss they carry. The binding requirement for a valid reduced network model is therefore
preservation of ΣU·L — the delivered loss — and not the geometry of the partition, which is
the same conclusion the decomposition reaches by a different route. For Memmingen
specifically, the node aggregation is in any case dictated by the metering — billing-grade
and mixing-valve-limited — rather than freely chosen, which is the validation-resolution
argument of §2.5. [§4.4, Figure F\_r16]

### R1.7 — deterministic, hourly, no reserves
Accepted; limitations expanded.

---

## Senior editor
Lumped references removed with a build-time check; abstract merged to one
paragraph; Conclusions subheadings removed; restructured to five sections;
Highlights and a corrected graphical abstract resubmitted.

## Disclosed proactively
Corrections we made that the reviewers did not raise: asset placement in the
graphical abstract; a percentage inconsistency between the graphical abstract and
the text; removal of an orphaned configuration file from the public repository;
and the withdrawal of a reported figure. On re-examination we found that the
temperature-propagation level, solved with free node temperatures, is degenerate —
the optimiser floors the supply temperature for about 91 % of hours rather than
reproducing the physical decay, collapsing the loss term and producing a spurious
cost reduction roughly six times the forward-evaluated effect. That level's solved
objective is therefore no longer reported; temperature propagation is quantified
through the forward evaluator instead, and the appendix states the degeneracy
explicitly.

We also note two items where the manuscript is deliberately more conservative than
the original submission. The piecewise-linearisation sensitivity at five and eight
segments remains an extrapolation from the per-segment variable increment and is
labelled as such in the appendix; we did not simulate those settings, because the
quantity they were previously used to bound — the linearisation error — is now
measured directly by solving the nonlinear reference. And the supply-temperature
validation is now reported at the network far end over the full annual record,
rather than as a mean over the six validation nodes across a winter window as
previously. The earlier figure was not favourably selected — the all-node mean lies
between the validation-node and calibration-node group means, and two excluded nodes
are the best-performing in the network (Appendix) — but the unselected far-end
figure is the more conservative view and we now report that.
