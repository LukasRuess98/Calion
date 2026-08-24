# R1.6 — zone-clustering sensitivity (data answer)

> **Conserving version (2026-08-15).** All 24 clusterings conserve total ΣU·L = 1140.2 W/K (producer
> j_1 resolved as its own zone), verified per-config and via the identical realised annual loss
> (1257.8–1257.9 MWh). An earlier non-conserving pass — which dropped producer-zone internal pipes for
> clusterings that merged j_1 with downstream nodes — is superseded and reported below only as a
> modelling-hazard result.

Reviewer R1.6 asked how sensitive the results are to the L2 zone aggregation, which in the
submitted paper is a single hand-made 7-zone partition of the 15-node L3 network.

## Method

A verified L3→L2 aggregator (`tools/r16_zone_clustering.py`) was used to generate, at identical
L2 physics (heat_loss on, pressure off), full-year MILP solves for a family of clusterings that
**all conserve total ΣU·L = 1140.2 W/K** (= the L3 network, using L3's own U-values). Conservation
is enforced by keeping the **producer node j\_1 as its own zone** in every clustering — this is
also what the paper's L2 does (it resolves the plant), and it is *required* for conservation: a
clustering that merged j\_1 with downstream nodes would have no incoming pipe to carry the
producer-zone's internal trunk losses, dropping them (see "reported result" below). Because ΣU·L is
equalised, the only thing that varies across the family is **where the zone boundaries fall — a
pure routing effect.**

The family (all solved to optimality, MIPGap 1e-4):

- the **original** partition (the paper's 7-zone map) run through the same conserving aggregator
  (`L2_orig`), used as the reference;
- **3 deliberate alternatives** spanning granularity: coarse **4 zones**, fine **10 zones**, a
  **shifted 7-zone** boundary set (each with j\_1 isolated);
- a **null distribution** of **20 random partitions** (`random.Random(1234)`, n = 20). *Null-space
  restriction (stated explicitly):* since j\_1 is always its own zone, each null draw cuts the
  producer edge j1→j2 and then 5 further random tree edges, partitioning the remaining **14 consumer
  nodes into 6 zones** (7 zones total). This is the correct control — it isolates consumer-zone
  boundary choice at fixed producer resolution and fixed total loss.

Every emitted config is asserted to conserve ΣU·L; `r16_clustering_costs.csv` carries
`sum_UL_w_per_k` and `annual_loss_mwh` columns so conservation is auditable from the data, not only
asserted. Results in `results/v2/analysis/r16_clustering_costs.csv`, figure
`results/v2/figures/F_r16_clustering.{png,pdf}`.

## Result — with loss conserved, zone routing is a null effect

Every clustering delivers the **same realised annual loss** (1257.8–1257.9 MWh; ΣU·L = 1140.2 W/K
by construction), so the only thing free to move is routing. It barely does:

| Clustering | zones | L2 econ cost (€/yr) | vs orig |
|---|---|---:|---:|
| **Original partition** (`L2_orig`) | 7 | 136 262 | — |
| Alt: coarse | 4 | 136 261 | **−0.00 %** |
| Alt: shifted | 7 | 136 260 | **−0.00 %** |
| Alt: fine | 10 | 136 270 | **+0.01 %** |
| Null (20 random, producer-isolated) | 7 | mean 136 268, **sd 4 € (0.003 %)** | — |

- **Full spread across all 24 clusterings: 11 € = 0.008 % of cost.** Granularity (4→10 zones) moves
  cost by ≤0.01 %. The routing effect is, for planning purposes, zero.

### R1.6 independently corroborates the central decomposition

Because ΣU·L is equalised, this residual is a pure **routing** effect and is directly comparable to
the decomposition's own spatial term. On the CP→L1 gap (`decomposition_live.csv`):

| Effect | Cost | % of gap |
|---|---:|---:|
| Loss (visibility) | 19 737 € | 95.9 % |
| Topology main effect (resolving routing) | 961 € | 4.7 % |
| **Zone-clustering routing choice** (R1.6) | **11 €** | **<0.01 %** |

Routing choice is ~2 orders of magnitude below even the (already small) topology main effect, and
~3 below loss (figure `F_r16_clustering`, log scale). R1.6 is therefore not a side experiment: it is
independent confirmation that **loss — not geometry — carries the cost.**

### Reported result: ΣU·L conservation is a real modelling hazard

The first pass exposed a practical warning worth one sentence in the paper. A zone aggregation that
does **not** conserve total ΣU·L — e.g. one that merges the producer with downstream nodes and drops
the producer-zone's internal trunk pipes (−10 to −18 % of ΣU·L here) — shifts the reported cost by
**up to ~6 %**, whereas conserving clusterings agree to within **0.01 %**. The lesson for anyone
building reduced zone models: the aggregation must preserve ΣU·L (equivalently, the delivered loss),
which is exactly why the loss term, not the zone geometry, is what has to be got right.

## Drop-in response text

> We thank the reviewer. We tested sensitivity to the zone aggregation directly, at fixed
> node-resolved reference and fixed total ΣU·L (the producer is resolved as its own zone in every
> case): we re-solved the aggregated (L2) model for three alternative clusterings spanning 4–10
> zones and for a null distribution of 20 random producer-isolated partitions (new Fig. R1.6).
> With the delivered loss held equal, the aggregated economic cost is invariant to the clustering —
> the full spread across 24 partitions is 0.008 % of cost (null sd 0.003 %). This residual routing
> effect (≈11 €/yr) is two orders of magnitude below the topology main effect (961 €/yr, 4.7 % of
> the gap) and three below the loss main effect, so R1.6 independently corroborates the paper's
> central result that loss visibility, not network geometry, sets the fidelity requirement. We also
> note the corollary as a modelling caution: a zone aggregation that fails to conserve ΣU·L can
> shift cost by up to ~6 %, so preserving the delivered loss is the binding requirement for a valid
> reduced model. [§X, Fig. R1.6]

## Data note (worth one line in the paper)

The L3 config's pipe **j13→j15 carries `u_value_supply = 1.31` W/m·K** (vs the 0.28 assumed when
the hand-made L2 was built). The aggregator uses the actual L3 value, so it reproduces the
hand-made L2 exactly on 6/7 aggregated pipes and differs only on zone_F→zone_G (ΣU·L 214 vs 85).
All clusterings here use the same consistent aggregation, so the comparison is unaffected — but
the 1.31 value looks like an un-insulated-lateral outlier and should be confirmed as intended.

**Two-artifact reconciliation (j13→j15).** The shipped `validation_kpis.json` `calibrated_u_values`
lists **1.0** for *every* pipe including j13→j15, while the R1.6 aggregator (and this table) use the
**per-pipe design U** from `Memmingen_L3_MILP.yaml`, where j13→j15 = **1.31**. These are two different
parameterisations for two different purposes and are both correct as such: the validation calibrates a
*single uniform* U (1.0 W/m·K, one free parameter) to reproduce the measured **annual** loss to 1.2 %,
whereas the planning/decomposition model uses the network's **per-pipe design** U-values (j13→j15's 1.31
being the old uninsulated far-east lateral). They are not meant to match pipe-by-pipe. This should be
stated once in the text so the two shipped numbers for the same pipe are not read as a contradiction;
if a single value is preferred, adopt the per-pipe design U throughout and re-report the uniform-U
calibration as a sensitivity.
