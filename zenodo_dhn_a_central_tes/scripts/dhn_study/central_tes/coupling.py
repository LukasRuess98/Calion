"""Coupling energy layer ↔ hydraulic layer.

Mode E – energy-only MILP, then hydraulic validation of every hour (schedule unchanged); classification FEASIBLE /
INFEASIBLE (limit, location, magnitude). Attribution test per violating hour: does the violation disappear when the
central feed-in is set to zero and the other plants are re-dispatched in proportion to their MILP split?

Mode H – hydraulic-envelope iteration. Two methods:
* ``cuts`` (default, deviation from the spec, see docs): every violated limit of an hour becomes a linear cut on all
  feed-ins (MVA, GT, Bio-KWK, HW1, Q_central; the KWK balances), from a finite-difference gradient of the anchored
  hydraulic evaluation: x(Q) ≈ x(Q^k) + Σ a_g (Q_g − Q_g^k) ≤ −ε. Re-solve, re-validate all hours, repeat until no
  violation or k_max.
* ``central_bisection`` (spec 6.2): bisection on Q_central only (others re-dispatched proportionally); bound
  Q_central ≤ Q_max_hyd; violations that persist at Q_central = 0 are logged as not attributable.
"""

from __future__ import annotations

import time

import numpy as np
import pandas as pd

from . import milp
from .hydraulics import Hydro
from .milp import PLANTS

VARS = ["MVA", "GT", "BIO", "HW1", "NEW", "central", "tes_ext"]


def _sched_cols(sched: pd.DataFrame) -> pd.DataFrame:
    s = sched.copy()
    for c in ("Q_NEW", "Q_tes_ext"):
        if c not in s:
            s[c] = 0.0
    if "Q_EBK" in s:                        # electric boiler at the main plant feeds at the KWK node (root)
        s["Q_KWK"] = s["Q_KWK"] + s["Q_EBK"]
    return s[[f"Q_{g}" for g in PLANTS] + ["Q_central", "Q_tes_ext"]].copy()


def redispatch(sched: pd.DataFrame, rows: np.ndarray, qc_new: np.ndarray, hi: pd.DataFrame, lo: pd.DataFrame) -> pd.DataFrame:
    """Set Q_central to ``qc_new`` in ``rows``; the difference is taken by the other plants in proportion to their MILP
    output (within their bounds); the KWK closes any remainder (it is the balancing node)."""
    out = sched.copy()
    cols = [f"Q_{g}" for g in PLANTS]
    q = out[cols].to_numpy()[rows].copy()
    h, lw = hi[PLANTS].to_numpy()[rows], lo[PLANTS].to_numpy()[rows]
    delta = out["Q_central"].to_numpy()[rows] - qc_new                       # >0: plants must deliver more
    for _ in range(5):
        up = delta > 1e-9
        room = np.where(up[:, None], h - q, q - lw)
        w = np.where(up[:, None], np.maximum(q, 1e-3), q) * (room > 1e-9)
        ws = w.sum(axis=1, keepdims=True)
        share = np.divide(w, ws, out=np.zeros_like(w), where=ws > 0)
        step = np.clip(share * np.abs(delta)[:, None], 0, room)
        q += np.where(up[:, None], step, -step)
        delta = delta - np.where(up, 1, -1) * step.sum(axis=1)
        if np.all(np.abs(delta) < 1e-6):
            break
    q[:, PLANTS.index("KWK")] += delta                                       # remainder to the balancing plant
    out.iloc[rows, [out.columns.get_loc(c) for c in cols]] = q
    out.iloc[rows, out.columns.get_loc("Q_central")] = qc_new
    return out


def attributable(hy: Hydro, sched: pd.DataFrame, rows: np.ndarray, hi, lo) -> np.ndarray:
    """True where the violation disappears with Q_central = 0 (proportional re-dispatch)."""
    if len(rows) == 0:
        return np.zeros(0, bool)
    s0 = redispatch(_sched_cols(sched), rows, np.zeros(len(rows)), hi, lo)
    ev = hy.evaluate(s0, sel=rows)
    return ~ev["violation"].to_numpy()


