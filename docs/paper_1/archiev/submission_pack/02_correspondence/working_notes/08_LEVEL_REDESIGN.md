# Level redesign — proposed Table 2 (for discussion, 2026-08-10)

Redesigns the v1 five-level scope table into a clean, confound-free ladder that
(a) keeps the loss-vs-topology decomposition controls (R2.2), (b) isolates ONE
phenomenon per step (R1.3/R2.3), (c) carries the **transmission-station count at
every level, just more aggregated** (R2.5 consistent taxonomy), and (d) adds the
pressure-study station physics as new fidelity tiers (L4).

## Two axes

- **Spatial resolution S** = how finely the demand side is resolved:
  `S0` single point (copperplate) · `S1` zones · `S2` network nodes (15 for MM) ·
  `S3` individual transmission stations (174 for MM, laterals resolved).
- **Physics P** = what is modelled on top:
  `P0` none · `P1` pipe losses · `P2` trunk pressure/pumping · `P3` station
  hydraulics · `P4` nonlinear+delay.

The 174 stations exist at every level; only their **aggregation** changes with S.

## Proposed levels

**Block A — decomposition controls** (isolate loss from topology; no hydraulics):
`T0P0` copperplate no-loss · `T0P1` copperplate + aggregate loss · `T1P1` zones+loss ·
`T2P0` nodes no-loss · `T2P1` nodes+loss (**comparison baseline**).

**Block B — fidelity ladder** (each column adds ONE phenomenon, on the T2 network):
`T2P1` → `T2P2` (+trunk Δp/pumping) → `T2P3` (+station resolution: laterals + flat
station Δp) → `T2P4` (+dynamic flow-dependent station Δp + station pumping) → `T2P5`
(+nonlinear temp-propagation & transport delay).

## Redesigned Table 2 (phenomenon × level)

Legend: – none · A aggregated · ✓ present · PWL piecewise-linear · Quad/Bil native.

| Phenomenon | T0P0 | T0P1 | T1P1 | T2P0 | T2P1 | T2P2 | T2P3 | T2P4 | T2P5 |
|---|---|---|---|---|---|---|---|---|---|
| **Spatial** | | | | | | | | | |
| Demand aggregation points | 1 | 1 | zones | nodes | nodes | nodes | stations | stations | nodes |
| Transmission-station count | A(all) | A(all) | A(zone) | A(node) | A(node) | A(node) | ✓resolved | ✓resolved | A(node) |
| **Thermal** | | | | | | | | | |
| Pipe/trunk losses (U·L·ΔT) | – | ✓(exog) | ✓ | – | ✓ | ✓ | ✓ | ✓ | ✓ |
| Service-lateral losses (last-mile) | – | – | – | – | – | – | ✓ | ✓ | ✓ |
| Temperature propagation | – | – | – | – | – | PWL | PWL | PWL | Bil |
| Time-varying COP | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Storage losses & η | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| **Hydraulic** | | | | | | | | | |
| Trunk pressure drop (DW) | – | – | – | – | – | PWL | PWL | PWL | Quad |
| Trunk pumping power | – | – | – | – | – | ✓ | ✓ | ✓ | ✓ |
| Station Δp requirement | – | – | – | – | – | flat0.6 | flat0.6 | **dynamic** | dynamic |
| Station/lateral pumping power | – | – | – | – | – | – | ✓ | ✓ | ✓ |
| **Temporal** | | | | | | | | | |
| Transport delay | – | – | – | – | – | – | – | – | ✓ |
| Hourly grid e-factors | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

Out of scope (all levels): sub-hourly transients; capacity **sizing → Paper 2**;
T_sup optimisation; ring/bidirectional flow.

## What each step isolates (the contrast table)

| contrast | isolates | answers |
|---|---|---|
| T0P0→T0P1 | loss visibility (no topology) | R2.2 |
| T0P0→T2P0 | spatial topology (no loss) | R2.2 |
| T2P1 vs T0P1+T2P0 | loss × topology interaction | R2.2 |
| T2P1→T2P2 | trunk pressure/pumping | R2.4 |
| T2P2→T2P3 | **station resolution + laterals (flat Δp)** | **R2.4 / novelty** |
| T2P3→T2P4 | **dynamic (flow-dependent) station Δp** | **novelty** |
| T2P4→T2P5 | nonlinear temp-prop + delay | R1.3/R2.3 |

Every arrow changes exactly one thing → no confounds.

## FINALISED DESIGN (2026-08-10, all 5 decisions locked)

Decisions: (1) split station tier; (2) each step isolates ONE phenomenon
experimentally; (3) delay = own runnable level, nonlinear = exact-decomposition
reference (not a solve); (4) real-data L4/L5 on Memmingen (validated, answers R2.4)
+ parameterised L4/L5 on synthetic (out-of-sample generalisation); (5) reader-friendly
L-names + T×P codes.

### Table 2 — model scope across the fidelity ladder (primary case)

