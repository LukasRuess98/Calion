# Reviewer comments — condensed to engineering actions

> **ALIGNED to `00_MASTER_STATUS.md` (2026-08-10).** Where the tables below say
> "Stadtbach"/"Case A/B/C" or the old 5-level scheme, read Shape A: **Memmingen +
> synthetic only**; moderator via the synthetic gen-topology factor; R2.4 answered by
> the real-component pressure study + new **L4/L5 station-hydraulics** levels;
> taxonomy = the redesigned `08_LEVEL_REDESIGN.md` ladder with **defensible trunk U**
> and laterals at L4. The reviewer→action mapping still holds; only the case/level
> labels changed.

## Reviewer 1

| ID | Substance | Action | Where answered in v2 |
|----|-----------|--------|----------------------|
| R1.1 | "Dominates" broader than demonstrated scope: radial, **central generation**, fixed heating curve, **unidirectional flow**, fixed capacities | retitle + Stadtbach removes two of the listed restrictions | Title, §1, Stadtbach case |
| R1.2 | Measures model-result sensitivity, not empirical accuracy | **regret is a decision quantity** — this dissolves the objection rather than caveating it | P11, §2.1 |
| R1.3 | L3+→L3NL confounds formulation and delay | `T2P3` | P3, P4 |
| R1.4 | Pre-upgrade validation only | **legacy Memmingen becomes the primary validated case** | Case A |
| R1.5 | Assumptions structurally limit what physics can do | concede as conditional scope | GAP:SCOPE-CEILING |
| R1.6 | L2 clustering arbitrary | 3 clusterings + null distribution | P6 |
| R1.7 | Deterministic, hourly, no reserves | limitations | §4.9 |

## Reviewer 2 — the decisive reviewer

| ID | Substance | Action | Where |
|----|-----------|--------|-------|
| R2.1 | **"Requires substantial revision before its contribution can be assessed as sufficiently significant"** — novelty | reframe: regret metric, control condition, moderator finding, validation-resolution argument, prediction | `04_NOVELTY_STATEMENT.md` |
| R2.2 | L1→L2 changes topology AND losses; asks explicitly for a copperplate with calibrated aggregate losses | `T0P1a/b/c` | P3 |
| R2.3 | Linearisation not rigorous: confounded with delay; solver gaps comparable to differences. Asks for intermediate models, **optimality-bound intervals, or a validated nonlinear reference** | all three: `T2P3`, bound reporting, and the forward evaluator | P3, P7, P11 |
| R2.4 | Hydraulic validation weak; **implausibly low pumping energy**; asks about supply/return, substations, valves, pressure requirements, pump characteristics | validate on Stadtbach measured pressure, transfer to Memmingen | P1, P12 |
| R2.5 | 36/81 retained; inconsistent taxonomy; unbalanced statistics | 81 factorial, unified T×P, ANOVA + regression | P2, P5 |

**Read R2.1 as one round from reject on novelty.** Prose reframing will not move
them. v2 adds a new metric, a new control condition, a second real network and an
out-of-sample test.

## Senior editor

Lumped references removed · abstract one paragraph · no Conclusions subheadings ·
restructure to AE house style · Highlights mandatory (3–5 bullets, ≤85 chars).

## Internal defects to fix (not raised by reviewers)

- Graphical abstract: HP at remote node (contradicts j1); "+10,5 %" vs 10.4 %;
  typo "topolpgy"
- Orphaned `Memmingen_L3_NoPhys.yaml`
- Paper η_pump 0.75 vs Memmingen config 0.70; roughness 0.5 vs 0.05 mm —
  **Stadtbach uses the paper's values, Memmingen is the outlier**
- "statistically meaningful bound" — no sampling distribution exists
- v1 Table 15: K=5 and K=8 extrapolated, labelled "not simulated"
- **BCM validation is in-sample**: calibrated on Oct–Feb, reported on Oct–Feb.
  R2 asked for out-of-sample validation and may have seen this.
- Stadtbach config header says "~6 km network"; pipes sum to ~54 km
- Manuscript number mismatch: letter APEN-D-26-15734, PDF APEN-S-26-20346

## The contradiction that likely triggered R2.4

§2.2 cites Frederiksen & Werner: pumping is **1–5 % of thermal energy cost**.
§5.3 reports **+255 EUR/yr on 2.4 MWh**; Appendix F.3 reports **<5 kW peak**.
For a 12 MW network with 3.3 km of pipe these are two orders of magnitude apart.
The paper contradicts its own literature basis. Resolve it; do not defend it.
