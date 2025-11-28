#!/bin/bash

# ============================================================================
# EnerGIS Dashboard - Stop Script
# ============================================================================
# Stoppt alle laufenden Dashboard-Instanzen
#
# Verwendung:
#   ./stop_dashboard.sh
# ============================================================================

echo "======================================================================"
echo "🛑 Stoppe EnerGIS Dashboard"
echo "======================================================================"
echo ""

# Find running panel serve processes
PIDS=$(pgrep -f "panel serve load_dashboard.py")

if [ -z "$PIDS" ]; then
    echo "ℹ️  Kein laufendes Dashboard gefunden"
    echo ""
else
    echo "🔍 Gefundene Dashboard-Prozesse:"
    ps aux | grep "panel serve load_dashboard.py" | grep -v grep
    echo ""

    echo "🛑 Stoppe Prozesse..."
    pkill -f "panel serve load_dashboard.py"

    sleep 2

    # Check if stopped
    PIDS_AFTER=$(pgrep -f "panel serve load_dashboard.py")
    if [ -z "$PIDS_AFTER" ]; then
        echo "   ✅ Dashboard erfolgreich gestoppt"
    else
        echo "   ⚠️  Einige Prozesse laufen noch, versuche force kill..."
        pkill -9 -f "panel serve load_dashboard.py"
        echo "   ✅ Dashboard gestoppt (force)"
    fi
fi

echo ""
echo "======================================================================"
