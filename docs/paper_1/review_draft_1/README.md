# APEN Revision Pack v2 — Agent Instruction Set

**Manuscript:** APEN-D-26-15734 (submission file header: APEN-S-26-20346)
**Journal:** Applied Energy — Major Revision · **Owner:** Lukas Ruess
**Repo:** `calion`

> ## ⚠ READ `00_MASTER_STATUS.md` FIRST — it is the current source of truth.
> Below is the original v2 pack; several decisions have since been finalised and the
> pack is being aligned to the master status. Key finalised points:
> - **Scope = Shape A** (Memmingen + synthetic only; Stadtbach + Case C CUT → Paper 2;
>   moderator via the synthetic gen-topology factor). See `06_SCOPE_REEVALUATION.md`.
> - **Redesigned levels** (CP/CP+L/ZN/ND⁰/L1–L6/NL, station tiers L4/L5, one phenomenon
>   per step, transmission stations at every level). See `08_LEVEL_REDESIGN.md`.
> - **Recompute the whole study from scratch** on the c19d690 worktree with
>   **defensible trunk U-values** (no ×4.7 multiplier); service-lateral losses enter at
>   L4. v1 numbers are reference only.
> - R2.4 answered by the real-component pressure study (`05_PRESSURE_AND_NOVELTY.md`) +
>   the new L4/L5 station-hydraulics levels; pandapipes = one appendix table.
> Any mention of "three cases"/"two networks"/"five levels" below is superseded.

> **v2 supersedes v1 of this pack.** v1 patched the existing study. v2 reframes it.
> The reason is Reviewer 2's novelty objection, which no amount of extra runs
> answers. Read `04_NOVELTY_STATEMENT.md` before anything else.

---

## The reframe in three sentences

v1 measured **bias**: the difference between objective values of two formulations.
v2 additionally measures **regret**: the cost of having *decided* with the simpler
model, obtained by re-simulating each model's dispatch schedule under a common
high-fidelity forward model. The five fidelity levels stop being the subject of
the paper and become instrumentation.

## Three cases, three distinct roles

| Case | Role | Validation available |
|---|---|---|
| **Memmingen legacy** (CHP + gas + biomass, no HP/EB/TES) | Validated bias decomposition | T + flow at **27 consumer nodes** → node resolution |
| **Stadtbach** (dispatch-only, existing assets) | Regret under *distributed* generation; hydraulic validation; out-of-sample rule test | T + flow + **pressure** at shafts → zone resolution |
| **Memmingen upgraded** (+HP/EB/TES) | Electrification sensitivity; bridge to paper 2 | plausibility only |

Stadtbach is what retires the scope objections: distributed generation
(6 producer nodes), bidirectional trunk, spread merit order (waste heat 10 /
biomass 20 / gas 58.6 EUR/MWh), and roughly an order of magnitude more pipe than
Memmingen — beyond the fitted synthetic range, so applying the selection rules to
it is genuine extrapolation.

---

## Read order (human)

1. `04_NOVELTY_STATEMENT.md` — what we claim is new, and what we concede is not
2. `00_CONTEXT.md` — reviewer comments as engineering actions
3. `02_STUDY_REDESIGN.md` — **core**: T×P factorial, bias/regret, three cases
4. `01_REVISION_PLAN.md` — traceability, risk, timeline
5. `03_FIGURE_SPEC.md`
6. `paper/paper_v15_skeleton.tex` — restructured draft with `%% <<GAP:...>>` markers

## Execution order (agent)

| # | Prompt | Blocks | Note (Shape A) |
|---|--------|--------|------|
| P0 | `P0_repo_audit.md` | all | done — inventory + v1 freeze (`results/v1_frozen/`) |
| ~~P12~~ | ~~`P12_stadtbach_discovery.md`~~ | — | **SHELVED (Stadtbach cut)** |
| P1 | `P1_hydraulics_validate_transfer.md` | P4, P11 | **Memmingen real-component write-up only** (pressure study); drop Stadtbach Δp transfer |
| P2 | `P2_taxonomy_refactor.md` | P4, P5 | T×P codes, bound recording — on the **c19d690 worktree** |
| P3 | `P3_new_variants.md` | P4 | `T0P1a/b/c`, `T2P3` |
| **P11** | `P11_regret_evaluator.md` | P4, P7 | forward simulator — the new metric (**critical path**) |
| P4 | `P4_run_campaign.md` | P7 | **Case A only** (Memmingen legacy); Cases B & C shelved |
| P5 | `P5_synthetic_full_factorial.md` | P7 | 81 configs + **gen-topology factor promoted** (carries the moderator) |
| P6 | `P6_robustness.md` | P7 | **3 named clusterings only**; drop the 10 random partitions |
| P7 | `P7_analysis.md` | P8, P9 | bias + regret decomposition; **OOS = synthetic held-out band** |
| P8 | `P8_figures.md` | P9 | pandapipes = 1 appendix table |
| P9 | `P9_tables_and_editorial.md` | writing | |
| P10 | `P10_release_hygiene.md` | Zenodo | Memmingen only — Stadtbach NDA moot under Shape A |

Critical path under Shape A: **P2 (worktree + taxonomy) → P3 (`T0P1`) + P11 (evaluator)
→ P4 Case A → P5 synthetic → P7 → P8/P9.** P1 is a write-up of already-done pressure work.

---

## Non-negotiables

1. **Never overwrite v1 results.** Everything new goes to `results/v2/…`.
2. **Every number in the paper comes from a CSV** via `tablegen`/`fill_paper`.
3. **Every run records `objective` AND `bound`.** The revision depends on being
   able to say "smaller than the solver can resolve."
4. **The evaluator contains no PWL.** It uses native exponentials. That is what
   makes it a defensible physics reference (Reviewer 2.3 asked for exactly this).
5. **Stadtbach enters paper 1 dispatch-only.** `investment.enabled: false` on
   `hp_sb`, `ek_sb`, `tes_sb`. Sizing is paper 2 and must not be spent here.
6. **Stadtbach raw data is NDA.** It does not go to Zenodo. Publish configs with
   anonymised/derived series only, and say so in the data-availability statement.
7. If a prompt contradicts the repo, **stop and report**; do not improvise a fix
   that changes model semantics.

## Hardware

66 cores / 180 GB. Full-year MIQCP on Memmingen (15 nodes) is now worth
attempting — if it converges, the "intractable on single-workstation hardware"
limitation and the shoulder-season gap both leave the paper.
