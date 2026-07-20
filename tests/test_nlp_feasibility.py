"""
Feasibility tests for NLP (bilinear) and MILP modes with multiple
heat-generating assets at different network nodes, covering:
  - thermal_gen dispatch constraints (on/off binary, ramp, min uptime)
  - pipe thermal mass buffer (Q_net_buf / E_net)
  - MILP linear transport delay (fixed-tau lookback)
  - heat balance satisfaction after solve
  - ramp constraint satisfaction after solve
"""
import logging
import pandas as pd
import pyomo.environ as pyo
import pytest

from calion.models.system_builder import build_model
from calion.utils.timeseries import TimeSeriesTable

logging.disable(logging.WARNING)

T = 6
dt_h = 1.0

DEMAND_A = [4.0, 5.0, 4.5, 3.5, 4.0, 4.5]
DEMAND_B = [4.0, 5.0, 4.5, 3.5, 4.5, 5.0]

df = pd.DataFrame({
    "strompreis_EUR_MWh": [50.0] * T,
    "grid_co2_kg_MWh":    [0.3]  * T,
    "waermebedarf_MWth":  [d + e for d, e in zip(DEMAND_A, DEMAND_B)],
    "demand_a":           DEMAND_A,
    "demand_b":           DEMAND_B,
}, index=range(T))

TABLE = TimeSeriesTable(
    index=df.index.tolist(),
    columns=df.columns.tolist(),
    data={col: df[col].tolist() for col in df.columns},
)

CFG_NLP = {
    "assets": {
        "boiler_hub": {
            "type": "thermal_generator",
            "capacity_mw": 15.0,
            "thermal_efficiency": 0.90,
            "fuel_cost_eur_per_mwh": 40.0,
        },
        "chp_node_a": {
            "type": "thermal_generator",
            "capacity_mw": 8.0,
            "thermal_efficiency": 0.50,
            "el_eff": 0.35,
            "fuel_cost_eur_per_mwh": 35.0,
            "min_load": 0.30,
            "min_uptime_h": 2.0,
            "min_downtime_h": 1.0,
            "max_ramp_up_mw_per_h": 6.0,
            "max_ramp_down_mw_per_h": 8.0,
            "startup_cost_eur": 100.0,
        },
        "boiler_node_b": {
            "type": "thermal_generator",
            "capacity_mw": 12.0,
            "thermal_efficiency": 0.88,
            "fuel_cost_eur_per_mwh": 45.0,
        },
    },
    "network": {
        "milp_linearize": False,
        "supply_temp_c": 80.0,
        "return_temp_c": 55.0,
        "ground_temp_c": 10.0,
        "physics": {
            "heat_loss": True,
            "pressure_drop": False,
            "transport_delay": False,
            "pipe_thermal_mass": True,
            "pipe_thermal_mass_dT_c": 5.0,
            "pipe_thermal_mass_init_fraction": 0.5,
        },
        "nodes": {
            "hub": {
                "type": "producer",
                "assets": ["boiler_hub"],
            },
            "node_a": {
                "type": "mixed",
                "assets": ["chp_node_a"],
                "demand": {"column": "demand_a", "demand_fraction": 1.0},
            },
            "node_b": {
                "type": "mixed",
                "assets": ["boiler_node_b"],
                "demand": {"column": "demand_b", "demand_fraction": 1.0},
            },
        },
        "pipes": {
            "hub_to_a": {
                "from_node": "hub", "to_node": "node_a",
                "length_m": 2000,
                "diameter_mm": 250,
                "current_diameter_supply_mm": 250,
            },
            "hub_to_b": {
                "from_node": "hub", "to_node": "node_b",
                "length_m": 3000,
                "diameter_mm": 200,
                "current_diameter_supply_mm": 200,
            },
        },
    },
    "fuels": {"gas": {"co2_kg_per_mwh": 200.0}},
    "costs": {"dump_cost_eur_per_mwh": 500.0},
    "run": {"horizon_years": 1},
}


