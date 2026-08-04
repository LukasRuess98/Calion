# Manuscript draft v0.1

**Status.** Introduction and Method are drafted to near-submission quality and are not blocked by
your data. Case studies, Results, Discussion and Conclusions are scaffolds, as agreed — each
carries the argument it has to make, the figure or table that supports it, and the sentence
pattern to fill once the measured profiles are in. Numbers appear as `[XX]`.

Citation keys refer to `04_literature_review.md` §8 (technical, refs 1–44) and
`02_regulatory_basis_and_model_mapping.md` §7 (legal, refs L1–L16). Anything marked ⚠ or ⛔ in
those documents must be opened and verified before it survives into a submitted version.

---

## Title

**Sizing an electrified industrial heat supply behind a flexible connection agreement: thermal
and battery storage under a time-varying grid limit**

Alternatives, in decreasing order of my preference:

* *What can you build behind a flexible connection agreement? Storage sizing for industrial heat
  electrification under contractual power limits*
* *Restriction windows, not technology costs, determine storage size in industrial heat
  electrification*
* *From firm to flexible: designing electrified industrial heat supply under non-firm grid access*

The third is the safest for an international readership; the second is the one that states the
finding and will be read.

## Highlights

* Industrial heat electrification is sized against a contractual, time-varying grid limit rather
  than a firm connection.
* Flexible connection agreements are formalised from their statutory contract content, giving a
  directly parameterised optimisation constraint.
* Required thermal storage varies by a factor of `[XX]` across connection regimes at constant
  technology cost.
* A feasibility boundary predicted by load factor separates sites a flexible agreement can serve
  from those it cannot.
* Restriction windows and high-load tariff windows interact; optimising against one degrades the
  other.

## Abstract

Electrifying industrial process heat with heat pumps and electrode boilers raises the electrical
peak load of a site far above its existing grid connection, at a time when reinforcement is
subject to multi-year queues across Europe. Network operators increasingly respond with flexible
or non-firm connection agreements, which grant additional capacity subject to a static or dynamic
limitation of withdrawal. Germany introduced such agreements in 2025 under § 17 Abs. 2b EnWG;
comparable instruments exist in the Netherlands, the United Kingdom, Belgium and Spain. The
design problem this creates for the connectee — how to build an electrified heat supply behind a
contractually restricted connection — has not been addressed. This paper formalises the flexible
connection agreement as a time-varying power constraint whose parameters are exactly those the
statute obliges the contract to specify, and embeds it in a linear programme that co-optimises
the sizing and 15-minute dispatch of heat pumps, electrode boilers, thermal storage and battery
storage for full decarbonisation of the heat supply. The framework is applied to five industrial
sites spanning continuous, multi-shift, batch and campaign load archetypes, across six connection
regimes from a firm unenlarged connection to a full upgrade, over `[2023–2025]` at 15-minute
resolution. We find that the restriction structure of the agreement, not the relative cost of the
storage technologies, dominates the required storage capacity: thermal storage requirements vary
by a factor of `[XX]` across regimes while technology costs are held constant. A feasibility
boundary emerges that is predicted by the site's load factor, separating sites for which storage
can bridge the restricted periods from those for which no storage size suffices — a quantitative
counterpart to network operators' position that flexible agreements address temporary congestion
only. We further show that the agreement's restriction windows interact with the high-load
windows used to assess individual network charges, so that optimising against one can forfeit the
benefit of the other. Under a rolling-horizon controller with forecast error and unannounced
curtailment, `[XX]` % of the perfect-foresight benefit is retained, and day-ahead notification of
restrictions recovers `[XX]` of the shortfall. The results give plant operators a contract space —
the set of agreements a given design can accommodate — rather than a single sizing figure, and
give network operators evidence on how contract design propagates into industrial investment.

**Keywords:** industrial heat electrification; flexible connection agreement; non-firm connection;
thermal energy storage; battery storage; grid congestion; optimal sizing

---

## 1 · Introduction

### 1.1 The constraint has moved

Process heat is the largest single component of industrial final energy demand in Europe, and
below roughly 160 °C it can be supplied electrically with mature equipment: high-temperature heat
pumps are commercially available across the 90–160 °C sink range from a substantial number of
manufacturers and at capacities relevant to industrial sites [1], with electrode and resistance
boilers covering the temperatures above [13]. The technical question of *whether* industrial heat
can be electrified is largely settled for this temperature band.

