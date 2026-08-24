# Critical pre-resubmission audit — Applied Energy manuscript

**Manuscript:** *Estimation Bias versus Decision Regret in District-Heating Dispatch Optimisation*  
**Journal:** *Applied Energy*  
**Review stage:** Major revision / revise and resubmit  
**Audit date:** 20 August 2026  
**Basis of audit:** current clean and marked-up manuscript, LaTeX source, reviewer letter, response letter, correction notes, and an external literature check focused on district-heating model fidelity, network aggregation, spatial resolution, thermo-hydraulic modelling, validation, and optimisation.

---

# 1. Executive verdict

## Current recommendation: **NO-GO for immediate resubmission**

The revision is scientifically **substantially stronger than the original submission** and now contains a credible contribution for *Applied Energy*. In particular, the new loss/topology decomposition and the distinction between estimation bias and decision regret materially improve both novelty and methodological clarity.

The main remaining risk is no longer a missing central experiment. It is now:

1. **internal inconsistency in the model taxonomy and terminology,**
2. **overinterpretation of forward-evaluated results,**
3. **an insufficiently precise definition of the nonlinear reference and regret evaluation,**
4. **validation wording that is stronger than the available measurements justify,**
5. **technical inconsistencies between printed equations and the implemented model,**
6. **numerical inconsistencies across manuscript, figures, tables, and response letter,**
7. **a literature review that misses several highly relevant 2025 papers and contains some citation-to-claim pairings that should be rechecked.**

After correcting these points, the manuscript is in my assessment suitable for resubmission.

---

# 2. What is already strong

| Area | Assessment | Why it is strong |
|---|---|---|
| CP / CP+L / ND0 / L1 decomposition | **Very strong** | Directly answers Reviewer 2.2 and separates loss visibility from topology instead of changing both simultaneously. |
| Estimation bias vs. decision regret | **Strong** | Moves the paper beyond a standard model-comparison study and makes fidelity decision-oriented. |
| 135-network synthetic factorial | **Strong** | Much more convincing than the original retained subset and gives a structured generalisation test. |
| Hydraulic validation | **Strongly improved** | Manufacturer pump characteristics, DXF-derived station/lateral representation and an independent nonlinear pipe-flow cross-check directly address Reviewer 2.4. |
| Clustering sensitivity | **Very strong** | Deliberate 4/7/10-zone alternatives plus random tree-contiguous partitions answer Reviewer 1.6 experimentally. |
| Weekly nonlinear re-solves | **Useful and credible** | Actual incumbent/lower-bound information is much stronger than an unsupported statement of “<0.5% linearisation error”. |
| Limitations | **Much improved** | Fixed temperatures, deterministic hourly dispatch, radial topology, centrally located generation and pre-upgrade measurements are now recognised explicitly. |
| New title | **Good** | It avoids the unsupported original wording “Topology Resolution Dominates Dispatch Accuracy”. |
| Abstract structure | **Good** | One paragraph and a much clearer motivation–method–result–scope sequence. |
| Reviewer response strategy | **Good in principle** | The response often acknowledges where the reviewer was right and reports the actual corrective experiment. |

---

# 3. Submission blockers

## 3.1 Model taxonomy is not yet fully consistent

The manuscript currently mixes:

- decomposition controls,
- independently optimised fidelity levels,
- forward-evaluated physical extensions,
- an annual forward reference,
- representative-week nonlinear re-solves.

This creates the impression that all rungs L1–L6 are equivalent independently optimised models, although L2, L4 and L5 are treated differently.

### Recommended global taxonomy

| Category | Models | Treatment |
|---|---|---|
| Decomposition controls | CP, CP+L, ND0, L1 | Independently optimised |
| Additional independently optimised levels | L3, L6 | Independently optimised |
| Aggregation sensitivity | ZN | Independently optimised sensitivity case |
| Forward-evaluated extensions | L2, L4, L5 | Baseline schedule evaluated with additional physics, not independently re-optimised |
| Higher-fidelity forward reference | Forward evaluator | Fixed schedule evaluated under richer physics |
| Nonlinear weekly reference | NL-week | Continuous weekly re-solves with specified discrete decisions fixed |

### Mandatory edits

- Remove every remaining occurrence of **“the five formulations compared here”**.
- Do not call L2/L4/L5 equivalent “optimised levels” unless they are actually re-optimised.
- Table 2 and Table 3 should explicitly distinguish **optimised**, **forward evaluated**, and **reference only**.
- The synthetic study should say exactly which model configurations were solved for all 135 networks.
- The nomenclature should not imply that NL is simply the next rung of the same solved ladder.

---

## 3.2 False distributed-generation factor in the synthetic factorial

The factorial is:

\[
3 \times 5 \times 3 \times 3 = 135
\]

corresponding to the four factors currently reported in the design. There is therefore **no additional central-versus-distributed generation factor**.

Any sentence saying that generation topology was included as a factorial factor is inconsistent with the experiment and also contradicts later statements that distributed generation remains outside scope.

### Replace with

> All synthetic networks use centrally located generation. The balanced factorial varies node count, trunk length, demand heterogeneity and storage size. Distributed generation, bidirectional flow and meshed topologies remain outside the scope of the present study.

### Also correct

- response to Reviewer 1.1,
- response to Reviewer 2.5,
- Introduction / contribution section,
- synthetic-method section,
- limitations/conclusion,
- any graphical summary that implies distributed generation was tested.

---

## 3.3 Remove “true cost”, “true physics” and equivalent wording

The forward evaluator is a **computational reference**, not empirical truth.