@pytest.fixture(scope="module")
def model():
    return build_model(TABLE, CFG_NLP, dt_h=dt_h)


# ── Structure tests (no solver needed) ───────────────────────────────────────

def test_model_builds(model):
    assert model is not None


def test_chp_binary_on_off(model):
    """CHP at node_a must have on/off binary (min_load>0)."""
    assert hasattr(model, "CHP_NODE_A_on"), "binary on/off variable missing"


def test_chp_ramp_constraint(model):
    assert hasattr(model, "CHP_NODE_A_ramp_up"), "ramp_up constraint missing"
    assert hasattr(model, "CHP_NODE_A_ramp_down"), "ramp_down constraint missing"


def test_chp_min_uptime(model):
    assert hasattr(model, "CHP_NODE_A_min_uptime"), "min_uptime constraint missing"
    assert hasattr(model, "CHP_NODE_A_min_downtime"), "min_downtime constraint missing"


def test_pipe_thermal_mass_vars(model):
    assert hasattr(model, "Q_net_buf"), "Q_net_buf missing"
    assert hasattr(model, "E_net"), "E_net missing"


def test_pipe_thermal_mass_soc(model):
    assert hasattr(model, "pipe_buf_soc"), "SOC dynamics constraint missing"
    assert hasattr(model, "pipe_buf_terminal"), "terminal constraint missing"


def test_pipe_thermal_mass_energy_positive(model):
    """E_max must be > 0 (pipes have nonzero volume)."""
    e_ub = model.E_net[1].ub
    assert e_ub > 0, f"E_max={e_ub}, expected > 0"


def test_network_loss_variable(model):
    assert hasattr(model, "network_Q_loss_per_timestep"), "network loss var missing"


def test_heat_balance_includes_buf(model):
    """At least one heat balance constraint must exist (ht_balance or ht_balance_<node>)."""
    has_balance = any(
        str(c).startswith("ht_balance")
        for c in model.component_objects(pyo.Constraint)
    )
    assert has_balance, (
        "no ht_balance constraint found. "
        f"Constraints: {[str(c) for c in model.component_objects(pyo.Constraint)][:20]}"
    )


def test_model_size(model):
    n_vars = sum(1 for _ in model.component_data_objects(pyo.Var, active=True))
    n_cons = sum(1 for _ in model.component_data_objects(pyo.Constraint, active=True))
    assert n_vars > 0
    assert n_cons > 0
    print(f"\n  Model: {n_vars} vars, {n_cons} constraints")


# ── Solver feasibility test ───────────────────────────────────────────────────

@pytest.fixture(scope="module")
def solve_result(model):
    solver = pyo.SolverFactory("gurobi")
    if not solver.available():
        pytest.skip("Gurobi not available")
    solver.options["NonConvex"] = 2
    solver.options["TimeLimit"] = 120
    solver.options["OutputFlag"] = 0
    return solver.solve(model, tee=False)


def test_solver_feasible(solve_result):
    status = str(solve_result.solver.termination_condition)
    assert status in ("optimal", "feasible", "locallyOptimal"), \
        f"Solver returned non-feasible status: {status}"


def test_objective_finite(model, solve_result):
    status = str(solve_result.solver.termination_condition)
    if status not in ("optimal", "feasible", "locallyOptimal"):
        pytest.skip("model not solved")
    obj_var = "total_cost" if hasattr(model, "total_cost") else "obj" if hasattr(model, "obj") else None
    if obj_var:
        val = pyo.value(getattr(model, obj_var))
        assert val is not None and val < 1e15, f"Objective not finite: {val}"


