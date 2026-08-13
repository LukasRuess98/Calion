# Revision plan v2

> **ALIGNED to `00_MASTER_STATUS.md` (2026-08-10).** Scope = Shape A (Memmingen +
> synthetic; Stadtbach/Case C cut). Section structure below still applies but the
> **levels are the redesigned ladder** (`08_LEVEL_REDESIGN.md`: CP/CP+L/ZN/ND⁰/L1–L6/NL
> with station tiers L4/L5 and defensible-U/laterals-at-L4). Methodology §2 gains the
> station-hydraulics sub-model; Results gains a station-level decomposition row and the
> "coarse models undercount last-mile loss" finding. The whole study is **recomputed
> from scratch** on defensible-U configs. Timeline/extension unchanged.

## Strategy

The reviewers converge on two structural criticisms: several comparisons change
more than one factor at once, and the contribution reads as a structured
comparison of established models. We answer the first with a topology × physics
factorial plus two new model cells, and the second by changing what the paper
measures — from **estimation bias** (objective differences between formulations)
to **decision regret** (the cost of having decided with the simpler model,
evaluated under a common high-fidelity forward model). The reviewers' scope
objections (central generation, unidirectional flow, fixed loss/topology confound)
become **experimental factors** in a balanced synthetic factorial that varies node
count, pipe length, demand heterogeneity, storage and generation placement while
holding the taxonomy fixed — a cleaner controlled contrast than a second real
network, and one with no NDA or salami-slicing exposure (Stadtbach → Paper 2).

## Structure

Current 7 sections → 5, per AE house style:

```
1. Introduction              (absorbs Related work)
2. Methodology               2.1 factorial + reference definitions
                             2.2 base formulation · 2.3 extended physics
                             2.4 forward evaluator and regret   ← NEW
                             2.5 validation protocol · 2.6 implementation
3. Case studies              3.1 Memmingen (real) · 3.2 synthetic factorial
                             (Stadtbach + Memmingen-upgraded cut → Paper 2)
4. Results and discussion    4.1 validation (thermal + hydraulic)
                             4.2 bias decomposition
                             4.3 regret and physical feasibility   ← NEW
                             4.4 generation topology as moderator  ← NEW
                             4.5 hydraulics · 4.6 linearisation and delay
                             4.7 generalisability and out-of-sample prediction
                             4.8 sensitivity and robustness
                             4.9 computational performance
                             4.10 implications · 4.11 limitations
5. Conclusions               (no subheadings)
```

## Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `T0P1` recovers most of the bias | **High** | Title changes | Pre-committed; transferability argument prepared |
| Regret ≈ 0 everywhere | Medium | Headline changes | "Biased estimators, competent controllers" — arguably the better paper; ties to the CO2-policy section |
| Distributed-gen moderator not deliverable under Shape A (synth redesign pending, §5b) | Medium | Moderator demoted to open question | Central result proven (topo≈0, 42 nets); present distributed arm as motivated open question, not a delivered result |
| Station hydraulics push above 1 % | Low | Abstract wording | Ordering survives; restate magnitude |
| Out-of-sample prediction fails on held-out synth nets | Medium | Rules weaken | Report honestly; a failed extrapolation is informative and pre-committed |
| Reviewer reads reframing as evasion | Low | — | Response letter names every changed conclusion |
| Scope creep — new metric + full recompute, 20 days | **High** | Missed deadline | **Request extension** (below); Stadtbach cut removes ~half the work |

## Minimum viable scope if time is cut

Non-negotiable: **P1 (Memmingen pressure study), P3, P11, P4 (Memmingen +
synthetic), P7** plus editorial. Those cover R2.2, R2.3, R2.4 and R2.1. Defer:
the distributed-generation moderator arm, the parameterised-L4 OOS point.

## Timeline

Deadline 2026-08-29 — 20 days. The critical path (Memmingen pressure study →
evaluator → full recompute of Memmingen on defensible-U → synthetic factorial →
analysis → figures → rewrite) does not fit, and the reframing touches the
Introduction, contributions, Results and Conclusions.

**Request an extension to mid/late October:**

> We are grateful for the constructive reviews. Responding properly to Reviewer 2's
> comments 1 to 4 requires more than an incremental revision: we are adding a
> decision-regret evaluation, two model formulations that isolate effects the
> original design confounded, a balanced synthetic factorial, and a real-component
> hydraulic study (manufacturer pump data, DXF-reconstructed transmission stations
> and service laterals, pandapipes cross-check) that addresses the hydraulic-
> validation concern directly. We therefore request an extension until [date] to
> submit a revision that addresses the comments substantively.

(Authoritative extension text is `extension_request.md`; keep the two in sync.)

## Record (RESOLVED)

Live record in Editorial Manager is **APEN-D-26-15734** (confirmed by author 2026-08-11);
the `APEN-S-26-20346` in the old submission PDF header is a stray and is disregarded. Upload
the revision against APEN-D-26-15734 via the "Submit Revision" link in the revise-invitation
email.