There is no measured post-upgrade optimal dispatch against which the resulting schedule is validated. Calling the evaluated result “true cost” would directly reopen Reviewer 1.2 and Reviewer 1.4.

### Preferred terminology

Use:

> cost under a common higher-fidelity computational reference

and define:

> Decision regret is defined relative to the chosen computational reference and does not represent deviation from measured post-upgrade operation.

Avoid:

- true cost,
- true physics,
- ground truth, unless explicitly qualified as computational ground truth,
- empirically accurate dispatch,
- actual operating cost when the result is model-derived.

---

## 3.4 L4/L5 forward evaluation does not establish an optimisation bound

Evaluating the L1 schedule under station-resolved physics tells you the cost of **that fixed schedule** under richer physics.

It does **not** establish that a separately re-optimised L4/L5 schedule could not perform more than 1% better.

### Safe statement

> Adding station-level terms increases the forward-evaluated cost of the L1 schedule by less than 1% and produces no identified hydraulic feasibility violation. The corresponding re-optimised station-level dispatch was not evaluated.

This is still a useful result. It should be described as an **observed near-null effect on the evaluated baseline schedule**, not an upper bound on optimal improvement.

---

## 3.5 Decision-regret / heat-shortfall interpretation needs tightening

The current CP result is powerful but easily misread.

Existing post-processing indicates approximately:

| Quantity | CP |
|---|---:|
| Annual evaluated heat shortfall | ~1,159.5 MWh |
| Hours with shortfall | 8,760 h |
| Mean hourly shortfall | ~0.13 MW |
| Maximum hourly shortfall | ~0.14 MW |
| Regret under marginal replacement-price valuation | +46.1% |
| Regret under higher replacement-price sensitivity | +61.2% |
| Regret under unmet-demand/dump valuation | +831.7% |

The shortfall is therefore not a rare peak event. It is approximately a small persistent loss deficit.

### Critical distinction

If the forward evaluator does **not** physically redispatch all assets, recalculate storage states and check remaining capacity, do not say that the missing heat “is supplied by the marginal unit”.

Instead describe the procedure as:

**shortfall valuation under replacement-price assumptions.**

### Recommended wording

> The loss-blind CP schedule produces an evaluated annual heat shortfall of approximately 1.16 GWh, distributed across all 8,760 hours with a maximum hourly shortfall of approximately 0.14 MW. Because the forward evaluation does not independently re-optimise the asset dispatch, the shortfall is monetised under three replacement-price assumptions. Under the marginal replacement-cost assumption, the resulting reference-evaluated cost is 46.1% above the baseline.

### Table wording

Replace ambiguous **“Viol. = 0”** with separate information for:

- heat shortfall,
- velocity violations,
- differential-pressure violations,
- unresolved feasibility violations.

---

## 3.6 Solver objective and reported economic cost

This remains the most important methodological sensitivity check.

The schedules are generated by a solver objective that includes accounting terms that are not identical to the subsequently reported economic-cost metric. The manuscript reports a large residual between solver objective and economic cost, largely associated with:

- CHP CO2 accounting,
- thermal-storage cycling penalty.

The 2×2 loss/topology decomposition is arithmetically calculated from the economic-cost values, but that does **not by itself prove** that the schedules would be identical if the solver objective were aligned exactly with the reported economic cost.

## Strongly recommended targeted sensitivity run

Re-run only:

- CP,
- CP+L,
- ND0,
- L1,

with an optimisation objective that exactly matches the reported economic-cost convention.

### Desired result

If the loss/topology decomposition remains approximately unchanged, report this as a robustness check.

This is much stronger than arguing that post-processing terms “cancel”.

### Not necessary at this stage

- re-running all 135 synthetic networks,
- full-year nonlinear optimisation,
- adding distributed generation,
- adding meshed networks.

---

## 3.7 Nonlinear reference must be described as three distinct objects

The current wording risks conflating:

### A. Optimised PWL model
Contains the approximations used for tractability.

### B. Forward evaluator
Evaluates a fixed schedule under a common richer computational representation.

### C. Weekly nonlinear re-solve
Restores specific nonlinear/bilinear terms while fixing defined discrete decisions and re-optimising continuous variables.

Existing solver records give:

| Window | PWL/MILP cost | Nonlinear cost | Lower bound | Gap | Cost change |
|---|---:|---:|---:|---:|---:|
| Winter | €9,511.26 | €9,497.41 | €9,496.60 | 0.0085% | −0.146% |
| Autumn | €4,260.33 | €4,246.22 | €4,245.15 | 0.0252% | −0.331% |

### Important qualification

The weekly nonlinear reference restores the **bilinear temperature–decay coupling**, while the exponential decay factor itself remains represented by the common PWL approximation according to the existing audit.

Therefore avoid:

> native nonlinear physics

for the entire temperature propagation model.

### Better statement

> For the two feasible representative weeks, restoring the bilinear temperature–decay terms while retaining the common PWL representation of the exponential decay factor reduces cost by 0.15% and 0.33%, respectively.

Then add:

> This result is not established for the full annual operating range.

The full-year nonlinear problem did not produce a usable annual optimum and the summer case was infeasible under the fixed schedule. Do not generalise the two weekly values into a universal annual “linearisation error below 0.5%”.

---

# 4. Validation audit

## 4.1 Main issue

The validation section currently combines metrics with very different meanings:

- annual delivered-energy error,
- hourly measured-versus-modelled mismatch,
- flow MAPE,
- return-temperature error,
- quantities that cannot be validated because sensors are downstream of mixing valves,
- hydraulic cross-checks.

