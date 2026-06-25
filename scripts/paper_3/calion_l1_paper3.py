"""
CALION L1 Dispatch-Modell fuer Paper 3.

Kupferschienen-MILP: kein Netzmodell, nur Waermebilanz.
2 Netzwerke x 3 Systemkonfigurationen x 3 Betriebsstrategien = 18 Runs.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Optional, Union

import numpy as np
import pandas as pd

try:
    import pyomo.environ as pyo
    from pyomo.opt import SolverFactory, SolverStatus, TerminationCondition
    HAS_PYOMO = True
except ImportError:
    HAS_PYOMO = False

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class NetworkParams:
    """Netzwerkparameter fuer einen Dispatch-Run."""
    name: str
    q_demand_mwh: pd.Series    # Waermebedarf stündlich [MWh/h], tz-aware Europe/Berlin
    t_outside_c: pd.Series     # Aussentemperatur stündlich [°C]


@dataclass
class SystemParams:
    """Systemkonfiguration (S1 / S2 / S3)."""
    config: str                # "S1", "S2", "S3"
    hp_cap_mw: float           # WP Nennwaermeleistung [MW_th]
    hp_cop_rated: float        # COP bei Normbedingungen
    hp_t_ref_c: float = -7.0   # Referenzaussentemp. fuer COP [°C]
    hp_cop_min: float = 1.5    # Min. COP (Clipping)
    eb_cap_mw: float = 0.0     # EK elektr. Leistung [MW_el] (S3)
    eb_eta: float = 0.99       # EK Wirkungsgrad
    tes_cap_mwh: float = 0.0   # TES Kapazitaet [MWh_th] (S2)
    tes_loss_per_h: float = 0.005
    tes_eta_charge: float = 0.95
    tes_eta_discharge: float = 0.95
    tes_soc_min: Optional[float] = field(default=None)   # 0.05 * cap
    tes_soc_max: Optional[float] = field(default=None)   # 0.95 * cap
    tes_soc_init: Optional[float] = field(default=None)  # 0.50 * cap

    def __post_init__(self) -> None:
        if self.tes_cap_mwh > 0.0:
            if self.tes_soc_min is None:
                self.tes_soc_min = 0.05 * self.tes_cap_mwh
            if self.tes_soc_max is None:
                self.tes_soc_max = 0.95 * self.tes_cap_mwh
            if self.tes_soc_init is None:
                self.tes_soc_init = 0.50 * self.tes_cap_mwh
        else:
            self.tes_soc_min = 0.0
            self.tes_soc_max = 0.0
            self.tes_soc_init = 0.0


@dataclass
class OperationParams:
    """Betriebsstrategie (B1 / B2 / B3)."""
    strategy: str                              # "B1", "B2", "B3"
    prices_eur_mwh: Optional[pd.Series]       # DA-Preise stündlich [EUR/MWh] (B2/B3)
    price_fixed: float = 120.0                # Fixpreis fuer B1 [EUR/MWh]
    rh_horizon_h: int = 24                    # Rolling-Horizon Fenstergrösse [h]
    rh_step_h: int = 1                        # Rollschritt [h]
    mip_gap: float = 0.001                    # Solver MIPGap (B1/B2); B3 uses 0.005
    time_limit_s: int = 3600                  # Solver Zeitlimit [s]


# ---------------------------------------------------------------------------
# COP-Modell
# ---------------------------------------------------------------------------

def compute_cop(
    t_outside: Union[float, np.ndarray],
    cop_rated: float,
    t_ref: float = -7.0,
    cop_min: float = 1.5,
) -> Union[float, np.ndarray]:
    """
    Lineares COP-Modell: COP steigt mit Aussentemperatur.

    COP(T) = cop_rated + 0.08 * (T - t_ref), geclippt auf [cop_min, cop_rated * 1.5].
    """
    cop = cop_rated + 0.08 * (t_outside - t_ref)
    return np.clip(cop, cop_min, cop_rated * 1.5)


# ---------------------------------------------------------------------------
# Pyomo MILP Modell
# ---------------------------------------------------------------------------

def build_l1_model(
    net: NetworkParams,
    sys: SystemParams,
    ops: OperationParams,
    time_index: pd.DatetimeIndex,
    soc_init_override: Optional[float] = None,
) -> "pyo.ConcreteModel":
    """
    Baut das L1 MILP-Modell fuer einen gegebenen Zeithorizont.

    soc_init_override: fuer Rolling Horizon (B3) — aktueller SOC aus letztem Schritt.
    """
    if not HAS_PYOMO:
        raise ImportError("Pyomo nicht installiert. Bitte: pip install pyomo")

    n = len(time_index)
    t_vals = list(range(n))

    # Zeitreihen auf Horizont beschneiden
    t_out = net.t_outside_c.reindex(time_index, method="nearest").values
    q_dem = net.q_demand_mwh.reindex(time_index, method="nearest").values

    # Effektiver Strompreis
    if ops.strategy == "B1":
        price = np.full(n, ops.price_fixed)
    else:
        price = ops.prices_eur_mwh.reindex(time_index, method="nearest").values

    # COP-Vektor
    cop = compute_cop(t_out, sys.hp_cop_rated, sys.hp_t_ref_c, sys.hp_cop_min)

    # SOC-Initialisierung
    soc_init = soc_init_override if soc_init_override is not None else sys.tes_soc_init

    model = pyo.ConcreteModel(name=f"L1_{sys.config}_{ops.strategy}")
    model.T = pyo.Set(initialize=t_vals)

    # --- Entscheidungsvariablen ---
    model.p_hp_el = pyo.Var(model.T, domain=pyo.NonNegativeReals)
    model.p_eb_el = pyo.Var(model.T, domain=pyo.NonNegativeReals)
    model.q_tes_ch = pyo.Var(model.T, domain=pyo.NonNegativeReals)
    model.q_tes_dch = pyo.Var(model.T, domain=pyo.NonNegativeReals)
    model.soc_tes = pyo.Var(model.T, domain=pyo.NonNegativeReals)

    # --- Parameter als Pyomo Params ---
    model.cop = pyo.Param(model.T, initialize=dict(enumerate(cop)))
    model.q_demand = pyo.Param(model.T, initialize=dict(enumerate(q_dem)))
    model.price = pyo.Param(model.T, initialize=dict(enumerate(price)))

    has_tes = sys.tes_cap_mwh > 0.0
    has_eb = sys.eb_cap_mw > 0.0
    tes_ramp = sys.tes_cap_mwh * 0.5 if has_tes else 0.0

    # --- [C1] Waermebilanz ---
    def heat_balance_rule(m, t):
        q_hp = m.p_hp_el[t] * m.cop[t]
        q_eb = m.p_eb_el[t] * sys.eb_eta if has_eb else 0.0
        q_ch = m.q_tes_ch[t] if has_tes else 0.0
        q_dch = m.q_tes_dch[t] if has_tes else 0.0
        return q_hp + q_eb + q_dch - q_ch == m.q_demand[t]
    model.c_heat_balance = pyo.Constraint(model.T, rule=heat_balance_rule)

    # --- [C2] Kapazitaetsgrenzen ---
    def hp_upper_rule(m, t):
        return m.p_hp_el[t] <= sys.hp_cap_mw / m.cop[t]
    model.c_hp_upper = pyo.Constraint(model.T, rule=hp_upper_rule)

    if has_eb:
        def eb_upper_rule(m, t):
            return m.p_eb_el[t] <= sys.eb_cap_mw
        model.c_eb_upper = pyo.Constraint(model.T, rule=eb_upper_rule)
    else:
        def eb_fixed_zero(m, t):
            return m.p_eb_el[t] == 0.0
        model.c_eb_zero = pyo.Constraint(model.T, rule=eb_fixed_zero)

    if has_tes:
        def tes_ch_upper(m, t):
            return m.q_tes_ch[t] <= tes_ramp
        def tes_dch_upper(m, t):
            return m.q_tes_dch[t] <= tes_ramp
        model.c_tes_ch_upper = pyo.Constraint(model.T, rule=tes_ch_upper)
        model.c_tes_dch_upper = pyo.Constraint(model.T, rule=tes_dch_upper)
    else:
        def tes_ch_zero(m, t):
            return m.q_tes_ch[t] == 0.0
        def tes_dch_zero(m, t):
            return m.q_tes_dch[t] == 0.0
        model.c_tes_ch_zero = pyo.Constraint(model.T, rule=tes_ch_zero)
        model.c_tes_dch_zero = pyo.Constraint(model.T, rule=tes_dch_zero)

    # --- [C3] TES SOC-Dynamik ---
    if has_tes:
        def soc_dynamics_rule(m, t):
            if t == 0:
                return pyo.Constraint.Skip
            return (
                m.soc_tes[t]
                == m.soc_tes[t - 1] * (1.0 - sys.tes_loss_per_h)
                + m.q_tes_ch[t] * sys.tes_eta_charge
                - m.q_tes_dch[t] / sys.tes_eta_discharge
            )
        model.c_soc_dynamics = pyo.Constraint(model.T, rule=soc_dynamics_rule)

        def soc_min_rule(m, t):
            return m.soc_tes[t] >= sys.tes_soc_min
        def soc_max_rule(m, t):
            return m.soc_tes[t] <= sys.tes_soc_max
        model.c_soc_min = pyo.Constraint(model.T, rule=soc_min_rule)
        model.c_soc_max = pyo.Constraint(model.T, rule=soc_max_rule)

        # --- [C4] SOC-Initialisierung und Periodizitaet ---
        model.c_soc_init = pyo.Constraint(
            expr=model.soc_tes[0] == soc_init
            + model.q_tes_ch[0] * sys.tes_eta_charge
            - model.q_tes_dch[0] / sys.tes_eta_discharge
        )

        # Periodizitaet nur bei Ganzjahres-Solve (PF: B1/B2); nicht bei Rolling Horizon
        if soc_init_override is None and ops.strategy in ("B1", "B2"):
            model.c_soc_periodicity = pyo.Constraint(
                expr=model.soc_tes[n - 1] >= soc_init
            )
    else:
        def soc_zero(m, t):
            return m.soc_tes[t] == 0.0
        model.c_soc_zero = pyo.Constraint(model.T, rule=soc_zero)

    # --- Zielfunktion ---
    def objective_rule(m):
        return sum(
            (m.p_hp_el[t] + m.p_eb_el[t]) * m.price[t]
            for t in m.T
        )
    model.obj = pyo.Objective(rule=objective_rule, sense=pyo.minimize)

    return model


def _extract_results(
    model: "pyo.ConcreteModel",
    time_index: pd.DatetimeIndex,
    sys: SystemParams,
) -> dict:
    """Extrahiert Pyomo-Variablenwerte in pandas Series."""
    idx = time_index

    p_hp = pd.Series(
        [pyo.value(model.p_hp_el[t]) for t in model.T], index=idx, dtype=float
    )
    p_eb = pd.Series(
        [pyo.value(model.p_eb_el[t]) for t in model.T], index=idx, dtype=float
    )
    cop_arr = np.array([pyo.value(model.cop[t]) for t in model.T])
    q_hp = p_hp * pd.Series(cop_arr, index=idx)
    q_eb = p_eb * sys.eb_eta

    soc = pd.Series(
        [pyo.value(model.soc_tes[t]) for t in model.T], index=idx, dtype=float
    )
    q_ch = pd.Series(
        [pyo.value(model.q_tes_ch[t]) for t in model.T], index=idx, dtype=float
    )
    q_dch = pd.Series(
        [pyo.value(model.q_tes_dch[t]) for t in model.T], index=idx, dtype=float
    )

    p_el_total = p_hp + p_eb
    cost = float((p_el_total * pd.Series(
        [pyo.value(model.price[t]) for t in model.T], index=idx, dtype=float
    )).sum())

    return {
        "p_el_total_mw": p_el_total,
        "p_hp_el_mw": p_hp,
        "p_eb_el_mw": p_eb,
        "q_hp_mwh": q_hp,
        "q_eb_mwh": q_eb,
        "soc_tes_mwh": soc,
        "q_tes_ch_mwh": q_ch,
        "q_tes_dch_mwh": q_dch,
        "cost_eur": cost,
    }


# ---------------------------------------------------------------------------
# Solve-Funktion
# ---------------------------------------------------------------------------

def solve_dispatch(
    net: NetworkParams,
    sys: SystemParams,
    ops: OperationParams,
    horizon: pd.DatetimeIndex,
) -> dict:
    """
    Loest den Dispatch-MILP.

    B1/B2: Einmaliger Solve ueber den gesamten Horizont.
    B3: Rolling Horizon mit rh_horizon_h Fenster und rh_step_h Rollschritt.

    Returns dict mit p_el_total_mw, p_hp_el_mw, p_eb_el_mw, q_hp_mwh, q_eb_mwh,
    soc_tes_mwh, cost_eur, q_demand_mwh, solver_status, solve_time_s.
    """
    if not HAS_PYOMO:
        raise ImportError("Pyomo nicht installiert.")

    solver = SolverFactory("gurobi")
    if not solver.available():
        raise RuntimeError("Gurobi nicht verfuegbar. Bitte Lizenz pruefen.")

    q_demand_aligned = net.q_demand_mwh.reindex(horizon, method="nearest")

    if ops.strategy in ("B1", "B2"):
        return _solve_perfect_foresight(net, sys, ops, horizon, solver)
    else:
        return _solve_rolling_horizon(net, sys, ops, horizon, solver, q_demand_aligned)


def _solve_perfect_foresight(
    net: NetworkParams,
    sys: SystemParams,
    ops: OperationParams,
    horizon: pd.DatetimeIndex,
    solver,
) -> dict:
    """Einmaliger Solve ueber den gesamten Horizont (Perfect Foresight)."""
    t0 = time.perf_counter()
    model = build_l1_model(net, sys, ops, horizon)

    results = solver.solve(
        model,
        options={
            "MIPGap": ops.mip_gap,
            "TimeLimit": ops.time_limit_s,
        },
        tee=False,
    )
    solve_time = time.perf_counter() - t0

    status = _parse_solver_status(results)
    logger.info(
        "PF Solve (%s/%s/%s): %s in %.1fs",
        net.name, sys.config, ops.strategy, status, solve_time,
    )

    data = _extract_results(model, horizon, sys)
    data["q_demand_mwh"] = net.q_demand_mwh.reindex(horizon, method="nearest")
    data["solver_status"] = status
    data["solve_time_s"] = solve_time
    return data


def _solve_rolling_horizon(
    net: NetworkParams,
    sys: SystemParams,
    ops: OperationParams,
    horizon: pd.DatetimeIndex,
    solver,
    q_demand_aligned: pd.Series,
) -> dict:
    """
    Rolling-Horizon Implementierung fuer B3.

    8760 Solver-Calls; nur die erste Stunde je Fenster wird committed.
    SOC wird aus dem letzten committed Schritt uebernommen.
    """
    from tqdm import tqdm

    n_total = len(horizon)
    h_win = ops.rh_horizon_h
    h_step = ops.rh_step_h
    mip_gap_rh = 0.005  # lockerer als PF

    # Ergebnis-Puffer
    p_hp_out = np.zeros(n_total)
    p_eb_out = np.zeros(n_total)
    soc_out = np.zeros(n_total)
    q_ch_out = np.zeros(n_total)
    q_dch_out = np.zeros(n_total)

    current_soc = sys.tes_soc_init
    total_solve_time = 0.0

    steps = range(0, n_total, h_step)
    log_interval = 168  # wöchentlich

    for i, t_start in enumerate(tqdm(steps, desc=f"RH {net.name}/{sys.config}", leave=False)):
        t_end = min(t_start + h_win, n_total)
        win_idx = horizon[t_start:t_end]

        t0 = time.perf_counter()
        model = build_l1_model(net, sys, ops, win_idx, soc_init_override=current_soc)
        res = solver.solve(
            model,
            options={"MIPGap": mip_gap_rh, "TimeLimit": min(ops.time_limit_s, 60)},
            tee=False,
        )
        total_solve_time += time.perf_counter() - t0

        status = _parse_solver_status(res)
        if status not in ("optimal", "feasible"):
            logger.warning("RH Fenster t=%d: Solver-Status %s", t_start, status)

        # Nur erste h_step Stunden committen
        for k in range(min(h_step, t_end - t_start)):
            p_hp_out[t_start + k] = pyo.value(model.p_hp_el[k])
            p_eb_out[t_start + k] = pyo.value(model.p_eb_el[k])
            soc_out[t_start + k] = pyo.value(model.soc_tes[k])
            q_ch_out[t_start + k] = pyo.value(model.q_tes_ch[k])
            q_dch_out[t_start + k] = pyo.value(model.q_tes_dch[k])

        # SOC fuer naechstes Fenster
        current_soc = soc_out[t_start + h_step - 1] if (t_start + h_step) <= n_total else soc_out[t_end - 1]

        if i % log_interval == 0:
            logger.info(
                "RH %s/%s: Woche %d/%d, SOC=%.1f MWh, Ø-Solve=%.2fs",
                net.name, sys.config,
                i // log_interval + 1,
                n_total // (h_step * log_interval) + 1,
                current_soc,
                total_solve_time / max(i + 1, 1),
            )

    cop_arr = compute_cop(
        net.t_outside_c.reindex(horizon, method="nearest").values,
        sys.hp_cop_rated, sys.hp_t_ref_c, sys.hp_cop_min,
    )

    p_hp = pd.Series(p_hp_out, index=horizon)
    p_eb = pd.Series(p_eb_out, index=horizon)
    soc = pd.Series(soc_out, index=horizon)

    if ops.strategy == "B1":
        price_arr = np.full(n_total, ops.price_fixed)
    else:
        price_arr = ops.prices_eur_mwh.reindex(horizon, method="nearest").values

    cost = float(((p_hp + p_eb) * pd.Series(price_arr, index=horizon)).sum())

    logger.info(
        "RH abgeschlossen (%s/%s/B3): Kosten=%.0f EUR, Ø-Solve=%.3fs",
        net.name, sys.config, cost, total_solve_time / n_total,
    )

    return {
        "p_el_total_mw": p_hp + p_eb,
        "p_hp_el_mw": p_hp,
        "p_eb_el_mw": p_eb,
        "q_hp_mwh": p_hp * pd.Series(cop_arr, index=horizon),
        "q_eb_mwh": p_eb * sys.eb_eta,
        "soc_tes_mwh": soc,
        "q_tes_ch_mwh": pd.Series(q_ch_out, index=horizon),
        "q_tes_dch_mwh": pd.Series(q_dch_out, index=horizon),
        "cost_eur": cost,
        "q_demand_mwh": net.q_demand_mwh.reindex(horizon, method="nearest"),
        "solver_status": "feasible",
        "solve_time_s": total_solve_time,
    }


def _parse_solver_status(results) -> str:
    """Gibt 'optimal', 'feasible' oder 'infeasible' zurueck."""
    tc = results.solver.termination_condition
    if tc == TerminationCondition.optimal:
        return "optimal"
    if tc in (
        TerminationCondition.maxTimeLimit,
        TerminationCondition.maxIterations,
        TerminationCondition.feasible,
    ):
        return "feasible"
    return "infeasible"


# ---------------------------------------------------------------------------
# Qualitaetspruefungen
# ---------------------------------------------------------------------------

def validate_run_output(
    result: dict,
    net: NetworkParams,
    sys: SystemParams,
) -> None:
    """
    Pflichtchecks nach jedem Solver-Run.

    Wirft ValueError bei Fehlschlag.
    """
    q_supply = (result["q_hp_mwh"] + result["q_eb_mwh"]
                + result["q_tes_dch_mwh"] - result["q_tes_ch_mwh"])
    q_demand = result["q_demand_mwh"]

    q_sum = float(q_demand.sum())
    if q_sum <= 0:
        raise ValueError(f"[{net.name}/{sys.config}] q_demand Summe ist 0 oder negativ")

    # CHECK 1: Energiebilanz
    balance_err = abs(float(q_supply.sum()) - q_sum) / q_sum
    if balance_err >= 0.001:
        raise ValueError(
            f"[{net.name}/{sys.config}] CHECK 1 FAIL: Energiebilanzfehler {balance_err:.4%} >= 0.1%"
        )
    logger.info("[%s/%s] CHECK 1 OK: Energiebilanz %.4f%%", net.name, sys.config, balance_err * 100)

    # CHECK 2: Kapazitaetsgrenzen
    cop_min_val = sys.hp_cop_min
    hp_el_max_theoretical = sys.hp_cap_mw / cop_min_val * 1.001
    hp_el_actual_max = float(result["p_hp_el_mw"].max())
    if hp_el_actual_max > hp_el_max_theoretical:
        raise ValueError(
            f"[{net.name}/{sys.config}] CHECK 2 FAIL: p_hp_el.max()={hp_el_actual_max:.3f} > "
            f"hp_cap/COP_min={hp_el_max_theoretical:.3f}"
        )
    if sys.eb_cap_mw > 0.0:
        eb_max = float(result["p_eb_el_mw"].max())
        if eb_max > sys.eb_cap_mw * 1.001:
            raise ValueError(
                f"[{net.name}/{sys.config}] CHECK 2 FAIL: p_eb_el.max()={eb_max:.3f} > "
                f"eb_cap={sys.eb_cap_mw:.3f}"
            )
    logger.info("[%s/%s] CHECK 2 OK: Kapazitaetsgrenzen eingehalten", net.name, sys.config)

    # CHECK 3: SOC-Grenzen (S2)
    if sys.tes_cap_mwh > 0.0:
        soc = result["soc_tes_mwh"]
        soc_min_actual = float(soc.min())
        soc_max_actual = float(soc.max())
        if soc_min_actual < sys.tes_soc_min - 0.01:
            raise ValueError(
                f"[{net.name}/{sys.config}] CHECK 3 FAIL: SOC.min={soc_min_actual:.3f} < "
                f"soc_min={sys.tes_soc_min:.3f}"
            )
        if soc_max_actual > sys.tes_soc_max + 0.01:
            raise ValueError(
                f"[{net.name}/{sys.config}] CHECK 3 FAIL: SOC.max={soc_max_actual:.3f} > "
                f"soc_max={sys.tes_soc_max:.3f}"
            )
        logger.info("[%s/%s] CHECK 3 OK: SOC-Grenzen eingehalten", net.name, sys.config)

        # CHECK 4: Jahresperiodizitaet (nur PF: B1/B2)
        strategy = result.get("strategy", "")
        if strategy in ("B1", "B2"):
            soc_start = float(soc.iloc[0])
            soc_end = float(soc.iloc[-1])
            periodicity_err = abs(soc_end - soc_start) / sys.tes_cap_mwh
            if periodicity_err >= 0.05:
                raise ValueError(
                    f"[{net.name}/{sys.config}] CHECK 4 FAIL: SOC-Jahresperiodizitaet "
                    f"{periodicity_err:.3%} >= 5%"
                )
            logger.info("[%s/%s] CHECK 4 OK: Jahresperiodizitaet %.2f%%", net.name, sys.config, periodicity_err * 100)

    # CHECK 5: Solver-Status
    status = result.get("solver_status", "unknown")
    if status not in ("optimal", "feasible"):
        raise ValueError(
            f"[{net.name}/{sys.config}] CHECK 5 FAIL: Solver-Status '{status}'"
        )
    logger.info("[%s/%s] CHECK 5 OK: Solver-Status '%s'", net.name, sys.config, status)
    logger.info("[%s/%s] Alle Qualitaetspruefungen bestanden.", net.name, sys.config)
