#!/bin/bash
# Setup script for EnerGIS vs. oemof benchmarking
# Author: For Applied Energy paper
# Date: 2025-11-18

set -e  # Exit on error

echo "================================================================"
echo "Setting up EnerGIS vs. oemof Benchmarking Environment"
echo "================================================================"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check Python version
echo -e "\n${YELLOW}Checking Python version...${NC}"
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "  Found: Python $python_version"

if python3 -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)"; then
    echo -e "  ${GREEN}✓ Python >= 3.8${NC}"
else
    echo -e "  ${RED}✗ Python 3.8 or later required${NC}"
    exit 1
fi

# Create virtual environment
echo -e "\n${YELLOW}Creating virtual environment...${NC}"
if [ ! -d "venv_benchmark" ]; then
    python3 -m venv venv_benchmark
    echo -e "  ${GREEN}✓ Virtual environment created${NC}"
else
    echo -e "  ${YELLOW}⚠ Virtual environment already exists${NC}"
fi

# Activate virtual environment
echo -e "\n${YELLOW}Activating virtual environment...${NC}"
source venv_benchmark/bin/activate

# Upgrade pip
echo -e "\n${YELLOW}Upgrading pip...${NC}"
pip install --upgrade pip setuptools wheel > /dev/null 2>&1
echo -e "  ${GREEN}✓ pip upgraded${NC}"

# Install core dependencies
echo -e "\n${YELLOW}Installing core dependencies...${NC}"
pip install numpy pandas matplotlib > /dev/null 2>&1
echo -e "  ${GREEN}✓ numpy, pandas, matplotlib installed${NC}"

# Install oemof.solph
echo -e "\n${YELLOW}Installing oemof.solph...${NC}"
pip install oemof.solph > /dev/null 2>&1
if python3 -c "import oemof.solph" 2>/dev/null; then
    oemof_version=$(python3 -c "import oemof.solph; print(oemof.solph.__version__)")
    echo -e "  ${GREEN}✓ oemof.solph $oemof_version installed${NC}"
else
    echo -e "  ${RED}✗ Failed to install oemof.solph${NC}"
    exit 1
fi

# Check for solvers
echo -e "\n${YELLOW}Checking for MILP solvers...${NC}"

# Check CBC
if command -v cbc &> /dev/null; then
    cbc_version=$(cbc -v 2>&1 | head -n1 | awk '{print $3}')
    echo -e "  ${GREEN}✓ CBC found (version $cbc_version)${NC}"
    SOLVER_FOUND=1
else
    echo -e "  ${YELLOW}⚠ CBC not found${NC}"
    echo "    Install with: sudo apt-get install coinor-cbc  (Ubuntu/Debian)"
    echo "                  brew install coin-or-tools/coinor/cbc  (macOS)"
    SOLVER_FOUND=0
fi

# Check Gurobi
if python3 -c "import gurobipy" 2>/dev/null; then
    gurobi_version=$(python3 -c "import gurobipy; print(gurobipy.gurobi.version())")
    echo -e "  ${GREEN}✓ Gurobi found (version $gurobi_version)${NC}"
    SOLVER_FOUND=1
else
    echo -e "  ${YELLOW}⚠ Gurobi not found (optional, but recommended)${NC}"
    echo "    Get free academic license: https://www.gurobi.com/academia/"
fi

# Check GLPK
if command -v glpsol &> /dev/null; then
    glpk_version=$(glpsol --version | head -n1 | awk '{print $4}')
    echo -e "  ${GREEN}✓ GLPK found (version $glpk_version)${NC}"
    SOLVER_FOUND=1
else
    echo -e "  ${YELLOW}⚠ GLPK not found${NC}"
    echo "    Install with: sudo apt-get install glpk-utils  (Ubuntu/Debian)"
    echo "                  brew install glpk  (macOS)"
fi

if [ $SOLVER_FOUND -eq 0 ]; then
    echo -e "\n${RED}✗ No MILP solver found! At least one solver (CBC, Gurobi, GLPK) is required.${NC}"
    echo "  See README.md for installation instructions."
    exit 1
fi

# Create results directory
echo -e "\n${YELLOW}Creating results directory...${NC}"
mkdir -p results/{oemof,energis,plots}
echo -e "  ${GREEN}✓ results/ directory ready${NC}"

# Run quick test
echo -e "\n${YELLOW}Running quick test...${NC}"
python3 -c "
from oemof_implementation import OemofBenchmarkConfig, generate_synthetic_timeseries
print('  Testing oemof import... OK')
config = OemofBenchmarkConfig(hours=24)
print('  Testing config creation... OK')
ts = generate_synthetic_timeseries(hours=24)
print('  Testing time series generation... OK')
print('  All imports working correctly.')
"

if [ $? -eq 0 ]; then
    echo -e "  ${GREEN}✓ Quick test passed${NC}"
else
    echo -e "  ${RED}✗ Quick test failed${NC}"
    exit 1
fi

# Final summary
echo -e "\n${GREEN}================================================================${NC}"
echo -e "${GREEN}Setup Complete!${NC}"
echo -e "${GREEN}================================================================${NC}"

echo -e "\n${YELLOW}Next steps:${NC}"
echo "  1. Activate the virtual environment:"
echo "     source venv_benchmark/bin/activate"
echo ""
echo "  2. Run parity check (recommended first test):"
echo "     python run_comparison.py --parity --solver cbc"
echo ""
echo "  3. Run full benchmark suite:"
echo "     python run_comparison.py --all --solver cbc"
echo ""
echo "  4. Read the README for more details:"
echo "     cat README.md"
echo ""
echo -e "${YELLOW}For questions or issues:${NC}"
echo "  - See README.md Troubleshooting section"
echo "  - Check oemof documentation: https://oemof-solph.readthedocs.io/"
echo ""

echo -e "${GREEN}Happy benchmarking!${NC}"
