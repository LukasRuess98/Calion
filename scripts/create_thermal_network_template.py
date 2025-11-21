#!/usr/bin/env python3
"""Script to create an Excel template for thermal network configuration.

This script creates a multi-sheet Excel file with all necessary sheets
and column headers for defining a thermal network (Brownfield or Greenfield).

Usage:
    python scripts/create_thermal_network_template.py
    python scripts/create_thermal_network_template.py --output templates/my_template.xlsx
"""

import argparse
from pathlib import Path


def create_template_with_openpyxl(output_path: Path) -> None:
    """Create template using openpyxl library."""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment
    except ImportError:
        print("ERROR: openpyxl not installed. Install with: pip install openpyxl")
        print("Falling back to simple template creation...")
        create_template_simple(output_path)
        return

    wb = Workbook()
    wb.remove(wb.active)  # Remove default sheet

    # Styling
    header_font = Font(bold=True, size=11)
    header_fill = PatternFill(start_color="CCE5FF", end_color="CCE5FF", fill_type="solid")
    center_align = Alignment(horizontal="center", vertical="center")

    # ========== Sheet 1: Netzwerk ==========
    ws_network = wb.create_sheet("Netzwerk")
    ws_network.append(["Parameter", "Wert", "Einheit", "Beschreibung"])

    # Apply header styling
    for cell in ws_network[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align

    # Add example data
    network_data = [
        ["Name", "Musterhausen", "", "Name des Wärmenetzes"],
        ["T_Vorlauf_nom", 90.0, "°C", "Nominale Vorlauftemperatur"],
        ["T_Ruecklauf_nom", 50.0, "°C", "Nominale Rücklauftemperatur"],
        ["p_nominal", 6.0, "bar", "Nominaler Netzdruck"],
        ["Netztyp", "district_heating", "", "district_heating | building_network"],
        ["Optimierungsmodus", "cost", "", "cost | emissions | exergy"],
    ]

    for row in network_data:
        ws_network.append(row)

    # Set column widths
    ws_network.column_dimensions['A'].width = 25
    ws_network.column_dimensions['B'].width = 20
    ws_network.column_dimensions['C'].width = 10
    ws_network.column_dimensions['D'].width = 40

    # ========== Sheet 2: Erzeuger ==========
    ws_producers = wb.create_sheet("Erzeuger")
    producer_headers = [
        "ID", "Typ", "Bestand?", "Investition?", "Q_nom_MW", "Q_options_MW",
        "CAPEX_€_kW", "OPEX_fix_€_kW_a", "OPEX_var_€_MWh",
        "Wirkungsgrad", "COP", "Brennstoff",
        "Vorlauf_Knoten", "Ruecklauf_Knoten"
    ]
    ws_producers.append(producer_headers)

    # Apply header styling
    for cell in ws_producers[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align

    # Add example data
    producer_examples = [
        ["Kessel_1", "boiler", "ja", "nein", 5.0, "", 300, 15, 25, 0.95, "", "gas", "N1", "N1_R"],
        ["WP_1", "heat_pump", "nein", "ja", "", "1.0,2.0,3.0", 800, 20, 5, "", 3.5, "electricity", "N2", "N2_R"],
        ["BHKW_1", "chp", "ja", "nein", 2.0, "", 1200, 30, 20, 0.85, "", "gas", "N1", "N1_R"],
    ]

    for row in producer_examples:
        ws_producers.append(row)

    # Set column widths
    for col in range(1, len(producer_headers) + 1):
        ws_producers.column_dimensions[chr(64 + col)].width = 15

    # ========== Sheet 3: Speicher ==========
    ws_storage = wb.create_sheet("Speicher")
    storage_headers = [
        "ID", "Typ", "Bestand?", "Investition?",
        "Kapazitaet_MWh", "Kapazitaet_options_MWh",
        "T_max_C", "T_min_C", "Verlustrate_1_h",
        "CAPEX_€_kWh", "OPEX_fix_€_kWh_a",
        "Vorlauf_Knoten", "Ruecklauf_Knoten"
    ]
    ws_storage.append(storage_headers)

    # Apply header styling
    for cell in ws_storage[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align

    # Add example data
    storage_examples = [
        ["Speicher_1", "hot_water_tank", "ja", "nein", 10.0, "", 95, 40, 0.001, 50, 1, "N3", "N3_R"],
        ["Speicher_2", "hot_water_tank", "nein", "ja", "", "5,10,20", 95, 40, 0.001, 50, 1, "N4", "N4_R"],
    ]

    for row in storage_examples:
        ws_storage.append(row)

    # Set column widths
    for col in range(1, len(storage_headers) + 1):
        ws_storage.column_dimensions[chr(64 + col)].width = 18

    # ========== Sheet 4: Rohre ==========
    ws_pipes = wb.create_sheet("Rohre")
    pipe_headers = [
        "ID", "Von_Knoten", "Zu_Knoten", "Laenge_m", "Bestand?", "Investition?",
        "DN_fix", "Daemmung_fix", "Baujahr", "Zustand",
        "DN_options", "Daemmung_options", "CAPEX_€_m"
    ]
    ws_pipes.append(pipe_headers)

    # Apply header styling
    for cell in ws_pipes[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align

    # Add example data (only supply pipes, return pipes auto-generated!)
    pipe_examples = [
        ["P1", "N1", "N2", 500, "ja", "nein", "DN150", "standard", 2010, "good", "", "", ""],
        ["P2", "N2", "N3", 300, "ja", "nein", "DN100", "standard", 2010, "good", "", "", ""],
        ["P3", "N3", "N4", 200, "nein", "ja", "", "", "", "", "DN100,DN150,DN200", "standard,enhanced", 250],
    ]

    for row in pipe_examples:
        ws_pipes.append(row)

    # Set column widths
    for col in range(1, len(pipe_headers) + 1):
        ws_pipes.column_dimensions[chr(64 + col)].width = 16

    # ========== Sheet 5: Verbraucher ==========
    ws_consumers = wb.create_sheet("Verbraucher")
    consumer_headers = [
        "ID", "Knoten", "Lastgang",
        "Spitzenlast_MW", "Jahresbedarf_MWh",
        "T_Vorlauf_min_C", "T_Ruecklauf_C"
    ]
    ws_consumers.append(consumer_headers)

    # Apply header styling
    for cell in ws_consumers[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align

    # Add example data
    consumer_examples = [
        ["Gebiet_1", "N2", "Lastgang_Gebiet_1", 3.0, 15000, 70, 45],
        ["Gebiet_2", "N3", "Lastgang_Gebiet_2", 2.0, 10000, 70, 45],
        ["Gebiet_3", "N4", "Lastgang_Gebiet_3", 1.5, 7500, 70, 45],
    ]

    for row in consumer_examples:
        ws_consumers.append(row)

    # Set column widths
    for col in range(1, len(consumer_headers) + 1):
        ws_consumers.column_dimensions[chr(64 + col)].width = 18

    # ========== Sheet 6: Zeitreihen ==========
    ws_timeseries = wb.create_sheet("Zeitreihen")
    timeseries_headers = [
        "Zeitstempel",
        "Lastgang_Gebiet_1",
        "Lastgang_Gebiet_2",
        "Lastgang_Gebiet_3",
        "Strompreis_€_MWh",
        "Gaspreis_€_MWh",
        "Aussentemperatur_C"
    ]
    ws_timeseries.append(timeseries_headers)

    # Apply header styling
    for cell in ws_timeseries[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align

    # Add a few example rows (8760 hours in a year, but just show 5 examples)
    import datetime
    start_time = datetime.datetime(2023, 1, 1, 0, 0, 0)

    for hour in range(10):  # Just 10 example rows
        timestamp = start_time + datetime.timedelta(hours=hour)
        # Example load profiles (simplified)
        load1 = 2.0 + 1.0 * (hour % 24) / 24  # Varies 2-3 MW
        load2 = 1.5 + 0.5 * (hour % 24) / 24  # Varies 1.5-2.0 MW
        load3 = 1.0 + 0.5 * (hour % 24) / 24  # Varies 1.0-1.5 MW
        electricity_price = 50 + 30 * (hour % 24) / 24  # 50-80 €/MWh
        gas_price = 30  # constant
        ambient_temp = 5 + 10 * (hour % 24) / 24  # 5-15 °C

        ws_timeseries.append([
            timestamp,
            round(load1, 2),
            round(load2, 2),
            round(load3, 2),
            round(electricity_price, 2),
            gas_price,
            round(ambient_temp, 1)
        ])

    # Add note about 8760 hours
    ws_timeseries.append([])
    ws_timeseries.append(["HINWEIS: Für eine vollständige Jahressimulation benötigen Sie 8760 Zeilen (Stunden)"])

    # Set column widths
    ws_timeseries.column_dimensions['A'].width = 20
    for col in range(2, len(timeseries_headers) + 1):
        ws_timeseries.column_dimensions[chr(64 + col)].width = 18

    # Save workbook
    wb.save(output_path)
    print(f"✓ Created Excel template: {output_path}")
    print(f"\nTemplate structure:")
    print(f"  - Netzwerk: Network-level parameters")
    print(f"  - Erzeuger: Heat producers (boilers, heat pumps, CHP)")
    print(f"  - Speicher: Thermal storage units")
    print(f"  - Rohre: Pipe definitions (ONLY supply pipes, return auto-generated)")
    print(f"  - Verbraucher: Heat consumers")
    print(f"  - Zeitreihen: All timeseries data (8760 hours for full year)")
    print(f"\nNext steps:")
    print(f"  1. Open the template in Excel")
    print(f"  2. Fill in your network data")
    print(f"  3. Use ThermalNetworkExcelParser to convert to YAML")


def create_template_simple(output_path: Path) -> None:
    """Fallback: Create simple single-sheet template."""
    from energis.utils.xlsx import write_simple_xlsx

    headers = ["Sheet", "Column", "Description", "Example"]
    rows = [
        ["NETZWERK", "", "", ""],
        ["Netzwerk", "Name", "Network name", "Musterhausen"],
        ["Netzwerk", "T_Vorlauf_nom", "Supply temp [°C]", "90"],
        ["Netzwerk", "T_Ruecklauf_nom", "Return temp [°C]", "50"],
        ["", "", "", ""],
        ["ERZEUGER", "", "", ""],
        ["Erzeuger", "ID", "Unique ID", "Kessel_1"],
        ["Erzeuger", "Typ", "Type", "boiler"],
        ["Erzeuger", "Bestand?", "Existing?", "ja"],
        ["Erzeuger", "Q_nom_MW", "Capacity [MW]", "5.0"],
        ["", "", "", ""],
        ["ROHRE", "", "", ""],
        ["Rohre", "ID", "Pipe ID", "P1"],
        ["Rohre", "Von_Knoten", "From node", "N1"],
        ["Rohre", "Zu_Knoten", "To node", "N2"],
        ["Rohre", "Laenge_m", "Length [m]", "500"],
        ["Rohre", "Bestand?", "Existing?", "ja"],
        ["", "", "", ""],
        ["HINWEIS", "", "", ""],
        ["", "Install openpyxl for multi-sheet template:", "pip install openpyxl", ""],
    ]

    write_simple_xlsx(str(output_path), headers, rows)
    print(f"Created simple template: {output_path}")
    print("For full multi-sheet template, install openpyxl: pip install openpyxl")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Create Excel template for thermal network configuration"
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="templates/thermal_network_template.xlsx",
        help="Output path for template file (default: templates/thermal_network_template.xlsx)"
    )

    args = parser.parse_args()
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    create_template_with_openpyxl(output_path)


if __name__ == "__main__":
    main()
