"""LOCAL ONLY (configs/local is gitignored): build the Zenodo data/code package of the central-TES paper.

    python configs/local/zenodo_build.py [--out <dir>]

Contains the node-id anonymisation map, therefore never pushed. Steps: copy code, anonymise internal node ids, replace
pipe geometry / plant pump data by placeholders, write the K-only calibration, generate the synthetic example, copy the
aggregated results and figures, write the documentation and metadata. Checks (name scan, tests) run separately
(``zenodo_check.py``).
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
VERSION = "1.0.0"
NAME = f"central_tes_dhn_a_v{VERSION}"

# ------------------------------------------------------------------------------------------------ anonymisation map
# internal node ids of the equivalent network -> neutral ids (applied to code, calibration and result files)
RENAME = [
    (re.compile(r"SUED_"), "SO_"),          # south branch nodes / constants
    (re.compile(r"Sued-"), "SO-"),          # sub-area prefixes of the south branch
    (re.compile(r"\bSEC(\d)\b"), r"C\1"),   # city / centre section nodes
    (re.compile(r"KANTEN_SIGMA"), "KANTEN_PRIOR_SD"),
]
PLACEHOLDER_DN, PLACEHOLDER_L = 300, 1000     # pipe geometry placeholder (calibrated K is used by all calculations)

CODE = [
    "scripts/__init__.py", "scripts/dhn_study/__init__.py", "scripts/dhn_study/daten.py", "scripts/dhn_study/hydraulik.py",
    "scripts/dhn_study/netzmodell.py", "scripts/dhn_study/gegenrechnung_pandapipes.py",
    *[f"scripts/dhn_study/central_tes/{m}.py" for m in (
        "__init__", "config", "inputs", "cop", "milp", "coupling", "hydraulics", "metrics", "rolling", "run", "sensitivity",
        "hosting", "economics", "consolidate", "validate_pandapipes", "paper_figures", "paper_tables", "figures", "expansion",
        "synthetic_data")],
    "tests/test_central_tes.py", "configs/central_tes/base.yaml", "configs/central_tes/synthetic.yaml",
]
RESULTS = [
    "scenario_comparison.csv", "economics_break_even.csv", "economics_tes_sizes.csv",
    "scenario_runs/factorial_summary.csv", "scenario_runs/shapley.json",
    "hosting/summary.csv",
    "rolling_horizon/tes_values_rh.csv", "rolling_horizon/shapley_rh.json", "rolling_horizon/robustness_rh.csv",
    "rolling_horizon/at_values_rh.csv", "rolling_horizon/foresight/foresight_rh.csv",
    "pandapipes/pandapipes_summary.csv",
    "sensitivities/A3e/single_energy_only/F001-E/annual_metrics.json",
    "sensitivities/A3e/single_energy_only/F111-E/annual_metrics.json",
]
FIGS = {"fig1_value_attribution": "Fig. 2", "fig2_operation_week": "Fig. 3", "fig7_prosumers": "Fig. 4",
        "fig3_pressure_footprint": "Fig. 5", "fig5_south_hosting": "Fig. 6", "fig6_hydraulic_validation": "Fig. 7",
        "fig4_break_even_investment": "Fig. 8"}


def anon(text: str) -> str:
    for pat, rep in RENAME:
        text = pat.sub(rep, text)
    return text


def copy_text(src: Path, dst: Path, extra=None) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    t = anon(src.read_text(encoding="utf-8"))
    if extra:
        t = extra(t)
    dst.write_text(t, encoding="utf-8")


# ------------------------------------------------------------------------------------------------ code edits
def edit_netzmodell(t: str) -> str:
    """Pipe DN / length placeholders; docstring note."""
    def rep(m):
        return f'("{m.group(1)}", "{m.group(2)}", "{m.group(3)}", {PLACEHOLDER_DN}, {PLACEHOLDER_L})'
    t2, n = re.subn(r'\("(\w+)", "(\w+)", "(\w+)", \d+, \d+\)', rep, t)
    assert n >= 30, n
    t2 = t2.replace("# Kanten: id, von, nach, DN [mm], Länge [m] (Schätzwerte, nur Startwert der Kalibrierung).",
                    "# Kanten: id, von, nach, DN [mm], Länge [m]. DATA PUBLICATION: DN and length are PLACEHOLDERS "
                    f"(DN {PLACEHOLDER_DN}, {PLACEHOLDER_L} m);\n# all calculations use the calibrated resistances K "
                    "(scripts/dhn_study/kalibrierung/). Own network: enter the real geometry here.")
    assert "PLACEHOLDERS" in t2
    t2 = re.sub(r"Die Topologie stammt aus den Betreiberplänen \(anonymisiert, ohne Geografie\); Längen und Durchmesser sind Schätzwerte\n"
                r"und dienen nur als Startwert\.",
                "Die Topologie ist anonymisiert (ohne Geografie). In dieser Veröffentlichung sind Längen und Durchmesser Platzhalter;\n"
                "maßgeblich sind die kalibrierten Widerstände K.", t2)
    return t2


INIT_DHN = '''"""Shared modules of the DHN-A analyses used by the central-TES study (data publication subset).

