# P4 — Run campaign

> **ALIGNED 2026-08-10 (Shape A).** Cases = **Memmingen (real) + synthetic** only;
> Case B (Stadtbach) and Case C (Memmingen upgraded) CUT → Paper 2. Run the full
> redesigned ladder (CP/CP+L/ZN/ND⁰/L1–L6 + NL-ref) on Memmingen; controls + L1–L3 +
> parameterised L4/L5 on the synthetic factorial. All on the c19d690 worktree with
> defensible-U. Every run records objective **and** bound; feed every schedule to the
> forward evaluator (regret). NL-ref is exact-decomposition, not a solve.

**Depends on:** P1, P2, P3, P11, P12 · **Blocks:** P7
**Output:** `results/v2/…`, `revision/audit/P4_runs.md`

Hardware: 66 cores, 180 GB. Parallelise across configurations, not within solves,
except for the MIQCP runs which get the full machine.

---

## Case A — Memmingen legacy (validated bias)

Assets: CHP 0.2 MW, gas boiler, biomass boiler. **HP, EB, TES capacity = 0.**
This is the configuration the measurement record actually covers.

Full year, 8760 h, MIP gap 0.5 %:
`T0P0`, `T0P1a`, `T0P1b`, `T0P1c`, `T1P0`, `T1P1`, `T2P0`, `T2P1`, `T2P2`

MIQCP windows (Jan 744 h, Feb 672 h; February first — it converged tighter in v1):
`T2P2`, `T2P3`, `T2P4`

**Attempt full-year `T2P4`** with the full machine and a 24 h limit. If it
converges, the "intractable on single-workstation hardware" limitation and the
shoulder-season gap both leave the paper. Also retry the **May window** that
failed in v1 — with `Δp_crit` added, pump power no longer vanishes at low flow,
so the near-zero-flow degeneracy may be reduced.

Also: PWL sensitivity `T2P2` at `K = 3, 5, 8`. v1 extrapolated K=5 and K=8 and
labelled them "not simulated"; a reviewer can see that. They are MILPs — run them.

Expect **low dispatch freedom** here (near-fixed merit order, no storage).
Regret will likely be ≈0 for structural reasons. Report it and say why; do not
present a trivial zero as a finding.

## Case B — Stadtbach (regret, hydraulics, extrapolation)

**Dispatch-only.** Set `investment.enabled: false` for `hp_sb`, `ek_sb`, `tes_sb`
and fix their capacity to 0. Existing assets only: HKW, GT-Ost, BMHKW, AVA feed,
HWS, HWW, P2H. Sizing belongs to paper 2 and must not appear here.

Full year: `T0P0`, `T0P1b`, `T0P1c`, `T1P0`, `T1P1`, `T2P0`, `T2P1`, `T2P2`

`T1` for Stadtbach = aggregation to the **shaft/zone resolution** identified in
P12, not an arbitrary clustering. This is deliberate: it makes `T1` the level at
which the network can actually be validated, which is an argument in the paper.

MIQCP: windows only. Report as a scope limit.

**This is where routing has degrees of freedom.** Six producer nodes across three
arms, a bidirectional trunk (`hkw_to_ost`), and a merit order spanning 10–58.6
EUR/MWh. Report `topo_main` here against Memmingen's ≈0 — that contrast is the
moderator result.

Watch: the config carries `Cuts=2`, `MIPFocus=2`, `Heuristics=0.1` to fix a weak
LP bound. Keep them; the comments document a stuck-at-12 %-gap case fixed by them.

## Case C — Memmingen upgraded (electrification)

The v1 configuration with HP, EB, TES enabled. Full year:
`T0P0`, `T0P1b`, `T1P1`, `T2P1`, `T2P2`

One question only: does electrification change the fidelity requirement? Compare
the decomposition and regret against Case A. Do not extend beyond this — it is one
section and the bridge to paper 2.

## Sensitivity scenarios

The 11 v1 scenarios, on Case A and Case C: `T0P0`, `T0P1b_frozen`, `T1P1`,
`T2P1`, `T2P2`. `T0P1b_frozen` uses the **baseline** calibration unchanged — that
is what produces the transferability evidence. For cold/warm year, state why
`T0P0`–`T2P1` is or is not comparable rather than printing a dash as v1 did.

## Regret evaluation

Run `tools/evaluator.py` on **every** schedule from every run above. Cheap.

---

## Requirements

- Identical solver version, seed and thread count within any comparison set;
  assert from manifests before aggregating.
- Every run records `objective` **and** `bound`.
- Cross-feasibility check: is the `T2P2` incumbent feasible in `T2P3`'s
  constraint set? If so it bounds `T2P3` from above.
- Never write into `results/v1_frozen/`.

## Report

`revision/audit/P4_runs.md`: run table (objective, bound, gap, status, wall time,
memory) · non-convergences with diagnosis · comparison table from
`tools/compare_levels.py` · **explicitly flag any result contradicting an
expectation in `02_STUDY_REDESIGN.md`**, in particular whether `T0P1` recovers
most of the bias and whether `topo_main` differs between Memmingen and Stadtbach.
