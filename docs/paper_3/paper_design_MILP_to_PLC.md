# Paper Design: From MILP Optimization to PLC-Integrated Predictive Control

## Working title

**From MILP Optimization to PLC-Integrated Predictive Control: Quantifying the Simulation-to-Plant Gap in Flexible Thermal Energy Systems**

### Target journal

Primary target: **Applied Thermal Engineering**

Alternative: **Energy**

The manuscript should be written so that the contribution is primarily methodological and experimentally demonstrated. The paper should not become a general PLC implementation paper or a forecasting paper.

---

# 1. Central idea of the paper

MILP-based scheduling can demonstrate substantial economic potential under nominal model assumptions. However, the objective value of a numerical optimization is not necessarily the performance that can be obtained from the physical plant.

The paper therefore follows the complete path

> **MILP model → receding-horizon operation → interface → PLC/PID → physical plant**

and quantifies how much of the theoretically obtained performance survives each transition.

The core scientific question is:

> **How much of the performance promised by a nominal MILP remains when the optimization is operated causally, integrated into a PLC-based control architecture, and executed on a real thermal plant?**

The paper should distinguish the following effects:

1. loss caused by replacing full-horizon optimization with receding-horizon operation,
2. loss caused by the difference between the nominal model and the physical plant,
3. loss caused by only using information actually available at the decision time,
4. recovery obtained by measurement-based correction of the plant model,
5. additional value of the optimization compared with a good rule-based controller.

The optimizer itself remains a standard MILP. Measurement feedback does **not** modify the optimization algorithm. Instead, it updates selected parameters/characteristics of the plant representation used by the next optimization.

Preferred wording:

> **The MILP remains the optimizer – measurement feedback only corrects its representation of the real plant.**

Avoid describing this as “online optimization”. The optimization is repeatedly solved in a receding-horizon manner; the feedback mechanism adapts the model representation used by the next MILP.

---

# 2. Research gap

The introduction should establish three observations:

### 2.1 Numerical MILP studies

MILP-based scheduling and dispatch models demonstrate economic or energetic savings under nominal assumptions. These studies typically evaluate the optimized objective directly from the same model that generated the schedule.

### 2.2 Experimental MPC / PLC studies

Experimental predictive-control studies demonstrate that optimization-based control can be implemented on physical hardware and integrated with PLC/PID architectures.

### 2.3 Missing systematic balance

What is less clearly quantified is the transition between these two perspectives:

> **How much of the numerical optimization potential is physically realized after accounting for receding-horizon operation, limited future information, model–plant mismatch, interfaces, PLC execution and actual plant dynamics?**

The paper fills this gap through a controlled sequence of numerical and physical reference cases.

---

# 3. Research questions

## RQ1 – System integration

**How can a generic MILP be transferred into a real-time-capable, PLC-integrated closed-loop controller for flexible thermal energy systems?**

This question is answered through the architecture and implementation described in the Methods section.

The focus is not the novelty of the PLC communication itself, but the complete and reproducible integration chain from optimization to physical execution.

## RQ2 – Simulation-to-plant gap

**How large is the performance difference between the nominal model optimum, receding-horizon planning, and physical realization?**

This is the main quantitative research question.

## RQ3 – Practical information and implementation limits

The original formulation is:

> How do horizon, computational time limit and forecast quality influence the achievable physical implementation?

For the final manuscript, this should be refined because computational feasibility is primarily a **basic real-time requirement**, while forecasting is not intended to be a separate research contribution.

Recommended final formulation:

> **How do causal receding-horizon operation and limited future information affect the physically achievable performance, and to what extent can measurement-based model correction recover the resulting losses?**

A solver deadline should therefore not be presented as an independent scientific effect. Every RH-MILP run must satisfy the real-time requirement. If a solution is not available within the control interval, a predefined fallback strategy is executed and the event is recorded as a real-time feasibility failure.

Forecasting should be treated only as part of the distinction between ideal information and information actually available at the decision time.

---

# 4. System architecture

The implementation follows the architecture shown in the project concept:

```text
                    15 min re-optimization

   ┌────────────┐      ┌─────────┐      ┌────────────┐
   │ Input data │ ───► │  MILP   │ ───► │ Interface  │
   └────────────┘      └─────────┘      └─────┬──────┘
         ▲                                     │
         │                                     ▼
         │                              ┌────────────┐
         │                              │    PLC     │
         │                              │  Beckhoff  │
         │                              └─────┬──────┘
         │                                    │
         │                                    ▼
         │                              ┌────────────┐
         │                              │   Plant    │
         │                              └─────┬──────┘
         │                                    │
         └──────────── measurements ──────────┘
```

The implementation stack is:

