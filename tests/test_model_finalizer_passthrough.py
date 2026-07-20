from types import SimpleNamespace

from calion.models.model_finalizer import CostFlags, ModelFinalizer


def _mk_node(node_type: str):
    return SimpleNamespace(
        type=node_type,
        demands=[],
        demand=None,
        demand_fraction=None,
        assets=[],
    )


def _mk_pipe(from_node: str, to_node: str):
    return SimpleNamespace(
        from_node=from_node,
        to_node=to_node,
        length_m=100.0,
        diameter_mm=150.0,
        u_value_supply_w_per_m_k=0.32,
        u_value_return_w_per_m_k=0.34,
    )


def test_unified_network_cfg_preserves_return_v2_and_warmup_overrides():
    cfg = {
        "network": {
            "physics": {"heat_loss": True, "pressure_drop": False, "transport_delay": False},
            "nodes": {
                "j_2": {
                    "return_model_mode": "stateful_v2",
                    "return_v2_params": {"a0": 56.9, "a_q": 1.0, "a_out": 0.1, "a_sup": 0.05, "alpha": 0.4},
                    "return_state_init_c": 57.5,
                    "return_v2_outdoor_profile": {1: 4.0, 2: 3.8},
                    "return_state_penalty_eur_per_c": 2500.0,
                    "return_link_penalty_eur_per_c": 5000.0,
                    "flow_anchor_profile_kg_s": {1: 4.2, 2: 4.4},
                    "flow_anchor_penalty_eur_per_kg_s": 800.0,
                    "allow_heat_demand_slack": True,
                    "max_heat_demand_slack_frac": 0.02,
                    "max_heat_demand_slack_abs_mw": 0.03,
                    "demand_slack_penalty_eur_per_mwh": 1.0e6,
                }
            },
            "pipes": {
                "j1_to_j2": {
                    "heat_loss_flow_guard_kg_s": 0.05,
                    "stagnation_mode": "binary",
                    "stagnation_flow_threshold_kg_s": 0.02,
                    "summer_warmup_hours": 3,
                    "summer_warmup_penalty_eur_per_mwh": 2.0e6,
                    "summer_warmup_flow_relax_kg_s": 1.0,
                    "summer_warmup_flow_penalty_eur_per_kg_s": 5.0e5,
                }
            },
        }
    }
    finalizer = ModelFinalizer(
        model=None,
        cfg=cfg,
        table=[],
        buses=SimpleNamespace(),
        dt_h=1.0,
        flags=CostFlags(),
        unified_config=None,
        system_buses=None,
    )

    ucfg = SimpleNamespace(
        nodes={"j_1": _mk_node("mixed"), "j_2": _mk_node("consumer")},
        pipes={"j1_to_j2": _mk_pipe("j_1", "j_2")},
        physics=SimpleNamespace(supply_temp_c=86.0, return_temp_c=56.9, ground_temp_c=10.0),
    )

    net_cfg = finalizer._unified_to_network_cfg(ucfg)
    node_by_id = {n["id"]: n for n in net_cfg["nodes"]}
    pipe_by_id = {p["id"]: p for p in net_cfg["pipes"]}

    n2 = node_by_id["j_2"]
    assert n2["return_model_mode"] == "stateful_v2"
    assert n2["return_state_init_c"] == 57.5
    assert "return_v2_params" in n2 and "alpha" in n2["return_v2_params"]
    assert n2["flow_anchor_penalty_eur_per_kg_s"] == 800.0
    assert n2["allow_heat_demand_slack"] is True
    assert n2["max_heat_demand_slack_frac"] == 0.02
    assert n2["max_heat_demand_slack_abs_mw"] == 0.03
    assert n2["demand_slack_penalty_eur_per_mwh"] == 1.0e6

    p12 = pipe_by_id["j1_to_j2"]
    assert p12["stagnation_mode"] == "binary"
    assert p12["summer_warmup_hours"] == 3
    assert p12["summer_warmup_penalty_eur_per_mwh"] == 2.0e6
    assert p12["summer_warmup_flow_relax_kg_s"] == 1.0
    assert p12["summer_warmup_flow_penalty_eur_per_kg_s"] == 5.0e5
