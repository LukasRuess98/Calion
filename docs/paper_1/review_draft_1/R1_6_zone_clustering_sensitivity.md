# R1.6 — zone-clustering sensitivity (data answer)

Reviewer R1.6 asked how sensitive the results are to the L2 zone aggregation, which in the
submitted paper is a single hand-made 7-zone partition of the 15-node L3 network.

## Method

A verified L3→L2 aggregator (`tools/r16_zone_clustering.py`; reproduces the hand-made
`Memmingen_L2.yaml` to the metre and to ΣU·L on 6/7 pipes — see data note below) was used to
generate, at identical L2 physics (heat_loss on, pressure off), full-year MILP solves for:

- the **reported** hand-made 7-zone clustering;
- **3 deliberate alternatives** spanning granularity: coarse **4 zones**, fine **10 zones**, a
  **shifted 7-zone** boundary set;
- a **null distribution** of **20 random contiguous 7-zone partitions** (random tree cuts),
  isolating the pure effect of *where* the 7 zone boundaries fall.

All 24 solved to optimality (MIPGap 1e-4). Results in `results/v2/analysis/r16_clustering_costs.csv`,
figure `results/v2/figures/F_r16_clustering.{png,pdf}`.

## Result — the clustering is not a material lever

| Clustering | zones | L2 econ cost (€/yr) | vs reported |
|---|---|---:|---:|
| **Reported (hand-made)** | 7 | 133 756 | — |
| Alt: coarse | 4 | 132 171 | **−1.19 %** |
| Alt: shifted | 7 | 134 079 | +0.24 % |
| Alt: fine | 10 | 136 270 | **+1.88 %** |
| Null (20 random 7-zone) | 7 | mean 134 398, **sd 2 906 (2.2 %)** | — |

- The reported clustering is a **typical** 7-zone partition: it sits at **z = −0.22** (15th
  percentile) of the null distribution — i.e. it was not cherry-picked to favour any result.
- Changing the aggregation **granularity** from 4 to 10 zones moves the L2 economic cost by only
  **−1.2 % to +1.9 %**.
- Across all 20 random 7-zone partitions the cost spread (sd) is **2.2 %**.

Because the L3 (node-resolved) reference is clustering-independent, this ≈2 % band is also the
sensitivity of the L2→L3 gap to the zone choice — well below the loss/topology effects the paper
reports. **The conclusions do not depend on the specific zone aggregation.**

## Drop-in response text

> We thank the reviewer. We tested sensitivity to the zone aggregation directly: holding the
> node-resolved reference fixed, we re-solved the aggregated (L2) model for three alternative
> clusterings spanning 4–10 zones and for a null distribution of 20 random contiguous 7-zone
> partitions (new Fig. R1.6 / Fig. X). The aggregated economic cost varies by only −1.2 % to
> +1.9 % across granularities and has a standard deviation of 2.2 % across random 7-zone
> partitions; the clustering used in the paper is a statistically typical partition (z = −0.22).
> The reported loss- and topology-abstraction effects are therefore robust to the choice of zone
> aggregation, which we now state in §X and document in the supplement.

## Data note (worth one line in the paper)

The L3 config's pipe **j13→j15 carries `u_value_supply = 1.31` W/m·K** (vs the 0.28 assumed when
the hand-made L2 was built). The aggregator uses the actual L3 value, so it reproduces the
hand-made L2 exactly on 6/7 aggregated pipes and differs only on zone_F→zone_G (ΣU·L 214 vs 85).
All clusterings here use the same consistent aggregation, so the comparison is unaffected — but
the 1.31 value looks like an un-insulated-lateral outlier and should be confirmed as intended.
