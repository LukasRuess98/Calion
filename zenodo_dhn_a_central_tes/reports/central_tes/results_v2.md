# Results v2 — central TES with prosumers at site S, incl. south expansion (2026-10-08)

Supersedes the numbers of gate reports G3–G6 (v1). Revised after an independent review (section 8). Changes v1 → v2: `docs/dhn_storage_study/central_tes/model_and_deviations.md`,
section 4a (D10–D16). Reference: 5 000 m³ TES with temperature classes 90–120 °C, 40 MW; HP 5 MW on the merged
partner-A water stream; partner-B EB 10 MW (c_el,var high, π 10 EUR/MWh); DN 400; 2025 data and prices (gas
48 EUR/MWh, CO2 72 EUR/t); perfect foresight; HiGHS (MIP gap 0.1 %; achieved ≤ 2.4·10⁻⁵ in the factorial, ≤ 2·10⁻⁴ in X/X4/A5,
8·10⁻⁴ in one spec-model run of set P). **TES location: site S = the station of partner A, next to partner B (space
available); all paper results use this location.**
Costs in EUR/a, k = kEUR/a.

## 1. Factorial (today's load)

| scenario | C_E | v_E(S) | violating h (A/C/B) | ΔC_hyd A (C/B) |
|---|---|---|---|---|
| F000 | 15 706 300 | – | 3 / 3 / 3 | 21 (24 / 28) |
| F001 | 15 300 225 | 406.1 | 8 / 7 / 7 | 54 |
| F100 | 15 606 974 | 99.3 | 3 / 3 / 3 | 21 |
| F010 | 15 674 703 | 31.6 | 3 / 3 / 3 | 21 |
| F110 | 15 577 860 | 128.4 | 3 / 3 / 3 | 21 |
| F101 | 15 192 225 | 514.1 | 8 / 7 / 7 | 136 |
| F011 | 15 261 188 | 445.1 | 8 / 7 / 7 | 31 |
| F111 | 15 162 333 | **544.0** (3.5 %) | 8 / 7 / 7 | −122 (−120 / −156) ≈ 0 |

ΔC_hyd values below ≈ 0.4 k are within the solver tolerance.

**Shapley (E = H):** TES 411.9 k, partner A + HP 100.2 k, partner B EB 31.9 k; TES interaction term 9.5 k.
Storage value: alone 406.1 k, with A 414.7 k, with B 413.5 k, with A+B 415.5 k — **the TES is a stand-alone
flexibility asset, not mainly an enabler of the two prosumers** (v1 statement withdrawn; it was an artefact of the
single-temperature charging mask).

**Mechanism (F111 vs F000):** the TES is charged mainly from the network (19.0 GWh/a; HP 1.2, EB 0.4 GWh/a), 69 equivalent
full cycles. It moves KWK output to hours with higher power prices (price-weighted 109.8 → 117.6 EUR/MWh) and displaces
HW1 peak-boiler heat (10.5 → 4.4 GWh/a). CO2 net 33 682 → 32 317 t/a (−4.1 %).

