"""
Unified configuration parser for the CALION district heating framework.

Provides a single config schema where **nodes are the organizing principle**:
assets live at nodes, pipes connect nodes.

Supports three detail levels with zero schema changes between them:
- Level 1 (Copperplate): Single node, no pipes, no physics
- Level 2 (5-node):      Distributed assets, pipes with losses/pressure
- Level 3 (30-node):     Full detailed network

Example (Level 1 — copperplate):
    network:
      nodes:
        system:
          type: producer
          assets: [boiler_1, hp_1]
          demand:
            column: "Waermebedarf MW"

    assets:
      boiler_1:
        type: thermal_generator
        fuel: gas
        capacity_mw: 150.0
        thermal_efficiency: 0.90
      hp_1:
        type: heat_pump
        capacity_mw: 80.0
        cop_default: 3.5

Example (Level 2 — multi-node with pipes):
    network:
      physics:
        heat_loss: true
        pressure_drop: true
      supply_temp_c: 90
      return_temp_c: 55
      ground_temp_c: 10

      nodes:
        plant:
          type: producer
          assets: [boiler_1, hp_1, tes_1]
        north:
          type: consumer
          demand: {column: "demand_north_MW"}
        junction_1:
          type: junction
      pipes:
        plant_to_j1: {from: plant, to: junction_1, length_m: 1200, diameter_mm: 400}
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from calion.logging_config import get_logger

logger = get_logger(__name__)


# ─── Pydantic models ──────────────────────────────────────────────────────────

class DemandConfig(BaseModel):
    """Demand specification for a consumer (or producer-with-demand) node."""

    model_config = ConfigDict(populate_by_name=True)

    column: str

    @staticmethod
    def from_dict(raw: Any) -> DemandConfig:
        if isinstance(raw, str):
            return DemandConfig(column=raw)
        if isinstance(raw, dict):
            col = raw.get("column")
            if not col:
                raise ValueError("demand config must have 'column' key")
            return DemandConfig(column=col)
        raise ValueError(f"Invalid demand config: {raw!r}")


class NodeConfig(BaseModel):
    """Configuration for a single network node."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    type: str  # "producer", "consumer", "junction"
    assets: list[str] = Field(default_factory=list)
    demand: DemandConfig | None = None
    demand_fraction: float | None = Field(default=1.0)  # Default to 100% (no scaling) if not specified

    @staticmethod
    def from_dict(node_id: str, raw: dict[str, Any]) -> NodeConfig:
        node_type = raw.get("type", "junction")
        if node_type not in ("producer", "consumer", "junction"):
            raise ValueError(
                f"Node '{node_id}': type must be producer/consumer/junction, got '{node_type}'"
            )

        assets = raw.get("assets", [])
        if not isinstance(assets, list):
            assets = [assets]

        demand = None
        demand_raw = raw.get("demand")
        if demand_raw is not None:
            demand = DemandConfig.from_dict(demand_raw)

        # Default demand_fraction to 1.0 (100%) if not specified
        # This allows per-node demands to be used without scaling by fraction
        demand_fraction = raw.get("demand_fraction", 1.0)

        return NodeConfig(id=node_id, type=node_type, assets=assets, demand=demand, demand_fraction=demand_fraction)


class PipeConfig(BaseModel):
    """Configuration for a single pipe connecting two nodes."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    from_node: str
    to_node: str
    length_m: float
    diameter_mm: float
    insulation: str | None = None
    u_value_supply_w_per_m_k: float = 0.15
    u_value_return_w_per_m_k: float = 0.15

    @staticmethod
    def from_dict(pipe_id: str, raw: dict[str, Any]) -> PipeConfig:
        from_node = raw.get("from") or raw.get("from_node")
        to_node = raw.get("to") or raw.get("to_node")
        if not from_node or not to_node:
            raise ValueError(f"Pipe '{pipe_id}': must have 'from' and 'to' node references")

        length_m = float(raw.get("length_m", 0))
        if length_m <= 0:
            raise ValueError(f"Pipe '{pipe_id}': length_m must be > 0, got {length_m}")

        diameter_mm = float(raw.get("diameter_mm", 0))
        if diameter_mm <= 0:
            raise ValueError(f"Pipe '{pipe_id}': diameter_mm must be > 0, got {diameter_mm}")

        return PipeConfig(
            id=pipe_id,
            from_node=from_node,
            to_node=to_node,
            length_m=length_m,
            diameter_mm=diameter_mm,
            insulation=raw.get("insulation"),
            u_value_supply_w_per_m_k=float(raw.get("u_value_supply_w_per_m_k", 0.15)),
            u_value_return_w_per_m_k=float(raw.get("u_value_return_w_per_m_k", 0.15)),
        )


class AssetConfig(BaseModel):
    """Generic asset configuration — type field routes to HP/Gen/Storage/P2H."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    type: str  # "heat_pump", "thermal_generator", "storage", "p2h"
    params: dict[str, Any] = Field(default_factory=dict)

    @staticmethod
    def from_dict(asset_id: str, raw: dict[str, Any]) -> AssetConfig:
        asset_type = raw.get("type")
        if not asset_type:
            raise ValueError(f"Asset '{asset_id}': must have 'type' field")
        params = {k: v for k, v in raw.items() if k != "type"}
        return AssetConfig(id=asset_id, type=asset_type, params=params)


