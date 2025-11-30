#!/usr/bin/env python3
"""
Convert old notebook export format to dashboard-compatible metadata.

Old format (from notebooks):
  - manifest.json
  - design.json / pf_design.json
  - CSV files (pf_timeseries.csv, etc.)
  - PDF/SVG plots

New format (for dashboard):
  - workflow.pkl (cannot create without original workflow)
  - metadata.json (can convert from manifest.json + design.json)

Limitations:
  - Cannot create workflow.pkl (requires original workflow object)
  - Dashboard can show metadata but not load full results
  - Converted folders will have limited functionality
"""

import sys
import json
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def convert_old_export_to_metadata(export_dir):
    """Convert old export format to metadata.json.

    Parameters
    ----------
    export_dir : Path
        Directory containing old export files

    Returns
    -------
    dict or None
        Metadata dict if successful, None if conversion failed
    """

    manifest_file = export_dir / 'manifest.json'
    design_file = export_dir / 'design.json'
    pf_design_file = export_dir / 'pf_design.json'

    # Check if old format
    if not manifest_file.exists():
        print(f"   ⚠️  Not an old export: No manifest.json found")
        return None

    # Read manifest
    with open(manifest_file, 'r', encoding='utf-8') as f:
        manifest = json.load(f)

    # Read design (try design.json first, then pf_design.json)
    design = {}
    if design_file.exists():
        with open(design_file, 'r', encoding='utf-8') as f:
            design = json.load(f)
    elif pf_design_file.exists():
        with open(pf_design_file, 'r', encoding='utf-8') as f:
            design = json.load(f)

    # Extract timestamp from manifest or directory name
    export_timestamp = manifest.get('export_timestamp', '')
    if export_timestamp:
        # Convert "20251128_024040" to ISO format
        try:
            dt = datetime.strptime(export_timestamp, '%Y%m%d_%H%M%S')
            saved_at = dt.isoformat()
        except:
            saved_at = datetime.now().isoformat()
    else:
        saved_at = datetime.now().isoformat()

    # Extract scenario info
    scenario_title = manifest.get('scenario_title', 'Unknown')
    run_mode = manifest.get('run_mode', 'unknown')
    workflow_steps = manifest.get('workflow_steps', [])
    flags = manifest.get('flags', {})

    # Extract technologies from design
    technologies = {}

    # Heat pumps
    if 'heat_pumps' in design:
        hp_dict = {}
        for hp_name, hp_data in design['heat_pumps'].items():
            capacity = hp_data.get('capacity_mw', 0)
            if capacity > 0:  # Only include built heat pumps
                hp_dict[hp_name] = {
                    'capacity_mw': capacity,
                    'type': 'heat_pump'
                }
        if hp_dict:
            technologies['heat_pumps'] = hp_dict

    # Storage
    if 'storage' in design:
        storage = design['storage']
        capacity = storage.get('capacity_mwh', 0)
        if capacity > 0:
            technologies['storage'] = {
                'capacity_mwh': capacity,
                'power_mw': storage.get('power_mw', 0),
                'type': 'thermal_storage'
            }

    # Count timesteps from CSV if available
    timesteps = 0
    pf_csv = export_dir / 'pf_timeseries.csv'
    if pf_csv.exists():
        with open(pf_csv, 'r') as f:
            timesteps = sum(1 for _ in f) - 1  # -1 for header

    # Build metadata
    metadata = {
        'saved_at': saved_at,
        'name': export_dir.name,
        'description': f'Converted from old export: {scenario_title}',
        'scenario': {
            'name': scenario_title,
            'system': run_mode,
            'site': 'unknown',
        },
        'config_files': [],
        'workflow': {
            'steps': workflow_steps,
            'fix_design': False,
        },
        'results_available': {
            'pf': flags.get('has_pf', False),
            'rh': flags.get('has_rh', False),
            'mpc': flags.get('has_mpc', False),
        },
        'solver': 'unknown',
        'technologies': technologies,
        'statistics': {
            'timesteps': timesteps,
            'duration_hours': timesteps * 1.0,
        },
        'costs': {
            'total_eur': 0,
            'capex_eur': 0,
            'opex_eur': 0,
            'fuel_eur': 0,
        },
        'conversion_note': 'Converted from old notebook export format. workflow.pkl not available - limited dashboard functionality.',
    }

    return metadata


