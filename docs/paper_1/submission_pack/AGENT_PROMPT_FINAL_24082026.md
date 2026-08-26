You are a senior scientific-software engineer, optimisation researcher, and meticulous journal manuscript editor. Your task is to audit and revise the complete repository associated with:

“Estimation Bias versus Decision Regret in District-Heating Dispatch Optimisation”

The supplied PDF is `paper_CLEAN.pdf`. Treat the editable manuscript source, equations, model implementation, experiment configurations, generated results, tables, figures, supplements, and documentation as one consistency-critical research artifact.

## PRIMARY OBJECTIVE

Fix every methodological, mathematical, numerical, terminological, editorial, and code–manuscript inconsistency listed below.

Do not merely edit prose to hide implementation problems. Trace each claim back to code, configuration, data, and generated outputs. Where the manuscript and implementation disagree, determine which is correct from executable evidence and revise all affected artifacts consistently.

Never fabricate results. Do not invent missing experiments, measurements, bounds, solver outcomes, validation evidence, or citations.

## NON-NEGOTIABLE RULES

1. Preserve the paper’s valid central contribution:
   - separate loss visibility from spatial topology using the four-control design;
   - distinguish optimised-cost differences from forward-evaluated schedule performance;
   - identify the lowest decision-relevant fidelity within the tested regime.

2. Narrow unsupported claims instead of defending them rhetorically.

3. If a claim requires an experiment that can be run from the repository, run it reproducibly.

4. If a claim cannot be verified or reproduced:
   - mark it as unresolved;
   - remove or qualify it;
   - record it in `REVIEW_BLOCKERS.md`.

5. Never call a quantity:
   - “exact” unless the exact scope is stated;
   - a “bound” unless a valid mathematical inequality has been established;
   - “validated” unless the relevant observable was independently measured;
   - “regret” against a high-fidelity optimum unless that optimum or a rigorous bound is available.

6. Do not silently change numerical results. Every changed number must be traceable to:
   - a corrected equation,
   - a corrected unit conversion,
   - a corrected experiment,
   - a regenerated artifact, or
   - a corrected transcription.

7. Keep all manuscript terminology, code names, configuration names, table labels, captions, and supplementary files synchronised.

8. Prefer one canonical source for each reported result. Tables and figures should be generated from machine-readable outputs rather than manually duplicated values.

9. Preserve a clean build. The manuscript and supplement must compile without unresolved references, missing citations, malformed equations, or placeholder text.

10. Work on a dedicated branch. Commit changes in logically separated units with clear messages.

## REQUIRED FIRST PASS: REPOSITORY AND CLAIM MAP

Before editing:

1. Locate:
   - manuscript source;
   - bibliography;
   - supplementary material;
   - optimisation model;
   - forward evaluator;
   - nonlinear reference implementation;
   - synthetic-network generator;
   - experiment configurations;
   - result CSV/JSON/Parquet files;
   - table and figure generation scripts;
   - tests and CI configuration.

2. Create `REVIEW_AUDIT.md` containing a traceability matrix with these columns:

   | ID | Manuscript claim/equation | Source location | Code/config source | Verification command | Current status | Required fix | Final evidence |

3. Add every issue in this prompt to that matrix.

4. Record the current Git commit, environment, package versions, solver version, solver parameters, random seeds, hardware assumptions, and exact reproduction commands.

5. Build the current manuscript once and store the build log before making changes.

## A. RESOLVE MODEL-STATUS CONTRADICTIONS

### A1. L2 is both “solved” and “forward-evaluated”

Current conflict:
- nomenclature, Sections 2.1, 2.6, Table 14, and other passages classify L2 as forward-evaluated because its free-temperature formulation is non-convex and degenerate;
- Section 2.8 says “the one bilinear level” is solved to a 0.1% gap;
- some passages refer to L2 as though it supplies an optimised dispatch result.

