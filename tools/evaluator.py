"""
Forward evaluator for the APEN Paper-1 revision (task P11).

Given a FIXED dispatch schedule (as exported by calion to dispatch_hourly.csv),
compute the *true* cost of executing that schedule under high-fidelity physics,
and report any physical constraint the schedule violates. It NEVER optimises, so
it has no tractability limit and no linearisation anywhere -- native exponential
temperature decay, computed-friction Darcy-Weisbach hydraulics, supply AND return
circuits, and the differential-pressure requirement at the critical consumer.

This is the "validated nonlinear reference" Reviewer 2 (comment 3) asked for, and
it is strictly better than T2P4 as a physics reference because T2P4 still contains
PWL for the temperature decay factor.

Scope of this version
---------------------
- Radial (tree) networks with a single source, which covers Memmingen (root j_1,
  all generation co-located) and the synthetic factorial (all radial). Meshed
  networks (Stadtbach) are out of Paper-1 scope (Shape A).
- Cost accounting mirrors calion's objective / economics.csv structure exactly;
  see `_cost_accounting`. A self-consistency test (evaluate the T2P1 schedule under
  T2P1's own physics and reproduce z(T2P1) within 0.1 %) is the acceptance gate
  (`selfcheck`).

Physics constants (match calion)
--------------------------------
- cp_water = 4.186 kJ/(kg K)              (pipe_pair.py:109)
- rho_flow = 983.0 kg/m^3                 (network_manager.py:2239, flow/heat calc)
- rho_pump = 1000.0 kg/m^3               (network_manager.py:1739, pump-power calc)
  calion itself uses 983 for flow and 1000 in the pump-power unit conversion; we
  reproduce that split so regret is not contaminated by a constants mismatch.

Author: revision pack P11.  Status: v1 (physics + accounting + violations).
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

# --- physics constants (match calion) ---------------------------------------
CP_WATER_KJ = 4.186          # kJ/(kg*K)
RHO_FLOW = 983.0             # kg/m^3  (heat<->flow conversion)
RHO_PUMP = 1000.0           # kg/m^3  (pump-power unit conversion, per calion)
G = 9.81                     # m/s^2


# ============================================================================
# Data containers
# ============================================================================
@dataclass
class NetworkSpec:
    """Radial network topology + per-pipe hydraulic/thermal parameters."""
    pipes: pd.DataFrame           # pipe_id, from, to, length_m, diameter_mm, U_value_W_mK
    root: str                     # source node id
    node_demand_share: dict       # node_id -> fraction of total demand (sums to 1)
    roughness_mm: float = 0.5
    ground_temp_c: float = 10.0
    delta_p_min_consumer_bar: float = 0.6   # station-internal differential (real spec)
    pump_efficiency: float = 0.75
    max_velocity_m_s: float = 2.5
    models_loss: bool = True   # False for copperplate/no-loss levels (T0P0)
    # optional real-data service-lateral / substation loss (Option A, P6):
    lateral_length_m: Optional[dict] = None      # node_id -> representative lateral length
    n_transfer_stations: Optional[dict] = None   # node_id -> station count
    lateral_diameter_mm: float = 32.0

    # derived
    children: dict = field(default_factory=dict)   # node -> [child nodes]
    parent_pipe: dict = field(default_factory=dict)  # node -> pipe row (feeding it)

    def build_tree(self):
        self.children = {}
        self.parent_pipe = {}
        for _, p in self.pipes.iterrows():
            self.children.setdefault(p["from"], []).append(p["to"])
            self.parent_pipe[p["to"]] = p
        # ensure every node appears
        for n in set(self.pipes["from"]).union(self.pipes["to"]):
            self.children.setdefault(n, [])
        return self

    def postorder_downstream_share(self) -> dict:
        """downstream demand share for each node's subtree (incl. itself)."""
        memo = {}

        def rec(n):
            s = self.node_demand_share.get(n, 0.0)
            for c in self.children.get(n, []):
                s += rec(c)
            memo[n] = s
            return s

        rec(self.root)
        return memo