What has not moved with it is the grid connection. A site that replaces a gas boiler with heat
pumps and electrode boilers adds an electrical load comparable to its entire existing demand, and
does so at the moment its heat demand peaks — which for space-heating-influenced sites coincides
with system peak. The result is a connection request the network frequently cannot serve.
The scale is documented most clearly in the Netherlands, where regional operators hold waiting
lists of over 14,000 offtake requests totalling 9 GW and the transmission operator a further
38 GW [41], but the phenomenon is European.

### 1.2 The regulatory response, and what it asks of the connectee

Rather than queue, network operators increasingly offer access on non-firm terms. The United
Kingdom has a decade of practice: constrained connections that limit either the capacity or the
times at which it may be used, administered through active network management, explicitly to
avoid or defer reinforcement [31, 32]. One operator's product catalogue includes an *import
limited connection* and a *timed connection*, the latter subject to restrictions in specific time
periods [34] — that is, a scheduled power limit on withdrawal. The Netherlands has gone furthest
in codifying the trade: capacity restriction contracts from 2022 and non-firm transport
agreements from 2024, under which consumers accept flexible instead of guaranteed capacity in
return for a reduction in annual transport tariffs [37]; the transmission operator's
time-dependent transport right guarantees full access for at least 85 % of hours, reserves
restriction rights for the remaining 15 %, and notifies restrictions at least one day ahead [38].
Flexible connection is mandatory above a threshold in Wallonia and proposed or emerging elsewhere
[29, 30].

Germany introduced the instrument in 2025. Under § 17 Abs. 2b EnWG a network operator may offer a
connectee a flexible connection agreement giving the operator the right to demand a static or
dynamic limitation of maximum withdrawal or feed-in power [L1]. Critically for what follows, the
statute prescribes the agreement's content: the level of the limitation, the period or periods of
limitation, and the connectee's liability if the agreed maximum is exceeded [L1]. Published
operator contracts implement this as a reduced firm capacity plus a time- and magnitude-limited
dynamic withdrawal capacity, with setpoints called by the operator and a contractual response
time [L6].

For the plant, this converts a background condition into a design constraint. Capacity is
available, but not always, and the times are written into a contract. Whether the site can
electrify then depends on whether it can move heat production out of the restricted periods — that
is, on storage.

### 1.3 What the literature does and does not cover

Three literatures approach this and none of them occupies the position.

The first sizes electrified heat supply against energy and price signals. Power-to-heat and
thermal storage technologies have been classified and their tractable linear formulations
compiled [13]; joint optimisation of heat pump, electrode boiler and thermal storage portfolios
shows that the mean and variance of the electricity price significantly influence the resulting
sizes [18]; and a recent review takes a unified view of electrical versus thermal storage for
process electrification [19]. Throughout this strand the connection is firm.

The second sizes batteries against demand charges [24–27]. Here the peak is a tariff signal:
it is cost-reflective precisely because demand drives network cost [24], and it can be exceeded at
a price. Under a flexible connection agreement it cannot — exceedance is a breach whose
consequences the statute requires the parties to settle in advance [L1]. A model in which the
limit is purchasable is structurally the wrong model.

The third studies non-firm connections themselves, but from the network's side and overwhelmingly
for generation: distribution limits and expected curtailment frequency and duration for non-firm
renewable connections [28], allocation of restricted capacity and the fairness–efficiency
trade-off [29], the design choice between voluntary and mandatory contracting [29]. The nearest
work on the demand side selects among firm and non-firm contract types for electrolysers in the
Dutch market using bilevel programming [37]. That paper chooses a *contract* for a single flexible
asset. It does not size a multi-asset heat supply behind a given contract.

### 1.4 Contribution

This paper takes the flexible connection agreement as given and asks the connectee's question.
Specifically:

1. It **formalises the agreement as an optimisation constraint** whose parameters are the
   statutory contract contents — limitation level, limitation periods, and the hardness of the
   limit implied by the liability provision — so that the model is parameterised by what the law
   obliges the parties to write down rather than by modelling convention.
