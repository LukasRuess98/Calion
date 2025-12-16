"""
German Subsidies Module for District Heating

Implements subsidy calculations for:
- BEW (Bundesförderung für effiziente Wärmenetze) - Federal funding for efficient heat networks
- KWKG (Kraft-Wärme-Kopplungsgesetz) - Combined Heat and Power Act
- RED II (Renewable Energy Directive) compliance

Author: EnerGIS Development Team
Date: 2025-12-16

References:
- BEW: https://www.bafa.de/DE/Energie/Energieeffizienz/BEW/bew_node.html
- KWKG 2023: https://www.gesetze-im-internet.de/kwkg_2016/
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class BEWModule(Enum):
    """BEW funding modules."""
    MODULE_1 = "Modul 1: Transformationspläne"  # Transformation plans (up to 50%)
    MODULE_2 = "Modul 2: Systemische Förderung"  # Systemic funding (up to 40%)
    MODULE_3 = "Modul 3: Einzelmaßnahmen"  # Individual measures (up to 40%)
    MODULE_4 = "Modul 4: Betriebskostenförderung"  # Operating cost subsidy


@dataclass
class BEWParameters:
    """BEW subsidy parameters (as of 2024)."""

    # Module 2: Systemic funding rates
    base_rate_percent: float = 40.0  # Base funding rate
    bonus_efficiency_percent: float = 5.0  # Bonus for high efficiency
    bonus_small_network_percent: float = 5.0  # Bonus for small networks (<50 GWh/a)

    # Eligible investment categories and caps
    max_funding_rate_percent: float = 50.0  # Maximum total funding rate

    # Heat pump specific (€/kW thermal)
    hp_eligible_capex_eur_per_kw: float = 800.0  # Reference cost for heat pumps

    # Storage specific (€/m³)
    storage_eligible_capex_eur_per_m3: float = 300.0

    # Network specific (€/m trench)
    network_eligible_capex_eur_per_m: float = 600.0

    # Minimum renewable share for eligibility
    min_renewable_share_percent: float = 75.0  # After transformation


@dataclass
class KWKGParameters:
    """KWKG subsidy parameters (as of 2024)."""

    # CHP bonus rates (ct/kWh)
    chp_bonus_new_ct_per_kwh: float = 8.0  # New CHP plants <50 MW
    chp_bonus_modernized_ct_per_kwh: float = 6.0  # Modernized CHP

    # Network funding (€/m trench for new networks)
    network_new_eur_per_m: float = 100.0  # New heat networks
    network_extension_eur_per_m: float = 70.0  # Network extensions
    network_densification_eur_per_m: float = 30.0  # Densification

    # Duration of funding (years)
    chp_funding_duration_years: int = 30000  # Full load hours
    network_funding_once: bool = True  # One-time payment

    # Eligibility thresholds
    min_chp_efficiency_percent: float = 70.0  # Minimum CHP efficiency


@dataclass
class SubsidyResult:
    """Result of subsidy calculation."""

    # BEW results
    bew_eligible: bool = False
    bew_module: Optional[BEWModule] = None
    bew_investment_subsidy_eur: float = 0.0
    bew_operating_subsidy_eur_per_year: float = 0.0
    bew_funding_rate_percent: float = 0.0

    # KWKG results
    kwkg_chp_subsidy_eur_per_year: float = 0.0
    kwkg_network_subsidy_eur: float = 0.0

    # RED II compliance
    red2_renewable_share_percent: float = 0.0
    red2_compliant: bool = False

    # Totals
    total_investment_subsidy_eur: float = 0.0
    total_annual_subsidy_eur: float = 0.0

    # Details
    details: Dict[str, Any] = field(default_factory=dict)


class GermanSubsidyCalculator:
    """
    Calculator for German district heating subsidies.

    Supports:
    - BEW (Bundesförderung für effiziente Wärmenetze)
    - KWKG (Kraft-Wärme-Kopplungsgesetz)
    - RED II renewable share calculation
    """

    def __init__(
        self,
        bew_params: Optional[BEWParameters] = None,
        kwkg_params: Optional[KWKGParameters] = None,
    ):
        self.bew = bew_params or BEWParameters()
        self.kwkg = kwkg_params or KWKGParameters()

    def calculate_subsidies(
        self,
        investment_data: Dict[str, Any],
        operation_data: Dict[str, Any],
        network_data: Optional[Dict[str, Any]] = None,
    ) -> SubsidyResult:
        """
        Calculate all applicable German subsidies.

        Args:
            investment_data: Dict with investment costs and capacities
                - heat_pump_capacity_kw: Total HP capacity
                - heat_pump_capex_eur: Total HP investment
                - storage_volume_m3: Storage volume
                - storage_capex_eur: Storage investment
                - chp_capacity_kw: CHP capacity
                - chp_capex_eur: CHP investment
                - total_capex_eur: Total investment

            operation_data: Dict with annual operation data
                - heat_demand_mwh: Annual heat demand
                - chp_heat_mwh: Heat from CHP
                - chp_elec_mwh: Electricity from CHP
                - hp_heat_mwh: Heat from heat pumps
                - renewable_heat_mwh: Heat from renewable sources
                - total_heat_mwh: Total heat produced
                - chp_full_load_hours: CHP full load hours

            network_data: Optional dict with network data
                - network_length_m: Total network length
                - new_network_length_m: New pipe length
                - extension_length_m: Extension length
                - densification_length_m: Densification length

        Returns:
            SubsidyResult with all calculated subsidies
        """
        result = SubsidyResult()
        result.details = {}

        # Calculate renewable share (RED II)
        result.red2_renewable_share_percent = self._calculate_renewable_share(operation_data)
        result.red2_compliant = result.red2_renewable_share_percent >= 50.0

        # Calculate BEW subsidies
        bew_result = self._calculate_bew(investment_data, operation_data, result.red2_renewable_share_percent)
        result.bew_eligible = bew_result['eligible']
        result.bew_module = bew_result.get('module')
        result.bew_investment_subsidy_eur = bew_result['investment_subsidy']
        result.bew_operating_subsidy_eur_per_year = bew_result.get('operating_subsidy', 0)
        result.bew_funding_rate_percent = bew_result['funding_rate']
        result.details['bew'] = bew_result

        # Calculate KWKG subsidies
        kwkg_result = self._calculate_kwkg(investment_data, operation_data, network_data)
        result.kwkg_chp_subsidy_eur_per_year = kwkg_result['chp_subsidy']
        result.kwkg_network_subsidy_eur = kwkg_result['network_subsidy']
        result.details['kwkg'] = kwkg_result

        # Calculate totals
        result.total_investment_subsidy_eur = (
            result.bew_investment_subsidy_eur +
            result.kwkg_network_subsidy_eur
        )
        result.total_annual_subsidy_eur = (
            result.bew_operating_subsidy_eur_per_year +
            result.kwkg_chp_subsidy_eur_per_year
        )

        return result

    def _calculate_renewable_share(self, operation_data: Dict[str, Any]) -> float:
        """
        Calculate renewable energy share according to RED II.

        Renewable sources include:
        - Heat pumps (with grid factor)
        - Solar thermal
        - Geothermal
        - Biomass
        - Waste heat (partially)
        """
        total_heat = operation_data.get('total_heat_mwh', 0)
        if total_heat <= 0:
            return 0.0

        renewable_heat = operation_data.get('renewable_heat_mwh', 0)

        # Heat pump contribution (RED II: HP with SPF > 2.5 counts as renewable)
        hp_heat = operation_data.get('hp_heat_mwh', 0)
        hp_spf = operation_data.get('hp_seasonal_performance_factor', 3.5)

        if hp_spf > 2.5:
            # Renewable share = (1 - 1/SPF) * HP_heat
            hp_renewable = hp_heat * (1 - 1/hp_spf)
            renewable_heat += hp_renewable

        # Waste heat (50% counts as renewable in some interpretations)
        waste_heat = operation_data.get('waste_heat_mwh', 0)
        renewable_heat += waste_heat * 0.5

        renewable_share = (renewable_heat / total_heat) * 100
        return min(renewable_share, 100.0)

    def _calculate_bew(
        self,
        investment_data: Dict[str, Any],
        operation_data: Dict[str, Any],
        renewable_share: float
    ) -> Dict[str, Any]:
        """
        Calculate BEW (Bundesförderung für effiziente Wärmenetze) subsidies.

        BEW Module 2 (Systemic funding) criteria:
        - Transformation to >75% renewable by project end
        - New construction or existing network transformation
        """
        result = {
            'eligible': False,
            'module': None,
            'investment_subsidy': 0.0,
            'operating_subsidy': 0.0,
            'funding_rate': 0.0,
            'eligible_costs': {},
        }

        # Check basic eligibility (renewable share after transformation)
        target_renewable = operation_data.get('target_renewable_share_percent', renewable_share)

        if target_renewable < self.bew.min_renewable_share_percent:
            result['rejection_reason'] = (
                f"Renewable share {target_renewable:.1f}% below minimum "
                f"{self.bew.min_renewable_share_percent:.1f}%"
            )
            return result

        result['eligible'] = True
        result['module'] = BEWModule.MODULE_2

        # Calculate funding rate
        funding_rate = self.bew.base_rate_percent

        # Bonus for small networks (<50 GWh/a)
        heat_demand = operation_data.get('heat_demand_mwh', 0) / 1000  # Convert to GWh
        if heat_demand < 50:
            funding_rate += self.bew.bonus_small_network_percent
            result['bonus_small_network'] = True

        # Cap at maximum
        funding_rate = min(funding_rate, self.bew.max_funding_rate_percent)
        result['funding_rate'] = funding_rate

        # Calculate eligible investment costs
        eligible_costs = {}

        # Heat pumps
        hp_capacity_kw = investment_data.get('heat_pump_capacity_kw', 0)
        hp_capex = investment_data.get('heat_pump_capex_eur', 0)
        hp_eligible = min(hp_capex, hp_capacity_kw * self.bew.hp_eligible_capex_eur_per_kw)
        eligible_costs['heat_pumps'] = hp_eligible

        # Storage
        storage_volume = investment_data.get('storage_volume_m3', 0)
        storage_capex = investment_data.get('storage_capex_eur', 0)
        storage_eligible = min(storage_capex, storage_volume * self.bew.storage_eligible_capex_eur_per_m3)
        eligible_costs['storage'] = storage_eligible

        # Network
        network_length = investment_data.get('network_length_m', 0)
        network_capex = investment_data.get('network_capex_eur', 0)
        network_eligible = min(network_capex, network_length * self.bew.network_eligible_capex_eur_per_m)
        eligible_costs['network'] = network_eligible

        # Total eligible costs
        total_eligible = sum(eligible_costs.values())
        result['eligible_costs'] = eligible_costs
        result['total_eligible_costs'] = total_eligible

        # Calculate investment subsidy
        result['investment_subsidy'] = total_eligible * (funding_rate / 100)

        # Module 4: Operating cost subsidy (simplified)
        # For heat pumps: €0.03/kWh for 10 years
        hp_heat = operation_data.get('hp_heat_mwh', 0)
        result['operating_subsidy'] = hp_heat * 1000 * 0.03  # €/year

        return result

    def _calculate_kwkg(
        self,
        investment_data: Dict[str, Any],
        operation_data: Dict[str, Any],
        network_data: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Calculate KWKG (Kraft-Wärme-Kopplungsgesetz) subsidies.

        Covers:
        - CHP bonus for electricity generation
        - Network funding for new/extended networks
        """
        result = {
            'chp_subsidy': 0.0,
            'network_subsidy': 0.0,
            'details': {}
        }

        # CHP bonus calculation
        chp_elec_mwh = operation_data.get('chp_elec_mwh', 0)
        chp_capacity_kw = investment_data.get('chp_capacity_kw', 0)

        if chp_elec_mwh > 0 and chp_capacity_kw > 0:
            # Determine bonus rate based on plant type
            is_new = investment_data.get('chp_is_new', True)

            if is_new:
                bonus_rate = self.kwkg.chp_bonus_new_ct_per_kwh
            else:
                bonus_rate = self.kwkg.chp_bonus_modernized_ct_per_kwh

            # Annual CHP subsidy (€/year)
            chp_subsidy = chp_elec_mwh * 1000 * bonus_rate / 100  # Convert ct to €

            # Cap by full load hours (30,000 hours total)
            full_load_hours = operation_data.get('chp_full_load_hours', 4000)
            years_remaining = max(0, self.kwkg.chp_funding_duration_years / full_load_hours)

            result['chp_subsidy'] = chp_subsidy
            result['details']['chp_bonus_rate_ct'] = bonus_rate
            result['details']['chp_years_remaining'] = years_remaining

        # Network funding
        if network_data:
            network_subsidy = 0.0

            # New network
            new_length = network_data.get('new_network_length_m', 0)
            network_subsidy += new_length * self.kwkg.network_new_eur_per_m

            # Extension
            ext_length = network_data.get('extension_length_m', 0)
            network_subsidy += ext_length * self.kwkg.network_extension_eur_per_m

            # Densification
            dens_length = network_data.get('densification_length_m', 0)
            network_subsidy += dens_length * self.kwkg.network_densification_eur_per_m

            result['network_subsidy'] = network_subsidy
            result['details']['network_new_m'] = new_length
            result['details']['network_extension_m'] = ext_length
            result['details']['network_densification_m'] = dens_length

        return result

    def generate_funding_report(self, result: SubsidyResult) -> str:
        """
        Generate a human-readable funding report.

        Args:
            result: SubsidyResult from calculate_subsidies()

        Returns:
            Formatted report string (Markdown)
        """
        report = []
        report.append("# Förderanalyse – Deutsche Subventionen für Wärmenetze\n")

        # RED II Compliance
        report.append("## 1. RED II Erneuerbare-Energien-Anteil\n")
        report.append(f"- **Erneuerbarer Anteil**: {result.red2_renewable_share_percent:.1f}%")
        if result.red2_compliant:
            report.append(" ✓ RED II konform (≥50%)\n")
        else:
            report.append(" ✗ Nicht RED II konform (<50%)\n")

        # BEW Section
        report.append("\n## 2. BEW – Bundesförderung für effiziente Wärmenetze\n")
        if result.bew_eligible:
            report.append(f"- **Status**: ✓ Förderfähig ({result.bew_module.value if result.bew_module else 'k.A.'})\n")
            report.append(f"- **Fördersatz**: {result.bew_funding_rate_percent:.1f}%\n")
            report.append(f"- **Investitionszuschuss**: {result.bew_investment_subsidy_eur:,.0f} €\n")
            report.append(f"- **Betriebskostenzuschuss**: {result.bew_operating_subsidy_eur_per_year:,.0f} €/Jahr\n")

            if 'bew' in result.details:
                bew = result.details['bew']
                if 'eligible_costs' in bew:
                    report.append("\n**Förderfähige Kosten:**\n")
                    for category, amount in bew['eligible_costs'].items():
                        if amount > 0:
                            report.append(f"  - {category}: {amount:,.0f} €\n")
        else:
            report.append("- **Status**: ✗ Nicht förderfähig\n")
            if 'bew' in result.details and 'rejection_reason' in result.details['bew']:
                report.append(f"- **Grund**: {result.details['bew']['rejection_reason']}\n")

        # KWKG Section
        report.append("\n## 3. KWKG – Kraft-Wärme-Kopplungsgesetz\n")
        if result.kwkg_chp_subsidy_eur_per_year > 0:
            report.append(f"- **KWK-Zuschlag**: {result.kwkg_chp_subsidy_eur_per_year:,.0f} €/Jahr\n")
            if 'kwkg' in result.details and 'chp_bonus_rate_ct' in result.details['kwkg']:
                report.append(f"  - Vergütungssatz: {result.details['kwkg']['chp_bonus_rate_ct']:.1f} ct/kWh\n")
        else:
            report.append("- **KWK-Zuschlag**: Keine KWK-Anlage oder nicht förderfähig\n")

        if result.kwkg_network_subsidy_eur > 0:
            report.append(f"- **Netzförderung**: {result.kwkg_network_subsidy_eur:,.0f} € (einmalig)\n")
        else:
            report.append("- **Netzförderung**: Keine Netzmaßnahmen oder nicht förderfähig\n")

        # Summary
        report.append("\n## 4. Zusammenfassung\n")
        report.append(f"| Kategorie | Betrag |\n")
        report.append(f"|-----------|--------|\n")
        report.append(f"| Investitionszuschüsse (gesamt) | {result.total_investment_subsidy_eur:,.0f} € |\n")
        report.append(f"| Jährliche Zuschüsse (gesamt) | {result.total_annual_subsidy_eur:,.0f} €/Jahr |\n")

        # NPV of subsidies (simplified, 20 years, 3% discount)
        npv_factor = sum(1 / (1.03 ** i) for i in range(20))
        total_npv = result.total_investment_subsidy_eur + result.total_annual_subsidy_eur * npv_factor
        report.append(f"| **Barwert (20 Jahre, 3%)** | **{total_npv:,.0f} €** |\n")

        return "".join(report)