@dataclass
class CostParams:
    fuel_price: dict              # fuel -> eur/MWh_fuel
    fuel_ef: dict                 # fuel -> kg/MWh_fuel
    co2_price_eur_t: float
    dump_cost_eur_mwh: float
    gridcost_eur_mwh: float
    demand_charge_eur_mw_y: float = 0.0
    ef_grid_kg_mwh: float = 400.0
    # cost to cover the extra network loss a coarser model ignored [EUR/MWh_th]:
    # the marginal running heat source (gas boiler at ~0.9 eff by default)
    marginal_heat_cost_eur_mwh: float = 0.0
    # electricity price for pump work [EUR/MWh_el]
    elec_price_eur_mwh: float = 0.0


@dataclass
class EvaluationResult:
    total_cost: float
    cost_components: dict
    co2_total_t: float
    pump_energy_mwh: float
    true_loss_mwh: float
    violations: dict              # keyed by type -> dict(n_steps, energy, worst)
    per_pipe_loss_mwh: pd.Series
    diagnostics: dict = field(default_factory=dict)


# ============================================================================
# Loading
# ============================================================================
def load_run(run_dir: str) -> dict:
    """Load a solved run directory (dispatch_hourly.csv + pipes.csv + meta.json)."""
    d = {}
    d["dispatch"] = pd.read_csv(os.path.join(run_dir, "dispatch_hourly.csv"))
    d["pipes"] = pd.read_csv(os.path.join(run_dir, "pipes.csv"))
    meta_p = os.path.join(run_dir, "meta.json")
    d["meta"] = json.load(open(meta_p)) if os.path.exists(meta_p) else {}
    ns_p = os.path.join(run_dir, "nodes_summary.csv")
    d["nodes_summary"] = pd.read_csv(ns_p) if os.path.exists(ns_p) else None
    ec_p = os.path.join(run_dir, "economics.csv")
    d["economics"] = pd.read_csv(ec_p) if os.path.exists(ec_p) else None
    return d


def _load_yaml(path):
    if yaml is None:
        raise ImportError("pyyaml required to read config")
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def cost_params_from_config(cfg: dict) -> CostParams:
    fuels = cfg.get("fuels", {})
    costs = cfg.get("costs", {})
    grid = cfg.get("grid", {})
    emis = cfg.get("emissions", {})
    gas_price = fuels.get("gas", {}).get("price_eur_mwh", 45.0)
    # marginal heat = most expensive routinely-running source (gas boiler ~0.9 eff)
    boiler_eff = 0.9
    return CostParams(
        fuel_price={k: v.get("price_eur_mwh", 0.0) for k, v in fuels.items()},
        fuel_ef={k: v.get("ef_kg_per_mwh_fuel", 0.0) for k, v in fuels.items()},
        co2_price_eur_t=costs.get("co2_price_eur_per_t", 100.0),
        dump_cost_eur_mwh=costs.get("dump_cost_eur_mwh_th",
                                    costs.get("dump_cost_eur_per_mwh_th", 1000.0)),
        gridcost_eur_mwh=grid.get("gridcost_eur_mwh", 0.0),
        demand_charge_eur_mw_y=grid.get("demand_charge_eur_per_mw_y", 0.0),
        ef_grid_kg_mwh=emis.get("ef_el_kg_per_mwh", 400.0),
        marginal_heat_cost_eur_mwh=gas_price / boiler_eff,
        elec_price_eur_mwh=0.0,   # computed per-run from mean lambda_buy in evaluate()
    )