2. It **co-optimises sizing and dispatch** of heat pumps, electrode boilers, thermal storage and
   battery storage under that constraint, for full decarbonisation of the heat supply, at
   15-minute resolution over three years.
3. It applies this consistently across **five load archetypes and six connection regimes**,
   which is what allows the feasibility boundary to be identified rather than assumed.
4. It models the **interaction with time-differentiated network charges** — the high-load windows
   that determine individual network charges under § 19 Abs. 2 StromNEV — which are set by a
   different mechanism than the agreement's restriction windows and need not coincide.
5. It reports the **contract space**: for each design, the minimum uplift and the maximum
   restriction width that remain feasible. This is the object a plant needs when negotiating, and
   it is not a single sizing number.

---

## 2 · Method

### 2.1 Overview

The framework takes measured 15-minute electricity and heat demand for a site, a connection
regime, a storage configuration, and market and tariff data, and returns cost-optimal asset sizes
together with the dispatch that achieves them. One linear programme is solved per triple *(site,
storage configuration, connection regime)*. Sizing and dispatch are co-optimised under perfect
foresight; a rolling-horizon controller (§2.7) quantifies the loss when foresight is removed.

All inputs are held in a single workbook; no site, asset, tariff or contract value is embedded in
the code. This is a reproducibility measure and it is also what makes the sensitivity design in
§2.8 mechanical rather than bespoke.

### 2.2 Connection regimes

The grid connection appears as a time series $P_\text{limit}(t)$ rather than a scalar. It is
constructed from the contract parameters that § 17 Abs. 2b EnWG requires the agreement to state:

$$
P_\text{limit}(t) =
\begin{cases}
\alpha P_\text{exist} & t \in \mathcal{R} \\
\beta P_\text{exist} & t \notin \mathcal{R}
\end{cases}
\qquad \beta \ge \alpha
$$

where $P_\text{exist}$ is the site's existing firm connection, taken as the historical maximum of
its measured electricity demand; $\alpha$ is the static (always available) capacity as a fraction
of it; $\beta$ the capacity available outside restriction; and $\mathcal{R}$ the set of restricted
intervals. Six regimes are studied:

| Regime | $\mathcal{R}$ | Represents |
|---|---|---|
| firm | ∅, $\beta=\alpha=1$ | today's connection, no upgrade |
| firm upgrade | ∅, $\beta$ free | reinforcement, charged at $c_\text{reinf}$ per MW |
| static | all $t$ | *statische Begrenzung*: reduced but firm capacity |
| window | scheduled hours and weekdays | *zeitliche Begrenzung*, known ex ante |
| window (wide) | extended schedule | sensitivity on restriction width |
| dynamic | operator-called events | *dynamische Begrenzung*, not known ex ante |

For the dynamic regime, calls are placed on the highest-priced non-overlapping windows of the
contractual event duration, up to the contractual annual limit, on the reasoning that
distribution congestion correlates with system stress. This is a proxy; it is varied by seed in
the robustness analysis, and a call series obtained from a network operator would replace it.

The liability provision of § 17 Abs. 2b EnWG is represented by making the constraint hard.
Shortfall is not priced through; it appears as unserved heat and unserved electricity (§2.4),
so that an infeasible regime returns *how much* cannot be supplied instead of failing.

### 2.3 Asset models

Assets are linear; unit commitment, part-load characteristics and start-up costs are deliberately
excluded at this stage, following the tractable formulations compiled in [13].

**Heat pump.** Thermal output $\text{COP}(t)\,p_\text{hp}(t)$, with

$$\text{COP}(t) = \eta_\text{C}\,\frac{T_\text{sink}}{T_\text{sink}-T_\text{source}(t)}$$

clipped to $[\text{COP}_\min, \text{COP}_\max]$. The source temperature follows ambient
temperature for air-source sites and is constant for waste-heat sources. A heat pump is
admissible only where $T_\text{sink} \le T_\text{sink}^{\max}$, set to 160 °C on the basis of the
commercially available sink temperature range reported in [1]; above it the electrode boiler
carries the load. This gate is not cosmetic — it determines the technology split at the
high-temperature sites.

**Electrode boiler.** Thermal output $\eta_\text{EB}\,p_\text{eb}(t)$.