- **Time-series / input data:** heat demand, electricity prices, source availability, storage state and other exogenous inputs.
- **MILP:** Pyomo-based optimization model.
- **Interface:** Python interface and mapping between optimization variables and plant-relevant control variables.
- **PLC:** Beckhoff PLC implementing low-level control, limits, interlocks and PID functions.
- **Plant:** physical flexible thermal energy system.
- **Feedback:** measured plant variables are transferred back to the input layer for the next optimization cycle.

The architecture should explicitly separate responsibilities:

| Layer | Main task | Typical time scale |
|---|---|---:|
| Time-series / input data | Demand, prices, sources, storage state | 24 h horizon |
| MILP | Schedule / setpoint trajectory | 24 h horizon, 15 min re-optimization |
| Interface | Setpoint mapping, characteristic handling, rate limits | 1–5 min |
| PLC | Tracking, interlocks, safety limits, PID | ~100 ms |
| Plant | Physical dynamics | continuous |

The different time scales are a central methodological point: the MILP does not replace the PLC. It provides predictive setpoints; the PLC remains responsible for fast control and safety.

---

# 5. Control architecture and responsibility split

The paper should make the following hierarchy explicit.

## MILP

The MILP is responsible for:

- calculation of economically optimal schedules,
- coordination of flexible components,
- storage charging/discharging decisions,
- use of electricity prices,
- source selection,
- anticipation of future heat demand and other exogenous information,
- respecting optimization-level constraints.

## Interface

The interface is responsible for:

- mapping optimization variables to plant-relevant setpoints,
- applying characteristic curves,
- respecting rate limits where required,
- translating model variables into PLC-compatible commands,
- communication between the optimization environment and PLC.

## PLC / PID

The PLC is responsible for:

- setpoint tracking,
- low-level regulation,
- interlocks,
- safety boundaries,
- actuator limits,
- fast dynamics that cannot be represented by the MILP time scale.

## Plant

The physical system determines the actually achieved performance through:

- real component efficiencies,
- temperature-dependent behavior,
- actuator dynamics,
- delays,
- losses,
- disturbances,
- measurement errors,
- unmodeled interactions.

---

# 6. Time horizon and receding-horizon operation

The core controller uses a **24 h optimization horizon**.

The controller is re-optimized every **15 min**.

At each decision time `t`:

1. collect the current plant state,
2. collect all information available at `t`,
3. update the model parameters / characteristics if feedback correction is enabled,
4. solve the 24 h MILP,
5. transmit the next setpoint trajectory to the interface / PLC,
6. execute the first control interval,
7. collect measurements,
8. repeat at `t + 15 min`.

Only the first part of the optimized trajectory is committed to the plant. Future decisions are reconsidered at the next optimization cycle.

---

# 7. Numerical and physical reference cases

The experimental structure should be deliberately simple and causally consistent.

## Numerical cases

### S0 – Full-Horizon MILP

- full evaluation horizon,
- ideal future information,
- nominal plant model,
- numerical simulation,
- no receding-horizon restriction.

This is the **nominal theoretical reference**.

Denote the objective by:

\[
J_{S0}^{num}
\]

### S1 – Receding-Horizon MILP

- 24 h rolling horizon,
- ideal future information,
- nominal plant model,
- numerical simulation,
- 15 min re-optimization.

Denote the objective by:

\[
J_{S1}^{num}
\]

S1 is the first numerically executable controller reference.

---

## Physical cases

### R1 – Physical plant, ideal information

- RH-MILP,
- ideal/oracle future information,
- nominal model,
- real plant,
- same optimization structure as S1.

R1 is a **counterfactual physical reference**. It is used to isolate the model-to-plant gap without mixing it with uncertainty in future information.

The actual future profiles can be replayed where technically possible. This case should explicitly be described as an oracle/replay reference, not as realistic everyday operation.

Denote:

\[
J_{R1}^{phys}
\]

### R2 – Physical plant, available information

- RH-MILP,
- only information actually available at the decision time,
- nominal model,
- real plant.

Future heat demand and other uncertain quantities are represented using a transparent, reproducible information assumption. Forecasting is **not** studied as a separate research contribution.

Denote:

\[
J_{R2}^{phys}
\]

### R3 – Physical plant, feedback-corrected model

- RH-MILP,
- same information as R2,
- plant measurements are used to update selected model parameters / characteristics,
- real plant.

Denote:

\[
J_{R3}^{phys}
\]

### R4 – Rule-Based Control benchmark

- physical plant,
- same available information as R2/R3,
- no MILP optimization,
- predefined, well-tuned rule-based controller.

Denote:

\[
J_{R4}^{phys}
\]

The benchmark must be a **good practical Rule-Based Control (RBC)** strategy rather than an intentionally weak controller.

---

# 8. Causal information structure

A strict information boundary must be maintained.

At decision time `t`, the controller may use:

- measured current heat demand,
- measured storage state,
- measured current plant state,
- electricity prices that are already available,
- historical measurements,
- future profiles that are genuinely available at `t`.

The controller may not use future measurements that would only become available after the decision.

The causal sequence is:

\[
\text{measurement at }t
\rightarrow
\text{model correction for }t+1
\rightarrow
\text{MILP}(t+1)
\]

No future measurement may be used to alter a past decision.

---

# 9. Feedback-based model correction

This is one of the central methodological contributions.

The MILP itself remains unchanged. Only selected parameters or characteristics representing the physical plant are updated.

## 9.1 Model–plant residual

For measured output \(y\):

\[
e_t = y_t^{plant} - y_t^{model}
\]

Possible residuals include:

- heat output,
- electrical consumption,
- supply / return temperature,
- storage state,
- auxiliary power,
- other physically measurable variables.

## 9.2 Model parameters

Define a compact parameter vector:

\[
\theta_t = \{COP, Q_{max}, \eta_{TES}, P_{aux}, \ldots\}
\]

The update follows the generic structure:

\[
\theta_{t+1}=f(\theta_t,e_t)
\]

Only a small number of physically interpretable parameters should be corrected.

Potential examples:

- heat-pump COP characteristic,
- maximum available thermal output,
- electrical consumption characteristic,
- storage charging / discharging efficiency,
- storage loss parameter,
- auxiliary power.

## 9.3 Example

If the model predicts:

\[
Q_{HP}^{model}=100\,kW
\]

while the plant delivers:

\[
Q_{HP}^{plant}=93\,kW
\]

then:

\[
e_Q=-7\,kW
\]

The correction mechanism may update the corresponding `Qmax` or COP characteristic used in the next optimization cycle.

The schedule is **not directly corrected** based on the residual. Instead, the plant representation is corrected and the next MILP is solved using the updated model.

---

# 10. Feedback levels

The implementation should distinguish three possible feedback levels.

### Level 1 – State feedback

Directly synchronize model state with measured plant state.

Example:

\[
SOC^{model}\leftarrow SOC^{measured}
\]

This is necessary and should normally be considered part of standard closed-loop operation rather than the main novelty.

### Level 2 – Parameter feedback — preferred core method

Update physically interpretable parameters:

\[
\theta_t\rightarrow\theta_{t+1}
\]

This should be the main feedback mechanism in the paper.

### Level 3 – Characteristic / residual correction

Correct a model characteristic based on observed residuals.

This can be treated as an extension or sensitivity study if implementation effort allows.

The core paper should remain deliberately simple enough that the contribution is clearly about the simulation-to-plant gap rather than the development of a new machine-learning model.

---

# 11. Rule-Based Control benchmark

The physical MILP controller must be compared with a credible Rule-Based Control (RBC) benchmark.

The RBC should represent a realistic industrial / thermal control strategy and may contain:

- storage SOC or temperature hysteresis,
- charging during predefined low-price periods,
- fixed terminal recovery rules,
- backup / peak-load rules,
- simple priority logic between available heat sources.

The RBC should be tuned on a separate calibration period and then frozen before the main evaluation.

This prevents the benchmark from being deliberately weak and makes the comparison scientifically meaningful.

The key comparison is:

> Does the feedback-corrected predictive MILP provide additional economic value over a well-tuned practical controller?

---

# 12. Real-time computation requirement

The solver deadline is a **feasibility condition**, not a separate main experimental factor.

For each 15 min control interval:

\[
T_{solve} < T_{control}
\]

with an appropriate safety margin.

Every optimization run should record:

- solver runtime,
- solver status,
- objective value,
- optimality gap if applicable,
- whether the solution was available before the deadline.

If the deadline is not met:

1. classify the event as a real-time feasibility failure,
2. activate a predefined fallback strategy,
3. record the event and resulting performance.

The paper should not create an artificial comparison such as “5 min vs 10 min vs 15 min deadline” unless this is later identified as a dedicated research question.

---

# 13. Forecasting / future information

Forecasting is **not a research contribution of this paper**.

The purpose is only to distinguish:

- **ideal information**, and
- **information actually available at decision time**.

A simple and transparent historical estimate can be used where necessary, for example:

\[
\hat Q_{t+k|t}=Q_{t+k-24h}
\]

The manuscript should avoid a detailed comparison of forecasting algorithms.

Recommended wording:

> Forecasting is not treated as an independent research object. Instead, ideal future information is distinguished from information actually available at the decision time. A simple transparent historical estimate is used where a future quantity must be represented for reproducibility.

---

# 14. Electricity price scenarios

The study should distinguish between **fixed electricity prices** and **dynamic day-ahead electricity prices**, because the value of predictive optimization is expected to depend on price variability.

Recommended minimum experimental design:

