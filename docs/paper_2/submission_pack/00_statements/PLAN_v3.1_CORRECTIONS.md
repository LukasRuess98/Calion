# Paper 2 — Plan v3.1 corrections

**2026-09-02.** Supersedes the relevant parts of `00_prompts/PAPER2_ECM_PLAN_v3.md` and
`AGENT_PROMPT_Paper2_v3.md`. Triggered by an independent author review of the committed `main`
state (the session's atmospheric work was still local/uncommitted, hence not visible there).
Corrects BOTH the reviewer's v3 plan AND this session's earlier diagnosis.

## 1. ΔT is runtime-CONSTANT at 15 K across all HK stages — C2 is dead

`min_supply_delta_T_k = 15` floors the corridor ΔT, and the retrofit stages are built with
`T_VL_min − T_RL = 15 K` exactly, so the storage energy density is **identical across HK0/1/2 in
both networks** (verified):

| Net | HK0 | HK1 | HK2 |
|---|---|---|---|
| Memmingen | 15 K (floored ↑ from 10.4) | 15 K | 15 K |
| Stadtbach | 15 K (floored ↑) | 15 K | 15 K |

- Under **NORMAL charging** the density is HK-invariant (floored) — so the draft's claim "lowering
  supply inflates the volume" does NOT hold in the campaign as run.
- **BUT C2 is alive via HOT CHARGING** (author 2026-09-02, corrects the "C2 is dead" note): a
  hot-charged store uses the spread `T_VL,max − T_RL`, which DOES vary with the stage because the
  retrofit lowers T_RL. Memmingen (T_VL,max=100): HK0 36.4 K → HK1 45 K → HK2 49 K, i.e. **+35 %
  density, favourable sign**. So the honest, conditional framing: *whether HK lowering helps or
  hurts storage depends on (a) whether the retrofit lowers the return too and (b) whether the store
  is hot-charged.* This couples straight into the technology factor (below): hot charging at
  100/122 °C **requires the pressurised vessel**; atmospheric forces the low 15 K spread and thus
  large volume. The **charge-temperature ↔ vessel-technology ↔ volume triangle** is the core
  figure. Hot charging is already implemented (S3/S5/S7) — de-confound it from siting and cross it
  with the HK stage (QC-review already required this).
- Stadtbach HK2 does **not** collapse into HK1 — the per-stage `T_RL_c` is honored (HK1 65/50,
  HK2 60/45).

## 2. The 5,000 m³ cap is ASME-justified — the "raise to 50,000" instruction is WITHDRAWN

`AGENT_PROMPT_Paper2_v3.md`'s instruction to lift the cap to 50,000 m³ must NOT be executed — it
would undo the deliberate 2026-07-20 ASME/PED derivation. The real issue is a **scale mismatch**
(same absolute cap for a 40×-different load: 5,000 m³ ≈ 85 MWh = 17 h for Memmingen but only
0.4 h for Stadtbach).

## 3. Storage model — TECHNOLOGY AS AN EXPLICIT FACTOR (revises "hybrid by scale")

**Author correction 2026-09-02 (supersedes the earlier per-network hybrid):** "storage isn't
built → adjust cost until it is" reads as parameter-fitting. Instead, **storage technology is an
explicit factor of the experimental design**, and the result is *which technology is economic in
which network, and that it depends on network scale* — a genuine design finding.

Three technology levels, each with its OWN cost curve / p_max / vessel limit / charge ceiling,
**each formula applied IDENTICALLY to both networks** (fixes the review's Point 2 — one formula,
both networks; a per-network cost model confounds every cross-network claim):

| Technology | Cost | p_max | Charge ceiling | Vessel/footprint |
|---|---|---|---|---|
| Pressurised buffer | linear α·V + β | 10 bar | none (hot-charge OK) | ≤5,000 m³/vessel, multi-tank above |
| Atmospheric steel tank | degressive C0·(V/V0)^b | ~1.5 bar | ~95 °C | large single tank |
| Pit (PTES) | degressive (cheaper C0) | ~1 bar | ~90 °C | very cheap/m³, land-limited |

- Both networks run **all** technologies (a factor); the model reports which wins. Expectation:
  Memmingen suffices with a pressurised buffer; Stadtbach needs pit/atmospheric at ~800 MWh.
- **Degression, IF used, applies to both networks** (barely matters at Memmingen's small volumes) —
  it is a property of the *technology*, not the network. Resolves "different cost model per net."
- Config: `storage_geometry.yaml` moves from per-network `cost_model` to per-**technology**
  definitions + a per-network default + a factor-sweep hook. (TO IMPLEMENT.)

## 3b. Code point #2 — surface loss made class-consistent (DONE 2026-09-02)
The surface standing loss is now a **constant** `U·k(AR)·V^(2/3)·ΔT` computed the SAME way in the
fixed-V dispatch class and the endogenous investment class (per-rung constant selected by the size
binary → linear, no McCormick). So the sweep↔MILP cross-validation (T5/F3) compares like with like
— resolving the review's Point 4. (~0.1 %/h, negligible; `geometric_storage.py`.)

## 4. Adopted review points
- **F4 is not ceteris paribus.** An HK stage changes k, T_VL_min AND T_RL together. Add a
  **factor decomposition** (vary k / T_VL_min / T_RL individually, dispatch class, ~12 runs). It
  will also make the ΔT-constant point explicit (the coupled retrofit stages hold ΔT at 15 K by
  construction; breaking the coupling is what would move density). Claim "three retrofit
  programmes compared," not "heat-curve optimisation."
- **§4.4 siting text is outdated.** Post baseline-fix, endogenous wins in BOTH (MM −13.2 %,
  SB −3.2 %); SB's 3.2 % is inside the MIP gap → report as "not distinguishable," not a ranking.
- **Zenodo DOI is mandatory** (ECM Data Statement Option C) — add a CALION deposit as a required
  deliverable (was missing from the plan).

## 5. Not affected
- The running **Study G Memmingen** sweep stays valid: it measures OPEX(E), which is
  cost-model-independent; the linear vs degressive choice is applied offline in TAC = OPEX + CAPEX.
- The draft's own framing already matches the original brief (title = topology/geometry/heat-curve
  aware sizing; F4 = central figure) — less to repair than the August submission_pack docs implied.