**Prosumers:** partner A (merged water stream, 37.5 GWh/a, 17.4 °C time-mean source temperature; heat-weighted 20.9 °C, weighted by the HP's source use 18.3 °C) — U_A 6.3 %, HP 4.7 GWh/a
(946 full-load hours), COP ≈ 2, 97 % of HP heat at lifts > 70 K (two-stage HP implied); cascade ≤ 5 % of HP heat.
Partner B — 1.65 GWh/a (167 full-load hours), 70 % of its operating hours at negative prices, the rest at
0–10 EUR/MWh (price-weighted −21 EUR/MWh).

## 2. Hydraulics at today's load (pressure focus)

* Hard limits: violations in 3–8 h/a; Mode H repairs them with |ΔC_hyd| ≤ 0.35 k for every scenario, size, DN and
  V06 limit, i.e. zero within the solver tolerance (MIP gap ≈ 0.4 k) → **no measurable cost of hydraulic feasibility
  at today's load**, robust over the three calibrations (PS1 head control included).
* **Pressure footprint of the TES** (F111 vs F000, calibration A):
  * required KWK Δp P95 2.54 → 2.91 bar; hours above the KWK experience value 4.0 bar 30 → 109;
  * MVA above 7.5 bar 581 → 741 h;
  * flow reversals vs F000 (|ṁ| > 10 kg/s in both states): KWK outlet 848 h, L1/City mesh M12 777 h, L1a 761 h,
    south trunk L4a–d 274–488 h, L5a 462 h, L1b 332 h, L3 231 h, L5b/c 145–160 h (TES charging draws KWK water
    through L1a/L5a and changes the HW1 dispatch on the south line).
* pandapipes cross-check (90–97 hours per schedule incl. peak, violating and high-|Q_central| hours; values for the
  F111-E schedule, all 10 nodes): same friction law max 0.055 bar (P95 0.036 bar); Reynolds-dependent friction max
  0.32 bar, at S (P95 over all nodes 0.21 bar; pooled over the four schedules of figure 6: P95 0.16 bar) —
  this is the model uncertainty for pressures at the feed-in node.

## 3. Economics (break-even, PF, Mode E; cost data after the literature check of 2026-10-09)

| asset | value | I_max (5 %, lifetime) | literature investment |
|---|---|---|---|
| TES 5 000 m³ / 40 MW (pressurised) | 406–416 k | 6.2–6.4 M EUR (30 a) | 5.1 / **7.6** / 12.6 M EUR (1 000 / 1 500 / 2 500 EUR/m³ + 0.1 M) |
| HP 5 MW (partner A) | 99–100 k | 1.2 M EUR (20 a) | 4.75 M EUR (0.95 M EUR/MW, DEA) → **not economic** |
| connection pipe | enabling investment for all central assets | – | 0.6 M EUR (200 m DN 400, 3 000 EUR/m) = 35 k EUR/a, small against every asset value |

Whole concept (TES ref. cost + HP + link): annualised capital cost 911 k vs. value 544 k → **not economic as a bundle**.
The pressurised TES breaks even at 1 258 EUR/m³ (PF), i.e. inside the literature range but below the 1 500 EUR/m³
reference; the HP is the clearly uneconomic part.
Break-even specific TES cost (A1): 5 000 m³ 780–1 350 EUR/m³ (10–80 MW); 10 000 m³ 460–880; 20 000 m³ 380–560 EUR/m³.
**With rolling horizon the TES realises only 43–56 % of its PF value** (whole A1 grid run under RH, section 5) →
break-even 5 000 m³ **364–686 EUR/m³** (10–80 MW; reference 40 MW: 647 instead of 1 258), 10 000 m³ 212–399,
20 000 m³ 171–239 EUR/m³; 2 500 m³ 847–1 078 EUR/m³ — below the pressurised-tank range from 5 000 m³ on (2 500 m³ at
40–80 MW just above its 1 000 EUR/m³ lower bound; figure 4).
**Atmospheric alternative (set AT, classes ≤ 95 °C, F111 vs F110; HP COP for the 95 °C top class):** 10 000 m³ / 40 MW
190.1 k, 20 000 m³ / 40 MW 222.6 k, 50 000 m³ / 80 MW 293.6 k → break-even 282 / 166 / 88 EUR/m³ against ≈ 177 / ≈ 143 /
≈ 250 EUR/m³ (DEA cost curve, 20 000 m³ extrapolated; DEA 50 000 m³ case): the 10 000 and 20 000 m³ atmospheric tanks
are economic under perfect foresight, 50 000 m³ is not. Under RH (run, set AT with `--rh-at`): 94.1 / 118.3 / 127.5 k →
break-even 135 / 86 / 37 EUR/m³ → none economic (also with the uncredited end-of-year storage of 203–607 MWh valued at
the HW1 heat cost). The tank discharges only when the supply temperature is ≤ 95 °C (5.4–6.8 GWh/a vs 20.5 GWh/a for
the pressurised tank).

## 4. Sensitivities (Mode E)

* **A1 size (E + H, and RH):** value vs F110 grows with energy and power: 5 000 m³ 259 / 342 / 416 / 444 k (10/20/40/80 MW);
  20 000 m³ 502 / 655 / 736 k (20/40/80 MW). Attributable violations rise with power (80 MW: 7 h at 2 500 m³, 11–16 h from 5 000 m³);
  Mode H repairs all of them, ΔC_hyd ≤ 0.35 k for every size (all converged). Under RH the TES keeps 43–56 % (section 5).
* **A3 temperature handling (E + H):** spec single-state model fixed / monthly / daily: TES alone 17.1 / 11.4 / 186.5 k,
  v(F111) 212.9 / 206.9 / 327.8 k, U_A 7.6 / 8.3 / 7.4 %; class model 406.1 / 544.0 k, U_A 6.3 % — the charging mask
  removes most of the value (why the class model is the reference); lower T_set raises U_A but lowers the TES value (H6).
  **A3e energy-only bound (2026-10-11):** single state without temperature limits (charge/discharge in every hour,
  capacity at 120 °C): TES alone 1 017.2 k, v(F111) 1 108.5 k, 241 equivalent full cycles (71 GWh/a) — 2.5 × the class
  model. Bracket: energy-only 1 017 k > classes 406 k > single daily 187 k > single fixed 17 k (section 10).
* **A2 connection DN (E + H):** V_TES (F110 − F111) 402.4 / 411.9 / 415.5 / 416.3 / 416.2 k for DN 300 / 350 / 400 / 450 / 500
  (κ_link 0.24–0.61); |ΔC_hyd| ≤ 0.22 k for every DN (zero within the solver tolerance); the link binds only below DN 400.
* **PS partner-A data mapping (± 7 d calendar shift):** A alone 98.3 / 95.8 k (ref. 99.3), v(F111) 544.5 / 541.6 k →
  the weekday mapping of the 2023 profile does not drive the results.
* **A6 cascade:** off, or T_mid 70 / 90 / 100 °C, change C(F111) by −0.1 / +0.3 / +0.2 / +0.1 k (within the MIP tolerance) → no value.
* **Old prices** (gas 58.6, CO2 100): v(F111) 758 k, TES alone 404 k.
* **Partner B premium π** (v_B = C(F101) − C(F111)): 53.7 / 29.9 / 19.9 / 15.3 / 12.3 / 8.1 k for π = 0/10/20/30/40/60;
  premium revenue π·Q 0 / 16.5 / 13.9 / 10.6 / 10.3 / 10.1 k → a negotiable premium of ≈ 10–20 EUR/MWh.
* **Partner B cost regime:** low c_el,var (12 EUR/MWh, levy floor): v(F111) 758.5 k, EB 7.0 GWh, v_B 244 k; with a demand
  charge the EB is never used.
* **Waste-heat fee to partner A:** U_A 7.1 / 6.3 / 5.5 / 4.2 % for 0 / 5 / 10 / 20 EUR/MWh.
* **9.9 MW electric boiler at the KWK** (not in plan A): F000 −54 k; v(F111) 529 k.

## 5. Foresight

RH (72 h window / 24 h commit, demand forecast error σ 5 % drawn per window; prices known up to the end of the
delivery day (and the next day for decisions after the 12:00 auction), beyond the last known day repeated; the TES state
is handed over per temperature class; the tank starts empty, 69–71 MWh left at year end are not credited). *Version
2026-10-11:* the earlier price forecast (same hour of the previous day) used not-yet-known prices for hours 48–71; all RH
results were re-run (old: concept 329.7 k, TES 220.0 k; archive `rolling_horizon_v1_lag24`).
v(F111) **323.6 k** with partner-A schedule known day-ahead (**59.5 %** of PF), 310.9 k with persistence (57.2 %);
RH Mode H 322.6 k (59.3 % of PF Mode H). F000 under RH = PF (no inter-temporal coupling); F110 under RH loses 21.8 k
(HP and EB dispatch with forecasts). **Value of the TES under RH:** alone (F000 − F001) 214.5 k = 52.8 % of PF;
with A + B (F110 − F111) 217.0 k = 52.2 % of PF; A1 grid 43–56 % (larger tanks lose relatively more, e.g.
20 000 m³ / 80 MW 43 %), see `results/central_tes/rolling_horizon/tes_values_rh.csv`. The TES moves 18.3 GWh/a
(PF 20.5), 62 equivalent full cycles (PF 69); HW1 5.6 GWh/a (PF 4.4).
**Robustness (`--rh-robust`):** three noise seeds at σ 5 % give V_TES 212–214 k (reference 217 k) and a concept value of 319–324 k (324 k), i.e. −2 %…0 %; a worse demand forecast lowers the TES value strongly: σ 10 % 168 k (40 % of PF), σ 15 % 114 k (27 %) — forecast quality is a first-order driver of the realisable storage value.
**Decomposition of the foresight loss:** section 10.
*Correction:* the earlier 479.9 / 471.3 k (88 %) were biased upwards — the scalar state hand-over put all stored energy
into the 120 °C class at each window start (free temperature upgrade and volume).

## 6. South expansion with a new boiler — supplementary (superseded as main result by section 11)

*Author decision 2026-10-12: a new south boiler is not part of the current planning; the question is whether the storage lets the existing network serve more south demand. Section 11 (hosting capacity, no new capacity) replaces this section in the paper; the numbers below remain as "what new capacity would take" (supplement).*

Original scope: +10 / 20 / 30 % of today's demand, ≙ +53 / 107 / 160 % of the south load.

Set X: new customers at the south nodes (today's south weights, today's hourly shape); a new gas peak boiler at the south
end (node of station V06) with its capacity as a MILP decision (annualised 9.1 kEUR/MW/a); TES 5 000 m³ / 40 MW at S (reference)
or at the south end ("TES south", charged from the network). Mode H on calibration A, k_max = 10.

| level | scenario | C_E | C_H | ΔC_hyd | new boiler (H) | its heat | KWK Δp P95 (H) | Mode H |
|---|---|---|---|---|---|---|---|---|
| +10 % | F000 | 18 956 756 | 19 020 564 | 63.8 k | 0 MW | – | 5.9 bar | conv. |
| | F110 | 18 781 738 | 18 845 580 | 63.8 k | 0 | – | 5.9 | conv. |
| | F111 | 18 319 392 | 18 386 570 | 67.2 k | 0 | – | 6.0 | conv. |
| | F111, TES south | 18 364 660 | 18 604 972* | 240.3 k* | 0 | – | 6.9 | 76 h left |
| +20 % | F000 | 22 340 617 | 22 840 302 | 499.7 k | 8.4 MW | 22.4 GWh | 7.7 | conv. |
| | F110 | 22 123 155 | 22 632 420 | 509.3 k | 7.2 | 18.2 | 7.7 | conv. |
| | F111 | 21 631 687 | 22 150 078 | 518.4 k | 6.2 | 15.1 | 7.7 | 2 h left |
| | F111, TES south | 21 690 407 | 22 475 209* | 784.8 k* | 6.3 | 17.5 | 7.9 | 109 h left |
| +30 % | F000 | 25 831 452 | 26 960 581 | 1 129.1 k | 16.9 MW | 59.4 GWh | 7.9 | conv. |
| | F110 | 25 575 922 | 26 724 238 | 1 148.3 k | 16.5 | 54.8 | 7.9 | conv. |
| | F111 | 25 074 075 | 26 237 298 | 1 163.2 k | 15.5 | 50.3 | 7.9 | 6 h left |

\* not converged: a lower bound on the cost of a feasible schedule.

Value of the TES (vs. F110, i.e. with both prosumers):

| level | TES at | V_TES Mode E | V_TES Mode H | new boiler without → with TES |
|---|---|---|---|---|
| 0 % | S | 415.5 k | 415.7 k | – |
| +10 % | S | 462.3 k | 459.0 k | 0 → 0 MW |
| +10 % | south end (exploratory) | 417.1 k | ≤ 240.6 k* | 0 → 0 MW |
| +20 % | S | 491.5 k | 482.3 k | 7.2 → 6.2 MW |
| +20 % | south end (exploratory) | 432.7 k | ≤ 157.2 k* | 7.2 → 6.3 MW |
| +30 % | S | 501.8 k | 486.9 k | 16.5 → 15.5 MW |

Findings:

* **The capacity need of the south expansion is hydraulic, not energetic.** Mode E never builds the new boiler (the
  existing plants cover +30 % energy-wise). Mode H builds 8.4 MW (+20 %) and 16.9 MW (+30 %) at the south end and
  shifts KWK heat to it (KWK −23 / −59 GWh/a), because V06 (south end) binds in ≈ 95 % of the hours. The cost of
  hydraulic feasibility rises from ≈ 0 (today) to 64 k (+10 %), 0.50 M (+20 %) and 1.13 M EUR/a (+30 %); CO2 +0.6 / +1.5 kt/a
  versus Mode E.
* **Even with the new boiler the network runs far beyond today's operating envelope:** required KWK Δp P95 5.9 / 7.7 /
  7.9 bar (max 8.4 bar) against the operator experience value 4.0 bar (exceeded in 1 450–3 700 h/a); PS1 adds up to
  3.4 bar extra head (P95 ≈ 3 bar, at its curve limit in ≈ 1 % of the hours). Set X4 (KWK 4 bar as hard limit) quantifies what this costs (section 6a).
* **TES at S:** its value grows with the load (416 → 459 → 482 → 487 k in Mode H) and is almost unaffected by
  hydraulics (Mode E − Mode H ≤ 15 k). It reduces the new boiler by only ≈ 1 MW (≈ 9 k EUR/a), and ΔC_hyd stays
  unchanged — **the TES at S is not a substitute for south capacity**; it keeps its arbitrage value in the expanded
  network.
* **TES at the south end (exploratory only; the TES stays at S), charged from the network, is worse:** Mode H value
  ≤ 241 k (+10 %) and ≤ 157 k (+20 %), ΔC_hyd ≥ +177 / +276 k against F110 (upper/lower bounds, not converged); charging draws additional water through the bottleneck exactly when the south is
  short of pressure, and Mode H does not converge within 10 iterations (73–109 h left). A south TES would need its own
  local charging source (e.g. the new boiler or an electric boiler at the south end) to act as capacity — not modelled.
* Robustness: Mode H not fully converged in two runs with TES at S (2–6 h left; the cost changes in the last iterations
  are < 1 k EUR/a).

### 6a. KWK 4 bar as hard limit (X4)

The operator experience value of the KWK (Δp ≤ 4.0 bar) enforced as a hard hydraulic limit in Mode H:

| level | scenario | C_H | ΔC_hyd | new boiler (H) | its heat | Mode H |
|---|---|---|---|---|---|---|
| 0 % | F000 | 15 708 183 | 1.9 k | 0 MW | – | conv. |
| | F110 | 15 579 750 | 1.9 k | 0 | – | conv. |
| | F111 | 15 172 156 | 9.7 k | 0 | – | conv. |
| +20 % | F000 | 23 075 424 | 734.8 k | 11.2 MW | 35.8 GWh | conv. |
| | F110 | 22 870 318 | 747.2 k | 10.2 | 31.1 | conv. |
| | F111 | 22 414 668 | 783.0 k | 8.4 | 25.9 | 8 h left |

* **Today's load:** the 4 bar limit costs 1.9 k without and 9.7 k with the TES → **the pressure footprint of the TES
  (section 2) has a price of ≈ 8 kEUR/a** (V_TES,H 407.6 k instead of 415.7 k, −2 %).
* **+20 %:** keeping the KWK at ≤ 4 bar needs 2.2–3.0 MW more south capacity than without the limit and costs
  0.24–0.26 M EUR/a more. Here the TES at S reduces the new boiler by 1.8 MW (10.2 → 8.4 MW, ≈ 16 kEUR/a capital),
  but its operating value drops to 455.7 k (Mode E 491.5 k): the TES both relieves (peak shaving reduces the boiler)
  and loads (network charging raises the KWK head) the bottleneck.

### 6b. pandapipes cross-check of the expanded network

L20 F111 (Mode E 114 h, Mode H 101 h): same friction law max |Δp| 0.020 / 0.030 bar; Reynolds-dependent friction
max 0.16 / 0.21 bar (P95 0.08 / 0.10 bar; V06 ≤ 0.08 bar) — the expanded states are reproduced as well as today's
(0.32 bar max at S, section 2).

### 6c. What the expansion study adds to the paper

* It turns the pressure story from "no measurable cost" (today) into a quantified one: the cost of hydraulic
  feasibility grows non-linearly (≈ 0 → 0.06 → 0.50 → 1.13 M EUR/a) and creates a capacity need of 8–17 MW at the
  south end that a pure energy model does not see (Mode E: 0 MW).
* The central TES at S keeps (and increases) its arbitrage value in the expanded network but **does not solve the
  hydraulic capacity problem** (−1 MW; −1.8 MW with the 4 bar limit). A south TES charged through the bottleneck is
  counter-productive. This is a clear, defensible negative result on "storage as capacity".
* Limits: same hourly shape for the new customers; capacity options are the south boiler and (section 6d) a reinforced
  south trunk; Mode H not fully converged in 10 of 23 expansion and reinforcement runs (≤ 8 h left for TES at S;
  73–109 h for the exploratory TES at the south end).

## 6d. Reinforcement of the south trunk instead of the new boiler (XR)

Parallel pipe of equal DN (resistance × 0.25) on L4b (3.27 km) or on L4a–L4c (5.08 km), F111, Mode H; pipe
3 000 EUR/m, 40 a, 5 % (annuity 572 / 888 k EUR/a):

| level | reinforcement | C_H | saving vs. boiler-only (incl. boiler capital) | pipe annuity | net | new boiler | Mode H |
|---|---|---|---|---|---|---|---|
| +20 % | L4b | 21 929 018 | 221 k | 572 k | −351 k | 6.2 → 5.2 MW | 1 h left |
| +20 % | L4a–L4c | 21 694 075 | 456 k | 888 k | −432 k | 6.2 → 0 MW | conv. |
| +30 % | L4b | 25 912 016 | 325 k | 572 k | −246 k | 15.5 → 14.7 MW | 6 h left |
| +30 % | L4a–L4c | 25 461 661 | 776 k | 888 k | −113 k | 15.5 → 9.7 MW | 6 h left |

Reinforcing the whole south trunk removes the need for the new boiler at +20 % but costs more than the boiler-based
solution at both levels; it approaches break-even at +30 % (pipe cost ≈ 2 600 EUR/m). The boiler at the south end is
the cheaper capacity option for the expansions studied (XR run with the TES at S, F111).

## 6e. Robustness (Priority B, approved 2026-10-09)

* **B2 price years** (2025 demand and temperatures, day-ahead prices of 2023 / 2024; weather–price correlation lost):
  v(F111) 483.2 / 530.6 k (2025: 544.0 k); Shapley TES 347.0 / 341.0 k, A 88.8 / 157.0 k, B 47.4 / 32.6 k; TES alone
  340.6 / 330.6 k. Partner A's value varies most in relative terms (Shapley 89–157 k, up to +57 %), the TES value least (Shapley 341–412 k, −17 %).
* **B4 V06 limit 1.0 / 1.4 bar** (reference 1.2): ΔC_hyd(F111) 0.18 / 0.07 k, F000 0.05 / 0.01 k; violating hours
  in Mode E 10 / 2 (F111), KWK > 4 bar 103 / 114 h → the hydraulic conclusions at today's load do not depend on the
  south-end limit.
* **PG gas price downwards** (2026-10-11; 2025 spot level ≈ 37 EUR/MWh, reference 48; all eight scenarios, PF Mode E):
  gas 37 / 42: v(F111) 476.6 / 502.8 k (48: 544.0 k); Shapley TES 402.0 / 407.8 k, A 55.3 / 71.9 k, B 19.2 / 23.1 k
  (prosumer share 16 / 19 % instead of 24 %); V_TES (F110 − F111) 403.0 / 410.4 k → break-even 1 219 / 1 242 EUR/m³
  (48: 1 258). Upwards (set P, gas 58.6 + CO2 100 EUR/t): concept 757.6 k, V_TES 433.9 k. → The TES value is insensitive
  to the gas price (−3 % at 37); the prosumers' value is not (A −45 %, B −40 % at 37): cheaper gas makes the gas-fired
  heat that the HP and the EB displace cheaper.
* **BL partner-B electricity cost over the literature range** (2026-10-12; levy floor 11.4 + network charge 23.6 / 42.8 /
  61.8 EUR/MWh, BNetzA monitoring 2025, industrial 24 GWh case; no demand charge): c_el,var 35 / 54 / 73 EUR/MWh
  (reference 60): B alone 117.5 / 47.6 / 16.4 k (60: 31.6 k); Shapley B 116.5 / 46.2 / 18.0 k, TES 415.3 / 411.3 / 412.5 k,
  A 94.5 / 98.9 / 101.5 k; concept 626.2 / 556.4 / 532.0 k (prosumer share 34 / 26 / 22 %); EB heat in F111 4.5 / 2.5 /
  0.6 GWh/a. The reference (60) is in the upper half of the range, i.e. conservative for partner B. The EB puts 7 % of
  its energy into a typical winter-weekday 8–20 h window; keeping it out of the DSO's high-load windows (atypical grid
  use, § 19 (2) StromNEV) avoids the demand charge at small cost.