| Scenario | Electricity price | Purpose |
|---|---|---|
| P1 | Fixed price | Baseline; isolates thermal / plant effects from price-driven arbitrage |
| P2 | Dynamic day-ahead price | Represents realistic economic operation and tests predictive value under temporal price variation |

The exact price data source and period should be documented in the final implementation.

The same plant, constraints, demand profiles and controller settings should be retained between price scenarios as far as possible.

---

# 15. Experimental design

The main experiment should combine the controller/reference cases with the price scenarios.

Core matrix:

| Case | Controller | Information | Model | Plant | Price scenario |
|---|---|---|---|---|---|
| S0 | Full-Horizon MILP | Ideal | Nominal | Simulation | P1/P2 |
| S1 | RH-MILP | Ideal | Nominal | Simulation | P1/P2 |
| R1 | RH-MILP | Ideal/oracle | Nominal | Physical | P1/P2 |
| R2 | RH-MILP | Available | Nominal | Physical | P1/P2 |
| R3 | RH-MILP | Available | Feedback-corrected | Physical | P1/P2 |
| R4 | RBC | Available | Rule-based | Physical | P1/P2 |

The primary scientific chain is:

```text
S0 ── ΔRH ──► S1 ── ΔPlant ──► R1 ── ΔInfo ──► R2 ── ΔFeedback ──► R3
                                                                            │
                                                                            │
                                                                       compare
                                                                            │
                                                                            ▼
                                                                           R4
                                                                      RBC benchmark
```

---

# 16. Quantification of the individual effects

## 16.1 Receding-horizon effect

\[
\Delta_{RH}=J_{S1}^{num}-J_{S0}^{num}
\]

Question:

> How much performance is lost by replacing full-horizon optimization with rolling-horizon operation?

---

## 16.2 Simulation-to-plant effect

\[
\Delta_{Plant}=J_{R1}^{phys}-J_{S1}^{num}
\]

Question:

> How much does actual plant performance deviate from the nominal RH-MILP prediction?

This comparison is only valid if S1 and R1 use identical optimization logic, constraints and ideal future information, with the physical plant being the main changed element.

---

## 16.3 Effect of limited future information

\[
\Delta_{Info}=J_{R2}^{phys}-J_{R1}^{phys}
\]

Question:

> How much performance is lost when the controller is restricted to information actually available at the decision time?

Preferred terminology:

> **Effect of limited future information**

Avoid the vague term “information effect”.

---

## 16.4 Feedback effect / recovery

For an intuitive recovery measure:

\[
\Delta_{Feedback}=J_{R2}^{phys}-J_{R3}^{phys}
\]

Positive values indicate that feedback-based model correction reduces the objective.

For strict cost-change sign conventions in the manuscript, alternatively report:

\[
\Delta_{Feedback}^{cost}=J_{R3}^{phys}-J_{R2}^{phys}
\]

where a negative value indicates an improvement.

Preferred interpretation:

> **How much performance can be recovered through measurement feedback and model correction?**

---

## 16.5 MILP value relative to RBC

\[
\Delta_{MILP-RBC}=J_{R4}^{phys}-J_{R3}^{phys}
\]

Positive values indicate that the feedback-corrected MILP achieves a lower objective than the RBC benchmark.

Question:

> What additional economic value does predictive MILP control provide compared with a good practical rule-based controller?

---

# 17. Objective and performance metrics

The main objective should remain economically interpretable.

Recommended primary metric:

- total operating cost over the evaluation period.

Secondary metrics:

- electricity consumption,
- electricity cost,
- fuel / auxiliary energy cost,
- CO₂ emissions if included in the objective or evaluation,
- peak electrical demand,
- number of starts,
- operating hours,
- constraint violations,
- unmet thermal demand,
- storage state deviation,
- solver runtime,
- solver status / timeout frequency,
- communication / execution failures if relevant.

The paper should distinguish **economic performance** from **implementation performance**.

Implementation metrics should include at least:

- percentage of optimization cycles solved within the control interval,
- fallback frequency,
- communication reliability,
- tracking error between optimized setpoint and physical realization,
- model–plant residuals before and after feedback correction.

---

# 18. Bilancing and fairness rules

The comparison must use identical service requirements wherever possible.

The following should be fixed across controller comparisons:

- thermal demand / service requirements,
- initial storage state,
- terminal storage condition or common terminal corridor,
- physical component availability,
- safety constraints,
- evaluation period,
- relevant operating limits.

The evaluation must not reward a controller simply because it violates service requirements.

If thermal demand is not met beyond a predefined tolerance, the event should be reported explicitly and either:

- treated as a feasibility failure, or
- penalized according to a predefined common rule.

The rule must be identical for all controller cases.

---

# 19. Data split and calibration