Legend: – none · A aggregated · ✓ · PWL piecewise-linear · Bil/Quad native nonlinear.
Each column adds exactly ONE phenomenon vs the one to its left.

| Phenomenon | **L1**·T2P1 | **L2**·T2P2 | **L3**·T2P3 | **L4**·T2P4 | **L5**·T2P5 | **L6**·T2P6 | **NL-ref**† |
|---|---|---|---|---|---|---|---|
| *Spatial* | | | | | | | |
| Demand aggregation | nodes | nodes | nodes | stations | stations | stations | stations |
| Station representation | A(node) | A(node) | A(node) | resolved | resolved | resolved | resolved |
| *Thermal* | | | | | | | |
| Pipe/trunk losses (U·L·ΔT) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Service-lateral losses | – | – | – | ✓ | ✓ | ✓ | ✓ |
| Temperature propagation | – | PWL | PWL | PWL | PWL | PWL | Bil |
| Time-varying COP | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Storage losses & η | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| *Hydraulic* | | | | | | | |
| Trunk pressure drop (DW) | – | – | PWL | PWL | PWL | PWL | Quad |
| Trunk pumping power | – | – | ✓ | ✓ | ✓ | ✓ | ✓ |
| Station Δp requirement | – | – | flat | flat | **dynamic** | dynamic | dynamic |
| Station & lateral pumping | – | – | – | ✓ | ✓ | ✓ | ✓ |
| *Temporal* | | | | | | | |
| Transport delay | – | – | – | – | – | **✓** | ✓ |
| Hourly grid e-factors | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

† **NL-ref** is not a solved level (global bilinear+quadratic is intractable — 24 h,
no incumbent). It is the *nonlinear reference*: PWL-vs-native error evaluated by exact
decomposition + the forward evaluator (P11). Answers R2.3's "validated nonlinear
reference" and isolates linearisation from delay.

**What each arrow isolates** (one phenomenon each — no confounds):
L1→L2 temperature propagation · L2→L3 trunk pressure+pumping · L3→L4 station
resolution + service laterals · L4→L5 **dynamic (flow-dependent) station Δp** ·
L5→L6 transport delay · L6→NL linearisation error.

### Companion table — decomposition controls (additive identity, R2.2)

| Phenomenon | **CP**·T0P0 | **CP+L**·T0P1 | **ZN**·T1P1 | **ND⁰**·T2P0 | (**L1**·T2P1) |
|---|---|---|---|---|---|
| Demand aggregation | 1 point | 1 point | zones | nodes | nodes |
| Station representation | A(all 174) | A(all 174) | A(zone) | A(node) | A(node) |
| Pipe losses | – | ✓ (exogenous) | ✓ | – | ✓ |
| (all hydraulic/temporal) | – | – | – | – | – |

Identity: `cost(L1) − cost(CP) = [CP→CP+L loss] + [CP→ND⁰ topology] + interaction`.
Verified on Memmingen to the cent: loss 96%, topology 4%.

### Names ↔ codes ↔ one-line meaning

| Name | Code | Meaning |
|---|---|---|
| CP | T0P0 | copperplate, no loss (174 stations lumped at 1 point) |
| CP+L | T0P1 | copperplate + aggregate loss (loss-visibility control) |
| ZN | T1P1 | zone-aggregated + loss |
| ND⁰ | T2P0 | full nodes, no loss (topology control) |
| **L1** | T2P1 | full nodes + pipe loss — **comparison baseline** |
| **L2** | T2P2 | + temperature propagation (PWL) |
| **L3** | T2P3 | + trunk pressure drop & pumping |
| **L4** | T2P4 | + station resolution + service laterals (flat Δp) |
| **L5** | T2P5 | + dynamic flow-dependent station Δp & pumping |
| **L6** | T2P6 | + transport delay |
| NL-ref | — | nonlinear reference (exact decomposition, not solved) |

### Compute plan

Full ladder L1–L6 (+controls, +NL-ref) on **Memmingen** (primary case). On the
**synthetic factorial**: the decomposition controls + L1–L3 across all 42 nets
(generalise loss-vs-topology), and **parameterised L4/L5** as the out-of-sample
station-hydraulics sensitivity (stations ∝ node demand; laterals via pressure-study
bootstrap). L6/NL-ref stay Memmingen-only (state as scope).

## UNIFIED Table 2 (controls + ladder in one table, 2026-08-10)

Columns left→right. The first four are **decomposition controls** (a topology×loss
2×2 factorial — losses toggle by design; that is the point, not an inconsistency).
The rest is the monotonic **fidelity ladder** (each adds one phenomenon).

Legend: – none · A aggregated · ✓ · PWL · Bil/Quad native · exo exogenous.