## 6f. Prosumers — partner A (HP on waste heat) and partner B (electrode boiler)

* **Role in the value:** Shapley A 100 k + B 32 k = 24 % of the concept under perfect foresight, **34 % under rolling
  horizon** (A 88 k, B 21 k, TES 215 k; RH keeps 88 % of A's, 65 % of B's but only 52 % of the TES value), 28 % / 36 %
  with 2023 / 2024 prices. The prosumer contribution is the robust part of the concept.
* **Partner A drivers (value of A, alone / with B + TES):** HP size 2.5 / 5 / 10 / 15 MW: 69 / 99 / 133 / 154 k
  (saturating; U_A 4.3 → 10.0 %); source temperature +10 / +20 K: 119 / 146 k; Carnot fraction 0.4 / 0.6: 79 / 132 k;
  waste heat × 0.5 / 0.75 / 1.25: 74 / 88 / 109 k; fee 0 / 10 / 20 EUR/MWh: 112 / 88 / 70 k (P); HP grid fee
  55 / 76 EUR/MWh (literature range): 69 / 45 k. The TES does not
  raise A's value (alone ≈ with TES within 4.4 k): partner A competes with network charging of the TES, it is not
  enabled by it.
* **Partner A economics:** justifiable HP investment = value / annuity (5 %, 20 a): 0.35 / 0.25 / 0.17 / 0.13 M EUR/MW
  for 2.5 / 5 / 10 / 15 MW; +20 K source: 0.36 M EUR/MW — against 0.95 M EUR/MW (DEA). At the measured 17 °C source the
  HP needs 64–87 % investment support (62 % with a +20 K source; 88 % with a 76 EUR/MWh grid fee); the binding factors are source temperature and the HP's
  electricity cost.