This should not be summarised as “the thermo-hydraulic model is validated”.

## 4.2 Particularly vulnerable metric

The table contains approximately:

- annual delivered-energy error: **1.23%**,
- source flow MAPE: **33.8%**,
- per-step “energy-balance closure”: **6.4% mean / 99% max**.

The label **energy-balance closure** is dangerous because an optimisation researcher will interpret it as a model balance residual. A MILP energy-balance constraint should normally close to numerical tolerance.

If this is actually a comparison between measured and modelled hourly energy quantities, rename it.

### Recommended term

> Hourly measured-to-modelled energy mismatch

### Recommended validation reporting

Separate:

1. **Annual energy mismatch**
2. **Mean absolute hourly energy mismatch**
3. **Energy-weighted relative error**
4. **MAPE only above a minimum-load threshold**
5. **Number of low-load hours**
6. **Flow error by load band**
7. **Absolute flow error by load band**

The current argument that relative error explodes at low load becomes much more convincing when an energy-weighted or load-weighted metric is added.

## 4.3 Temperature validation

The manuscript correctly identifies that consumer sensors downstream of three-way mixing valves cannot directly validate primary junction temperatures.

This is an important limitation and should remain explicit.

Do not claim:

> node-by-node temperature validation

when the instrumentation cannot provide primary-node reference temperatures.

Instead state precisely that:

- annual energy transport is supported by measurement,
- source/far-end/corridor quantities can be compared only where instrumentation permits,
- intermediate primary-network temperatures are not directly measurement-validatable with the available metering,
- the nonlinear hydraulic solver cross-check is an independent computational check, not an additional field measurement.

---

# 5. Technical equation and unit audit

The existing code audit indicates that the implementation is correct in the following cases, but the printed manuscript equations/units need correction.

## 5.1 Pumping cost

The manuscript currently creates the appearance that pump electricity is counted twice:

1. pump power enters the electrical balance and therefore electricity procurement,
2. a separate \(C^{pump}\) is added to the objective.

The implementation apparently pays pump electricity through grid import only and does not add an independent pump-cost term.

### Action

- Remove separate \(C^{pump}\) from the printed objective unless it represents a genuinely separate cost.
- Remove or redefine the nomenclature entry.
- Explain that pumping electricity enters the procurement cost through \(P_t^{pump}\).

No re-run is required if the implementation is already correct.

---

## 5.2 Storage self-discharge

The implementation uses geometric/exponential time-step scaling:

\[
(1-\alpha_s)^{\Delta t}
\]

but the printed equation is visually ambiguous and can be read as multiplication by \(\Delta t\).

### Action

Typeset the exponent unambiguously.

No re-run required if the implementation already uses the correct factor.

---

## 5.3 Pump-power units

\[
\dot m \Delta p / \rho
\]

produces watts when SI units are used.

If \(P^{pump}\) is reported in MW, show the factor:

\[
P_t^{pump}
=
\frac{1}{10^6 \eta^{pump}}
\sum_p
\frac{\dot m_{p,t}\Delta p_{p,t}}{\rho}.
\]

No re-run required if the code already contains the conversion and pump efficiency.

---

## 5.4 Emission units

If \(e\) is in kg/MWh, Eq. (12) produces kg CO2.

Either:

- label the emission variables as **kg**, retaining the /1000 conversion in the cost equation, or
- divide by 1000 in the emission equation and label the variables as **t**.

Use one convention everywhere.

---

## 5.5 Mass-flow conversion

If \(Q\) is in MW and \(c_p\) is in J/(kg K), a \(10^6\) conversion is required.

The implementation apparently uses \(c_p\) internally in MJ/(kg K), which is dimensionally consistent.

### Action

State the actual implemented unit convention explicitly in the manuscript.

---

# 6. Numerical consistency audit

All values should be generated from one authoritative results source before final compilation.

| Quantity | Current problem | Recommended authoritative presentation |
|---|---|---|
| Loss main-effect share | 95.8 / 95.9 / other intermediate values appear | Use one rounding rule, e.g. **95.8%** |
| Topology main effect | varying rounding | **4.7%** |
| Interaction | varying rounding | **−0.5%** |
| Held-out error | ~14% vs. 19% | Match the final table exactly |
| 30 km extrapolation error | “couple of points” vs. ~7 points | State **within 7 percentage points** if that is the final result |
| Maximum loss burden | older 81.2% vs. newer lower value | Recompute and use one final value everywhere |
| Hydraulic effect | “under 1%” vs. L1→L3 ≈1.4% | Distinguish trunk hydraulics from incremental station hydraulics |
| NL model status | “unsolved” vs. weekly solved cases | Distinguish annual NL from NL-week |
| Synthetic models | “same ladder” vs. subset of configurations actually solved | State exact models solved across all 135 networks |

## Required global check

Search manuscript + response letter + graphical abstract + highlights + Editorial Manager abstract/title for every headline number.

---

# 7. Claims that should be moderated

Avoid universal or rhetorically aggressive wording such as:

- “incompetent controller”,
- “never use a copperplate”,
- “true physics”,
- “exactly what matters”,
- “everything beyond loss visibility is negligible”,
- “the loss-dominance result carries no such qualification”,
- “parameter-free design rule” without regime qualification.

### Preferred style

> Within the tested radial, centrally supplied, fixed-capacity and hourly deterministic dispatch regime, the loss effect was robust across the industrial case and the 135 synthetic configurations.

For the loss number:

> parameter-free screening heuristic for the tested network family

is safer than a universal:

