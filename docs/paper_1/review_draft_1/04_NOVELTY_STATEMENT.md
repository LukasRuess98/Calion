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

### 3. Generation topology as a moderator — the new knowledge

In Memmingen **all generation sits at j1**. With central generation there is no
routing decision: the network is a pure delivery tree, and spatial resolution can
only reveal loss. Our v1 finding "pure routing contributes ≈0" was therefore
partly a property of the case study, not a property of DH networks. We now say so.

Stadtbach has six producer nodes across three arms, a bidirectional trunk, and a
merit order spanning 10–58.6 EUR/MWh. Which source serves which demand is a live,
location-dependent decision. Two real networks, one of each type, test whether
the routing effect is conditional on generation topology.

This retires Reviewer 1.1's objection directly: "centrally located generation"
and "unidirectional flows" were listed as scope restrictions that made the
conclusion overbroad. They are now experimental factors.

### 4. Validation resolution bounds claimable fidelity

Memmingen is metered at 27 consumer nodes → validatable at node resolution.
Stadtbach is metered at shafts → validatable at zone resolution, but **including
pressure**, which Memmingen lacks entirely.

> A model resolved finer than its metering cannot be validated at that
> resolution; its additional detail is asserted, not verified.

This costs nothing to produce and converts a limitation into a result. It also
sharpens the practical recommendation: if operators can only validate at metering
resolution, the zone level is not merely cheap — it is the finest defensible level
for most of them.

Note the pairing is complementary, not redundant: node-resolved *thermal*
validation on one network, zone-resolved *thermal and hydraulic* validation on the
other. Between them every physical sub-model in the paper has empirical support.
In v1 the extended physics had none.

### 5. Prediction rather than description

An a-priori estimator of the bias from observable network properties (pipe
length, ΣU·L, heating curve, demand concentration), fitted on Memmingen plus the
synthetic factorial and tested on Stadtbach **without refitting**. Stadtbach lies
well beyond the fitted pipe-length range, so this is extrapolation, not
interpolation.

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
> bias from decision quality. Applying both to two real networks with contrasting
> generation topologies shows [RESULT], and that the effect of spatial resolution
> is conditional on whether generation is centrally or distributedly located — a
> dependency not previously identified.

---

## Risks, and the sentence to prepare for each

| Claim | Risk | Prepared response |
|---|---|---|
| 1 Regret | "standard ex-post evaluation" | Conceded in text; claim is the divergence and its predictability |
| 3 Moderator | Stadtbach shows routing ≈ 0 too | **Then that is the finding**, and a more surprising one: routing is null even under distributed generation. Write both sentences now, before seeing results. |
| 5 Prediction | Fails out-of-sample | Also a result, and more informative than a fitted curve — provided we commit to reporting it before we look. |
| All | Reviewer sees reframing as evasion | Response letter states plainly which v1 conclusions changed and why |
