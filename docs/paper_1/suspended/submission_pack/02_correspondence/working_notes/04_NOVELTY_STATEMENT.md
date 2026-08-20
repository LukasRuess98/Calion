# Novelty statement — the answer to Reviewer 2, comment 1

Reviewer 2 wrote that the manuscript "requires substantial revision before its
contribution can be assessed as sufficiently significant," and asked us to
distinguish genuine methodological contribution from a structured comparison of
established models. This file is the position we take. It governs the
Introduction, §1.2, the Conclusions and the response letter.

**Rule for everyone writing text: concede first, claim second.** Reviewer 2 will
punish an inflated claim far harder than an honest boundary.

---

## UPDATE 2026-08-10 — station-hydraulics claim added; Shape A adjusts §3–4

The five claims below stand, with these finalisations (see `00_MASTER_STATUS.md`):
- **NEW claim — station-resolved hydraulics (L4/L5).** We formalise the pressure-study
  physics as fidelity levels: transmission-station count, service-lateral losses, and
  **dynamic flow-dependent station Δp**, validated on real component data (Wilo pump
  datasheets, DXF laterals) and an independent pandapipes solve. This is the direct
  answer to R2.4 *and* a stronger finding: even resolved to the individual substation,
  hydraulics change dispatch cost by ε and decisions by ~0. No prior DH fidelity study
  resolves the demand side to the transmission station with real data.
- **§3 moderator** is now carried by the **synthetic** generation-topology factor (Shape
  A cut Stadtbach), which is a cleaner controlled contrast than two real networks.
- **§4 validation-resolution** now pairs Memmingen node-thermal + station-hydraulic
  (real component) validation; the synthetic parameterised L4/L5 is the out-of-sample
  test R2.4 asked for.

## What we concede, explicitly and early

Say this in the Introduction, before any claim:

- The five formulations are established. Steady-state losses follow Frederiksen
  & Werner; PWL Darcy–Weisbach follows Bordin and Mertz; temperature propagation
  follows van der Heijde; the MIQCP treatment follows Hering.
- Comparing model fidelity levels is itself not new: Wirtz et al. [53] varied 24
  MILP variants of a multi-energy system; Larsen [19] and Falay [20] studied
  network aggregation; Kotzur et al. [54] reviewed complexity management.
- Our v1 submission was, as the reviewer says, a comparative application.

## What we claim, in descending order of defensibility

### 1. Decision regret as the evaluation quantity

Every DH fidelity study — including our own v1 — evaluates fidelity by comparing
**objective values** across formulations. That quantity measures the models. The
decision-relevant quantity is the cost of *having decided* with the simpler model:

```
bias(l)   = z(l) − z(ref)                                  ← what the literature reports
regret(l) = z_eval(schedule(l)) − z_eval(schedule(ref))     ← what actually matters
```

Both evaluated by a common forward simulator using native exponentials, no PWL.

**Honest positioning — write this, do not omit it.** The logic is not invented
here: it is the Value of the Stochastic Solution transposed from the uncertainty
axis to the resolution axis (cite Kök et al., already in the reference list), and
it is close to model–plant mismatch evaluation in MPC (cite Quaggiotto, Jansen).
We claim the transfer to network resolution and the empirical finding, not the
concept.

**Pre-empt the obvious attack.** A reviewer will say "this is just ex-post
evaluation." Name that yourself and answer it: the contribution is the
demonstrated *divergence* between bias and regret and its dependence on network
properties, not the evaluation technique.

### 2. A control condition that isolates loss visibility from routing

`T0P1` is not a fidelity level. It is a designed control: a copperplate model
**supplied with the aggregate loss information it cannot itself compute**. Adding
it turns the comparison into an experiment with an exact decomposition identity:

```
total = loss_main + topo_main + interaction
```