| Phenomenon | CP T0P0 | CP+L T0P1 | ZN T1P1 | ND⁰ T2P0 | **L1** T2P1 | **L2** T2P2 | **L3** T2P3 | **L4** T2P4 | **L5** T2P5 | **L6** T2P6 | NL† |
|---|---|---|---|---|---|---|---|---|---|---|---|
| *Spatial* | | | | | | | | | | | |
| Demand aggregation | 1pt | 1pt | zones | nodes | nodes | nodes | nodes | stations | stations | stations | stations |
| Station representation | A(174) | A(174) | A(zone) | A(node) | A(node) | A(node) | A(node) | resolved | resolved | resolved | resolved |
| *Thermal* | | | | | | | | | | | |
| Trunk losses (U·L·ΔT), **defensible U** | – | exo | ✓ | – | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Service-lateral (last-mile) losses | – | – | – | – | – | – | – | **✓** | ✓ | ✓ | ✓ |
| Temperature propagation | – | – | – | – | – | **PWL** | PWL | PWL | PWL | PWL | Bil |
| Time-varying COP | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Storage losses & η | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| *Hydraulic* | | | | | | | | | | | |
| Trunk pressure drop (DW) | – | – | – | – | – | – | **PWL** | PWL | PWL | PWL | Quad |
| Trunk pumping power | – | – | – | – | – | – | ✓ | ✓ | ✓ | ✓ | ✓ |
| Station Δp requirement | – | – | – | – | – | – | flat | flat | **dynamic** | dynamic | dynamic |
| Station & lateral pumping | – | – | – | – | – | – | – | ✓ | ✓ | ✓ | ✓ |
| *Temporal* | | | | | | | | | | | |
| Transport delay | – | – | – | – | – | – | – | – | – | **✓** | ✓ |
| Hourly grid e-factors | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

† NL = nonlinear reference (exact decomposition + forward evaluator; not solved).

## Critical review: does the loss placement make sense? — ONE important change

**Issue found (the key "add losses earlier/later" question).** In v1 the trunk-loss
U-values were calibrated UP (terminal pipes ×4.7 — the multiplier R2.4 criticised) so
that the 15-node trunk loss *alone* matched the measured total. But the redesign adds
**explicit service-lateral (last-mile) losses at L4**. If L1–L3 keep the inflated
trunk loss AND L4 adds laterals, the last-mile loss is **double-counted**.

**Resolution (now baked into the table above):** L1–L3 use **defensible trunk
U-values** (no ×4.7 inflation), so they *honestly undercount* the real total loss —
they physically cannot see the last mile at node resolution. The missing lateral loss
then appears as genuinely **new** at L4, where stations are resolved. Total loss
(trunk-defensible + lateral) ≈ measured only at L4.

This is not just a fix — it is a *result*: **coarser models undercount real network
loss precisely because they cannot resolve the last mile; the indefensible multiplier
in v1 was the symptom.** It simultaneously (a) removes the ×4.7 multiplier R2.4
attacked, (b) makes the ladder monotone in "fraction of real loss captured", and
(c) gives L4 a concrete, physical job. Consequence: L1–L3 loss magnitude drops vs v1,
and the current Memmingen decomposition must be **recomputed on defensible-U configs**
(the 96%/4% split may shift; loss_main likely stays dominant, but restate).

**Two minor couplings, acceptable (noted, not fixed):**
1. L1→L2 (temperature propagation) slightly changes the loss too, because endogenous
   T changes the ΔT that drives U·L·ΔT. It is still "one phenomenon" (temperature
   *representation*), but say so: L1 = loss at prescribed uniform T; L2 = loss at
   spatially-propagated T.
2. COP is "on" at every level, but its input supply temperature only becomes
   spatially-resolved at L2 — footnote it.

**Everything else checks out:** thermal→hydraulic→temporal ordering is clean; the
flat→dynamic station-Δp split (L4→L5) isolates flow-dependence; delay isolated at L6;
nonlinear as a reference. No other phenomenon is mis-placed.

## Superseded open decisions (now resolved above)

1. **Split vs merge the station tier.** Above splits it: T2P3 = station resolution +
   laterals + *flat* station Δp; T2P4 = *dynamic* station Δp + station pumping. Merge
   into one L4 if two levels is too many — but splitting is what isolates "does
   flow-dependent station pressure matter."
2. **T2P5 (nonlinear) scope.** v1's L3NL bundled temp-prop-bilinear + DW-quad + delay.
   The full re-solve is intractable (exact decomposition stands). Keep T2P5 as the
   exact-decomposition reference, or split delay into its own column (T2P4b)?
3. **Station count on synthetic nets.** Real 174 only exists for Memmingen. On synth,
   parameterise stations ∝ node demand (pressure-study method). Keep L4 real-only, or
   run a parameterised L4 across the factorial too?
4. **T2P5 temperature propagation at T2P2–T2P4.** v1 had temp-propagation only appear
   at L3+/L3NL. Table above shows PWL from T2P2. Confirm: does the trunk-loss model at
   T2P1 already carry enough T-drop, or does temp-propagation (PWL) belong only at
   T2P2+? (Affects whether T2P1→T2P2 is "pressure only" or "pressure + temp-prop".)
5. **Naming.** Keep T{i}P{j} codes (unambiguous, R2.5-friendly) or map to reader-
   friendly L0..L5 in the prose with a translation table?
