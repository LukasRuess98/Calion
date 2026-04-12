"""Tests for the distributed pump model in PipePairBlock."""
import pytest

try:
    import pyomo.environ as pyo
    HAVE_PYOMO = True
except ImportError:
    HAVE_PYOMO = False

pytestmark = pytest.mark.skipif(not HAVE_PYOMO, reason="Pyomo not installed")


def _pipe_config(pump_efficiency: float = 0.70, pump_enabled: bool = True) -> dict:
    return {
        'id': 'pipe_pump_test',
        'from_node': 'A',
        'to_node': 'B',
        'length_m': 500.0,
        'current_diameter_supply_mm': 200,
        'supply_temp_nominal_c': 90.0,
        'return_temp_nominal_c': 50.0,
        'milp_linearize': True,
        'pump_efficiency': pump_efficiency,
        'pump_enabled': pump_enabled,
    }


def test_p_pump_variable_created():
    """PipePairBlock must add P_pump Var when pump_enabled=True."""
    from calion.models.blocks.pipe_pair import PipePairBlock

    m = pyo.ConcreteModel()
    m.t = pyo.RangeSet(1, 4)
    m.dt_h = 1.0

    PipePairBlock.attach(m, m.t, _pipe_config(), buses={})

    assert hasattr(m, 'PIPE_PUMP_TEST_P_pump'), "P_pump variable must exist"
    P_pump = m.PIPE_PUMP_TEST_P_pump
    assert isinstance(P_pump, pyo.Var), "P_pump must be a Pyomo Var"


def test_p_pump_nonnegative():
    """P_pump must be non-negative (pumps don't generate power)."""
    from calion.models.blocks.pipe_pair import PipePairBlock

    m = pyo.ConcreteModel()
    m.t = pyo.RangeSet(1, 4)
    m.dt_h = 1.0

    PipePairBlock.attach(m, m.t, _pipe_config(), buses={})
    P_pump = m.PIPE_PUMP_TEST_P_pump
    lb = P_pump[1].lb
    assert lb is not None and lb >= 0.0, "P_pump lower bound must be >= 0"


def test_p_pump_in_result_dict():
    """attach() must return P_pump reference in result dict."""
    from calion.models.blocks.pipe_pair import PipePairBlock

    m = pyo.ConcreteModel()
    m.t = pyo.RangeSet(1, 4)
    m.dt_h = 1.0

    result = PipePairBlock.attach(m, m.t, _pipe_config(), buses={})
    assert 'P_pump' in result, "Result dict must contain P_pump key"


def test_p_pump_zero_when_disabled():
    """When pump_enabled=False, P_pump must be fixed to 0."""
    from calion.models.blocks.pipe_pair import PipePairBlock

    m = pyo.ConcreteModel()
    m.t = pyo.RangeSet(1, 4)
    m.dt_h = 1.0

    PipePairBlock.attach(m, m.t, _pipe_config(pump_enabled=False), buses={})
    P_pump = getattr(m, 'PIPE_PUMP_TEST_P_pump', None)
    assert P_pump is not None, "P_pump variable must exist even when disabled"
    assert P_pump[1].fixed, "P_pump must be fixed when pump_enabled=False"


def test_p_pump_pwl_constraint_exists():
    """PWL constraint linking P_pump to m_dot must be present."""
    from calion.models.blocks.pipe_pair import PipePairBlock

    m = pyo.ConcreteModel()
    m.t = pyo.RangeSet(1, 4)
    m.dt_h = 1.0

    PipePairBlock.attach(m, m.t, _pipe_config(), buses={})
    assert hasattr(m, 'PIPE_PUMP_TEST_pump_power'), "pump_power PWL constraint must exist"
