# Central TES study (DHN-A, site S)

Energy-layer MILP (HiGHS) with a temperature-class TES + hydraulic evaluation on the calibrated meshed Ersatznetz +
Mode E/H coupling, factorial and Shapley attribution, sensitivities, rolling horizon, south expansion, pandapipes
cross-check, break-even economics, paper figures and tables. Documentation: `docs/dhn_storage_study/central_tes/`;
results and paper material: `reports/central_tes/` (start with `paper_readiness.md`).

```
pip install -e ".[study]" pyomo highspy          # HiGHS is the solver of this study
python -m scripts.dhn_study.central_tes.run --factorial          # 8 scenarios, E + H for calibrations A, C, B (≈ 45 min, 2 cores)
python -m scripts.dhn_study.central_tes.run --sensitivity <set>  # A1–A6, B2, B4, PR, PS, PG, AT, P, X, X4, XR (see sensitivity.py)
python -m scripts.dhn_study.central_tes.run --rh --rh-factorial --rh-tes --rh-at --rh-robust   # rolling horizon (≈ 2 h)
python -m scripts.dhn_study.central_tes.run --rh-foresight      # foresight decomposition: window, forecasts, end value (≈ 4 h)
python -m scripts.dhn_study.central_tes.validate_pandapipes      # cross-check of the hydraulic states
python -m scripts.dhn_study.central_tes.economics                # break-even investment
python -m scripts.dhn_study.central_tes.hosting                  # south hosting capacity without new capacity (TES at S vs south)
python -m scripts.dhn_study.central_tes.expansion                # summaries of X / X4 (supplementary: new boiler)
python -m scripts.dhn_study.central_tes.consolidate              # results/central_tes/scenario_comparison.csv
python -m scripts.dhn_study.central_tes.paper_fig_system         # paper figure 0 (system concept)
python -m scripts.dhn_study.central_tes.paper_figures            # paper figures 1–7 (PDF, 600 dpi PNG/TIFF)
python -m scripts.dhn_study.central_tes.paper_tables             # reports/central_tes/paper_tables.md
python -m pytest -o addopts="" tests/test_central_tes.py
python -m scripts.dhn_study.central_tes.name_scan <files to commit>   # real-name scan (needs the local term lists)
```

Partner-A waste heat and the grid CO2 factor are read from local, gitignored files configured in
`configs/local/central_tes_local.yaml`; without them partner A has zero availability. All results go to
`results/central_tes/` (gitignored, contains partner-derived time series). `figures.py` and set A2x are early draft /
exploratory tools and not part of the reported results.

Memory: one full-year MILP with Mode H needs ≈ 3.5 GB RAM; run heavy jobs sequentially on small machines.