class PhysicsConfig(BaseModel):
    """Network physics settings."""

    model_config = ConfigDict(populate_by_name=True)

    heat_loss: bool = False
    pressure_drop: bool = False
    transport_delay: bool = False
    supply_temp_c: float = 90.0
    return_temp_c: float = 55.0
    ground_temp_c: float = 10.0

    @staticmethod
    def from_dict(raw: dict[str, Any] | None, network_raw: dict[str, Any]) -> PhysicsConfig:
        physics = raw or {}
        return PhysicsConfig(
            heat_loss=bool(physics.get("heat_loss", False)),
            pressure_drop=bool(physics.get("pressure_drop", False)),
            transport_delay=bool(physics.get("transport_delay", False)),
            supply_temp_c=float(network_raw.get("supply_temp_c", 90.0)),
            return_temp_c=float(network_raw.get("return_temp_c", 55.0)),
            ground_temp_c=float(network_raw.get("ground_temp_c", 10.0)),
        )


class UnifiedSystemConfig(BaseModel):
    """Top-level parsed configuration for the entire system."""

    model_config = ConfigDict(populate_by_name=True)

    nodes: dict[str, NodeConfig]
    pipes: dict[str, PipeConfig]
    assets: dict[str, AssetConfig]
    physics: PhysicsConfig
    grid: dict[str, Any]
    fuels: dict[str, Any]
    costs: dict[str, Any]
    run: dict[str, Any]
    data: dict[str, Any]
    is_copperplate: bool

    # Raw config preserved for backward-compatible access
    raw: dict[str, Any] = Field(default_factory=dict)

    def node_ids_by_type(self, node_type: str) -> list[str]:
        """Return node IDs of the given type."""
        return [nid for nid, n in self.nodes.items() if n.type == node_type]

    def assets_at_node(self, node_id: str) -> list[AssetConfig]:
        """Return AssetConfig objects for all assets at a given node."""
        node = self.nodes.get(node_id)
        if node is None:
            return []
        return [self.assets[aid] for aid in node.assets if aid in self.assets]

    def consumer_nodes(self) -> dict[str, NodeConfig]:
        """Return all consumer nodes."""
        return {nid: n for nid, n in self.nodes.items() if n.type == "consumer"}

    def producer_nodes(self) -> dict[str, NodeConfig]:
        """Return all producer nodes."""
        return {nid: n for nid, n in self.nodes.items() if n.type == "producer"}


# ─── Parser ───────────────────────────────────────────────────────────────────