Required action:
1. Inspect the implementation and experiment outputs.
2. Determine whether any meaningful L2 dispatch optimisation was actually solved.
3. If the free-variable solve is degenerate and excluded from analysis:
   - classify L2 consistently as forward-evaluated only;
   - remove all claims of a 0.1% L2 optimality gap;
   - do not report L2 estimation bias as an optimised-cost comparison;
   - describe the degenerate solve, if retained, only as a diagnostic.
4. If a valid constrained L2 solve exists, document its exact formulation and show why it is meaningful.
5. Update nomenclature, Tables 2, 3, 12, 14, implementation text, abstract, results, supplement, and code comments consistently.

### A2. NL is both “unsolved” and “solved”

Current conflict:
- NL is called an unsolved reference and “not solved” globally;
- Section 3.8 says the nonlinear reference is solved;
- 72-hour fixed-integer continuous re-solves are reported.

Required action:
Use explicit, consistent terminology:
- `NL-forward`: native nonlinear forward evaluator with no optimisation;
- `NL-72h`: fixed-integer, continuous, 72-hour nonlinear re-optimisation, where actually run;
- `NL-full-year`: attempted full-year nonlinear problem, with its actual solver outcome.

Do not call a 72-hour fixed-integer continuous re-solve a global mixed-integer full-year solution. Report:
- which variables are fixed;
- which remain free;
- objective and feasibility tolerances;
- global/local solver status;
- incumbent and bound, where available;
- time horizon;
- initialisation method.

Replace “representative week” with “72-hour window” everywhere unless a true seven-day run exists.

### A3. Synthetic networks use the “same controls and ladder”

Determine exactly which formulations were run on:
- all 135 synthetic networks;
- only Memmingen;
- selected subsets.

Revise Table 6 and all scope claims accordingly. Do not say every synthetic network was solved through the full ladder unless the outputs prove it.

## B. FIX THE NONLINEAR-REFERENCE CONTRADICTION

Current conflict:
- Section 2.4 says the forward evaluator uses the native exponential and contains no PWL approximation;
- Appendix B.4 says every temperature-propagating level, including the nonlinear reference, uses PWL exponential decay;
- Section 2.6 also says the exponential PWL is shared across levels.

Required action:
1. Inspect the actual evaluator and nonlinear re-solve code.
2. Establish separately whether each of the following uses native exponential decay or PWL:
   - L2 diagnostic/forward evaluation;
   - L3, if applicable;
   - L4/L5 forward evaluation;
   - L6;
   - NL-forward;
   - NL-72h.
3. Select precise names for each reference and use them consistently.
4. If NL-forward uses the native exponential, remove Appendix B.4’s contrary statement.
5. If NL-72h uses PWL for the exponential but native bilinear products, do not call it wholly “native” or “non-linearised.”
6. Recompute any claimed “linearisation error” so the compared formulations differ only in the stated approximation.
7. If exponential and product linearisation cannot be isolated, report the combined approximation gap rather than attributing it to one component.
8. Add automated tests confirming which implementation path each fidelity level activates.

## C. FORMALISE THE DECISION AND RECOURSE MAPPING

The current forward-evaluation description does not specify what is fixed and what may adjust during execution.

Create a formal subsection and corresponding code-level schema defining, for every source model:
- generation outputs;
- generator commitment binaries;
- heat-pump mode and commitment;
- storage charging/discharging;
- storage state of charge;
- grid import/export;
- network flows;
- temperatures;
- pumping;
- loss shortfall;
- dumped heat;
- unmet demand;
- emergency/top-up generation.

For every variable, classify it as:
- fixed first-stage schedule;
- recomputed physical state;
- permitted recourse;
- prohibited adjustment;
- penalty slack.

Required action:
1. Formalise a mapping \(M_\ell(x_\ell)\) from each model’s decision vector into an executable evaluator input.
2. Define the feasible execution set and all recourse policies.
3. Explain how copperplate and zone schedules are spatially mapped.
4. Specify exactly how omitted losses are covered:
   - which unit;
   - under what capacity and commitment constraints;
   - at what marginal price;
   - whether storage may adjust;
   - whether grid import may adjust;
   - whether unmet heat is permitted.