* **Partner B drivers:** EB 5 / 10 / 20 MW: value alone 18 / 32 / 52 k, with A + TES 15 / 30 / 57 k (the TES raises B's
  value only at 20 MW: +5 k); premium π: operator net saving 54 / 30 / 20 / 15 / 12 / 8 k and partner revenue
  0 / 16.5 / 13.9 / 10.6 / 10.3 / 10.1 k for π = 0 / 10 / 20 / 30 / 40 / 60 EUR/MWh — the joint surplus falls with π,
  the partner's revenue peaks at ≈ 10 EUR/MWh (negotiation window 10–20 EUR/MWh); with low electricity cost
  (12 EUR/MWh, levy floor) B delivers 7.0 GWh, its value rises to 244 k and v(F111) to 759 k (A5) — partner B's role is
  set by the electricity-cost regime, i.e. by regulation, more than by the TES.
* **Mechanism at the site:** the partners charge the 120 °C class (HP 1.2, EB 0.4 GWh/a), which the network can only
  charge when its supply temperature reaches 120 °C (figure 2: weekend charging at low prices); the TES is mainly
  charged from the network (19.0 GWh/a).

## 7. Assessment and storyline (author decision 2026-10-09: prosumers are a main part of the paper)

* **Storyline:** a central TES at an industrial prosumer site — what it is worth, who creates the value, and what
  limits it (hydraulics, foresight, investment).
