"""
Tests for the InvestmentCalculator service.

Verifies that:
1. Annualization factor is computed correctly
2. Component cost expressions are created for all flags
3. Storage cost expressions handle energy/power split
4. Results match the original duplicated logic in system_builder.py
"""
import pytest

try:
    import pyomo.environ as pyo
    HAVE_PYOMO = True
except ImportError:
    HAVE_PYOMO = False
    pyo = None

from calion.models.investment_calculator import (
    InvestmentCalculator,
    ComponentInvestmentConfig,
    StorageInvestmentConfig,
    InvestmentTerms,
)


class TestAnnualizationFactor:
    """Tests for annual_factor() method."""

    def test_standard_annualization(self):
        """annual_factor should compute period_frac / lifetime."""
        calc = InvestmentCalculator(period_frac=1.0)
        assert calc.annual_factor(20.0) == pytest.approx(1.0 / 20.0)

    def test_partial_year(self):
        """Partial year (rolling horizon) should scale correctly."""
        # 8760 hours * 0.25 = one quarter of a year
        period_frac = 0.25
        calc = InvestmentCalculator(period_frac=period_frac)
        assert calc.annual_factor(20.0) == pytest.approx(0.25 / 20.0)

    def test_zero_lifetime_returns_zero(self):
        """Zero lifetime should return 0.0 safely."""
        calc = InvestmentCalculator(period_frac=1.0)
        assert calc.annual_factor(0.0) == 0.0

    def test_negative_lifetime_returns_zero(self):
        """Negative lifetime should return 0.0 safely."""
        calc = InvestmentCalculator(period_frac=1.0)
        assert calc.annual_factor(-5.0) == 0.0


class TestComponentCosts:
    """Tests for calculate_component_costs() method."""

    def test_all_terms_with_all_flags_enabled(self):
        """All cost terms should appear when all flags enabled."""
        calc = InvestmentCalculator(
            period_frac=1.0,
            include_capex=True,
            include_activation=True,
            include_tie_breaker=True,
        )
        config = ComponentInvestmentConfig(
            capex_eur_per_mw=100000.0,
            activation_cost_eur=5000.0,
            tie_breaker_eur_per_mw=0.01,
            lifetime_years=20.0,
        )

        # Use float scalars to simulate Pyomo variable expressions
        cap = 5.0
        build = 1.0
        terms = calc.calculate_component_costs(cap, build, config)

        assert len(terms.capex) == 1
        assert len(terms.activation) == 1
        assert len(terms.tie_breaker) == 1
        assert len(terms.storage_install) == 0

    def test_capex_value_matches_formula(self):
        """Capex term should be cap * capex_per_mw * annual_factor."""
        calc = InvestmentCalculator(period_frac=1.0)
        config = ComponentInvestmentConfig(
            capex_eur_per_mw=100000.0,
            activation_cost_eur=0.0,
            tie_breaker_eur_per_mw=0.0,
            lifetime_years=20.0,
        )

        cap = 5.0
        build = 1.0
        terms = calc.calculate_component_costs(cap, build, config)

        expected_af = 1.0 / 20.0
        expected_capex = 5.0 * 100000.0 * expected_af

        assert len(terms.capex) == 1
        assert terms.capex[0] == pytest.approx(expected_capex)

    def test_activation_excluded_when_flag_off(self):
        """Activation terms should not appear when include_activation=False."""
        calc = InvestmentCalculator(
            period_frac=1.0,
            include_activation=False,
        )
        config = ComponentInvestmentConfig(
            capex_eur_per_mw=100000.0,
            activation_cost_eur=5000.0,
            tie_breaker_eur_per_mw=0.0,
            lifetime_years=20.0,
        )

        terms = calc.calculate_component_costs(5.0, 1.0, config)

        assert len(terms.activation) == 0

    def test_capex_excluded_when_flag_off(self):
        """Capex terms should not appear when include_capex=False."""
        calc = InvestmentCalculator(period_frac=1.0, include_capex=False)
        config = ComponentInvestmentConfig(
            capex_eur_per_mw=100000.0,
            activation_cost_eur=0.0,
            tie_breaker_eur_per_mw=0.0,
            lifetime_years=20.0,
        )

        terms = calc.calculate_component_costs(5.0, 1.0, config)
        assert len(terms.capex) == 0

    def test_zero_capex_produces_no_term(self):
        """Zero capex should produce no cost term to avoid adding zeros."""
        calc = InvestmentCalculator(period_frac=1.0)
        config = ComponentInvestmentConfig(
            capex_eur_per_mw=0.0,
            activation_cost_eur=0.0,
            tie_breaker_eur_per_mw=0.0,
            lifetime_years=20.0,
        )

        terms = calc.calculate_component_costs(5.0, 1.0, config)

        # Empty lists when all costs are zero
        assert len(terms.capex) == 0
        assert len(terms.activation) == 0
        assert len(terms.tie_breaker) == 0