5. Verify that “marginal,” “peak,” and “unmet” schemes are clearly separate stress tests, not three definitions of the same metric.
6. Add tests for energy conservation, commitment consistency, storage continuity, capacity limits, and reproducibility under each recourse policy.
7. Update Table 9 and its caption to make the policy dependence explicit.

## D. CORRECT THE USE OF “DECISION REGRET”

Current quantity:
- forward-evaluated cost of a schedule relative to forward-evaluated L1;
- not necessarily relative to the high-fidelity optimum.

Required action:
1. Define:
   - optimised economic cost \(z_\ell\);
   - forward execution cost \(F(M_\ell(x_\ell); \pi)\) under recourse policy \(\pi\);
   - L1-relative execution-cost gap;
   - true high-fidelity regret, if computable.
2. Unless a high-fidelity optimum or rigorous bound is available, rename the primary metric throughout to one of:
   - “L1-relative execution-cost gap”;
   - “reference-relative execution gap”;
   - another equally precise term.
3. The first use may say this is the paper’s operational regret metric, but it must not be confused with regret against \(\min_x F(x)\).
4. If feasible, compute or bound:
   \[
   R(x_\ell)=F(x_\ell)-\min_{x\in X_F}F(x).
   \]
5. If not feasible, state that explicitly.
6. Revise title, abstract, keywords, nomenclature, equations, tables, figures, discussion, and conclusion if needed. If retaining “Decision Regret” in the title, define the nonstandard baseline-relative usage prominently and justify it.

## E. REMOVE INVALID BOUND CLAIMS

Current unsupported claims:
- re-costing L1 under L4/L5 physics “upper-bounds the regret”;
- finding less than 1% additional cost proves no schedule can be more than 1% better;
- forward evaluation “bounds rigorously” the nonlinear optimum.

Required action:
1. Remove these claims unless a valid lower bound on the finer-model optimum is computed.
2. Replace them with:
   - measured cost increment for the evaluated fixed schedule;
   - observed feasibility result;
   - explicit statement that re-optimisation could produce a different schedule.
3. Where possible, calculate:
   - a relaxation-based lower bound;
   - a feasible upper bound;
   - a certified optimality interval.
4. Only then use “upper bound,” “lower bound,” or “within X% of optimum.”
5. Reconcile Section 2.6.1 with Section 2.8, which correctly says forward evaluation is not a bound over all schedules.

## F. FIX THE FACTORIAL DESIGN AND DISTRIBUTED-GENERATION CLAIMS

Current conflict:
- \(3 \times 5 \times 3 \times 3 = 135\), accounting for node count, length, heterogeneity, and storage;
- Table 6 and Section 2.9.2 mention central/distributed generation as an additional factor;
- all examined cases are later said to use central generation;
- distributed generation is left open.

Required action:
1. Inspect generator configurations and outputs.
2. If no distributed-generation arm exists:
   - remove it from the factorial description;
   - state that all 135 networks use central generation;
   - preserve distributed generation as future work.
3. If distributed cases exist, correct the total count and report their formulation, signed-flow assumptions, and results.
4. Ensure abstract, Table 6, Sections 2.9.1–2.9.2, 3.5, 3.9, 3.14, conclusions, supplement, and README all agree.
5. Add a test that enumerates the Cartesian product and verifies the expected instance count and factor levels.

## G. NARROW THE “EXACT” DECOMPOSITION CLAIM

The four optimised cost outcomes satisfy an algebraic factorial identity. However, CP+L is an oracle/best-case intervention using exogenous network loss.

Required action:
1. Define the decomposition mathematically for the four outcomes:
   \[
   C_{00}, C_{01}, C_{10}, C_{11}.
   \]
