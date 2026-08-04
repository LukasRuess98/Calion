# Regulatory basis of the model — and how each legal element becomes a constraint

This is the "make the tool realistic" layer you asked for first. Every modelling choice in
`fca_electrification_framework.ipynb` is traced to a legal provision or an actual network
operator contract, so that the methods section can be written straight from this document.

**Verification status.** Primary legal texts are cited from the official consolidated version.
Items marked ⚠ come from secondary or trade sources and must be checked against the primary
source before they go into the manuscript.

---

## 1 · The instrument: flexible connection agreement, § 17 Abs. 2b EnWG

Since 2025 German law expressly provides for flexible connection agreements. Two parallel
provisions exist, and **only one of them is relevant here**:

| Provision | Covers | Relevant to us |
|---|---|---|
| § 8a EEG 2023 | renewable generators, **feed-in only** | no |
| **§ 17 Abs. 2b EnWG** | all connectees under § 17 Abs. 1 EnWG, **withdrawal *and* feed-in** | **yes** |

An industrial site electrifying its heat supply is an `Anschlussnehmer` increasing its
*withdrawal*, so § 17 Abs. 2b EnWG is the governing norm. This matters for the framing of the
paper: most of the current FCA literature and practice is about generators and batteries feeding
in. The withdrawal case — a factory that wants more power than the connection can firmly give —
is the same instrument applied to the opposite direction, and it is much less studied.

**What the statute requires the contract to contain** (§ 17 Abs. 2b S. 3 EnWG). The agreement
gives the network operator the right to demand a **static or dynamic limitation** of the maximum
withdrawal or feed-in power, and must in particular settle:

1. the **level** of the limitation,
2. the **period or periods** of the limitation,
3. …
5. the connectee's **liability if the agreed maximum is exceeded**.

Source: § 17 EnWG, consolidated text, <https://www.gesetze-im-internet.de/enwg_2005/__17.html>

Three modelling consequences follow directly:

* Items 1 and 2 are exactly the parameters `P_static_rel` / `P_flex_rel` and
  `restricted_hours` / `restricted_weekdays` / `restricted_months` in the `fca` sheet. The
  statutory content of the contract *is* the model's parameter set. That is a strong methods
  argument: the model is parameterised by what the law obliges the parties to write down.
* The static/dynamic distinction is why `fca.type` has both a `window` (deterministic, known
  ex ante) and a `dynamic` (called, unknown ex ante) variant. They are not two modelling
  conveniences — they are the two legal forms.
* Item 5, liability for exceedance, is why the model treats $p_g(t)\le P_\mathrm{limit}(t)$ as a
  **hard** constraint and pushes any shortfall into the unserved-energy variables instead of
  allowing an overshoot at a penalty price. An FCA overshoot is a contractual breach, not a
  tariff item.

Whether a network operator offers an FCA at all is discretionary ("können… anbieten"). The BEE
argued in the legislative consultation that connectees should have a general right to one, and
that a refusal should at least have to be justified transparently — evidence that the
availability of the instrument is itself contested, which belongs in the discussion section.
Source: BEE, Stellungnahme zur Änderung des Energiewirtschaftsrechts, 2025,
<https://www.bee-ev.de/service/publikationen-medien/beitrag/stellungnahme-zur-aenderung-des-energiewirtschaftsrechts>

## 2 · What an actual contract looks like

A published network operator contract under § 17 Abs. 2b EnWG (SachsenNetze, version 09/2025)
gives the operational structure the model reproduces:

* because of capacity bottlenecks — expressly including the upstream transmission network — the
  operator specifies a **reduced static connection capacity**;
* **in addition**, it offers a capacity that is limited in time and in magnitude, the **dynamic
  withdrawal power**, whose level the operator sets and which forms part of the agreement;
* the operator issues a **setpoint as a percentage of the contractually agreed maximum dynamic
  withdrawal**; the reduction must be fully implemented by the end of the **response time**,
  which runs from the call until the setpoint is reached;
* the restriction is released by a call with setpoint 100 %.

Source: SachsenNetze, Flexible Netzanschlussvereinbarung gemäß § 17 Abs. 2b EnWG, 09/2025,
<https://www.sachsen-netze.de/wps/wcm/connect/netze/13102dc5-edb4-4e8f-aee2-66635b2455ec/Flexible-Netzanschlussvereinbarung-SachsenNetze.pdf>

This maps one-to-one onto the model:

| Contract element | Model object |
|---|---|
| static connection capacity | `P_static_rel × P_grid_exist` |
| dynamic withdrawal power | `P_flex_rel × P_grid_exist` |
| setpoint call | `_dynamic_calls()` → `restricted` mask |
| response time | `MPC.response_time_min`; in the MPC the call becomes visible only this far ahead |
| release (setpoint 100 %) | end of the event, `max_event_h` |

**Modelling assumption that needs stating in the paper:** calls are placed on the highest-priced
non-overlapping windows, on the reasoning that distribution congestion correlates with system
stress. This is a proxy, not a measurement. It is varied by seed in the robustness runs, and the
honest alternative — a call series supplied by the network operator — should be requested if the
project has an industrial partner.