def calculate_subsidies_from_workflow(workflow_result: Any) -> SubsidyResult:
    """
    Calculate subsidies from a completed workflow result.

    Args:
        workflow_result: Result from run_workflow()

    Returns:
        SubsidyResult with all calculated subsidies
    """
    calculator = GermanSubsidyCalculator()

    # Extract investment data from design
    investment_data = {}
    if hasattr(workflow_result, 'design') and workflow_result.design:
        design = workflow_result.design

        # Heat pumps
        if design.heat_pumps:
            hp_capacity = sum(hp.get('cap_th_kw', 0) for hp in design.heat_pumps.values())
            hp_capex = sum(hp.get('capex_eur', 0) for hp in design.heat_pumps.values())
            investment_data['heat_pump_capacity_kw'] = hp_capacity
            investment_data['heat_pump_capex_eur'] = hp_capex

        # Storage
        if design.storage:
            storage = design.storage
            investment_data['storage_volume_m3'] = storage.get('volume_m3', 0)
            investment_data['storage_capex_eur'] = storage.get('capex_eur', 0)

    # Extract operation data from summary
    operation_data = {}
    if hasattr(workflow_result, 'rh_result') and workflow_result.rh_result:
        result = workflow_result.rh_result

        if hasattr(result, 'summary') and result.summary:
            summary = result.summary

            # Grid section
            if 'grid' in summary:
                operation_data['heat_demand_mwh'] = summary['grid'].get('Heat_demand_MWh', 0)

            # Heat pump heat
            hp_heat = 0
            for key, section in summary.items():
                if key.startswith('HP') and isinstance(section, dict):
                    hp_heat += section.get('Heat_produced_MWh', 0)
            operation_data['hp_heat_mwh'] = hp_heat

            # Total heat
            operation_data['total_heat_mwh'] = operation_data.get('heat_demand_mwh', 0)

            # Estimate renewable heat (HP + solar + biomass)
            renewable_heat = hp_heat * 0.7  # Simplified: 70% of HP heat is renewable
            if 'BMHKW' in summary:
                renewable_heat += summary['BMHKW'].get('Heat_produced_MWh', 0)
            operation_data['renewable_heat_mwh'] = renewable_heat

    # Extract network data
    network_data = None
    if hasattr(workflow_result, 'rh_result') and workflow_result.rh_result:
        result = workflow_result.rh_result
        if hasattr(result, 'summary') and 'thermal_network' in result.summary:
            net_summary = result.summary['thermal_network']
            network_data = {
                'network_length_m': net_summary.get('Total_pipe_length_m', 0),
                'new_network_length_m': 0,  # Would need to track this
            }

    return calculator.calculate_subsidies(investment_data, operation_data, network_data)