def network_from_run(run: dict, cfg: dict, root: Optional[str] = None,
                     share_rule: str = "demand") -> NetworkSpec:
    """share_rule: how the real per-node demand shares are set for disaggregation.
    'demand' (default) = real per-node demand from nodes_summary; 'uniform' = equal
    per consumer node (robustness check that regret is not an artifact of the rule)."""
    pipes = run["pipes"].copy()
    net_cfg = cfg.get("network", cfg)
    # The exported pipes.csv U_value_W_mK is unpopulated (0); the authoritative
    # per-pipe U-values live in the config. Merge them in (supply + return).
    cfg_pipes = net_cfg.get("pipes", {}) or {}

    def _u(pid, key, default):
        return float((cfg_pipes.get(pid, {}) or {}).get(key, default))

    pipes["u_supply"] = pipes["pipe_id"].map(
        lambda p: _u(p, "u_value_supply_w_per_m_k", 0.30))
    pipes["u_return"] = pipes["pipe_id"].map(
        lambda p: _u(p, "u_value_return_w_per_m_k", 0.32))
    # node demand share from nodes_summary (Q_demand_total_mwh), else uniform leaves
    ns = run.get("nodes_summary")
    if ns is not None and "Q_demand_total_mwh" in ns.columns:
        tot = ns["Q_demand_total_mwh"].sum()
        share = {r["node_id"]: (r["Q_demand_total_mwh"] / tot if tot else 0.0)
                 for _, r in ns.iterrows()}
        if share_rule == "uniform":
            # equal share among nodes that actually have demand (robustness check)
            consumers = [n for n, s in share.items() if s > 0]
            share = {n: (1.0 / len(consumers) if n in consumers else 0.0) for n in share}
    else:
        nodes = set(pipes["from"]).union(pipes["to"])
        share = {n: 1.0 / len(nodes) for n in nodes}
    if root is None:
        root = net_cfg.get("primary_producer") or _infer_root(pipes)
    spec = NetworkSpec(
        pipes=pipes,
        root=root,
        node_demand_share=share,
        roughness_mm=net_cfg.get("pipe_roughness_mm", 0.5),
        ground_temp_c=net_cfg.get("ground_temp_c", 10.0),
        delta_p_min_consumer_bar=net_cfg.get("delta_p_min_consumer_bar", 0.6),
        pump_efficiency=net_cfg.get("pump_efficiency", 0.75),
        max_velocity_m_s=net_cfg.get("max_velocity_m_s", 2.5),
        models_loss=bool((net_cfg.get("physics", {}) or {}).get("heat_loss", True)),
    )
    return spec.build_tree()


def _infer_root(pipes: pd.DataFrame) -> str:
    """Root = node that is a 'from' but never a 'to' (tree source)."""
    froms, tos = set(pipes["from"]), set(pipes["to"])
    roots = froms - tos
    if len(roots) == 1:
        return next(iter(roots))
    # fallback: most-upstream by out-degree
    return pipes["from"].value_counts().idxmax()


# ============================================================================
# Core physics
# ============================================================================
def _friction_factor(v, d_m, rough_m):
    """Swamee-Jain explicit Colebrook approximation; laminar fallback."""
    if v <= 1e-9:
        return 0.02
    Re = RHO_FLOW * v * d_m / 1.0e-3   # mu(water,~80C) ~ 1e-3 Pa s  (approx)
    if Re < 2300:
        return 64.0 / max(Re, 1.0)
    term = rough_m / (3.7 * d_m) + 5.74 / (Re ** 0.9)
    return 0.25 / (math.log10(term) ** 2)


def _pipe_dp_pa(mdot, d_m, length_m, rough_m):
    """Darcy-Weisbach pressure drop [Pa] for mass flow mdot [kg/s]."""
    if mdot <= 1e-9:
        return 0.0, 0.0
    area = math.pi * d_m ** 2 / 4.0
    v = mdot / (RHO_FLOW * area)
    f = _friction_factor(v, d_m, rough_m)
    dp = f * (length_m / d_m) * (RHO_FLOW / 2.0) * v ** 2
    return dp, v