def _bounds_built(x, cfg, sched):
    lo, hi = milp.plant_bounds(x, cfg)
    if "C_new_MW" in sched and not milp.unserved_mode(cfg):
        hi["NEW"] = np.minimum(hi["NEW"], float(np.asarray(sched["C_new_MW"])[0]))
    return lo, hi


def validate(hy: Hydro, sched: pd.DataFrame, cfg: dict, x: pd.DataFrame) -> pd.DataFrame:
    ev = hy.evaluate(_sched_cols(sched), keep_flows=True)
    lo, hi = _bounds_built(x, cfg, sched)
    rows = np.flatnonzero(ev["violation"].to_numpy() & (np.abs(sched["Q_central"].to_numpy()) > 1e-6))
    ev["attributable"] = False
    if len(rows):
        ev.iloc[rows, ev.columns.get_loc("attributable")] = attributable(hy, sched, rows, hi, lo)
    ev["status"] = np.where(ev["violation"], "INFEASIBLE", "FEASIBLE")
    return ev


# ------------------------------------------------------------------------------------------------- cuts
def gradients(hy: Hydro, sched: pd.DataFrame, rows: np.ndarray, limits: list[str], dq: float = 2.0) -> dict:
    """Finite-difference gradients of the violation functions x_k (bar per MW) w.r.t. VARS in ``rows``."""
    base = _sched_cols(sched)
    ev0 = hy.evaluate(base, sel=rows)
    g = {}
    for v in VARS:
        p = base.copy()
        col = {"central": "Q_central", "tes_ext": "Q_tes_ext"}.get(v, f"Q_{v}")
        p.iloc[rows, p.columns.get_loc(col)] += dq
        p.iloc[rows, p.columns.get_loc("Q_KWK")] -= dq                       # the KWK balances
        ev1 = hy.evaluate(p, sel=rows)
        g[v] = {k: np.nan_to_num((ev1[f"x_{k}"].to_numpy() - ev0[f"x_{k}"].to_numpy()) / dq, posinf=0.0, neginf=0.0)
                for k in limits}
    return {"x0": {k: ev0[f"x_{k}"].to_numpy() for k in limits}, "grad": g}


def make_cuts(hy: Hydro, sched: pd.DataFrame, ev: pd.DataFrame, eps: float, has_central: bool, has_new: bool = False,
              has_tx: bool = False, anticipate_bar: float | None = None) -> list[dict]:
    """Cuts for violating hours. ``anticipate_bar`` (only with a TES away from S): also for every hour in which a limit
    is within this margin (speeds up convergence when the TES charges through a bottleneck; the final
    validation stays exact)."""
    viol = ev["violation"].to_numpy()
    if len(np.flatnonzero(viol)) == 0:
        return []
    ant = np.zeros(len(viol), bool)
    if anticipate_bar is not None and has_tx and "Q_tes_ext" in sched:
        near = np.zeros(len(viol), bool)
        for c in [c for c in ev.columns if c.startswith("x_")]:
            near |= np.nan_to_num(ev[c].to_numpy(), nan=-np.inf) > -float(anticipate_bar)
        ant = near & ~viol          # every hour close to a limit: the TES can move its charging into any of them
    rows = np.flatnonzero(viol | ant)
    thr = {int(t): (1e-6 if viol[t] else -float(anticipate_bar or 0.0)) for t in rows}
    lims = sorted({c[2:] for c in ev.columns if c.startswith("x_")})
    gr = gradients(hy, sched, rows, lims)
    cuts = []
    sc = _sched_cols(sched)
    q0 = {v: sc[{"central": "Q_central", "tes_ext": "Q_tes_ext"}.get(v, f"Q_{v}")].to_numpy()[rows] for v in VARS}
    for k in lims:
        x0 = gr["x0"][k]
        for i, t in enumerate(rows):
            if not np.isfinite(x0[i]) or x0[i] <= thr[int(t)]:
                continue
            a = {v: float(gr["grad"][v][k][i]) for v in VARS if (v != "central" or has_central)}
            if not has_new:
                a.pop("NEW", None)
            if not has_tx:
                a.pop("tes_ext", None)
            if max(abs(c) for c in a.values()) < 1e-6:
                continue
            rhs = -eps - x0[i] + sum(a[v] * q0[v][i] for v in a)
            cuts.append({"t": int(t), "a": a, "rhs": float(rhs), "limit": k, "x0": float(x0[i])})
    return cuts


