#!/bin/bash
# 🖥️ EnerGIS Dashboard für Server
# Startet das Dashboard für Zugriff von externen Clients

set -e  # Exit on error

# Farben für Output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  🖥️  EnerGIS Dashboard für Server${NC}"
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
    echo -e "${RED}❌ Notebook nicht gefunden: $NOTEBOOK${NC}"
    exit 1
fi

# Prüfe ob Port bereits belegt ist
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo -e "${YELLOW}⚠️  Port $PORT ist bereits belegt!${NC}"
    echo -e "${YELLOW}   Versuche anderen Port: ./start_dashboard_server.sh 5007${NC}"
    exit 1
fi

# Ermittle Server-IP
SERVER_IP=$(hostname -I | awk '{print $1}')

echo -e "${GREEN}✅ Alle Voraussetzungen erfüllt${NC}"
echo ""
echo -e "${BLUE}📊 Starte Dashboard im Server-Modus...${NC}"
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  Dashboard verfügbar unter:${NC}"
echo -e "${GREEN}  👉 Lokal:     http://localhost:$PORT/interactive_dashboard${NC}"
echo -e "${GREEN}  👉 Netzwerk:  http://$SERVER_IP:$PORT/interactive_dashboard${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${BLUE}💡 Wichtig:${NC}"
echo -e "   • Dashboard ist von außen erreichbar!"
echo -e "   • Firewall-Port öffnen: ${YELLOW}sudo ufw allow $PORT/tcp${NC}"
echo -e "   • Zum Beenden: ${YELLOW}Strg+C${NC}"
echo ""
echo -e "${YELLOW}⚠️  Sicherheitshinweis:${NC}"
echo -e "   Für Produktiv-Einsatz sollten Sie:"
echo -e "   • HTTPS aktivieren (--ssl-certfile, --ssl-keyfile)"
echo -e "   • Authentifizierung einrichten"
echo -e "   • Zugriff auf vertrauenswürdige IPs beschränken"
echo ""

# Starte Panel Server im Server-Modus
panel serve "$NOTEBOOK" \
    --port "$PORT" \
    --address "0.0.0.0" \
    --allow-websocket-origin="*" \
    --autoreload \
    --num-procs 1

echo ""
echo -e "${BLUE}👋 Dashboard wurde beendet${NC}"