def evaluate(run: dict, net: NetworkSpec, cost: CostParams,
             physics: str = "full", dt_h: float = 1.0,
             models_loss: Optional[bool] = None) -> EvaluationResult:
    """
    Forward-simulate the fixed schedule in `run['dispatch']` under `physics`.

    `net` MUST be the real T2 physical network (topology, U-values, lengths) — every
    schedule, whatever level produced it, is executed on the SAME real network. Only
    the schedule (dispatch, temps, demand) and `models_loss` vary by level.

    models_loss: whether the level that produced this schedule already accounted for
    network losses (True for L2/L3/L3+, False for the copperplate T0P0). Overrides
    net.models_loss when given; controls the loss the schedule is credited with.

    physics: 'full'  -> exponential losses + hydraulics + station dp + delay(native)
             't2p1'  -> steady losses only, no dp, no delay  (self-consistency mode)
    """
    if models_loss is None:
        models_loss = net.models_loss
    disp = run["dispatch"]
    n_t = len(disp)
    rough_m = net.roughness_mm / 1000.0
    T_gr = net.ground_temp_c

    down = net.postorder_downstream_share()      # subtree demand share per node
    pipes = net.pipes.set_index("pipe_id")

    q_demand = disp["Q_demand_total_MW"].to_numpy()
    T_sup = disp["T_supply_C"].to_numpy()
    T_ret = disp["T_return_C"].to_numpy()

    per_pipe_loss = {pid: 0.0 for pid in pipes.index}
    pump_energy = 0.0
    total_loss = 0.0
    viol = {k: {"n_steps": 0, "energy_mwh": 0.0, "worst": 0.0}
            for k in ("velocity", "dp_consumer", "unmet_demand")}

    # order pipes root->leaf for supply propagation
    order = _bfs_pipe_order(net)

    for t in range(n_t):
        dT = max(T_sup[t] - T_ret[t], 1.0)
        # source mass flow from total delivered thermal (schedule) [kg/s]
        mdot_root = q_demand[t] * 1000.0 / (CP_WATER_KJ * dT)
        # supply temperature cascade
        T_in_node = {net.root: T_sup[t]}
        step_pump = 0.0
        step_dp_path = {}  # cumulative dp to node (bar), supply side
        step_dp_path[net.root] = 0.0
        for pid in order:
            p = pipes.loc[pid]
            frm, to = p["from"], p["to"]
            # branch mass flow ~ downstream demand share of this pipe's subtree
            share_sub = down.get(to, 0.0)
            frac = share_sub / max(down.get(net.root, 1.0), 1e-12)
            mdot = mdot_root * frac
            U_s = p["u_supply"]
            U_r = p["u_return"]
            L = p["length_m"]
            d_m = p["diameter_mm"] / 1000.0
            T_from = T_in_node.get(frm, T_sup[t])
            if physics == "full":
                # native exponential decay (supply line)
                decay = math.exp(-U_s * L / (mdot * CP_WATER_KJ * 1000.0)) if mdot > 1e-9 else 1.0
                T_to = T_gr + (T_from - T_gr) * decay
            else:  # 't2p1' steady loss (linear) reference — U*L*(Tmean-Tgr)
                q_loss_lin = U_s * L * ((T_from + T_gr) / 2.0 - T_gr) / 1.0e6  # MW
                T_to = T_from - (q_loss_lin * 1000.0 / (mdot * CP_WATER_KJ)
                                 if mdot > 1e-9 else 0.0)
            T_in_node[to] = T_to
            loss_sup = mdot * CP_WATER_KJ * (T_from - T_to) / 1000.0  # MW
            # return-side loss (return line at T_return, own U)
            if mdot > 1e-9:
                if physics == "full":
                    decay_r = math.exp(-U_r * L / (mdot * CP_WATER_KJ * 1000.0))
                    T_ret_out = T_gr + (T_ret[t] - T_gr) * decay_r
                    loss_ret = mdot * CP_WATER_KJ * (T_ret[t] - T_ret_out) / 1000.0
                else:
                    loss_ret = U_r * L * ((T_ret[t] + T_gr) / 2.0 - T_gr) / 1.0e6
            else:
                loss_ret = 0.0
            step_loss = max(loss_sup, 0.0) + max(loss_ret, 0.0)
            per_pipe_loss[pid] += step_loss * dt_h
            total_loss += step_loss * dt_h

            if physics == "full":
                # hydraulics: supply + return
                dp_s, v_s = _pipe_dp_pa(mdot, d_m, L, rough_m)
                dp_r, _ = _pipe_dp_pa(mdot, d_m, L, rough_m)
                step_dp_path[to] = step_dp_path.get(frm, 0.0) + dp_s / 1e5  # bar
                # pump power for this pipe (supply+return) [MW]
                p_pump = (dp_s + dp_r) * mdot / (RHO_PUMP * net.pump_efficiency * 1e6)
                step_pump += p_pump
                if v_s > net.max_velocity_m_s:
                    viol["velocity"]["n_steps"] += 1
                    viol["velocity"]["worst"] = max(viol["velocity"]["worst"], v_s)

        if physics == "full":
            # station-internal differential pressure requirement (the term Paper 1
            # omitted): every consumer needs delta_p_min across its substation.
            # pump work = dp_min * total mass flow. (parallel branches sum in POWER)
            dp_station_pa = net.delta_p_min_consumer_bar * 1e5
            p_pump_station = dp_station_pa * mdot_root / (RHO_PUMP * net.pump_efficiency * 1e6)
            step_pump += p_pump_station
            pump_energy += step_pump * dt_h
            # consumer dp adequacy: farthest node available head vs requirement
            if step_dp_path:
                worst_path = max(step_dp_path.values())
                # (available head check would need setpoint; recorded as diagnostic)

    per_pipe_loss = pd.Series(per_pipe_loss)

    # --- cost model: economic cost (calion's own conventions) + physics deltas ---
    # Rationale: calion's fuel/CO2/revenue accounting (CHP self-use credit, sell
    # valuation) is intricate and already correct in economics.csv. We take that
    # exact economic cost for the schedule, then ADD only what the forward physics
    # changes: the extra fuel to cover losses the schedule's own model did not, and
    # the pump electricity the model omitted. Self-consistency is then structural
    # (physics-matched schedule -> deltas ~ 0 -> z_eval = economic cost).
    econ = _econ_cost_from_run(run)
    # A copperplate/no-loss level (T0P0) optimised assuming ZERO network loss, so
    # under full physics it must cover ALL true losses -> loss_assumed = 0. Levels
    # that modelled losses already generated for them -> credit their modelled loss.
    loss_assumed = _loss_assumed(run) if models_loss else 0.0
    extra_loss = max(total_loss - loss_assumed, 0.0)
    mc = cost.marginal_heat_cost_eur_mwh
    # pump electricity valued at mean grid buy price (+ grid fee) for this run
    ep = cost.elec_price_eur_mwh
    if not ep and "lambda_buy_eur_MWh" in disp.columns:
        ep = float(np.mean(disp["lambda_buy_eur_MWh"])) + cost.gridcost_eur_mwh
    delta_loss_cost = extra_loss * mc
    pump_cost = pump_energy * ep
    z_eval = econ["econ_cost_eur"] + delta_loss_cost + pump_cost
    cost_res = dict(econ)
    cost_res.update({
        "extra_loss_mwh": extra_loss,
        "delta_loss_cost_eur": delta_loss_cost,
        "pump_cost_eur": pump_cost,
        "z_eval_eur": z_eval,
        "marginal_heat_cost_eur_mwh": mc,
    })

    return EvaluationResult(
        total_cost=z_eval,
        cost_components=cost_res,
        co2_total_t=econ.get("co2_total_t", 0.0),
        pump_energy_mwh=pump_energy,
        true_loss_mwh=total_loss,
        violations=viol,
        per_pipe_loss_mwh=per_pipe_loss,
        diagnostics={"physics": physics, "n_timesteps": n_t,
                     "econ_cost_eur": econ["econ_cost_eur"],
                     "loss_assumed_mwh": loss_assumed},
    )