**Thermal and battery storage.** Both are represented with charge and discharge efficiencies,
a standing loss, a maximum C-rate coupling power to energy capacity, a minimum state of charge,
and a cyclic boundary condition over the horizon. Energy capacity is the sizing variable; power
capacity follows from the C-rate.

### 2.4 Optimisation problem

Decision variables per interval $t$ (all non-negative): grid withdrawal $p_g$, heat pump and
electrode boiler electricity $p_\text{hp}, p_\text{eb}$, thermal storage charge and discharge
$q_c, q_d$ and level $s^\text{th}$, battery charge and discharge $p_c, p_d$ and level
$s^\text{el}$, unserved heat $q_u$ and unserved electricity $p_u$. Sizing variables: heat pump
thermal capacity $\dot Q_\text{HP}$, electrode boiler electrical capacity $P_\text{EB}$, storage
energy capacities $E_\text{TES}, E_\text{BES}$, billed peak $\hat P$, and connection uplift
$\Delta P$.

Heat balance, for full electrification with no residual fossil boiler:

$$\text{COP}(t)p_\text{hp}(t) + \eta_\text{EB}p_\text{eb}(t) + q_d(t) - q_c(t) + q_u(t) = \dot Q_\text{dem}(t)$$

Electricity balance:

$$p_g(t) + p_d(t) + p_u(t) = P_\text{el}(t) + p_\text{hp}(t) + p_\text{eb}(t) + p_c(t)$$

Connection constraint, the paper's central formal element:

$$p_g(t) \le P_\text{limit}(t)$$

Storage dynamics, for each medium, with $\lambda$ the standing loss and cyclic closure:

$$s_t = (1-\lambda\Delta t)s_{t-1} + \eta_c x_c(t)\Delta t - x_d(t)\Delta t/\eta_d$$

Objective — total annualised cost:

$$\min \sum_a \text{ann}_a\,\text{size}_a
+ \Delta t\sum_t p_g(t)c_\text{el}(t)
+ (1-\delta_\text{FCA})(1-\delta_\text{atyp})\,c_\text{cap}\hat P
+ \text{ann}(c_\text{reinf}\Delta P)
+ c_\text{VoLL}\Delta t\sum_t\big(q_u(t)+p_u(t)\big)$$

with $\text{ann}_a = i/(1-(1+i)^{-n_a})$ applied to each asset's capital cost plus fixed operating
cost. $\delta_\text{FCA}$ is the network-charge reduction granted in exchange for accepting the
agreement, and $\delta_\text{atyp}$ that available to an atypical network user (§2.5). Both are
inputs, not results: they are the terms a plant negotiates, and §`[X]` reports how the design
responds to them.

$c_\text{VoLL}$ is set far above every other marginal cost so that unserved energy is a last
resort rather than a cheap means of peak reduction.

### 2.5 Network charge model

The capacity charge is levied on $\hat P$, defined as the maximum withdrawal over a **billing
set** $\mathcal{B}$:

$$\hat P \ge p_g(t) \quad \forall t \in \mathcal{B}$$

For a standard consumer $\mathcal{B}$ is all intervals. Where the site qualifies as an atypical
network user under § 19 Abs. 2 S. 1 StromNEV — its annual peak falling predictably in low-load
periods — $\mathcal{B}$ is restricted to the network operator's published high-load windows, and
the charge is reduced by $\delta_\text{atyp}$ [L5].

$\mathcal{R}$ and $\mathcal{B}$ are set by different mechanisms and need not coincide. Shifting
heat production out of $\mathcal{R}$ may move it into $\mathcal{B}$. Modelling both is necessary
to see this, and to our knowledge has not been done.

A second § 19 provision cuts the other way. Under § 19 Abs. 2 S. 2 StromNEV a site using the
network *intensively* — at least 7,000 utilisation hours and 10 GWh per year — may agree an
individual network charge reduced by $\delta_\text{int}$. Electrification raises both quantities,
so a site can cross the threshold *because* of the project. This is the opposite incentive to peak
shaving: flattening the draw to reduce $\hat P$ also raises utilisation hours toward eligibility.
Because eligibility depends on the sizing outcome, it cannot enter the linear programme without a
binary; we evaluate it post hoc — utilisation hours $=$ annual withdrawal $/$ annual peak — and,
where a design qualifies, re-solve once with $\delta_\text{int}$ applied to the capacity charge.
Since the discount only weakens the incentive to peak-shave, an eligible design remains eligible,
so the second solve is a confirmation rather than an iteration.

