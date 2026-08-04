"""Manuscript-ready exports: CSV, LaTeX and a reproducibility record."""
from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd
import pyomo.environ as pyo

from .config import CFG, DATA_XLSX, ECON, OUT_DIR
from .data import Inputs


def export_tables(kpi: pd.DataFrame):
    t2 = kpi[kpi["scenario"] == "S0_BASE"][
        ["site", "P_grid_exist_MW", "E_grid_MWh", "E_heat_MWh",
         "CO2_phys_t", "CO2_cert_t"]].round(1)
    t3 = kpi[["site", "scenario", "fca", "Qhp_MW", "Peb_MW", "Etes_MWh", "Ebes_MWh",
              "peak_grid_MW", "billed_peak_MW", "unserved_share_pct",
              "LCOH_EUR_MWh", "abatement_EUR_t"]].round(2)
    t4 = kpi[kpi["scenario"] == "S4_TES_BES"].pivot_table(
        index="site", columns="fca", values="Etes_MWh").round(1)
    for name, t in [("table2_sites", t2), ("table3_results", t3),
                    ("table4_tes_by_regime", t4)]:
        t.to_csv(OUT_DIR / f"{name}.csv", index=(name == "table4_tes_by_regime"))
        with open(OUT_DIR / f"{name}.tex", "w") as f:
            f.write(t.to_latex(index=(name == "table4_tes_by_regime"), escape=False))
    return t2, t3, t4


def export_metadata(inp: Inputs):
    meta = dict(
        timestamp=pd.Timestamp.now().isoformat(),
        config=CFG, economics=ECON,
        workbook=str(DATA_XLSX), workbook_mtime=DATA_XLSX.stat().st_mtime,
        versions=dict(python=sys.version.split()[0], pandas=pd.__version__,
                      numpy=np.__version__, pyomo=pyo.__version__ if hasattr(pyo, "__version__") else "n/a"),
        sites=list(inp.sites["site_id"]),
    )
    (OUT_DIR / "run_metadata.json").write_text(json.dumps(meta, indent=2, default=str))
    return meta
