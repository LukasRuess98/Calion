"""Tests for energis.analysis.sensitivity — pure-logic functions only.

No solver required; all tested functions are deterministic computations.
"""

import pytest

from energis.analysis.sensitivity import (
    ParameterVariation,
    SensitivityResult,
    apply_parameter_variation,
    calculate_sensitivity_indices,
    create_standard_sensitivity_study,
    format_sensitivity_table,
)


# ---------------------------------------------------------------------------
# ParameterVariation — construction and validation
# ---------------------------------------------------------------------------

class TestParameterVariation:
    def test_invalid_variation_type_raises(self):
        with pytest.raises(ValueError, match="variation_type must be"):
            ParameterVariation(
                param_path="a.b",
                base_value=1.0,
                variations=[0.9, 1.0, 1.1],
                variation_type="relative",  # invalid
            )

    def test_valid_multiplicative(self):
        pv = ParameterVariation(
            param_path="a.b",
            base_value=2.0,
            variations=[0.5, 1.0, 1.5],
            variation_type="multiplicative",
        )
        assert pv.variation_type == "multiplicative"

    def test_valid_absolute(self):
        pv = ParameterVariation(
            param_path="a.b",
            base_value=10.0,
            variations=[-2.0, 0.0, 2.0],
            variation_type="absolute",
        )
        assert pv.variation_type == "absolute"

    def test_default_variation_type_is_multiplicative(self):
        pv = ParameterVariation(param_path="x", base_value=1.0, variations=[1.0])
        assert pv.variation_type == "multiplicative"


# ---------------------------------------------------------------------------
# ParameterVariation.get_values()
# ---------------------------------------------------------------------------

class TestGetValues:
    def test_multiplicative_values(self):
        pv = ParameterVariation(
            param_path="p", base_value=10.0, variations=[0.9, 1.0, 1.1]
        )
        values = pv.get_values()
        assert values == pytest.approx([9.0, 10.0, 11.0])

    def test_absolute_values(self):
        pv = ParameterVariation(
            param_path="p",
            base_value=5.0,
            variations=[-1.0, 0.0, 1.0],
            variation_type="absolute",
        )
        values = pv.get_values()
        assert values == pytest.approx([4.0, 5.0, 6.0])

    def test_single_variation(self):
        pv = ParameterVariation(param_path="p", base_value=3.0, variations=[2.0])
        assert pv.get_values() == pytest.approx([6.0])


# ---------------------------------------------------------------------------
# ParameterVariation.get_labels()
# ---------------------------------------------------------------------------

class TestGetLabels:
    def test_multiplicative_baseline_label(self):
        pv = ParameterVariation(
            param_path="p", base_value=1.0, variations=[0.9, 1.0, 1.1]
        )
        labels = pv.get_labels()
        assert labels[1] == "baseline"

    def test_multiplicative_non_baseline_label(self):
        pv = ParameterVariation(
            param_path="p", base_value=1.0, variations=[0.8, 1.2]
        )
        labels = pv.get_labels()
        assert "80%" in labels[0]
        assert "120%" in labels[1]

    def test_absolute_labels_contain_value_and_units(self):
        pv = ParameterVariation(
            param_path="p",
            base_value=10.0,
            variations=[-2.0, 0.0, 2.0],
            variation_type="absolute",
            units="MW",
        )
        labels = pv.get_labels()
        assert "8" in labels[0]
        assert "MW" in labels[0]
        assert "10" in labels[1]
        assert "12" in labels[2]

    def test_label_count_matches_variations(self):
        pv = ParameterVariation(param_path="p", base_value=5.0, variations=[0.5, 1.0, 1.5, 2.0])
        assert len(pv.get_labels()) == 4


# ---------------------------------------------------------------------------
# apply_parameter_variation
# ---------------------------------------------------------------------------

