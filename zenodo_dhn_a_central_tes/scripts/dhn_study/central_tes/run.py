"""CLI entry point.

    python -m scripts.dhn_study.central_tes.run --scenario F111-H
    python -m scripts.dhn_study.central_tes.run --factorial [--variants A C B] [--no-h]
    python -m scripts.dhn_study.central_tes.run --sensitivity A1
    python -m scripts.dhn_study.central_tes.run --rh

Results: results/central_tes/scenario_runs/{code}/ (gitignored: they contain partner-derived time series).
"""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from . import config as C
from . import cop, coupling, inputs, metrics, milp
from .hydraulics import Hydro

warnings.filterwarnings("ignore", category=RuntimeWarning)


def _log(msg: str, f: Path | None = None):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    if f:
        with open(f, "a", encoding="utf-8") as h:
            h.write(line + "\n")


def _jsonable(o):
    if isinstance(o, dict):
        return {str(k): _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, np.ndarray):
        return _jsonable(o.tolist())
    if isinstance(o, (np.floating, float)):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    return o


def _save_ev(ev: pd.DataFrame, p: Path):
    e = ev.copy()
    e.attrs = {}
    e.to_parquet(p)


def _dump(obj, p: Path):
    p.write_text(json.dumps(_jsonable(obj), indent=1, ensure_ascii=False), encoding="utf-8")


def _meta(cfg: dict, code: str, info: dict, extra: dict | None = None) -> dict:
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=C.root()).stdout.strip()
    except Exception:  # noqa: BLE001
        commit = ""
    import highspy
    import pyomo
    return {"code": code, "solver": cfg["solver"], "solver_info": info, "python": sys.version.split()[0],
            "pyomo": pyomo.__version__, "highspy": getattr(highspy, "__version__", "n/a"), "platform": platform.platform(),
            "git_commit": commit, "time": time.strftime("%Y-%m-%d %H:%M:%S"), **(extra or {})}