## 3 · Practice, and the limits of the instrument

* A model contract for FCAs was developed on behalf of the Fachagentur Wind und Solar and
  published; further templates are to follow during 2026. The parties involved describe the work
  as legal and technical new ground.
  Source: DOMBERT Rechtsanwälte, 05/2026, <https://dombert.de/mustervertrag-fuer-flexible-netzanschlussvereinbarungen-fcas-veroeffentlicht/>;
  Fachagentur Wind und Solar, <https://www.fachagentur-wind-solar.de/veroeffentlichungen/mustervertraege/mustervertrag-fcas>
* Network operators are rolling out FCA-based products during 2026, beginning with stand-alone
  battery storage. Sources: MITNETZ STROM,
  <https://www.mitnetz-strom.de/energie-einspeisen/fca---flexible-netzanschlussvereinbarung>;
  energis-Netzgesellschaft (roll-out planned for Q3 2026),
  <https://www.energis-netzgesellschaft.de/fuer-zuhause/einspeisung/fca-flexible-netzanschlussvereinbarung.html>
* **The key qualification, and a sentence the paper should quote-check and cite:** FCAs only help
  with *temporary* overloads. If a network section is permanently congested, reinforcement is
  still required (MITNETZ STROM, ibid.).

That last point is the physical counterpart of what the model already produces: the distinction
between a site that a time-window FCA can serve and one where storage cannot bridge the
restricted periods no matter how large it gets. The regulatory literature states the principle;
this paper quantifies where the boundary lies for a given load profile. **That is the
contribution.**

* The Bundesnetzagentur maintains an FCA FAQ page.
  <https://www.bundesnetzagentur.de/DE/Fachthemen/ElektrizitaetundGas/Netzanschluss/start.html>

## 4 · The second regulatory layer: § 19 Abs. 2 StromNEV

Independent of the FCA, the *charging* of network use is time-structured, and the two structures
interact.

Under § 19 Abs. 2 StromNEV, final consumers may agree an individual network charge if either

* their **annual peak load predictably falls in low-load periods** (atypical network use,
  S. 1), or
* they use the network **particularly intensively** — at least 7,000 utilisation hours and
  10 GWh per year (S. 2).

Agreements must be notified to Beschlusskammer 4. Source: Bundesnetzagentur,
<https://www.bundesnetzagentur.de/DE/Beschlusskammern/BK04/BK4_71_NetzE/BK4_71_Ind_NetzE_Strom/BK4_Ind_NetzEntg_Strom.html>

For atypical users the network operator publishes annual **high-load time windows**
(Hochlastzeitfenster, HLZF), and the charge is then based on the peak *within* those windows
rather than the absolute annual peak. ⚠ The magnitude of the reduction — trade sources state up
to 80 %, i.e. down to 20 % of the standard rate — must be verified against the Festlegung and
the operator's price sheet before publication. ⚠ Secondary sources also state a minimum
differential of 100 kW between the in-window and out-of-window peak; verify.
Secondary sources: <https://www.eha.net/blog/details/stromnev-individuelle-netzentgelte.html>,
<https://wert-e.de/leistungen/energiewirtschaft/atypische-netzentgelte-gemaess-%C2%A7-19-abs-2-stromnev/>

**Why this belongs in the model.** The FCA restriction windows and the HLZF are set by different
mechanisms and need not coincide. A plant that shifts its heat production out of the FCA
restriction windows may push it straight into an HLZF and lose its individual network charge, or
conversely may qualify for one it did not have before. The framework represents both — `fca` and
`hlzf` — and bills the capacity charge on `billed_peak_MW`, computed over the HLZF mask where the
site is eligible. To our knowledge this interaction has not been quantified. It is the second
novel element of the paper after the withdrawal-side FCA sizing itself.

**Live policy risk, and an opportunity.** Beschlusskammer 4 has opened a procedure aimed at
replacing § 19 Abs. 2 StromNEV with a special network charge for industrial customers that sets
system-serving incentives, taking the view that reform of the industrial network charge discounts
is unavoidable because the present rules no longer match a system dominated by renewable
generation (source as above). The paper should therefore **not** present the current § 19
parameters as fixed. Better: treat the discount level and the HLZF definition as policy variables
in the sensitivity study, and report what a designer would build under each. That converts a
threat to the paper's shelf life into a policy-relevant result.

## 5 · Consolidated mapping: law → constraint

