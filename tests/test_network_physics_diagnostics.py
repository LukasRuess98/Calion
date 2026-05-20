"""Diagnostics regression tests for NetworkManager physics residual exports."""

import pytest

try:
    import pyomo.environ as pyo
    HAVE_PYOMO = True
except ImportError:
    HAVE_PYOMO = False

from calion.models.network_manager import NetworkManager


pytestmark = pytest.mark.skipif(not HAVE_PYOMO, reason="Pyomo not installed")


def _build_base_case():
    m = pyo.ConcreteModel()
    m.t = pyo.RangeSet(1, 2)

    m.m_dot = pyo.Var(m.t)
    m.m_dot_abs = pyo.Var(m.t, domain=pyo.NonNegativeReals)
    m.t_supply_out = pyo.Var(m.t)
    m.t_return_out = pyo.Var(m.t)
    m.q_delivered = pyo.Var(m.t, domain=pyo.NonNegativeReals)
    m.q_consumer = pyo.Var(m.t, domain=pyo.NonNegativeReals)
    m.node_t_supply = pyo.Var(m.t)
    m.node_t_return = pyo.Var(m.t)
    m.m_dot_demand = pyo.Var(m.t, domain=pyo.NonNegativeReals)
    m.P1_z_delay = pyo.Var([0], m.t, domain=pyo.NonNegativeReals)

    values = {
        1: {"m_dot": 10.0, "t_supply_out": 84.0, "t_return_out": 54.0, "q_delivered": 5.0},
        2: {"m_dot": 12.0, "t_supply_out": 83.0, "t_return_out": 55.0, "q_delivered": 7.0},
    }
    for t in m.t:
        v = values[int(t)]
        m.m_dot[t].fix(v["m_dot"])
        m.m_dot_abs[t].fix(v["m_dot"])
        m.t_supply_out[t].fix(v["t_supply_out"])
        m.t_return_out[t].fix(v["t_return_out"])
        m.q_delivered[t].fix(v["q_delivered"])
        m.node_t_supply[t].fix(v["t_supply_out"])
        m.node_t_return[t].fix(v["t_return_out"])
        m.m_dot_demand[t].fix(v["m_dot"])
        m.P1_z_delay[0, t].fix(1.0)

    # hold_first warmup with tau=1 -> expected q_consumer: [q1, q1]
    m.q_consumer[1].fix(5.0)
    m.q_consumer[2].fix(5.0)

    pipe_comp = {
        "m_dot": m.m_dot,
        "m_dot_abs": m.m_dot_abs,
        "T_supply_out": m.t_supply_out,
        "T_return_out": m.t_return_out,
        "Q_delivered": m.q_delivered,
        "Q_consumer": m.q_consumer,
        "tau_steps": [1],
        "delay_warmup_mode": "hold_first",
        "prefix": "P1",
    }
    node_comp = {
        "type": "consumer",
        "incoming_pipes": ["p1"],
        "outgoing_pipes": [],
        "supply_incoming_pipes": ["p1"],
        "return_incoming_pipes": ["p1"],
        "T_supply": m.node_t_supply,
        "T_return": m.node_t_return,
        "m_dot_demand": m.m_dot_demand,
    }

    nm = NetworkManager({"thermal_network": {"enabled": False}})
    nm.pipes = {"p1": {"Q_pipe_initial_mw": 0.0}}
    nm._last_pipe_components = {"p1": pipe_comp}
    nm._last_node_components = {"n1": node_comp}
    return nm, m


def test_diagnostics_zero_for_consistent_case():
    nm, m = _build_base_case()
    diag = nm._compute_physics_diagnostics(m, m.t)

    assert diag["mass_balance"]["global_max_abs_kg_s"] == pytest.approx(0.0, abs=1e-9)
    assert diag["enthalpy_mixing"]["supply_global_max_abs_c"] == pytest.approx(0.0, abs=1e-9)
    assert diag["enthalpy_mixing"]["return_global_max_abs_c"] == pytest.approx(0.0, abs=1e-9)
    assert diag["delay_consistency"]["global_max_abs_mw"] == pytest.approx(0.0, abs=1e-9)


def test_diagnostics_capture_return_mixing_error():
    nm, m = _build_base_case()
    m.node_t_return[2].fix(49.0)
    diag = nm._compute_physics_diagnostics(m, m.t)

    node_err = diag["enthalpy_mixing"]["return_by_node"]["n1"]["max_abs_c"]
    assert node_err == pytest.approx(6.0, abs=1e-9)


def test_delay_skip_warmup_reduces_sample_count():
    nm, m = _build_base_case()
    nm._last_pipe_components["p1"]["tau_steps"] = [2]
    nm._last_pipe_components["p1"]["delay_warmup_mode"] = "skip"
    # Only t=2 has i>=tau? No, for tau=2 and 2 timesteps both are warm-up (0,1 < 2).
    diag = nm._compute_physics_diagnostics(m, m.t)

    by_pipe = diag["delay_consistency"]["by_pipe"]["p1"]
    assert by_pipe["samples"] == pytest.approx(0.0)
    assert by_pipe["skipped_warmup_samples"] == pytest.approx(2.0)
