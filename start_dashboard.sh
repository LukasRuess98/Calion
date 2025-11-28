#!/bin/bash

# ============================================================================
# EnerGIS Dashboard - Start Script
# ============================================================================
# Startet das Multi-Workflow Dashboard
#
# Verwendung:
#   ./start_dashboard.sh          # Standard-Port 5006
#   ./start_dashboard.sh 8080     # Custom Port
#
# Stoppen:
#   Strg+C im Terminal
#   Oder: pkill -f "panel serve"
# ============================================================================

PORT=${1:-5006}  # Default: 5006, oder erster Parameter

echo "======================================================================"
echo "🎛️ EnerGIS Multi-Workflow Dashboard"
echo "======================================================================"
echo ""

# Check if saved_workflows exists
if [ ! -d "saved_workflows" ] || [ -z "$(ls -A saved_workflows 2>/dev/null)" ]; then
    echo "❌ Keine Simulationen gefunden!"
    echo ""
    echo "💡 Bitte zuerst Mock-Simulationen erstellen:"
    echo "   python3 create_mock_simulations.py"
    echo ""
    echo "   Oder komplette Installation:"
    echo "   ./install_dashboard.sh"
    echo ""
    exit 1
fi

# Count workflows
NUM_WORKFLOWS=$(find saved_workflows -mindepth 1 -maxdepth 1 -type d | wc -l)
echo "📊 $NUM_WORKFLOWS Simulation(en) gefunden"
echo ""

# Check if port is in use
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "⚠️  Port $PORT ist bereits belegt!"
    echo ""
    echo "💡 Optionen:"
    echo "   1. Stoppe den laufenden Prozess: pkill -f 'panel serve'"
    echo "   2. Verwende anderen Port: ./start_dashboard.sh 8080"
    echo ""
    exit 1
fi

echo "🚀 Starte Dashboard auf Port $PORT..."
echo ""

# Detect environment
if [ -f "/.dockerenv" ]; then
    ENV_TYPE="Docker Container"
    ACCESS_INFO="
💡 Du bist in einem Docker Container!

   Zugriff hängt von deinem Setup ab:

   📌 Lokale Maschine (Docker Desktop):
      → http://localhost:$PORT/load_dashboard

   📌 Remote-Server:
      → Port-Forwarding: ssh -L $PORT:localhost:$PORT user@server
      → Oder öffentlich: panel serve ... --address 0.0.0.0

   📌 VS Code Remote:
      → Port wird automatisch weitergeleitet
      → Schaue in 'Ports' Tab"
else
    ENV_TYPE="Lokale Maschine"
    ACCESS_INFO="
📊 Dashboard URL:
   → http://localhost:$PORT/load_dashboard"
fi

echo "🖥️  Umgebung: $ENV_TYPE"
echo "$ACCESS_INFO"
echo ""
echo "💡 Zum Stoppen: Strg+C"
echo ""
echo "======================================================================"
echo ""

# Start dashboard
panel serve load_dashboard.py --port $PORT --show
