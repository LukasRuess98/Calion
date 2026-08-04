# Literature review — technical field and flexible connections

Companion to `02_regulatory_basis_and_model_mapping.md`, which covers the German legal sources.
This document covers the two remaining strands and states the research gap the paper claims.

**Verification status.** ✅ = author list, title and venue confirmed from the record.
⚠ = located and relevant, but bibliographic detail (authors, year, volume, pages) still to be
completed before submission. ⛔ = cited only inside another paper; the primary must be obtained.
Do not paste a ⚠ or ⛔ entry into the manuscript without opening the primary source.

---

## 1 · Review method (write this into the paper)

Databases: Scopus, Web of Science, ScienceDirect, IEEE Xplore, arXiv; plus grey literature from
network operators, regulators and the Danish Energy Agency, which is where the contract and
tariff material lives. Search strings combined three blocks: *(industrial heat OR process heat OR
district heating)* × *(electrification OR heat pump OR electrode boiler OR power-to-heat)* ×
*(storage sizing OR peak shaving OR grid connection OR non-firm OR flexible connection)*.
Coverage 2015–2026, with older work retained where it is the origin of a concept. Screening on
title and abstract, then full text.

Note for the methods section: the flexible-connection material is largely **not** in the journal
literature. It sits in network operator contracts, regulator decisions and consultancy reports.
That asymmetry is itself a finding and worth one sentence — the instrument is being deployed
faster than it is being studied.

---

## 2 · Strand A — electrification of industrial heat

The temperature ceiling is the parameter that decides everything downstream, and it is now well
established. Arpagaus et al. reviewed high-temperature heat pumps with heat sink temperatures of
90–160 °C and identified more than twenty models from thirteen manufacturers on the market, with
capacities from 20 kW to 20 MW ✅. A 2025 review confirms the same band, treating 100–160 °C as
the conventional HTHP range and anything above as ultra-high-temperature ⚠. Recent work extends
the frontier — transcritical and large-glide cycles, CO₂ as refrigerant, solid-state and
gas-cycle approaches — but as research status, not as procurable equipment ⚠.

**Consequence for our model, and a defensible citation for it:** `HP.T_sink_max_C = 160` is not a
modelling convenience. Above it the electrode boiler must carry the load, which is why one of the
five sites in the framework (supply temperature 130 °C) sits near the boundary and another sits
above the comfortable range. This is exactly the kind of parameter a reviewer will probe, and it
now has a primary source.

Market potential has been quantified at European scale (Marina et al., RSER 2021 ⚠) and in
national climate pathways (Obrist et al., Energy Policy 2023 ⚠). Barriers are consistently
reported as much organisational as technical — awareness, skilled labour, integration ⚠.

## 3 · Strand B — power-to-heat and thermal storage, and how they are modelled

Maruf et al. provide the reference classification: they identify and classify the mature P2H and
TES technologies, report technology readiness levels, and — most useful for us — compile the
mathematical formulations in one place, explicitly motivated by the need for linear, tractable
representations in large energy-system models ✅. Our LP formulation follows that lineage and
should cite it as the modelling convention it adopts rather than reinventing.

Earlier work established the flexibility framing for power-to-heat with storage in the renewable
integration context ⚠, and the district-heating literature has since made TES the standard
flexibility asset ⚠.

**What this strand assumes throughout:** a firm grid connection. Storage is sized against
*prices* and *demand variability*. The connection is a background condition, not a constraint
with structure.

## 4 · Strand C — sizing HP, EB, TES and BES together

This is the closest existing work and must be engaged with directly, not just cited.

* A MILP determines the technology portfolio and equipment sizes at lowest total annual cost and
  finds that the **mean and variance of the electricity price** significantly influence the
  sizing of heat pumps, electric boilers and thermal storage ⚠.
* A 2026 review takes a unified view of energy storage options for thermal process
  electrification, comparing electrical and thermal storage on the same footing, and situates the
  prior sizing literature — battery sizing and dispatch under real-time pricing, thermal storage
  capacity co-optimised with arbitrage across markets, and joint selection and sizing of heat
  pumps, electric boilers and thermal storage for a utility system with fluctuating heat demand ⛔
  for each of those three primaries.

**Read honestly, this strand has already answered "TES or BES for electrified process heat?" in
the price-arbitrage framing.** Our paper must not re-answer it. What it can say is that the
answer *changes* when the binding constraint is a contractual power limit rather than a price
signal — which is what our placeholder runs show, with TES sizes moving by a factor of seven
across connection regimes while relative technology costs stay fixed.

## 5 · Strand D — battery storage against demand charges

A mature, largely separate literature sizes batteries to shave industrial peaks. Representative
work optimises component sizing while trading off energy purchase, peak-power tariff and battery
ageing ✅, and the recent generation adds degradation-aware sizing frameworks and demand-response
participation ⚠. A useful framing from this strand: peak-based tariffs are cost-reflective
because demand level drives network costs — reinforcement and transformer loading ✅.

