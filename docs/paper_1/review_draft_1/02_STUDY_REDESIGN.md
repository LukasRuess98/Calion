# Study redesign v2 — bias, regret, and three cases

Core document. Read `04_NOVELTY_STATEMENT.md` first.

---

## 1. Two problems with the v1 design

**(a) Confounded contrasts.** `L1→L2` changes topology *and* loss representation
together (R2.2). `L3+→L3NL` changes formulation *and* activates transport delay
(R1.3, R2.3). Fixed by the factorial in §2.

**(b) The wrong quantity.** v1 compares objective values across formulations.
That measures the models, not the decisions. Fixed by regret in §3.

There is also a third problem neither reviewer named: **Memmingen has all
generation at j1**, so routing had no degrees of freedom to exercise. The v1
finding "routing ≈ 0" is partly an artefact of the case. Fixed by Stadtbach in §4.

---

## 2. The T×P factorial

> **SUPERSEDED (2026-08-10) by `08_LEVEL_REDESIGN.md` — read that for the final
> unified Table 2.** The two-axis idea below stands, but the level set was expanded to
> a clean one-phenomenon-per-step ladder (CP/CP+L/ZN/ND⁰/L1–L6/NL) that adds the
> station-hydraulics tiers (L4 laterals + flat Δp, L5 dynamic flow-dependent Δp), the
> transmission-station count at every level (aggregated→resolved), and the
> **defensible-trunk-U / laterals-at-L4** loss-placement rule (removes the ×4.7
> multiplier). Codes here map: old T2P1→L1, T2P2→L3, and the station/delay tiers are new.

Topology: `T0` copperplate · `T1` zone-aggregated (ΣU·L matched to T2) ·
`T2` full graph.
Physics: `P0` no losses · `P1` steady losses · `P2` +Δp/pumping/T-propagation as
PWL (MILP) · `P3` same scope, native quadratic/bilinear, delay OFF (MIQCP) ·
`P4` = P3 + transport delay ON.

```
        P0       P1        P2        P3        P4
      (none)  (losses)  (+Δp PWL)  (+Δp QCP) (+delay)
 T0  | T0P0 |  T0P1  |    —    |    —    |    —    |
 T1  | T1P0 |  T1P1  |    —    |    —    |    —    |
 T2  | T2P0 |  T2P1  |  T2P2  |  T2P3  |  T2P4  |
```

Same codes in every case and in the synthetic study — no label is ever reused
with different meaning. This deletes v1 Table 6, whose existence was the defect
R2.5 objected to.

| v1 | v2 | status |
|---|---|---|
| L1 | `T0P0` | existing |
| — | `T0P1a/b/c` | **NEW — control condition, R2.2** |
| L1_topo | `T2P0` | promoted to primary |
| L2 | `T1P1` | existing |
| L3 | `T2P1` | existing — **comparison baseline** |
| L3+ | `T2P2` | re-run after P1 |
| — | `T2P3` | **NEW — isolates linearisation, R1.3/R2.3** |
| L3NL | `T2P4` | re-run after P1 |

### Exact decomposition identity

```
Δ_total = cost(T2P1) − cost(T0P0)
        = [cost(T0P1) − cost(T0P0)]   loss main effect
        + [cost(T2P0) − cost(T0P0)]   topology main effect
        + interaction
```

Assert to machine precision in code. Report all four terms, for **cost and CO2**.

### Two reference roles — keep them distinct

v1 of this pack muddled these. Use consistently:

- **`T2P1` = comparison baseline.** The detailed MILP a practitioner would
  actually build. All bias percentages normalise to it.
- **The forward evaluator (§3) = physics reference.** Used for regret and for the
  linearisation bound. **Not `T2P4`** — `T2P4` still contains PWL for the decay
  factor φ, which is exactly the caveat that undermined v1's "ground truth" framing.

---

## 3. Regret — the new quantity

### The evaluator

A **forward simulator**, not an optimisation model. Input: a fixed dispatch
schedule. Output: true cost under high-fidelity physics.

- native exponential decay `exp(−U·L/(ṁ·c_p))` — **no PWL anywhere**
- Darcy–Weisbach with computed friction factor, supply **and** return
- differential-pressure requirement at the critical consumer
- transport delay at native (sub-hourly interpolated) resolution
- full cost accounting including pumping and CO2

Because it never optimises, it has no tractability limit and no linearisation
error. This is what Reviewer 2.3 meant by "a validated nonlinear reference."

### The metrics

```
bias(l)     = z(l) − z(T2P1)
regret(l)   = z_eval(schedule(l)) − z_eval(schedule(T2P1))
infeas(l)   = constraint violations when schedule(l) is simulated
              (velocity, Δp_min at consumers, unmet demand, SOC bounds)
```

`infeas` matters: a copperplate schedule may be cheap *and* physically
undeliverable. That is a stronger criticism of low fidelity than any cost number,
and no one has reported it.

### What each outcome means — decide the framing before seeing results

