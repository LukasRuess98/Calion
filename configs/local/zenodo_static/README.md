# CALION central-TES study — model code, synthetic example and aggregated results

Supplementary code and data for

> L. Ruess, A. Sauer. *Central thermal energy storage at an industrial prosumer site: value, hydraulic limits and
> foresight in a meshed district heating network.* Energy (Elsevier), 2026. DOI: `10.1016/j.energy.2026.XXXXXX`
> (placeholder — replace on publication)

Version 1.0.0. Licence: CC BY 4.0 (see `LICENSE`). Funding: this work was funded by the German Federal Ministry for Economic Affairs and Energy (BMWE) on the basis of a decision by the German Bundestag within the project eProNet (grant no. 03EN6057B).

## What the model does

An hourly mixed-integer linear dispatch model (Pyomo + HiGHS) of an existing district heating network (DHN-A) with a
central pressurised thermal energy storage (TES) at site S, partner A (industrial waste heat lifted by a heat pump) and
partner B (10 MW electrode boiler), coupled to a calibrated hydraulic equivalent network of the meshed grid:

* **Mode E** — energy dispatch with temperature-layer TES, followed by a hydraulic check of every hour;
* **Mode H** — Mode E plus iteratively added linearised hydraulic cuts until the pump curves and pressure limits hold;
* value attribution by Shapley values over the 2³ asset combinations (factorial F[A][B][TES]);
* rolling horizon (72 h window, 24 h commitment, day-ahead price information, demand forecast noise) vs. perfect foresight;
* south hosting capacity (additional demand without new capacity, unserved heat as penalised slack);
* structurally independent cross-check of the hydraulic states with pandapipes.

Plant labels in the paper vs. code: GCHP = `KWK` / `gas_CHP` (main plant, pressure holder), WI = `MVA` /
`waste_incineration`, GT = `GT` / `gas_turbine`, BCHP = `BIO` / `biomass_CHP`, GB = `HW1` / `boiler_plant_1`;
HW2 = west transfer, PS1/PS2 = pump stations, V01–V24 = stations, S = TES site. Scenario codes: `F[A][B][T]-[E|H]`,
e.g. `F111-H` = partner A + partner B + TES, Mode H.

## Contents

| folder | content |
|---|---|
| `scripts/dhn_study/central_tes/` | study code: inputs, COP, MILP, hydraulic coupling, metrics/Shapley, rolling horizon, sensitivities, hosting study, economics, pandapipes validation, tables, figures, synthetic data generator |
| `scripts/dhn_study/` | shared modules: water properties and data loading (`daten`), mass flows (`hydraulik`), equivalent network and calibration (`netzmodell`), pandapipes model (`gegenrechnung_pandapipes`), calibration I/O (`run_netzmodell`, trimmed) |
| `scripts/dhn_study/kalibrierung/` | calibrated edge resistances K of the equivalent network, variants A (reference), B, C |
| `configs/central_tes/` | `base.yaml` = configuration of the paper; `synthetic.yaml` = the same on the synthetic data |
| `data/synthetic/` | SYNTHETIC example input (Jan–Feb 2025, generated, not measured) |
| `docs/` | `input_data_schema.md` (columns, units, resolution), `model_and_deviations.md` (model description and documented deviations) |
| `results/central_tes/` | aggregated results behind all tables and figures (annual values, summaries, Shapley, sensitivity summaries, hosting summary, foresight decomposition, pandapipes deviation statistics) |
| `results/paper_tables.md` | all paper and supplement tables, generated from these results |
| `figures/` | final figure PDFs |
| `tests/` | unit and integration tests (run on the synthetic example) |

**Not included (non-disclosure agreements):** the measured operating data of the network 2025, the operator's plant and
network plan data, partner A's waste-heat data and all hourly time series derived from them (demand, temperatures,
dispatch, pressures, flows, waste heat). Consequently the paper's numbers cannot be recomputed from this package; the
aggregated results are provided instead. In the equivalent network, node and edge ids are anonymised, pipe lengths and
diameters are placeholders (DN 300, 1 000 m), and the load-group weights and station offsets of the calibration are
replaced by neutral values; the calibrated resistances K are the ones used in the paper. Plant pump data are generic
example values in the synthetic data set.

## Installation

Python 3.11–3.13 (tested: 3.13), HiGHS via `highspy` 1.15 (no commercial solver needed).

```bash
python -m venv .venv && source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt                            # pinned versions as tested
python -m pytest -q tests/                                 # 18 tests on the synthetic example, ≈ 5 s
```

`pandapipes` is only needed for the cross-check (`validate_pandapipes`); `openpyxl` only for the original partner-A
spreadsheet reader. The figures use Latin Modern Roman if a TeX installation provides it (converted once to a local
font cache), otherwise matplotlib's Computer Modern.

## Run the synthetic example end to end

All modules read the configuration from `CENTRAL_TES_CONFIG` (default `configs/central_tes/base.yaml`).

