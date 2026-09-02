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

- The reviewer's **C2** ("lower HK reduces usable storage density") and the review note ("density
  rises 40 %") are **both wrong**: density does not vary with HK at all.
- **C2 must be reframed/dropped.** The HK stages differ only in absolute supply temp (→ COP) and
  network losses, NOT in storage density. New C2 framing: *lower HK raises COP and cuts losses
  (win); the storage optimum is set by scale/cost, not by the heat curve.* The genuine HK
  tradeoff is COP-gain vs. hydraulics (flow), documented elsewhere.
- Stadtbach HK2 does **not** collapse into HK1 — the per-stage `T_RL_c` is honored (HK1 65/50,
  HK2 60/45).

## 2. The 5,000 m³ cap is ASME-justified — the "raise to 50,000" instruction is WITHDRAWN

`AGENT_PROMPT_Paper2_v3.md`'s instruction to lift the cap to 50,000 m³ must NOT be executed — it
would undo the deliberate 2026-07-20 ASME/PED derivation. The real issue is a **scale mismatch**
(same absolute cap for a 40×-different load: 5,000 m³ ≈ 85 MWh = 17 h for Memmingen but only
0.4 h for Stadtbach).

## 3. Storage model — HYBRID BY SCALE (decision 2026-09-02)

Technology follows scale (both give an interior optimum; implemented in
`configs/paper_2/storage_geometry.yaml`, opt-in `CALION_ATMOSPHERIC_TES=1`):

| | Memmingen (~2 MWh) | Stadtbach (~500–800 MWh) |
|---|---|---|
| Technology | pressurized **buffer** (realistic at small scale) | atmospheric **pit** (realistic at large scale; a farm of pressurised vessels is not) |
| Cost | **linear** α·V + β (ASME 1200 €/m³ + 100k/tank) | **degressive** C0·(V/V0)^b (one pit, real scale economy) |
| Cap | 10 bar / 5,000 m³ (non-binding here) | atmospheric / footprint |
| Loss | surface `V^(2/3)` | surface `V^(2/3)` |

- Resolves the review's "drop degressive": degressive is **correct for the SB pit** (economies of
  scale of one structure); per-tank β was only right if SB were pressurised vessels — it isn't.
- **WP1 scope** shrinks as the review suggested for MM (surface loss only, keep linear cost) but
  SB keeps the degressive pit curve. Surface loss is kept for BOTH (endorsed enhancement).

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
