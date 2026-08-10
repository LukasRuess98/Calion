# P1 — Hydraulic model: validate on Stadtbach, transfer to Memmingen

**Depends on:** P0, P12 · **Blocks:** P4, P5, P11
**Output:** `revision/audit/P1_hydraulics.md`, code/config changes, sanity CSV
**Priority: HIGHEST** together with P11.

## Context

Reviewer 2 wrote that "the relatively large flow errors, strongly calibrated
pipe-loss multipliers, and exceptionally low pumping-energy estimate raise
questions about physical fidelity," and asked us to clarify supply and return
networks, substations, valves, pressure requirements and pump characteristics.

The v1 paper reports 2.4 MWh/yr of pump electricity and <5 kW peak for a 12 MW
network — while citing Frederiksen & Werner for 1–5 % of thermal energy cost.
Two orders of magnitude apart. Treat as a suspected defect, not a finding.

**New information that changes the approach:** Stadtbach has **measured pressure
in VL and RL at shafts**. Memmingen has none. So the hydraulic model can be
validated where there is pressure data and the validated parameterisation
transferred to where there is not.

---

## Step 1 — Config diff BEFORE touching code

Compare `network:` blocks of the Memmingen and Stadtbach configs:

| | Memmingen v1 | Stadtbach |
|---|---|---|
| `pipe_roughness_mm` | 0.05 | **0.5** (= paper's stated value) |
| `pump_efficiency` | 0.70 | **0.75** (= paper's stated value) |
| `delta_p_min_consumer_bar` | absent? | **0.7** |
| supply pressure setpoint | ? | 16 bar |
| `max_pressure_drop_bar` | ? | 2.0 |
| booster pump stations | — | modelled at j_pss / j_psw |
| `physics.pressure_drop` | ? | true |

The Stadtbach config comments describe a pressure-propagation fix in
`network_manager._link_pressure_propagation` (secondary producers get a
pump-boosted supply pressure floored at setpoint rather than pinned; node-to-node
propagation as an inequality). **Determine whether calion already supports the
differential-pressure requirement and Memmingen simply never enabled it.**

If yes, this task is largely a config correction plus re-runs, not a rework.
Report this as the finding either way — "the capability existed and the case
config did not use it" is an honest and easily explained correction.

## Step 2 — Unit-chain trace

Follow `Q_p,t [MW] → ṁ_p,t [kg/s] → Δp_p,t [Pa] → P_pump [MW]`. Verify:
- every `1e6` W↔MW conversion
- `f_D`: computed (Colebrook / Swamee–Jain) or fixed? at what roughness?
- inner vs outer diameter
- `ρ` appears exactly once: `P = ṁ·Δp/(ρ·η)`
- supply **and** return both in the sum
- `Δp_crit` at the hydraulically worst consumer is included

Unit test on a hand-computed single pipe for each fix.

## Step 3 — Validate against measured Δp (Stadtbach)

Using `shaft_pairs.csv` from P12, ranked by confidence:

1. For each valid pair and each hour with good data, compute measured
   `Δp = p_a − p_b` (VL and RL separately) and the corresponding measured flow.
2. Compute modelled Δp for the same segments at the same flow, using the
   steady-state Darcy–Weisbach chain **without any optimisation**.
3. Handle elevation: if `elevation_delta_m` is known, apply `ρ·g·Δh`. If unknown,
   fit a constant offset per pair and **report it as a fitted nuisance parameter**,
   including its magnitude relative to friction — if the offset dominates, that
   pair is not evidence and must be dropped.
4. Fit **roughness** (and, if warranted, a per-DN correction) by minimising MAE
   over the pairs. Report the fitted value against the config's 0.5 mm and against
   literature for aged steel DH pipe.
5. Report MAE, RMSE, bias, R², and coverage, **split into fitted and held-out
   pairs**. Fitting and reporting on the same pairs is in-sample error, which is
   exactly the criticism to avoid here.
6. Produce Figure F11: modelled vs measured Δp, coloured by flow, 1:1 line.

## Step 4 — Pump-power sanity gate

Write `revision/audit/pump_sanity.csv` for both networks:

| quantity | plausibility band |
|---|---|
| peak Δp across critical path [bar] | 1.5–6 |
| pump electricity / thermal demand [%] | 0.3–1.5 |
| pump cost / total cost [%] | 0.2–1.5 |
| max pipe velocity [m/s] | ≤ 2.5 (config allows 3.0) |

For Stadtbach, additionally check the modelled pump power against the documented
pump ratings in the config comments (PSS 858 m³/h at DN400 v≈1.9 m/s; PSW
700 m³/h at DN500 v≈1.0 m/s). Those are real operating data and a strong check.

**If the model falls outside a band, diagnose and report. Never tune to land inside.**

## Step 5 — Transfer to Memmingen

Apply the validated parameterisation (roughness, friction correlation, η_pump,
Δp_crit convention, substation boundary) to Memmingen. Document each transferred
value and its justification. Where Memmingen genuinely differs (smaller DN, shorter
paths, different age class), say so and justify the deviation.

Re-run `T2P1` and `T2P2` on Memmingen; report the new `T2P2 − T2P1` against
v1's +0.11 %. Expect growth. The ordering claim (losses ≫ hydraulics) survives;
the magnitude claim gets restated.

## Report

`revision/audit/P1_hydraulics.md`: config diff verdict · unit-chain trace ·
Stadtbach Δp validation with in-sample/out-of-sample split · fitted roughness ·
sanity table for both networks · transfer justification · new Memmingen gap ·
**a publication-ready paragraph** for `GAP:HYDRAULIC-DETAIL` covering supply and
return circuits, the differential-pressure requirement and its source, the
substation/valve boundary, and pump characteristics.
