# Response letter — section pointers and substantive corrections
Everything here must survive; `02_correspondence/` is regenerated.

---

## 1. Final section numbering

Under the four-section structure (see `ASSEMBLY.md`):

| § | Section |
|---|---|
| 1 | Introduction — 1.1 Literature review and research gap · 1.2 Contributions and research questions |
| 2 | Experimental design and methodology — 2.1 Experimental design · 2.2 Base formulation · 2.3 Copperplate with aggregate losses · 2.4 Forward evaluator and decision regret · **2.5 Cost accounting** · 2.6 Extended thermo-hydraulic formulation · 2.7 Validation protocol · 2.8 Computational setup · 2.9 Case studies and data |
| 3 | Results and discussion — 3.1 Validation · 3.2 Estimation bias · 3.3 Decision regret · **3.4 Zone-aggregation sensitivity** · 3.5 Generation-topology moderator · 3.6 Thermo-hydraulic effect · 3.7 Supply-temperature flexibility · 3.8 Linearisation and transport delay · 3.9 Generalisability and out-of-sample prediction · 3.10 Sensitivity and robustness · **3.11 Fidelity versus computational cost** · **3.12 Why the extended physics moves so little** · 3.13 Implications · 3.14 Limitations |
| 4 | Conclusions |

## 2. Pointer map — old → new

| Item | Currently cites | Should cite |
|---|---|---|
| R2.1 novelty | §1.2, §2.4, §4.3, §4.4, §4.7 | §1.2, §2.4, §3.3, §3.9 |
| R2.2 confound | §2.3, §4.2 | §2.3, §3.2 |
| R2.2 methods note | §2.6, §4.2 | **§2.5**, §3.2 |
| R2.3 linearisation | §2.4, §4.6 | §2.6, **§3.8** |
| R2.4 validation | §2.5, §4.1, §4.5 | **§2.6**, §3.1, **§3.6** |
| R2.5 generality | §3.2, §4.7 | **§2.9**, **§3.9** |
| R1.1 scope | Title, §1, §3.2, §4 limitations | Title, §1, §2.9, **§3.14** |
| R1.2 accuracy | §2.1 | §2.1 (unchanged) |
| R1.3 confounded | §2.1, §2.4, §4.6 | §2.1, §2.6, **§3.8** |
| R1.4 pre-upgrade | §2.5, §4 limitations | **§2.9**, **§3.14** |
| R1.5 assumptions | §4 | **§3.12**, §3.14 |
| R1.6 clustering | §4.4 | **§3.4** |
| R1.7 determinism | — | **§3.14** |

Every `[... Table ..., Figure ...]` tag still needs final numbers from the compiled PDF.

## 3. Substantive corrections already applied — reapply if the letter is regenerated

**R2.2 topology bound.** "topology within ±2.4 % on every single network" →
> topology within ±0.6 % on every network of 5 km trunk length or more, and never above
> 2.4 % even on the 1 km networks, whose entire cost gap is below 6 % of cost

**R2.2 drift.** Remove the unverified "short→long pipe transfer under-provisions the true
loss by 13–95 %". Verified wording:
> the loss burden spans 3.2–81.2 % of cost, so no single adder can track it; even the most
> transferable choice mis-estimates by a mean of 23.5 pts and up to 40.1 pts

**R2.2 methods note.** The three terms originally blamed for the 39–41 % residual — return-
temperature anchor, terminal storage valuation, demand slack — are **structurally zero**.
The residual is gross-vs-net CHP carbon accounting plus storage cycling. Add the bias pair:
> the copperplate's estimation bias reads −11.8 % on the Gurobi objective and −15.1 % on the
> economic cost — the same finding, diluted by a constant

**R2.5 filtering.** "All 81 synthetic configurations are now solved" was wrong twice: the
count is 135 and the redesigned grid is 3×5×3×3, not 81. Replace with the complete-balanced-
factorial wording plus the ANOVA shares (length 95.9 %, storage 3.2 %).

**R1.6 clustering.** The `spread […]` placeholder is replaced by the full data answer — 24
solves, ΣU·L conserved at 1140.2 W/K, 11 € spread (0.008 %), against a 961 € topology term
and a 19 737 € loss term; plus the non-conserving ~6 % hazard as a reported result.

**Disclosed proactively.** The claim to have *simulated* the K=5 and K=8 piecewise settings
is unsupported and was removed. What replaced it, and is the stronger disclosure: the
temperature-propagation level is degenerate when solved (supply temperature floored for
~91 % of hours), its solved objective produced a spurious cost reduction about six times the
forward-evaluated effect, and it has been withdrawn from the reported results.

**Also disclose** (drafted, in the letter): the supply-temperature validation is now
reported at the far end over the full annual record rather than as a six-node winter mean,
and the earlier selection was *not* favourable — the all-node mean lies between the
validation- and calibration-node group means.

## 4. One addition still to make

R2.4's response promises "we split the spatial validation into fitted and held-out node
sets". `validation_spatial.py` has since established that a multi-node held-out validation
is not supportable on this metering — which is exactly the argument §3.1 makes. Leaving the
promise unamended is worse than amending it. Suggested replacement:

> On further examination we found that a held-out node split cannot be constructed on this
> network for the same reason the temperature gates cannot be met: with consumer sensors
> downstream of mixing valves, no node provides a junction-temperature reference against
> which a held-out prediction could be scored. Rather than report a split we cannot defend,
> we added a first-difference comparison, which is immune to a fixed valve offset and tests
> whether the model reproduces the network's variation: flow level r = 0.91 and day-to-day
> change r = 0.80, demand 0.93 and 0.89. The held-out evidence in the paper is therefore the
> synthetic out-of-sample test, reported including its degradation beyond the fitted range.

## 5. Level nomenclature bridge — add near the top

The reviewers hold v1 and will read this letter with v1's level names in front of them.
**All three of `L1`, `L2`, `L3` mean different things in the two versions.** Add a short
table before the point-by-point responses:

| v1 | v1 meaning | v2 |
|---|---|---|
| L1 | copperplate, no loss | **CP** |
| L2 | 7 aggregated zones | **ZN** |
| L1_topo | routing, no loss (synthetic auxiliary) | **ND⁰** |
| L3 | 15 nodes + trunk loss | **L1** (baseline) |
| L3⁺ | + pressure, temperature, delay bundled | split into **L2**, **L3** |
| L3ᴺᴸ | native nonlinear, delay active | split into **L6**, **NL** |

And restate the quoted figures: R1.2's "13 % between L1 and L3" is the CP→L1 gap, now
−11.8 % on the objective and −15.1 % on economic cost.

**Note honestly** that v1 already contained `L1_topo` — routing without losses, today's
`ND⁰` — as a synthetic-only auxiliary. R2.2's objection stands for the *primary* results,
and saying so is better than having R2 find it.