Any model calibration, feedback tuning or RBC tuning must be separated from the main evaluation.

Recommended structure:

```text
Historical data
      │
      ├── Calibration / tuning period
      │       ├── RBC tuning
      │       └── feedback update-rule tuning
      │
      └── Frozen main evaluation period
              ├── S0 / S1
              ├── R1 / R2 / R3
              └── R4
```

Once the feedback update law and RBC parameters are frozen, they must not be manually adjusted based on the main evaluation results.

---

# 20. Suggested feedback implementation

The first implementation should use a small number of interpretable corrections rather than a complex machine-learning model.

A generic form is:

\[
\theta_{t+1}=\theta_t+K e_t
\]

with appropriate bounds and filtering.

For example:

\[
Q_{max,t+1}=clip(Q_{max,t}+K_Q e_{Q,t},Q_{min},Q_{max})
\]

or an analogous update for COP / efficiency characteristics.

The exact update mechanism should be selected based on the available measurements and physical model structure.

Important requirements:

- bounded updates,
- physically meaningful parameter ranges,
- no future information,
- no direct schedule manipulation,
- stable behavior under noisy measurements,
- deterministic and reproducible update rules.

If the feedback mechanism becomes a substantial machine-learning contribution, the scope of the paper changes and should be reconsidered.

---

# 21. Interface and PLC implementation

The interface section should document the complete chain:

```text
Pyomo / MILP
     │
     ▼
Optimization variables
     │
     ▼
Setpoint mapping
     │
     ▼
Python interface / PyADS
     │
     ▼
Beckhoff PLC
     │
     ▼
PID / interlocks / safety limits
     │
     ▼
Physical plant
```

The interface must explicitly address:

- variable mapping,
- units,
- sampling periods,
- communication protocol,
- missing / invalid data,
- rate limits,
- bounds,
- fallback behavior,
- synchronization between optimization and PLC cycles.

The implementation should follow the established approach / terminology of the relevant literature, including the intended methodological positioning against work such as Langerova et al. (2025), Frison et al. (2019), and D’Ettorre et al. (2019), where appropriate and after verification of the exact references.

Do not claim methodological equivalence with these papers without checking the original sources.

---

# 22. Results structure

The Results section should follow the causal chain rather than simply listing experiments.

## 22.1 Real-time feasibility

First demonstrate that the controller can actually operate at the required 15 min re-optimization interval.

Report:

- solve-time distribution,
- median / mean / maximum runtime,
- fraction within deadline,
- fallback events.

This establishes feasibility before interpreting economic results.

## 22.2 Nominal optimization vs RH optimization

Compare S0 and S1.

Main result:

\[
\Delta_{RH}
\]

Show how much theoretical performance is lost solely because the controller becomes causal and receding-horizon.

## 22.3 Simulation vs physical plant

Compare S1 and R1.

Main result:

\[
\Delta_{Plant}
\]

This is the central simulation-to-plant gap.

## 22.4 Ideal vs available information

Compare R1 and R2.

Main result:

\[
\Delta_{Info}
\]

This quantifies the effect of limited future information without turning forecasting into a separate research topic.

## 22.5 Model correction

Compare R2 and R3.

Main result:

\[
\Delta_{Feedback}
\]

Show:

- residuals before correction,
- parameter evolution,
- residuals after correction,
- economic recovery.

## 22.6 MILP vs RBC

Compare R3 and R4.

Main result:

\[
\Delta_{MILP-RBC}
\]

This establishes whether the added complexity of predictive MILP control produces meaningful additional plant-level value.

---

# 23. Recommended figures

## Figure 1 – Overall architecture

Use the existing project architecture as the conceptual basis:

> Input data → MILP → Interface → PLC → Plant → measurements → Input data

Include the 15 min re-optimization label and the different time scales.

## Figure 2 – Experimental reference chain

```text
S0 → S1 → R1 → R2 → R3
                    │
                    └──── R4: RBC benchmark
```

Annotate the five quantified effects.

## Figure 3 – Feedback mechanism

Show:

> RH-MILP → PLC/PID → Plant → Measurements → Residual → Model correction → RH-MILP

The key message should be visually dominant:

> **Model is corrected, optimizer remains unchanged.**

## Figure 4 – Solver / real-time feasibility

Show solver runtime distribution relative to the 15 min control interval.

## Figure 5 – Simulation-to-plant performance gap

Recommended bar or waterfall representation:

```text
S0 nominal reference
      ↓ ΔRH
S1 RH numerical
      ↓ ΔPlant
R1 physical / ideal information
      ↓ ΔInfo
R2 physical / available information
      ↓ ΔFeedback
R3 physical / corrected model
```

R4 should be shown as a separate benchmark bar.

## Figure 6 – Model correction

Show one or two representative physical quantities:

- predicted vs measured heat output,
- parameter correction over time,
- residual before / after feedback.

Do not overload this figure with many parameters.

---

# 24. Recommended tables

## Table 1 – Architecture and time scales

| Layer | Task | Implementation | Time scale |
|---|---|---|---|
| Input data | Load, price, source and state information | Python / data layer | 24 h horizon |
| MILP | Predictive scheduling | Pyomo | 15 min re-optimization |
| Interface | Mapping / limits | Python / PyADS | 1–5 min |
| PLC | Tracking / safety | Beckhoff | ~100 ms |
| Plant | Physical dynamics | Hardware | Continuous |

## Table 2 – Controller reference cases

Use the S0–S1 and R1–R4 definition from Section 7.

## Table 3 – Experimental parameters

Include:

- horizon,
- control interval,
- solver,
- solver tolerance / time limit,
- fallback rule,
- initial and terminal storage conditions,
- demand profiles,
- price scenarios,
- model correction parameters,
- RBC parameters.

## Table 4 – Main results

| Case | Cost | Electricity | CO₂ | Constraint violations | Runtime | Fallback |
|---|---:|---:|---:|---:|---:|---:|
| S0 | | | | | | |
| S1 | | | | | | |
| R1 | | | | | | |
| R2 | | | | | | |
| R3 | | | | | | |
| R4 | | | | | | |

## Table 5 – Effect decomposition

| Effect | Definition | Result | Relative effect |
|---|---|---:|---:|
| RH effect | ΔRH | | |
| Simulation-to-plant | ΔPlant | | |
| Limited information | ΔInfo | | |
| Feedback recovery | ΔFeedback | | |
| MILP vs RBC | ΔMILP-RBC | | |

---

# 25. Relative metrics

Absolute objective differences should be accompanied by relative differences where meaningful.

For example:

\[
\Delta_{rel} = \frac{J_A-J_B}{J_B}\cdot100\%
\]

For feedback recovery, a useful measure is:

\[
Recovery =
\frac{J_{R2}-J_{R3}}
     {J_{R2}-J_{R1}}
\cdot100\%
\]

This should only be used where the denominator is meaningful and should be interpreted carefully.

A second useful quantity is the share of the total physical gap recovered by feedback.

---

# 26. Expected scientific contribution

The paper should claim the following contributions, provided they are supported by the final experiments:

1. **A reproducible architecture for transferring MILP-based predictive scheduling into a PLC-integrated physical thermal control system.**
2. **A controlled decomposition of the gap between nominal numerical optimization and physical plant performance.**
3. **A quantitative distinction between receding-horizon effects, simulation-to-plant mismatch and limited future information.**
4. **A measurement-feedback mechanism that corrects selected physically interpretable model parameters without changing the underlying MILP optimizer.**
5. **An experimental comparison against a credible rule-based controller.**
6. **A practical assessment of real-time feasibility and fallback behavior under a 15 min optimization cycle.**

The paper should not claim:

- a novel forecasting method,
- a novel MILP formulation solely because Pyomo is used,
- a new PLC communication protocol,
- generic superiority of MILP over all existing control methods,
- universal conclusions about all thermal energy systems from one plant.

---

# 27. Discussion structure

The Discussion should answer the research questions directly.

## RQ1

Was the complete optimization-to-plant chain operationally feasible?

Discuss:

- communication,
- computational time,
- tracking,
- fallback,
- interface complexity.

## RQ2

Where does the numerical potential disappear?

Use the effect decomposition:

\[
\Delta_{RH},\quad
\Delta_{Plant},\quad
\Delta_{Info}
\]

Discuss which source dominates.

## RQ3

Can feedback recover the lost performance?

Discuss:

\[
\Delta_{Feedback}
\]

and compare against RBC:

\[
\Delta_{MILP-RBC}
\]

---

# 28. Limitations

The paper should explicitly discuss:

- single-plant or limited hardware validation,
- dependence on the selected thermal system architecture,
- dependence on the selected MILP model fidelity,
- dependence on price and demand scenarios,
- limited forecasting treatment,
- assumptions behind the oracle-information reference,
- calibration requirements for feedback correction,
- possible overfitting of model correction parameters,
- PLC / interface architecture being hardware-specific,
- limited generalizability of the exact numerical results.

A key limitation is that R1 is a counterfactual oracle-information experiment and therefore cannot represent normal operation. Its purpose is causal decomposition.

---

# 29. Manuscript structure for Applied Thermal Engineering

## 1. Introduction

- Industrial thermal flexibility and predictive scheduling
- MILP potential
- Experimental / PLC implementation literature
- Missing simulation-to-plant balance
- Research gap
- Research questions
- Contributions

## 2. System and control architecture

### 2.1 Physical thermal system
### 2.2 MILP optimization
### 2.3 Receding-horizon operation
### 2.4 Interface and PLC architecture
### 2.5 Closed-loop information flow