def mode_h(cfg: dict, x: pd.DataFrame, s: pd.DataFrame, fl: milp.Flags, hy: Hydro, sched_e: pd.DataFrame,
           info_e: dict, log=print) -> tuple[pd.DataFrame, dict, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Mode H with the configured method. Returns schedule, solver info, validation of the final schedule, iteration log,
    cuts."""
    hc = cfg["hydraulics"]
    method = hc.get("mode_h_method", "cuts")
    k_max, eps = int(hc["k_max"]), float(hc.get("cut_margin_bar", 0.02))
    sched, info = sched_e, info_e
    cuts: list[dict] = []
    m = None
    bounds = pd.DataFrame({"lo": np.nan, "hi": np.nan}, index=x.index)
    lo_b, hi_b = milp.plant_bounds(x, cfg)
    it_rows = []
    for k in range(k_max + 1):
        ev = validate(hy, sched, cfg, x)
        nv = int(ev["violation"].sum())
        it_rows.append({"iteration": k, "violations": nv, "attributable": int(ev["attributable"].sum()),
                        "cuts_or_bounds": len(cuts) if method == "cuts" else int(bounds.notna().any(axis=1).sum()),
                        "objective": info["objective"], "runtime_s": info["runtime_s"], "status": info["status"]})
        log(f"    H[{hy.variant}] it {k}: violations {nv}, obj {info['objective']:.0f}")
        if nv == 0 or k == k_max:
            break
        import gc
        if k > 0:
            del m
        gc.collect()
        if method == "cuts":
            new = make_cuts(hy, sched, ev, eps, fl.link and milp.tes_colocated(cfg) or (fl.A or fl.B),
                            bool(cfg.get("new_boiler", {}).get("enabled")), fl.TES and not milp.tes_colocated(cfg),
                            hc.get("anticipate_tes_ext_bar"))
            if not new:
                break
            cuts += new
            m = milp.build(x, s, cfg, fl, cuts=cuts)
        else:
            rows = np.flatnonzero(ev["violation"].to_numpy() & ev["attributable"].to_numpy())
            if len(rows) == 0:
                break
            qc = sched["Q_central"].to_numpy()[rows]
            a_lo, a_hi = np.zeros(len(rows)), np.ones(len(rows))
            for _ in range(int(hc["bisection_iter"])):
                a = 0.5 * (a_lo + a_hi)
                s1 = redispatch(_sched_cols(sched), rows, a * qc, hi_b, lo_b)
                ok = ~hy.evaluate(s1, sel=rows)["violation"].to_numpy()
                a_lo, a_hi = np.where(ok, a, a_lo), np.where(ok, a_hi, a)
            q_ok = a_lo * qc
            col = np.where(qc > 0, "hi", "lo")
            for i, t in enumerate(rows):
                c = col[i]
                old = bounds.iat[t, bounds.columns.get_loc(c)]
                new_v = q_ok[i] if not np.isfinite(old) else (min(old, q_ok[i]) if c == "hi" else max(old, q_ok[i]))
                bounds.iat[t, bounds.columns.get_loc(c)] = new_v
            m = milp.build(x, s, cfg, fl, bounds=bounds)
        info = milp.solve(m, cfg)
        sched = milp.extract(m, x, s, cfg)
    ev = validate(hy, sched, cfg, x)
    info = {**info, "iterations": len(it_rows) - 1, "n_cuts": len(cuts), "converged": int(ev["violation"].sum()) == 0}
    cuts_df = pd.DataFrame([{k: v for k, v in c.items() if k != "a"} | {f"a_{g}": c["a"].get(g, 0.0) for g in VARS} for c in cuts])
    return sched, info, ev, pd.DataFrame(it_rows), cuts_df
