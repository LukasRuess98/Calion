#!/usr/bin/env python3
"""
🎛️ EnerGIS Standalone Dashboard

Startet ein interaktives Dashboard zur Visualisierung gespeicherter Simulationen.

Das Dashboard ist vollständig unabhängig von laufenden Simulationen und lädt
gespeicherte Workflows aus dem 'saved_workflows/' Verzeichnis.

Features:
- 📁 Automatisches Scannen aller gespeicherten Simulationen
- 🔍 Dropdown-Auswahl zur Navigation zwischen Simulationen
- 📊 Vollständiges Dashboard mit allen Tabs (Übersicht, Zeitreihen, Kosten, Anlagen)
- 📈 Zugriff auf CSV-Daten und exportierte Plots
- 🔀 Vergleichs-Modus für multiple Simulationen

Usage:
    # Standard-Start (öffnet Browser automatisch)
    python start_dashboard.py

    # Mit spezifischem Verzeichnis
    python start_dashboard.py --dir my_workflows/

    # Mit Port-Angabe
    python start_dashboard.py --port 5008

    # Ohne automatisches Öffnen
    python start_dashboard.py --no-show

    # Debug-Modus
    python start_dashboard.py --debug
"""

import argparse
import logging
import sys
from pathlib import Path


def setup_logging(debug: bool = False):
    """Configure logging."""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def main():
    """Start the standalone dashboard."""
    parser = argparse.ArgumentParser(
        description='EnerGIS Standalone Dashboard - Visualisierung gespeicherter Simulationen',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # Standard-Start
  %(prog)s --dir my_workflows/      # Spezifisches Verzeichnis
  %(prog)s --port 5008              # Anderer Port
  %(prog)s --debug                  # Debug-Modus
        """
    )

    parser.add_argument(
        '--dir',
        type=str,
        default='notebooks/saved_workflows',
        help='Verzeichnis mit gespeicherten Workflows (default: notebooks/saved_workflows)'
    )

    parser.add_argument(
        '--port',
        type=int,
        default=5007,
        help='Port für den Webserver (default: 5007)'
    )

    parser.add_argument(
        '--no-show',
        action='store_true',
        help='Browser nicht automatisch öffnen'
    )

    parser.add_argument(
        '--debug',
        action='store_true',
        help='Debug-Modus aktivieren'
    )

    parser.add_argument(
        '--title',
        type=str,
        default='EnerGIS Dashboard - Gespeicherte Simulationen',
        help='Dashboard-Titel'
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.debug)
    logger = logging.getLogger(__name__)

    # Check dependencies
    try:
        import panel as pn
    except ImportError:
        logger.error("❌ Panel nicht installiert!")
        logger.error("   Installation: pip install panel holoviews bokeh plotly")
        sys.exit(1)

    # Import dashboard
    try:
        from energis.io.workflow_browser import create_workflow_browser
    except ImportError as e:
        logger.error(f"❌ Fehler beim Import: {e}")
        logger.error("   Stelle sicher, dass das Skript im Projekt-Root ausgeführt wird")
        sys.exit(1)

    # Check workflows directory
    workflows_dir = Path(args.dir)
    if not workflows_dir.exists():
        logger.warning(f"⚠️ Verzeichnis existiert nicht: {workflows_dir}")
        logger.warning("   Dashboard wird trotzdem gestartet (zeigt Hinweis)")

    # Print header
    print("\n" + "="*70)
    print("🎛️  EnerGIS Standalone Dashboard")
    print("="*70)
    print(f"📁 Workflow-Verzeichnis: {workflows_dir.absolute()}")
    print(f"🌐 Port: {args.port}")
    print(f"🔍 Auto-open Browser: {not args.no_show}")
    print(f"📝 Debug-Modus: {args.debug}")
    print("="*70 + "\n")

    # Create dashboard
    logger.info("Erstelle Dashboard...")
    dashboard = create_workflow_browser(
        saved_workflows_dir=str(workflows_dir),
        title=args.title
    )

    # Print instructions
    print("\n💡 Dashboard-Steuerung:")
    print("   • Ctrl+C zum Beenden")
    print(f"   • URL: http://localhost:{args.port}")
    print("   • Wähle eine Simulation im Dropdown zur Visualisierung\n")

    # Serve dashboard
    logger.info(f"Starte Webserver auf Port {args.port}...")

    try:
        pn.serve(
            dashboard,
            port=args.port,
            show=not args.no_show,
            title=args.title,
            websocket_origin=f"localhost:{args.port}",
            # Disable autoreload for production use
            autoreload=args.debug
        )
    except KeyboardInterrupt:
        print("\n\n👋 Dashboard beendet")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Fehler beim Starten des Dashboards: {e}")
        if args.debug:
            raise
        sys.exit(1)


if __name__ == '__main__':
    main()