def parse_unified_config(cfg: dict[str, Any]) -> UnifiedSystemConfig:
    """Parse a unified config dict into a validated UnifiedSystemConfig.

    Args:
        cfg: Raw configuration dictionary (from YAML loading).

    Returns:
        Fully validated UnifiedSystemConfig.

    Raises:
        ValueError: On missing/invalid configuration.
    """
    issues: list[str] = []

    # ── Assets ────────────────────────────────────────────────────────────
    assets_raw = cfg.get("assets", {})
    if not assets_raw:
        issues.append("'assets' section is required and must not be empty")
    assets: dict[str, AssetConfig] = {}
    for aid, araw in (assets_raw or {}).items():
        try:
            assets[aid] = AssetConfig.from_dict(aid, araw)
        except ValueError as exc:
            issues.append(str(exc))

    # ── Network / Nodes ───────────────────────────────────────────────────
    network_raw = cfg.get("network", {})
    if not network_raw:
        issues.append("'network' section with 'nodes' is required")

    nodes_raw = (network_raw or {}).get("nodes", {})
    if not nodes_raw:
        issues.append("'network.nodes' is required and must not be empty")

    nodes: dict[str, NodeConfig] = {}
    for nid, nraw in (nodes_raw or {}).items():
        try:
            nodes[nid] = NodeConfig.from_dict(nid, nraw)
        except ValueError as exc:
            issues.append(str(exc))

    # ── Pipes ─────────────────────────────────────────────────────────────
    pipes_raw = (network_raw or {}).get("pipes", {})
    pipes: dict[str, PipeConfig] = {}
    for pid, praw in (pipes_raw or {}).items():
        try:
            pipes[pid] = PipeConfig.from_dict(pid, praw)
        except ValueError as exc:
            issues.append(str(exc))

    # ── Physics ───────────────────────────────────────────────────────────
    physics_raw = (network_raw or {}).get("physics")
    physics = PhysicsConfig.from_dict(physics_raw, network_raw or {})

    # ── Cross-reference validation ────────────────────────────────────────

    # 1. All asset references in nodes must point to defined assets
    for nid, node in nodes.items():
        for aid in node.assets:
            if aid not in assets:
                issues.append(
                    f"Node '{nid}' references undefined asset '{aid}'"
                )

    # 2. All pipe from/to must reference existing nodes
    for pid, pipe in pipes.items():
        if pipe.from_node not in nodes:
            issues.append(
                f"Pipe '{pid}': from_node '{pipe.from_node}' is not a defined node"
            )
        if pipe.to_node not in nodes:
            issues.append(
                f"Pipe '{pid}': to_node '{pipe.to_node}' is not a defined node"
            )

    # 3. Every consumer node must have a demand column specified
    for nid, node in nodes.items():
        if node.type == "consumer" and node.demand is None:
            issues.append(
                f"Consumer node '{nid}' must have 'demand.column' specified"
            )

    # 4. At least one producer node
    producer_ids = [nid for nid, n in nodes.items() if n.type == "producer"]
    if not producer_ids and nodes:
        issues.append("At least one producer node is required")

    # ── Fail if validation errors ─────────────────────────────────────────
    if issues:
        raise ValueError(
            f"Unified config validation failed ({len(issues)} issue(s)):\n"
            + "\n".join(f"  - {i}" for i in issues)
        )

    # ── Copperplate detection ─────────────────────────────────────────────
    is_copperplate = len(pipes) == 0

    if is_copperplate:
        logger.info("[CONFIG] Copperplate mode (no pipes) — single-node model")
    else:
        logger.info(
            "[CONFIG] Multi-node mode: %d nodes, %d pipes",
            len(nodes), len(pipes),
        )

    return UnifiedSystemConfig(
        nodes=nodes,
        pipes=pipes,
        assets=assets,
        physics=physics,
        grid=cfg.get("grid", {}),
        fuels=cfg.get("fuels", {}),
        costs=cfg.get("costs", {}),
        run=cfg.get("run", {}),
        data=cfg.get("data", {}),
        is_copperplate=is_copperplate,
        raw=cfg,
    )


# ─── Helpers ─────────────────────────────────────────────────────────────────

def unified_generators_defaults(ucfg: UnifiedSystemConfig) -> dict[str, dict[str, Any]]:
    """Extract generator/p2h defaults for the top-level ``generators`` config key.

    Returns a dict keyed by generator id (lowercase) with th_eff, fuel_bus, etc.
    Used by :mod:`calion.models.component_assembler` during model building.
    """
    result: dict[str, dict[str, Any]] = {}
    for asset in ucfg.assets.values():
        if asset.type == "thermal_generator":
            p = dict(asset.params)
            result[asset.id.lower()] = {
                "th_eff": p.get("thermal_efficiency", 0.9),
                "fuel_bus": p.get("fuel", "gas"),
                "el_eff": p.get("el_eff"),
            }
        elif asset.type == "p2h":
            p = dict(asset.params)
            result["p2h"] = {
                "el_to_th_eff": p.get("efficiency", 0.99),
                "min_load": p.get("min_load", 0.0),
            }
    return result
