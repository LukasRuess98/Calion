#!/bin/bash

# ============================================================================
# EnerGIS Dashboard - Komplette Installation
# ============================================================================
# Dieses Script installiert alle benötigten Pakete und erstellt Mock-Daten
#
# Verwendung:
#   ./install_dashboard.sh
#
# Nach Installation:
#   ./start_dashboard.sh     # Dashboard starten
# ============================================================================

set -e  # Stop on error

echo "======================================================================"
echo "🚀 EnerGIS Dashboard - Installation"
echo "======================================================================"
echo ""

# ============================================================================
# Schritt 1: Python-Version prüfen
# ============================================================================
echo "📋 Schritt 1/4: Python-Version prüfen..."
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "   ✅ Python $PYTHON_VERSION gefunden"
echo ""

# ============================================================================
# Schritt 2: Dashboard-Pakete installieren
# ============================================================================
echo "📦 Schritt 2/4: Dashboard-Pakete installieren..."
echo "   Installiere: panel, holoviews, bokeh, plotly"
echo ""

pip install --quiet panel holoviews bokeh plotly

# Verify installation
python3 -c "
import panel as pn
import plotly
import holoviews as hv
import bokeh

print('   ✅ Panel:', pn.__version__)
print('   ✅ Plotly:', plotly.__version__)
print('   ✅ Holoviews:', hv.__version__)
print('   ✅ Bokeh:', bokeh.__version__)
"

echo ""
echo "   ✅ Alle Dashboard-Pakete erfolgreich installiert!"
echo ""

# ============================================================================
# Schritt 3: Mock-Simulationen erstellen
# ============================================================================
echo "🎨 Schritt 3/4: Mock-Simulationen erstellen..."
echo ""

python3 create_mock_simulations.py

echo ""

# ============================================================================
# Schritt 4: Zusammenfassung
# ============================================================================
echo "======================================================================"
echo "✅ INSTALLATION ERFOLGREICH!"
echo "======================================================================"
echo ""
echo "📊 Installierte Komponenten:"
echo "   ✅ Dashboard-Pakete (Panel, Plotly, Holoviews, Bokeh)"
echo "   ✅ Mock-Simulationen (3 Szenarien in saved_workflows/)"
echo ""
echo "🚀 Dashboard starten:"
echo "   ./start_dashboard.sh"
echo ""
echo "   Oder manuell:"
echo "   panel serve load_dashboard.py --show"
echo ""
echo "📖 Dokumentation:"
echo "   Siehe REAL_DATA_GUIDE.md für Details"
echo ""
echo "======================================================================"