> parameter-free design rule.

---

# 8. Results-section structure

The current Results section is scientifically rich but somewhat fragmented, reflecting the reviewer-response history.

For a stronger *Applied Energy* narrative, consider reducing the number of small subsections and regrouping them into approximately:

1. **Validation and calibration**
2. **Loss–topology decomposition and aggregation sensitivity**
3. **Estimation bias, decision regret and shortfall valuation**
4. **Thermo-hydraulic fidelity, temperature and transport delay**
5. **Generalisation and screening heuristic**
6. **Implications, robustness and limitations**

This would make the revision read as one coherent paper rather than a sequence of experiments added comment-by-comment.

---

# 9. Response-letter audit

The response letter has a strong underlying strategy but is not yet ready to submit.

## Keep

- explicitly acknowledge where a reviewer was correct,
- say what changed,
- provide quantitative result,
- name the exact manuscript section/table/figure.

## Correct

### Reviewer 2.2
- use one final loss-share value,
- remove outdated maximum loss-burden values,
- do not say accounting terms “cancel” if schedule selection is based on the augmented solver objective.

### Reviewer 2.3
- distinguish forward evaluator from weekly nonlinear re-solve,
- state exactly which nonlinear terms were restored and which remain PWL,
- report weekly incumbent / lower bound / gap.

### Reviewer 2.4
- do not imply L4/L5 were independently re-optimised if they were only forward evaluated,
- distinguish measured validation from computational cross-check.

### Reviewer 2.5
- replace outdated “81 synthetic configurations” with the actual 135-case design,
- remove any false central/distributed-generation factorial claim.

### Reviewer 1.1
- do not say distributed generation was converted into an experimental factor,
- state that it remains outside scope.

### Reviewer 1.4
Avoid:

> invariant to the exact post-upgrade dispatch

This is too absolute. The comparative design reduces sensitivity to common component-model errors, but it does not mathematically guarantee invariance to post-upgrade dispatch.

### Remove drafting artefacts

Anything such as:

- “skeleton”,
- “fill after…”,
- internal rules,
- developer notes,
- temporary version nomenclature,
- worktree/build comments,

must be removed from the submitted response letter.

---

# 10. Literature review and scientific-source audit

# 10.1 Overall assessment

## Current quality: **good structure, incomplete state of the art**

The literature review has a clear conceptual structure:

1. spatial aggregation / topology,
2. thermo-hydraulic model fidelity,
3. comparison of objective values versus decision quality,
4. separate literature on generation technologies.

That structure is appropriate and should be retained.

The main weakness is **bibliographic completeness and precision of the novelty claims**.

Several highly relevant papers published in 2025 are absent. At least one of them comes very close to the paper's “decision-oriented evaluation of aggregation” argument. Therefore, some current statements of the form:

> “No prior study …”

are too absolute unless the missing literature is incorporated and the precise distinction is made explicit.

---

# 10.2 Missing literature that should be added

## A. **Vrain et al. (2025) — MUST ADD**

**Maxime Vrain et al.**  
*An aggregation method to model district heating networks in large-scale multi-energy simulations*  
**Energy 334 (2025), 137384**  
DOI: https://doi.org/10.1016/j.energy.2025.137384

### Why it matters

This is very close to your conceptual problem.

The paper:

- compares aggregated and detailed DHN models,
- explicitly develops an **aggregation-error metric**,
- injects the solution of the aggregated model into the unitary/detailed DHN models,
- measures whether the aggregated decision is admissible under the disaggregated representation,
- shows that similar objective values can hide different or infeasible hourly operation.

This is conceptually close to your argument that objective-value differences are insufficient.

### Consequence for your novelty claim

The current broad statement:

> none evaluates fidelity by the resulting decisions

is no longer safe.

Vrain et al. **do evaluate the admissibility of decisions produced by the aggregated model**.

However, your contribution remains distinct because Vrain et al. do not appear to:

- isolate thermal-loss visibility from spatial topology with a 2×2 control,
- re-cost the fixed dispatch under a common high-fidelity thermo-hydraulic reference,
- formulate the resulting monetary difference as decision regret,
- derive the same loss/topology decomposition.

### Recommended positioning

Add something like:

> Vrain et al. [new ref] move beyond objective-value comparison by injecting the schedule of an aggregated DHN representation into the underlying unitary models and quantifying its inadmissibility. Their metric therefore tests whether aggregation creates operationally impossible schedules. It does not, however, isolate thermal-loss visibility from spatial topology or re-cost a fixed schedule under a common thermo-hydraulic reference. The present study complements this line of work by quantifying the monetary consequence of the decision and by separating the loss and topology effects experimentally.

This acknowledgement **strengthens**, rather than weakens, your novelty.

---

## B. **Cassetti et al. (2025) — MUST ADD**

**Lorenzo Aurelio Cassetti et al.**  
*Impact of spatial resolution in modelling decarbonized district heating networks*  
**Energy 334 (2025), 137357**  
DOI: https://doi.org/10.1016/j.energy.2025.137357

### Why it matters

This paper explicitly studies:

- spatial resolution,
- district-heating optimisation,
- network topology,
- total system costs,
- computational time,
- model accuracy versus computational feasibility.

This is closer to your research question than the current analogy to spatial resolution in electricity-system models.

### Consequence

The current sentence that the “closest evidence comes from a neighbouring field” is too strong if this 2025 DH paper is not discussed.

### Recommended use

Cite it in the spatial-resolution paragraph and explain the difference:

- Cassetti et al. study the impact of spatial resolution on **large-scale DH expansion/design**,
- your paper studies **operational dispatch fidelity** and experimentally separates **loss visibility** from **routing/topology**.

This creates a very clean gap.

---

## C. **Friedrich et al. (2025) — MUST ADD or strongly recommended**

**Pascal Friedrich, Thanh Huynh, Stefan Niessen**  
*Optimizing district heating operations: Network modeling and its implications on system efficiency and operation*  
**Smart Energy 18 (2025), 100175**  
DOI: https://doi.org/10.1016/j.segy.2025.100175

### Why it matters

The paper compares different DHN modelling approaches for operational planning, including linear and nonlinear formulations, and validates operational schedules using a detailed Modelica simulation.

This is highly relevant to:

- your physical-fidelity ladder,
- the claim that simplified optimisation schedules should be checked under richer physics,
- Reviewer 2.3 / 2.4,
- the discussion of operational feasibility.

### Novelty implication

Do not say that the idea of validating a simplified optimisation schedule in a richer physical model is absent from the literature.

Your stronger distinction is:

- exact loss/topology decomposition,
- common-reference monetary regret,
- controlled single-phenomenon contrasts,
- synthetic transferability analysis.

---

## D. **Brown et al. (2022) — SHOULD ADD**

**Alastair Brown, Aoife Foley, David Laverty, Seán McLoone, Patrick Keatley**  
*Heating and cooling networks: A comprehensive review of modelling approaches to map future directions*  
**Energy 261 (2022), 125060**  
DOI: https://doi.org/10.1016/j.energy.2022.125060

### Why it matters

This is a broad review of:

- heating/cooling network modelling methods,
- network components,
- optimisation approaches,
- software tools,
- computational complexity and scalability.

It is more suitable than individual framework papers for supporting general statements about the model-fidelity / tractability trade-off.

Use it early in §1.1.

---

## E. **Sporleder et al. (2022) — SHOULD ADD**

**Maximilian Sporleder, Michael Rath, Mario Ragwitz**  
*Design optimization of district heating systems: A review*  
**Frontiers in Energy Research 10 (2022), 971912**  
DOI: https://doi.org/10.3389/fenrg.2022.971912

### Why it matters

This systematic review explicitly finds that:

- mathematical programming is widespread in DH optimisation,
- most analysed optimisation models are linear,
- spatial discretisation increases model complexity,
- reducing computational effort and assessing the resulting uncertainty are open issues.

### Best use

This is a better source for broad claims such as:

> MILP/linear mathematical programming is widely used in district-heating optimisation.

It is stronger evidence for a field-level statement than one single operational-optimisation paper.

---

## F. **Recent transport-delay paper (2025) — SHOULD ADD**

*A quasi-dynamic model and comprehensive simulation study of district heating networks considering temperature delay*  
**Energy 318 (2025), 134855**  
DOI: https://doi.org/10.1016/j.energy.2025.134855

### Why it matters

This is recent, explicitly focuses on temperature transport delay and includes measured validation.

It is a stronger contemporary source for the relevance of delay than relying only on older Modelica work.

---

## G. Further optional contemporary context

### Boussaid et al. (2024)
*Enabling fast prediction of district heating networks transients via a physics-guided graph neural network*  
**Applied Energy 370 (2024), 123634**  
DOI: https://doi.org/10.1016/j.apenergy.2024.123634

Useful for the model-fidelity versus computational-cost motivation and reduced-order/surrogate modelling context.

### HeatNetSim (2024)
An open-source simulation tool for dynamic and bidirectional heating/cooling networks.

Useful if the Introduction wants a modern modelling-tool perspective, but not essential to the central gap.

---

# 10.3 Existing citation-to-claim pairings that require rechecking

## [14] Bünning et al. — **HIGH RISK**

Current manuscript claim:

> Bünning et al. report that a zone-based representation captures 85–95% of dynamic temperature variation.

The cited paper is:

> *Bidirectional low temperature district energy systems with agent-based control: Performance comparison and operation optimization.*

From the accessible bibliographic/abstract material, this paper is primarily about:

- bidirectional low-temperature networks,
- agent-based control,
- system-performance comparison,
- operation optimisation.

I could not substantiate the specific **zone aggregation / 85–95% dynamic temperature variation** claim from the accessible source material.

### Action

Verify the full paper manually.

If the exact number is not present, **replace the citation and/or claim**.

This is not a minor stylistic issue. A reviewer can easily check a numerical literature claim.

---

## [19] Leitner et al. — **HIGH RISK**

Current manuscript claim:

> Leitner et al. compare copperplate and full-graph representations of an Austrian network and report cost differences of 3–8%.

The cited paper is:

> *A method for technical assessment of power-to-heat use cases to couple local district heating and electrical distribution grids*, Energy 182 (2019) 729–738.

The accessible full-text material describes:

- a dynamic thermo-hydraulic DH model,
- a quasi-static electric-network model,
- co-simulation,
- power-to-heat use cases,
- technical assessment of coupled heat/electric networks.

I could not verify from the accessible text that it performs the claimed controlled **copperplate-versus-full-graph cost comparison with 3–8% cost differences**.

### Action

This citation should be manually verified against the full article.

If the claim is not actually in the paper:

- remove it,
- identify the intended source,
- or replace the sentence with Cassetti et al. (2025), Vrain et al. (2025), Larsen et al. (2004), and another genuinely matching optimisation comparison.

---

## [16] Giraud et al. — **HIGH RISK / overextended claim**

Current manuscript uses Giraud et al. to support:

> full-graph models remain tractable to roughly a hundred nodes over hourly annual horizons

