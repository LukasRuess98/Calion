from pathlib import Path

import pytest

from energis.config.merge import (
    PROJECT_ROOT,
    load_and_merge,
    deep_merge,
    normalise_config_keys,
    _navigate,
)


def test_load_and_merge_from_subdirectory(monkeypatch):
    repo_root = PROJECT_ROOT
    notebooks_dir = repo_root / "notebooks"
    assert notebooks_dir.is_dir(), "Expected notebooks directory to exist"

    monkeypatch.chdir(notebooks_dir)

    cfg = load_and_merge(["configs/base.yaml"])

    merged_paths = [Path(p).resolve() for p in cfg["meta"]["merged_from"]]
    expected = (repo_root / "configs/base.yaml").resolve()

    assert expected in merged_paths


def test_grid_caps_schema_validation(tmp_path):
    config = tmp_path / "grid_caps.yaml"
    config.write_text(
        """
grid:
  max_import_mw: wrong
"""
    )

    with pytest.raises(TypeError):
        load_and_merge([str(config)])


# ---------------------------------------------------------------------------
# deep_merge
# ---------------------------------------------------------------------------

class TestDeepMerge:
    def test_simple(self):
        assert deep_merge({"a": 1}, {"b": 2}) == {"a": 1, "b": 2}

    def test_override(self):
        assert deep_merge({"a": 1}, {"a": 2}) == {"a": 2}

    def test_nested(self):
        a = {"x": {"a": 1, "b": 2}}
        b = {"x": {"b": 3, "c": 4}}
        result = deep_merge(a, b)
        assert result == {"x": {"a": 1, "b": 3, "c": 4}}

    def test_no_mutation(self):
        a = {"x": {"a": 1}}
        b = {"x": {"b": 2}}
        result = deep_merge(a, b)
        assert "b" not in a["x"]


# ---------------------------------------------------------------------------
# _navigate
# ---------------------------------------------------------------------------

class TestNavigate:
    def test_simple(self):
        cfg = {"a": {"b": {"c": 1}}}
        assert _navigate(cfg, "a.b") == {"c": 1}

    def test_missing_key(self):
        assert _navigate({"a": 1}, "a.b") is None

    def test_non_dict_leaf(self):
        assert _navigate({"a": "string"}, "a") is None

    def test_top_level(self):
        cfg = {"a": 1, "b": 2}
        # Single key that IS a dict
        assert _navigate({"x": {"y": 1}}, "x") == {"y": 1}


# ---------------------------------------------------------------------------
# normalise_config_keys
# ---------------------------------------------------------------------------

class TestNormaliseConfigKeys:
    def test_storage_soc_init(self):
        cfg = {"system": {"storage": {"SOC_init": 50.0}}}
        normalise_config_keys(cfg)
        assert cfg["system"]["storage"]["soc_init_mwh"] == 50.0
        assert cfg["system"]["storage"]["SOC_init"] == 50.0  # kept

    def test_storage_soc0_mwh(self):
        cfg = {"system": {"storage": {"soc0_mwh": 30.0}}}
        normalise_config_keys(cfg)
        assert cfg["system"]["storage"]["soc_init_mwh"] == 30.0

    def test_canonical_not_overwritten(self):
        cfg = {"system": {"storage": {"SOC_init": 50.0, "soc_init_mwh": 100.0}}}
        normalise_config_keys(cfg)
        assert cfg["system"]["storage"]["soc_init_mwh"] == 100.0  # not overwritten

    def test_rolling_horizon_uppercase(self):
        cfg = {
            "scenario": {
                "rolling_horizon": {
                    "HEAT_HORIZON_HOURS": 168,
                    "STEP_HOURS": 24,
                    "OVERLAP_HOURS": 6,
                    "TERMINAL_POLICY": "cyclic",
                }
            }
        }
        normalise_config_keys(cfg)
        rh = cfg["scenario"]["rolling_horizon"]
        assert rh["heat_horizon_hours"] == 168
        assert rh["step_hours"] == 24
        assert rh["overlap_hours"] == 6
        assert rh["terminal_policy"] == "cyclic"

    def test_window_hours_alias(self):
        cfg = {"scenario": {"rolling_horizon": {"window_hours": 48}}}
        normalise_config_keys(cfg)
        assert cfg["scenario"]["rolling_horizon"]["heat_horizon_hours"] == 48

    def test_inputs_soc_init(self):
        cfg = {"inputs": {"SOC_init": 25.0}}
        normalise_config_keys(cfg)
        assert cfg["inputs"]["soc_init_mwh"] == 25.0

    def test_no_inputs_section(self):
        cfg = {"system": {}}
        normalise_config_keys(cfg)  # should not raise

    def test_inputs_not_dict(self):
        cfg = {"inputs": "not_a_dict"}
        normalise_config_keys(cfg)  # should not raise
