# Response to the Editor and Reviewers

## Opening statement

We thank the editor and both reviewers for identifying substantive weaknesses in the original manuscript. In particular, Reviewer 2 was correct that our principal comparison confounded network topology with heat loss. The requested calibrated-loss control changes our main conclusion: **within the tested central-source, radial networks, heat loss—not routing topology—accounts for nearly all of the copperplate-to-node-resolved cost gap**. We have revised the title, abstract, and conclusions accordingly.

We made three main changes.

1. **Decision evaluation.** We now evaluate every model-derived schedule under the same nonlinear forward model, restoring the native heat-loss and friction relations used in this study. Because the full-year forward model is not itself globally re-optimised, we report a signed *forward-evaluated decision-cost difference*, not mathematical regret. The evaluation also identifies schedules for which no feasible native-physics recourse is found under the stated fixed decisions.

2. **Experimental separation.** We added the requested copperplate with calibrated aggregate losses (`CP+L`) and promoted the existing routing-without-loss formulation (`ND⁰`) into the primary analysis. Together with the copperplate (`CP`) and node-resolved baseline (`L1`), these form a crossed design that separates loss, topology, and their interaction.

3. **Evidence and scope.** We reconstructed 174 transmission stations and their service laterals from the network DXF plans, incorporated manufacturer pump characteristics, cross-checked the hydraulic implementation against pandapipes, and added station-resolved hydraulic levels. We also replaced the filtered synthetic study with a balanced 135-cell factorial covering node count, trunk length, demand heterogeneity, and storage size. Generation remains central in this factorial; distributed generation and looped networks are now stated explicitly as outside the tested scope.

## Nomenclature bridge: original submission to revision

The level names were reorganised in the revision. To avoid ambiguity, the responses below use semantic labels wherever possible.

| Original label | Original meaning | Revised label |
|---|---|---|
| `L1` | Copperplate, no loss | `CP` |
| `L2` | Seven aggregated zones | `ZN` |
| `L1_topo` | Routing without loss; synthetic auxiliary | `ND⁰` |
| `L3` | 15 nodes plus trunk loss | `L1` baseline |
| `L3⁺` | Pressure, temperature, and delay bundled | Split into `L2` and `L3` |
| Not present | Station count/laterals and dynamic station pressure | `L4` and `L5` |
| `L3ᴺᴸ` | Native nonlinear physics with delay | Split into `L6` and `NL` |

Thus, Reviewer 1’s reference to the 13% difference between original `L1` and `L3` corresponds to the revised `CP→L1` comparison. The recalculated copperplate underestimation is 11.8% on the optimisation objective and 15.1% on the operator-accounting cost.

# Reviewer 2

## R2.1 — Novelty and significance

> **Condensed comment:** The original manuscript appears primarily to be a comparative application, and its methodological novelty and broader significance are unclear.

**Response:** We agree that the original manuscript did not establish a contribution beyond a comparative case study. We have repositioned the paper accordingly and now identify four specific contributions.

First, every schedule is evaluated under a common nonlinear forward model. We define the signed decision-cost difference as

\[
\Delta C_F(m)=C_F(s_m)-C_F(s_{\mathrm{ref}}),
\]

where \(s_m\) is the schedule selected by formulation \(m\). Because \(s_{\mathrm{ref}}\) is not guaranteed to minimise \(C_F\) globally over the full year, negative values are possible and we no longer label this quantity “regret.” We cite the Value of the Stochastic Solution literature and present our contribution as transferring a decision-focused comparison from the uncertainty axis to the model-resolution axis.

Second, the new `CP+L` control and the existing `ND⁰` formulation now form a crossed experiment that separates the economic effects of loss, topology, and their interaction.

Third, the new `L4` and `L5` levels test whether station-resolved hydraulics alter dispatch. Their parameters are grounded in manufacturer pump data and a reconstruction of all 174 transmission stations and service laterals.

Fourth, we introduce a zero-fitted-coefficient screening approximation,

\[
\hat b=\frac{\lambda}{1+\lambda},
\qquad
\lambda=
\frac{\text{estimated annual network loss}}
{\text{annual delivered demand}}.
\]

Here, \(\lambda\) is estimated before dispatch optimisation from the pipe inventory, assumed operating temperatures, and annual demand; it is not obtained from measured annual loss. The relation explains \(R^2=0.87\) across the reported 136-case evaluation set. We now describe it as a **screening approximation**, not an exact economic identity: it indicates when loss is likely to make a copperplate inadequate, but it does not provide the accurate network-specific loss adder used in the ex-post `CP+L` control.