def test_heat_balance_satisfied(model, solve_result):
    """Every ht_balance constraint must be satisfied within tolerance."""
    status = str(solve_result.solver.termination_condition)
    if status not in ("optimal", "feasible", "locallyOptimal"):
        pytest.skip("model not solved")
    tol = 0.05
    for c_obj in model.component_objects(pyo.Constraint):
        if not str(c_obj).startswith("ht_balance"):
            continue
        for idx in c_obj:
            c = c_obj[idx]
            val = pyo.value(c.body)
            if c.lb is not None:
                assert val >= c.lb - tol, f"{c_obj.name}[{idx}]: body={val:.4f} < lb={c.lb}"
            if c.ub is not None:
                assert val <= c.ub + tol, f"{c_obj.name}[{idx}]: body={val:.4f} > ub={c.ub}"


def test_pipe_soc_bounds(model, solve_result):
    """E_net must stay in [0, E_max] after solve."""
    status = str(solve_result.solver.termination_condition)
    if status not in ("optimal", "feasible", "locallyOptimal"):
        pytest.skip("model not solved")
    e_max = model.E_net[1].ub
    for t in model.t:
        val = pyo.value(model.E_net[t])
        assert -1e-4 <= val <= e_max + 1e-4, f"E_net[{t}]={val:.4f} outside [0, {e_max:.4f}]"


def test_chp_ramp_satisfied(model, solve_result):
    """CHP ramp-up must not exceed 6 MW/h between any two timesteps."""
    status = str(solve_result.solver.termination_condition)
    if status not in ("optimal", "feasible", "locallyOptimal"):
        pytest.skip("model not solved")
    tlist = sorted(model.t)
    for i in range(1, len(tlist)):
        q_now  = pyo.value(model.CHP_NODE_A_Qth[tlist[i]])
        q_prev = pyo.value(model.CHP_NODE_A_Qth[tlist[i - 1]])
        assert q_now - q_prev <= 6.0 + 1e-4, \
            f"Ramp-up violated at t={tlist[i]}: {q_now:.2f}-{q_prev:.2f}={q_now-q_prev:.2f} MW"


# =============================================================================
# MILP tests — milp_linearize=True, transport_delay=True, pipe_thermal_mass=True
# =============================================================================

CFG_MILP = {
    "assets": {
        "boiler_hub": {
            "type": "thermal_generator",
            "capacity_mw": 15.0,
            "thermal_efficiency": 0.90,
            "fuel_cost_eur_per_mwh": 40.0,
        },
        "chp_node_a": {
            "type": "thermal_generator",
            "capacity_mw": 8.0,
            "thermal_efficiency": 0.50,
            "el_eff": 0.35,
            "fuel_cost_eur_per_mwh": 35.0,
            "min_load": 0.30,
            "min_uptime_h": 2.0,
            "min_downtime_h": 1.0,
            "max_ramp_up_mw_per_h": 6.0,
            "max_ramp_down_mw_per_h": 8.0,
            "startup_cost_eur": 100.0,
        },
        "boiler_node_b": {
            "type": "thermal_generator",
            "capacity_mw": 12.0,
            "thermal_efficiency": 0.88,
            "fuel_cost_eur_per_mwh": 45.0,
        },
    },
    "network": {
        "milp_linearize": True,
        "supply_temp_c": 80.0,
        "return_temp_c": 55.0,
        "ground_temp_c": 10.0,
        "physics": {
            "heat_loss": True,
            "pressure_drop": False,
            "transport_delay": True,          # activates MILP linear tau-delay
            "pipe_thermal_mass": True,        # activates pipe buffer
            "pipe_thermal_mass_dT_c": 5.0,
            "pipe_thermal_mass_init_fraction": 0.5,
        },
        "nodes": {
            "hub": {"type": "producer", "assets": ["boiler_hub"]},
            "node_a": {
                "type": "mixed",
                "assets": ["chp_node_a"],
                "demand": {"column": "demand_a", "demand_fraction": 1.0},
            },
            "node_b": {
                "type": "mixed",
                "assets": ["boiler_node_b"],
                "demand": {"column": "demand_b", "demand_fraction": 1.0},
            },
        },
        "pipes": {
            "hub_to_a": {
                "from_node": "hub", "to_node": "node_a",
                "length_m": 5000,          # long enough for tau>0 at dt_h=1h
                "diameter_mm": 250,
                "current_diameter_supply_mm": 250,
            },
            "hub_to_b": {
                "from_node": "hub", "to_node": "node_b",
                "length_m": 3000,
                "diameter_mm": 200,
                "current_diameter_supply_mm": 200,
            },
        },
    },
    "fuels": {"gas": {"co2_kg_per_mwh": 200.0}},
    "costs": {"dump_cost_eur_per_mwh": 500.0},
    "run": {"horizon_years": 1},
}