## 3. Methodology for quantifying the simulation-to-plant gap

### 3.1 Reference cases S0–S1
### 3.2 Physical cases R1–R4
### 3.3 Causal information structure
### 3.4 Feedback-based model correction
### 3.5 Rule-Based Control benchmark
### 3.6 Real-time feasibility and fallback
### 3.7 Performance metrics

## 4. Experimental setup

### 4.1 Hardware and PLC
### 4.2 Communication / PyADS interface
### 4.3 Data and operating scenarios
### 4.4 Fixed vs dynamic day-ahead electricity prices
### 4.5 Calibration and evaluation periods

## 5. Results

### 5.1 Real-time feasibility
### 5.2 Receding-horizon effect
### 5.3 Simulation-to-plant gap
### 5.4 Effect of limited future information
### 5.5 Feedback-based model correction
### 5.6 Comparison with Rule-Based Control

## 6. Discussion

- interpretation of gap decomposition,
- practical meaning,
- robustness,
- generalizability,
- implications for industrial predictive control.

## 7. Conclusions

One coherent conclusion section, without excessive sub-subsections.

---

# 30. Abstract design

The abstract should follow this sequence:

1. Problem: numerical MILP savings are not necessarily physically realized.
2. Gap: simulation-to-plant transition is insufficiently quantified.
3. Method: controlled numerical and physical reference cases from S0 to R4.
4. Experimental platform: 24 h RH-MILP, 15 min re-optimization, PLC/PID and physical thermal plant.
5. Feedback: measurement-based correction of selected model parameters.
6. Main quantitative result: report the dominant gap and recovery once experiments are available.
7. Practical implication: numerical optimization potential should be evaluated together with causal information, model mismatch and real-time execution.

Do not write the final abstract until the numerical results are available.

---

# 31. Writing style and positioning

The manuscript should be written for an energy-system / thermal-engineering audience rather than a control-theory-only audience.

Emphasize:

- energy-economic consequences,
- physical realization,
- reproducibility,
- system integration,
- quantitative gap decomposition.

Do not overemphasize software engineering.

The PLC / PyADS / Pyomo implementation is important as the enabling infrastructure, but the scientific contribution is the **quantification and decomposition of the simulation-to-plant gap**.

Avoid unnecessary terminology such as “digital twin”, “AI control”, “online optimization” or “self-learning control” unless the implemented method genuinely requires those concepts.

---

# 32. Coding-agent implementation plan

The coding agent should implement the study in the following order.

## Phase A – Freeze the baseline MILP

- verify the existing MILP,
- freeze the nominal model,
- document all parameters,
- define objective and constraints,
- define initial / terminal conditions.

## Phase B – Implement S0

- full-horizon optimization,
- deterministic input data,
- export objective and all relevant trajectories.

## Phase C – Implement S1

- 24 h rolling horizon,
- 15 min control interval,
- ideal future information,
- identical nominal model,
- log runtime and solver status.

## Phase D – Implement physical R1

- connect the same RH controller to the plant,
- replay / provide ideal future information,
- verify identical optimization logic,
- log all commands and measurements.

## Phase E – Implement R2

- replace ideal future information with actually available information,
- preserve all other controller settings,
- evaluate performance impact.

## Phase F – Implement R3 feedback

- implement state synchronization,
- implement selected parameter correction,
- add filtering and parameter bounds,
- freeze update rules before main evaluation,
- log parameter evolution and residuals.

## Phase G – Implement R4 RBC

- implement a transparent rule-based benchmark,
- tune using separate data,
- freeze parameters,
- execute on the same physical plant.

## Phase H – Evaluation

Generate automatically:

- objective values,
- relative savings,
- effect decomposition,
- solver runtime statistics,
- fallback statistics,
- model residuals,
- feedback parameter evolution,
- RBC comparison.

## Phase I – Reproducibility

Every experiment should have:

- configuration file,
- controller identifier,
- price scenario identifier,
- data period,
- random seed if applicable,
- model version,
- feedback version,
- RBC version,
- solver settings,
- timestamp / experiment ID.

The final analysis should be reproducible from stored experiment outputs rather than manual spreadsheet calculations.

---

# 33. Recommended repository structure

```text
project/
├── model/
│   ├── milp.py
│   ├── parameters.py
│   └── constraints.py
├── controllers/
│   ├── rh_milp.py
│   ├── feedback.py
│   └── rbc.py
├── interface/
│   ├── mapping.py
│   ├── pyads_interface.py
│   └── safety.py
├── experiments/
│   ├── S0_full_horizon/
│   ├── S1_rh_ideal/
│   ├── R1_physical_ideal/
│   ├── R2_physical_available/
│   ├── R3_physical_feedback/
│   └── R4_rbc/
├── data/
│   ├── calibration/
│   └── evaluation/
├── analysis/
│   ├── effects.py
│   ├── runtime.py
│   ├── residuals.py
│   └── figures.py
├── results/
├── configs/
└── docs/
```