class Study:
    """Holds inputs and hydraulic evaluators for one configuration."""

    def __init__(self, cfg: dict, out: Path, variants: list[str] | None = None, log: Path | None = None):
        self.cfg, self.out, self.logf = cfg, out, log
        self.x = inputs.build(cfg)
        self.s = cop.series(self.x, cfg)
        self.variants = variants or cfg["hydraulics"]["calibration_variants"]
        self.hy = {v: Hydro(cfg, self.x, v) for v in self.variants}
        self.ref_flows: dict = {}
        out.mkdir(parents=True, exist_ok=True)

    def log(self, msg):
        _log(msg, self.logf)

    def energy(self, code: str):
        f = C.parse_code(code)
        fl = milp.Flags(f["A"], f["B"], f["TES"])
        t = time.time()
        m = milp.build(self.x, self.s, self.cfg, fl)
        tb = time.time() - t
        info = milp.solve(m, self.cfg)
        info["build_s"] = tb
        sched = milp.extract(m, self.x, self.s, self.cfg)
        return fl, sched, info

    def run(self, base: str, mode_h: bool = True, h_variants: list[str] | None = None) -> dict:
        """Mode E (+ validation for all variants) and, optionally, Mode H per variant."""
        base = base.split("-")[0]
        fl, sched, info = self.energy(base)
        self.log(f"{base}-E: obj {info['objective']:.0f} EUR, {info['runtime_s']:.1f} s, gap {info['gap']:.2e}")
        de = self.out / f"{base}-E"
        de.mkdir(parents=True, exist_ok=True)
        sched.to_parquet(de / "milp_timeseries.parquet")
        res = {"E": {"metrics": metrics.annual(sched, self.x, self.s, self.cfg, info), "hydraulics": {}}}
        for v, hy in self.hy.items():
            ev = coupling.validate(hy, sched, self.cfg, self.x)
            if base == "F000":
                self.ref_flows[("E", v)] = ev.attrs["flows"]
            hs = metrics.hydraulic_summary(ev, self.ref_flows.get(("E", v)), hy.nz, self.cfg)
            res["E"]["hydraulics"][v] = hs
            _save_ev(ev, de / f"hydraulic_timeseries_{v}.parquet")
            ev.loc[ev["violation"], ["violated_limit", "violation_bar", "attributable", "dp_KWK", "bind"]].to_csv(de / f"violations_{v}.csv")
            self.log(f"  validate[{v}]: {hs['violating_hours']} violating h ({hs['attributable_to_central_h']} attributable), {hs['by_limit']}")
        _dump(res["E"], de / "annual_metrics.json")
        _dump(_meta(self.cfg, f"{base}-E", info), de / "run_metadata.json")
        if not mode_h:
            return res
        res["H"] = {}
        for v, hy in self.hy.items():
            if h_variants is not None and v not in h_variants:
                continue
            dh_ = self.out / f"{base}-H" / v
            dh_.mkdir(parents=True, exist_ok=True)
            sh, ih, evh, it, cuts = coupling.mode_h(self.cfg, self.x, self.s, fl, hy, sched, info, log=self.log)
            if base == "F000":
                self.ref_flows[("H", v)] = hy.evaluate(coupling._sched_cols(sh), keep_flows=True).attrs["flows"]
            evh = hy.evaluate(coupling._sched_cols(sh), keep_flows=True).assign(
                attributable=evh["attributable"], status=evh["status"])
            mh = metrics.annual(sh, self.x, self.s, self.cfg, ih)
            hs = metrics.hydraulic_summary(evh, self.ref_flows.get(("H", v)), hy.nz, self.cfg)
            res["H"][v] = {"metrics": mh, "hydraulics": hs, "info": ih,
                           "dC_hyd_EUR": ih["objective"] - info["objective"]}
            sh.to_parquet(dh_ / "milp_timeseries.parquet")
            _save_ev(evh, dh_ / "hydraulic_timeseries.parquet")
            evh.loc[evh["violation"], ["violated_limit", "violation_bar"]].to_csv(dh_ / "violations.csv")
            it.to_csv(dh_ / "iterations.csv", index=False)
            cuts.to_csv(dh_ / "cuts.csv", index=False)
            _dump(res["H"][v], dh_ / "annual_metrics.json")
            _dump(_meta(self.cfg, f"{base}-H[{v}]", ih), dh_ / "run_metadata.json")
            self.log(f"{base}-H[{v}]: obj {ih['objective']:.0f}, dC_hyd {ih['objective'] - info['objective']:.0f} EUR, "
                     f"converged {ih['converged']} after {ih['iterations']} it, {ih['n_cuts']} cuts")
        return res