**The distinction that creates our gap.** In this literature the peak is a *tariff* signal.
Exceeding it costs money. Under § 17 Abs. 2b EnWG, exceeding the agreed limit is a **contractual
breach with a liability consequence** the statute requires the parties to settle in advance. A
model in which the limit can be bought through at a price is the wrong model for a flexible
connection agreement. Ours treats it as hard and reports shortfall as unserved energy. That is a
small formal difference with a large consequence for sizing, and it is worth a paragraph in the
methods.

## 6 · Strand E — flexible and non-firm connections

The instrument Germany introduced in 2025 is not new in Europe; Germany is late to it. This is
the strand that internationalises the paper and it should carry the introduction.

**United Kingdom.** A decade of operational experience. Distribution operators offer constrained
or "non-firm" connections that limit either the times at which capacity may be used or the
capacity itself, managed through active network management, in order to avoid or defer
reinforcement ✅. One operator's published product list is strikingly close to our model's
regimes: an *import limited connection* where installed equipment exceeds the agreed import, and
a *timed connection* where capacity is subject to restrictions in specific time periods ✅ — the
latter is our `FCA_WINDOW` under a different name, and it applies to demand, not only generation.
Operators report avoided reinforcement savings in the millions of pounds, and in some cases such
a connection is the only route onto the network at all ⚠. The academic work in this strand is
predominantly network-side: assessing distribution limits for non-firm connection and estimating
the frequency and duration of curtailment ✅.

**Netherlands.** The most advanced and best-quantified case, and the one that gives us numbers.
Capacity restriction contracts were introduced in 2022 and non-firm transport agreements in 2024,
under which consumers take flexible instead of guaranteed capacity in exchange for **discounts on
their annual transport tariffs** ⚠. The transmission operator's time-dependent transport right
gives users full grid access at least 85 % of the time, reserves the right to restrict during the
remaining 15 %, and — critically for control design — **communicates restrictions at least one
day in advance** ✅. The scale of the underlying problem is documented: waiting lists of over
14,000 offtake requests totalling 9 GW at regional operators and 212 requests totalling 38 GW at
the transmission operator ⚠.

Two direct consequences for our framework, both of which I recommend adopting:

1. **Calibrate the restriction share.** The Dutch 85/15 split is a real, published parameter. Our
   `FCA_WINDOW` default (nine restricted hours on working days ≈ 27 % of all hours) is more
   severe than any deployed product. Report both, and use 15 % as the international reference
   point.
2. **Fix the notice assumption in the MPC.** Our dynamic regime currently reveals a call only
   within the response time, which is the pessimistic reading of the German contract. The Dutch
   product gives day-ahead notice. Run both — *no notice* and *day-ahead notice* — and the
   foresight-gap chapter becomes a comparison of contract designs rather than a caveat.

**Belgium and Spain.** Flexible connection is mandatory above a capacity threshold in Wallonia,
proposed in Flanders, and appears as future access agreements in Spain ⚠ — evidence that the
voluntary/mandatory design choice is live across Europe. The comparative analysis of voluntary
versus mandatory contracting for demand-side flexibility in distribution grids is the reference
work here ⚠.

**The closest single paper.** A study of contracting strategies for electrolysers securing grid
connection in the Dutch case uses bilevel programming to choose among firm and non-firm contract
types ⚠. It is the nearest thing to our question — a large flexible load facing non-firm
contract options — and the paper must position against it explicitly. The difference: that work
selects a *contract* for a single flexible asset; ours takes the contract as given and sizes a
*multi-asset heat supply with storage* behind it. Related work also notes that most customers
prefer firm connections unless substantial tariff reductions are offered ⚠, which is precisely
why `fca.netzentgelt_discount` is the parameter we flagged as economically decisive.

---

## 7 · The gap, stated for the introduction

Three literatures meet here and none of them covers the question:

| Strand | Sizes what, against what | What it assumes about the connection |
|---|---|---|
| A–C: industrial electrification, P2H, TES/BES sizing | HP, EB, TES, BES against energy prices and demand variability | firm, unconstrained |
| D: battery peak shaving | BES against demand charges | a price signal that may be exceeded at a cost |
| E: flexible and non-firm connections | network hosting capacity, curtailment allocation, contract choice | studied from the network's side, and overwhelmingly for **generation** |

The unoccupied position is the **connectee's design problem on the withdrawal side**: *given a
flexible connection agreement with a specified restriction structure, how must an electrified
industrial heat supply be sized?* That question has a hard, time-varying power constraint whose
parameters are dictated by contract law; it involves two storage media with an order-of-magnitude
cost difference; and its answer varies with load archetype in a way that the single-case studies
in strands C and D cannot show.