**Location:** Revised §§1.2, 2.3–2.4, 3.3, and 3.9.

## R2.2 — Confounding of topology and heat loss

> **Condensed comment:** The principal comparison confounds network topology with heat loss. A copperplate formulation with calibrated aggregate losses is needed to separate the two effects.

**Response:** **The reviewer is correct, and this experiment changed our principal conclusion.** We implemented the requested `CP+L` control and crossed it with `CP`, `ND⁰`, and `L1`. The resulting loss, topology, and interaction decomposition is an exact additive identity by construction; it closes to €0 before rounding. All four Memmingen formulations were solved to an optimality gap of at most 0.01%.

Using defensible pipe \(U\)-values without loss inflation, the Memmingen cost gap decomposes as follows:

- heat loss: **95.9%**;
- topology: **4.7%**;
- interaction: **−0.5%**.

The displayed values sum to 100.1% because of rounding. Across the balanced 135-network factorial, all formulations were solved to gaps of at most 0.1%. Heat loss accounts for a median 100.0% of the copperplate-to-node-resolved gap. When normalised by annual cost, the topology term remains within ±0.6 percentage points for all networks with trunk lengths of at least 5 km and has a magnitude no greater than 2.4 points for the 1 km networks; the entire cost gap in those short networks is below 6% of annual cost.

We also tested whether `CP+L` could replace spatial modelling. For Memmingen, a network-specific ex-post adder gives an estimation bias of −0.6% and a signed forward-evaluated decision-cost difference of −0.5%. However, this accuracy does not transfer. The loss burden spans 3.2–81.2% of annual cost across the factorial. When an adder is frozen and transferred between networks, even the most transferable choice has a mean absolute error of 23.5 percentage points and a maximum error of 40.1 points.

We therefore distinguish two claims:

- An **ex-post calibrated** aggregate adder can reproduce a particular network.
- The pre-optimisation \(\lambda\)-rule is only a screening approximation. When it indicates material losses and no local calibration is available, a spatial model that computes losses endogenously is the defensible choice.

The revised conclusion is consequently conditional: spatial resolution matters primarily because it computes heterogeneous network loss, whereas routing topology itself has little economic effect within the tested central-source, radial systems.

### Optimisation objective and operator-accounting cost

We now report and label both cost definitions rather than assuming that their differences cancel.

The solver objective includes gross CO₂ accounting and a thermal-storage cycling penalty. The separately reported operator-accounting cost comprises energy purchases minus sales, fuel, CO₂ under the selected cogeneration self-use allocation, dumping, and demand charges. It excludes the cycling penalty and credits the CO₂ associated with exported CHP electricity.

On Memmingen, these definitions differ by approximately €80–87 thousand, or 38–41%:

- exported-electricity CO₂ allocation: approximately €55–58 thousand;
- storage-cycling penalty: approximately €24–26 thousand.

These terms can influence dispatch, so we no longer describe them as cancelling automatically. Optimisation bounds and optimality claims are reported on the solver objective, while operator-accounting results are reported in parallel. The revised table shows that the central ranking and decomposition conclusion are unchanged under either measure: the copperplate underestimation is 11.8% on the solver objective and 15.1% on operator-accounting cost.

**Location:** Revised §§2.3, 2.5, and 3.2; decomposition table; Fig. F6.

## R2.3 — Rigour of the linearisation assessment

> **Condensed comment:** The original comparison did not isolate linearisation from transport delay, did not provide adequate optimisation bounds, and lacked a nonlinear reference.

**Response:** We accept all three criticisms.

First, transport delay is now introduced only at `L6`, rather than being bundled with the piecewise-linear physics. Every preceding ladder transition changes one phenomenon.

Second, every mixed-integer comparison now reports the incumbent objective, rigorous bound, and optimality gap. We removed the phrase “statistically meaningful bound” and make no substantive claim for effects smaller than the attained optimisation tolerance.

Third, the common forward model restores native exponential heat propagation and computed-friction hydraulics. This is a model-to-model nonlinear reference for the represented physics, not a claim of complete empirical validation. Annual network loss is not independently metered; the available empirical checks concern delivered energy, aggregate flow, and the source-to-far-end corridor described under R2.4.

