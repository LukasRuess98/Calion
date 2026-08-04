# Paper 1 — Manuscript finalization prompt (pump/pressure model + demand_fraction² corrections)

Use this as the instruction set to finalize `docs/paper_1/MainEingereicht06072026.tex`.
Line numbers are from the submitted version; re-grep before editing. Every "corrected"
value comes from the faithful c19d690 worktree (baseline reproduces the paper to the cent)
with FOUR corrections applied (pump-attribution, demand_fraction², fine-PWL friction,
transfer-station Δp) — see §"What changed & why" at the bottom. The pumping model change
is a disclosed model upgrade (methods note §7), not just a bug fix.

Status: **ALL runs are complete** (primary L1–L3⁺, sensitivity, synth, and the L3NL
linearization analysis). Every number below is final and validated against the corrected
outputs in `output/paper1_corrected/`; no pending items remain.

---

## 1. Primary case §5.3 "Extended physics: L3→L3⁺"  (≈ lines 1618–1626)

The pumping model was upgraded to physical realism (a disclosed MODEL CHANGE — see
methods note §7): pump power now resolves BOTH pipe friction (Darcy–Weisbach, PWL
with low-flow-concentrated breakpoints) AND the differential pressure maintained at
each transfer station (Übergabestation, 0.6 bar). The old pump-attribution bug
(only the plant's immediately-outgoing pipe counted) is also corrected (BFS over all
downstream pipes).

| Quantity | SUBMITTED | CORRECTED (validated on primary L3⁺) |
|---|---|---|
| L3→L3⁺ cost gap | +0.11 % | **+0.33 %** ✓ confirmed (level_consistency: 225,717 → 226,452 €, +0.326 %) |
| Pump electricity | 2.4 MWh | **~10.6 MWh/yr = 0.11 % of heat** |
| Peak pump power | — | ~5 kW (friction) + station term |
| "two orders of magnitude smaller than the topology gap" | — | reword: topology 13.0 % vs pump 0.33 % ⇒ **~40× (about 1.6 orders of magnitude)** |

REWORD "attributable entirely to pumping power (+255 EUR/yr on 2.4 MWh additional
pump electricity)". Replace with e.g.:
> "increases annual cost by +0.33 %. The pumping model resolves pipe friction
> (Darcy–Weisbach) and the 0.6 bar differential pressure held at each transfer
> station; total pump electricity is ~10.6 MWh/yr (0.11 % of heat), and the cost
> increment splits between that electricity and its grid-CO₂ charge."

Keep the qualitative conclusion — topology dominates pumping ~40×; it holds firmly.

> **Calibration note (records, not paper):** ~0.11 % of heat sits at the LOW edge of
> the real-DH band (0.2–1 %), consistent with Memmingen's compact (3.3 km) oversized
> (DN400, ~0.8 m/s) low-friction network + the 0.6 bar station minimum. A higher
> plant differential (~3 bar) would land mid-band but deviates further from the
> submitted model. Evolution of the number as fixes were layered: friction-only
> buggy +0.11 % → pump-attribution +0.33 % → +station 0.6 bar (loose PWL) +0.808 %
> → +fine-PWL friction (clean, pinned) **+0.33 %**. The tangent lower-bound variant
> was rejected: with 92 strongly-negative-price hours in the data it let the solver
> inflate P_pump for profit (L3⁺ came out cheaper than L3).

