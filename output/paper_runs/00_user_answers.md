# User Answers — §10 of CLAUDE_CODE_TASKS.md
# Written: 2026-04-27

1. **HP capacity**: Keep 100 MW for now. User will adjust manually later.
2. **Electrode boiler**: Does NOT exist at Memmingen site. Omit from all configs. Document in paper Limitations.
3. **Validation data**: Not yet available. All runs produce `validation.json` with `status: "no_measured_data"`.
4. **Pipe roughness**: **0.5 mm** confirmed (aged steel network).
5. **CO₂ price**: **1000 €/t** as primary (already in all configs — consistent with paper).
6. **Time horizon**: **8760 h** assumed (2025-01-01 00:00 → 2025-12-31 23:00). User did not explicitly confirm.
7. **Heat curtailment**: Raise `dump_cost_eur_per_mwh_th` to **1000 €/MWh**.
8. **Temperature propagation linearization**: Framework uses **nominal-temperature MILP linearization** — Q_loss computed from fixed T_supply_nominal / T_return_nominal (fully linear). Implemented in `calion/models/blocks/pipe_pair.py` (`temperature_linearize=True` branch). Neither Taylor nor McCormick — simpler fixed-point approximation.
9. **Journal**: **Applied Energy** → author-year bibliography style (`\bibliographystyle{elsarticle-harv}`).