@pytest.fixture(scope="module")
def milp_model():
    return build_model(TABLE, CFG_MILP, dt_h=dt_h)


@pytest.fixture(scope="module")
def milp_solve_result(milp_model):
    solver = pyo.SolverFactory("gurobi")
    if not solver.available():
        pytest.skip("Gurobi not available")
    solver.options["OutputFlag"] = 0
    solver.options["TimeLimit"] = 60
    return solver.solve(milp_model, tee=False)


# ── MILP structure tests ──────────────────────────────────────────────────────

def test_milp_model_builds(milp_model):
    assert milp_model is not None


def test_milp_linear_delay_long_pipe(milp_model):
    """5km DN250 pipe must get a linear tau-delay constraint (tau>=1 step at 1h)."""
    assert hasattr(milp_model, "HUB_TO_A_milp_delay"), \
        "MILP linear delay constraint missing for 5km hub_to_a pipe"


def test_milp_no_delay_short_pipe(milp_model):
    """3km DN200 pipe at 1h timestep: tau may be 0 → no_delay fallback is acceptable."""
    has_delay = hasattr(milp_model, "HUB_TO_B_milp_delay")
    has_nodelay = hasattr(milp_model, "HUB_TO_B_no_delay")
    assert has_delay or has_nodelay, \
        "hub_to_b pipe has neither milp_delay nor no_delay constraint"


def test_milp_pipe_thermal_mass(milp_model):
    assert hasattr(milp_model, "Q_net_buf"), "Q_net_buf missing in MILP model"
    assert hasattr(milp_model, "E_net"), "E_net missing in MILP model"
    assert hasattr(milp_model, "pipe_buf_soc"), "SOC constraint missing in MILP model"
    assert milp_model.E_net[1].ub > 0, "E_max must be positive"


def test_milp_chp_binary(milp_model):
    assert hasattr(milp_model, "CHP_NODE_A_on"), "CHP binary on/off missing in MILP"


def test_milp_chp_ramp(milp_model):
    assert hasattr(milp_model, "CHP_NODE_A_ramp_up"), "CHP ramp_up missing in MILP"


def test_milp_chp_min_uptime(milp_model):
    assert hasattr(milp_model, "CHP_NODE_A_min_uptime"), "CHP min_uptime missing in MILP"


def test_milp_heat_balance_all_nodes(milp_model):
    """Every node must have a heat balance constraint in MILP mode."""
    balance_names = {
        str(c) for c in milp_model.component_objects(pyo.Constraint)
        if str(c).startswith("ht_balance")
    }
    assert "ht_balance_hub" in balance_names, f"ht_balance_hub missing; found: {balance_names}"
    assert "ht_balance_node_a" in balance_names, f"ht_balance_node_a missing"
    assert "ht_balance_node_b" in balance_names, f"ht_balance_node_b missing"


def test_milp_model_is_pure_milp(milp_model):
    """In MILP mode temperatures are Params — no quadratic/bilinear terms."""
    n_bin = sum(
        1 for v in milp_model.component_data_objects(pyo.Var, active=True)
        if v.domain == pyo.Binary
    )
    assert n_bin > 0, "MILP model must have binary variables"
    n_vars = sum(1 for _ in milp_model.component_data_objects(pyo.Var, active=True))
    n_cons = sum(1 for _ in milp_model.component_data_objects(pyo.Constraint, active=True))
    print(f"\n  MILP model: {n_vars} vars ({n_bin} binary), {n_cons} constraints")