> **Note for revision.** The German regulator has opened a procedure to replace the § 19 Abs. 2
> discounts with a special industrial network charge, taking the view that reform is unavoidable
> [L5]. The paper therefore treats $\delta_\text{atyp}$ and the definition of $\mathcal{B}$ as
> policy variables in §`[X]` rather than as fixed law.

### 2.6 Baseline and performance indicators

The baseline is the existing gas boiler supplied with certified biomethane: zero emissions under
certificate accounting, non-zero physically. Both are reported, and the certificate premium is
carried as an explicit cost so that the comparison is between two decarbonisation routes rather
than between decarbonisation and inaction.

Indicators: installed capacities; peak and billed-peak withdrawal; unserved heat as a share of
demand (the feasibility measure); binding share, the fraction of intervals in which the
connection limit is active; annualised cost and its decomposition; levelised cost of heat and CO₂
abatement cost relative to the baseline; storage cycles; realised versus average purchase price.

### 2.7 Rolling-horizon operation

Sizing assumes perfect foresight, which is standard for greenfield design and gives an upper
bound on the achievable benefit. Because the central claim concerns a *contractual* limit, that
bound must be qualified: a controller that misses the limit once does not incur a tariff, it
breaches an agreement.

Fixed designs are therefore re-operated over the full horizon with a receding-horizon controller.
At each step the controller optimises over a horizon on forecast demand and prices, commits the
first block, and the committed block is re-evaluated against realised data and the realised
limit. Restrictions are visible only within the contractual notification interval. Two
notification regimes are compared: response-time-only visibility, the pessimistic reading of the
German contract [L6], and day-ahead notification, following the Dutch product [38]. A state-of-
charge reserve is held against unannounced calls; its level is a sensitivity parameter.

Reported: unserved energy, limit violations, and the foresight gap against the perfect-foresight
result.

### 2.8 Sensitivity design

One-at-a-time variation over the parameters listed in `[Table X]`, reported as tornado charts on
storage size and total cost, plus two-way analysis on the pairs where interaction is expected:
storage cost against price spread, and restriction width against granted uplift. The latter
produces the contract-space map.

Inverse analyses by bisection: the minimum granted uplift, and the maximum restriction width, at
which a given design still supplies the full heat demand.

### 2.9 Implementation

Python, Pyomo, HiGHS. `[N]` linear programmes, `[N]` variables and `[N]` constraints for the
largest instance. Interior point with crossover disabled; a simplex fallback on non-convergence.
Sizing is performed on one design year at 15-minute resolution; the remaining years are
re-simulated with sizes fixed. Configuration, package versions and input file identity are
recorded per run. Code and input template: `[repository DOI]`.

---

## 3 · Case studies and data — SCAFFOLD

**What this section must establish, before any result appears:** that the five sites differ along
the two axes that turn out to predict everything — **load factor** and **heat-to-power ratio** —
and that this difference is a property of the production regime, not of the sites' size.

* Table 2: site characterisation. Sector, production regime, annual electricity and heat,
  $P_\text{exist}$, load factor, heat-to-power ratio, supply temperature, heat source, atypical
  eligibility.
* Fig. 1: monthly mean electricity and heat, five sites.
* Fig. 2: load duration curves. Use this to *introduce* load factor as the paper's organising
  variable rather than deriving it later.
* Data provenance, resolution, treatment of gaps and daylight saving, forecast versus measured
  years.
* Table 1: parameters and sources.
* Market data: day-ahead prices, grid emission factor — state clearly whether average or
  marginal, a reviewer will ask.

> Open the moment the data arrive: plot load factor against heat-to-power ratio for the five
> sites. If they cluster, the multi-site framing does not hold and the paper needs restructuring
> around a single site with a parameter sweep. Do this before any production run.

## 4 · Results — SCAFFOLD

**4.1 What a flexible agreement looks like.** Fig. 3, $P_\text{limit}(t)$ by regime over one
week with the site's demand behind it. This is the reader's entry point; the paper is unreadable
without it.

