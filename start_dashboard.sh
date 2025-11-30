#!/bin/bash
# 🎛️ EnerGIS Dashboard Starter
# Startet das interaktive Dashboard im Browser

set -e  # Exit on error

# Farben für Output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  🎛️  EnerGIS Dashboard Starter${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Default Port
PORT="${1:-5006}"

# Prüfe ob Panel installiert ist
if ! python -c "import panel" 2>/dev/null; then
    echo -e "${YELLOW}⚠️  Panel ist nicht installiert!${NC}"
    echo ""
    echo -e "Installiere Dependencies..."
    pip install panel holoviews bokeh plotly
    echo ""
fi

# Prüfe ob Notebook existiert
NOTEBOOK="notebooks/interactive_dashboard.ipynb"
if [ ! -f "$NOTEBOOK" ]; then
    echo -e "${YELLOW}⚠️  Notebook nicht gefunden: $NOTEBOOK${NC}"
    exit 1
fi

# Prüfe ob Port bereits belegt ist
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo -e "${YELLOW}⚠️  Port $PORT ist bereits belegt!${NC}"
    echo -e "${YELLOW}   Versuche anderen Port: ./start_dashboard.sh 5007${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Alle Voraussetzungen erfüllt${NC}"
echo ""
echo -e "${BLUE}📊 Starte Dashboard auf Port $PORT...${NC}"
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  Dashboard verfügbar unter:${NC}"
echo -e "${GREEN}  👉 http://localhost:$PORT/interactive_dashboard${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${BLUE}💡 Tipps:${NC}"
echo -e "   • Dashboard läuft im Hintergrund - Browser öffnet automatisch"
echo -e "   • Zum Beenden: Drücke ${YELLOW}Strg+C${NC}"
echo -e "   • Anderen Port: ${YELLOW}./start_dashboard.sh 5007${NC}"
echo ""

# Starte Panel Server
panel serve "$NOTEBOOK" \
    --port "$PORT" \
    --show \
    --autoreload \
    --num-procs 1

echo ""
echo -e "${BLUE}👋 Dashboard wurde beendet${NC}"