2. State that closure is an exact algebraic identity for those four optimised economic costs under the specified exogenous-loss intervention.
3. Do not imply that the labels are universal, intervention-free physical causal effects.
4. Describe CP+L consistently as:
   - an oracle/best-case attribution control;
   - not generally operational unless the loss profile is independently known.
5. Clarify the timing of loss-adder construction:
   - generated from which reference data/model;
   - frozen before CP+L optimisation;
   - “ex post” relative to a naïve copperplate modeller.
6. Report constant and heating-curve adders separately where relevant.
7. Restrict “every arrow changes exactly one phenomenon” to contrasts where that is literally true.
8. Do not describe the whole ladder as an exact one-factor sequence if some transitions also change representation, evaluation mode, laterals, pressure, and station detail.

## H. CORRECT MATHEMATICAL AND UNIT ERRORS

### H1. Storage standing loss

Equation (11) currently appears as:
\[
E_{s,t}=(1-\alpha_s)\Delta t E_{s,t-1}+\cdots
\]
while the prose calls it exponential and time-step independent.

Determine the implemented formula. Use one dimensionally correct form, such as:
\[
E_{s,t}=(1-\alpha_s)^{\Delta t}E_{s,t-1}
+\eta_s^{ch}Q_{s,t}^{ch}\Delta t
-\frac{Q_{s,t}^{dis}\Delta t}{\eta_s^{dis}},
\]
if \(\alpha_s\) is a per-hour fractional loss.

Alternatively, use \(e^{-k_s\Delta t}\) if the code uses a continuous decay constant. Align nomenclature, units, prose, code, and tests.

### H2. CO2 units

Current conflict:
- \(E^{CO2}\) is declared in tonnes;
- \(e\) is in kg/MWh;
- Equation (12) produces kilograms;
- Equation (1) divides by 1000.

Choose one convention:
- store emissions in kg and divide by 1000 in carbon cost; or
- store emissions in tonnes and convert in Equation (12).

Update variable names, units, exports, equations, CSV headers, and tests. Add a dimensional test with a known 1 MWh example.

### H3. Heat-flow to mass-flow conversion

With \(Q\) in MW and \(c_p\) in J/(kg K), Equation (14) requires:
\[
\dot m=\frac{10^6 Q}{c_p\Delta T}.
\]

Confirm whether the implementation uses the factor explicitly or uses \(c_p\) in MJ/(kg K). Make the manuscript and code convention identical. Add unit tests.

### H4. Pumping-power conversion

\[
\frac{\dot m \Delta p}{\rho\eta}
\]
is in watts. If \(P^{pump}\) is in MW, include \(10^{-6}\). Confirm implementation and update Equation (16), code, and tests.

### H5. Pressure-drop SOS2 formulation

Equation (15) currently multiplies quantities called “segment slopes” by SOS2 weights, but proper interpolation normally requires breakpoint abscissae and function values.

Inspect the code and write the complete formulation:
\[
Q=\sum_k q_k w_k,\qquad
\Delta p=\sum_k f(q_k)w_k,\qquad
\sum_k w_k=1,
\]
with SOS2 adjacency, or document the incremental formulation actually used.

Correct the nomenclature:
- breakpoint flow \(q_k\);
- breakpoint pressure \(f(q_k)\);
- slopes only if an incremental slope formulation is used.

### H6. Pumping-power PWL and MILP classification

The manuscript calls L3 a MILP but displays the nonlinear product \(\dot m\Delta p\).

Show the actual direct PWL representation of pumping power as a function of \(Q\), including breakpoints, weights, and units. If the implementation is not linear, correct the model classification.

Check the claim that SOS2 introduces 368,000 binary variables. In Gurobi/Pyomo, SOS2 may not correspond to explicitly declared binary variables. Report declared variable types accurately.

### H7. Native nonlinear pumping expression

The statement that \(W=Q^2\) enters as \(QW\) is cubic and not an MIQCP term. Determine the actual NL formulation and classify it correctly:
- NLP;
- non-convex polynomial program;
- MIQCP only if no cubic term remains.

