# Prompt for the local coding agent — central TES paper on network DHN-A

You continue a project that was prepared in a cloud session. Your job in this session is **Phase 0 (audit +
decisions) up to gate G0**, then stop and report. Later phases follow only after explicit approval.

**Precedence of instructions** (highest first):
1. this prompt;
2. `docs/dhn_storage_study/Paper_central_TES_plan.md` in the repository;
3. the specification `energy_tes_prosumer_coding_agent_v2.md` (local file, written with real names).

The specification keeps its gates (G0–G6), the STOP-after-each-gate rule, the gate-report template, the MUST/MUST NOT
list and the stop criteria, except where this prompt overrides them.

---

## 1. Read first

* `docs/dhn_storage_study/Paper_central_TES_plan.md` — decisions, screening results, deviations, blockers, phase plan.
* `docs/dhn_storage_study/Netzmodell.md` — calibrated meshed network (Sections 2–5), calibration variants (3.1),
  pandapipes cross-check (4.7).
* `docs/dhn_storage_study/Datenanalyse_Auslegung.md` — control points (5.6), Ost coupling (6), levers (7), tracer (8).
* `data/dhn_a/plants.yaml` and `data/dhn_a/README.md` — plants, pumps, elevations, pressures, data set.
* Code: `scripts/dhn_study/netzmodell.py`, `run_netzmodell.py`, `screening_einspeisung_s.py`, `hydraulik.py`,
  `gegenrechnung_pandapipes.py`.
* CALION blocks you will extend: `calion/models/blocks/heat_pump.py`, `p2h.py`, `geometric_storage.py`,
  `calion/run/rh_engine.py`, `calion/forecasting/`.

---

## 2. Confidentiality — hard rules

1. **The paper and everything pushed to the repository are anonymised.** Use only:
   * network: DHN-A;
   * plants by type (KWK, MVA, GT, Bio-KWK, HW1, HW2, PS1, PS2);
   * consumers V01–V24;
   * site S;
   * partners: "partner A" and "partner B".
2. **Never write a real name into a pushed file:** code, config, comment, test, doc, figure, commit message or file
   name. This covers the network, the operator, the city, both industrial partners, plant and street names. Section 3
   lists them.
3. Real names may appear only in local, gitignored files. Add the gitignore entries before creating such files:
   `configs/local/`, `data/local/`, `reports/local/`.
4. **Never push:**
   * this prompt;
   * the specification file;
   * the name mapping `data/raw_dhn_a/`;
   * the operator plan PDFs;
   * the raw measurement files;
   * the energy-model input file of the real network;
   * partner A's waste-heat data.
5. **Do not reference the existing named energy configuration in pushed files** (Section 3). Copy the values you need
   into a new anonymised config.
6. **Before every commit:** scan the staged files for the real-name terms from Section 3 and from
   `data/raw_dhn_a/anonymisierung/zuordnung_verbraucher.csv`. Abort on any hit.
7. **Git history:** older commits and `main` still contain real names. Do not rewrite history; do not merge `main` into
   the paper branch without asking.

---

## 3. Name mapping (LOCAL ONLY — never copy into the repository)

| Specification / real name | Anonymised |
|---|---|
| Stadtbach network, operator SWA, city | DHN-A, "the operator" |
| MAN (engine-test waste heat, ≈ 40 °C; also consumer V22) | **partner A**, consumer V22 at **site S** |
| UPM (10 MW spare electrode-boiler capacity) | **partner B** |
| HKW (gas CHP, pressure holder) | KWK |
| AVA (waste incineration) | MVA |
| GT-Ost | GT |
| BMHKW | Bio-KWK |
| HWS / PSS (south) | HW1 / PS1 |
| HWW / PSW (west, secondary network via heat exchangers) | HW2 / PS2 |
| `configs/paper_2/Stadtbach_topo.yaml` | "the existing energy configuration" (named file, do not reference) |
| `data/Stadtbach/…` input file (price, grid CO₂, `WRG…` waste-heat columns) | local input; the `WRG…` columns are partner B's waste heat → **out of scope** |

---

## 4. Decisions that override the specification

