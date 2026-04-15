import pytest
from calion.models.blocks.temperature_linearization import build_temperatures


TIME_SET = list(range(3))  # t=0,1,2


def _demands(vals):
    return {t: v for t, v in zip(TIME_SET, vals)}


# ── fixed ──────────────────────────────────────────────────────────────────

def test_fixed_returns_nominal():
    temps = build_temperatures('fixed', {}, _demands([0, 50, 100]), 100.0, 100.0, 40.0, TIME_SET)
    for t in TIME_SET:
        assert temps[t][0] == 100.0
        assert temps[t][1] == 40.0


def test_fixed_is_default_when_method_empty():
    temps = build_temperatures('', {}, _demands([0, 50, 100]), 100.0, 80.0, 35.0, TIME_SET)
    for t in TIME_SET:
        assert temps[t] == (80.0, 35.0)


# ── global ─────────────────────────────────────────────────────────────────

GLOBAL_CFG = {
    'global_profile': {
        'T_supply_min_c': 70.0,
        'T_supply_max_c': 95.0,
        'T_return_max_c': 55.0,
        'T_return_min_c': 45.0,
    }
}


def test_global_at_zero_load():
    temps = build_temperatures('global', GLOBAL_CFG, _demands([0, 0, 0]), 100.0, 90.0, 50.0, TIME_SET)
    T_s, T_r = temps[0]
    assert T_s == pytest.approx(70.0)
    assert T_r == pytest.approx(55.0)


def test_global_at_full_load():
    temps = build_temperatures('global', GLOBAL_CFG, _demands([100, 100, 100]), 100.0, 90.0, 50.0, TIME_SET)
    T_s, T_r = temps[0]
    assert T_s == pytest.approx(95.0)
    assert T_r == pytest.approx(45.0)


def test_global_at_half_load():
    temps = build_temperatures('global', GLOBAL_CFG, _demands([50, 50, 50]), 100.0, 90.0, 50.0, TIME_SET)
    T_s, T_r = temps[0]
    assert T_s == pytest.approx(82.5)   # 70 + 0.5*(95-70)
    assert T_r == pytest.approx(50.0)   # 55 - 0.5*(55-45)


# ── pwl ────────────────────────────────────────────────────────────────────

PWL_CFG = {
    'temperature_profile': {
        'load_fractions': [0.0, 0.5, 1.0],
        'T_supply_c':     [70.0, 82.5, 95.0],
        'T_return_c':     [55.0, 50.0, 45.0],
    }
}


def test_pwl_at_breakpoints():
    demands = _demands([0.0, 50.0, 100.0])
    temps = build_temperatures('pwl', PWL_CFG, demands, 100.0, 90.0, 50.0, TIME_SET)
    assert temps[0] == pytest.approx((70.0, 55.0))
    assert temps[1] == pytest.approx((82.5, 50.0))
    assert temps[2] == pytest.approx((95.0, 45.0))


def test_pwl_between_breakpoints():
    # λ = 0.25 → halfway between breakpoints 0 and 1
    temps = build_temperatures('pwl', PWL_CFG, {0: 25.0}, 100.0, 90.0, 50.0, [0])
    T_s, T_r = temps[0]
    assert T_s == pytest.approx(76.25)  # 70 + 0.5*(82.5-70)
    assert T_r == pytest.approx(52.5)   # 55 + 0.5*(50-55)


# ── invariants ─────────────────────────────────────────────────────────────

def test_supply_gt_return_all_methods():
    demands = _demands([0.0, 50.0, 100.0])
    for method, cfg in [
        ('fixed', {}),
        ('global', GLOBAL_CFG),
        ('pwl', PWL_CFG),
    ]:
        temps = build_temperatures(method, cfg, demands, 100.0, 100.0, 40.0, TIME_SET)
        for t in TIME_SET:
            T_s, T_r = temps[t]
            assert T_s > T_r, f"method={method} t={t}: T_supply ({T_s}) not > T_return ({T_r})"


def test_heat_delivered_balance():
    """Q = m_dot * cp * dT / 1000 with cp=4.186 kJ/(kg·K)"""
    temps = build_temperatures('global', GLOBAL_CFG, {0: 50.0}, 100.0, 90.0, 50.0, [0])
    T_s, T_r = temps[0]
    m_dot = 10.0   # kg/s
    cp = 4.186     # kJ/(kg·K)
    Q_expected = m_dot * cp * (T_s - T_r) / 1000  # MW
    assert Q_expected > 0.0
    assert T_s - T_r == pytest.approx(82.5 - 50.0)


# ── validation ─────────────────────────────────────────────────────────────

def test_invalid_pwl_raises_on_bad_fractions():
    bad_cfg = {
        'temperature_profile': {
            'load_fractions': [0.0, 1.5],   # > 1
            'T_supply_c':     [70.0, 95.0],
            'T_return_c':     [55.0, 45.0],
        }
    }
    with pytest.raises(ValueError, match="load_fractions"):
        build_temperatures('pwl', bad_cfg, {0: 50.0}, 100.0, 90.0, 50.0, [0])


def test_invalid_pwl_raises_on_supply_le_return():
    bad_cfg = {
        'temperature_profile': {
            'load_fractions': [0.0, 1.0],
            'T_supply_c':     [70.0, 95.0],
            'T_return_c':     [80.0, 45.0],  # T_return > T_supply at breakpoint 0
        }
    }
    with pytest.raises(ValueError, match="T_supply"):
        build_temperatures('pwl', bad_cfg, {0: 50.0}, 100.0, 90.0, 50.0, [0])


def test_unknown_method_raises():
    with pytest.raises(ValueError, match="Unknown"):
        build_temperatures('nonexistent', {}, {0: 0.0}, 1.0, 90.0, 40.0, [0])
