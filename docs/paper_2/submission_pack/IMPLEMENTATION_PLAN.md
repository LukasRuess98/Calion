# Paper 2 — Rework Implementation & Paper Plan

**Author-facing plan. Date 2026-08-30.** Everything below is what we will run, why,
and what we expect. Target journal: *Energy Conversion & Management*.

---

## 0. One-paragraph summary
We reposition Paper 2 from an implicit "comparison of network characteristics"
(which two case studies cannot support) to **"a multi-fidelity DH-electrification
optimisation *framework*, demonstrated on two contrasting real networks."** The
**designed centrepiece is an electrification sweep** (cost/CO₂/COP vs heat-pump
penetration — a *controlled* factor, not an accidental outcome). **Network
structure and siting stay a key element** (the siting-landscape result, F6). We
re-solve everything with a **tighter MIP gap** (coarser time resolution + big-M
tightening → target ≤1–2% vs today's 4–9%), which also removes the incumbent
variance that currently muddies fine comparisons. The two networks are framed as
**illustrative endpoints**; the MIP-gap and single-year scope are stated up front
as limitations.

---

## 1. Repositioning & contribution

**Claim we CAN defend:** a framework + method (fidelity levels L1–L3+, the
tractable linearised formulation) that, on two real networks, quantifies the
heat-curve→COP→cost coupling, the value and non-obviousness of HP/TES siting, and
the cost/CO₂ trade-off of electrification level.

**Claims we DROP (n=2 cannot support):** "network size/topology *drives* X."
Any Memmingen-vs-Stadtbach difference is confounded by size, topology, generator
mix, and demand shape simultaneously. We present the two networks as endpoints and
phrase cross-network differences as *observations*, not causal conclusions.

**Four significant findings to feature (all established this cycle):**
1. **Memmingen electrification is economic** (+44.8% TAC, +20.8% CO₂) — after
   fixing a baseline-matching bug that had inverted the sign.
2. **The heat-curve's economic benefit is electrification-dependent** — lowering
   the curve always raises COP, but only cuts cost where the HP carries real load
   (Memmingen −4.4%; Stadtbach ≈flat, HP <1% of supply). *(new F4)*
3. **Siting is decisive** — the wrong HP/TES node costs up to **77× (Stadtbach) /
   4× (Memmingen)** the optimum; the optimum is non-obvious. *(new F6)*
4. **Stadtbach is a net electricity exporter** (CHP), so higher power prices *lower*
   its cost — opposite sign to Memmingen. *(F7)*

---

## 2. Revised paper structure

| § | Title | Content | Elements |
|---|---|---|---|
| 1 | Introduction | Motivation, gap, framework-contribution framing, scope | — |
| 2 | Model formulation | Nodal heat/mass balance, HK stages, HP/EK/TES, investment, **L3+ + McCormick as numbered equations** (former F1) | eqs. |
| 3 | Case studies & experimental design | The two networks as endpoints; **the DoE (§3.3 below)**; parameters | T1, T2, F2 |
| 4 | Results — electrification spine | **Electrification sweep (centrepiece)**; heat-curve coupling; cost/CO₂ vs baseline | **F-elec (new)**, F4, F5, T3, T4 |
| 5 | Results — siting | **Siting landscape**; fixed vs endogenous; storage cycling | F6, F9 |
| 6 | Discussion | Sensitivity; why electrification level governs value; limits (MIP gap, single year, n=2) | F7, T5 |
| 7 | Conclusions | Framework + transferable findings; no new results | — |

Supplement: F3 capacity surface, F8 spatial profile, Teil-6 pump comparison, full 46-row KPI tables.

---

## 3. Design of experiment (the runs)

All studies use factors defined **identically in both networks**. Every reported
comparison will carry its MIP gap; comparisons whose ΔTAC is within the gap are
**not** ranked.

### Study A — Electrification sweep *(centrepiece, NEW)*
- **Factor:** HP nameplate capacity fixed at levels {0, 20, 40, 60, 80, 100}% of a
  network-specific ceiling (⇒ electrification share as a controlled x-axis).
- **Held fixed:** siting at each network's optimum; HK2; TES sized by the model.
- **Machinery:** the proven fixed-capacity dispatch path (as in `capacity_sweep.py`).
- **Runs:** 6 levels × 2 networks × 3 HK (0/1/2) = **36** (dispatch-class solves).
- **Output → new central figure "F-elec":** TAC, LCOH, CO₂, annual COP, HP-share
  vs electrification level, per network.

### Study B — Heat-curve coupling *(F4)*
- Ceteris paribus, HK0/1/2 at fixed siting, at a *meaningfully electrified* design.
- **Runs:** 3 × 2 = **6** (reuse; re-solve at tight gap).

### Study C — Siting landscape *(F6 — KEY element, kept)*
- Full enumeration of HP × TES candidate nodes at HK2.
- **Runs:** Memmingen 6×6 = 36, Stadtbach 5×5 = 25 → **61**.

### Study D — TES configuration factorial
- **Factors (crossed):** TES location {none, central, at-WP, free} × charging
  {normal, hot} × HK {0,1,2}. Disentangles charging mode from siting (currently
  confounded in S3/S5/S7).
- **Runs:** ≈ **30–40** per the feasible/finite subset (drop infeasible combos).

### Study E — Sensitivity tornado *(F7)*
- **Fixed-design tier-2**: freeze the optimum, re-dispatch LP per parameter variant
  (c_el, c_co2, c_gas ±; discount ±2pp). Deterministic; captures operational response.
- **Runs:** ≈ 5 params × 2 dirs × 2 networks = **~20** dispatch-class solves.

### Baselines & headline scenarios
- BC-MM, BC-SB + the canonical 40-run matrix re-solved for T3/T4 (**~42**).

**Total ≈ 200 solves**, but at the tighter resolution most are **minutes**, not
hours (see §4). Compute is dominated by Study C + the canonical matrix.

---

## 4. Tighter-MIP-gap methodology

**Diagnosis (from a 24 h Memmingen log):** 78,842 binaries (~9 × 8,760 h), each
B&B node solves a 1.6 M-column LP, only 11.7 k nodes explored in a day, final gap
3.8%; the root LP dual bound starts at −3.8×10¹⁰ (very loose relaxation). It is a
**size + loose-relaxation** problem, not a fundamentally intractable one.

**LOCKED DECISIONS (2026-08-31):** canonical code = **`e8e445e` worktree**; gap
target = **aim 0.1%, accept tightest unbiased gap**; electrification sweep =
**fix HP capacity at levels of network peak**; single year = **disclosed limit**.

**Levers (revised after prototype):**
1. ~~**Coarser time resolution** `dt_h`~~ — **REJECTED (prototype 2026-08-31).**
   MM-S1-HK2 TAC vs 1 h (328,948 €): 2 h = 290,351 € (**−11.7%**), 3 h = 245,453 €
   (**−25.4%**), and it did *not* reliably tighten the gap (2 h came back 16.7%).
   Naive resampling averages away demand peaks → systematically under-costs. Dead
   on both counts. (Proper *weighted* typical-days with the peak day preserved would
   avoid this — see lever 4.)
2. **Big-M tightening — PRIMARY (safe, no answer change).** Root cause of the
   −3.8×10¹⁰ bound = `max_import_mw = max_export_mw = 5000 MW` for both networks,
   vs peaks of ~5 MW (MM) / ~200 MW (SB) — the grid is oversized 25–1000×, so the
   LP relaxation imports/exports absurd amounts. Tighten to a realistic multiple of
   peak electric load (the optimum never uses more). Testing on MM-S1-HK2 (grid
   capped 50 MW, MIPGap 0.001). *Also* tightens the `grid_mode` big-M implicitly.
3. **Relax redundant binaries.** `min_uptime/downtime/startup = 0` (unset) → the
   `u`/`v` startup binaries are dead; `grid_mode` (buy-XOR-sell) is never binding at
   optimum → relax to continuous. NOTE: `on` binaries are load-bearing (`min_load`
   0.1–0.3 is set) → keep. Storage charge/discharge-mode: relax only if the
   shared-port cut already enforces exclusivity (to verify).
4. **Weighted typical-days** (proper, peak-preserving) — the correct route to <1%
   *without* bias, but a real feature build (stub only today). Reserved if levers
   2–3 don't reach target.
5. `MIPGap` target **0.001**; `MIPFocus=3` if the bound remains the bottleneck.

**RESULT (2026-08-31 experiments):**
- **Big-M fix WORKS and is applied.** Grid capped 5000→50 MW (MM) / →500 MW (SB):
  root LP bound **−3.8×10¹⁰ → +228,992** (finite/meaningful), binaries **78,842 →
  52,572** (presolve). The bound is no longer garbage, so B&B can actually converge.
- **But it is NOT sufficient for 0.1%.** The root LP is still ~30% below the optimum
  (bound ~232 k vs true ~329 k), driven by the load-bearing `min_load` on/off binaries
  over 8,760 h. Binary relaxation buys almost nothing: `u`/`v` startup binaries don't
  exist (`min_up/down = 0`), `on` binaries are load-bearing (`min_load` set), and
  `grid_mode` is minor and not the gap-driver.
- **0.1% requires proper weighted typical-days** — confirmed a real feature build: the
  objective weights OPEX by a *scalar* `dt_h`, so per-day weighting must be threaded
  through ~10+ cost terms + `period_frac=1` + TES linking + validation. NOT rushed
  autonomously (risk = the silent-bias failure that killed coarse resolution).
- **DECISION (per "aim 0.1%, accept best"):** run the reworked campaign with the grid
  fix + `MIPFocus=1`, **report every scenario's achieved gap** (~1–4% expected), and
  never rank within-gap. Reserve the typical-days build as a deliberate, supervised
  follow-on for proven <1%. The electrification sweep + siting landscape (fixed-capacity
  / fixed-siting) converge tighter than the full-investment matrix.
2. **Big-M tightening.** Track down the constraint producing the −3.8×10¹⁰ root
   bound (likely a loose pressure/pump or TES-linking big-M) and tighten it. Helps
   the *bound* without changing optimal answers.
3. **Relax redundant binaries** where the shared-port cut already enforces TES
   charge/discharge exclusivity; consider SOS2 for PWL pressure segments.
4. `MIPGap` target **0.01**; `MIPFocus=3` (bound-focus) if the bound is the
   bottleneck after (1)–(2).

**NOT doing now:** proper representative/typical-days (the `RepresentativePeriods`
schema exists but is a **stub — not wired into the model build**; implementing
clustering + period weighting + seasonal TES linking + KPI up-scaling is a separate
multi-week feature). Documented as future work.

**Canonical code for the re-run:** the validated worktree **`e8e445e`** (reproduces
the demonstrated model at 271–299 k for MM-S4, tractable) + the closure-export fix
(§5). Current `main`'s added lateral-loss/pressure physics is noted as a modelling
refinement / future sensitivity, not the canonical basis (it is harder to solve and
would re-open every number). **This is a decision to confirm.**

**Expected outcome:** gap **≤1–2%** (from 4–9%), solve time **minutes–~1 h**/scenario
(from 24 h), incumbent variance largely removed → fine comparisons become valid.

---

## 5. Data-quality fixes to fold into the re-run
- **Energy-balance closure at source:** export HP/WP **heat** output
  (Σ hourly P_el × COP) in the extractor so `validation.json` closure is ≤~2%
  (today it mis-counts HP *electricity* as heat → 25–53% artefact).
- **KPI baseline guard** (`_is_diagnostic`) — already fixed; carries into the re-run.
- **Report MIP gaps** in T3/T4/T5 (parse Gurobi logs).

---

## 6. Validation plan
1. **Resolution convergence:** solve the two headline scenarios at 1 h, 2 h, 3 h;
   accept the coarsest whose TAC, LCOH, CO₂, COP, TES-cycling differ from 1 h by a
   stated tolerance (target ≤2%). Report the convergence table.
2. **Gap reporting:** every scenario's final gap in the tables; no ranking within-gap.
3. **Energy balance:** ≤~2% closure after the heat-output fix (§5).
4. **Cross-checks:** sweep optimum ≈ MILP optimum (F3); pandapipes pressure spot-check
   (existing); Paper 1 consistency stated with the price-harmonisation disclosure.

---

## 7b. ACTUAL electrification-sweep result (2026-08-31) — REFRAMES THE PAPER
The sweep (both networks, fixed siting S2, HK2, grid-fixed, HP forced with CAPEX)
shows: **mandated heat-pump electrification MONOTONICALLY RAISES cost and does NOT
cut CO₂** — Memmingen LCOH 26→56 €/MWh, Stadtbach 18→36; CO₂ flat-to-rising. The
forced HP sits **largely idle** (SB electrification 0.6% even at 40 MW) because the
existing CHP/biomass/waste-heat is cheaper to run and already low-carbon → the HP is
pure added CAPEX. **At 2026 prices, HP electrification is not cost-effective in either
real network.** This refines the earlier "+44.8% Memmingen" (that was TES + heat-curve,
NOT the HP). CAVEATS: price-dependent (higher CO₂ / lower elec price could flip it — see
F7); SB 60–100% points are maxTimeLimit/garbage (80% = €252 M failure) → re-solve needed;
result is for fixed S2 siting. **This is a strong, counterintuitive, publishable finding
but it changes the thesis from "how to electrify" to "when electrification does/doesn't
pay" — needs an author framing decision.**

## 7. Expected results (what we predict)
- **Electrification sweep (F-elec):** monotone TAC/CO₂ *decrease* with HP share in
  Memmingen up to a knee, then diminishing/rising as peak-EK/grid-charge cost
  bites; Stadtbach cost ~flat/slightly rising with forced HP (its CHP already cheap)
  → **explains finding #2 by design**.
- **Heat-curve (F4):** COP rises ~5%/5 °C both nets; TAC falls only where electrified.
- **Siting (F6):** decisive; optimum non-obvious; tighter gap sharpens the landscape.
- **Cost/CO₂ vs baseline (F5):** MM +~45%/+~21%; SB modest cost, larger CO₂.
- **Sensitivity (F7):** SB gas-dominated (±~22%), net-power-exporter elec sign;
  MM CO₂/elec-led.
- **Gaps:** ≤1–2% throughout; numbers shift a few % from the frozen set but the four
  findings hold.

---

## 8. Execution order & milestones
1. **M1 — Resolution prototype** (this session): 1 MM scenario at 2 h/3 h vs 1 h →
   pick `dt_h`. *(gate: KPI delta ≤2%.)*
2. **M2 — Big-M audit + closure-export fix** in the worktree.
3. **M3 — Electrification sweep (Study A)** → F-elec. *(highest-leverage.)*
4. **M4 — Siting landscape (Study C)** re-solve at tight gap → F6.
5. **M5 — Canonical matrix + baselines** (T3/T4) + Study B/D.
6. **M6 — Sensitivity tier-2 (Study E)** → F7.
7. **M7 — Rebuild all figures/tables + validation tables.**
8. **M8 — Rewrite draft** to the §2 structure.

## 9. Risks & honest caveats
- Coarse resolution may under-resolve peak hours / large-TES seasonal cycling
  (Stadtbach's 4,982 m³ store) → the convergence test (M-V1) is the guard; SB may
  need 2 h where MM tolerates 3 h.
- Big-M audit may only partly tighten the bound; resolution is the main lever.
- Re-run replaces every current number; the frozen figures become obsolete once M7
  lands (intended).
- Canonical-code choice (e8e445e vs main) is a **confirm-before-M2** decision.