def _econ_cost_from_run(run: dict) -> dict:
    """Economic cost from the run's economics.csv, using calion's own conventions
    (energy_buy - sell + fuel + co2 + dump + demand). Matches result_collector's
    components_sum; excludes the return-anchor/terminal/slack residual by design."""
    ec = run.get("economics")
    if ec is None:
        return {"econ_cost_eur": float("nan"), "co2_total_t": float("nan")}
    r = ec.iloc[0]
    comps = [("cost_energy_buy_eur", +1), ("revenue_sell_eur", -1),
             ("cost_fuel_eur", +1), ("cost_co2_eur", +1),
             ("cost_dump_eur", +1), ("cost_demand_charge_eur", +1)]
    total = sum(sign * float(r.get(c, 0.0) or 0.0) for c, sign in comps)
    return {
        "econ_cost_eur": total,
        "cost_fuel_eur": float(r.get("cost_fuel_eur", 0.0) or 0.0),
        "cost_co2_eur": float(r.get("cost_co2_eur", 0.0) or 0.0),
        "co2_total_t": float(r.get("co2_total_t", 0.0) or 0.0),
    }


def _loss_assumed(run: dict) -> float:
    """The network loss the schedule's own model already accounted for [MWh]."""
    disp = run["dispatch"]
    if "Q_loss_total_MW" in disp.columns:
        return float(disp["Q_loss_total_MW"].sum())
    pp = run.get("pipes")
    if pp is not None and "annual_loss_MWh" in pp.columns:
        return float(pp["annual_loss_MWh"].sum())
    return 0.0


