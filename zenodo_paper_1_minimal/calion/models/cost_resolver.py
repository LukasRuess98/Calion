"""Zone cost resolver with hierarchical fallback.

Implements cost resolution with three-level hierarchy:
1. Dynamic (CSV-based, timestep-dependent)
2. Zone-specific (static overrides)
3. Global (standard fallback)

Usage:
    resolver = CostResolver(cfg, table)
    zone_charge = resolver.get_zone_cost("zone_01", "demand_charge_eur_per_mw_y", t=5)
"""

from __future__ import annotations

from typing import Any

from calion.logging_config import get_logger

logger = get_logger(__name__)


class CostResolver:
    """Resolve zone costs with fallback chain: dynamic → zone-specific → global."""

    def __init__(self, cfg: dict[str, Any], table: Any | None = None):
        """Initialize cost resolver.

        Args:
            cfg: Configuration dict containing 'costs_config' section
            table: TimeSeriesTable or dict-like object with data columns
                   Required only if dynamic costs are enabled.
        """
        self.cfg = cfg
        self.table = table

        # Extract sections from config
        costs_config = cfg.get("costs_config", {})
        self.global_costs = costs_config.get("global", {})
        self.zone_costs = costs_config.get("zones", {})
        self.dynamic_config = costs_config.get("dynamic", {})

        # Dynamic cost settings
        self.dynamic_enabled = self.dynamic_config.get("enabled", False)
        self.dynamic_mappings = self.dynamic_config.get("mappings", {})

        if self.dynamic_enabled and self.table is None:
            logger.warning("Dynamic costs enabled but no table provided — will fall back to static values")

        logger.info(
            "CostResolver initialized: %d global, %d zone-specific costs, "
            "dynamic enabled=%s",
            len(self.global_costs),
            len(self.zone_costs),
            self.dynamic_enabled,
        )

    def get_zone_cost(
        self,
        zone_id: str,
        cost_type: str,
        timestep: int | None = None,
    ) -> float:
        """Get cost for zone with three-level fallback.

        Precedence order:
        1. Dynamic (CSV column) if enabled and column exists for this timestep
        2. Zone-specific (YAML) if zone defined in costs_config.zones
        3. Global (YAML) standard fallback
        4. 0.0 if not defined anywhere

        Args:
            zone_id: Zone identifier (e.g., "zone_01", "j_north")
            cost_type: Cost key (e.g., "demand_charge_eur_per_mw_y", "energy_fee_eur_per_mwh")
            timestep: Time index (1-based, as in Pyomo) for dynamic lookup.
                     Optional; required only for dynamic costs.

        Returns:
            Cost value in EUR or EUR/MWh depending on cost_type
        """
        # 1. Try dynamic cost (timestep-dependent, highest priority)
        if self.dynamic_enabled and timestep is not None and self.table is not None:
            try:
                cost_value = self._get_dynamic_cost(zone_id, cost_type, timestep)
                if cost_value is not None:
                    logger.debug(
                        "Dynamic cost for %s.%s[t=%d] = %.2f",
                        zone_id,
                        cost_type,
                        timestep,
                        cost_value,
                    )
                    return cost_value
            except (KeyError, IndexError, ValueError) as e:
                logger.debug("Dynamic cost lookup failed: %s", e)

        # 2. Try zone-specific static cost (medium priority)
        if zone_id in self.zone_costs:
            zone_cfg = self.zone_costs[zone_id]
            if cost_type in zone_cfg:
                cost_value = float(zone_cfg[cost_type])
                logger.debug("Zone-specific cost for %s.%s = %.2f", zone_id, cost_type, cost_value)
                return cost_value

        # 3. Fall back to global cost (lowest priority)
        if cost_type in self.global_costs:
            cost_value = float(self.global_costs[cost_type])
            logger.debug("Global cost for %s = %.2f", cost_type, cost_value)
            return cost_value

        # 4. Default to zero with warning if truly not defined
        logger.debug("Cost %s.%s not defined anywhere — defaulting to 0.0", zone_id, cost_type)
        return 0.0

    def _get_dynamic_cost(
        self,
        zone_id: str,
        cost_type: str,
        timestep: int,
    ) -> float | None:
        """Get dynamic cost from CSV table.

        Args:
            zone_id: Zone identifier
            cost_type: Cost type key
            timestep: 1-based time index (convert to 0-based for table access)

        Returns:
            Cost value or None if not found
        """
        # Build CSV column name from mapping
        lookup_key = f"{zone_id}_{cost_type}"
        if lookup_key not in self.dynamic_mappings:
            return None

        csv_column = self.dynamic_mappings[lookup_key]

        # Access table — try different attribute patterns
        if hasattr(self.table, "columns") and csv_column in self.table.columns:
            # TimeSeriesTable with DataFrame
            row_idx = timestep - 1  # 1-based → 0-based
            if 0 <= row_idx < len(self.table[csv_column]):
                return float(self.table[csv_column][row_idx])
        elif isinstance(self.table, dict) and csv_column in self.table:
            # Dict-like table
            if timestep in self.table[csv_column]:
                return float(self.table[csv_column][timestep])

        return None

    def get_all_zones_costs(self) -> dict[str, dict[str, float]]:
        """Get resolved static costs for all zones (no dynamic lookup).

        Useful for reporting and validation.

        Returns:
            Dict mapping zone_id → {cost_type: value}
        """
        zones = {}

        if not self.zone_costs:
            # No zones defined — return global only
            zones["__global__"] = {k: float(v) for k, v in self.global_costs.items()}
            return zones

        # Metadata keys to exclude (not costs)
        METADATA_KEYS = {"type", "description", "id", "name"}

        for zone_id in self.zone_costs.keys():
            zones[zone_id] = {}

            # Collect all possible cost types (excluding metadata)
            zone_keys = set(k for k in self.zone_costs[zone_id].keys() if k not in METADATA_KEYS)
            all_types = set(self.global_costs.keys()) | zone_keys

            for cost_type in all_types:
                try:
                    zones[zone_id][cost_type] = self.get_zone_cost(zone_id, cost_type)
                except (ValueError, TypeError) as e:
                    logger.debug("Failed to resolve cost %s.%s: %s", zone_id, cost_type, e)
                    # Use 0.0 as fallback
                    zones[zone_id][cost_type] = 0.0

        return zones

    def get_zone_type(self, zone_id: str) -> str:
        """Get the 'type' metadata for a zone (e.g., 'premium', 'standard', 'peripheral').

        Args:
            zone_id: Zone identifier

        Returns:
            Zone type string, or "standard" if not defined
        """
        if zone_id in self.zone_costs:
            return str(self.zone_costs[zone_id].get("type", "standard"))
        return "standard"

    def log_resolution_summary(self):
        """Log a summary of cost resolution for all zones (debugging)."""
        logger.info("=" * 70)
        logger.info("COST RESOLUTION SUMMARY")
        logger.info("=" * 70)

        all_costs = self.get_all_zones_costs()
        for zone_id, costs in sorted(all_costs.items()):
            zone_type = self.get_zone_type(zone_id) if zone_id != "__global__" else "system"
            logger.info("")
            logger.info("Zone: %-30s Type: %s", zone_id, zone_type)
            for cost_type, value in sorted(costs.items()):
                logger.info("  %-35s %.2f", cost_type, value)

        logger.info("=" * 70)
