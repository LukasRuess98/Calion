"""Tests for energis.api — verify public API surface is importable."""


def test_api_imports():
    from energis.api import (
        load_config,
        validate_config_schema,
        EnerGISConfig,
        run_workflow,
        ScenarioResult,
        RollingHorizonResult,
        WorkflowResult,
        WorkflowPlan,
        InvestmentDecisions,
        Component,
        BaseComponent,
        Bus,
        Flow,
        register_component,
        ComponentRegistry,
        build_model,
    )
    # Verify they are callable / class types
    assert callable(load_config)
    assert callable(run_workflow)
    assert callable(build_model)


def test_top_level_network():
    from energis import Network
    net = Network()
    assert net.dt_h == 1.0
