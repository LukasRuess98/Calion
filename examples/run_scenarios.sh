#!/bin/bash
#
# Beispiel-Script: Verschiedene Szenarien ausführen
# ================================================
#
# Usage:
#   chmod +x examples/run_scenarios.sh
#   ./examples/run_scenarios.sh
#

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXAMPLE_SCRIPT="${SCRIPT_DIR}/standalone_heat_planning_example.py"

echo "========================================"
echo "Heat Planning - Szenario-Analyse"
echo "========================================"
echo ""

# Prüfe ob Import_Data.xlsx existiert
if [ ! -f "Import_Data.xlsx" ]; then
    echo "ERROR: Import_Data.xlsx nicht gefunden!"
    echo "Bitte sicherstellen, dass die Datei im aktuellen Verzeichnis liegt."
    exit 1
fi

# Erstelle Export-Verzeichnis
mkdir -p exports/scenarios

# ========================================
# Szenario 1: Baseline (PF Only)
# ========================================
echo "----------------------------------------"
echo "Szenario 1: Baseline (PF Only)"
echo "----------------------------------------"

RUN_MODE=PF_ONLY \
SCENARIO_TITLE=Baseline_PF \
CO2_PRICE_EUR_PER_T=100 \
GASPREIS_EUR_PER_MWh_th=58.6 \
SOLVER_NAME=cbc \
EXPORT_BASE_DIR=exports/scenarios \
python3 "$EXAMPLE_SCRIPT"

echo ""
echo "✓ Szenario 1 abgeschlossen"
echo ""

# ========================================
# Szenario 2: Hoher CO2-Preis
# ========================================
echo "----------------------------------------"
echo "Szenario 2: Hoher CO2-Preis (200 EUR/t)"
echo "----------------------------------------"

RUN_MODE=PF_ONLY \
SCENARIO_TITLE=High_CO2_200 \
CO2_PRICE_EUR_PER_T=200 \
GASPREIS_EUR_PER_MWh_th=58.6 \
SOLVER_NAME=cbc \
EXPORT_BASE_DIR=exports/scenarios \
python3 "$EXAMPLE_SCRIPT"

echo ""
echo "✓ Szenario 2 abgeschlossen"
echo ""

# ========================================
# Szenario 3: Niedriger Gaspreis
# ========================================
echo "----------------------------------------"
echo "Szenario 3: Niedriger Gaspreis (40 EUR/MWh)"
echo "----------------------------------------"

RUN_MODE=PF_ONLY \
SCENARIO_TITLE=Low_Gas_40 \
CO2_PRICE_EUR_PER_T=100 \
GASPREIS_EUR_PER_MWh_th=40.0 \
SOLVER_NAME=cbc \
EXPORT_BASE_DIR=exports/scenarios \
python3 "$EXAMPLE_SCRIPT"

echo ""
echo "✓ Szenario 3 abgeschlossen"
echo ""

# ========================================
# Szenario 4: Hoher Gaspreis
# ========================================
echo "----------------------------------------"
echo "Szenario 4: Hoher Gaspreis (85 EUR/MWh)"
echo "----------------------------------------"

RUN_MODE=PF_ONLY \
SCENARIO_TITLE=High_Gas_85 \
CO2_PRICE_EUR_PER_T=100 \
GASPREIS_EUR_PER_MWh_th=85.0 \
SOLVER_NAME=cbc \
EXPORT_BASE_DIR=exports/scenarios \
python3 "$EXAMPLE_SCRIPT"

echo ""
echo "✓ Szenario 4 abgeschlossen"
echo ""

# ========================================
# Szenario 5: Vollständiger Lauf (PF + RH)
# ========================================
echo "----------------------------------------"
echo "Szenario 5: Komplett (PF + RH)"
echo "----------------------------------------"

RUN_MODE=PF_THEN_RH \
SCENARIO_TITLE=Complete_PF_RH \
CO2_PRICE_EUR_PER_T=100 \
GASPREIS_EUR_PER_MWh_th=58.6 \
HEAT_HORIZON_HOURS=168 \
STEP_HOURS=24 \
RH_TERMINAL_POLICY=geq \
SOLVER_NAME=cbc \
EXPORT_BASE_DIR=exports/scenarios \
python3 "$EXAMPLE_SCRIPT"

echo ""
echo "✓ Szenario 5 abgeschlossen"
echo ""

# ========================================
# Zusammenfassung
# ========================================
echo "========================================"
echo "Alle Szenarien abgeschlossen!"
echo "========================================"
echo ""
echo "Ergebnisse in: exports/scenarios/"
echo ""
echo "Generierte Dateien:"
ls -lh exports/scenarios/*.xlsx 2>/dev/null || echo "  (keine Excel-Dateien gefunden)"
ls -lh exports/scenarios/*.json 2>/dev/null || echo "  (keine JSON-Dateien gefunden)"
echo ""
echo "Fertig!"