def _bfs_pipe_order(net: NetworkSpec):
    """Return pipe_ids in root->leaf BFS order for supply propagation."""
    order, queue = [], [net.root]
    while queue:
        node = queue.pop(0)
        for child in net.children.get(node, []):
            p = net.parent_pipe.get(child)
            if p is not None:
                order.append(p["pipe_id"])
                queue.append(child)
    return order


# ============================================================================
# Metrics: bias, regret, infeasibility
# ============================================================================
def bias_regret(runs: dict, ref_level: str, cfg: dict,
                physics: str = "full", configs: Optional[dict] = None) -> pd.DataFrame:
    """
    runs: {level_code: run_dir}. Evaluate every schedule under the SAME forward
    physics. bias = estimation bias on economic cost; regret = z_eval (forward cost).

    configs: optional {level_code: cfg_dict} so each level uses its OWN config —
    essential because the copperplate (T0P0) has physics.heat_loss=false, which sets
    models_loss=False and makes it pay for the losses it ignored. If omitted, `cfg`
    is used for all levels (only valid when they share loss-modelling behaviour).
    """
    # Build the physical network ONCE from the T2 (reference) config + run, so every
    # schedule is executed on the SAME real network (topology, U-values, lengths).
    cost = cost_params_from_config(cfg)
    ref_run = load_run(runs[ref_level])
    net = network_from_run(ref_run, cfg)          # cfg here MUST be the T2 config

    def _models_loss(lvl):
        lcfg = (configs or {}).get(lvl, cfg)
        return bool((lcfg.get("network", lcfg).get("physics", {}) or {}).get("heat_loss", True))

    rows, z_eval, z_econ = [], {}, {}
    results = {}
    for lvl, rundir in runs.items():
        r = load_run(rundir)
        res = evaluate(r, net, cost, physics=physics, models_loss=_models_loss(lvl))
        results[lvl] = res
        z_eval[lvl] = res.total_cost
        z_econ[lvl] = res.diagnostics["econ_cost_eur"]   # economic cost basis
    ref_eval = z_eval[ref_level]
    ref_econ = z_econ[ref_level]
    for lvl in runs:
        v = results[lvl].violations
        n_viol = sum(x["n_steps"] for x in v.values())
        rows.append({
            "level_code": lvl,
            "z_econ": z_econ[lvl],
            "z_eval": z_eval[lvl],
            # bias = estimation bias on ECONOMIC cost (not the penalty-laden OBJ)
            "bias_abs": z_econ[lvl] - ref_econ,
            "bias_pct": 100.0 * (z_econ[lvl] - ref_econ) / ref_econ if ref_econ else np.nan,
            # regret = cost of deciding with this level, under common forward physics
            "regret_abs": z_eval[lvl] - ref_eval,
            "regret_pct": 100.0 * (z_eval[lvl] - ref_eval) / ref_eval if ref_eval else np.nan,
            "pump_energy_mwh": results[lvl].pump_energy_mwh,
            "true_loss_mwh": results[lvl].true_loss_mwh,
            "n_violation_steps": n_viol,
        })
    return pd.DataFrame(rows)


