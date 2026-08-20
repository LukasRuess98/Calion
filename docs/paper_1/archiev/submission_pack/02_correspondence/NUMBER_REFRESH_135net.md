# Number refresh — 42-net → 135-net grid
**Checked 2026-08-12 against the new CSVs.** Every synthetic figure in the manuscript,
abstract and tables was computed on 42 networks. The grid is now complete
(3 node counts × 5 lengths × 3 heterogeneity × 3 storage = **135**, balanced).
The numbers below **must be replaced everywhere** before the rewrite.

## Synthetic decomposition — `synth_factorial_decomposition.csv` (135 rows)

| Quantity | Printed (42 nets) | Correct (135 nets) | Where it appears |
|---|---|---|---|
| Topology main effect bound | ±0.72 %, "every network" | **−0.72 % … +2.38 %** ❌ | Abstract, §4.2, §4.8, `tab_decomposition` |
| Loss share range | 99.4–100.7 % | **97.6–100.7 %** | §4.2, letter R2.2 |
| Loss share median | 100.0 % | ~100.0 % (unchanged) | Abstract, §4.2, §4.8 |
| Loss burden range | 3.4–67.4 % of cost | **3.2–81.2 %** | Abstract, §4.8, `tab_decomposition` |

### The ±0.72 % claim is now false — and the fix makes it stronger
Eight networks exceed 0.72 %. **All eight are at 1 km trunk length**, and the worst
(`synth_n15_L1p0km_hi0p4_s12h`, topo **+2.38 %**) is a network whose *entire* cost gap is
5.8 % of cost. Topology is a larger share of a much smaller pie.

Recommended wording, which is defensible and arguably better than the original:

> The topology main effect stays within ±0.72 % of the gap on every network with a trunk
> length of 5 km or more. On the 1 km networks it reaches 2.4 %, but there the entire
> copperplate-to-baseline gap is under 6 % of cost, so the absolute topology term remains
> negligible in every case.

Do **not** re-print "±0.72 % on every network" — R2 now has the full grid logic to check it.

### Two changes that help
- Burden now spans **3.2 → 81.2 %** (was 3.4–67.4). The frozen-adder non-transfer argument
  gets a wider range to work with.
- The grid is genuinely balanced, so `tab_synth_anova`'s variance decomposition is now
  legitimate — but **it must be recomputed on 135 nets**; the printed 82/11/6/1 % split is
  from the unbalanced 42.

## Frozen-adder drift — `frozen_adder_drift.csv` (135 rows, sorted ascending)

| Quantity | Printed | Correct (135 nets) |
|---|---|---|
| Most transferable adder, mean drift | 17.2 pts | **23.5 pts** |
| …its max drift | 32.3 pts | **40.1 pts** |
| Worst reference net, mean drift | 36.9 pts | **41.5 pts** |
| Largest single drift | 64.0 pts | **78.0 pts** |

The argument strengthens: even the best-case frozen adder now mis-estimates by a mean of
**23.5** percentage points of cost, not 17.2.

**Still unresolved: the abstract's "drift 17–95 %" and the letter's "17–94 %" / "53–94 %".**
No column in the file reaches 94 under any reading, old or new. Replace with the 23.5 / 40.1
figures, or supply the normalisation that produced 94.

## Fidelity design rule — `fidelity_rule_fit.csv` (new file, 136 points)

| Quantity | Printed | Correct |
|---|---|---|
| n points | 43 | **136** (135 synthetic + Memmingen) |
| Zero-parameter R² | 0.86 | **0.873** |
| Zero-parameter MAE | 4.8 pts | **6.72 pts** (RMSE 9.33) |
| Calibrated R² | 0.93 | **0.957** (MAE 4.33 pts) |
| λ range | 0.03–1.7 | 0.0328–1.7489 ✓ unchanged |
| Memmingen λ / pred / meas | 0.12 / 11 % / 15 % | 0.1212 / 10.81 / 15.12 ✓ unchanged |