* **Storage:** TES value 0.42–0.49 M EUR/a under perfect foresight (Mode H, today → +30 %), Shapley 76 % of the
  concept; only ≈ 52 % is realised under rolling horizon (0.22 M EUR/a) → break-even 364–686 EUR/m³ for 5 000 m³,
  below the pressurised-tank range; a 10 000 m³ atmospheric tank (≤ 95 °C) breaks even under perfect foresight.
  Mechanism: CHP power-price shifting + peak-boiler displacement; modelling lesson: temperature classes vs
  single-temperature mask and energy-only storage (TES alone 406 vs 17 k vs 1 017 k).
* **Prosumers:** 24 % of the concept value under perfect foresight, 34 % under rolling horizon, 28–36 % with other price
  years — the robust part of the value (A keeps 88 %, B 65 % under RH). Partner A's value scales with HP size and
  source temperature (69–154 k) but the HP needs 64–87 % investment support at the 17 °C source; partner B's value is
  set by the electricity-cost regime (30 → 244 k) and a premium window of 10–20 EUR/MWh. The TES neither enables nor
  displaces the prosumers (interaction 9.5 k) — partners and network compete for the tank's top class.
* **Pressure:** today no cost of hydraulic feasibility but a measurable footprint of the TES (KWK > 4 bar 30 → 109 h,
  flow reversals; ≈ 8 k under a hard 4 bar limit), independent of the V06 limit (B4). With more south demand and no
  new capacity, the existing network serves +19 % of today's total demand (redispatch 0.25–1.3 M EUR/a); a TES at S
  raises this to +20 %, a TES at the south end to +30…35 % at ≈ 60 % lower market value (section 11). Validated against pandapipes (≤ 0.32 bar).
* **Author decisions 2026-10-12:** literature / regulatory basis for partner B's cost regime (BL) and the hydraulic
  limits; KWK 4 bar stays the operator's experience value (no generic literature value; soft threshold); network
  schematic approved.

## 8. Review log (independent check, 2026-10-08)

An independent review re-computed every number of this report from the result files and reviewed the code.
Corrections made:

1. **Rolling horizon (bug):** the TES state was handed to the next window as one number and placed in the 120 °C
   class (free temperature upgrade and volume); RH also started with a half-full tank without a hand-back condition.
   Fixed (per-class hand-over, empty start, no credit for the final state) and re-run: 60.6 % / 58.8 % / 60.2 % of PF
   instead of 88 / 87 / 88 % (section 5); dependent statements in sections 3 and 7 updated. A second check showed that
   the RH loss falls almost entirely on the TES (F000 RH = PF, F110 RH −18.7 k): F110, F001 and the A1 grid were then
   run under RH, and the break-even values in section 3 / figure 4 use these runs (no ratio scaling).
2. Report values corrected: MIP gaps (header), partner-B price statement (section 1), KWK Δp of the +10 % TES-south
   run (6.9 bar) and the maximum KWK Δp (8.4 bar) in section 6; TES-south Mode H values marked as non-converged bounds.
3. Metrics: heat balance and CO2 now include an external TES and the optional electric boiler at the KWK
   (no reported number affected); stale A1 "V0" result re-run (now equal to F110 within solver tolerance).
4. Documentation: model description updated to the class model, the objective (waste-heat fee, new-boiler capital
   cost), the heat balance, PS1 head control and the RH state hand-over.

Checked without findings: TES class logic hour by hour, energy balances, cost components, units, Mode H ≥ Mode E
within the MIP gap, monotonicity of A1/A4/expansion, CO2 consistency, factorial, Shapley, economics, X/X4, pandapipes.

## 9. Final pre-writing check (2026-10-10)

Two independent checks (numbers/figures and methods/code/anonymity) re-derived ≈ 250 values and found no error in the
core results. Changes made: atmospheric set AT re-run with the HP COP of its 95 °C top class and run under RH; RH
results re-run with the current code (F111 reproduced to the euro) and extended by noise-seed / σ robustness;
partner-A calendar shift (PS); link velocity metric recomputed (link flow only); wording and rounding fixes
(+57 %, 112 k, |ΔC_hyd| within tolerance, DEA 143 EUR/m³); figure colour roles fixed across figures (violet for
non-prosumer identities), heat export drawn as a sink in fig0, non-converged Mode H points marked in fig5;
reproducibility: all RH and paper scripts have CLI entries (README, model doc). Remaining reviewer-risk items are
listed as limitations in `paper_writing_brief.md` §8.

## 10. Literature contrasts for the discussion (2026-10-11)

### 10a. Foresight: why the TES keeps 52 % here and 85–97 % in the literature (`--rh-foresight`, T4b)

V_TES = C(F110) − C(F111) under identical forecast settings; PF = 415.5 k = 100 %; noise per window (seed 1234).

| setting | V_TES RH [k] | RH / PF |
|---|---|---|
| reference (72 h window, 24 h commitment, demand noise σ 5 %, known prices + last known day repeated) | 217.0 | 52 % |
| window 120 / 168 / 336 h | 220.7 / 226.5 / 241.1 | 53 / 54 / 58 % |
| terminal value (mean marginal heat cost of the next week per class) — 72 h / 120 h | 214.0 / 221.8 | 52 / 53 % |
| PF storage level as soft end-of-window target (upper bound of any end value) | 237.6 | 57 % |
| hourly re-planning (commitment 1 h) | 238.2 | 57 % |
| perfect price forecast | 254.6 | 61 % |
| no demand noise | 267.3 | 64 % |
| perfect information (prices, demand, partner A), 72 h | 305.5 | 74 % |
| perfect information, 120 / 168 / 336 / 720 h | 318.8 / 322.7 / 359.6 / 389.0 | 77 / 78 / 87 / 94 % |
| perfect information, 72 h + terminal value / + PF guide curve | 295.5 / 354.6 | 71 / 85 % |
| MIP gap 10⁻⁵ instead of 10⁻³ per window (reference / perfect information) | 216.9 / 306.9 | 52 / 74 % |

* **Comparable to the literature is the perfect-information case:** 74 % (72 h), 77 % (120 h ≈ the 5-day window of the
  nearest DH case), 87 % (336 h), 94 % (720 h). With a long enough window the model reproduces the literature range;
  with 3–5 days it stays 13–16 pp below.
* **Why longer windows are needed here:** the temperature classes make the tank a multi-day to multi-week store. Water
  charged at a high supply temperature can only be discharged when the supply temperature falls below its class
  temperature. In PF the tank holds 115 MWh on average (39 % of its capacity; stock/discharge ≈ 49 h) and stays above
  20 MWh for 61 % of the hours in stretches longer than one week. A PF guide curve as end-of-window target recovers
  most of this (74 → 85 %). A simple terminal value (mean marginal heat cost of the next week) does not (−1…−2 pp):
  it cannot represent the temperature-dependent timing.
* **Realistic forecasts cost a further 22 pp** (74 → 52 %): demand noise ≈ 10 pp (σ 0 → 64 %), price forecast ≈ 9 pp
  (perfect prices → 61 %), together with the partner-A forecast 22 pp; the robustness runs show σ 10 / 15 % → 40 / 27 %.
* **Commitment:** hourly re-planning instead of 24 h commitment +5 pp (57 %). The MIP gap per window is irrelevant.
* **The writer's three candidates, quantified:** window 72 → 120 h +1 pp under realistic forecasts (+3 pp with perfect
  information); price extrapolation +9 pp (perfect prices); terminal value: simple heuristic 0 pp, ideal (PF guide)
  +5 pp (realistic) / +11 pp (perfect information). Dominant: forecast errors, then window × temperature-driven
  long-term storage, then commitment.
* **Limitation:** i.i.d. hourly demand noise is a simple error model; the realised value depends on forecast quality
  to first order — a statement the paper should make explicitly.

### 10b. Single-state vs temperature-class storage model: the sign of the error

TES alone (F000 − F001), PF Mode E: energy-only single state (no temperature limits, capacity at 120 °C) **1 017 k**
(241 cycles, 71 GWh/a) > temperature classes **406 k** (67 cycles, 19.9 GWh/a) > single state with daily set
temperature 187 k > fixed 120 °C 17 k (monthly 11 k).

* **Overestimation (energy-only):** network water at 95–105 °C is booked at 120 °C energy density (52.5 K instead of
  27.5–37.5 K above T_low; up to × 1.9), and stored water may be discharged into a hotter supply (energy-weighted
  supply temperature at charge 105.3 °C, at discharge 105.6 °C — infeasible for stratified water without upgrading).