class TestStorageCosts:
    """Tests for calculate_storage_costs() method."""

    def test_energy_and_power_both_contribute(self):
        """Both energy and power CAPEX should be included."""
        calc = InvestmentCalculator(period_frac=1.0)
        config = StorageInvestmentConfig(
            energy_capex_eur_per_mwh=50000.0,
            power_capex_eur_per_mw=20000.0,
            activation_cost_eur=1000.0,
            tie_breaker_eur_per_mwh=0.01,
            installation_cost_share=0.0,
            lifetime_years=25.0,
        )

        terms = calc.calculate_storage_costs(
            energy_cap_var=100.0,  # 100 MWh
            power_cap_var=10.0,   # 10 MW
            build_var=1.0,
            config=config,
        )

        # Capex should have 2 terms (energy + power)
        assert len(terms.capex) == 2
        assert len(terms.activation) == 1
        assert len(terms.tie_breaker) == 1

    def test_installation_cost_included(self):
        """Installation cost should be added when share > 0."""
        calc = InvestmentCalculator(
            period_frac=1.0,
            include_storage_install=True
        )
        config = StorageInvestmentConfig(
            energy_capex_eur_per_mwh=50000.0,
            power_capex_eur_per_mw=0.0,
            activation_cost_eur=0.0,
            tie_breaker_eur_per_mwh=0.0,
            installation_cost_share=0.15,
            lifetime_years=25.0,
        )

        terms = calc.calculate_storage_costs(
            energy_cap_var=100.0,
            power_cap_var=None,
            build_var=None,
            config=config,
        )

        assert len(terms.storage_install) == 1

    def test_installation_cost_excluded_when_flag_off(self):
        """Installation cost should not appear when include_storage_install=False."""
        calc = InvestmentCalculator(
            period_frac=1.0,
            include_storage_install=False
        )
        config = StorageInvestmentConfig(
            energy_capex_eur_per_mwh=50000.0,
            power_capex_eur_per_mw=0.0,
            activation_cost_eur=0.0,
            tie_breaker_eur_per_mwh=0.0,
            installation_cost_share=0.15,
            lifetime_years=25.0,
        )

        terms = calc.calculate_storage_costs(
            energy_cap_var=100.0,
            power_cap_var=None,
            build_var=None,
            config=config,
        )

        assert len(terms.storage_install) == 0

    def test_none_vars_are_skipped(self):
        """None capacity vars should produce no cost terms."""
        calc = InvestmentCalculator(period_frac=1.0)
        config = StorageInvestmentConfig(
            energy_capex_eur_per_mwh=50000.0,
            power_capex_eur_per_mw=20000.0,
            activation_cost_eur=1000.0,
            tie_breaker_eur_per_mwh=0.0,
            lifetime_years=25.0,
        )

        terms = calc.calculate_storage_costs(
            energy_cap_var=None,
            power_cap_var=None,
            build_var=None,
            config=config,
        )

        assert len(terms.capex) == 0
        assert len(terms.activation) == 0