Calibration constants now available for the text: slope **a = 116.0**, intercept
**c = 1.4 pts**. The R² *rose* and the MAE *rose* — both consistent with a wider λ range;
state the MAE as 6.7, not 4.8.

## Objective vs. economic cost — `objective_decomposition.csv` (new file)

This replaces the stale `economic_gaps.csv` and **corrects the response letter's R2.2
methods note, which was wrong twice.**

| Level | Gurobi objective | Economic cost | Residual | Residual % |
|---|---|---|---|---|
| CP | 195,994.34 | 115,551.16 | 80,443.18 | 41.04 |
| CP+L | 221,501.84 | 135,287.78 | 86,214.06 | 38.92 |
| CP+Lb | 221,385.97 | 135,205.67 | 86,180.30 | 38.93 |
| ND⁰ | 196,844.84 | 116,512.46 | 80,332.38 | 40.81 |
| L1 | 222,226.96 | 136,142.42 | 86,084.54 | 38.74 |

1. **The residual is not what the letter says it is.** The letter names a return-temperature
   anchor penalty, terminal storage valuation and demand slack. All three are **0.00 €**.
   The residual is CHP CO₂ self-use accounting (54.9–58.2 k€) + TES cycling (24.0–26.4 k€),
   plus an unexplained closure residual of 1.39–1.64 k€.
2. **The bias numbers were wrong.** Correct, on the current lineage:
   **CP reads −11.8 % on the Gurobi objective and −15.1 % on economic cost.**
   (Not −13.0 / −16.6 — those were the old L1-vs-L3 pair from `economic_gaps.csv`.)
   ND⁰: −11.4 % objective / −14.4 % economic. CP+L: −0.33 % / −0.63 %.
3. The "38–41 % of the objective" framing survives ✓ (38.7–41.0 %).
4. **Action:** name the 1.4–1.6 k€ closure residual or report it explicitly as "other";
   an unexplained term in a methods note inviting scrutiny is worse than a labelled one.

## R1.6 clustering — `r16_clustering_costs.csv` (new file)

| Variant | Zones | Economic cost | vs. orig |
|---|---|---|---|
| orig | 7 | 133,756.34 | — |
| alt, coarse | 4 | 132,170.80 | −1.19 % |
| alt, shifted | 7 | 134,078.87 | +0.24 % |
| alt, fine | 10 | 136,269.96 | +1.88 % |
| **null draws (20)** | 7 | **125,583 – 136,271** | spread **10,687 €** |

Reference: L1 (node-resolved) = 136,142.42.

**Reads well:** the finer the clustering, the closer to the node-resolved model
(10 zones lands within 0.1 % of L1) — a clean monotone convergence story.

**Reads badly if unaddressed:** the null spread is **7.9 % of L1**, roughly **11× the
topology main effect** (961 €). And `orig` sits in the lower tail — only 3 of 20 random
7-zone clusterings come out cheaper. A reviewer will notice that an arbitrary aggregation
choice moves cost more than the effect the paper calls negligible.

**The interpretation hinges on one thing the file does not record:** do the alternative and
null clusterings **preserve total U·L**? R1.6 asked specifically about the case where
"total annual losses are preserved."

- If yes → clustering moves cost 8 % at constant loss, which is a real tension with the
  loss-dominance framing and must be discussed, not buried.
- If no → the spread is *another loss effect*, which confirms the thesis and turns R1.6
  into a supporting result.

**This is the one number still needed from the coding agent:** total U·L (or annual loss)
per clustering variant, alongside cost. Until then the R1.6 paragraph cannot be written
honestly either way.

## Regenerate before writing

`tab_decomposition`, `tab_synth_anova`, `tab_prediction` and `tab_regret` are all
auto-generated by `tablegen_p1.py` from the 42-net inputs. Re-run it against the 135-net
CSVs rather than hand-patching the `.tex`, or the tables and the prose will drift apart.
`prediction_oos_summary.csv` still reports n_train=36 / n_test=6 — that is the old split
and needs redoing on 135.