* **Underestimation (single state with fixed set temperature):** the network can charge only when its supply water
  reaches the set temperature (no tolerance, dT_tol_K = 0; with a 5 K tolerance it would be 295 h): with 120 °C this is the case in 43 of 8 759 h (median supply 96 °C,
  P95 113 °C), so only the HP and EB charge.
* **Resolution:** the sign depends on what the single-state model assumes about temperature. Without temperature
  limits it overestimates (consistent with studies that model the tank as an energy bucket); with a fixed set
  temperature and feasibility masks it underestimates. The class model lies in between (2.5 × below the energy-only
  bound, 24 × above the fixed-temperature model).

### 10c. Differential pressure at the feed-in (see also section 2)

Pressure holding (static level) is at one point, the KWK, as in any network; differential pressure comes from several
pumps: the KWK as Δp master for the worst-point stations (V06, city centre), the feed-in pumps of MVA, GT, Bio-KWK and
HW1, and the booster stations PS1 (south, with head control) and PS2 (west, measured head). The sign of the KWK Δp change
follows the flow direction at S (F111 vs F000, Mode E, calibration A): charging from the network (728 h; ≈ 158 kg/s
drawn at S; KWK +22 MW) +0.86 bar mean (P95 +2.08), hours > 4 bar 9 → 90; discharging (1 354 h; ≈ 77 kg/s fed in)
−0.16 bar mean, lower in 70 % of these hours, hours > 4 bar 4 → 2; idle ± 0. Feed-in relieves the KWK as reported for
prosumers in the literature; the annual footprint is a charging effect of a tank that is filled mainly from the network.

**Footprint vs model uncertainty (2026-10-12).** In the pandapipes cross-check the KWK Δp is an input (pressure holder),
so there is no deviation at the KWK node itself; the deviation that maps onto the required KWK Δp is the one at V06,
which sets it in ≈ 95 % of the hours. At V06: same friction law max 0.02 bar; Reynolds-dependent friction mean
+0.01 bar, SD 0.05 bar, max 0.14 bar (F111; F000 +0.01 / 0.03 / 0.12) — the bias differs between the schedules by
0.002 bar. The 0.32 bar maximum is at S, not at the node that sets the KWK Δp. The footprint is therefore well above the
numerical uncertainty (P95 +0.37 bar; charging hours +0.86 bar mean). It depends on the calibration variant (A / C / B):
P95 2.543 / 2.537 / 2.537 → 2.909 / 2.743 / 2.663 bar (+0.37 / +0.21 / +0.13), hours > 4 bar 30 → 109 / 29 → 72 / 31 → 62, charging hours
+0.86 / +0.59 / +0.43 bar, discharging −0.16 / −0.15 / −0.13 bar: sign and mechanism robust, magnitude within a factor
≈ 2–3. Against measurements, V06 has a high-load holdout RMSE of 0.32 bar with weak correlation (r 0.18;
`hydraulic_calibration.md`) — the scenario difference is model-internal and should be reported as such.

## 11. South hosting capacity without new capacity — can the TES help? (2026-10-12, replaces section 6 in the paper)

*Author decision 2026-10-12: a new south boiler is not considered; the question is how much additional south demand the
existing network can serve and whether the TES raises that limit.* Set-up (`hosting.py`, `new_boiler.mode: unserved`):
new customers at the south nodes (share of today's total demand, today's hourly shape); no new capacity; heat that the
existing plants, pumps and PS1 head control cannot deliver to the new customers within the hydraulic limits is
**unserved heat** (penalty 1 000 EUR/MWh, ≤ the new customers' demand, withdrawn from the south nodes like their load);
Mode H, calibration A, perfect foresight. Hosting limit = last growth level without unserved heat. Values at equal
delivered heat: unserved heat charged at the HW1 heat cost (72.6 EUR/MWh). Mode H for a TES in the south uses
anticipatory cuts (all hours within 0.5 bar of a limit) and up to 20 iterations; remaining violations ≤ 0.05 bar count
as converged (larger residuals are marked).

**Reference limits (pump curves; KWK 4 bar as soft value):**

| south growth | no TES | TES at S (5 000 m³, 40 MW) | TES in the south at V06 (5 000 m³, 40 MW) |
|---|---|---|---|
| +15 % | served (redispatch 0.25 M EUR/a) | served (0.25 M) | – |
| +19 % | served (0.48 M) | – | – |
| +20 % | 2 MWh/a unserved, peak 1.1 MW, 2 h (0.54 M) | served (0.54 M) | served (0.82 M) |
| +21 % | – | 3 MWh/a, 1.2 MW | – |
| +22.5 % | 29 MWh/a, 5.2 MW, 13 h (0.72 M) | 20 MWh/a, 4.0 MW (0.72 M) | – |
| +25 % | 132 MWh/a, 9.3 MW, 40 h (0.90 M) | 97 MWh/a, 8.6 MW (0.92 M) | served (1.20 M) |
| +30 % | 1 039 MWh/a, 18.3 MW, 209 h (1.27 M) | – | served* (1.64 M; 4 h with ≤ 0.27 bar residual) |
| +35 % | 4 035 MWh/a, 27.7 MW, 635 h (1.57 M) | – | 1 628 MWh/a, 27.0 MW, 256 h (2.0 M) |

Large south TES (20 000 m³, 80 MW) at +35 %: 429 MWh/a, peak 27.0 MW, 64 h. Partners A + B do not change the south
hydraulics (F110 = F000 within 4 %; TES at S + A + B served at +15 / +20 %).

* **Hosting limit without new capacity:** no TES **+19 %** of today's total demand (≈ +100 % of today's south load);
  TES at S **+20 %**; TES in the south **+30…35 %**.
* **Why:** the binding limits are the pump curves of KWK, MVA and GT (V06 sets the KWK Δp in ≈ 95 % of the hours);
  the existing south peak boiler HW1 is redispatched to supply the south locally, which costs 0.25 → 1.3 M EUR/a
  (+15 → +30 %). A TES at S sits upstream of the bottleneck and changes almost nothing (+1 pp); a TES at the south
  end charges in low-load hours through the trunk and discharges locally at peak — it acts as local capacity.