We also solved native-physics continuous re-optimisations on representative windows while holding the operational schedule from the piecewise-linear model fixed. The resulting non-convex QCPs reached certified gaps of at most 0.03% for one winter and one autumn week. Relative to the piecewise-linear recourse under the same fixed schedule, the cost changed by −0.15% and −0.33%. These results indicate that the piecewise-linear approximation is slightly conservative on those two windows; they do not establish the sign or magnitude of the full-year global error.

The corresponding full-year QCP did not produce an incumbent within the solver budget. For a low-load summer week, no feasible native-physics recourse was found under the fixed piecewise-linear schedule. We report this narrowly as incompatibility under the stated fixing, not as proof that no alternative summer schedule is physically feasible.

Temperature propagation remains part of the nonlinear evaluator rather than a separate mixed-integer level. Freeing the node temperatures creates a non-convex formulation and, without a hydraulic penalty, a degenerate optimisation response in which temperatures are reduced uniformly rather than reproducing physical decay. A forward ablation attributes approximately 2% of network loss to this temperature-propagation effect.

**Location:** Revised §§2.1, 2.6, and 3.8; linearisation table; Fig. F13.

## R2.4 — Validation and pumping-energy magnitude

> **Condensed comment:** The hydraulic and thermal validation is insufficient, and the very low pumping-energy estimate appears implausible.

**Response:** We agree that the original evidence did not justify describing the pumping result as empirically validated. The revision now distinguishes component grounding, implementation verification, and validation against operational measurements.

### Hydraulic reconstruction and verification

We reconstructed the demand side down to 174 individual transmission stations and their service laterals using the network DXF plans. The calculated station-plus-lateral operating requirement is approximately 3 kW, compared with 110.8 kW of installed Wilo pumping capacity. This comparison establishes that the calculated duty lies within the installed operating envelope; installed capacity alone does not validate electricity consumption.

We independently reproduced the trunk hydraulic calculation in pandapipes. The pressure results agree within 0.007 bar. We now label this as cross-solver implementation verification, not empirical validation.

The revised hierarchy also includes:

- `L4`: station count and explicit service laterals;
- `L5`: dynamic, flow-dependent station pressure drop.

At these levels, hydraulic detail changes annual dispatch cost by less than 1%, while the forward-evaluated decision-cost difference remains within the reported numerical tolerance. We also restrict the pipe-loss multiplier to a defensible range and represent residual last-mile loss through an explicit service-lateral term introduced only at `L4`.

No direct pump-electricity measurement is available. The revised claim is therefore that the low pumping requirement is physically plausible and independently cross-verified, not directly measurement-validated.

### Corrections identified during the revision

We made two corrections and regenerated the affected results.

1. The previously reported 6.4% mean energy-balance residual was caused by an export error, not by the optimisation model. Electrode-boiler heat—approximately 1,749 MWh per year—was written to a legacy output column and read back as zero, creating an apparent hourly gap of up to 5 MW. After correcting the export, the reported per-step energy balance closes to machine precision.

2. A piecewise-linear pump-segment constraint allowed an unselected segment to carry flow. We corrected the constraint and re-solved the pressure levels. Annual dispatch cost changes by no more than 0.03%, because pumping on this network is dominated by the linear station differential-pressure term rather than trunk-friction segmentation.

### Thermal and flow evidence

Consumer temperature sensors are located downstream of three-way mixing valves. Their readings are typically 5–15°C below the corresponding primary-junction temperatures and therefore cannot directly validate intermediate node temperatures. At the network far end, the mixing valve operates close to fully open; we consequently limit the spatial comparison to the 2.1 km source-to-far-end corridor \(j_1\rightarrow j_{15}\). Even there, point-temperature agreement remains sensitive to network flow, which the billing data do not uniquely determine.

We therefore report three distinct checks without treating any as stronger than the data permit:

- The annual delivered-energy reconstruction agrees with billing data within approximately 1.2%. This is an energy-consistency check; network loss is the modelled difference between generated and delivered heat and is not independently metered.
- Aggregate flow MAPE is approximately 34%, driven mainly by low-load hours. Below 25% of peak demand—60% of all hours—MAPE is 46%, while absolute error remains approximately 12–13 m³/h. At 50–75% of peak demand, MAPE falls to 12.9%. Above 75% of peak, it is 23%, but that band contains only 56 hours.
- First-difference comparisons, which are less sensitive to fixed valve offsets, give correlations of \(r=0.91\) for flow level and \(r=0.80\) for day-to-day flow change; the corresponding demand correlations are 0.93 and 0.89.

