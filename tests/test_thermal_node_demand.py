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
    with pytest.raises(ValueError, match="demand_column or demand_profile"):
        ThermalNodeBlock.validate_config({"id": "x", "type": "consumer"})


def test_consumer_validate_config_accepts_demand_column():
    """validate_config accepts config with demand_column."""
    ThermalNodeBlock.validate_config({"id": "x", "type": "consumer", "demand_column": "col_x"})


def test_consumer_validate_config_accepts_demand_profile():
    """validate_config accepts config with demand_profile."""
    ThermalNodeBlock.validate_config({"id": "x", "type": "consumer", "demand_profile": {1: 5.0}})


def test_demand_fraction_alone_is_rejected():
    """validate_config raises if only demand_fraction is provided (no longer valid)."""
    with pytest.raises(ValueError, match="demand_column or demand_profile"):
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