Do not call a cubic formulation quadratically constrained.

### H8. Darcy–Weisbach and hydraulic-resistance consistency

Verify:
- supply and return are both counted;
- the friction factor is constant or computed as claimed;
- diameter powers and units are correct;
- \(R_p\) truly has units Pa/MW² under the chosen conversion;
- station and lateral pressure contributions are not double-counted.

Add numerical regression tests against pandapipes or an independently calculated pipe case.

### H9. Transport delay units

Equation (19) yields seconds under SI inputs, not hours. Include the conversion to hours or state the internal units. Verify discretisation and boundary handling.

### H10. Delay discretisation

The use of \(k_p=\lfloor \tau_p/\Delta t\rfloor\) makes every sub-hour delay zero. Justify this choice or use a fractional-delay/interpolation method.

Do not say “transport delay is physically exactly zero.” Say its represented integer-step effect is zero at hourly resolution under the chosen discretisation.

## I. VALIDATION CLAIMS MUST MATCH THE EVIDENCE

### I1. Annual delivered energy does not validate network loss

The site lacks independently metered source-side thermal energy. Therefore:
- annual delivered-demand agreement cannot independently validate network loss;
- loss is model-implied or calibrated, not directly measured.

Required changes:
1. Replace claims that delivered-energy agreement “fixes,” “anchors,” or validates annual loss with precise language.
2. State what was measured, what was calibrated, and what was inferred.
3. Use wording such as:
   - “aggregate-demand validated”;
   - “energy-calibrated”;
   - “hydraulically cross-checked.”
4. Do not call the full forward model “validated high-fidelity physics” without qualifications.

### I2. Temperature validation failures

Current tables and prose conflict:
- Table 4 says temperature gates are not met;
- Table 7 labels applicable NLP metrics “n/a” despite numerical failures;
- the far-end row uses a 1.5 K gate although Table 4 associates worst-node error with 2.5 K;
- a trunk-drop gate appears in Table 7 but not Table 4;
- the model is called “displaced, not wrong,” based on an unverified mixing-valve explanation.

Required action:
1. Define every validation metric and its matching gate in one canonical table.
2. Use:
   - `pass`;
   - `fail`;
   - `not applicable`;
   - `not independently verifiable`.
3. For the propagating model, numerical exceedance of an applicable gate is `fail`, not `n/a`.
4. For a formulation that does not produce a metric, use `not applicable`.
5. Do not assert that the model is correct but displaced unless independent evidence establishes the sensor offset.
6. State that the temperature field is not validated with the available instrumentation.
7. Reconcile annual and 744-hour node analyses without implying that one validates the other.

### I3. Source-flow error

Keep the 33.8% MAPE visible. Do not dismiss it solely as denominator noise without quantitative evidence. If load-band analysis supports the interpretation:
- provide sample counts;
- provide MAE and MAPE per band;
- report energy-weighted error;
- retain the limitation.

### I4. New assets

Clearly distinguish:
- validation of pre-upgrade transport behaviour;
- plausibility checks for post-upgrade heat pump, electrode boiler, and storage;
- absence of post-upgrade dispatch validation.

### I5. U-value calibration and lateral losses

Trace all loss coefficients to:
- manufacturer/design data;
- allowed calibration range;
- fitted parameters;
- station/lateral reconstruction.

Do not say the total matches “measurement” if total network loss was not independently measured. If an inferred target was used, name it as such.

## J. REVISE STATION-LEVEL AND HYDRAULIC CLAIMS

1. Replace “no schedule could be more than 1% better” unless a valid bound exists.
2. Replace “the optimiser has no lever to re-optimise” unless proved from the model.
3. Describe the result as:
   - less than 1% additional evaluated cost for the fixed L1 schedule under the station model;
   - no observed hydraulic violation;
   - no demonstrated material need for re-optimisation in this case.