The cited 2015 Modelica-library paper demonstrates a dynamic simulation library and an example network with roughly **26 consumers**, not an obvious annual MILP/optimisation benchmark of ~100 nodes × 8760 h.

### Action

Do not use this source for the specific annual optimisation tractability claim unless the full paper explicitly demonstrates it.

Either:

- remove the numerical “roughly a hundred nodes” statement,
- or replace it with a paper that directly reports annual optimisation scale and solve time.

---

## [2] Perea-Moreno et al. (2026) — **weak support for the exact claim**

The bibliometric/worldwide-scientific-landscape paper may support the general growth of DH research, but it is not the strongest source for:

> operational optimisation relies increasingly on mathematical programming.

Use a systematic optimisation review such as Sporleder et al. (2022), plus a recent operational optimisation paper.

---

## [7]–[11] Framework papers — **overgeneralised collective statement**

Current claim:

> oemof, PyPSA, FINE, Calliope and urbs represent the thermal network in their default configuration at CP level.

This is a broad software-behaviour claim.

Individual framework papers do not necessarily support one identical “default thermal-network fidelity” statement across all five tools, and capabilities may have evolved since the original publications.

### Safer wording

> General-purpose energy-system frameworks such as oemof, PyPSA, FINE, Calliope and urbs are frequently used with aggregated or component-based thermal-network representations; detailed thermo-hydraulic coupling typically requires additional or external formulations.

If you want to retain a precise “default configuration” statement, verify the current documentation/version of each framework and cite accordingly.

---

## [27] Ommen et al. / MIQCP wording — **check precision**

If the sentence specifically introduces **MIQCP formulations**, the source should itself be a MIQCP formulation.

Hering et al. is the stronger direct citation.

Ommen et al. is useful for the broader linear/MILP/nonlinear dispatch-method comparison.

---

# 10.4 Novelty claims after the external literature check

## Current claim that is too broad

> None of the literature evaluates fidelity by the decisions produced.

### Why it is no longer safe

Vrain et al. (2025) explicitly inject the aggregated optimisation solution into disaggregated models and quantify its inadmissibility.

Friedrich et al. (2025) evaluate operational schedules with a detailed Modelica simulation.

### Stronger and more defensible novelty claim

> Prior work has begun to evaluate whether simplified or aggregated district-heating schedules remain admissible under more detailed representations, but the monetary consequence of committing to a simplified schedule remains insufficiently separated from the model’s own objective-value bias. In addition, existing comparisons do not isolate the visibility of thermal losses from the spatial routing representation. This study addresses these two issues through a common-reference regret evaluation and an exact 2×2 loss/topology decomposition.

This is both more current and more convincing.

---

# 10.5 “Linearisation error has not been published” should be narrowed

Current broad statement:

> The magnitude of that linearisation error in a district-heating dispatch setting has not been published.

This is risky after the 2025 literature, particularly Friedrich et al. and other nonlinear operational-planning studies.

### Better formulation

> We found no prior district-heating dispatch study that isolates the cost effect of the present temperature-propagation linearisation while holding transport delay and the remaining model structure fixed.

This precisely describes what your experiment contributes and is much easier to defend.

---

# 10.6 “Closest evidence comes from electricity systems” should be revised

The current Introduction uses Frysztacki et al. as the closest quantitative evidence.

That analogy is useful, but after 2025 it is no longer the closest evidence overall.

### Better structure

1. Cite **Cassetti et al. (2025)** as recent DH-specific evidence that spatial resolution affects topology, costs and computation in expansion modelling.
2. Cite **Vrain et al. (2025)** as evidence that aggregation can create inadmissible operational decisions even when aggregate outputs look plausible.
3. Then cite **Frysztacki et al. (2021)** as a cross-sector analogy showing how strongly spatial resolution can matter in electricity-system modelling.

This moves the literature review from “electricity analogy” to a genuinely current DH state of the art.

---

# 10.7 Recommended revised Table 1

The current column **“Evaluates decisions”** is now too broad because Vrain et al. do evaluate decision admissibility.

Use more precise columns:

| Study | Varies spatial/network fidelity | Separates loss from topology | Tests simplified decision in detailed/reference model | Re-costs fixed decision in common reference | Reports monetary regret |
|---|---:|---:|---:|---:|---:|
| Larsen et al. (2004) | ✓ | × | × | × | × |
| Wirtz et al. (2021) | ✓ | × | × | × | × |
| Vrain et al. (2025) | ✓ | × | ✓ | × / limited | × |
| Cassetti et al. (2025) | ✓ | × | × | × | × |
| Friedrich et al. (2025) | ✓ physics | × | ✓ | not your metric | × |
| This study | ✓ | ✓ | ✓ | ✓ | ✓ |

Before publication, verify the exact cell assignment from each full paper.

This table would communicate the novelty much more credibly than excluding the closest recent studies.

---

# 10.8 Recommended literature-review architecture

## Paragraph 1 — Scope and modelling trade-off
- DH operational optimisation,
- model fidelity vs. tractability,
- recent reviews: Brown et al.; Sporleder et al.

## Paragraph 2 — Spatial/network aggregation
- Larsen 2004,
- Falay 2020,
- Cassetti 2025,
- Vrain 2025.

## Paragraph 3 — Full network / thermo-hydraulic modelling
- van der Heijde,
- Hering,
- Friedrich 2025,
- recent delay paper 2025,
- Maldonado 2024 validation.