def factorial(cfg: dict, out: Path, variants: list[str] | None, mode_h: bool = True, h_all: tuple = ("F000", "F111")) -> dict:
    """Mode E validated on all calibration variants; Mode H on the reference variant for all scenarios and on all
    variants for the scenarios in ``h_all``."""
    st = Study(cfg, out, variants, out / "run.log")
    ref = cfg["hydraulics"]["reference_variant"]
    allres = {}
    for code in C.FACTORIAL:                # F000 first (reference flows)
        allres[code] = st.run(code, mode_h, None if code in h_all else [ref])
    summary = {"E": metrics.shapley({c: r["E"]["metrics"]["cost_total_EUR"] for c, r in allres.items()})}
    if mode_h:
        summary[f"H_{ref}"] = metrics.shapley({c: r["H"][ref]["metrics"]["cost_total_EUR"] for c, r in allres.items()})
    _dump(summary, out / "shapley.json")
    rows = []
    for c, r in allres.items():
        e = r["E"]["metrics"]
        row = {"scenario": c, "C_E": e["cost_total_EUR"]}
        for v in st.variants:
            row[f"viol_E_{v}"] = r["E"]["hydraulics"][v]["violating_hours"]
            row[f"attr_E_{v}"] = r["E"]["hydraulics"][v]["attributable_to_central_h"]
            if mode_h and v in r["H"]:
                row[f"C_H_{v}"] = r["H"][v]["metrics"]["cost_total_EUR"]
                row[f"dC_hyd_{v}"] = r["H"][v]["dC_hyd_EUR"]
                row[f"conv_H_{v}"] = r["H"][v]["info"]["converged"]
        rows.append(row)
    pd.DataFrame(rows).to_csv(out / "factorial_summary.csv", index=False)
    return {"results": allres, "shapley": summary}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=None, help="YAML (default: env CENTRAL_TES_CONFIG, else configs/central_tes/base.yaml)")
    ap.add_argument("--scenario")
    ap.add_argument("--factorial", action="store_true")
    ap.add_argument("--sensitivity")
    ap.add_argument("--rh", action="store_true", help="RH F111 (E, both partner-A forecasts; H with PF cuts)")
    ap.add_argument("--rh-factorial", action="store_true", help="all eight scenarios under RH + Shapley")
    ap.add_argument("--rh-tes", action="store_true", help="TES value under RH: F001/F110 + A1 grid")
    ap.add_argument("--rh-at", action="store_true", help="atmospheric-tank set AT under RH")
    ap.add_argument("--rh-robust", action="store_true", help="RH robustness: noise seeds and σ")
    ap.add_argument("--rh-foresight", action="store_true", help="RH foresight decomposition (window, forecasts, end value)")
    ap.add_argument("--rh-forecast", action="store_true",
                    help="RH with realistic demand forecasts (LOMO demand model, weather error, AR(1)) -> rolling_horizon_forecast/")
    ap.add_argument("--variants", nargs="*")
    ap.add_argument("--no-h", action="store_true")
    ap.add_argument("--out")
    ap.add_argument("--only", nargs="*", help="sensitivity cases to run")
    ap.add_argument("--set", nargs="*", default=[], help="overrides key=value (YAML value), e.g. solver.threads=1")
    a = ap.parse_args(argv)
    import yaml
    cfg = C.load(a.config, {k: yaml.safe_load(v) for k, v in (kv.split("=", 1) for kv in a.set)})
    base_out = C.root() / cfg["paths"]["results"]
    if a.factorial:
        factorial(cfg, Path(a.out) if a.out else base_out / "scenario_runs", a.variants, not a.no_h)
    elif a.scenario:
        st = Study(cfg, Path(a.out) if a.out else base_out / "scenario_runs", a.variants, base_out / "run.log")
        if C.parse_code(a.scenario)["mode"] == "H" and not a.scenario.startswith("F000"):
            st.run("F000", mode_h=True)
        st.run(a.scenario, mode_h=C.parse_code(a.scenario)["mode"] == "H")
    elif a.sensitivity:
        from . import sensitivity
        sensitivity.run(cfg, a.sensitivity, base_out / "sensitivities" / a.sensitivity, a.only, a.no_h)
    elif a.rh or a.rh_factorial or a.rh_tes or a.rh_at or a.rh_robust or a.rh_foresight or a.rh_forecast:
        from . import rolling
        o = base_out / "rolling_horizon"
        if a.rh:
            rolling.run_all(cfg, o)
        if a.rh_factorial:
            rolling.run_factorial_rh(cfg, o)
        if a.rh_tes:
            rolling.run_tes_values(cfg, o)
        if a.rh_at:
            rolling.run_at_values(cfg, o)
        if a.rh_robust:
            rolling.run_robustness(cfg, o)
        if a.rh_foresight:
            rolling.run_foresight(cfg, o, a.only)
        if a.rh_forecast:      # new folder: the reference RH results are not touched
            print(rolling.run_forecast_variants(cfg, base_out / "rolling_horizon_forecast", a.only).round(1).to_string(index=False))


if __name__ == "__main__":
    main()