def process_export_dir(export_dir):
    """Process a single export directory.

    Parameters
    ----------
    export_dir : Path
        Directory to process

    Returns
    -------
    bool
        True if conversion successful, False otherwise
    """

    metadata_file = export_dir / 'metadata.json'

    # Check if metadata already exists
    if metadata_file.exists():
        print(f"   ℹ️  Überspringe {export_dir.name}: metadata.json existiert bereits")
        return False

    # Check if workflow.pkl exists (new format)
    workflow_file = export_dir / 'workflow.pkl'
    if workflow_file.exists():
        print(f"   ℹ️  Überspringe {export_dir.name}: Bereits neues Format (hat workflow.pkl)")
        return False

    # Try to convert old format
    try:
        metadata = convert_old_export_to_metadata(export_dir)

        if metadata is None:
            print(f"   ⚠️  Überspringe {export_dir.name}: Keine erkanntes altes Format")
            return False

        # Save metadata
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        print(f"   ✅ {export_dir.name}: metadata.json konvertiert")
        print(f"      ⚠️  WARNUNG: Keine workflow.pkl - Dashboard kann nur Metadaten anzeigen")
        return True

    except Exception as e:
        print(f"   ❌ Fehler bei {export_dir.name}: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main execution."""

    print("="*70)
    print("🔄 Konvertiere alte Notebook-Exports zu Dashboard-Metadaten")
    print("="*70)
    print()
    print("⚠️  WICHTIG:")
    print("   Diese Konvertierung erstellt nur metadata.json aus alten Exports.")
    print("   workflow.pkl kann NICHT erstellt werden (benötigt Original-Workflow).")
    print("   Dashboard zeigt Metadaten an, aber KEINE interaktiven Plots/Daten!")
    print()

    # Get target directory
    if len(sys.argv) > 1:
        target_dir = Path(sys.argv[1])
        if not target_dir.exists():
            print(f"❌ Ordner nicht gefunden: {target_dir}")
            sys.exit(1)
        export_dirs = [target_dir] if target_dir.is_dir() else []
    else:
        saved_workflows_dir = project_root / 'saved_workflows'
        if not saved_workflows_dir.exists():
            print(f"❌ Ordner nicht gefunden: {saved_workflows_dir}")
            sys.exit(1)
        export_dirs = [d for d in saved_workflows_dir.iterdir() if d.is_dir()]

    print(f"📁 Prüfe {len(export_dirs)} Ordner...")
    print()

    converted_count = 0
    for export_dir in sorted(export_dirs):
        if process_export_dir(export_dir):
            converted_count += 1

    print()
    print("="*70)
    if converted_count > 0:
        print(f"✅ {converted_count} metadata.json Datei(en) konvertiert!")
        print()
        print("⚠️  LIMITATION:")
        print("   Konvertierte Ordner haben nur metadata.json, KEIN workflow.pkl!")
        print("   Dashboard zeigt diese Simulationen in der Liste an,")
        print("   aber kann KEINE Plots/Zeitreihen/Daten laden.")
        print()
        print("💡 Für volle Dashboard-Funktionalität:")
        print("   - Führe neue Simulationen mit save_workflow_results.py aus")
        print("   - Oder erstelle Mock-Daten: python create_mock_simulations.py")
        print()
        print("💡 Dashboard starten:")
        print("   python -m panel serve load_dashboard.py --port 5006 --show")
    else:
        print("ℹ️  Keine Ordner konvertiert")
        print("   (Alle Ordner haben bereits metadata.json oder sind nicht im alten Format)")
    print("="*70)


if __name__ == '__main__':
    main()
