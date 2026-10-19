# Scientific sanity check (spec section 14) — 2026-10-08 — VERSION 1, SUPERSEDED

> **Superseded.** These are the v1 numbers (single-state TES, old prices, two partner-A streams). The v2 answers are in
> `reports/central_tes/paper_readiness.md` (section 6); the v2 results in `results_v2.md` and `paper_tables.md`.

Reference: F111 with 5 MW HP (partner A), 10 MW EB (partner B, c_el,var high, π 10 EUR/MWh, no demand charge),
5 000 m³ / 296 MWh / 40 MW TES at 120 °C (fixed strategy), DN 400 link, 2025 data, perfect foresight, HiGHS.
All costs in EUR/a; "k" = kEUR/a. Mode E unless stated. Calibration A unless stated (C and B in brackets where they differ).

1. **Did TES increase partner-A utilisation (H1)?** Yes, but little: U_A 13.1 % (F100) → 15.0 % (F101), and
   13.2 % (F110) → 14.6 % (F111). Of the 30.4 GWh unused in F111, 20.2 GWh fall in hours with the HP off (summer/
   transition, when MVA and Bio-KWK heat at 10–17 EUR/MWh is cheaper than HP heat at COP ≈ 2) and 9.4 GWh in hours with
   the HP at its 5 MW limit (source peaks up to 51 MW on weekdays). The source limit binds in 2 745 h (nights/weekends).
   The temperature mask does not limit the HP→TES route. The cascade adds nothing measurable (A6: ≤ 0.9 k, below solver
   tolerance; ≤ 3.6 % of HP heat).
2. **Did TES shift partner-B operation to lower prices (H2)?** Yes: price-weighted electricity price −4.9 EUR/MWh (F010)
   → −7.4 EUR/MWh (F011) while full-load hours rise from 346 h to 573 h (annual mean price 89.3 EUR/MWh). The EB runs only
   in negative/very-low-price hours (max 31 EUR/MWh in F111) because the reference electricity cost is 60 EUR/MWh.
3. **Energy shifting or hydraulic relief?** Energy shifting. Mode H changes the TES value by ≤ 0.1 k in every A1
   case; with KWK ≤ 4.0 bar as hard limit (exploratory) ΔC_hyd rises to 29.6–29.9 k but is still independent of the
   central assets (spread 0.4 k). S does not relieve the binding south point V06.
4. **Does the central feed-in shift stagnation points (H3)?** Yes, moderately: flow reversals (|ṁ| > 10 kg/s in both
   states) on the south trunk L4b–L4d 162–258 h, L4a 147 h (85–147 h over A/C/B), the L1→City link M12 59 h (4–59 h),
   L1a 48 h (18–48 h), L5a 23–26 h; the KWK/east mixing boundary on L5 moves in 431 h (413–474 h), 387 h of them in the
   heating period. Water from S reaches K2 (≥ 10 %) in ≤ 2 h. The L4 reversals stem from the changed HW1 dispatch as
   much as from S itself.
5. **Are Mode-E schedules hydraulically infeasible?** Yes, in 91–97 h (A, C) and 98–105 h (B) in every scenario,
   including F000: east pump curves (MVA 77–90 h, GT 13–15 h) and once the KWK pump; mainly March and October, in hours
   where the energy-only dispatch runs HW1 at 0 MW and the GT high, so that the KWK must raise its Δp for V06.
6. **Attributable to the central feed-in, existing plants or demand?** Existing-plant dispatch: 0 of 93 h in F000 and
   only 0–8 h per scenario are attributable to S. Attributable hours grow with network charging and power (A3 daily
   22 h; A2x daily/80 MW 19 / 25 / 67 h for DN 300 / 400 / 500).
7. **ΔC_hyd relative to v(F111); does attribution change between E and H?** ΔC_hyd(F111) = 2.44 k (A), 2.47 k (C),
   2.63 k (B) = 0.6 % of v(F111) = 436.2 k, and 65 EUR/a *below* ΔC_hyd(F000). Shapley values change by ≤ 0.1 k
   (partner A 268.0 k, partner B 84.3 k, TES 83.9 k in E and H). Largest ΔC_hyd seen: 4.35 k (A2x, DN 500, daily, 80 MW).
8. **Robustness to TES power/energy, DN and strategy?** The value grows with energy more than with power (A1: 122 → 167 k
   from 5 000 to 20 000 m³ at 10 MW; 122 → 137 k from 10 to 80 MW at 5 000 m³) — **H5 is not supported** at 2025 load:
   power above ≈ 20 MW and the link DN (A2: spread 63 EUR/a) do not limit the value. The temperature strategy dominates:
   daily strategy +73 k on v(F111), +150 k on TES alone (network charging possible in 531 h instead of 43 h).
9. **How much does RH reduce the PF value (H7)?** v(F111) 436.2 k (PF) → 336.9 k (RH, partner A known day-ahead,
   −23 %) → 297.4 k (RH, persistence, −32 %). RH Mode H: 337.2 k. **H7 supported.**
10. **Statements depending on unconfirmed assumptions:** partner-A source temperature/profile (2023 data, ≈ 17 °C),
    HP size and η_C, partner-B electricity cost (A5: v(F111) 354–771 k) and demand charge (switches the EB off), TES
    reference size and the charging mask (A3), plant costs of the existing configuration (gas 58.6 EUR/MWh,
    CO2 100 EUR/t), MVA availability (monthly P95), control concept (KWK pressure holder all year, derived from data),
    pump curves (envelope-scaled), the 4.0 bar KWK experience value (soft).
11. **Does the τ × κ_link map transfer beyond DHN-A?** Only partly. At the 2025 load the link capacity is never
    binding (κ_link 0.24–0.61 give the same value), so the map collapses to a τ-curve: value rises with E (τ) and
    saturates in power above ≈ 20 MW, because the charging sources are small (15 MW) and the network can charge the TES
    only in few hours. The transferable insight is therefore the ratio of charging sources to TES power plus the
    charging mask, not κ_link. A κ_link effect appears only with network charging and high power (A2x).

CO2 (secondary, net incl. CHP power credit at the hourly grid factor): F000 34 019 t → F111 32 734 t (−3.8 %).