| Topic | Decision |
|---|---|
| Hydraulic layer | The **calibrated meshed Ersatznetz** (`scripts/dhn_study/netzmodell.py`: 25 nodes, 31 edges, 7 meshes) with calibration variants A (reference), C and B. **Not** the tree in the existing energy configuration. Production runs use our vectorised solver; pandapipes is the cross-check (≤ 0.016 bar shown). |
| Site of the central feed-in | Node `S` (consumer V22 = partner A), on transport line L5, 1.25 km from the KWK busbar (L1a + L5a). TES, HP and partner B's boiler connect there. Partner A's own heat demand (V22, measured flow) stays a load at S. |
| Heat pump | **One HP, 5 MW thermal** (flag as assumption). Source: **only partner A's waste heat**. Partner B's waste heat is out of scope. No manufacturer map → Carnot-fraction COP per specification; take η_C, ΔT_app and COP_max from cited literature for large DH heat pumps. Flag the lift-limit hours. |
| Partner B | Electrode boiler, 10 MW available (constant, flagged), heat-purchase price c = (λ_DA + c_el,var)/η + π per specification. |
| Partner B electricity-cost components | Still open → build a **defensible low/high pair** for c_el,var from published German 2025 tariff components (grid-fee level, KWKG, offshore, §19 StromNEV, electricity tax, concession fee, possible reductions), with sources. Demand-charge switch `none`/`full` per specification. |
| Connection pipe | **Same DN as the network trunk at S.** The repo sources disagree: the Ersatznetz start value is DN 400 for L5a/L5b (only a calibration start value); the existing energy configuration has DN 600 for the east trunk. Determine the DN from the operator plans (local PDFs, east trunk L5 near S), document it, flag it. A2 sweeps ±1–2 DN classes. |
| TES reference size | A **typical literature value for comparable networks** (pressurised hot-water tank, ≈ 120 °C, network peak ≈ 250 MW, annual demand of the order of the 2025 data). Cite sources, e.g. Danish Energy Agency technology data for heat storage, AGFW/IEA-DHC reports, published case studies. Express it as volume, energy at the reference ΔT and τ = E/Q_max. A1 sweeps around it. Design pressure and standing losses also from literature (flagged); tank pressure never enters the MILP. |
| Pump curves (limits) | **Literature-based generic centrifugal-pump curves** (head rising towards zero flow, cited shut-off/nominal ratio), anchored at the nominal points in `data/dhn_a/plants.yaml`. Check each against the 2025 maximum Δp per plant (MVA 9.0, GT 8.2, Bio-KWK 7.8 bar). If F000 violates a curve, report it (G2 rule); do not adjust silently. The 7.5-bar experience values of the east plants and the 4.0 bar of the KWK are **soft limits**: report them, they do not trigger infeasibility. |
| Other limits | V06 ≥ 1.2 bar (sweep 1.0–1.4 in B4); Mitte (V03, V10, V12, V23, V24) ≥ 1.0 bar; KWK ≤ pump; minimum static pressure per area and supply temperature (`min_static_pressure_bar`, saturation check), PN25 — all from `plants.yaml`. |
| Δp master in summer | **Determine from the 2025 measurements.** The KWK flow is < 10 kg/s in 99 % of summer hours and 21 % of heating-period hours. Repeat the regulation-signature analysis (`hydraulik.regelpunkt_signatur`, Datenanalyse 5.6) restricted to hours without KWK flow: which plant's Δp follows a station set point, which plant varies? Define the summer control concept and the re-dispatch rule for Mode H from it. |
| Re-dispatch in Mode H | Not "master takes residual" in hours without KWK operation. Use the MILP merit order (`proportional_to_milp_split` or a seasonal rule derived from the item above); document it. |
| Prices | **2025 day-ahead, bidding zone DE-LU (SDAC)**; 15-min MTU from 1 Oct 2025 averaged to hourly means, as in the specification. Check whether the price column in the local input file is exactly this; otherwise fetch from ENTSO-E Transparency or SMARD and document. Time zone Europe/Berlin, DST handled. B2 uses 2023 and 2024. |
| Plant data | `data/dhn_a/plants.yaml` (operator plan A) first. Differences to the existing energy configuration (e.g. HW1 40 vs 32 MW; MVA 40/43.6 vs 45 MW; GT 31 vs 35 MW; the 9.9 MW electric boiler at the KWK that `plants.yaml` does not list) go into the G0 report as questions. |
| West network | As in the calibrated model: the measured heat-exchanger import of the west network is an exogenous sink at node HW2 (2025 operation); HW2 boilers are outside the MILP. Flag it. |
| Loss model | Reuse the formulation validated in Paper 1. Paper 1 used a **different network**: reuse the method, not its network data. |
| Paper 2 | Paper 2 (TES sizing) includes this network under its real name. Do not copy its network-specific numbers into anonymised text; any citation is the authors' decision. |

---

## 5. Results already available (build on them, do not redo)

* Calibration (`Netzmodell.md`): Holdout RMSE 0.13–0.25 bar. Three equally good optima (A/C/B) that differ mainly in the
  link edges into Mitte-L4 and in the L1a/L1b split → always show hydraulic results for all three.
* Control concept in winter: the KWK is the only pressure holder and regulates on V06 (≈ 1.2 bar). The east plants are
  mass-flow controlled (validated); PS1/PS2 are boosters.
* Ost coupling: Δp_MVA − Δp_KWK = c + d·(ṁ_Ost/100)² − f·(ṁ_KWK/100)². Measured f = 0.215, model 0.175: the model
  under-estimates the coupling by ≈ 20 %. State this wherever the effect matters.
