# P3 — New model cells

> **ALIGNED 2026-08-10.** DONE so far: `T0P1a/b` (copperplate+aggregate-loss via demand
> pre-inflation, `tools/make_t0p1_data.py`) and `T2P0` (U=0 pipes — the `heat_loss:false`
> flag does NOT disable losses; verified). NEW cells still to build for the redesigned
> ladder: **L2** (temperature propagation isolated, before pressure), **L4** (station
> resolution + service-lateral losses, flat Δp — port pressure-study `thermal_node`
> lateral PWL + `n_transfer_stations` into the worktree, gated byte-identical on L1–L3),
> **L5** (dynamic flow-dependent station Δp), **L6** (transport delay isolated). NL =
> exact-decomposition reference, not solved. `T0P1c` blocked on measured plant
> generation (`DATA_REQUESTS.md`). Use **defensible trunk U** on L1–L3.

**Depends on:** P1, P2 · **Blocks:** P4
**Output:** `T0P1a/b/c`, `T1P0`, `T2P3` configs and code, unit tests

## Part A — `T0P1`: copperplate with aggregate losses (R2.2)

`T0P0` with an exogenous loss term added to demand. Stays LP — no new constraint
classes. Prefer a `network.lumped_loss` YAML block over Pyomo changes so a
reviewer can verify it by reading the config.

Three calibration sources:

- **`T0P1a`** constant: `L_const = E_loss_annual(T2P1)/8760`
- **`T0P1b`** heating-curve-consistent:
  `L(t) = Σ_p U_p L_p (T_sup^nom(t) + T_ret^nom(t) − 2 T_gr(t)) / 1e6`
- **`T0P1c`** **measurement-calibrated**: annual heat generated minus annual heat
  delivered, from the monitoring record

`T0P1c` exists because a and b are calibrated against the reference model's own
answer; a hostile reviewer calls that an oracle rather than a calibration.
`T0P1c` is what a practitioner actually has. Report all three.

**Pre-registered protocol:** fit once on the baseline of each case, then freeze.
Apply the frozen adder unchanged to all scenarios, both networks, all synthetic
configs. Any refit is a separate, labelled variant.

Diagnostic:
`drift = (cost(T0P1_frozen) − cost(T2P1)) / cost(T2P1)` per scenario and per
synthetic pipe-length class.

Tests: `T0P1b` annual loss energy matches `T2P1` within 0.1 %;
`cost(T0P0) ≤ cost(T0P1)`; **variable count of `T0P1` equals `T0P0`** — it must
not quietly become a network model.

## Part B — `T2P3`: intermediate MIQCP (R1.3, R2.3)

`T2P4` with `transport_delay: false` (`k_p = 0` ∀p). Everything else
byte-identical: quadratic pressure drop, bilinear `T·φ`, the shared PWL for φ,
seed, `NonConvex=2`, time limit, threads.

```
T2P3 − T2P2 = linearisation, isolated
T2P4 − T2P3 = transport delay, isolated
```

Warm-start chain `T2P2 → T2P3 → T2P4`; record the source in each manifest.

Tests: config diff shows **only** the delay flag differs; `T2P3` with quadratics
off reproduces `T2P1` within 0.01 %; both `objective` and `bound` written.

## Part C — `T1P0`

Zone topology, zero losses. Completes the grid so the aggregation effect can be
separated at both physics levels. Config-only.

## Report

`revision/audit/P3_variants.md`: config diffs, test results, the **frozen
calibration constants** for each `T0P1` variant with the exact fitting procedure,
and confirmation that `T2P3`/`T2P4` differ only in the delay flag.
