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
> we added a second real district heating network, with distributed generation,
> bidirectional flow and measured pressure data, which addresses the
> hydraulic-validation concern directly and turns three of the scope restrictions
> Reviewer 1 identified into experimental factors. These changes altered one of
> our headline conclusions, which we now state differently.

---

## Reviewer 2

### R2.1 — novelty
**Response:** we accept that the original submission read as a comparative
application, and we now say so explicitly in the Introduction before making any
claim. The revision adds: (i) decision regret as the evaluation quantity, with a
forward evaluator that contains no linearisation; (ii) `T0P1`, a designed control
condition rather than a fidelity level — a copperplate supplied with the loss
information it cannot itself compute; (iii) a second real network that lets us
test whether the routing effect is conditional on generation topology, a
dependency not previously identified; (iv) the observation that validation
resolution bounds claimable fidelity; and (v) an a-priori bias estimator tested
out-of-sample. We position (i) honestly as the Value of the Stochastic Solution
transposed from the uncertainty axis to the resolution axis, and claim the
transfer and the finding rather than the concept. [§1.2, §2.4, §4.3, §4.4, §4.7]

### R2.2 — topology/loss confound  ← decisive
**Response:** **the reviewer is correct.** We implemented the requested
copperplate with calibrated aggregate losses in three variants, differing in
calibration source, including one calibrated on measured data rather than on the
reference model. The decomposition is now an exact identity […]. The result
changed our principal conclusion, and the title with it. We additionally quantify
the limit of the lumped-loss approach: a coefficient calibrated on one
configuration drifts by […] when transferred, which is the precise sense in which
spatial resolution remains necessary. [§2.3, §4.2, Table X, Figure F6]

### R2.3 — linearisation not rigorous
**Response:** accepted; we adopted all three remedies the reviewer offered.
(i) An intermediate formulation `T2P3` separates linearisation from transport
delay. (ii) Every mixed-integer comparison now reports a rigorous bound alongside
the point estimate and both solver gaps, and we no longer assert effects smaller
than the attained tolerance; the phrase "statistically meaningful bound" has been
removed. (iii) The forward evaluator provides the validated nonlinear reference
the reviewer asked for — it uses native exponentials with no piecewise
linearisation, and is validated against measured temperatures and pressures.
[§2.4, §4.6, Table X, Figure F13]

### R2.4 — validation and pumping energy
**Response:** this comment led us to identify [FINDING]. The second network is
instrumented with pressure sensors in both flow and return at shaft level, which
allowed us to validate the hydraulic model against measured differential pressure
and to transfer the validated parameterisation to the first network. The pumping
energy share is now […] % of thermal demand, consistent with the literature we
cite. We also constrained the pipe-loss calibration to a defensible multiplier
range, moved the residual into an explicit service-pipe term, and now report
in-sample and out-of-sample validation metrics separately. Supply and return
circuits, substation boundary, pressure requirements and pump characteristics are
described in §2.5. [§2.5, §4.1, Figure F11]

### R2.5 — generality
**Response:** accepted on all three points. All 81 synthetic configurations are
now solved; the previous filtering reflected under-sized generation capacity, and
we diagnosed each infeasibility and adopted a stated sizing convention whose
influence on the results we report. The taxonomy is unified — both real networks
and the synthetic study use identical level definitions and the previous
physics-scope mapping table is removed. The analysis is a variance decomposition
plus regression with confidence intervals over the balanced design, and the
selection rules are tested out-of-sample on the second network, which lies beyond
the fitted range. Thresholds are presented as observations within the tested
regimes. [§3.4, §4.7]

---

## Reviewer 1

### R1.1 — scope of "dominates"
Accepted; retitled. The second network removes two of the listed restrictions
(central generation, unidirectional flow), which are now experimental factors
rather than caveats.

### R1.2 — accuracy vs sensitivity
Accepted, and addressed structurally rather than terminologically: regret is a
decision quantity, so "accuracy" is now used only where it refers to decisions.
The two reference roles are defined explicitly in §2.1.

### R1.3 — confounded comparison
Resolved by `T2P3`. Isolated linearisation: […]. Isolated delay: […].

### R1.4 — pre-upgrade validation
Addressed by restructuring: the legacy configuration is now the primary case, so
every headline bias number rests on the configuration the measurements cover. The
electrified configuration is reported separately as a sensitivity.

### R1.5 — assumptions constrain the physics
Accepted and stated as a conditional scope in §4.11.

### R1.6 — clustering arbitrariness
Three alternative clusterings plus a null distribution; spread […]. For the
second network the aggregation is dictated by the metering rather than chosen.

### R1.7 — deterministic, hourly, no reserves
Accepted; limitations expanded.

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