* Screening at S (`python -m scripts.dhn_study.screening_einspeisung_s`, plan §2):
  * +20 MW at S relieves the KWK by 0.16–0.19 bar but raises the Δp of the east plants by ≈ 0.4 bar.
  * MVA hours > 9.0 bar go from 0 to 35.
  * TES charging from the network at S (−20 MW) raises the required KWK Δp by up to 0.6 bar.
  * Flow reverses on L1a, M12 and L3; the counts are strongly calibration-dependent.
  * → RQ2/H3/H4 are testable at 2025 load. The binding elements are plant Δp limits, not pipes.

---

## 6. Tasks in this session (Phase 0 → G0, then STOP)

1. **Environment.**
   * Install: `pip install -e ".[study]" gurobipy pandapipes`.
   * Confirm the Gurobi licence.
   * Run `python -m pytest -o addopts="" tests/test_dhn_study.py` (expect 34 passed with pandapipes installed).
   * Run `python -m scripts.dhn_study.run_netzmodell --ohne-kalibrierung` (must reproduce the published numbers).
   * Do not fix the four unrelated test files that fail at collection on `main`.
2. **Data audit** → `docs/dhn_storage_study/paper_tes/data_requirements.md` (anonymised). For each input: source, year,
   resolution, units, time zone, coverage, NaNs, DST. Inputs:
   * demand / boundary conditions 2025;
   * supply and return temperature (report the measured supply mean ≈ 99 °C against the heating curve up to 120 °C);
   * prices;
   * grid CO₂;
   * partner A waste heat — interface only until the author provides the file. It is read from a local path in
     `configs/local/paths.yaml`. If it is missing at G0: BLOCKER.
3. **Summer control concept** from the measurements (Section 4) → short note with numbers and one figure.
4. **Literature values with citations:**
   * TES reference size, design pressure, standing losses;
   * pump-curve shape;
   * HP Carnot fraction, approach temperatures, COP_max, single-stage lift limit;
   * partner B c_el,var low/high.

   Use one YAML block per value: `value`, `unit`, `source`, `assumption: true`, one-line justification.
5. **Connection-pipe DN** from the operator plans (local PDFs) → anonymised statement "trunk at S: DN …" plus the
   resulting ṁ_max and κ_link.
6. **Repo audit and implementation plan** → `docs/dhn_storage_study/paper_tes/repo_audit.md` and
   `implementation_plan.md`. Plan the file-level changes:
   * Generic extensions in `calion/`, no names: HP cascade and mode exclusivity, waste-heat cap over all modes, TES
     strategies and masks, contract price, Q_central with link capacity.
   * The study driver in `scripts/paper_tes/`.
   * The anonymised config in `configs/dhn_a_tes/`.
   * One CLI: `python -m scripts.paper_tes.run --config configs/dhn_a_tes/base.yaml --scenario F111-H`, plus
     `--factorial` and `--sensitivity A1`.
   * The MILP→hydraulics node mapping onto the Ersatznetz.
7. **Blockers** → `docs/dhn_storage_study/paper_tes/blockers.md` in the specification's format. Expected: partner A data
   (B1), partner B cost components (B3, sensitivity substitute), and anything new you find.
8. **G0 report** → `docs/dhn_storage_study/paper_tes/reports/gate_G0.md` in the specification's template. Include the
   list of deviations from the specification that still need approval (plan §3) and numbered questions. Commit and push
   the anonymised files, then **STOP and wait**.

---

## 7. Later phases (only after approval, each ends at its gate)

| Phase | Content |
|---|---|
| P1 | MILP extensions + unit tests 1–9 of the specification; F000-E reproduction |
| P2 | Hydraulic baseline F000 on the Ersatznetz: absolute pressure from pressure holding + elevations, saturation margin, pump power, limit check (G2 stop rule) |
| P3 | Factorial Mode E + post-hoc validation (G3) |
| P4 | Mode H for all calibration variants, ΔC_hyd, Shapley E vs H (G4) |
| P5 | Rolling horizon for F111 and sensitivities A1–A6 (G5) |
| P6 | Consolidation and draft figures (G6) |

Every run writes to `results/scenario_runs/{code}/` per specification.

**Solver:**
* Gurobi with deterministic settings: fixed `Threads`, `Seed`, documented `MIPGap`.
* Store status, objective, bound, gap and runtime per run.
* The MILP has fixed sizes (no investment binaries) and no pressure constraints. Binaries only for TES direction, HP
  modes and documented minimum loads.

---

## 8. Git and reporting

* Work on a new branch from `claude/dreamy-turing-jjcno2`, e.g. `paper/central-tes`. No pull request unless asked.
* Small commits with clear messages. Run the name scan (Section 2.6), `ruff check` and the tests before each push.
* Gate reports: short, numbers in tables, one sentence per finding, assumptions listed with their config keys.
* When unsure about a value: flag it and ask in the gate report. Never invent operator, partner or tank data.