4. Verify whether 3 kW pumping is consistent with all unit corrections. Regenerate every hydraulic result after fixing units.
5. Verify the relationship among:
   - 3 kW peak pump power;
   - 7.9 MWh annual pump energy;
   - 784 EUR/year pump cost;
   - 1.4% L1→L3 cost increase.
   These numbers may not be mutually consistent. Recompute and explain.
6. Check whether the pressure cross-check validates only trunk hydraulics or also station/lateral components. Phrase scope accurately.
7. Do not infer low operating energy from installed pump capacity alone.

## K. REVISE THE SUPPLY-TEMPERATURE SENSITIVITY

The current experiment is a forward parameter sweep, not an optimisation with endogenous temperature.

Required action:
1. Rename “cost-optimal reduction” to “lowest-cost tested feasible reduction” unless a continuous optimisation was solved.
2. Document:
   - grid of temperature reductions;
   - fixed variables;
   - recomputed variables;
   - feasibility checks;
   - pricing of recovered heat;
   - treatment of COP and return temperature.
3. Do not claim the entire saving is purely a loss effect if other quantities change.
4. State that this sensitivity opens only a restricted temperature lever and does not reproduce full co-optimisation.
5. Verify the velocity limit and pumping values after unit corrections.

## L. FIX LINEARISATION-ERROR CLAIMS

1. Use “72-hour windows,” not “weeks.”
2. Specify exactly what “mixed-integer schedule fixed” means.
3. Verify whether the solver’s claimed 0.03% is a global optimality gap for a non-convex problem or only a local termination measure.
4. Do not say “within 0.03% of the global optimum” unless the solver supplies a valid global bound.
5. Distinguish:
   - pressure PWL error;
   - pumping PWL error;
   - exponential-decay approximation;
   - Taylor/bilinear-product approximation;
   - dispatch re-optimisation effect.
6. Do not infer cost error from a pointwise pressure approximation bound.
7. If the summer fixed-schedule model is infeasible, provide diagnostics or an IIS. Do not automatically interpret infeasibility as a real physical deliverability failure until numerical and formulation causes are excluded.
8. Correct Table 12 and Appendix B.4 accordingly.

## M. REVISE THE SCREENING RULE

The relation
\[
b=\frac{\lambda}{1+\lambda}
\]
is a first-order heat/energy burden relation under proportional-cost assumptions, not a general cost law.

Required action:
1. Derive the formula explicitly and list assumptions:
   - proportional marginal cost;
   - no commitment discontinuities;
   - no material CHP export interactions;
   - no storage or demand-charge nonlinearities;
   - consistent loss definition.
2. Call it a “first-order heuristic” or “screening approximation.”
3. Do not describe residuals as “the topology effect” unless demonstrated by the decomposition; accounting and dispatch nonlinearity may also contribute.
4. Report:
   - \(R^2\);
   - MAE in percentage points;
   - maximum error;
   - calibration/validation split;
   - uncertainty interval if possible.
5. Define the thresholds for “copperplate okay,” “calibrate,” and “resolve nodes.” If thresholds are judgmental and not validated, remove categorical bands or label them illustrative.
6. Reconcile “resolve nodes” with the paper’s own result that a copperplate with a known transferable loss profile can perform well.
7. Avoid calling the regression “a priori” if it was fitted and assessed on the same synthetic family without independent external validation.
8. Verify the held-out extrapolation claims and avoid MAPE where the denominator makes it unstable.

## N. NARROW GENERALISATION AND CAUSAL LANGUAGE

Use the following scope consistently:

“Deterministic hourly dispatch of centrally supplied, radial networks with fixed capacities and a prescribed heating curve.”

