# Changelog — framework v3

Edits arising from `04_literature_review.md` §10. Workbook and notebook both updated; validated
end to end.

---

## 1 · New connection regime: `FCA_TDTR` (85/15, day-ahead notice)

Calibrated to the Dutch time-dependent transport right: full access for at least 85 % of hours,
restriction rights over the remaining 15 %, notification at least one day ahead, grid tariff
discount in return. Implemented as a `dynamic` regime with `max_curtail_h_per_a = 1314`
(= 0.15 × 8760), `max_event_h = 4`, `notice_h = 24`.

Purpose: the German window and dynamic forms now have a deployed international product to be
benchmarked against, rather than being compared only to each other.

## 2 · New column `fca.notice_h` — notification interval as a contract variable

How far ahead a restriction becomes visible to the plant:

| Value | Meaning | Regimes |
|---|---|---|
| 0.25 | response time only — pessimistic reading of the German contract | `FCA_DYNAMIC` |
| 24 | day-ahead notification — the Dutch product | `FCA_TDTR` |
| ≥ horizon | fully known ex ante | `FCA_WINDOW`, `FCA_WINDOW_WIDE` |

`run_mpc(..., notice_override_h=...)` and `run_mpc_all_sites(..., notices=(0.25, 24.0))` sweep it
with **identical hardware**, so the difference is attributable purely to contract design. New
figure `fig_notice_value()` (F12). New sensitivity row `fca_notice` (0.25 / 24 / 168 h).

This is what turns §6 of the notebook from a caveat about perfect foresight into a result about
what a notification interval is worth.

## 3 · Two bugs found and fixed during validation

**3.1 — Curtailment budget was scaled by calendar years, not horizon length.** `_dynamic_calls()`
computed the number of call events from `max_h_per_a × index.year.nunique()`. On any sub-year run
— i.e. every screening run with `CFG["months"]` set — a one-month horizon received a *full year's*
curtailment. `FCA_TDTR` came out at 91 % restricted instead of 15 %. Now pro-rated by actual
horizon length. Full-year results were unaffected; every short run before this fix was wrong.

**3.2 — `restriction_bite` double-counted the conditioning.** It divided a quantity already
conditional on restricted intervals by the restricted share, producing values above 1. Replaced by
`restriction_bite_share = binding_restricted_share × restricted_share`: the share of *all*
intervals in which the contractual restriction actually constrains the plant.

## 4 · New KPIs

| KPI | Meaning |
|---|---|
| `restricted_share` | fraction of time the contract reserves the right to restrict |
| `binding_restricted_share` | of those intervals, the fraction in which the limit actually binds |
| `restriction_bite_share` | product of the two — how much of the year the restriction really costs |
| `binding_free_share` | limit binding outside restricted periods (diagnoses an undersized static capacity) |

The gap between `restricted_share` and `restriction_bite_share` is capacity the operator reserves
but never needs. That is the plant's strongest argument in a negotiation, and it is now a number.

## 5 · Sourcing

`HP.T_sink_max_C = 160 °C` now cites Arpagaus et al. (2018), *Energy* 152, 985–1010 — commercially
available HTHP sink temperatures of 90–160 °C, more than 20 models from 13 manufacturers, 20 kW to
20 MW. One fewer ⛔ secondary citation.

---

## 6 · What the edits produced — read this before the next run

Single site, January, screening resolution, `S4_TES_BES`:

| Regime | Time reserved | Of that, binding | Bite | TES |
|---|---|---|---|---|
| `FCA_FIRM` | – | – | – | 406 MWh |
| `FCA_WINDOW` (07–11, 13–18) | 27.8 % | **93.7 %** | 26.1 % | **193 MWh** |
| `FCA_TDTR` (85/15, day-ahead) | 15.1 % | **7.1 %** | 1.1 % | **59 MWh** |
| `FCA_DYNAMIC` (300 h/a) | 3.2 % | 8.3 % | 0.3 % | 58 MWh |
| `FCA_UPGRADE` | – | – | – | 55 MWh |

**The deterministic window is far more expensive for the plant than the dynamic regime, even
though it reserves less than twice as much time.** 193 MWh against 59 MWh — and the 85/15 dynamic
agreement lands within 7 % of a full grid upgrade's storage requirement.

The mechanism is visible in the "of that, binding" column. A scheduled block recurs every working
day and lasts five hours, so essentially every restricted interval binds: the plant must carry
enough storage to bridge the same long gap, every day, all year. Dynamic calls are dispersed and
short, and only a fraction of them ever bind, because they land on hours the plant was not heavily
drawing anyway.

**The intuition this overturns is worth the paper.** Predictability sounds like the friendlier
contract term — a plant knows exactly when it may not draw. It is not what matters. What drives
storage capital is *how long the longest recurring restricted block is*, and a predictable daily
block is the worst case on that measure. A regulator designing flexible connection products should
therefore prefer many short dispersed restrictions with notice over a few long scheduled ones,
even if the total restricted hours are higher.

Two caveats before this becomes a claim: the numbers are placeholder data over one month, and the
dynamic call placement is a price-percentile proxy. Confirm on the real profiles over a full year,
and vary the call seed. If it survives both, it is the paper's headline and the abstract should be
rewritten around it.

## 7 · Still open

* Intensive network use (7,000 h / 10 GWh, § 19 Abs. 2 S. 2 StromNEV) is still not modelled.
  Electrification pushes sites toward the threshold — an effect that works *against* peak shaving.
* The five reference gaps in `04_literature_review.md` §9.
* `fca.netzentgelt_discount` remains the single most economically decisive placeholder.