## 2. Table `tab:cost_extended`  (≈ lines 1637–1638)  ✅ RESOLVED
- Row "L3→L3⁺ | Full year": change `+0.11%` → **`+0.33%`** (MIP gap column unchanged, <0.5 %).
- The two `L3⁺→L3NL` window rows: **KEEP the submitted +0.35 % (Jan) / +0.50 % (Feb)**
  and add the footnote below. These gaps are dominated by *temperature* linearization,
  which the pump correction does not touch; the corrected pump physics moves them by only
  ≈ −0.03 % → ≈ +0.32 % / +0.47 % (within the 0.5 % MIP‑gap band).

  A full global L3NL re‑solve with the corrected pump model is **intractable**: the BFS
  pump‑attribution fix multiplies the exact model's bilinear constraints ~14× (to 58,774),
  and 24 h/window found no incumbent. The pump contribution was therefore quantified by
  **exact decomposition** on the L3⁺ optimal dispatch — see
  `L3NL_LINEARIZATION_ANALYSIS.md` (in this folder) + `corrected_data/pump_linearization_error.json`:
  - pump‑friction PWL‑vs‑cubic error = **+0.031 % (Jan) / +0.027 % (Feb)** of total
    (L3⁺ over‑charges friction by ~0.11 MWh/month; exact L3ᴺᴸ is that much cheaper);
  - the 0.6 bar station Δp is **linear and charged identically** in L3⁺ and L3ᴺᴸ → it
    **cancels** in the gap.

  > **Suggested footnote (tab:cost_extended / §5.3):** "The L3⁺→L3ᴺᴸ gaps are reported
  > from the originally‑submitted nonlinear reference. Under the upgraded pump model the
  > added differential‑pressure term is linear and enters L3⁺ and L3ᴺᴸ identically
  > (cancelling in the gap), while the pipe‑friction PWL error, evaluated exactly on the
  > L3⁺ optimal dispatch, is +0.03 % of cost; the linearization gap is therefore
  > unchanged to within the 0.5 % MIP tolerance."

## 3. Table `tab:gap_stability` (App.) — L3–L3⁺ column  (≈ lines 2871–2883)  ✅

Replace the whole L3–L3⁺ column:

| Scenario | SUBMITTED | CORRECTED |
|---|---|---|
| Baseline | +0.11 | **+0.330** |
| Gas high | +0.18 | **+0.362** |
| Gas low | +0.05 | **+0.388** |
| Elec. high | +0.00 | **−0.187** |
| Elec. low | +0.10 | **+0.151** |
| CO₂ high | +0.08 | **+0.188** |
| CO₂ low | +0.16 | **+0.265** |
| Cold year | +0.11 | **+0.329** |
| Warm year | +0.00 | **+0.321** |
| HP COP low | +0.01 | **+0.232** |
| Biomass exp. | +0.20 | **+0.356** |

Prose (≈ line 1801–1803): "L3–L3⁺ gap stays below 0.3 % in all 11 scenarios" →
**"below ~0.4 % in all scenarios"** (max is +0.388 %; one small negative −0.19 %
in elec-high is within MIP-gap noise — optionally footnote it).

## 4. Synthetic study §5.4  ✅ (36-config basis, matches the paper's `n=36`)

Confirmed: the pump fixes move **only** the pressure-drop term. Everything else
reproduces the paper on the same 36 configs (fresh L3 reproduces the backup L3 to
−0.04 %; L1cp/L1/L2 are the paper's own values).

| Synth gap | SUBMITTED | CORRECTED (n=36) |
|---|---|---|
| L1cp→L3 topology | 20.0 % | **+20.22 %** (range +3.1 to +44.8) ✓ reproduces |
| L1→L2 heat-loss | ~20 % | **+20.01 %** ✓ exact |
| **L2→L3 pressure-drop** (≈ line 1740, "+0.02 %") | +0.02 % | **median +0.165 %, max +0.764 %** |
| L3→L3⁺ delay ("identically zero", ≈ lines 1767–1778) | ~0 | **+0.000 %** ✓ reproduces |

- The **pressure-drop sentence "at or below the MIP-gap noise floor"** must change:
  +0.165 % median now exceeds the ~0.5 % gap only at its max, but it is no longer
  "≈+0.02 %". State it as ~+0.17 % (median), consistent with the primary L3→L3⁺.
- Topology (20.2 %) and "L3→L3⁺ identically zero" are **unchanged** — keep as written.
- NOTE (basis): the campaign accidentally ran 42 configs (6 extra 30/50 km networks
  I added); the reported numbers above are filtered back to the paper's **36**. The
  6 extras have high topology gaps (up to 67 %) and would inflate the median to 34.7 %
  if included — do NOT include them unless the study is deliberately extended.
  ✓ Confirmed from the final synth summary (n=36): the L3→L3⁺ delay term is **median
  0.0000 %, max 0.0000 %** — identically zero, exactly as submitted.

## 5. Appendix "Post-processing validation" (≈ lines 2852–2855)  ✅
"Pumping (L1/L2/L3): <5 kW peak, <1 % of thermal losses" — with the upgraded pump
model (friction + 0.6 bar station Δp), total pump electricity is **~10.6 MWh/yr =
0.11 % of heat ≈ 0.8 % of the ~1330 MWh annual thermal loss**, so the "<1 % of
losses" claim still holds. Peak pump power (computed on the corrected L3⁺ winter
window) is **~2.8 kW** — station-Δp-dominated (~2.80 kW) plus ~0.20 kW pipe friction
— so the "**<5 kW peak**" claim also still holds (peak at Q_demand ≈ 4.0 MW, total
demand mass flow ≈ 35 kg/s). ✓

