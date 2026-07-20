"""Tests for stateful return-v2 node modeling and summer warmup slacks."""
import pytest

try:
    import pyomo.environ as pyo
    HAVE_PYOMO = True
except ImportError:
    HAVE_PYOMO = False

pytestmark = pytest.mark.skipif(not HAVE_PYOMO, reason="Pyomo not installed")


def _make_node_model(with_flow_anchor: bool) -> "pyo.ConcreteModel":
    from calion.models.blocks.thermal_node import ThermalNodeBlock

    m = pyo.ConcreteModel()
    m.t = pyo.RangeSet(1, 4)
    m.dt_h = 1.0

    # Minimal incoming pipe references required by node mass/temperature constraints.
    m.J14_TO_J15_m_dot = pyo.Var(m.t, domain=pyo.NonNegativeReals, initialize=1.0)
    m.J14_TO_J15_T_supply_out = pyo.Var(m.t, domain=pyo.NonNegativeReals, initialize=80.0)

    cfg = {
        "id": "j_15",
        "type": "consumer",
        "demand_profile": {1: 1.0, 2: 1.1, 3: 1.2, 4: 1.1},
        "return_model_mode": "stateful_v2",
        "return_temp_range": [50.0, 78.0],
        "return_temp_load_factor": 0.2,  # would create legacy load constraints if not skipped
        "return_temp_load_mode": "equal",
        "return_temp_ref_profile": {1: 60.0, 2: 60.0, 3: 60.0, 4: 60.0},
        "return_v2_params": {
            "a0": 56.0,
            "a_q": 0.8,
            "a_out": 0.1,
            "a_sup": 0.1,
            "alpha": 0.35,
            "q_ref": 1.0,
            "t_outdoor_ref": 10.0,
            "t_supply_ref": 86.0,
        },
        "return_v2_outdoor_profile": {1: 10.0, 2: 11.0, 3: 12.0, 4: 11.5},
        "return_state_penalty_eur_per_c": 2500.0,
        "return_link_penalty_eur_per_c": 5000.0,
        "flow_anchor_penalty_eur_per_kg_s": 800.0,
    }
    if with_flow_anchor:
        cfg["flow_anchor_profile_kg_s"] = {1: 0.8, 2: 0.9, 3: 1.0, 4: 0.9}

    ThermalNodeBlock.attach(
        m,
        m.t,
        cfg,
        buses={},
        network_pipes={"j14_to_j15": {"from_node": "j_14", "to_node": "j_15"}},
    )
    return m


def test_stateful_v2_builds_state_and_skips_legacy_load_constraints():
    m = _make_node_model(with_flow_anchor=True)

    assert hasattr(m, "J_15_T_return_state")
    assert hasattr(m, "J_15_return_state_link")
    assert hasattr(m, "J_15_flow_anchor_lb")
    assert hasattr(m, "J_15_flow_anchor_ub")

    # Legacy load-mode constraints must not be generated in stateful_v2 mode.
    assert not hasattr(m, "J_15_return_temp_load")
    assert not hasattr(m, "J_15_return_temp_load_lb")
    assert not hasattr(m, "J_15_return_temp_load_ub")

    # Configured summer-terminal bounds should be respected for T_return.
    assert m.J_15_T_return[1].lb == pytest.approx(50.0)
    assert m.J_15_T_return[1].ub == pytest.approx(78.0)


def test_flow_anchor_constraints_are_skipped_without_profile():
    m = _make_node_model(with_flow_anchor=False)
    assert not hasattr(m, "J_15_flow_anchor_lb")
    assert not hasattr(m, "J_15_flow_anchor_ub")


def test_pipe_warmup_slack_active_only_for_first_n_hours():
    from calion.models.blocks.pipe_pair import PipePairBlock

    m = pyo.ConcreteModel()
    m.t = pyo.RangeSet(1, 5)
    m.dt_h = 1.0

    cfg = {
        "id": "pipe_warm",
        "from_node": "A",
        "to_node": "B",
        "length_m": 500.0,
        "current_diameter_supply_mm": 200,
        "supply_temp_nominal_c": 90.0,
        "return_temp_nominal_c": 50.0,
        "ground_temp_c": 10.0,
        "milp_linearize": False,
        "stagnation_mode": "binary",
        "physics": {"heat_loss": True, "transport_delay": False},
        "summer_warmup_hours": 2,
        "summer_warmup_penalty_eur_per_mwh": 2.0e6,
    }

    PipePairBlock.attach(m, m.t, cfg, buses={})
    assert hasattr(m, "PIPE_WARM_summer_warmup_slack")

    warmup_slack = m.PIPE_WARM_summer_warmup_slack
    for t in m.t:
        if int(t) <= 2:
            assert warmup_slack[t].fixed is False
        else:
            assert warmup_slack[t].fixed is True
            assert pyo.value(warmup_slack[t]) == pytest.approx(0.0)
