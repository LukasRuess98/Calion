"""Paper 2 artefact extractor.

Extends the Paper 1 extract_artefacts.py pattern with Paper 2-specific outputs:
- geometry.csv: V_TES, h_TES (derived), E_TES_max, p_betr
- dsm_hourly.csv: delta(t), dpos(t), dneg(t) per DSM consumer
- kpis.json: All 24 KPIs from spec Section 6
- economics.csv (extended): CAPEX breakdown by component

Mirrors the extract_all() interface from scripts/paper/extract_artefacts.py.
"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path

logger = logging.getLogger(__name__)

# Water properties
_RHO = 971.8
_CP = 4.189
_G = 9.81
_P_ATM = 1.013


def _try_get(wf_result, attr: str, default=None):
    """Safely extract attribute from workflow result."""
    try:
        pf = wf_result.pf_result
        if pf is None:
            return default
        return getattr(pf, attr, default)
    except Exception:
        return default


def _pyomo_val(var, default: float = 0.0) -> float:
    """Extract scalar value from a Pyomo variable."""
    try:
        import pyomo.environ as pyo
        return float(pyo.value(var))
    except Exception:
        return default


def write_meta_p2(outdir: Path, scen_id: str, cfg: dict, wf_result, solve_s: float) -> dict:
    """Write meta.json with solver stats and scenario metadata."""
    pf = getattr(wf_result, "pf_result", None)
    # 2026-07-08 (O-7): ScenarioResult has no `solver_status` attribute, so the
    # old getattr() always wrote "unknown". Read the real solver metadata dict
    # (termination_condition, status, solution_count) that solver.py populates,
    # and derive an honest status: "no_incumbent" when solution_count <= 0 so a
    # zero-cost / no-solution run is never silently recorded as a valid result.
    solver_meta = getattr(pf, "solver", {}) if pf is not None else {}
    if not isinstance(solver_meta, dict):
        solver_meta = {}
    term_cond = str(solver_meta.get("termination_condition", "")).strip()
    sol_count = solver_meta.get("solution_count", None)
    if sol_count is not None and sol_count <= 0:
        status = "no_incumbent"
    elif term_cond:
        status = term_cond            # e.g. "optimal", "maxTimeLimit"
    else:
        status = str(solver_meta.get("status", "unknown"))

    # Objective: read from the summary objective section (never fabricate 0);
    # force None when there is no incumbent.
    obj_eur = None
    if sol_count is None or sol_count > 0:
        summ = getattr(pf, "summary", {}) if pf is not None else {}
        obj_section = summ.get("objective", {}) if hasattr(summ, "get") else {}
        if isinstance(obj_section, dict):
            for _k in ("OBJ_value_EUR", "Model_OBJ_value_EUR"):
                if obj_section.get(_k) is not None:
                    obj_eur = float(obj_section[_k])
                    break

    meta = {
        "scenario_id": scen_id,
        "solver": cfg.get("run", {}).get("solver", "gurobi"),
        "solve_s": round(solve_s, 2),
        "status": status,
        "termination_condition": term_cond or None,
        "solution_count": sol_count,
        "mip_gap": solver_meta.get("mip_gap", _try_get(wf_result, "mip_gap")),
        "obj_eur": obj_eur,
        "n_vars": solver_meta.get("num_vars", _try_get(wf_result, "n_vars")),
        "n_constraints": solver_meta.get("num_constr", _try_get(wf_result, "n_constraints")),
    }
    outdir.mkdir(parents=True, exist_ok=True)
    with open(outdir / "meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    return meta


def write_geometry_p2(outdir: Path, wf_result, scen: dict) -> dict | None:
    """Write geometry.csv: TES volume, height (derived), capacity, pressure.

    Reads the geometry scalars captured by result_collector in
    summary["objective"]["tes_geometry"] (pf_result carries no model handle).
    Returns dict with geometry values of the investable TES, or None.
    """
    try:
        pf = wf_result.pf_result
        if pf is None:
            return None
        summary = getattr(pf, "summary", None) or {}
        obj_section = summary.get("objective", {}) if hasattr(summary, "get") else {}
        geo_map = obj_section.get("tes_geometry") or {}
        if not geo_map:
            return None

        rows = []
        r_hd = 3.0
        # Try to read the real aspect ratio from the scenario's asset params
        for _acfg in (scen.get("overrides", {}) or {}).get("assets", {}).values():
            if isinstance(_acfg, dict) and "r_hd" in _acfg:
                r_hd = float(_acfg["r_hd"])
        for comp, g in geo_map.items():
            V = float(g.get("V_m3") or 0.0)
            if V > 0:
                # V = pi/(4*r_hd^2) * h^3  ->  h = (V * 4 * r_hd^2 / pi)^(1/3)
                h = (V * 4.0 * r_hd**2 / math.pi) ** (1.0 / 3.0)
            else:
                h = 0.0
            p_betr = _P_ATM + _RHO * _G * h / 1e5 if h > 0 else _P_ATM
            rows.append({
                "component": comp,
                "build": round(float(g.get("build") or 0.0)),
                "V_TES_m3": round(V, 2),
                "h_TES_m": round(h, 2),
                "E_TES_max_MWh": round(float(g.get("E_max_MWh") or 0.0), 2),
                "cap_power_MW": round(float(g.get("cap_power_MW") or 0.0), 2),
                "p_betr_bar": round(p_betr, 3),
            })

        # Endogenous site choice (if present)
        endog_sites = {
            "endog_hp_site": obj_section.get("endog_hp_site"),
            "endog_tes_site": obj_section.get("endog_tes_site"),
        }

        if rows:
            import csv
            csv_path = outdir / "geometry.csv"
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                w.writeheader()
                w.writerows(rows)
            if any(v for v in endog_sites.values()):
                with open(outdir / "endog_sites.json", "w", encoding="utf-8") as f:
                    json.dump(endog_sites, f, indent=2)
            return rows[0]

    except Exception as exc:
        logger.warning("geometry.csv extraction failed: %s", exc)
    return None


def write_dsm_hourly_p2(outdir: Path, wf_result) -> bool:
    """Write dsm_hourly.csv: delta(t), dpos(t), dneg(t) for each DSM consumer."""
    try:
        pf = wf_result.pf_result
        if pf is None:
            return False
        model = getattr(pf, "model", None)
        if model is None:
            return False

        rows = {}
        for attr_name in dir(model):
            if attr_name.endswith("_dpos"):
                comp = attr_name[:-5]
                dpos_var = getattr(model, attr_name)
                dneg_var = getattr(model, f"{comp}_dneg", None)
                if dneg_var is None:
                    continue
                for t in dpos_var:
                    rows.setdefault(t, {})[f"{comp}_dpos"] = round(_pyomo_val(dpos_var[t]), 4)
                    rows[t][f"{comp}_dneg"] = round(_pyomo_val(dneg_var[t]), 4)
                    rows[t][f"{comp}_delta"] = round(
                        _pyomo_val(dpos_var[t]) - _pyomo_val(dneg_var[t]), 4
                    )

        if rows:
            import csv
            sorted_ts = sorted(rows.keys())
            fieldnames = ["t"] + sorted(next(iter(rows.values())).keys())
            with open(outdir / "dsm_hourly.csv", "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=fieldnames)
                w.writeheader()
                for t in sorted_ts:
                    row = {"t": t, **rows[t]}
                    w.writerow(row)
            return True

    except Exception as exc:
        logger.warning("dsm_hourly.csv extraction failed: %s", exc)
    return False


def extract_all_p2(
    scen_id: str,
    cfg: dict,
    wf_result,
    solve_s: float,
    outdir: Path,
    scen: dict,
) -> Path:
    """Master extractor for Paper 2 artefacts.

    Calls all write_* functions and delegates economics/dispatch to
    the Paper 1 extract_artefacts module for reuse.
    """
    outdir.mkdir(parents=True, exist_ok=True)

    # Reuse Paper 1 extraction for standard artefacts.
    # NOTE (2026-07-08, O-7): the Paper 1 extractor ALSO writes meta.json (its
    # own write_meta), which used to clobber the P2 meta.json with a less
    # informative version. Run it FIRST, then write the authoritative P2
    # meta.json last so it wins.
    try:
        from scripts.paper.extract_artefacts import extract_all as extract_p1
        # Paper 1 extractor writes economics.csv, dispatch_hourly.csv, etc.
        _tmp_cfg_path = _write_tmp_yaml(cfg)
        try:
            extract_p1(scen_id, str(_tmp_cfg_path), wf_result, solve_s, outdir=outdir)
        except Exception as exc:
            logger.warning("[%s] Paper 1 extraction partial failure: %s", scen_id, exc)
        finally:
            try:
                _tmp_cfg_path.unlink()
            except OSError:
                pass
    except ImportError:
        logger.warning("Paper 1 extract_artefacts not importable — skipping standard artefacts")

    # Authoritative P2 meta.json (written AFTER P1 so it is not overwritten).
    meta = write_meta_p2(outdir, scen_id, cfg, wf_result, solve_s)
    logger.info("[%s] meta.json: status=%s, obj=%.0f €",
                scen_id, meta.get("status"), meta.get("obj_eur") or 0)

    # Paper 2-specific artefacts
    geo = write_geometry_p2(outdir, wf_result, scen)
    if geo:
        logger.info("[%s] geometry.csv: V=%.1f m³, h=%.1f m, E=%.1f MWh, p=%.2f bar",
                    scen_id, geo["V_TES_m3"], geo["h_TES_m"],
                    geo["E_TES_max_MWh"], geo["p_betr_bar"])

    write_dsm_hourly_p2(outdir, wf_result)

    # Scenario metadata — include heat curve parameters for KPI calculator
    _HK_PARAMS = {
        "memmingen": {"HK0": (1.0, 74.0), "HK1": (0.8, 70.0), "HK2": (0.6, 66.0)},
        "stadtbach":  {"HK0": (1.0, 70.0), "HK1": (0.8, 65.0), "HK2": (0.6, 60.0)},
    }
    network = scen.get("network", "")
    hk_stage = scen.get("heat_curve_stage", "HK0")
    hk_data = _HK_PARAMS.get(network, {}).get(hk_stage)
    k_val, T_VL_min_val = hk_data if hk_data else (None, None)
    with open(outdir / "scenario_meta.json", "w", encoding="utf-8") as f:
        json.dump({
            "id": scen["id"],
            "network": network,
            "heat_curve_stage": hk_stage,
            "tes_node": scen.get("tes_node"),
            "baseline": scen.get("baseline", False),
            "k": k_val,
            "T_VL_min_c": T_VL_min_val,
        }, f, indent=2)

    return outdir


def _write_tmp_yaml(cfg: dict) -> "Path":
    import tempfile
    import yaml
    tmp = tempfile.NamedTemporaryFile(suffix=".yaml", delete=False, mode="w", encoding="utf-8")
    yaml.dump(cfg, tmp, allow_unicode=True, default_flow_style=False)
    tmp.flush()
    return Path(tmp.name)