## Paragraph 4 — Decision-oriented model assessment
- Vrain: admissibility of aggregated decisions,
- Friedrich: detailed simulation of optimised schedules,
- Quaggiotto/Jansen: MPC / detailed representation,
- explain what remains missing: **common-reference monetary regret + exact loss/topology decomposition**.

## Paragraph 5 — Research gap
Make only the two claims you can defend strongly:

1. **Existing spatial-resolution comparisons do not isolate loss visibility from routing/topology.**
2. **Existing decision/feasibility assessments do not quantify the same common-reference monetary regret while separating estimation bias from decision consequence.**

This is a stronger novelty story than claiming that nobody has ever evaluated decisions.

---

# 10.9 Literature-review verdict

| Criterion | Current | After recommended edits |
|---|---:|---:|
| Conceptual structure | 8.5/10 | 9/10 |
| Recency | 6/10 | 9/10 |
| Coverage of closest literature | 6/10 | 9/10 |
| Accuracy of novelty positioning | 6.5/10 | 9/10 |
| Citation-to-claim precision | 6.5/10 | 9/10 |
| Suitability for Applied Energy | 7/10 | 9/10 |

The literature review does **not** need to become much longer. It needs to become **more current and more selective**.

Adding approximately 4–6 highly relevant sources while removing or correcting weakly matched citations will improve it more than adding another page of generic DH literature.

---

# 11. Reviewer-by-reviewer status after this audit

## Reviewer 1

### R1.1 Scope too broad
**Mostly addressed.**  
Remaining risk: universal wording and the erroneous distributed-generation statement.

### R1.2 “Accuracy” not empirically validated
**Conceptually addressed.**  
Remaining risk: “true cost/true physics” wording.

### R1.3 Delay and linearisation confounded
**Substantially addressed.**  
Need exact weekly nonlinear-reference description and no annual extrapolation.

### R1.4 No post-upgrade validation
**Addressed as a limitation.**  
Do not imply that common modelling assumptions make the conclusion invariant to actual post-upgrade dispatch.

### R1.5 Assumptions suppress network physics
**Addressed reasonably.**  
Keep sensitivity analyses explicitly labelled as forward sensitivities, not complete co-optimised operation.

### R1.6 Clustering arbitrariness
**Strongly addressed.**

### R1.7 Deterministic hourly model
**Addressed as a limitation.**

---

## Reviewer 2

### R2.1 Novelty
**Much stronger, but the Literature Review must now acknowledge Vrain 2025, Cassetti 2025 and Friedrich 2025.**

The novelty should be framed as:

- controlled 2×2 loss/topology decomposition,
- monetary common-reference regret,
- transferability analysis,
- not new thermo-hydraulic component equations.

### R2.2 Loss/topology confound
**Strongly addressed.**

This is now one of the best parts of the paper.

### R2.3 Linearisation
**Addressable with existing results.**

Do not overgeneralise beyond the two feasible weekly nonlinear re-solves.

### R2.4 Validation
**Improved but remains the most sensitive reviewer point.**

The validation presentation must be exceptionally precise.

### R2.5 Generality
**Much improved by 135 networks.**

Correct the false distributed-generation factor and moderate screening-rule wording.

---

# 12. Senior-editor requirements

## Already addressed or mostly addressed

- Abstract merged into one paragraph.
- Conclusion no longer uses subheadings.
- Reference lumping appears reduced.

## Final checks required

- Search entire manuscript for grouped references such as `[1–3]` and retain only cases that are genuinely necessary.
- Ensure final article structure resembles current *Applied Energy* research articles.
- Check Highlights: 3–5 bullets, maximum 85 characters including spaces.
- Ensure the exact revised title and abstract are copied into Editorial Manager.
- Upload editable source files and production-quality figure sources.
- Ensure clean and marked-up manuscripts are generated from the **same authoritative source version**.

---

# 13. What requires new simulations?

| Item | New optimisation required? | Priority |
|---|---:|---:|
| CP / CP+L / ND0 / L1 objective-alignment sensitivity | **Recommended** | High |
| All 135 synthetic networks | No | — |
| Full-year nonlinear solve | No | — |
| L4/L5 independent optimisation | No, if claims are moderated | Optional |
| Distributed generation | No | Future work |
| Meshed networks | No | Future work |
| New field measurements | No for this revision | Future work |
| Winter/autumn nonlinear re-solves | No if logs are complete | — |
| Shortfall analysis | No, post-processing sufficient | High text priority |
| Validation metrics | No optimisation; recalculate/report appropriately | High |

---

# 14. Prioritised action list

## P0 — must be completed before resubmission

- [ ] Establish one final model taxonomy throughout the manuscript.
- [ ] Remove the false distributed-generation factorial claim.
- [ ] Remove “true cost”, “true physics” and equivalent wording.
- [ ] Correct L4/L5 forward-evaluation interpretation.
- [ ] Define regret shortfall as valuation unless physical redispatch is actually performed.
- [ ] Separate annual forward evaluator and weekly nonlinear re-solves.
- [ ] Correct validation terminology and weighted-error reporting.
- [ ] Correct printed equations/units.
- [ ] Reconcile every headline number from a single results source.
- [ ] Synchronise clean PDF, markup PDF, LaTeX source and response letter.
- [ ] Add Vrain et al. (2025).
- [ ] Add Cassetti et al. (2025).
- [ ] Add Friedrich et al. (2025) or explicitly justify its exclusion.
- [ ] Recheck Bünning [14], Leitner [19], and Giraud [16] claims against full papers.
- [ ] Rewrite novelty statements after including the 2025 literature.
- [ ] Update Table 1 so “decision evaluation” is defined precisely.