No defensible held-out physical node can be constructed because every consumer temperature sensor is downstream of a mixing valve. We state this limitation directly. The synthetic held-out experiment in R2.5 provides model-based out-of-sample evidence, but it is not presented as a substitute for independent field validation.

**Location:** Revised §§2.6, 3.1, and 3.6; Fig. F11 and the source-to-far-end corridor figure.

## R2.5 — Generality

> **Condensed comment:** The synthetic study is filtered and unbalanced, uses a taxonomy inconsistent with the case study, and does not establish out-of-sample generality.

**Response:** We accept all three points. We replaced the original 81-configuration design, of which only 36 cases had been retained, with a balanced 135-cell factorial:

- three node counts;
- five trunk lengths;
- three demand-heterogeneity levels;
- three storage sizes.

The previous infeasibilities resulted from undersized generation capacity. We diagnosed them and adopted a documented sizing convention, report its influence, and solve all 135 cells. Generation is central in every factorial case; generation topology is not claimed as an experimental factor.

The Memmingen and synthetic studies now use the same level definitions, and the previous physics-scope mapping table has been removed. The statistical analysis comprises variance decomposition and regression with confidence intervals over the balanced design. Separate held-out networks have pipe lengths beyond the fitted range, and we report the resulting degradation rather than extrapolating the fitted thresholds without qualification. All selection thresholds are now described as observations within the tested regimes.

**Location:** Revised §§2.9 and 3.9.

# Reviewer 1

## R1.1 — Scope of the “dominates” claim

> **Condensed comment:** The claim that one modelling feature “dominates” is too broad given the single-network case, radial topology, central generation, fixed capacities, and fixed heating curve.

**Response:** **The reviewer is correct that the original wording exceeded the evidence.** We removed “dominates” from the title and restrict the conclusion to the tested central-source, radial, unidirectional systems.

The balanced synthetic factorial varies node count, pipe length, demand heterogeneity, and storage size. It shows that the loss contribution remains large across those factors, but it does not test distributed generation or looped topology. The manuscript no longer states otherwise.

The remaining restrictions—central generation, radial topology, unidirectional flow, fixed capacities, and a fixed heating curve—are now explicit scope conditions. A forward supply-temperature sensitivity shows that relaxing the fixed-temperature assumption can make hydraulics binding; the revised conclusion is therefore conditional on the operating-temperature policy.

We also state precisely why distributed and looped systems were not added. Multiple sources on a radial graph require a revised pressure treatment in which one source defines the reference head and the remaining source heads can float above their setpoints. The present formulation pins all source heads and can therefore suppress a secondary source. Looped networks additionally require signed-flow variables and direction-dependent pressure-drop, temperature-propagation, and mixing equations. These extensions are outside the present radial formulation and are deferred rather than approximated.

**Location:** Revised title, §1, §§2.9, 3.7, and 3.14.

## R1.2 — Accuracy versus sensitivity

> **Condensed comment:** The manuscript conflates model accuracy with sensitivity of cost to modelling resolution.

**Response:** Accepted. We now use separate terms for separate quantities:

- **estimation bias** for differences in model-reported cost;
- **forward-evaluated decision-cost difference** for the consequences of applying a model-derived schedule under common forward physics;
- **physical prediction discrepancy** for differences in states such as flow, pressure, or temperature.

The generic term “accuracy” is no longer used for raw objective differences, and the two reference roles are defined explicitly.

**Location:** Revised §§2.1 and 2.4.

## R1.3 — Confounded ladder transitions

> **Condensed comment:** Several ladder transitions change multiple physical or numerical assumptions simultaneously, so their effects cannot be attributed separately.

**Response:** **The reviewer is correct.** The revised ladder changes one phenomenon at each transition. `CP`, `CP+L`, `ND⁰`, and `L1` isolate loss, topology, and interaction; transport delay is introduced only at `L6`; and piecewise-linearisation error is assessed separately through the nonlinear forward evaluator and fixed-schedule QCP re-solves. We also replace raw objective comparisons with certified bounds whenever optimisation tolerance is material.

**Location:** Revised §§2.1, 2.6, and 3.8; table of contrasts.

## R1.4 — Validation predates the new assets

> “The pipe model is calibrated and validated using data collected before the installation of the heat pump, electrode boiler, and thermal storage [...] evaluated through plausibility checks rather than post-upgrade measurements [...] does not fully validate the dispatch interactions that drive the study’s cost conclusions.”

