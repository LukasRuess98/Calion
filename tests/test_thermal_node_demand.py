"""Tests that ThermalNodeBlock uses demand_column (heatd_{id}) directly, not demand_fraction."""
import pytest

try:
    import pyomo.environ as pyo
    HAVE_PYOMO = True
except ImportError:
    HAVE_PYOMO = False

pytestmark = pytest.mark.skipif(not HAVE_PYOMO, reason="Pyomo not installed")

from calion.models.blocks.thermal_node import ThermalNodeBlock


def _make_model_with_node_heatd(demand_values: list) -> "pyo.ConcreteModel":
    m = pyo.ConcreteModel()
    m.t = pyo.RangeSet(1, len(demand_values))
    m.heatd_mynode = pyo.Param(
        m.t,
        initialize={i + 1: float(v) for i, v in enumerate(demand_values)},
        mutable=True,
    )
    return m


def test_consumer_uses_demand_column_directly():
    """Consumer Q_demand equals heatd_{node_id} values without any fraction scaling."""
    demand = [10.0, 20.0, 30.0]
    m = _make_model_with_node_heatd(demand)
    config = {
        "id": "mynode",
        "type": "consumer",
        "demand_column": "col_mynode",
    }
    ThermalNodeBlock.attach(m, m.t, config, buses={}, network_pipes={})
    q_demand = getattr(m, "MYNODE_Q_demand")
    values = [pyo.value(q_demand[t]) for t in m.t]
    assert values == pytest.approx(demand), f"Expected {demand}, got {values}"


def test_consumer_validate_config_requires_demand_column_or_profile():
    """validate_config raises when neither demand_column nor demand_profile is present."""
    with pytest.raises(ValueError, match="demand_column"):
        ThermalNodeBlock.validate_config({"id": "x", "type": "consumer"})


def test_consumer_validate_config_accepts_demand_column():
    """validate_config accepts config with demand_column."""
    ThermalNodeBlock.validate_config({"id": "x", "type": "consumer", "demand_column": "col_x"})


def test_consumer_validate_config_accepts_demand_profile():
    """validate_config accepts config with demand_profile."""
    ThermalNodeBlock.validate_config({"id": "x", "type": "consumer", "demand_profile": {1: 5.0}})


def test_demand_fraction_alone_is_rejected():
    """validate_config raises if only demand_fraction is provided (no longer valid)."""
    with pytest.raises(ValueError, match="demand_column"):
        ThermalNodeBlock.validate_config({"id": "x", "type": "consumer", "demand_fraction": 0.5})


def test_result_dict_has_no_demand_fraction():
    """attach() result dict must not contain demand_fraction key."""
    demand = [5.0, 10.0]
    m = _make_model_with_node_heatd(demand)
    config = {
        "id": "mynode",
        "type": "consumer",
        "demand_column": "col_mynode",
    }
    result = ThermalNodeBlock.attach(m, m.t, config, buses={}, network_pipes={})
    assert "demand_fraction" not in result


# ---------------------------------------------------------------------------
# Multi-consumer helpers and tests
# ---------------------------------------------------------------------------

def _make_model_with_two_consumers(demand_a: list, demand_b: list):
    m = pyo.ConcreteModel()
    T = len(demand_a)
    m.t = pyo.RangeSet(1, T)
    m.heatd_abnode_0 = pyo.Param(
        m.t,
        initialize={i + 1: float(v) for i, v in enumerate(demand_a)},
        mutable=True,
    )
    m.heatd_abnode_1 = pyo.Param(
        m.t,
        initialize={i + 1: float(v) for i, v in enumerate(demand_b)},
        mutable=True,
    )
    # Also create sum param (backward compat)
    m.heatd_abnode = pyo.Param(
        m.t,
        initialize={i + 1: float(demand_a[i] + demand_b[i]) for i in range(T)},
        mutable=True,
    )
    return m


def test_validate_config_accepts_consumers_list():
    """validate_config accepts consumers list without demand_column."""
    ThermalNodeBlock.validate_config({
        "id": "x", "type": "consumer",
        "consumers": [{"column": "col_a"}, {"column": "col_b"}]
    })


def test_validate_config_accepts_mixed_type():
    """validate_config accepts mixed type with consumers."""
    ThermalNodeBlock.validate_config({
        "id": "x", "type": "mixed",
        "consumers": [{"column": "col_a"}]
    })


def test_multi_consumer_q_demand_params_created():
    """attach() creates ABNODE_Q_demand_0 and ABNODE_Q_demand_1 params for multi-consumer node."""
    m = _make_model_with_two_consumers([1.0, 2.0], [3.0, 4.0])
    config = {
        "id": "abnode",
        "type": "consumer",
        "consumers": [{"column": "col_a"}, {"column": "col_b"}],
    }
    ThermalNodeBlock.attach(m, m.t, config, buses={}, network_pipes={})
    assert hasattr(m, "ABNODE_Q_demand_0")
    assert hasattr(m, "ABNODE_Q_demand_1")


def test_multi_consumer_q_demand_values():
    """attach() Q_demand_0 and Q_demand_1 match the heatd_{id}_0 and heatd_{id}_1 param values."""
    demand_a = [1.0, 2.0]
    demand_b = [3.0, 4.0]
    m = _make_model_with_two_consumers(demand_a, demand_b)
    config = {
        "id": "abnode",
        "type": "consumer",
        "consumers": [{"column": "col_a"}, {"column": "col_b"}],
    }
    ThermalNodeBlock.attach(m, m.t, config, buses={}, network_pipes={})
    q0 = [pyo.value(m.ABNODE_Q_demand_0[t]) for t in m.t]
    q1 = [pyo.value(m.ABNODE_Q_demand_1[t]) for t in m.t]
    assert q0 == pytest.approx(demand_a)
    assert q1 == pytest.approx(demand_b)


def test_multi_consumer_m_dot_demand_sum_constraint():
    """attach() creates m_dot_demand_sum constraint tying aggregate to per-consumer flows."""
    m = _make_model_with_two_consumers([2.0, 4.0], [1.0, 3.0])
    config = {
        "id": "abnode",
        "type": "consumer",
        "consumers": [{"column": "col_a"}, {"column": "col_b"}],
    }
    ThermalNodeBlock.attach(m, m.t, config, buses={}, network_pipes={})
    assert hasattr(m, "ABNODE_m_dot_demand_sum")
    assert hasattr(m, "ABNODE_m_dot_demand_0")
    assert hasattr(m, "ABNODE_m_dot_demand_1")
