"""v12 B6: CALION_HP_DEFAULT_CHANNEL=off|on (default off). Off => hp Q_def fixed to 0, HP heat only via the WRG source."""
import numpy as np
import pyomo.environ as pyo
import pytest

from tests.v12 import twonode_helper as h


def _build(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("CALION_HP_DEFAULT_CHANNEL", raising=False)
    else:
        monkeypatch.setenv("CALION_HP_DEFAULT_CHANNEL", value)
    model, _ = h.build(h.make_cfg(hp_mw=8.0, cap_mw=0.5))
    return model


def test_default_is_off_and_heat_only_from_wrg(monkeypatch):
    m = _build(monkeypatch, None)
    assert all(m.hp_sb_Q_def[t].fixed and pyo.value(m.hp_sb_Q_def[t]) == 0.0 for t in m.t)
    assert h.solve(m) == "optimal"
    q = np.array([pyo.value(m.hp_sb_Q[t]) for t in m.t])
    wrg_cap = np.array([pyo.value(m.hp_sb_WRG_cap[t]) for t in m.t])
    assert q.sum() > 0, "HP should run (cheap WRG heat) in this 48 h test"
    assert np.all(q <= wrg_cap + 1e-6)


def test_on_leaves_channel_free(monkeypatch):
    m = _build(monkeypatch, "on")
    assert not any(m.hp_sb_Q_def[t].fixed for t in m.t)


def test_invalid_value_raises(monkeypatch):
    with pytest.raises(Exception, match="CALION_HP_DEFAULT_CHANNEL"):
        _build(monkeypatch, "maybe")