class TestConfigExtraction:
    """Tests for config extraction static methods."""

    def test_extract_component_config_uses_defaults(self):
        """extract_component_config should fall back to defaults."""
        inv_cfg = {}
        inv_defaults = {
            "capex_eur_per_mw": 80000.0,
            "activation_cost_eur": 3000.0,
            "tie_breaker_eur_per_mw": 0.01,
            "lifetime_years": 15.0,
        }

        config = InvestmentCalculator.extract_component_config(inv_cfg, inv_defaults)

        assert config.capex_eur_per_mw == 80000.0
        assert config.activation_cost_eur == 3000.0
        assert config.lifetime_years == 15.0

    def test_extract_component_config_overrides_defaults(self):
        """inv_cfg should override inv_defaults."""
        inv_cfg = {"capex_eur_per_mw": 120000.0}
        inv_defaults = {"capex_eur_per_mw": 80000.0}

        config = InvestmentCalculator.extract_component_config(inv_cfg, inv_defaults)
        assert config.capex_eur_per_mw == 120000.0

    def test_extract_storage_config_uses_defaults(self):
        """extract_storage_config should fall back to defaults."""
        inv_cfg = {}
        inv_defaults = {
            "energy_capex_eur_per_mwh": 45000.0,
            "power_capex_eur_per_mw": 15000.0,
            "lifetime_years": 30.0,
        }

        config = InvestmentCalculator.extract_storage_config(inv_cfg, inv_defaults)

        assert config.energy_capex_eur_per_mwh == 45000.0
        assert config.power_capex_eur_per_mw == 15000.0
        assert config.lifetime_years == 30.0


class TestRegressionVsLegacy:
    """Regression tests comparing new service vs original system_builder logic."""

    def test_hp_capex_matches_legacy_formula(self):
        """HP investment cost should match original calculation."""
        period_frac = 0.5  # half year
        cap = 8.0  # 8 MW
        build = 1.0

        # Legacy calculation (from system_builder.py lines 314-328)
        lifetime = 20.0
        capex = 100000.0
        activation = 5000.0
        tie_breaker = 0.01

        annual_factor = period_frac / lifetime
        legacy_capex = cap * capex * annual_factor
        legacy_activation = build * activation * annual_factor
        legacy_tie_breaker = cap * tie_breaker

        # New service calculation
        calc = InvestmentCalculator(period_frac=period_frac)
        config = ComponentInvestmentConfig(
            capex_eur_per_mw=capex,
            activation_cost_eur=activation,
            tie_breaker_eur_per_mw=tie_breaker,
            lifetime_years=lifetime,
        )
        terms = calc.calculate_component_costs(cap, build, config)

        assert terms.capex[0] == pytest.approx(legacy_capex)
        assert terms.activation[0] == pytest.approx(legacy_activation)
        assert terms.tie_breaker[0] == pytest.approx(legacy_tie_breaker)

    def test_storage_capex_matches_legacy_formula(self):
        """Storage investment cost should match original calculation."""
        period_frac = 1.0
        e_cap = 50.0  # 50 MWh
        p_cap = 10.0  # 10 MW
        build = 1.0

        # Legacy calculation (from system_builder.py lines 748-776)
        lifetime = 25.0
        e_capex = 45000.0
        p_capex = 15000.0
        activation = 2000.0

        annual_factor = period_frac / lifetime
        legacy_e_capex = e_cap * e_capex * annual_factor
        legacy_p_capex = p_cap * p_capex * annual_factor
        legacy_activation = build * activation * annual_factor

        # New service calculation
        calc = InvestmentCalculator(period_frac=period_frac)
        config = StorageInvestmentConfig(
            energy_capex_eur_per_mwh=e_capex,
            power_capex_eur_per_mw=p_capex,
            activation_cost_eur=activation,
            tie_breaker_eur_per_mwh=0.0,
            lifetime_years=lifetime,
        )
        terms = calc.calculate_storage_costs(e_cap, p_cap, build, config)

        # capex list has 2 items: energy + power
        assert len(terms.capex) == 2
        total_legacy_capex = legacy_e_capex + legacy_p_capex
        total_new_capex = sum(terms.capex)

        assert total_new_capex == pytest.approx(total_legacy_capex)
        assert terms.activation[0] == pytest.approx(legacy_activation)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