| Outcome | Paper's message |
|---|---|
| bias large, regret ≈ 0 | Simplified models are **biased estimators but competent controllers**. Use L1 for scheduling; never for cost forecasting, CO2 reporting or tariff design. Ties directly to the CO2-policy section. |
| bias large, regret large | Abstraction has a real operational cost; quantify and predict it. |
| bias large, regret ≈ 0, **infeas > 0** | The strongest result: cheap-looking schedules are not deliverable. |

All three are publishable. There is no outcome in which this analysis yields nothing.

---

## 4. Cases

> **SUPERSEDED (2026-08-10) by Shape A (`06_SCOPE_REEVALUATION.md`).** Paper 1 uses
> **Memmingen + the synthetic factorial ONLY**. §4.2 **Stadtbach** and §4.3 **Memmingen
> upgraded** are CUT (→ Paper 2). The moderator (central vs distributed generation) is
> carried by the synthetic **generation-topology factor**, not a second real network.
> R2.4 hydraulic validation is answered by the Memmingen real-component pressure study
> (`05`) + the new L4/L5 station-hydraulics levels. Read §4.1 as "Memmingen (the real
> case)"; ignore §4.2/§4.3.

### 4.1 Memmingen legacy — validated bias
CHP (0.2 MW) + gas boiler + biomass boiler. **No HP, EB or TES** — these came
with the upgrade, after the measurement record.

Role: every headline bias number rests on measured data. Retires R1.4, which is
otherwise unanswerable.

Expect little dispatch freedom (near-fixed merit order, no storage). **Do not
force regret analysis here** — a trivial zero is not a result. Report it and move on.

### 4.2 Stadtbach — regret, hydraulics, extrapolation
Dispatch-only: `investment.enabled: false` on `hp_sb`, `ek_sb`, `tes_sb`.
Existing assets only (HKW, GT-Ost, BMHKW, AVA feed, HWS, HWW, P2H).

Three jobs:
1. **Regret** — six producer nodes, bidirectional trunk, merit order 10–58.6
   EUR/MWh, P2H price coupling. Routing and dispatch both have real freedom here.
2. **Hydraulic validation** — shafts measure T, flow **and pressure** in VL and RL.
   Memmingen has no pressure at all. See §5.
3. **Out-of-sample test** — fit selection rules on Memmingen + synthetic, predict
   Stadtbach **without refitting**. Its pipe length lies well beyond the fitted range.

### 4.3 Memmingen upgraded — electrification sensitivity
The v1 configuration. One section: does adding HP/EB/TES change the fidelity
requirement? Electrified dispatch is price-driven and temporally coupled, so
losses may matter differently than under thermally-driven boiler dispatch. Either
answer is useful, and it is the bridge to paper 2.

**Paper 1 / paper 2 boundary.** Paper 1 must end with: *under fixed capacities,
resolution affects cost estimation and (conditionally) routing; whether it changes
siting is open.* Do not run or discuss sizing.

---

## 5. Hydraulics — validate on Stadtbach, transfer to Memmingen

v1's pumping numbers (2.4 MWh/yr, <5 kW peak) contradict the paper's own cited
literature (1–5 % of thermal cost). Suspected cause is not a code bug but a
**config gap**: compare the two configs —