Reviewer 2 asked for precisely this model ("a copperplate model incorporating
calibrated aggregate heat losses should be added to separate the effects of
topology and thermal losses"). It is the clearest single answer to "what is the
genuinely new methodological contribution."

### 3. Generation topology as a moderator (secondary finding)

In Memmingen **all generation sits at j1**. With central generation there is no
routing decision: the network is a pure delivery tree, and spatial resolution can
only reveal loss. Our v1 finding "pure routing contributes ≈0" was therefore
partly a property of the case study, not a property of DH networks. We now say so.

Under Shape A this is tested by the **synthetic** central-vs-distributed generation
factor rather than a second real network — a cleaner controlled contrast, since only
the source placement changes while topology, demand and merit order are held fixed.
The central arm is settled: `topo_main`≈0 across all 42 nets. The **distributed** arm
requires a synth source-injection redesign (multi-node injection + bidirectional
flow; see `00_MASTER_STATUS.md` §5b — the radial synth model currently roots all
generation at the primary producer, so a non-root source is stranded/infeasible).
Until that lands we present the moderator as a **motivated open question with the
central result proven**, not a delivered two-regime result. This is honest and still
retires Reviewer 1.1's framing: "centrally located generation" and "unidirectional
flows" become explicit experimental factors, one resolved and one scoped.

### 4. Validation resolution bounds claimable fidelity

Memmingen is metered at 27 consumer nodes → validatable at node resolution. Its
station hydraulics (L4/L5) are validated against **real component data** (Wilo pump
datasheets, DXF-reconstructed service laterals, 174 transmission stations) and an
independent **pandapipes** solve — the R2.4 answer, with no borrowed pressure data.

> A model resolved finer than its metering cannot be validated at that
> resolution; its additional detail is asserted, not verified.

This costs nothing to produce and converts a limitation into a result. It also
sharpens the practical recommendation: if operators can only validate at metering
resolution, the zone level is not merely cheap — it is the finest defensible level
for most of them. The station-hydraulics validation shows the converse edge: even
resolved to the individual substation, the hydraulic detail changes decisions by ~0,
so the fidelity requirement is set below it.

### 5. Prediction rather than description (secondary finding)

An a-priori estimator of the bias from observable network properties (pipe
length, ΣU·L, heating curve, demand concentration), fitted on Memmingen plus a
training subset of the synthetic factorial and tested on **held-out synthetic nets
without refitting**. The held-out nets sit at longer pipe lengths beyond the fitted
range, so this is extrapolation, not interpolation; the parameterised L4 point
extends the same test to station resolution.

---

## Draft §1.2 text (adjust numbers after P7)

> The five formulations compared here are established, and comparative fidelity
> studies exist. The contribution is not the formulations but the experimental
> structure and the evaluation quantity. Prior fidelity comparisons vary network
> representation and loss representation together, so the resulting cost
> differences cannot be attributed to either; and they evaluate fidelity by
> comparing objective values across formulations, which measures the models
> rather than the decisions they produce. This paper introduces (i) a control
> condition — a copperplate model supplied with the aggregate loss information it
> cannot itself compute — that isolates loss visibility from spatial routing, and
> (ii) a decision-regret metric, obtained by re-simulating each model's dispatch
> schedule under a common high-fidelity forward model, that separates estimation
> bias from decision quality. Applying both to a real network (Memmingen) and a
> balanced synthetic factorial shows [RESULT]: loss visibility, not spatial routing,
> sets the fidelity requirement, and schedules that look cheap can be physically
> undeliverable. Whether the routing effect is conditional on distributed generation
> is posed as a controlled open question with the central-generation case resolved.

---

## Risks, and the sentence to prepare for each

| Claim | Risk | Prepared response |
|---|---|---|
| 1 Regret | "standard ex-post evaluation" | Conceded in text; claim is the divergence and its predictability |
| 3 Moderator | Distributed arm not deliverable under Shape A (synth redesign pending, §5b) | Present as open question with central result proven; do **not** claim a delivered two-regime result. If the redesign lands and routing is ≈0 too, that is a *more* surprising finding — routing null even under distributed generation. |
| 5 Prediction | Fails out-of-sample on held-out synthetic nets | Also a result, and more informative than a fitted curve — provided we commit to reporting it before we look. |
| All | Reviewer sees reframing as evasion | Response letter states plainly which v1 conclusions changed and why |