Three claims follow, each supported by an output the framework already produces:

1. **The restriction structure dominates the technology costs in setting storage size.** Across
   connection regimes at fixed technology cost, required thermal storage moves by roughly a
   factor of seven.
2. **There is a feasibility boundary, and it is predicted by load factor.** For high-load-factor
   continuous sites no storage size makes an unenlarged firm connection work — the model
   reproduces from first principles what network operators state as policy, that flexible
   connections bridge *temporary* congestion only.
3. **Restriction windows and tariff windows interact.** The FCA restriction periods and the
   § 19 Abs. 2 StromNEV high-load windows are set by different mechanisms; optimising against one
   can degrade the other. No prior study models both.

---

## 8 · Reference list, current state

**German legal and regulatory (16)** — see `02_regulatory_basis_and_model_mapping.md` §7.

**Strand A — industrial heat electrification**
1. ✅ Arpagaus, C., Bless, F., Uhlmann, M., Schiffmann, J., Bertsch, S. S. — High temperature heat
   pumps: market overview, state of the art, research status, refrigerants, and application
   potentials. *Energy* 152 (2018) 985–1010.
2. ✅ Arpagaus, C., Bless, F., Uhlmann, M., Schiffmann, J., Bertsch, S. S. — same title, Int.
   Refrigeration and Air Conditioning Conference, Paper 1876 (2018). *Conference version; cite one
   or the other, not both.*
3. ⚠ Adamson, K.-M. et al. — High-temperature and transcritical heat pump cycles and
   advancements: a review. *Renew. Sustain. Energy Rev.* 167 (2022) 112798.
4. ⚠ Mateu-Royo, C., Arpagaus, C., Mota-Babiloni, A., Navarro-Esbrí, J., Bertsch, S. S. —
   Advanced high temperature heat pump configurations using low GWP refrigerants for industrial
   waste heat recovery. *Energy Convers. Manag.* 229 (2021) 113752.
5. ⚠ Marina, A. et al. — An estimation of the European industrial heat pump market potential.
   *Renew. Sustain. Energy Rev.* 139 (2021) 110545.
6. ⚠ Obrist, M. et al. — High-temperature heat pumps in climate pathways for selected industry
   sectors in Switzerland. *Energy Policy* 173 (2023) 113383.
7. ⚠ Wu, D. et al. — *Int. J. Refrigeration* 69 (2016) 437–465.
8. ⚠ Emerging opportunities for high-temperature solid-state and gas-cycle heat pumps.
   *Nature Energy* (2025), doi 10.1038/s41560-025-01908-4.
9. ⚠ High-temperature heat pumps: key technologies and industrial applications toward
   carbon-neutral process heating. *Carbon Neutral Systems* (2025), doi 10.1007/s44438-025-00021-z.
10. ⚠ A technological update on heat pumps for industrial applications. *Energies* 17(19) (2024) 4942.
11. ⚠ Advances in high-temperature heat pump technologies … carbon dioxide as a refrigerant.
    *Energy Convers. Manag.* (2025), S0196890425014578.
12. ⛔ Fleiter, T. et al. — temperature split between HTHP and resistance heating. *Cited in
    arXiv:2506.14664; obtain primary.*

**Strand B — power-to-heat and thermal storage**
13. ✅ Maruf, M. N. I., Morales-España, G., Sijm, J., Helistö, N., Kiviluoma, J. —
    Classification, potential role, and modeling of power-to-heat and thermal energy storage in
    energy systems: a review. *Sustainable Energy Technologies and Assessments* 53 (2022) 102553.
14. ⚠ Power-to-heat for renewable energy integration: a review of technologies, modeling
    approaches, and flexibility potentials. *Applied Energy* (2018), S0306261917317889.
    *Verify author list before citing.*
15. ⚠ Role of power-to-heat and thermal energy storage in decarbonization of district heating.
    *Energy* (2024), S0360544224021467.
16. ⛔ Profaiser et al. — packed-bed TES storage efficiency. *Cited in arXiv:2506.14664.*
17. ⚠ Enerdata (2026) — The rise of industrial heat storage in Europe. *Grey literature; useful
    for the Heat-as-a-Service financing point in the discussion.*

**Strand C — joint sizing of electrification and storage**
18. ⚠ MILP portfolio and sizing study linking electricity price mean and variance to HP/EB/TES
    sizing. *Applied Thermal Engineering* (2025), S1359431125002947.
19. ⚠ A unified view of energy storage options for thermal process electrification.
    *Applied Energy* (2026).