Required action:
1. Replace broad claims such as “spatial structure itself is worth almost nothing” with conditional wording.
2. Do not claim loss dominance is free of assumptions. The decomposition is exact for the outcomes, but its empirical magnitude is conditional on the tested systems.
3. Avoid the statement that relaxing assumptions “can only” make detailed physics matter more. Additional freedoms can also reduce costs or alter effects non-monotonically.
4. Keep distributed generation, bidirectional flow, meshed networks, joint sizing, endogenous temperatures, uncertainty, and real-time control explicitly out of scope.
5. Distinguish routing value from loss endogeneity.
6. Make clear that co-located generation and uncongested radial routing strongly limit the opportunity for topology to affect dispatch.

## O. RECONCILE COST ACCOUNTING

1. Define the solver objective and reported economic cost with complete equations.
2. Verify the carbon units and export-credit convention.
3. Explain why schedules are optimised under one objective but compared under another.
4. Do not say the economic cost is “the only quantity a dispatch decision changes”; emissions and accounting allocations can also change.
5. Ensure claims about decomposition are based on the same cost definition for all four cells.
6. Verify the reported 38.7–41.0%, 55–58 kEUR, 24–26 kEUR, 1.5 kEUR residual, and 5.6 kEUR variation from generated outputs.
7. If exported CHP receives an avoided-emissions credit only in reporting, label this as an accounting choice, not necessarily an operator cash flow.
8. Add reconciliation tests:
   \[
   Z = z_{\text{econ}} + \text{cycling term} + \text{carbon-allocation adjustment} + \text{residual}.
   \]
9. Report unexplained residuals honestly.

## P. EDITORIAL AND STRUCTURAL CORRECTIONS

Fix at minimum:

1. Replace `Section ??` with the correct cross-reference.
2. Remove duplicated implementation/optimality paragraphs in Section 2.8.
3. Replace “five formulations” with an accurate description.
4. Correct “representative winter and autumn week” to “72-hour windows.”
5. Clarify whether all synthetic solves use a 0.01% or 0.1% gap.
6. Verify the project-period statement in the acknowledgments; do not alter it without evidence.
7. Check the date consistency of all 2025–2026 references and DOI metadata.
8. Correct malformed ligatures and encoding artifacts such as “model-delity,” “eect,” and broken dashes.
9. Harmonise:
   - fidelity-level names;
   - `forward-evaluated` spelling;
   - station/substation/transmission-station terminology;
   - node, junction, consumer, and station counts;
   - `economic cost`, `objective`, `bias`, and execution-gap terms.
10. Shorten repetitive discussion, especially repeated claims about:
    - loss dominance;
    - metering limitations;
    - distributed generation;
    - supply-temperature flexibility;
    - loss-adder non-transfer.
11. Distinguish:
    - solved optimisation levels;
    - diagnostic formulations;
    - forward-evaluated physics scenarios;
    - nonlinear re-solve experiments.
12. Update Table 2 so it does not claim every arrow is an unconfounded solved-model contrast.
13. Update Table 15 so recommendations are explicitly observational and conditional.

## Q. CODE AND TEST REQUIREMENTS

Add or improve automated tests for:

1. Dimensional consistency:
   - MW ↔ W;
   - kg ↔ t CO2;
   - seconds ↔ hours;
   - Pa, bar, and pump-power conversions.

2. Model-feature activation:
   - each fidelity configuration activates exactly the intended code paths;
   - NL-forward uses the documented exponential path;
   - L2 is not accidentally included as a solved result.

3. Factorial identity:
   \[
   (C_{01}-C_{00})+(C_{10}-C_{00})
   +[C_{11}-C_{10}-C_{01}+C_{00}]
   =C_{11}-C_{00}.
   \]

4. Synthetic design:
   - exactly 135 unique cells for the stated four factors;
   - no undocumented generation-topology factor.

5. Forward evaluation:
   - fixed/recourse variable policy;
   - energy conservation;
   - storage continuity;
   - generation and grid limits;
   - unmet-demand accounting;
   - deterministic reproducibility.

6. SOS2 interpolation:
   - exact at breakpoints;
   - bounded interpolation error on test cases;
   - monotonic pressure and pump-power curves.

