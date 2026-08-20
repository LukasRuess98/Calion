# Scope re-evaluation — fit the revision in ONE paper

Written 2026-08-09, after the author flagged the pack is too big and questioned
pandapipes. This revisits the earlier "full second case (Stadtbach)" decision.

## Diagnosis

The pack as written is ~2 papers: two real networks + new metric/evaluator + two new
model cells + 648-run factorial + robustness sweeps + OOS prediction + full restructure.
The largest single scope driver — **Stadtbach as a full second real network** — is also
the only piece carrying NDA and Paper-1/Paper-2 overlap risk. The reviewers did **not**
ask for a second real network.

## Recommended shape: Memmingen + synthetic only ("Shape A")

Every binding reviewer request is answerable without Stadtbach:

- **R2.1 novelty** — regret evaluator + T0P1 control + validated hydraulics-below-threshold.
- **R2.2 topology/loss confound** — T0P1 copperplate + exact decomposition.
- **R2.3 linearisation confound** — exact decomposition (already done; full re-solve intractable).
- **R2.4 hydraulic validation** — Memmingen real-component pressure study (Wilo 110.8 kW
  vs ~3 kW need) + pandapipes cross-check. Stadtbach measured Δp was a bonus, not required.
- **R2.5 synthetic** — full 81 factorial, consistent T×P taxonomy, ANOVA + regression.
- **R1.1 moderator (central vs distributed gen)** — the **synthetic gen-topology factor**,
  which is *cleaner* than a two-real-network contrast (no multi-factor confound).
- **R1.2 accuracy terminology** — regret.
- **R1.6 clustering** — 3 named clusterings on Memmingen.

### Keep / reduce / cut

**KEEP (core):**
1. Forward evaluator + regret + physical-deliverability violations. (novelty #1)
2. `T0P1` copperplate-with-aggregate-losses + exact decomposition identity. (R2.2)
3. Exact linearisation decomposition — already done. (R2.3)
4. Memmingen hydraulic validation write-up from the pressure study. (R2.4)
5. Synthetic full 81 factorial + unified T×P taxonomy + ANOVA/regression. (R2.5)
6. Synthetic central-vs-distributed generation factor — carries the moderator. (R1.1)
7. Out-of-sample prediction **within** the synthetic factorial (hold out the
   longest-pipe-length band = genuine extrapolation). (novelty #5)
8. Editorial: retitle, 7→5 sections, one-paragraph abstract, de-lump citations,
   no Conclusions subheadings, highlights. (senior editor)

**REDUCE:**
- pandapipes → one appendix table cross-checking the evaluator's hydraulics on a few
  hours. Not a comparison axis. (Already built — near-free.)
- Robustness clustering → 3 named clusterings; drop the 10 random partitions (or keep
  as a single spread bar, not a distribution).

**CUT (defer to Paper 2):**
- **Stadtbach full second case** (P12 discovery, Δp validation, distributed-generation
  regret, real-network OOS). Removes ~half the work + all NDA/overlap risk. Stadtbach
  is Paper 2's case study — putting it centrally in both invites a salami-slicing flag.
- **Memmingen upgraded / electrification (Case C)** — it is explicitly the bridge to
  Paper 2; it belongs there.

## What the paper loses by cutting Stadtbach — and why it's acceptable

- A *real-network* out-of-sample test → replaced by synthetic held-out extrapolation.
- Measured operational pressure → not needed; R2.4 is met by real-component + pandapipes.
- The two-real-network moderator visual → replaced by the controlled synthetic factor,
  which is a stronger causal design.

Net: strictly fewer confounds, half the runtime, no NDA problem, cleaner Paper-1/Paper-2
separation, and full reviewer coverage retained.

## Consequence for the pack files

- `P12` (Stadtbach discovery), Stadtbach parts of `P1`, `P4` Case B & C → **shelved**
  (move to a Paper-2 backlog note, don't delete).
- `P5` gen-topology factor → **promoted** to carry the moderator (was optional §5).
- `P7` OOS → refit to synthetic holdout.
- `04_NOVELTY_STATEMENT.md` §3–4 → moderator and validation-resolution arguments
  restated for one real network + synthetic (see `05_PRESSURE_AND_NOVELTY.md`).
- Timeline shrinks materially; the extension request may be shortened accordingly.

## Fallback ("Shape B")

If a reviewer specifically wanted a second real network (they did not), Stadtbach can be
added in a *second* revision round or held for Paper 2. Do not pre-spend it now.