## P1 — strongly recommended

- [ ] Run the four-model objective-alignment sensitivity.
- [ ] Add Brown et al. (2022) review.
- [ ] Add Sporleder et al. (2022) systematic review.
- [ ] Add a recent 2025 transport-delay paper.
- [ ] Consolidate Results into fewer scientific themes.
- [ ] Add a concise techno-economic input/source table or clearly point to Supplementary Material.
- [ ] Replace strong universal statements with regime-qualified conclusions.

## P2 — optional / future work

- [ ] Independently optimise station-resolved L4/L5.
- [ ] Test distributed generation.
- [ ] Test meshed/ring networks.
- [ ] Add additional nonlinear seasonal windows.
- [ ] Add stochastic/sub-hourly operation.
- [ ] Validate post-upgrade dispatch against new field data.

---

# 15. Final assessment

## Scientific contribution

The paper is now much stronger than a simple “five model levels” comparison.

The most defensible contribution is:

1. **an exact controlled decomposition of loss visibility and spatial topology,**
2. **a distinction between objective-value estimation bias and the consequence of using the simplified model’s decision,**
3. **a transferability test over a balanced synthetic network family,**
4. **a targeted examination of how much additional thermo-hydraulic detail changes the evaluated schedule within the tested regime.**

## Biggest remaining threat

The biggest threat is not Reviewer 2’s original request anymore.

It is that a second-round reviewer notices:

- recent close literature omitted,
- a literature claim assigned to the wrong source,
- a forward-evaluated level described as optimised,
- a computational reference described as “truth”,
- or an overly broad novelty statement contradicted by a 2025 paper.

These are all avoidable.

## Resubmission recommendation

**Do not submit the current clean PDF unchanged.**

After the P0 items above, and preferably the four-model objective-alignment sensitivity, I would consider the manuscript **ready for a high-quality Applied Energy resubmission**.

The correct strategy now is not to add many more model features. It is to make the manuscript maximally precise about:

- what was optimised,
- what was only evaluated,
- what was measured,
- what was only computationally cross-checked,
- what the literature already did,
- and exactly what remains new in this study.

---

# 16. Externally checked literature — key records

The following sources were externally checked during this audit and are especially relevant to the revised Literature Review.

1. Vrain, M. et al. (2025). *An aggregation method to model district heating networks in large-scale multi-energy simulations*. **Energy, 334**, 137384.  
   https://doi.org/10.1016/j.energy.2025.137384

2. Cassetti, L. A. et al. (2025). *Impact of spatial resolution in modelling decarbonized district heating networks*. **Energy, 334**, 137357.  
   https://doi.org/10.1016/j.energy.2025.137357

3. Friedrich, P., Huynh, T., Niessen, S. (2025). *Optimizing district heating operations: Network modeling and its implications on system efficiency and operation*. **Smart Energy, 18**, 100175.  
   https://doi.org/10.1016/j.segy.2025.100175

4. Brown, A., Foley, A., Laverty, D., McLoone, S., Keatley, P. (2022). *Heating and cooling networks: A comprehensive review of modelling approaches to map future directions*. **Energy, 261**, 125060.  
   https://doi.org/10.1016/j.energy.2022.125060

5. Sporleder, M., Rath, M., Ragwitz, M. (2022). *Design optimization of district heating systems: A review*. **Frontiers in Energy Research, 10**, 971912.  
   https://doi.org/10.3389/fenrg.2022.971912

6. Maldonado, D. et al. (2024). *Validation of a calibrated steady-state heat network model using measured data*. **Applied Thermal Engineering, 248**, 123267.  
   https://doi.org/10.1016/j.applthermaleng.2024.123267

7. *A quasi-dynamic model and comprehensive simulation study of district heating networks considering temperature delay* (2025). **Energy, 318**, 134855.  
   https://doi.org/10.1016/j.energy.2025.134855

8. Boussaid, T. et al. (2024). *Enabling fast prediction of district heating networks transients via a physics-guided graph neural network*. **Applied Energy, 370**, 123634.  
   https://doi.org/10.1016/j.apenergy.2024.123634

9. Larsen, H. V., Bøhm, B., Wigbels, M. (2004). *A comparison of aggregated models for simulation and operational optimisation of district heating networks*. **Energy Conversion and Management, 45**, 1119–1139.  
   https://doi.org/10.1016/j.enconman.2003.08.006

10. Leitner, B., Widl, E., Gawlik, W., Hofmann, R. (2019). *A method for technical assessment of power-to-heat use cases to couple local district heating and electrical distribution grids*. **Energy, 182**, 729–738.  
    https://doi.org/10.1016/j.energy.2019.06.016  
    **Audit note:** recheck before using it for a “copperplate vs. full-graph 3–8% cost difference” claim.

11. Bünning, F., Wetter, M., Fuchs, M., Müller, D. (2018). *Bidirectional low temperature district energy systems with agent-based control: Performance comparison and operation optimization*. **Applied Energy, 209**, 502–515.  
    https://doi.org/10.1016/j.apenergy.2017.10.072  
    **Audit note:** recheck before using it for a “zone aggregation captures 85–95% of dynamic temperature variation” claim.

12. Giraud, L., Bavière, R., Vallée, M., Paulus, C. (2015). *Presentation, validation and application of the DistrictHeating Modelica library*. Proceedings of the 11th International Modelica Conference, 79–88.  
    https://doi.org/10.3384/ecp1511879  
    **Audit note:** the accessible paper material does not substantiate an annual ~100-node optimisation-tractability claim.

---

**End of audit**