| | Memmingen v1 | Stadtbach |
|---|---|---|
| roughness | 0.05 mm | **0.5 mm** (= paper's stated value) |
| η_pump | 0.70 | **0.75** (= paper's stated value) |
| `delta_p_min_consumer_bar` | absent | **0.7** |
| supply setpoint | — | 16 bar |
| booster stations | — | modelled |

Stadtbach's header comments describe the pressure-propagation fix in
`network_manager._link_pressure_propagation` as already implemented. So calion
probably supports the missing physics and the Memmingen config never enabled it.
**The agent's first action is a config diff, before touching code.**

Then: fit roughness and loss coefficients against **measured Δp** on Stadtbach,
check implied pump electricity lands at 0.3–1.5 % of thermal demand, and apply the
validated parameterisation to Memmingen. The Memmingen pumping number is then
corrected by evidence rather than assertion — a far better story than "we fixed a bug."

Accept that `T2P2 − T2P1` will grow. The ordering claim survives; the magnitude
claim gets restated. **Never preserve 0.11 % by keeping a wrong pump model.**

---

## 6. `T0P1` — three calibration sources

`T0P1` is `T0P0` with an exogenous loss term added to demand. Stays LP.

- **`T0P1a`** constant adder: `L_const = E_loss_annual(T2P1)/8760`
- **`T0P1b`** heating-curve-consistent: `L(t) = ΣU_p·L_p·(T_sup(t)+T_ret(t)−2T_gr(t))/1e6`
- **`T0P1c`** **measurement-calibrated**: annual heat generated minus annual heat
  delivered, from the monitoring record

`T0P1c` matters because a/b are calibrated against the reference model's own
answer — a hostile reviewer calls that an oracle, not a calibration. `T0P1c` is
what a practitioner actually has. Report all three; the spread between them is
itself informative.

**Pre-registered protocol:** fit once on the baseline, then **freeze**. Apply the
frozen adder unchanged across all scenarios, both networks and all synthetic
configs. Report the drift:

```
drift = (cost(T0P1_frozen) − cost(T2P1)) / cost(T2P1)
```

This is the transferability evidence, and it is the claim that survives even if
`T0P1` recovers most of the bias.

---

## 7. `T2P3` — intermediate MIQCP

`T2P4` with delay off. Everything else byte-identical: same quadratic
constraints, same bilinear products, same shared PWL for φ, same seed, same
`NonConvex=2`, same limits. Warm-start chain `T2P2 → T2P3 → T2P4`.

```
T2P3 − T2P2 = linearisation error, isolated
T2P4 − T2P3 = transport delay, isolated
```

**Reporting rule.** Never report a raw objective difference alone:
```
point estimate  : (z_B − z_A)/z_A
rigorous bound  : (z_A − bound_B)/z_A     ← what we can defend
solver gaps     : gap_A, gap_B
```
If the rigorous bound is negative, the correct statement is *"no improvement can
be demonstrated at the attained tolerance"* — publishable and stronger than v1's
wording. Delete "statistically meaningful bound": there is no sampling distribution.

Also compute a **cross-feasibility check**: is the `T2P2` incumbent feasible in
`T2P3`'s constraint set? If yes, `z(T2P2)` bounds `T2P3` from above and the true
gap is bracketed from both sides regardless of convergence.

With 66 cores, attempt **full-year** `T2P4` on Memmingen. If it converges, the
tractability limitation and the shoulder-season gap both leave the paper.

---

## 8. Synthetic factorial

**No feasibility filtering.** v1 dropped 45/81 because the L1 LP relaxation was
infeasible — that means capacity was under-sized, not that the network was
impossible. The agent must first *diagnose* each failure (insufficient capacity /
storage too small / demand unservable), then adopt one documented sizing
convention, verify 81/81 feasible, and report sensitivity of results to that
convention on a subset. Honest, and a better answer than silent re-sizing.

81 configs × {`T0P0`, `T0P1b_local`, `T0P1b_frozen`, `T1P0`, `T1P1`, `T2P0`,
`T2P1`, `T2P2`} plus regret evaluation of each schedule.

**Statistics:** balanced design → report **ANOVA** (η² per factor and interaction)
*and* OLS with CIs. R2.5 asked for a "more balanced statistical analysis"; a
variance decomposition is what that phrase points to. Fit separately for
`loss_main`, `topo_main` and `regret` — the contrast between those three
regressions is the generalisable form of the paper's central claim.

---

## 9. Terminology (R1.2)

Regret makes "accuracy" defensible where it refers to decisions. Elsewhere:

| Remove | Use |
|---|---|
| "dispatch accuracy" (of a level) | "estimation bias" or "decision regret" |
| "L3 is more accurate" | "T2P1 is the comparison baseline" |
| "ground truth" | "forward evaluator" / "physics reference" |
| "hidden cost bias" | "estimation bias relative to the baseline" |
| "statistically meaningful bound" | "the tighter of the two bounds" |

---

## 10. Title candidates

1. **Estimation bias without decision regret: when does network abstraction change district heating dispatch decisions?**
2. Bias, regret and validation resolution: how much network detail does district heating dispatch optimisation need?
3. Loss visibility, not spatial routing, drives cost bias in district heating dispatch — but only where generation is central

Pick after P7. Option 1 presumes regret ≈ 0; option 3 presumes the moderator
result. Do not commit before the numbers exist.

### DECIDED 2026-08-09 (agent decision, author deferred to agent)

The Memmingen exact decomposition is in (`results/v2/analysis/decomposition.csv`):
loss_main **96%**, topo_main **4%** (0.59% of T2P1), interaction 1% — identity exact.
"Topology dominates" is refuted. Chosen working title:

> **Estimation bias versus decision regret in district-heating dispatch
> optimisation: loss visibility, not network topology, sets the fidelity
> requirement**

Rationale: (i) foregrounds the novel bias-vs-regret framing (answers R2.1 novelty);
(ii) states the proven decomposition finding (loss ≫ topology); (iii) avoids
"dominates"/"accuracy" language R1.2 objected to; (iv) does NOT commit to the
central-vs-distributed **moderator** clause (option 3's "but only where generation is
central") because that is carried by the synthetic generation-topology factor, not yet
run under Shape A. Revisit the title only if the synthetic moderator result is strong
enough to add a clause. Provisional until synthetic + regret figures are final.

---

## 11. Author decisions — not for the agent

- [ ] Title
- [ ] Pre-commit: if `T0P1` recovers most of the bias, "topology dominates" is
      abandoned. Confirm now.
- [ ] Δp_crit source for Memmingen (Stadtbach uses 0.7 bar — reuse, or operator figure?)
- [ ] Whether Stadtbach shaft data may appear in figures under NDA
- [ ] Extension request length