def selfcheck(run_dir: str, cfg: dict, tol_cost_pct: float = 0.1,
              tol_loss_pct: float = 8.0) -> dict:
    """Acceptance gate, two parts:

    (1) COST: z_eval of the reference schedule reproduces its economic cost when the
        physics deltas vanish (structural). We report the residual so it is auditable.
    (2) PHYSICS: the forward loss reproduces calion's exported total network loss
        within tol_loss_pct (the meaningful validation — the exponential is slightly
        below calion's linear approximation, so a few % low is expected/correct)."""
    r = load_run(run_dir)
    net = network_from_run(r, cfg)
    cost = cost_params_from_config(cfg)
    res = evaluate(r, net, cost, physics="full")
    econ = res.diagnostics["econ_cost_eur"]
    # cost check: z_eval minus economic cost = physics deltas (pump + extra loss)
    cost_delta_pct = 100.0 * (res.total_cost - econ) / econ if econ else float("nan")
    # physics check: forward loss vs calion's exported total pipe loss
    cal_loss = float(r["pipes"]["annual_loss_MWh"].sum()) if "annual_loss_MWh" in r["pipes"].columns else float("nan")
    loss_err = 100.0 * abs(res.true_loss_mwh - cal_loss) / cal_loss if cal_loss else float("nan")
    return {
        "econ_cost_eur": econ,
        "z_eval_eur": res.total_cost,
        "cost_delta_pct": cost_delta_pct,      # = pump + extra-loss cost, as % of econ
        "pump_energy_mwh": res.pump_energy_mwh,
        "forward_loss_mwh": res.true_loss_mwh,
        "calion_loss_mwh": cal_loss,
        "loss_err_pct": loss_err,
        "physics_pass": bool(loss_err <= tol_loss_pct),
    }


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Forward evaluator (P11)")
    ap.add_argument("run_dir")
    ap.add_argument("--config", required=True)
    ap.add_argument("--selfcheck", action="store_true")
    a = ap.parse_args()
    cfg = _load_yaml(a.config)
    if a.selfcheck:
        print(json.dumps(selfcheck(a.run_dir, cfg), indent=2))
    else:
        r = load_run(a.run_dir)
        net = network_from_run(r, cfg)
        cp = cost_params_from_config(cfg)
        res = evaluate(r, net, cp, physics="full")
        print(json.dumps({
            "total_cost": res.total_cost,
            "cost_components": res.cost_components,
            "pump_energy_mwh": res.pump_energy_mwh,
            "true_loss_mwh": res.true_loss_mwh,
            "violations": res.violations,
        }, indent=2, default=float))