## 6. Abstract / Conclusion / RQ2 wording  ✅
Any sentence quantifying the L3→L3⁺ / pressure-drop magnitude as "+0.11 %",
"negligible", or "two orders of magnitude" (e.g. §7 RQ2 ≈ line 2187 "+0.11 %
attributable entirely to pumping power") → update to **+0.33 %** and soften
"two orders of magnitude" to "~40× (about 1.6 orders of magnitude)". Conclusion that
pressure-drop physics are marginal for planning **stands** (topology gap ≫ pumping).

## 7. Methods — DISCLOSE the pump-model upgrade (required for a corrected resubmission)
The pumping model changed materially vs the submitted version; state it near
eq. `eq:pump_power` (≈ line 1034–1046):
> "Network pumping power resolves (i) pipe friction (Darcy–Weisbach, PWL) aggregated
> over EVERY pipe downstream of a producer (nearest-path attribution, not only its
> immediately-outgoing pipe), and (ii) the differential pressure Δp_s = 0.6 bar held
> at each consumer transfer station, charged on that station's mass flow."
(The demand_fraction² item is a code-reproducibility fix; it does not change the
paper's synth numbers and need not appear in the manuscript.)

---

## What changed & why (for your records — do NOT put in the paper)
1. **Pump-attribution fix** (`network_manager.py::_link_pump_head`): old code counted
   only a producer's immediately-outgoing pipe(s); radial plant j_1 has one, so 13/14
   pipes' pumping was dropped from the objective. Fixed via BFS ownership.
2. **demand_fraction² fix** (`thermal_node.py`): committed code applied
   `demand_fraction` twice → synth served ~20 % of demand. Fixed; reproduces the
   paper's synth to the cent (L2 exact, L3 within 0.2 %). Primary unaffected
   (its consumers have demand_fraction removed).
3. **fine-PWL friction** (`pipe_pair.py`): pump-power PWL breakpoints moved to
   `[0, 0.12, 0.35, 1.0]` (low-flow-dense) to cut the cubic-secant over-estimation
   ~16×→~2× at part-load, keeping the PINNED equality. A tangent lower-bound was
   tried and REJECTED — with 92 strongly-negative-price hours it let the solver
   inflate P_pump for profit (L3⁺ came out cheaper than L3).
4. **transfer-station Δp** (`network_manager.py::_link_pump_head`): pump now also
   pays the 0.6 bar differential held at each Übergabestation (linear in
   `m_dot_demand`, exact). Turns friction-only pumping (0.006 % of heat, unrealistic)
   into ~0.11 %.
All four patches are in `output/paper1_corrected/*.patch` and the isolated worktree
`../paper1_faithful_c19d690`; your Paper-2 working tree is untouched.

## NB — Druckverluste study (Paper 2, SEPARATE) also needs attention
`configs/pressure/Memmingen_pump_pressure_study.ipynb` runs the CURRENT main-repo
code, whose pump uses a **tangent lower-bound** (`pipe_pair.py` ~L1217) — the exact
formulation rejected in fix #3: with 92 strongly-negative-price hours it can inflate
P_pump (full-year Paper-2 runs at risk; the notebook's January window is largely
safe — only mildly-negative hours). It also **lacks the 0.6 bar station Δp** term, so
its pumping under-represents reality the same way Paper 1 did. See chat report.