**Response:** **The reviewer is correct.** The measurements predate the heat pump, electrode boiler, and storage, so their dispatch interactions are not validated against post-upgrade operational data. We now state this explicitly and have removed the claim that the comparative results are invariant to the post-upgrade dispatch.

The revised manuscript makes three narrower points.

First, the new assets are represented using documented component relations—temperature-dependent COP, storage round-trip efficiency and standby loss—but these remain model assumptions supported by parameter sources and plausibility checks rather than post-upgrade validation.

Second, the constitutive pipe equations do not depend on which asset produces the heat, but their inputs—especially flow and temperature—do depend on dispatch. Pre-upgrade measurements therefore support the transport model only over the conditions represented in those data; they do not validate the full post-upgrade operating-state distribution.

Third, using identical asset models in every fidelity formulation creates a controlled comparison and reduces asymmetric confounding, but shared asset-model error does not automatically cancel. Likewise, the synthetic factorial demonstrates robustness within the modelled design space, not independent empirical validation.

We consequently restrict the claim to comparative behaviour under the specified asset models and operating assumptions. The Memmingen schedules are not presented as validated absolute forecasts or operational recommendations. Post-upgrade metering would be required for that purpose.

**Location:** Revised §§2.9 and 3.14.

## R1.5 — Assumptions constrain the relevance of extended physics

> **Condensed comment:** Fixed capacities, temperatures, and operating rules may suppress the mechanisms through which pressure, temperature, and delay would affect dispatch.

**Response:** Accepted. We added a mechanism subsection explaining which physical channel each assumption closes. In particular, the flexible supply-temperature sensitivity makes hydraulics binding, whereas hydraulics remain economically small under the fixed heating curve. We therefore no longer present the negligible-hydraulics result as unconditional.

**Location:** Revised §§3.12 and 3.14.

## R1.6 — Arbitrariness of spatial clustering

> **Condensed comment:** The results may depend on an arbitrary choice of zone boundaries.

**Response:** We addressed this through a solved clustering experiment. We tested deliberate four-, seven-, and ten-zone partitions and 20 random tree-contiguous partitions. Every partition conserves total heat-loss capacity,

\[
\sum_p U_pL_p,
\]

and every formulation was solved to an optimality gap of at most 0.01%.

The deliberate alternatives differ from the original partition by no more than 0.01% of annual cost. Across the 20 random partitions, annual cost has a standard deviation of €4. Within this network and these admissible partitions, zone-boundary placement is therefore immaterial once total delivered loss is preserved. The manuscript no longer generalises this result beyond the tested radial system.

For Memmingen, the baseline aggregation also follows the available billing-grade metering boundaries rather than an optimisation-selected partition.

**Location:** Revised §§3.1 and 3.4.

## R1.7 — Deterministic hourly model without reserves

> **Condensed comment:** The deterministic hourly formulation omits uncertainty, sub-hourly operation, and reserve requirements.

**Response:** Accepted. The limitations section now states that the study does not represent forecast uncertainty, stochastic recourse, sub-hourly dynamics, start-up transients, or reserve provision. The conclusions are restricted to deterministic hourly scheduling.

**Location:** Revised §3.14.

# Senior Editor

> **Condensed comment:** Address formatting, structure, reference placement, highlights, and graphical-abstract requirements.

**Response:** We removed lumped references and added a build-time check for recurrence. The abstract is now one paragraph, the conclusion subheadings have been removed, and the manuscript has been reorganised into five principal sections. We also resubmitted the Highlights and a corrected graphical abstract.

**Location:** Revised manuscript structure, bibliography build configuration, Highlights, and graphical abstract.

# Additional corrections disclosed proactively

During the revision, we also corrected items not raised directly by the reviewers:

- incorrect asset placement in the graphical abstract;
- a percentage inconsistency between the graphical abstract and manuscript text;
- an orphaned configuration file in the public repository;
- two piecewise-linearisation settings that had previously been extrapolated and are now simulated directly.

The energy-export and pump-segment corrections are described under R2.4, together with their quantified effects.

We thank the editor and reviewers again. Their comments changed both the experimental design and the paper’s principal conclusion, and we believe the revised manuscript is substantially stronger and more appropriately scoped.

---

## Final checks before submission

1. Replace each condensed reviewer comment with the verbatim wording.
2. Confirm that ±0.6% and 2.4% in R2.2 are normalised by annual cost.
3. Replace descriptive figure references with final figure numbers.