**4.2 The peak problem.** Electrification without storage against each regime. Establishes the
magnitude of the gap.

**4.3 Storage sizing across regimes.** Fig. 5 and Table 4 — the headline. Sentence pattern:
*"Holding technology costs constant, required thermal storage falls from `[XX]` MWh under a firm
unenlarged connection to `[XX]` MWh under a time-window agreement and `[XX]` MWh under a dynamic
agreement, a factor of `[XX]`."*

**4.4 The feasibility boundary.** Fig. 4, the configuration × regime matrix. Sentence pattern:
*"For sites with load factor above `[XX]`, no storage capacity within the modelled bounds
supplies the full heat demand under the firm regime; the shortfall is `[XX]` % of annual heat
demand."* Connect explicitly to the operators' temporary-versus-permanent congestion position
[L9].

**4.5 Operation.** Fig. 6, one winter week, restriction windows shaded. Show the storage
pre-charging ahead of a restriction. Fig. 7, withdrawal duration curves by regime.

**4.6 TES versus BES.** Where the battery earns a place and where it does not, and what has to
change for that to reverse. Be explicit that under arbitrage and peak shaving alone it does not.

**4.7 Interaction with network charges.** The § 19 result. Report the case where optimising
against $\mathcal{R}$ pushes the peak into $\mathcal{B}$.

**4.8 Contract space.** Fig. 11, restriction width against granted uplift, shaded by feasibility,
one panel per site. This is the practitioner-facing output and a candidate for the graphical
abstract.

**4.9 Foresight gap.** MPC results, both notification regimes, all sites.

**4.10 Sensitivity.** Tornado plus the two-way maps.

## 5 · Discussion — SCAFFOLD

Points the discussion has to make:

* Load factor as a screening variable a plant can compute before commissioning any study.
* Contract design as a policy instrument: what notification interval and restriction share buy in
  terms of avoided industrial storage investment. The Dutch 85/15 with day-ahead notice [38] is
  the natural comparator for the German window and dynamic forms.
* The network-charge reform [L5] and what it would do to these designs.
* Whether the flexible agreement is a bridge or a permanent arrangement, and how that changes the
  investment case given asset lifetimes.
* Transferability: which results are German and which follow from the load physics.

## 6 · Limitations

Linear assets without unit commitment; single temperature level; a detailed heat pump model is
deferred; perfect-foresight sizing with the MPC check as the correction; the operator call series
is proxied by price percentile rather than observed; storage costs linear in size; no on-site
generation; certificate-based baseline accounting whose additionality is contested; one country's
regulatory frame, with international comparison by analogy rather than by re-modelling.

## 7 · Conclusions — SCAFFOLD

Three sentences, each tied to a number: the restriction structure dominates storage sizing; the
feasibility boundary is predicted by load factor; contract design propagates into industrial
capital expenditure and is therefore a policy lever, not an administrative detail.

---

## Nomenclature

| Symbol | Meaning | Unit |
|---|---|---|
| $P_\text{exist}$ | existing firm connection = historical max of measured demand | MW |
| $P_\text{limit}(t)$ | connection limit under the agreement | MW |
| $\alpha,\beta$ | static and flexible capacity, relative to $P_\text{exist}$ | – |
| $\mathcal{R}$ | restricted intervals | – |
| $\mathcal{B}$ | billing intervals for the capacity charge | – |
| $\hat P$ | billed peak withdrawal | MW |
| $\delta_\text{FCA},\delta_\text{atyp},\delta_\text{int}$ | network charge reductions (FCA, atypical S. 1, intensive S. 2) | – |
| $c_\text{VoLL}$ | penalty on unserved energy | EUR/MWh |
| $\text{ann}_a$ | annuity factor of asset $a$ | 1/a |

## Submission checklist

- [ ] All ⚠ references opened and bibliographic data completed
- [ ] All ⛔ references replaced by primaries
- [ ] Every `PLACEHOLDER` in the parameter table replaced and sourced
- [ ] Emission factor stated as average or marginal
- [ ] Biomethane additionality addressed, not assumed away
- [ ] Load factor × heat-to-power scatter checked before production runs
- [ ] Sites anonymised as archetypes
- [ ] Code and input template deposited, DOI in §2.9
- [ ] Graphical abstract: contract-space map
