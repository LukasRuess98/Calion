"""
Pump-friction linearisation error by POST-PROCESSING the L3+ optimal dispatch.

The corrected pump model changed only the pump term of the L3+ vs L3^NL gap.
The station Δp (0.6 bar) term is LINEAR and charged identically in L3+ and L3^NL,
so it cancels in the difference. The ONLY thing that differs between L3+ and L3^NL
on the pump is the pipe FRICTION power: L3+ charges the secant-PWL of the cubic
P(ṁ)=2·k_flow·ṁ³·C, L3^NL charges the exact cubic. Because both are functions of
the SAME per-pipe mass flow ṁ (which the fixed L3+ dispatch gives us), the friction
linearisation error is computable exactly here — no intractable NonConvex re-solve.

We reconstruct each pipe's exact model curve from pipes.csv geometry using the
identical constants/formulae as calion/models/blocks/pipe_pair.py, evaluate the
secant-PWL (what L3+ paid) and the exact cubic (what L3^NL would pay) at every
hour's ṁ, and value the difference at the hourly electricity+grid-CO₂ price.
"""
import json, sys
from math import pi
from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[0]
WIN = ROOT / "output" / "paper_runs" / "_linearization_2window_24h"

# --- model constants (verbatim from pipe_pair.py) ---------------------------
DENSITY = 1000.0        # kg/m³            (pipe_pair.py:110)
F_FRIC  = 0.02          # friction factor  (pipe_pair.py:858 default)
ETA     = 0.75          # pump_efficiency  (config pump_efficiency)
VMAX    = 2.5           # m/s              (max_velocity_m_s)
CO2_PRICE = 100.0       # EUR/t            (config co2_price_eur_per_t)
BP_FRACS = [0.0, 0.12, 0.35, 1.0]   # fine-PWL breakpoints (pipe_pair.py:934)


def pipe_curves(length_m, diameter_mm, m_dot_max):
    """Return (P_exact_fn, P_pwl_fn) [MW] as functions of ṁ [kg/s], matching the model."""
    d_inner = diameter_mm / 1000.0 * 0.94
    area = pi * (d_inner / 2.0) ** 2
    k_pressure = F_FRIC * (length_m / d_inner) * (DENSITY / 2.0) / 1e5
    k_flow = k_pressure / ((DENSITY * area) ** 2)
    v_max_calc = VMAX * DENSITY * area
    eff_max = min(m_dot_max, v_max_calc) if m_dot_max else v_max_calc

    C = 2.0 * k_flow * 1e5 / (DENSITY * ETA * 1e6)   # P = C·ṁ³  [MW]  (pipe_pair.py:1009-1011)
    bp_flows = [f * eff_max for f in BP_FRACS]
    bp_p = [C * f ** 3 for f in bp_flows]
    slopes, intercepts = [], []
    for s in range(3):
        denom = bp_flows[s + 1] - bp_flows[s]
        sl = (bp_p[s + 1] - bp_p[s]) / denom if denom > 0 else 0.0
        slopes.append(sl); intercepts.append(bp_p[s] - sl * bp_flows[s])

    def p_exact(m):
        return C * m ** 3

    def p_pwl(m):
        # secant PWL: pick the segment containing m (the pinned equality means the
        # charged value is the segment line evaluated at m)
        m = min(m, bp_flows[-1])
        for s in range(3):
            if m <= bp_flows[s + 1] + 1e-9:
                return max(slopes[s] * m + intercepts[s], 0.0)
        return slopes[-1] * m + intercepts[-1]

    return p_exact, p_pwl, eff_max


def analyse(window: str):
    d = WIN / window / "L3plus"
    pipes = pd.read_csv(d / "pipes.csv")
    ps = pd.read_parquet(d / "pipe_state_hourly.parquet")
    disp = pd.read_csv(d / "dispatch_hourly.csv", index_col=0, parse_dates=True)
    econ = pd.read_csv(d / "economics.csv").iloc[0]

    base_ids = set(pipes["pipe_id"])
    ps = ps[ps["pipe_id"].isin(base_ids)].copy()          # 14 real pipes only
    dt_h = 1.0

    # marginal €/MWh for extra pump electricity = buy price + grid-CO₂ charge
    price = (disp["lambda_buy_eur_MWh"] + 0.1 * disp["ef_grid_kg_MWh"]).astype(float)
    price.index = pd.to_datetime(price.index)

    geo = {r.pipe_id: pipe_curves(r.length_m, r.diameter_mm, r.m_dot_max_kg_s)
           for r in pipes.itertuples()}

    ps["ts"] = pd.to_datetime(ps["timestamp"])
    e_exact = e_pwl = cost_delta = 0.0
    for pid, g in ps.groupby("pipe_id"):
        pex, ppw, _ = geo[pid]
        m = g["m_dot_kg_s"].clip(lower=0).values
        pe = np.array([pex(x) for x in m]); pp = np.array([ppw(x) for x in m])
        e_exact += pe.sum() * dt_h
        e_pwl   += pp.sum() * dt_h
        pr = price.reindex(g["ts"].values).fillna(price.mean()).values
        cost_delta += ((pp - pe) * pr * dt_h).sum()

    tot = float(econ["cost_total_eur"])
    return {
        "window": window,
        "cost_total_eur": round(tot, 2),
        "friction_pump_exact_MWh": round(e_exact, 4),
        "friction_pump_pwl_MWh": round(e_pwl, 4),
        "friction_pump_overcharge_MWh": round(e_pwl - e_exact, 4),
        "friction_lin_cost_delta_eur": round(cost_delta, 2),
        "friction_lin_error_pct_of_total": round(cost_delta / tot * 100, 4),
        "mean_price_eur_MWh": round(float(price.mean()), 2),
    }


if __name__ == "__main__":
    out = {}
    for w in ["jan_2025", "feb_2025"]:
        if (WIN / w / "L3plus" / "pipes.csv").exists():
            out[w] = analyse(w)
            r = out[w]
            print(f"\n=== {w} ===")
            print(f"  friction pump  exact = {r['friction_pump_exact_MWh']:.3f} MWh | "
                  f"PWL(charged) = {r['friction_pump_pwl_MWh']:.3f} MWh | "
                  f"over-charge = {r['friction_pump_overcharge_MWh']:.3f} MWh")
            print(f"  friction linearisation cost error = {r['friction_lin_cost_delta_eur']:+,.2f} EUR "
                  f"= {r['friction_lin_error_pct_of_total']:+.4f} % of L3+ total ({r['cost_total_eur']:,.0f} EUR)")
    (WIN / "pump_linearization_error.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\n[OK] -> {WIN / 'pump_linearization_error.json'}")