class TestApplyParameterVariation:
    def _base_config(self):
        return {"fuels": {"gas": {"price_eur_mwh": 50.0}}, "x": 1}

    def test_updates_nested_value(self):
        cfg = self._base_config()
        new_cfg = apply_parameter_variation(cfg, "fuels.gas.price_eur_mwh", 60.0)
        assert new_cfg["fuels"]["gas"]["price_eur_mwh"] == 60.0

    def test_original_config_unchanged(self):
        cfg = self._base_config()
        apply_parameter_variation(cfg, "fuels.gas.price_eur_mwh", 99.0)
        assert cfg["fuels"]["gas"]["price_eur_mwh"] == 50.0

    def test_top_level_key(self):
        cfg = {"x": 1}
        new_cfg = apply_parameter_variation(cfg, "x", 42)
        assert new_cfg["x"] == 42

    def test_missing_intermediate_key_raises(self):
        cfg = {"a": {"b": 1}}
        with pytest.raises(KeyError, match="c"):
            apply_parameter_variation(cfg, "a.c.d", 5.0)

    def test_missing_final_key_raises(self):
        cfg = {"a": {"b": 1}}
        with pytest.raises(KeyError, match="z"):
            apply_parameter_variation(cfg, "a.z", 5.0)

    def test_deep_copy_isolates_nested_structures(self):
        cfg = {"outer": {"inner": [1, 2, 3]}}
        # Add a leaf float so we can navigate
        cfg["outer"]["val"] = 1.0
        new_cfg = apply_parameter_variation(cfg, "outer.val", 2.0)
        # Mutate nested list in original
        cfg["outer"]["inner"].append(4)
        assert new_cfg["outer"]["inner"] == [1, 2, 3]


# ---------------------------------------------------------------------------
# create_standard_sensitivity_study
# ---------------------------------------------------------------------------

class TestCreateStandardSensitivityStudy:
    def test_returns_list_of_parameter_variations(self):
        study = create_standard_sensitivity_study()
        assert isinstance(study, list)
        assert all(isinstance(s, ParameterVariation) for s in study)

    def test_contains_seven_variations(self):
        study = create_standard_sensitivity_study()
        assert len(study) == 7

    def test_all_have_three_variation_points(self):
        study = create_standard_sensitivity_study()
        for pv in study:
            assert len(pv.variations) == 3

    def test_all_have_param_paths(self):
        study = create_standard_sensitivity_study()
        for pv in study:
            assert "." in pv.param_path  # dot-notation path

    def test_known_param_paths_present(self):
        study = create_standard_sensitivity_study()
        paths = {pv.param_path for pv in study}
        assert "fuels.gas.price_eur_mwh" in paths
        assert "generators.p2h.el_to_th_eff" in paths


# ---------------------------------------------------------------------------
# format_sensitivity_table
# ---------------------------------------------------------------------------

def _make_results_dict(with_baseline: bool = True) -> dict:
    """Build a minimal results dict for format_sensitivity_table tests.

    Uses 'baseline' as the exact label for the centre point so the
    sensitivity-index computation identifies the correct baseline value.
    The outer labels deliberately avoid the word 'baseline' to prevent
    the substring match in calculate_sensitivity_indices from firing on them.
    """
    results = {
        "fuels.gas.price_eur_mwh": [
            SensitivityResult(
                param_path="fuels.gas.price_eur_mwh",
                param_value=46.88,
                variation_label="low (80%)",
                objective_value=900.0,
            ),
            SensitivityResult(
                param_path="fuels.gas.price_eur_mwh",
                param_value=58.6,
                variation_label="baseline",
                objective_value=1000.0,
            ),
            SensitivityResult(
                param_path="fuels.gas.price_eur_mwh",
                param_value=70.32,
                variation_label="high (120%)",
                objective_value=1100.0,
            ),
        ]
    }
    return results