7. Hydraulic benchmark:
   - one hand-calculated pipe;
   - comparison against pandapipes for a fixed flow.

8. Cost reconciliation:
   - objective versus reported economic cost;
   - carbon and cycling terms.

9. Table consistency:
   - manuscript numbers read from canonical result files;
   - no manually diverging duplicated values.

10. Build checks:
    - no undefined references;
    - no missing citations;
    - no placeholder markers;
    - no encoding corruption.

## R. REPRODUCIBILITY REQUIREMENTS

Create or update:

- `README.md` with end-to-end reproduction instructions;
- `environment.yml`, `requirements.txt`, or lockfile;
- exact solver configuration files;
- `Makefile`, `justfile`, or equivalent commands for:
  - tests;
  - core experiments;
  - synthetic factorial;
  - figures;
  - tables;
  - manuscript build;
- a manifest mapping generated files to scripts and source data;
- random seed documentation;
- machine-readable experiment metadata.

Where proprietary Memmingen data prevent full reproduction, clearly separate:
- reproducible synthetic tests;
- anonymised summaries;
- non-reproducible private-data runs.

## S. REQUIRED OUTPUT FILES

Deliver:

1. Revised manuscript source and compiled PDF.
2. Revised supplement and compiled PDF, if separate.
3. Corrected model/evaluator code.
4. Regenerated tables and figures.
5. `REVIEW_AUDIT.md` with every issue closed or marked blocked.
6. `REVIEW_BLOCKERS.md` for items requiring author input, private data, or unavailable solver access.
7. `CHANGELOG_REVIEW.md` listing:
   - claim changes;
   - equation/unit changes;
   - numerical changes;
   - rerun experiments;
   - removed unsupported statements.
8. `REPRODUCTION.md` with exact commands and expected outputs.
9. A concise reviewer-response-style summary explaining how each major inconsistency was resolved.
10. Test logs and manuscript build logs.

## T. ACCEPTANCE CRITERIA

The work is complete only when:

- L2 has one consistent status everywhere.
- NL-forward, NL-72h, and NL-full-year are clearly distinguished.
- The exponential/PWL contradiction is resolved from code evidence.
- No forward evaluation is falsely described as an optimisation bound.
- The execution metric is precisely named and defined.
- The fixed-versus-recourse mapping is explicit.
- The synthetic design count and factor list agree.
- Distributed generation is not claimed as tested unless it actually was.
- Storage, CO2, mass-flow, pump-power, and delay units are dimensionally correct.
- The SOS2 and pumping formulations are fully documented and match code.
- Validation claims do not exceed the measurements.
- Applicable failed temperature gates are marked failed.
- The 72-hour experiments are not called weeks.
- The screening rule is presented as a conditional heuristic.
- All changed numbers are regenerated and traceable.
- All tests pass.
- The manuscript compiles without warnings that indicate unresolved content.
- The final paper’s strongest conclusion is conditional and defensible:

  “Within deterministic hourly dispatch of centrally supplied radial networks with fixed capacities and prescribed temperatures, representing thermal losses is substantially more consequential than resolving detailed routing or station-level hydraulics. This result is not established for distributed generation, meshed or bidirectional networks, joint sizing, endogenous temperature optimisation, uncertainty, or real-time control.”

## EXECUTION ORDER

Proceed in this order:

1. Inventory repository and build baseline.
2. Create the audit matrix.
3. Resolve model-status and reference-physics contradictions.
4. Fix units and equations.
5. Formalise execution mapping and metric definitions.
6. Correct experimental-design metadata.
7. Add tests.
8. Rerun affected experiments.
9. Regenerate tables and figures.
10. Revise manuscript claims and structure.
11. Build manuscript and supplement.
12. Perform an independent final consistency scan.
13. Produce the audit, changelog, blockers, and reviewer-response summary.

Do not stop after editing prose. The task is complete only when the manuscript, mathematics, code, configurations, generated results, and documentation tell the same verifiable story.