* ``daten``                     data loading, water properties, corrected generation per plant
* ``hydraulik``                 plant mass flows and pressure-coupling helpers
* ``netzmodell``                hydraulic equivalent network (meshed, supply + return) and its calibration
* ``run_netzmodell``            calibration I/O (published calibration in ``kalibrierung/``)
* ``gegenrechnung_pandapipes``  independent pandapipes model of the equivalent network
* ``central_tes``               the study (MILP, coupling, rolling horizon, sensitivities, tables, figures)
"""
'''


def edit_hydraulik(t: str) -> str:
    return t.replace("(z. B. KWK, Heizwerk West)", "(z. B. KWK, HW2)")      # no-op once the repo is cleaned


def edit_hydraulics(t: str) -> str:
    old = "        # PS1 towards the south: one pump 429 m³/h @ 40 m (no parallel operation, plan A), generic curve\n" \
          "        self.ps1_curve = PumpCurve(Qn=429 * daten.rho_w(100.0) / 3600, Hn=40.0,"
    new = "        # PS1 towards the south: one pump, generic example curve (450 m³/h @ 40 m; data publication placeholder)\n" \
          "        self.ps1_curve = PumpCurve(Qn=450 * daten.rho_w(100.0) / 3600, Hn=40.0,"
    assert old in t
    return t.replace(old, new)


RUN_NETZMODELL = '''"""Calibration I/O of the equivalent network (trimmed for the data publication).

The calibration driver of the study (fit of the edge resistances to the measured pressures and flows of 2025) needs the
measured data set and is not part of this package; the fit itself is ``netzmodell.kalibriere``. This module keeps the
functions the study code uses: the location of the published calibration and reading / writing a calibration.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import netzmodell as nm

KALIBRIERUNG_REPO = Path(__file__).resolve().parent / "kalibrierung"   # published calibration (variants A, B, C)
MINDEST_MITTE = 1.0                                                   # minimum Δp at the city/centre stations [bar]


def speichere_kalibrierung(kal: dict, nz: nm.Netz, ordner: Path) -> None:
    """Calibration as CSV: resistance per edge plus load weights, base-load shifts and station offsets."""
    ordner.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"Multiplikator": kal["multiplikator"], "K [bar/(kg/s)²]": kal["K"],
                  "K_prior": nz.k0}).rename_axis("Kante").to_csv(ordner / "kalibrierung_kanten.csv")
    pd.Series({**{f"Gewicht {k}": v for k, v in kal["gewichte"].items()},
               **{f"Grundlast {k} [kg/s]": v for k, v in kal["grundlast"].items()},
               **{f"Versatz {k} [bar]": v for k, v in kal["versatz"].items()}}).to_csv(ordner / "kalibrierung_last_versatz.csv")