| Legal element | Source | Model |
|---|---|---|
| static or dynamic limitation of withdrawal | § 17 Abs. 2b S. 2 EnWG | `fca.type` ∈ {static, window, dynamic} |
| level of limitation | § 17 Abs. 2b S. 3 Nr. 1 | `P_static_rel`, `P_flex_rel` |
| periods of limitation | § 17 Abs. 2b S. 3 Nr. 2 | `restricted_hours/weekdays/months`, `max_curtail_h_per_a`, `max_event_h` |
| liability for exceedance | § 17 Abs. 2b S. 3 Nr. 5 | constraint III is hard; shortfall → `q_u`, `p_u` |
| setpoint call and response time | DSO contract, § 2.3 ff. | `_dynamic_calls()`, `response_time_min`, MPC visibility |
| FCA only bridges temporary congestion | DSO guidance | infeasible regimes reported as unserved energy, not hidden |
| atypical network use | § 19 Abs. 2 S. 1 StromNEV | `hlzf` sheet, `billed_peak_MW`, `atypical_discount_max` |
| intensive network use (7,000 h / 10 GWh) | § 19 Abs. 2 S. 2 StromNEV | post-hoc `intensive_eligible` (`util_hours_h`, `annual_energy_GWh`) + optional two-pass discount `intensive_discount_max`; `runner.solve_intensive_two_pass` |
| firm connection, no FCA | § 17 Abs. 1 EnWG | `FCA_FIRM` |

## 6 · Open regulatory items

1. **Intensive network use (Bandlast) — now modelled (post-hoc).** Electrifying heat *raises* both
   utilisation hours and annual consumption, so a site may cross the 7,000 h / 10 GWh threshold
   *because* of the project and gain a discount — a driver working against peak shaving. Implemented
   as an eligibility check (`util_hours_h = annual grid energy / annual peak`, `annual_energy_GWh`)
   reported on every solve, plus a two-pass re-solve (`runner.solve_intensive_two_pass`) that
   applies `ECON.intensive_discount_max` to the capacity charge once eligibility is confirmed; it is
   *not* an LP binary (rule 6). Early finding on placeholder data: peak-shaving window/dynamic
   regimes sit just under 7,000 h, but the static reduced-connection and upgrade regimes force
   band-load and clear it — the two § 19 layers interact. ⚠ The discount *magnitude* (floor ~20 %
   of the standard charge, i.e. up to 80 %) and the tiered 7,000/7,500/8,000 h structure are not yet
   verified against the Festlegung — `intensive_discount_max` is a single-tier PLACEHOLDER, treat as
   a sensitivity/policy variable like `atypical_discount_max`.
2. **Reduced network charge in exchange for the FCA.** `fca.netzentgelt_discount` is currently a
   placeholder. Whether, and by how much, accepting an FCA reduces the charge is the single most
   important economic parameter in the study and must come from an actual offer.
3. **Baukostenzuschuss** for the reinforcement alternative — currently one lump figure in
   `ECON.grid_reinforcement_EUR_per_MW`; needs the applicable calculation basis.
4. **Electricity tax and levy treatment** of heat pumps and electrode boilers in an industrial
   installation.
5. **EU layer** — the 2024 electricity market design reform and the network codes on flexible
   connections have not yet been reviewed here. Needed for a journal with a European readership.

## 7 · Sources cited in this document

Primary law
1. § 17 EnWG (consolidated), esp. Abs. 2b. <https://www.gesetze-im-internet.de/enwg_2005/__17.html>
2. § 8a EEG 2023 (feed-in FCAs) — referenced in § 17 Abs. 2b S. 4 EnWG.
3. § 19 Abs. 2 StromNEV — via BNetzA BK4, below.

Regulator
4. Bundesnetzagentur, Netzanschluss / FCA FAQ. <https://www.bundesnetzagentur.de/DE/Fachthemen/ElektrizitaetundGas/Netzanschluss/start.html>
5. Bundesnetzagentur BK4, Individuelle Netzentgelte Strom gemäß § 19 StromNEV, incl. the announced
   procedure on a special industrial network charge. <https://www.bundesnetzagentur.de/DE/Beschlusskammern/BK04/BK4_71_NetzE/BK4_71_Ind_NetzE_Strom/BK4_Ind_NetzEntg_Strom.html>

Contracts and practice
6. SachsenNetze, Flexible Netzanschlussvereinbarung gem. § 17 Abs. 2b EnWG, 09/2025.
7. Fachagentur Wind und Solar, Mustervertrag FCAs.
8. DOMBERT Rechtsanwälte, Mustervertrag für FCAs veröffentlicht, 05/2026.
9. MITNETZ STROM, FCA product page (incl. the temporary-vs-permanent congestion limitation).
10. energis-Netzgesellschaft, FCA product page (roll-out Q3 2026).

Commentary
11. Stiftung Umweltenergierecht, Was sollte in flexiblen Netzanschlussverträgen geregelt werden?, 09/2025.
12. Bird & Bird, Flexibler Flaschenhals — Chancen und Risiken der neuen Regelungen zu FCAs.
13. Chatham Partners, Flexible Netzanschlussvereinbarungen — Booster für die Stromspeicherindustrie?
14. BEE, Stellungnahme zur Änderung des Energiewirtschaftsrechts, 01/2025.
15. Clearingstelle EEG, häufige Rechtsfrage on flexible Netzanschlussvereinbarungen (2026),
    reported by Solarserver and top agrar.
16. zfk, Flexible Netzanschlüsse: worüber die Branche jetzt diskutiert, 06/2026.

Full bibliographic details (author, exact title, date of access) still need to be completed for
the manuscript; the URLs above are the retrieval points.