20. ⛔ Shakrina et al. — battery sizing and dispatch under real-time pricing.
21. ⛔ Wikoff et al. — thermal storage capacity co-optimised with arbitrage dispatch.
22. ⛔ Bielefeld et al. — joint selection and sizing of HP, EB and TES for a utility system.
23. ⚠ arXiv:2506.14664 — advanced reliability reserve; source of the process-heat flexibility
    assumptions and of refs 12 and 16.

**Strand D — battery peak shaving**
24. ✅ Optimal component sizing for peak shaving in battery energy storage systems for industrial
    applications. *Energies* 11(8) (2018) 2048.
25. ⚠ Optimal sizing of BESS for peak shaving and demand response using a degradation-aware
    Bayesian optimisation–MILP framework. *Energy Convers. Manag.* (2025), S0196890425014712.
26. ⚠ Optimal sizing of battery storage for cost-effective peak shaving in regional distribution
    networks. *J. Energy Storage* (2025), S2352152X25042161.
27. ⚠ Comparative analysis of BESS operation strategies for peak shaving in industries with or
    without installed photovoltaic capacity (2024), S1755008424000383.

**Strand E — flexible and non-firm connections**
28. ✅ Boehme, T., Harrison, G. P., Wallace, A. R. — Assessment of distribution network limits for
    non-firm connection of renewable generation. *IET Renewable Power Generation*.
29. ⚠ Demand-side flexibility in distribution grids: voluntary versus mandatory contracting.
    *Energy Policy* (2022), S0301421522005614.
30. ⛔ Beckstedde et al. (2019) — European survey of flexible connection practice.
    *Cited in ref 29.*
31. ✅ Energy Networks Association — Open Networks, Flexibility Connections: Explainer and Q&A,
    August 2021.
32. ✅ Energy Networks Association — Open Networks WS2 P4, Connection Agreement Review, Jan 2022.
33. ⚠ Energy Systems Catapult (2025) — Active Network Management: opportunities and risks for
    smart local energy systems.
34. ✅ Electricity North West — Flexible connections product definitions (import limited
    connection, timed connection).
35. ⚠ UK Power Networks — Flexible connections and curtailable connection access arrangement.
36. ⚠ arXiv:2606.03887 — A dynamic capacity allocation model for DERs under non-firm connection
    agreements.
37. ⚠ arXiv:2502.09748 — Contracting strategies for electrolyzers to secure grid connection: the
    Dutch case. **Position against this one explicitly.**
38. ✅ TenneT — Time-dependent transport rights (TDTR): ≥ 85 % access, ≤ 15 % restriction,
    day-ahead notification, tariff discount.
39. ⚠ Regulatory Assistance Project (2024) — Gridlock in the Netherlands.
40. ⚠ Van Doorne (2024) — Alternative and flexible transmission capacity rights in the Netherlands.
41. ⚠ Stibbe (2026) — Parliamentary letter on grid congestion: eight measures.
42. ⚠ Taylor Wessing (2025) — Grid capacity in the Dutch energy sector.

**Techno-economic data**
43. ✅ Danish Energy Agency — Technology Data catalogues (electricity and district heating; energy
    storage). Cite the specific catalogue, version and datasheet used.
44. ⚠ IEA HPT Annex 48 — Industrial Heat Pumps, Task 1 and Task 2 national reports.

## 9 · Count and what is still missing

Verified or located: **16 German legal/regulatory + 44 technical = 60**. Of these, 14 are ✅ fully
confirmed, 38 are ⚠ located but need bibliographic completion, 8 are ⛔ secondary and must be
obtained as primaries.

To reach a defensible ~70 and, more importantly, to close real holes:

* **Industrial demand-side flexibility potential** — 4–6 refs. Currently absent; a reviewer will
  expect the demand-response framing alongside the storage framing.
* **Grid connection queues and reinforcement lead times in Germany** — 3–4 refs. The paper's
  motivation rests on this and it is currently asserted rather than cited.
* **Biomethane certification, additionality and price** — 3–4 refs. Your baseline depends on it,
  and the additionality debate is contested enough that ignoring it is a reviewer risk.
* **Model predictive control for industrial energy systems** — 3–4 refs, to support §6 of the
  notebook.
* **§ 19 StromNEV and industrial network tariffs in the academic literature** — 2–3 refs.

That is one further search session, and it is better spent than padding the existing strands.

## 10 · Recommended changes to the framework arising from this review

1. Add a **day-ahead notice** variant to the dynamic regime, alongside the current
   response-time-only visibility. Justified by the Dutch product; turns the MPC chapter into a
   contract-design comparison.
2. Add an **85/15 reference regime** calibrated to the Dutch TDTR so the German window case has an
   international benchmark.
3. Report the **binding-share** KPI against the contractual restriction share — the gap between
   "hours the DSO restricts" and "hours the limit actually binds" is a clean, quotable result.
4. Keep `T_sink_max_C = 160` and cite Arpagaus et al. (2018) for it.
