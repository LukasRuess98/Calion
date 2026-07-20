"""Regression tests for zero-flow thermal network pipes."""
import pytest

try:
    import pyomo.environ as pyo
    HAVE_PYOMO = True
except ImportError:
    HAVE_PYOMO = False

pytestmark = pytest.mark.skipif(not HAVE_PYOMO, reason="Pyomo not installed")


def _pipe_config() -> dict:
    return {
        "id": "pipe_zero_flow",
        "from_node": "A",
        "to_node": "B",
        "length_m": 500.0,
        "current_diameter_supply_mm": 200,
        "supply_temp_nominal_c": 90.0,
        "return_temp_nominal_c": 50.0,
        "ground_temp_c": 10.0,
        "milp_linearize": False,
        # Binary stagnation mode is the exact zero-flow physics mode:
        # at m_dot=0 the pipe can stay inactive with no forced heat loss.
        "stagnation_mode": "binary",
    }


def _assert_constraint_satisfied(c, tol: float = 1e-9) -> None:
    body = pyo.value(c.body)
    if c.lower is not None:
        assert body >= pyo.value(c.lower) - tol
    if c.upper is not None:
        assert body <= pyo.value(c.upper) + tol


def test_zero_flow_pipe_can_have_zero_losses_in_nlp_mode():
    """Stagnant pipes should not be forced to lose heat when m_dot is zero."""
    from calion.models.blocks.pipe_pair import PipePairBlock

    m = pyo.ConcreteModel()
    m.t = pyo.RangeSet(1, 1)
    m.dt_h = 1.0

    PipePairBlock.attach(m, m.t, _pipe_config(), buses={})

    m.PIPE_ZERO_FLOW_m_dot[1].fix(0.0)
    m.PIPE_ZERO_FLOW_T_supply_in[1].fix(60.0)
    m.PIPE_ZERO_FLOW_T_supply_out[1].fix(60.0)
    m.PIPE_ZERO_FLOW_T_return_in[1].fix(40.0)
    m.PIPE_ZERO_FLOW_T_return_out[1].fix(40.0)
    m.PIPE_ZERO_FLOW_Q_loss_supply[1].fix(0.0)
    m.PIPE_ZERO_FLOW_Q_loss_return[1].fix(0.0)
    m.PIPE_ZERO_FLOW_Q_delivered[1].fix(0.0)
    m.PIPE_ZERO_FLOW_is_active[1].fix(0.0)

    assert pyo.value(m.PIPE_ZERO_FLOW_Q_loss_supply[1]) == pytest.approx(0.0)
    assert pyo.value(m.PIPE_ZERO_FLOW_Q_loss_return[1]) == pytest.approx(0.0)
    assert pyo.value(m.PIPE_ZERO_FLOW_T_supply_in[1]) == pytest.approx(pyo.value(m.PIPE_ZERO_FLOW_T_supply_out[1]))
    assert pyo.value(m.PIPE_ZERO_FLOW_T_return_in[1]) == pytest.approx(pyo.value(m.PIPE_ZERO_FLOW_T_return_out[1]))

    _assert_constraint_satisfied(m.PIPE_ZERO_FLOW_heat_loss_supply[1])
    _assert_constraint_satisfied(m.PIPE_ZERO_FLOW_heat_loss_supply_relax_lb[1])
    _assert_constraint_satisfied(m.PIPE_ZERO_FLOW_heat_loss_return[1])
    _assert_constraint_satisfied(m.PIPE_ZERO_FLOW_heat_loss_return_relax_lb[1])
    _assert_constraint_satisfied(m.PIPE_ZERO_FLOW_temp_drop_supply[1])
    _assert_constraint_satisfied(m.PIPE_ZERO_FLOW_temp_drop_supply_relax_lb[1])
    _assert_constraint_satisfied(m.PIPE_ZERO_FLOW_temp_drop_return[1])
    _assert_constraint_satisfied(m.PIPE_ZERO_FLOW_temp_drop_return_relax_lb[1])
