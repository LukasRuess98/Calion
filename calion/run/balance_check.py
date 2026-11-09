"""System heat balance check R(t) (v12 B1, 2026-11-06).

    R(t) = sum generation - sum demand - sum pipe losses (supply + return) - sum dump - sum storage charge
           (storage discharge is part of generation: it sits on the same heat-out bus as the generators)

R < 0 means demand or losses were covered without any generation (phantom heat, v11-M1 / v12-M1).
A small positive R is expected: junctions without a heat balance lose energy where incoming and outgoing
pipes carry different dT Params (v12-M2, Stadtbach ~ +0.1 MW, conservative).

Two entry points, one formula and one classification:
  * balance_from_model(model)   -- solved Pyomo model; the terms are registered by
                                   constraint_builder.add_per_node_heat_balance as model._v12_balance_terms
  * balance_from_dump(run_dir)  -- an existing run directory (full_solution_dump.json + dispatch_hourly.csv),
                                   for runs solved before this check existed. Model time index is 1-based,
                                   dispatch_hourly.csv rows are 0-based (row i <-> t = i + 1).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

# Thresholds from the v12 task (Teil B1). Only ever tighten them, never loosen.
R_MIN_MW = -0.05            # any hour below -> phantom heat
ABS_R_MAX_MW = 0.5          # any hour with |R| above
ABS_SUM_FRAC = 0.002        # |sum R| above 0.2 % of the demand over the horizon


def classify(R: np.ndarray, demand_sum_mwh: float, dt_h: float = 1.0) -> dict[str, Any]:
    R = np.asarray(R, dtype=float)
    r_sum = float(R.sum() * dt_h)
    reasons = []
    if R.min() < R_MIN_MW:
        reasons.append(f"min R = {R.min():.4f} MW < {R_MIN_MW} MW")
    if np.abs(R).max() > ABS_R_MAX_MW:
        reasons.append(f"max |R| = {np.abs(R).max():.4f} MW > {ABS_R_MAX_MW} MW")
    if demand_sum_mwh > 0 and abs(r_sum) > ABS_SUM_FRAC * demand_sum_mwh:
        reasons.append(f"|sum R| = {abs(r_sum):.1f} MWh > {ABS_SUM_FRAC:.1%} of demand ({demand_sum_mwh:.1f} MWh)")
    return {
        "status": "balance_fail" if reasons else "ok",
        "reasons": reasons,
        "R_min_MW": float(R.min()),
        "R_max_MW": float(R.max()),
        "R_abs_max_MW": float(np.abs(R).max()),
        "R_sum_MWh": r_sum,
        "R_sum_pct_of_demand": (100.0 * r_sum / demand_sum_mwh) if demand_sum_mwh > 0 else None,
        "hours_R_below_min": int((R < R_MIN_MW).sum()),
        "hours_R_negative": int((R < 0.0).sum()),
        "demand_MWh": float(demand_sum_mwh),
        "thresholds": {"R_min_MW": R_MIN_MW, "abs_R_max_MW": ABS_R_MAX_MW, "abs_sum_frac_of_demand": ABS_SUM_FRAC},
        "formula": "R = gen - demand - pipe losses (supply+return) - dump - storage charge; R<0 = phantom heat",
    }


def balance_from_model(model, dt_h: float = 1.0) -> dict[str, Any] | None:
    """R(t) from a solved model. Returns None if the model has no registered terms (non-network model)."""
    import pyomo.environ as pyo

    terms = getattr(model, "_v12_balance_terms", None)
    if not terms:
        return None
    T = list(model.t)

    def _v(x):
        v = pyo.value(x, exception=False)
        return 0.0 if v is None else float(v)

    def _sum(comps):
        out = np.zeros(len(T))
        for c in comps:
            out += np.array([_v(c[t]) for t in T])
        return out

    gen = _sum(terms["gen"])
    charge = _sum(terms["store_in"])
    dump = _sum(terms["dump"])
    loss = _sum(terms["loss"])
    demand = np.array([_v(sum(f(model, t) for f in terms["demand"])) if terms["demand"] else 0.0 for t in T])
    R = gen - demand - loss - dump - charge
    out = classify(R, float(demand.sum() * dt_h), dt_h)
    out.update(source="model", generation_MWh=float(gen.sum() * dt_h), loss_MWh=float(loss.sum() * dt_h),
               dump_MWh=float(dump.sum() * dt_h), storage_charge_MWh=float(charge.sum() * dt_h),
               R_MW=[float(x) for x in R])
    return out


def balance_from_dump(run_dir: str | Path) -> dict[str, Any]:
    """R(t) from an existing run directory (model variables of full_solution_dump.json; demand = the model's own
    demand series as exported to dispatch_hourly.csv)."""
    import pandas as pd

    run_dir = Path(run_dir)
    v = json.loads((run_dir / "full_solution_dump.json").read_text(encoding="utf-8"))["vars"]
    disp = pd.read_csv(run_dir / "dispatch_hourly.csv")
    T = len(disp)

    def s(name):
        a = np.zeros(T)
        d = v.get(name)
        if isinstance(d, dict):
            for k, x in d.items():
                i = int(k) - 1
                if 0 <= i < T:
                    a[i] = float(x or 0.0)
        return a

    # Heat-out terms: thermal generators / P2H (*_Qth), heat pumps (<hp>_Q), storage discharge (*_Qd)
    hp_ids = {k[:-len("_Q_wrg")] for k in v if k.endswith("_Q_wrg")}
    # + HP hot channel (<hp>_Q_hot, S3 hot charging): it feeds the TES directly and is NOT part of <hp>_Q, while
    #   the matching TES charge (*_Qc) is subtracted below -- without it a hot-charging run shows false phantom heat
    gen_names = ([k for k in v if k.endswith("_Qth")] + [f"{h}_Q" for h in hp_ids] + [k for k in v if k.endswith("_Qd")]
                 + [f"{h}_Q_hot" for h in hp_ids if f"{h}_Q_hot" in v])
    gen = sum((s(k) for k in gen_names), np.zeros(T))
    charge = sum((s(k) for k in v if k.endswith("_Qc")), np.zeros(T))
    loss = sum((s(k) for k in v if k.endswith("_Q_loss_supply") or k.endswith("_Q_loss_return")), np.zeros(T))
    # per-node dump Vars only (Q_dump_chp_<asset> are CHP-internal, not node-balance terms)
    dump = sum((s(k) for k in v if k.startswith("Q_dump_") and not k.startswith("Q_dump_chp_")), np.zeros(T))
    slack = sum((s(k) for k in v if k.endswith("_Q_demand_slack")), np.zeros(T))
    demand = disp["Q_demand_total_MW"].to_numpy(dtype=float) - slack
    R = gen - demand - loss - dump - charge
    out = classify(R, float(demand.sum()))
    out.update(source="dump", generation_MWh=float(gen.sum()), loss_MWh=float(loss.sum()),
               dump_MWh=float(dump.sum()), storage_charge_MWh=float(charge.sum()), gen_terms=sorted(gen_names))
    return out


def merge_into_validation(run_dir: str | Path, result: dict[str, Any]) -> dict[str, Any]:
    """Write the check into <run_dir>/validation.json (key `system_balance`) and set the top-level status:
    'balance_fail' if the check fails; otherwise 'ok' unless an earlier gate already reported a warning."""
    run_dir = Path(run_dir)
    vj = run_dir / "validation.json"
    payload = json.loads(vj.read_text(encoding="utf-8")) if vj.exists() else {}
    stored = {k: val for k, val in result.items() if k != "R_MW"}
    payload["system_balance"] = stored
    if result["status"] == "balance_fail":
        payload["status"] = "balance_fail"
    elif payload.get("status") in (None, "linked", "ok"):
        payload["status"] = "ok"
    vj.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    if "R_MW" in result:
        (run_dir / "system_balance_hourly.json").write_text(json.dumps({"R_MW": result["R_MW"]}), encoding="utf-8")
    return payload
