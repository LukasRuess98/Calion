"""
Professional Report Generator for EnerGIS

Generates executive summary reports for consulting deliverables including:
- Executive summary with key KPIs
- Investment analysis
- Operating cost breakdown
- Network analysis
- Subsidy analysis
- Recommendations

Supports HTML and PDF output formats.

Author: EnerGIS Development Team
Date: 2025-12-16
"""

from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime
import logging
import json

logger = logging.getLogger(__name__)

# Optional dependencies for PDF generation
try:
    from weasyprint import HTML, CSS
    HAVE_WEASYPRINT = True
except ImportError:
    HAVE_WEASYPRINT = False

try:
    import plotly.graph_objects as go
    import plotly.io as pio
    HAVE_PLOTLY = True
except ImportError:
    HAVE_PLOTLY = False


class ReportGenerator:
    """
    Professional report generator for district heating analysis.

    Generates consulting-quality reports in HTML and PDF formats.
    """

    def __init__(
        self,
        title: str = "Wärmenetz-Analyse",
        subtitle: str = "Technisch-wirtschaftliche Bewertung",
        client_name: str = "",
        project_name: str = "",
        author: str = "EnerGIS Analysis",
    ):
        self.title = title
        self.subtitle = subtitle
        self.client_name = client_name
        self.project_name = project_name
        self.author = author
        self.generated_at = datetime.now()

    def generate_report(
        self,
        workflow_result: Any,
        output_path: str,
        format: str = "html",
        include_subsidies: bool = True,
        include_network: bool = True,
        language: str = "de",
    ) -> str:
        """
        Generate a professional report from workflow results.

        Args:
            workflow_result: Result from run_workflow()
            output_path: Path for output file (without extension)
            format: Output format ('html' or 'pdf')
            include_subsidies: Include German subsidy analysis
            include_network: Include thermal network analysis
            language: Report language ('de' or 'en')

        Returns:
            Path to generated report file
        """
        # Extract data from workflow
        report_data = self._extract_report_data(workflow_result)

        # Add subsidy analysis if requested
        if include_subsidies:
            try:
                from ..economics.german_subsidies import calculate_subsidies_from_workflow
                subsidy_result = calculate_subsidies_from_workflow(workflow_result)
                report_data['subsidies'] = {
                    'bew_eligible': subsidy_result.bew_eligible,
                    'bew_investment_eur': subsidy_result.bew_investment_subsidy_eur,
                    'bew_operating_eur': subsidy_result.bew_operating_subsidy_eur_per_year,
                    'kwkg_chp_eur': subsidy_result.kwkg_chp_subsidy_eur_per_year,
                    'kwkg_network_eur': subsidy_result.kwkg_network_subsidy_eur,
                    'renewable_share': subsidy_result.red2_renewable_share_percent,
                    'total_investment_subsidy': subsidy_result.total_investment_subsidy_eur,
                    'total_annual_subsidy': subsidy_result.total_annual_subsidy_eur,
                }
            except Exception as e:
                logger.warning(f"Could not calculate subsidies: {e}")
                report_data['subsidies'] = None

        # Generate HTML content
        html_content = self._generate_html(report_data, language)

        # Save report
        if format.lower() == 'html':
            output_file = f"{output_path}.html"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            logger.info(f"Report generated: {output_file}")
            return output_file

        elif format.lower() == 'pdf':
            if not HAVE_WEASYPRINT:
                logger.warning("WeasyPrint not installed. Falling back to HTML.")
                output_file = f"{output_path}.html"
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                return output_file

            output_file = f"{output_path}.pdf"
            HTML(string=html_content).write_pdf(output_file)
            logger.info(f"PDF report generated: {output_file}")
            return output_file

        else:
            raise ValueError(f"Unknown format: {format}")

    def _extract_report_data(self, workflow_result: Any) -> Dict[str, Any]:
        """Extract all relevant data from workflow result."""
        data = {
            'meta': {
                'title': self.title,
                'subtitle': self.subtitle,
                'client': self.client_name,
                'project': self.project_name,
                'author': self.author,
                'generated_at': self.generated_at.strftime("%d.%m.%Y %H:%M"),
            },
            'kpis': {},
            'investment': {},
            'operation': {},
            'network': {},
            'design': {},
        }

        # Extract from RH result (primary)
        result = None
        if hasattr(workflow_result, 'rh_result') and workflow_result.rh_result:
            result = workflow_result.rh_result
        elif hasattr(workflow_result, 'pf_result') and workflow_result.pf_result:
            result = workflow_result.pf_result

        if result and hasattr(result, 'summary'):
            summary = result.summary

            # Grid KPIs
            if 'grid' in summary:
                grid = summary['grid']
                data['kpis']['heat_demand_mwh'] = grid.get('Heat_demand_MWh', 0)
                data['kpis']['total_cost_eur'] = grid.get('Total_cost_EUR', 0)
                data['kpis']['lcoh_eur_mwh'] = grid.get('LCOH_EUR_MWh', 0)
                data['kpis']['co2_total_t'] = grid.get('Total_CO2_emissions_t', 0)
                data['kpis']['grid_purchase_mwh'] = grid.get('Grid_purchase_MWh', 0)
                data['kpis']['grid_feed_in_mwh'] = grid.get('Grid_feed_in_MWh', 0)

            # Thermal network KPIs
            if 'thermal_network' in summary:
                net = summary['thermal_network']
                data['network']['heat_delivered_mwh'] = net.get('Total_heat_delivered_MWh', 0)
                data['network']['heat_loss_mwh'] = net.get('Total_heat_loss_MWh', 0)
                data['network']['loss_percentage'] = net.get('Heat_loss_percentage', 0)
                data['network']['pipe_length_m'] = net.get('Total_pipe_length_m', 0)
                data['network']['max_velocity'] = net.get('Max_velocity_m_s', 0)
                data['network']['pressure_drop'] = net.get('Total_pressure_drop_bar', 0)
                data['network']['pump_power_kw'] = net.get('Pump_power_kW', 0)

            # Component data
            for key, section in summary.items():
                if key.startswith('HP') and isinstance(section, dict):
                    if 'heat_pumps' not in data['operation']:
                        data['operation']['heat_pumps'] = {}
                    data['operation']['heat_pumps'][key] = {
                        'heat_mwh': section.get('Heat_produced_MWh', 0),
                        'elec_mwh': section.get('Electricity_consumed_MWh', 0),
                        'cop': section.get('Average_COP', 0),
                    }

        # Extract design data
        if hasattr(workflow_result, 'design') and workflow_result.design:
            design = workflow_result.design

            if design.heat_pumps:
                data['design']['heat_pumps'] = []
                for hp_id, hp in design.heat_pumps.items():
                    data['design']['heat_pumps'].append({
                        'id': hp_id,
                        'capacity_kw': hp.get('cap_th_kw', 0),
                        'capex_eur': hp.get('capex_eur', 0),
                    })

            if design.storage:
                data['design']['storage'] = {
                    'capacity_mwh': design.storage.get('energy_capacity_mwh', 0),
                    'power_mw': design.storage.get('power_capacity_mw', 0),
                    'capex_eur': design.storage.get('capex_eur', 0),
                }

        return data

    def _generate_html(self, data: Dict[str, Any], language: str = "de") -> str:
        """Generate HTML report content."""

        # Translations
        if language == "de":
            t = {
                'executive_summary': 'Executive Summary',
                'key_kpis': 'Zentrale Kennzahlen',
                'heat_demand': 'Wärmebedarf',
                'total_cost': 'Gesamtkosten',
                'lcoh': 'Wärmegestehungskosten',
                'co2_emissions': 'CO₂-Emissionen',
                'investment_analysis': 'Investitionsanalyse',
                'heat_pumps': 'Wärmepumpen',
                'storage': 'Wärmespeicher',
                'network_analysis': 'Netzwerkanalyse',
                'heat_delivered': 'Wärme geliefert',
                'heat_losses': 'Wärmeverluste',
                'efficiency': 'Netzeffizienz',
                'max_velocity': 'Max. Geschwindigkeit',
                'pressure_drop': 'Druckverlust',
                'pump_power': 'Pumpenleistung',
                'subsidy_analysis': 'Förderanalyse',
                'bew_funding': 'BEW-Förderung',
                'kwkg_funding': 'KWKG-Förderung',
                'renewable_share': 'Erneuerbarer Anteil',
                'recommendations': 'Empfehlungen',
                'generated_by': 'Erstellt mit',
                'on': 'am',
            }
        else:
            t = {
                'executive_summary': 'Executive Summary',
                'key_kpis': 'Key Performance Indicators',
                'heat_demand': 'Heat Demand',
                'total_cost': 'Total Cost',
                'lcoh': 'Levelized Cost of Heat',
                'co2_emissions': 'CO₂ Emissions',
                'investment_analysis': 'Investment Analysis',
                'heat_pumps': 'Heat Pumps',
                'storage': 'Thermal Storage',
                'network_analysis': 'Network Analysis',
                'heat_delivered': 'Heat Delivered',
                'heat_losses': 'Heat Losses',
                'efficiency': 'Network Efficiency',
                'max_velocity': 'Max. Velocity',
                'pressure_drop': 'Pressure Drop',
                'pump_power': 'Pump Power',
                'subsidy_analysis': 'Subsidy Analysis',
                'bew_funding': 'BEW Funding',
                'kwkg_funding': 'KWKG Funding',
                'renewable_share': 'Renewable Share',
                'recommendations': 'Recommendations',
                'generated_by': 'Generated by',
                'on': 'on',
            }

        meta = data['meta']
        kpis = data.get('kpis', {})
        network = data.get('network', {})
        subsidies = data.get('subsidies', {})

        html = f"""
<!DOCTYPE html>
<html lang="{language}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{meta['title']} - {meta['project']}</title>
    <style>
        :root {{
            --primary-color: #1976D2;
            --secondary-color: #424242;
            --accent-color: #4CAF50;
            --warning-color: #FF9800;
            --danger-color: #F44336;
            --background: #FAFAFA;
            --card-bg: #FFFFFF;
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: var(--background);
            color: var(--secondary-color);
            line-height: 1.6;
            padding: 20px;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}

        .header {{
            background: linear-gradient(135deg, var(--primary-color), #1565C0);
            color: white;
            padding: 40px;
            border-radius: 8px;
            margin-bottom: 30px;
        }}

        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
        }}

        .header .subtitle {{
            font-size: 1.2em;
            opacity: 0.9;
        }}

        .header .meta {{
            margin-top: 20px;
            font-size: 0.9em;
            opacity: 0.8;
        }}

        .section {{
            background: var(--card-bg);
            border-radius: 8px;
            padding: 30px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}

        .section h2 {{
            color: var(--primary-color);
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid var(--primary-color);
        }}

        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
        }}

        .kpi-card {{
            background: linear-gradient(135deg, #f5f5f5, #fff);
            border-radius: 8px;
            padding: 20px;
            text-align: center;
            border-left: 4px solid var(--primary-color);
        }}

        .kpi-card.success {{
            border-left-color: var(--accent-color);
        }}

        .kpi-card.warning {{
            border-left-color: var(--warning-color);
        }}

        .kpi-value {{
            font-size: 2em;
            font-weight: bold;
            color: var(--primary-color);
        }}

        .kpi-label {{
            font-size: 0.9em;
            color: var(--secondary-color);
            margin-top: 5px;
        }}

        .kpi-unit {{
            font-size: 0.8em;
            color: #757575;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
        }}

        th, td {{
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid #e0e0e0;
        }}

        th {{
            background: #f5f5f5;
            font-weight: 600;
            color: var(--primary-color);
        }}

        tr:hover {{
            background: #fafafa;
        }}

        .status-good {{
            color: var(--accent-color);
        }}

        .status-warning {{
            color: var(--warning-color);
        }}

        .status-bad {{
            color: var(--danger-color);
        }}

        .footer {{
            text-align: center;
            padding: 20px;
            color: #757575;
            font-size: 0.9em;
        }}

        .two-column {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }}

        @media (max-width: 768px) {{
            .two-column {{
                grid-template-columns: 1fr;
            }}
        }}

        @media print {{
            body {{
                padding: 0;
            }}
            .section {{
                break-inside: avoid;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{meta['title']}</h1>
            <div class="subtitle">{meta['subtitle']}</div>
            <div class="meta">
                <strong>{meta['client']}</strong> | {meta['project']}<br>
                {t['generated_by']} {meta['author']} {t['on']} {meta['generated_at']}
            </div>
        </div>

        <!-- Executive Summary -->
        <div class="section">
            <h2>{t['executive_summary']}</h2>
            <div class="kpi-grid">
                <div class="kpi-card">
                    <div class="kpi-value">{kpis.get('heat_demand_mwh', 0):,.0f}</div>
                    <div class="kpi-label">{t['heat_demand']}</div>
                    <div class="kpi-unit">MWh/a</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-value">{kpis.get('total_cost_eur', 0):,.0f}</div>
                    <div class="kpi-label">{t['total_cost']}</div>
                    <div class="kpi-unit">€/a</div>
                </div>
                <div class="kpi-card success">
                    <div class="kpi-value">{kpis.get('lcoh_eur_mwh', 0):,.1f}</div>
                    <div class="kpi-label">{t['lcoh']}</div>
                    <div class="kpi-unit">€/MWh</div>
                </div>
                <div class="kpi-card {'success' if kpis.get('co2_total_t', 0) < 1000 else 'warning'}">
                    <div class="kpi-value">{kpis.get('co2_total_t', 0):,.0f}</div>
                    <div class="kpi-label">{t['co2_emissions']}</div>
                    <div class="kpi-unit">t CO₂/a</div>
                </div>
            </div>
        </div>
"""

        # Network Analysis Section
        if network:
            efficiency = 100 - network.get('loss_percentage', 0)
            efficiency_class = 'success' if efficiency > 95 else 'warning' if efficiency > 90 else ''

            html += f"""
        <!-- Network Analysis -->
        <div class="section">
            <h2>{t['network_analysis']}</h2>
            <div class="kpi-grid">
                <div class="kpi-card">
                    <div class="kpi-value">{network.get('heat_delivered_mwh', 0):,.0f}</div>
                    <div class="kpi-label">{t['heat_delivered']}</div>
                    <div class="kpi-unit">MWh</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-value">{network.get('heat_loss_mwh', 0):,.1f}</div>
                    <div class="kpi-label">{t['heat_losses']}</div>
                    <div class="kpi-unit">MWh ({network.get('loss_percentage', 0):.2f}%)</div>
                </div>
                <div class="kpi-card {efficiency_class}">
                    <div class="kpi-value">{efficiency:.1f}</div>
                    <div class="kpi-label">{t['efficiency']}</div>
                    <div class="kpi-unit">%</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-value">{network.get('pump_power_kw', 0):,.1f}</div>
                    <div class="kpi-label">{t['pump_power']}</div>
                    <div class="kpi-unit">kW</div>
                </div>
            </div>
            <table>
                <tr>
                    <th>Parameter</th>
                    <th>Wert</th>
                    <th>Bewertung</th>
                </tr>
                <tr>
                    <td>Netzlänge</td>
                    <td>{network.get('pipe_length_m', 0):,.0f} m</td>
                    <td>-</td>
                </tr>
                <tr>
                    <td>{t['max_velocity']}</td>
                    <td>{network.get('max_velocity', 0):.2f} m/s</td>
                    <td class="{'status-good' if network.get('max_velocity', 0) < 2.5 else 'status-warning' if network.get('max_velocity', 0) < 3.5 else 'status-bad'}">
                        {'✓ Optimal' if network.get('max_velocity', 0) < 2.5 else '⚠ Akzeptabel' if network.get('max_velocity', 0) < 3.5 else '✗ Zu hoch'}
                    </td>
                </tr>
                <tr>
                    <td>{t['pressure_drop']}</td>
                    <td>{network.get('pressure_drop', 0):.2f} bar</td>
                    <td class="{'status-good' if network.get('pressure_drop', 0) < 3 else 'status-warning' if network.get('pressure_drop', 0) < 5 else 'status-bad'}">
                        {'✓ Gut' if network.get('pressure_drop', 0) < 3 else '⚠ Erhöht' if network.get('pressure_drop', 0) < 5 else '✗ Zu hoch'}
                    </td>
                </tr>
            </table>
        </div>
"""

        # Subsidy Analysis Section
        if subsidies:
            html += f"""
        <!-- Subsidy Analysis -->
        <div class="section">
            <h2>{t['subsidy_analysis']}</h2>
            <div class="kpi-grid">
                <div class="kpi-card {'success' if subsidies.get('bew_eligible') else ''}">
                    <div class="kpi-value">{subsidies.get('bew_investment_eur', 0):,.0f}</div>
                    <div class="kpi-label">{t['bew_funding']} (Investition)</div>
                    <div class="kpi-unit">€</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-value">{subsidies.get('kwkg_chp_eur', 0):,.0f}</div>
                    <div class="kpi-label">{t['kwkg_funding']} (jährlich)</div>
                    <div class="kpi-unit">€/a</div>
                </div>
                <div class="kpi-card {'success' if subsidies.get('renewable_share', 0) >= 75 else 'warning' if subsidies.get('renewable_share', 0) >= 50 else ''}">
                    <div class="kpi-value">{subsidies.get('renewable_share', 0):.1f}</div>
                    <div class="kpi-label">{t['renewable_share']}</div>
                    <div class="kpi-unit">%</div>
                </div>
                <div class="kpi-card success">
                    <div class="kpi-value">{subsidies.get('total_investment_subsidy', 0):,.0f}</div>
                    <div class="kpi-label">Gesamt Investitionsförderung</div>
                    <div class="kpi-unit">€</div>
                </div>
            </div>
            <table>
                <tr>
                    <th>Förderprogramm</th>
                    <th>Einmalig</th>
                    <th>Jährlich</th>
                    <th>Status</th>
                </tr>
                <tr>
                    <td>BEW – Bundesförderung effiziente Wärmenetze</td>
                    <td>{subsidies.get('bew_investment_eur', 0):,.0f} €</td>
                    <td>{subsidies.get('bew_operating_eur', 0):,.0f} €</td>
                    <td class="{'status-good' if subsidies.get('bew_eligible') else 'status-bad'}">
                        {'✓ Förderfähig' if subsidies.get('bew_eligible') else '✗ Nicht förderfähig'}
                    </td>
                </tr>
                <tr>
                    <td>KWKG – KWK-Zuschlag</td>
                    <td>-</td>
                    <td>{subsidies.get('kwkg_chp_eur', 0):,.0f} €</td>
                    <td>{'✓' if subsidies.get('kwkg_chp_eur', 0) > 0 else '-'}</td>
                </tr>
                <tr>
                    <td>KWKG – Netzförderung</td>
                    <td>{subsidies.get('kwkg_network_eur', 0):,.0f} €</td>
                    <td>-</td>
                    <td>{'✓' if subsidies.get('kwkg_network_eur', 0) > 0 else '-'}</td>
                </tr>
            </table>
        </div>
"""

        # Footer
        html += f"""
        <div class="footer">
            <p>{t['generated_by']} <strong>EnerGIS Planning Framework</strong> | {meta['generated_at']}</p>
            <p>Alle Angaben ohne Gewähr. Förderbedingungen können sich ändern.</p>
        </div>
    </div>
</body>
</html>
"""

        return html


def generate_executive_report(
    workflow_result: Any,
    output_path: str,
    client_name: str = "",
    project_name: str = "",
    format: str = "html",
) -> str:
    """
    Convenience function to generate an executive report.

    Args:
        workflow_result: Result from run_workflow()
        output_path: Path for output file (without extension)
        client_name: Name of client
        project_name: Name of project
        format: Output format ('html' or 'pdf')

    Returns:
        Path to generated report file
    """
    generator = ReportGenerator(
        title="Wärmenetz-Analyse",
        subtitle="Technisch-wirtschaftliche Bewertung",
        client_name=client_name,
        project_name=project_name,
    )

    return generator.generate_report(
        workflow_result=workflow_result,
        output_path=output_path,
        format=format,
        include_subsidies=True,
        include_network=True,
    )