---

# 34. Automatic experiment logging

For every RH cycle, store at least:

```text
experiment_id
timestamp
controller_case
price_scenario
horizon
control_interval
solver_runtime
solver_status
optimality_gap
fallback_used
objective
heat_demand
price
storage_state
plant_measurements
model_predictions
model_parameters_before
model_parameters_after
residuals
setpoints
```

This logging structure is essential for reconstructing the simulation-to-plant gap.

---

# 35. Key methodological rules for the coding agent

The coding agent must obey the following rules:

1. **Do not change the nominal MILP while implementing the baseline cases.**
2. **Do not use future plant measurements in causal controller decisions.**
3. **Do not directly modify the schedule using residuals.** Feedback modifies the model representation; the next MILP then generates the schedule.
4. **Do not tune RBC parameters on the final evaluation period.**
5. **Do not tune feedback parameters on the final evaluation period.**
6. **Do not use different service requirements for different controllers.**
7. **Do not count solver timeout as successful optimization.**
8. **Do not silently replace a failed MILP with an arbitrary solution.** Use the predefined fallback and log it.
9. **Do not introduce a forecasting model comparison unless explicitly requested.**
10. **Do not call the feedback mechanism “online optimization”.**
11. **Do not change the physical plant or PLC logic only for one controller case unless the experiment explicitly tests that feature.**
12. **Keep all experiment definitions configuration-driven.**
13. **Every result must be traceable to a stored experiment configuration and output.**

---

# 36. Core narrative of the paper

The final paper should tell one coherent story:

> A MILP can promise substantial savings when evaluated with a nominal model and complete future information. However, the numerical objective is not automatically the physically achievable objective. Moving to a receding-horizon controller introduces causal decision making; transferring the controller to a physical plant introduces model–plant mismatch; restricting the controller to information actually available at the decision time introduces additional uncertainty. A closed-loop measurement mechanism can correct selected plant-model parameters and recover part of this lost performance. Finally, the resulting predictive controller must demonstrate a meaningful advantage over a good rule-based benchmark while remaining computationally feasible for real-time operation.

The scientific contribution is therefore not simply:

> “We implemented an MILP on a PLC.”

It is:

> **“We quantify, decompose and partially recover the gap between numerical optimization potential and physically realized performance.”**

---

# 37. Final checklist before manuscript submission

## Scientific consistency

- [ ] S0 and S1 use exactly the intended nominal model.
- [ ] S1 and R1 differ primarily by simulation vs physical plant.
- [ ] R1 and R2 differ primarily by ideal vs available future information.
- [ ] R2 and R3 differ primarily by feedback-based model correction.
- [ ] R3 and R4 differ primarily by controller concept.
- [ ] All cases use identical service requirements.
- [ ] Initial and terminal storage conditions are controlled.

## Causality

- [ ] No future measurements leak into decisions.
- [ ] Feedback uses only past/current measurements.
- [ ] Model correction affects the next optimization cycle.

## Real-time operation

- [ ] 15 min re-optimization is defined.
- [ ] Runtime is logged for every cycle.
- [ ] Timeout / fallback behavior is predefined.
- [ ] Fallback events are reported.

## Feedback

- [ ] Parameters are physically interpretable.
- [ ] Parameter bounds are defined.
- [ ] Update rule is frozen before final evaluation.
- [ ] Residuals are logged.

## Benchmark

- [ ] RBC is tuned separately.
- [ ] RBC parameters are frozen.
- [ ] RBC is a credible practical benchmark.

## Reporting

- [ ] Absolute and relative results are reported.
- [ ] Effect decomposition is reported.
- [ ] Runtime feasibility is reported.
- [ ] Physical tracking / residuals are reported.
- [ ] Limitations are explicitly discussed.

---

# 38. One-slide summary for the project / paper pitch

**Research question:**

> How much of the numerical MILP potential remains physically realizable after the transition to causal RH operation and PLC-integrated plant control?

**Method:**

```text
S0       S1        R1        R2        R3
│        │         │         │         │
Full →   RH →      Plant →   Available → Feedback
MILP     MILP      + ideal   information + model
                                  │       correction
                                  │
                                  ▼
                                 R4
                              RBC benchmark
```

**Quantified effects:**

\[
\Delta_{RH},\quad
\Delta_{Plant},\quad
\Delta_{Info},\quad
\Delta_{Feedback},\quad
\Delta_{MILP-RBC}
\]

**Core message:**

> **From numerical optimization potential to physically realized performance — quantified step by step.**
