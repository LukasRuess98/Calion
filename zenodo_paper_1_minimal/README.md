# Code and Configuration Package (minimal)
## "Loss Visibility versus Spatial Detail in industrial District-Heating Dispatch Optimisation"

**Journal:** Applied Energy (APEN-D-26-15734R1)
**Zenodo:** https://doi.org/10.5281/zenodo.21219368

This is a **minimal, code-and-configuration-only** release. It contains the `calion`
optimisation framework (Pyomo/Gurobi) and the YAML configurations for the Memmingen
primary case and the 135-network synthetic factorial, together with the scripts and
tools that drive them. It is intended for inspection of the model and the exact
experimental configurations.

## Contents

```
calion/            Optimisation framework (Pyomo/Gurobi): models, io, economics,
                   run, analysis, validation, utils
configs/memmingen/ Primary-case configurations (L1, L2, L3-MILP, L3-NLP, native)
synth_configs/     Synthetic-network configurations (the 3x5x3x3 = 135 factorial,
                   each with its copperplate/node-resolved variants)
data/synthetic_site/  Synthetic input time series (demand, prices, weather) - NDA-safe
scripts/paper/     Scripts that drive the paper pipeline and synthetic study
tools/             Figure and table generators
requirements.txt   Python dependencies
pyproject.toml     Package metadata
LICENSE            MIT
CITATION.cff       Citation metadata
```

## Not included (by design)

- **Raw operational data** for the primary (Memmingen) case (non-disclosure agreement).
- **Pre-computed results** — regenerable from the code and configurations here; the
  full deposit also ships them.
- **Manuscript text, figures, and tables.**

The complete data-and-code archive (with anonymised results sufficient to reproduce
every figure and table) is the versioned deposit at the Zenodo DOI above.

## Requirements

- Python 3.10+
- Gurobi 10.0+ with a valid license (NonConvex=2 for the nonlinear reference)
- `pip install -r requirements.txt`

## Running

The Memmingen case and the synthetic factorial are driven from `scripts/paper/`
using the configurations in `configs/` and `synth_configs/`. The **135-network
synthetic study is runnable end-to-end** with the included input time series in
`data/synthetic_site/`. The primary (Memmingen) case additionally requires its raw
operational input, which is not shared (non-disclosure agreement).