def lade_kalibrierung(out, nz: nm.Netz) -> dict:
    """Restore a calibration from its CSV files."""
    k = pd.read_csv(out / "kalibrierung_kanten.csv", index_col=0)
    lv = pd.read_csv(out / "kalibrierung_last_versatz.csv", index_col=0).iloc[:, 0]
    sub = lambda pre, suf="": {i[len(pre):].replace(suf, ""): float(v) for i, v in lv.items() if i.startswith(pre)}  # noqa: E731
    return {"K": k.loc[nz.kanten_ids, "K [bar/(kg/s)²]"].to_numpy(), "multiplikator": k.loc[nz.kanten_ids, "Multiplikator"],
            "gewichte": sub("Gewicht "), "grundlast": sub("Grundlast ", " [kg/s]"),
            "versatz": pd.Series(sub("Versatz ", " [bar]")), "erfolg": True, "kosten": float("nan")}
'''

CONFTEST = '''"""Tests run on the SYNTHETIC example unless CENTRAL_TES_CONFIG points to another configuration."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("CENTRAL_TES_CONFIG", "configs/central_tes/synthetic.yaml")
if not (ROOT / "data" / "synthetic" / "measurements_2025_hourly.parquet").exists():
    from scripts.dhn_study.central_tes import synthetic_data
    synthetic_data.write(ROOT / "data" / "synthetic", 2025, "2025-01-01 00:00", "2025-02-28 23:00")
'''


def write_calibration(pkg: Path) -> None:
    """K only (option chosen by the author): fitted resistances per edge; load weights 1, base-load shifts 0, station
    offsets 0; multiplier and K_prior refer to the placeholder geometry."""
    sys.path.insert(0, str(pkg))
    for k in [m for m in list(sys.modules) if m.startswith("scripts")]:
        del sys.modules[k]
    from scripts.dhn_study import netzmodell as nm          # the package copy (anonymised, placeholder geometry)
    nz = nm.netz()
    for v in ("A", "B", "C"):
        src = pd.read_csv(REPO / "scripts/dhn_study/kalibrierung" / v / "kalibrierung_kanten.csv", index_col=0)
        K = src.loc[nz.kanten_ids, "K [bar/(kg/s)²]"].to_numpy()
        out = pkg / "scripts/dhn_study/kalibrierung" / v
        out.mkdir(parents=True, exist_ok=True)
        pd.DataFrame({"Multiplikator": K / nz.k0, "K [bar/(kg/s)²]": K, "K_prior": nz.k0},
                     index=pd.Index(nz.kanten_ids, name="Kante")).to_csv(out / "kalibrierung_kanten.csv")
        lv = {**{f"Gewicht {g}": 1.0 for g in nm.LASTGRUPPEN}, **{f"Grundlast {g} [kg/s]": 0.0 for g in nm.LASTGRUPPEN},
              **{f"Versatz {s} [bar]": 0.0 for s in nm.STATIONEN}}
        pd.Series(lv).to_csv(out / "kalibrierung_last_versatz.csv")
    (pkg / "scripts/dhn_study/kalibrierung/README.md").write_text(
        "# Calibration of the equivalent network (variants A, B, C)\n\n"
        "`kalibrierung_kanten.csv`: calibrated resistance K of each edge (supply + return, bar/(kg/s)²) of the three\n"
        "equally good calibration variants used in the paper (A = reference, B and C = sensitivity). `K_prior` and\n"
        "`Multiplikator` refer to the placeholder geometry in `netzmodell.KANTEN` and carry no information.\n\n"
        "`kalibrierung_last_versatz.csv`: load-group weights, base-load shifts and station offsets are NOT published\n"
        "(neutral values 1 / 0 / 0). Node and edge ids are anonymised; the topology corresponds to Fig. 1 of the paper.\n",
        encoding="utf-8")
    sys.path.remove(str(pkg))


def pandapipes_stats(src: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Aggregated deviation statistics (no hourly values): per case / friction law / node and binned over Δp."""
    h = pd.read_csv(src).dropna(subset=["dp_pandapipes"])
    h["diff"] = h["dp_pandapipes"] - h["dp_ersatznetz"]
    q = lambda p: (lambda s: float(s.quantile(p)))  # noqa: E731
    g = h.groupby(["case", "model", "node"])["diff"]
    node = g.agg(n="count", mean="mean", sd="std", p5=q(0.05), median="median", p95=q(0.95)).join(
        h.assign(a=h["diff"].abs()).groupby(["case", "model", "node"])["a"].agg(abs_p95=q(0.95), abs_max="max")).reset_index()
    fig = h[h["case"].isin(["F000-E", "F111-E", "F111-H", "L20 F111-H"])].copy()
    bins = np.arange(0, np.ceil(fig["dp_ersatznetz"].max() * 2) / 2 + 0.5, 0.5)
    fig["dp_bin_bar"] = pd.cut(fig["dp_ersatznetz"], bins).astype(str)
    b = fig.groupby(["model", "dp_bin_bar"], observed=True)["diff"].agg(
        n="count", p5=q(0.05), median="median", p95=q(0.95)).reset_index()
    return node.round(4), b.round(4)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/tmp/zenodo_build")
    a = ap.parse_args(argv)
    pkg = Path(a.out) / NAME
    if pkg.exists():
        shutil.rmtree(pkg)
    pkg.mkdir(parents=True)
    # code
    for f in CODE:
        extra = {"scripts/dhn_study/netzmodell.py": edit_netzmodell, "scripts/dhn_study/hydraulik.py": edit_hydraulik,
                 "scripts/dhn_study/central_tes/hydraulics.py": edit_hydraulics,
                 "scripts/dhn_study/__init__.py": lambda t: INIT_DHN}.get(f)
        copy_text(REPO / f, pkg / f, extra)
    (pkg / "scripts/dhn_study/run_netzmodell.py").write_text(RUN_NETZMODELL, encoding="utf-8")
    (pkg / "tests/conftest.py").write_text(CONFTEST, encoding="utf-8")
    write_calibration(pkg)
    # synthetic example (generated with the package code)
    import subprocess
    subprocess.run([sys.executable, "-m", "scripts.dhn_study.central_tes.synthetic_data", "--out", "data/synthetic"],
                   cwd=pkg, check=True, capture_output=True)
    # aggregated results
    r_src, r_dst = REPO / "results/central_tes", pkg / "results/central_tes"
    for f in RESULTS:
        if (r_src / f).exists():
            copy_text(r_src / f, r_dst / f)
    for p in sorted((r_src / "sensitivities").glob("*/summary.csv")) + sorted((r_src / "sensitivities").glob("*/expansion_*.csv")) \
            + sorted((r_src / "sensitivities").glob("*/cases.json")):
        copy_text(p, r_dst / p.relative_to(r_src))
    node, bins = pandapipes_stats(r_src / "pandapipes/pandapipes_hours.csv")
    for df in (node, bins):
        if "node" in df:
            df["node"] = df["node"].map(anon)
    node.to_csv(r_dst / "pandapipes/pandapipes_deviation_by_node.csv", index=False)
    bins.to_csv(r_dst / "pandapipes/pandapipes_deviation_binned.csv", index=False)
    # tables (generated from these results) and figure list
    copy_text(REPO / "reports/central_tes/paper_tables.md", pkg / "results/paper_tables.md")
    copy_text(REPO / "docs/dhn_storage_study/central_tes/model_and_deviations.md", pkg / "docs/model_and_deviations.md")
    # documentation and metadata
    static = Path(__file__).resolve().parent / "zenodo_static"
    for f in sorted(static.rglob("*")):
        if f.is_file():
            (pkg / f.relative_to(static)).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, pkg / f.relative_to(static))
    # figures
    (pkg / "figures").mkdir()
    for stem in FIGS:
        shutil.copy2(REPO / "results/central_tes/paper_figures" / f"{stem}.pdf", pkg / "figures" / f"{stem}.pdf")
    for d in list(pkg.rglob("__pycache__")):
        shutil.rmtree(d)
    print(pkg)


if __name__ == "__main__":
    main()