class TestFormatSensitivityTable:
    def test_returns_string(self):
        table = format_sensitivity_table(_make_results_dict())
        assert isinstance(table, str)

    def test_contains_header(self):
        table = format_sensitivity_table(_make_results_dict())
        assert "Parameter" in table
        assert "Variation" in table
        assert "Value" in table

    def test_contains_param_display_name(self):
        table = format_sensitivity_table(_make_results_dict())
        assert "price_eur_mwh" in table

    def test_baseline_row_has_zero_delta(self):
        table = format_sensitivity_table(_make_results_dict())
        # baseline delta should be +0.00
        assert "+0.00" in table

    def test_none_objective_shows_na(self):
        results = {
            "p.q": [
                SensitivityResult(
                    param_path="p.q",
                    param_value=1.0,
                    variation_label="test",
                    objective_value=None,
                    solve_status="error: infeasible",
                )
            ]
        }
        table = format_sensitivity_table(results)
        assert "N/A" in table

    def test_custom_format_spec(self):
        table = format_sensitivity_table(_make_results_dict(), format_spec=".0f")
        assert "1000" in table

    def test_key_metrics_used_when_specified(self):
        results = {
            "p.q": [
                SensitivityResult(
                    param_path="p.q",
                    param_value=1.0,
                    variation_label="baseline",
                    objective_value=100.0,
                    key_metrics={"fuel_cost": 50.0},
                )
            ]
        }
        table = format_sensitivity_table(results, metric_name="fuel_cost")
        assert "50" in table

    def test_empty_results(self):
        table = format_sensitivity_table({})
        assert "Parameter" in table
        assert len(table.splitlines()) == 2  # header + separator only


# ---------------------------------------------------------------------------
# calculate_sensitivity_indices
# ---------------------------------------------------------------------------

class TestCalculateSensitivityIndices:
    def test_basic_index_calculation(self):
        results = _make_results_dict()
        indices = calculate_sensitivity_indices(results)
        # range = 1100 - 900 = 200; baseline = 1000; index = 0.2
        assert "fuels.gas.price_eur_mwh" in indices
        assert indices["fuels.gas.price_eur_mwh"] == pytest.approx(0.2)

    def test_symmetric_variation_nonzero_index(self):
        results = _make_results_dict()
        indices = calculate_sensitivity_indices(results)
        assert indices["fuels.gas.price_eur_mwh"] > 0

    def test_skips_param_with_none_values(self):
        results = {
            "p.q": [
                SensitivityResult(
                    param_path="p.q",
                    param_value=1.0,
                    variation_label="baseline",
                    objective_value=None,
                )
            ]
        }
        indices = calculate_sensitivity_indices(results)
        assert "p.q" not in indices

    def test_skips_param_with_zero_baseline(self):
        results = {
            "p.q": [
                SensitivityResult(
                    param_path="p.q", param_value=0.0,
                    variation_label="baseline", objective_value=0.0
                ),
                SensitivityResult(
                    param_path="p.q", param_value=1.0,
                    variation_label="high", objective_value=10.0
                ),
            ]
        }
        indices = calculate_sensitivity_indices(results)
        # baseline == 0, so index cannot be computed
        assert "p.q" not in indices

    def test_returns_dict(self):
        assert isinstance(calculate_sensitivity_indices(_make_results_dict()), dict)

    def test_empty_results(self):
        assert calculate_sensitivity_indices({}) == {}

    def test_key_metrics_metric(self):
        results = {
            "p.q": [
                SensitivityResult(
                    param_path="p.q", param_value=0.8,
                    variation_label="low", objective_value=None,
                    key_metrics={"fuel_cost": 80.0}
                ),
                SensitivityResult(
                    param_path="p.q", param_value=1.0,
                    variation_label="baseline", objective_value=None,
                    key_metrics={"fuel_cost": 100.0}
                ),
                SensitivityResult(
                    param_path="p.q", param_value=1.2,
                    variation_label="high", objective_value=None,
                    key_metrics={"fuel_cost": 120.0}
                ),
            ]
        }
        indices = calculate_sensitivity_indices(results, metric_name="fuel_cost")
        assert "p.q" in indices
        assert indices["p.q"] == pytest.approx(0.4)  # (120-80)/100
