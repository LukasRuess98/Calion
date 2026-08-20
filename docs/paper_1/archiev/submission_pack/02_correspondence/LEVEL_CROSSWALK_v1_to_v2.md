# Level nomenclature: v1 → v2 crosswalk
**Working reference for the v1 carry-over. Read before merging any v1 prose.**

All three of `L1`, `L2`, `L3` exist in both versions and mean **different things** in each.
Any sentence pasted from v1 without remapping will be silently wrong.

## The collision

| Symbol | v1 (submitted) | v2 (revision) |
|---|---|---|
| `L1` | copperplate, single bus, no loss | **node-resolved + trunk loss** (= v1 `L3`) |
| `L2` | 7 aggregated demand zones | **node-resolved + temperature propagation** |
| `L3` | 15 junction nodes, steady-state loss | **node-resolved + trunk pressure & pumping** |

## Full mapping

| v1 level | v1 definition | v2 name | v2 code |
|---|---|---|---|
| `L1` | single bus, no spatial structure, no pipe losses | **CP** | T0P0 |
| — | *(new)* copperplate + exogenous aggregate loss | **CP+L** | T0P1 |
| `L2` | 7 demand zones, ΣU·L matched to L3 | **ZN** | T1P1 |
| `L1_topo` | full nodal routing, zero pipe losses (v1 auxiliary, synthetic only) | **ND⁰** | T2P0 |
| `L3` | 15 nodes, steady-state loss, heating curve, precomputed COP | **L1** *(baseline)* | T2P1 |
| `L3⁺` | + PWL pressure drop, linearised temp. propagation, pumping; delay bypassed | split → **L2** + **L3** | T2P2, T2P3 |
| — | *(new)* station resolution + service laterals | **L4** | T2P4 |
| — | *(new)* dynamic flow-dependent station Δp | **L5** | T2P5 |
| `L3ᴺᴸ` | native quadratic pressure, bilinear temp., delay active | split → **L6** + **NL** | T2P6, NL |

**Note for the response letter:** v1 already contained `L1_topo` — routing without losses,
i.e. today's `ND⁰` — but only as an auxiliary in the synthetic decomposition, never on the
real case. R2.2's confound objection stands for the *primary* results, and the letter should
say that rather than imply the control is wholly new. If R2 notices `L1_topo` in v1 and we
have claimed `ND⁰` as new, that is an avoidable credibility hit.

## Numbers the reviewers quote in v1 terms

Each of these must be bridged explicitly, or the reviewer cannot verify their own comment
was addressed.

| Reviewer wrote | v1 meaning | v2 restatement |
|---|---|---|
| R1.2: "13 % difference between L1 and L3" | copperplate → node-resolved | CP → L1 gap: **−11.8 % on the objective, −15.1 % on economic cost** |
| R2.2: "transition from L1 to L2" | copperplate → zones | CP → ZN; now decomposed exactly via CP+L and ND⁰ |
| R1.3 / R2.3: "L3⁺−L3ᴺᴸ … up to 0.5 %" | linearisation + delay, confounded | delay isolated as L6; solved linearisation error **−0.15 % / −0.33 %** |
| R1.6: "L2 aggregates into seven zones … matching total U·L" | zone model | ZN; conservation now enforced and tested (R1.6 experiment) |
| R2.5: "only 36 of the 81 configurations" | old synthetic grid | full **135**-cell balanced factorial (3×5×3×3) |

## Merge rule

When pulling v1 text:

1. Replace every `\Lone` → `\CP`, `\Ltwo` → `\ZN`, `\Lthree` → `\Lone`, `\Lplus` →
   `\Lthree`, `\Lnl` → `\NLref`. **Do not** rely on find-and-replace alone — v1 also
   spells levels in prose ("Level 1", "the copperplate level (L1)", "L1 copperplate").
2. Grep the merged text for the literal strings `L1`, `L2`, `L3` outside the macros and
   check each by hand.
3. Any v1 sentence stating a *number* against a level name must be re-derived from the v2
   CSVs, not carried over — the lineage changed (defensible U-values, hardened gaps,
   economic cost rather than objective).

## Sections to carry over

From `03_draft_revision/01_draft_original/20260706_Topology_Study_submitted (1).tex`:

| v1 section | line | Target `<<KEEP:>>` |
|---|---|---|
| Introduction (opening) | 186 | `intro-motivation` |
| Related work, 3 subsections | 317–508 | `rw-milp-topology`, `rw-thermohydraulic`, `rw-positioning` |
| Basic MILP formulation | 724 | `objective`, `balances`, `losses`, `hp`, `storage`, `emissions` |
| Extended physics formulation | 967 | `pressure-drop`, `temp-prop`, `delay` |
| Validation protocol | 1138 | `stage1`, `stage2` |
| Implementation | 1206 | `implementation` (update: 66 cores / 180 GB) |
| Validation results | 1449 | `validation-results` |
| Computational performance | 1812 | `computation` |
| Limitations | 2085 | `limitations-other` |
| Nomenclature | 2275 | `nomenclature` |
| Appendices (COP, linear components, PWL, Taylor, selling price, per-node MAE, HI, BCM) | 2416–2668 | `cop`, `components`, `pwl`, `taylor`, `selling-price`, `per-node-mae`, `hi`, `bcm` |
| Heating curve, L2 zone mapping | 2802, 2823 | `heating-curve`, `l2-zones` |

Highest-risk carry-overs: **Basic MILP formulation** (level names throughout) and
**Limitations** (v1's limitations partly became v2 results — the fixed heating curve is now
the T_sup study, the clustering caveat is now the R1.6 experiment).