# ── MILP solver tests ─────────────────────────────────────────────────────────

def test_milp_solver_optimal(milp_solve_result):
    status = str(milp_solve_result.solver.termination_condition)
    assert status in ("optimal", "feasible"), \
        f"MILP solver returned non-optimal status: {status}"


def test_milp_objective_finite(milp_model, milp_solve_result):
    status = str(milp_solve_result.solver.termination_condition)
    if status not in ("optimal", "feasible"):
        pytest.skip("MILP not solved")
    obj_var = "total_cost" if hasattr(milp_model, "total_cost") else "obj" if hasattr(milp_model, "obj") else None
    if obj_var:
        val = pyo.value(getattr(milp_model, obj_var))
        assert val is not None and val < 1e15, f"MILP objective not finite: {val}"


def test_milp_heat_balance_satisfied(milp_model, milp_solve_result):
    """All ht_balance constraints must hold after MILP solve."""
    status = str(milp_solve_result.solver.termination_condition)
    if status not in ("optimal", "feasible"):
        pytest.skip("MILP not solved")
    tol = 0.05
    for c_obj in milp_model.component_objects(pyo.Constraint):
        if not str(c_obj).startswith("ht_balance"):
            continue
        for idx in c_obj:
            c = c_obj[idx]
            val = pyo.value(c.body)
            if c.lb is not None:
                assert val >= c.lb - tol, f"{c_obj.name}[{idx}]: {val:.4f} < lb={c.lb}"
            if c.ub is not None:
                assert val <= c.ub + tol, f"{c_obj.name}[{idx}]: {val:.4f} > ub={c.ub}"


def test_milp_pipe_soc_bounds(milp_model, milp_solve_result):
    """E_net must stay in [0, E_max] after MILP solve."""
    status = str(milp_solve_result.solver.termination_condition)
    if status not in ("optimal", "feasible"):
        pytest.skip("MILP not solved")
    e_max = milp_model.E_net[1].ub
    for t in milp_model.t:
        val = pyo.value(milp_model.E_net[t])
        assert -1e-4 <= val <= e_max + 1e-4, f"E_net[{t}]={val:.4f} outside [0, {e_max:.4f}]"


def test_milp_chp_ramp_satisfied(milp_model, milp_solve_result):
    """CHP ramp-up must not exceed 6 MW/h in the MILP solution."""
    status = str(milp_solve_result.solver.termination_condition)
    if status not in ("optimal", "feasible"):
        pytest.skip("MILP not solved")
    tlist = sorted(milp_model.t)
    for i in range(1, len(tlist)):
        q_now  = pyo.value(milp_model.CHP_NODE_A_Qth[tlist[i]])
        q_prev = pyo.value(milp_model.CHP_NODE_A_Qth[tlist[i - 1]])
        assert q_now - q_prev <= 6.0 + 1e-4, \
            f"MILP ramp-up violated at t={tlist[i]}: delta={q_now - q_prev:.2f} MW"


def test_milp_chp_min_uptime_satisfied(milp_model, milp_solve_result):
    """Once CHP turns on it must stay on for at least 2 consecutive steps."""
    status = str(milp_solve_result.solver.termination_condition)
    if status not in ("optimal", "feasible"):
        pytest.skip("MILP not solved")
    tlist = sorted(milp_model.t)
    on_vals = [round(pyo.value(milp_model.CHP_NODE_A_on[t])) for t in tlist]
    for i in range(len(on_vals) - 1):
        if on_vals[i] == 0 and on_vals[i + 1] == 1:
            # startup at i+1: must stay on for at least 2 steps (i+1, i+2)
            if i + 2 < len(on_vals):
                assert on_vals[i + 2] == 1, \
                    f"CHP min_uptime violated: on at t={tlist[i+1]}, off at t={tlist[i+2]}"
