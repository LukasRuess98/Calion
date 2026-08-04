# Sizing an electrified industrial heat supply behind a flexible connection agreement

Research framework and manuscript for a paper on how an industrial heat supply must be designed
when the grid connection is **flexible rather than firm** — i.e. when additional withdrawal
capacity is granted subject to a static or dynamic limitation under § 17 Abs. 2b EnWG.

The connection is modelled as a time series rather than a scalar:

    p_grid(t) <= P_limit(t)

built from the parameters that the statute requires the agreement to state. Heat pump, electrode
boiler, thermal storage and battery storage are sized and dispatched against it.

## Quick start

```bash
pip install -r requirements.txt
pytest -q                 # ~5 s
python run_study.py --smoke    # 1 site, 1 month, ~1 min
```

Full screening run, all sites and regimes, one year at hourly resolution:

```bash
python run_study.py --years 2024 --resolution 1h --contract-space
```

Production run (hours, not minutes):

```bash
python run_study.py --years 2023 2024 2025 --resolution 15min --mpc --sensitivity
```

Results land in `results/`, figures in `results/figures/` as HTML and SVG.

## Where to look

| | |
|---|---|
| **`CLAUDE.md`** | working brief — rules, traps, backlog. Read first. |
| **`FIGURES.md`** | every figure the paper needs, built and unbuilt |
| `data/input_data_template_v2.xlsx` | all inputs. Single source of truth. Yellow cells are yours. |
| `fcaheat/` | the package. Canonical code. |
| `notebooks/study.ipynb` | thin driver, imports the package, holds no logic |
| `docs/02_…` | regulatory basis — how each legal provision becomes a constraint |
| `docs/04_…` | literature review and the gap statement |
| `docs/05_…` | manuscript draft |
| `docs/06_…` | changelog and the current headline result |

## Status

Framework runs end to end on placeholder data. All time series in the workbook are synthetic and
must be replaced. Technology parameters are Danish Energy Agency catalogue values or marked
`PLACEHOLDER`; the two economically decisive ones — the network-charge discount granted for
accepting the agreement, and the site's actual tariff — can only come from a real operator offer.