```bash
export CENTRAL_TES_CONFIG=configs/central_tes/synthetic.yaml       # Windows: set CENTRAL_TES_CONFIG=...
python -m scripts.dhn_study.central_tes.synthetic_data              # (re)generate data/synthetic (shipped already)
python -m scripts.dhn_study.central_tes.run --factorial             # 8 scenarios, Mode E + H, Shapley   (≈ 1 min)
python -m scripts.dhn_study.central_tes.run --rh                    # rolling horizon F111               (≈ 1.5 min)
python -m scripts.dhn_study.central_tes.validate_pandapipes         # pandapipes cross-check             (≈ 20 s)
python -m scripts.dhn_study.central_tes.hosting --only F000 F001_S --shares 0.2   # south hosting, two variants
python -m scripts.dhn_study.central_tes.run --sensitivity A2 --only DN300         # one sensitivity case
```

Results go to `results/synthetic/`. They have **no meaning** for the network of the paper. `--full` in
`synthetic_data` generates the whole year 2025 (≈ 9 MB); then the runtimes below apply.

## Reproducing the tables and figures (with the full data set)

With the measured data set in `data/dhn_a/` (same schema as `data/synthetic/`), partner-A data in
`paths.partner_a_csv` and `CENTRAL_TES_CONFIG` unset (base configuration):

| paper item | command(s) | result file(s) |
|---|---|---|
| Table 2, factorial (T2) / Shapley (T3), Fig. 2 | `run --factorial`, then `consolidate` | `scenario_runs/factorial_summary.csv`, `scenario_runs/shapley.json`, `scenario_comparison.csv` |
| Foresight (T4), Fig. 2 c | `run --rh`, `run --rh-factorial`, `run --rh-tes` | `rolling_horizon/shapley_rh.json`, `rolling_horizon/tes_values_rh.csv` |
| Foresight decomposition (T4b) | `run --rh-foresight` | `rolling_horizon/foresight/foresight_rh.csv` |
| TES size × power, break-even (T5), Fig. 8 | `run --sensitivity A1`, `run --rh-tes`, `economics` | `sensitivities/A1/summary.csv`, `economics_tes_sizes.csv`, `economics_break_even.csv` |
| Sensitivities (T6): A2, A3, A4, A5, A6, P, PR, PG, BL, B2, B4, PS, AT | `run --sensitivity <ID>` (AT under RH: `run --rh-at`; RH robustness: `run --rh-robust`) | `sensitivities/<ID>/summary.csv`, `rolling_horizon/at_values_rh.csv`, `rolling_horizon/robustness_rh.csv` |
| A3e energy-only bound | `run --scenario F001-E --set tes.model=single tes.T_set_strategy=fixed tes.temperature_masks=false --out results/central_tes/sensitivities/A3e/single_energy_only` (same for `F111-E`) | `sensitivities/A3e/…` (summary in `paper_tables.md`) |
| South hosting capacity (T7), Fig. 6 | `hosting` (all variants; `--only`, `--shares` for subsets), then `hosting --collect` | `hosting/summary.csv` |
| New capacity, supplementary (T7b) | `run --sensitivity X`, `X4`, `XR` | `sensitivities/X*/summary.csv`, `expansion_*.csv` |
| Fig. 3 (operation week), Fig. 5 (pressure footprint) | from the factorial runs | hourly files (not published) |
| Fig. 7 / validation statistics | `validate_pandapipes` | `pandapipes/pandapipes_summary.csv`; published here as aggregated `pandapipes_deviation_by_node.csv`, `pandapipes_deviation_binned.csv` |
| Fig. 4 (prosumers) | sensitivities PR, A4, A5, BL, B2, PG and `run --rh-factorial` | see above |
| all tables / all figures | `paper_tables`, `paper_figures` | `reports/central_tes/paper_tables.md`, `results/central_tes/paper_figures/` |

All commands are `python -m scripts.dhn_study.central_tes.<module> …`. `paper_tables` and `paper_figures` need the
complete results tree including the (unpublished) hourly files. Fig. 1 (system concept) is a drawing.

## Runtime and memory (full year, 8 759 h; 2 threads, 7 GB RAM)

* one scenario in Mode E: 3–60 s (≈ 52 000 binaries; MIP gap 0.1 %); full factorial (8 × Mode E, Mode H on calibrations A/B/C): ≈ 30 min;
* Mode H: one iteration ≈ 2 min; 0–3 iterations at today's load, up to 20 iterations (≈ 40 min) for a TES at the south end;
* rolling horizon: ≈ 2–3 min per scenario and forecast mode (365 windows);
* memory: two full-year Mode-H runs in parallel exceeded 7 GB; run Mode-H jobs one at a time on small machines.

## Using your own data

1. Put your data in a folder with the files and columns of `docs/input_data_schema.md` and point `paths.data_dir`,
   `paths.prices_dir`, `paths.partner_a_csv` and `paths.grid_co2_csv` to them (copy `configs/central_tes/synthetic.yaml`
   as a template: `extends: base.yaml` plus the paths).
2. Adapt the plants, prices and partner parameters in the configuration (`plants`, `heat_pump`, `electrode_boiler`, `tes`,
   `economics`, `hydraulics`).
3. Network: enter your topology and geometry in `scripts/dhn_study/netzmodell.py` and provide a calibration in
   `scripts/dhn_study/kalibrierung/<variant>/` (from `netzmodell.kalibriere` with measured pressures, or from the pipe data
   via `netzmodell.k_prior`).

## Citation

See `CITATION.cff`. Please cite the paper and this record.
