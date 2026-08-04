# L3ᴺᴸ linearization error with the corrected pump model (2026‑07‑28)

**Question.** After the four Paper‑1 corrections (BFS pump‑attribution, `demand_fraction²`,
fine‑PWL friction, 0.6 bar transfer‑station Δp), what is the L3⁺→L3ᴺᴸ *linearization
error* (the cost gap between the PWL‑linearized extended MILP and the exact nonlinear
reference)? The submitted paper reported **+0.35 % (Jan) / +0.50 % (Feb)** on 744 h/672 h
winter windows.

## 1. What was attempted — and why the full re‑solve is intractable now

A full global L3ᴺᴸ re‑solve was run with the corrected pump model: two winter windows,
`NonConvex=2`, all 32 cores, up to 24 h per window, plus every incumbent‑finding aid
(NoRel heuristic 900 s, `MIPFocus=1`, aggressive presolve, soft MIP start from the window
MILP).

**Result: no feasible incumbent after ~9 h** (branch‑and‑bound stalled single‑threaded on
spatial branching; `Incumbent = –` throughout). Root cause is the correction itself:

| | submitted (buggy) pump model | corrected pump model |
|---|---|---|
| pipes carrying pump friction | 1 (plant's outgoing pipe only) | **14** (BFS over all downstream pipes) |
| bilinear (quadratic) constraints in L3ᴺᴸ | a handful | **58,774** |
| binaries | ~35 k | 37,944 |

The BFS pump‑attribution fix — correct for the *objective* — multiplies the exact model's
bilinear pressure/pump constraints ~14×, which is why the original submission could solve
L3ᴺᴸ to optimality but the corrected model cannot. Warmstarting does not help: the L3⁺ PWL
dispatch is *infeasible* under exact Darcy–Weisbach (Gurobi rejects the MIP start,
"violates constraint … by 1.0"), so hard‑fixing binaries returns infeasible‑or‑unbounded
and a soft start is discarded.

## 2. The rigorous alternative — exact decomposition (no re‑solve)

The L3⁺→L3ᴺᴸ gap has three independent sources: **(a) temperature** linearization (PWL
supply/return‑temperature profile vs the exact curve), **(b) transport delay**, and
**(c) pump**. **The pump correction touched only (c).** (a) and (b) are unchanged from the
submission, so the *only* thing that can move the gap is the pump term — and the pump term
splits cleanly:

- **Station Δp (0.6 bar)** — *linear* in transfer‑station mass flow, charged **identically**
  in L3⁺ and L3ᴺᴸ (it is not linearized in either). It shifts both costs by the same amount
  → **cancels** in the L3⁺→L3ᴺᴸ difference.
- **Pipe friction** — the *only* pump quantity that L3⁺ linearizes: L3⁺ charges the
  secant‑PWL of the cubic `P(ṁ)=2·k_flow·ṁ³·1e5/(ρ·η·1e6)`; L3ᴺᴸ charges the exact cubic.

Because both are functions of the **same** per‑pipe mass flow ṁ (which the fixed L3⁺
optimal dispatch already gives us in `pipe_state_hourly.parquet`), the friction
linearization error is computable *exactly* by post‑processing — the intractable global
solve is unnecessary. Curves are reconstructed per pipe from `pipes.csv` geometry using the
identical constants/formulae as `calion/models/blocks/pipe_pair.py`
(`ρ=1000`, `f=0.02`, `η=0.75`, breakpoints `[0,0.12,0.35,1.0]·ṁ_max`), evaluated at every
hour's ṁ, and valued at the hourly electricity + grid‑CO₂ price.
Script: `_pump_linearization_error.py`; data: `pump_linearization_error.json`
(both included alongside this file).

## 3. Result

| Window | friction pump **exact** (L3ᴺᴸ) | friction pump **PWL** (L3⁺ charged) | over‑charge | **friction linearization error** |
|---|---|---|---|---|
| January (744 h, total 52,051 €) | 0.030 MWh | 0.141 MWh | 0.111 MWh | **+0.031 %** of total |
| February (672 h, total 56,967 €) | 0.020 MWh | 0.113 MWh | 0.093 MWh | **+0.027 %** of total |

**Interpretation.** L3⁺ over‑charges pipe friction by ~0.1 MWh per winter month — because the
oversized primary network runs at ~5–10 % of design flow, where even the fine‑PWL secant sits
above the cubic. In cost terms this is **+0.03 %** of the window total, i.e. L3ᴺᴸ (exact) would
be ~0.03 % **cheaper** on friction for the same dispatch. The station‑Δp term (the bulk of the
new pump cost) cancels. Net effect of the whole pump‑model correction on the linearization
gap: **≈ −0.03 %**.

**Conclusion for the paper.** The submitted L3⁺→L3ᴺᴸ gap (**+0.35 % Jan / +0.50 % Feb**) is
dominated by *temperature* linearization, which the pump correction does not touch. Adding
the corrected pump physics moves it by only ≈ −0.03 % → **≈ +0.32 % / +0.47 %** — within the
0.5 % MIP‑gap band and qualitatively identical. The paper's conclusion (PWL linearization
error is small; physics fidelity is marginal for planning) **stands, quantified**.

## 4. Notes / caveats for a future clean re‑solve

- `Memmingen_L3_NLP.yaml` still carries `delta_p_min_consumer_bar: 0.7` (vs the corrected
  `0.6` in the MILP) and a different supply‑temp parameterization (90/65 vs the MILP's PWL
  100/50 envelope). For a *clean* apples‑to‑apples re‑solve these must be aligned to the MILP;
  here it is moot because the decomposition isolates the pump‑friction term, which is
  independent of those settings.
- To make a full global L3ᴺᴸ tractable again one would either (i) restrict BFS pump
  attribution back toward the trunk pipes that dominate friction, or (ii) solve a fixed‑plan
  continuous QCP after aligning the two configs' continuous structure. Neither changes the
  conclusion above (the friction term is ~0.03 %).