* **Where it stops:** at +35 % the deficit lasts longer than the tank can bridge; the energy gap shrinks by 60 % (large
  tank 89 %), but the peak gap (27 MW) stays because the tank cannot be recharged through the bottleneck during the
  cold spell.
* **Value trade-off (equal delivered heat):** TES at S 445–456 kEUR/a (price shifting; today 406), TES in the south
  170–183 kEUR/a — the south location gives up ≈ 60 % of the market value but adds ≥ 10 pp of hosting capacity. The
  redispatch cost (Mode H − E) is higher with the south TES (0.82 vs 0.54 M at +20 %) because its energy-only schedule
  also charges through the bottleneck.
* **KWK Δp ≤ 4 bar as hard limit:** the hosting limit without TES falls to **+13.5 %** (0.6 MWh/a at +14 %; 4 MWh/a,
  2.1 MW at +15 %). With TES: see 11a.
* All growth levels drive the required KWK Δp to P95 7–8 bar (pump-curve case): the hosting limits above rely on the
  pump curves, not on the 4 bar experience value.

### 11a. Hosting capacity with KWK Δp ≤ 4 bar as hard limit

| south growth | no TES | TES at S | TES in the south at V06 |
|---|---|---|---|
| +13.5 % | served (redispatch 0.37 M EUR/a) | – | – |
| +15 % | 4 MWh/a, 2.1 MW, 3 h (0.46 M) | 0.2 MWh/a, 0.2 MW, 1 h (0.48 M) | served (0.73 M) |
| +17.5 % | – | 23 MWh/a, 5.2 MW (0.66 M) | – |
| +20 % | 197 MWh/a, 10.2 MW, 61 h (0.80 M) | – | served* (1.11 M; ≤ 0.12 bar residual) |
| +25 % | 1 531 MWh/a, 18.8 MW, 324 h (1.09 M) | – | 153 MWh/a, 17.9 MW, 32 h* (1.52 M; ≤ 0.44 bar residual) |

Hosting limit under the 4 bar rule: no TES **+13.5 %**, TES at S **≈ +15 %**, TES in the south **+20…25 %** (unserved
heat at +25 % −90 % vs no TES). Value at equal delivered heat: TES at S 425 kEUR/a (+15 %), TES in the south 134–177
kEUR/a. The ranking and the location trade-off of section 11 hold under the stricter operator rule; all limits shift
down by ≈ 5–10 pp.


## 13. Reviewer checks (2026-10-16): realistic demand forecasts, V06 correlation, achieved MIP gaps

**Realistic demand forecasts in the RH** (`run --rh-forecast`, `results/central_tes/rolling_horizon_forecast/`; all other
settings as the RH reference; the i.i.d. reference was re-run in the same folder and reproduces 217.0 / 323.6 k):

| variant | demand forecast | nRMSE day 1 / 2 / 3 | V_TES RH [k] (% PF 415.5) | v(F111) RH [k] (% PF 544.0) | TES discharge [GWh] |
|---|---|---|---|---|---|
| reference | actual × (1 + ε), ε i.i.d. N(0, 5 %) | 5.9 / 5.8 / 5.8 % | 217.0 (52 %) | 323.6 (59 %) | 18.3 |
| A1 | imputation demand model, leave-one-month-out fit, measured temperature | 18.0 / 18.1 / 18.0 % | 44.8 (11 %) | 84.7 (16 %) | 21.2 |
| A2 | A1 + daily-temperature error 1 / 2 / 3 K | 19.7 / 23.1 / 29.8 % | 26.8 (6 %) | 51.3 (9 %) | 21.1 |
| A3 | actual × (1 + ε), ε AR(1), σ 5 %, ρ 0.9 | 5.8 / 6.2 / 5.7 % | 208.1 (50 %) | 313.8 (58 %) | 18.2 |
| A4 | A1 + residual of the same hour of the last measured day, all lead times | 15.4 / 18.8 / 20.2 % | 111.6 (27 %) | 176.2 (32 %) | 18.7 |
| A4b | A4 with the correction × 0.7^lead day | 14.0 / 16.1 / 16.7 % | 99.4 (24 %) | 164.4 (30 %) | 19.4 |

The imputation model is not a forecast model (in-sample nRMSE 16 %). 68 % of the A1 forecast MSE is the error of the daily mean (daily-mean nRMSE 14.9 %), against 3.9 % (3.4 %) for i.i.d. σ 15 % with similar total nRMSE (17.4 %); the daily-mean residual has an autocorrelation of 0.66 / 0.45 / 0.33 at lag 1 / 2 / 3 days (basis of the 0.7 damping in A4b). With its errors the committed 24-h central schedule
is not corrected intraday; over-forecasts let committed storage/central heat displace waste-incineration heat (A1:
WI −5.1 GWh/a, GCHP +2.7 GWh/a vs the RH reference).

**V06 correlation** (`v06_check`, `results/central_tes/v06_check/`): holdout top load decile (241 h): measured V06 Δp
mean 1.20, SD 0.12 bar, 70 % of hours within ±0.1 bar of 1.2 bar (signal resolution 0.1 bar); modelled SD 0.31 bar;
r 0.18, RMSE 0.32, bias +0.07 bar (reproduced). V22 / V15 / V03: measured SD 0.55 / 0.59 / 0.37 bar, r 0.98 / 0.98 / 0.89.
All hours: V06 measured SD 0.24, modelled 0.31, r 0.31, RMSE 0.34, bias −0.10 bar.

**Achieved MIP gaps** (`solver_gaps`, `results/central_tes/solver_gaps/`): factorial PF E/H max 2.4·10⁻⁵ (0.36 k);
A1–A6 max 4.2·10⁻⁵ (0.64 k); other sensitivities max 6.2·10⁻⁵ (1.1 k) except P/tes_single_fixed/F011-E 8.0·10⁻⁴
(12.6 k); hosting max 5.3·10⁻⁵ (1.2 k); X/X4/XR/XN max 2.0·10⁻⁴ (4.5 k); RH windows (reference) max 9.7·10⁻⁴ per
window (0.36 k per 72-h window). Differences within these gaps: ΔC_hyd in T2, A2, B4; A6 cascade.
