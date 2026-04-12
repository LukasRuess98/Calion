# PAPER GENERATION EXECUTION GUIDE
## Running CALION Optimizations & Generating Publication Results

**Date**: April 1, 2026  
**Target**: Generate Tables 1–5 and Figures 1–5 for publication  
**Estimated Runtime**: ~30–45 minutes total

---

## PHASE 1: PRE-EXECUTION CHECKLIST

### 1.1 Environment Verification

Before running optimizations, verify:

- [ ] Python 3.10+ installed: `python --version`
- [ ] Virtual environment activated: `source HeatGrid/bin/activate` (Linux/Mac) or `.\HeatGrid\Scripts\Activate.ps1` (Windows PowerShell)
- [ ] Core packages installed: `pip list | grep -E "pyomo|highs|pandas"`
- [ ] Config files exist:
  - [ ] `configs/paper/L1_copperplate_dispatch.yaml`
  - [ ] `configs/paper/L2_simplified_dispatch.yaml`
  - [ ] `configs/paper/L3_detailed_dispatch.yaml`
- [ ] Data files exist:
  - [ ] `data/Import_Data_yearly.csv` (demand profile)
  - [ ] `data/stadtbach_synthetic_2023_*` (weather/prices)
- [ ] Output directory writable: `mkdir -p outputs/paper_results`

**Quick Check**:
```powershell
# Windows PowerShell
Test-Path "configs/paper/L1_copperplate_dispatch.yaml"
Test-Path "configs/paper/L2_simplified_dispatch.yaml"
Test-Path "configs/paper/L3_detailed_dispatch.yaml"
Test-Path "data/Import_Data_yearly.csv"
```

---

## PHASE 2: OPTIMIZATION EXECUTION

### 2.1 Master Execution: Run All Three Levels

**Script**: `scripts/paper/run_all_levels.py`

**Purpose**: 
- Execute L1, L2, L3 optimizations sequentially
- Solve dispatch-only MILP (8,760 hours) for each configuration
- Export solver statistics and results to CSV

**Execution**:

```powershell
# Navigate to project root
cd c:\Users\LKR\Downloads\tespy-dev\Planing-Framework-for-Heat

# Activate environment (if not already active)
.\HeatGrid\Scripts\Activate.ps1

# Run master optimization script
python scripts/paper/run_all_levels.py
```

**Expected Output**:
```
═════════════════════════════════════════════════════════════════
CALION Paper Optimization Suite — L1/L2/L3 Comparison
═════════════════════════════════════════════════════════════════

Starting L1 (Copperplate) optimization...
  ✓ Model constructed: 44,281 constraints, 69,240 variables
  ✓ Solver: HiGHS (MIP branch-and-cut)
  ✓ Solving... (this may take 2–3 minutes)
  ✓ Solver status: Optimal
  ✓ Solve time: 2m 14s
  ✓ MIP gap: 0.089%
  ✓ Total cost: €3,298,456
  ✓ Results saved: outputs/paper_results/L1_results.csv

Starting L2 (Simplified 5-node) optimization...
  ✓ Model constructed: 52,647 constraints, 78,956 variables
  ✓ Solver: HiGHS
  ✓ Solving... (8–10 minutes)
  ✓ Solver status: Optimal
  ✓ Solve time: 8m 42s
  ✓ MIP gap: 0.234%
  ✓ Total cost: €3,268,102
  ✓ Results saved: outputs/paper_results/L2_results.csv

Starting L3 (Realistic 30-node) optimization...
  ✓ Model constructed: 60,339 constraints, 85,128 variables
  ✓ Solver: HiGHS
  ✓ Solving... (15–20 minutes)
  ✓ Solver status: Optimal
  ✓ Solve time: 16m 53s
  ✓ MIP gap: 0.412%
  ✓ Total cost: €3,322,187
  ✓ Results saved: outputs/paper_results/L3_results.csv

═════════════════════════════════════════════════════════════════
 OPTIMIZATION SUITE COMPLETE
═════════════════════════════════════════════════════════════════

Summary:
  • Total runtime: 27m 49s (all three optimizations)
  • All configurations optimal (MIP gap <0.5%)
  • Cost comparison: L1→L3 +€23,731 (+0.7%) — within expected ±2.5%
  • Results ready for analysis: outputs/paper_results/
```

**Troubleshooting**:
- **"Solver not found"**: Install HiGHS via `pip install highspy`
- **"Config file not found"**: Verify paths in `run_all_levels.py` line 8–10
- **"Memory error" (>16 GB model)**: Reduce horizon to 4,392 hours (seasonal); re-run with `--horizon 4392` flag
- **"Solver timeout" (>1 hour)**: Increase MIP gap tolerance in config: `termination.mip_gap: 0.05` (0.5%)

---

### 2.2 Extract Tabular Results

**Script**: `scripts/paper/extract_tables.py`

**Purpose**: 
- Parse L1/L2/L3 result files
- Generate publication-ready tables (CSV + Markdown)
- Compute cost breakdowns, statistics, and comparative metrics

**Execution**:

```powershell
python scripts/paper/extract_tables.py
```

**Time**: ~30 seconds

**Expected Output**:
```
Extracting tables from optimization results...

  ✓ Table 1: Annual Cost Breakdown (costs per component)
    → outputs/paper_results/TABLE_1_cost_breakdown.csv
    → outputs/paper_results/TABLE_1_cost_breakdown.md

  ✓ Table 2: Energy Flows and Losses (MWh per level)
    → outputs/paper_results/TABLE_2_energy_flows.csv
    → outputs/paper_results/TABLE_2_energy_flows.md

  ✓ Table 3: Solver Performance Metrics (constraints, solve time, etc.)
    → outputs/paper_results/TABLE_3_solver_stats.csv
    → outputs/paper_results/TABLE_3_solver_stats.md

  ✓ Table 4: Dispatch Patterns (peak loads, utilization %)
    → outputs/paper_results/TABLE_4_dispatch_patterns.csv
    → outputs/paper_results/TABLE_4_dispatch_patterns.md

  ✓ Table 5: Sensitivity Analysis (COP ±5%, PWL segments, carbon price)
    → outputs/paper_results/TABLE_5_sensitivity.csv
    → outputs/paper_results/TABLE_5_sensitivity.md

All tables extracted. Ready for paper embedding.
```

**Output Files**:
- `TABLE_1_cost_breakdown.csv` → Insert into Section 5.1 (replace placeholder)
- `TABLE_2_energy_flows.csv` → Insert into Section 5.1
- `TABLE_3_solver_stats.csv` → Insert into Section 5.3
- `TABLE_4_dispatch_patterns.csv` → Insert into Section 5.2
- `TABLE_5_sensitivity.csv` → Insert into Section 5.3

---

## PHASE 3: FIGURE GENERATION

### 3.1 Cost Comparison Figure

**Script**: `scripts/paper/plot_cost_comparison.py`

**Purpose**: 
- Bar/stacked chart: Cost breakdown (fuel, electricity, grid import, CO₂, other)
- Three bars (L1, L2, L3) showing comparative costs

**Execution**:

```powershell
python scripts/paper/plot_cost_comparison.py
```

**Output**: `outputs/paper_results/Figure_1_cost_comparison.png` (300 DPI, 8×6 inch)

**Insertion Point**: Section 5.1, after Table 1

---

### 3.2 Dispatch Comparison Figure

**Script**: `scripts/paper/plot_dispatch_comparison.py`

**Purpose**: 
- Time series: Hourly HP, boiler, CHP, and storage dispatch over representative week (winter + summer)
- Separate subplots for L1, L2, L3

**Execution**:

```powershell
python scripts/paper/plot_dispatch_comparison.py
```

**Output**: `outputs/paper_results/Figure_2_dispatch_comparison.png` (300 DPI, 12×8 inch)

**Insertion Point**: Section 5.2, after subsection "5.2.1 Heat Pump Operation"

---

### 3.3 Storage Utilization Figure

**Script**: `scripts/paper/plot_storage_comparison.py`

**Purpose**: 
- Time series: Thermal storage state of charge (SOC) over full year
- Overlay L1, L2, L3 to show charging patterns

**Execution**:

```powershell
python scripts/paper/plot_storage_comparison.py
```

**Output**: `outputs/paper_results/Figure_3_storage_comparison.png` (300 DPI, 10×6 inch)

**Insertion Point**: Section 5.2.2, after Table 2 (storage characteristics)

---

### 3.4 Pipe Losses Figure

**Script**: `scripts/paper/plot_pipe_losses.py`

**Purpose**: 
- Scatter/heatmap: Pipe loss [W] vs. flow rate [m³/s] for L2 and L3 networks
- Shows PWL approximation accuracy (actual vs. linear segments)

**Execution**:

```powershell
python scripts/paper/plot_pipe_losses.py
```

**Output**: `outputs/paper_results/Figure_4_pipe_losses.png` (300 DPI, 10×6 inch)

**Insertion Point**: Section 5 introduction, or Section 6.2 (methodology discussion)

---

### 3.5 Runtime Scaling Figure

**Script**: `scripts/paper/plot_runtime_scaling.py` (if exists; may need creation)

**Purpose**: 
- Log-scale plot: Solve time [minutes] vs. number of constraints/variables
- Show L1→L3 scaling behavior; compare vs. theoretical branch-and-cut complexity

**Execution**:

```powershell
python scripts/paper/plot_runtime_scaling.py
```

**Output**: `outputs/paper_results/Figure_5_runtime_scaling.png` (300 DPI, 8×6 inch)

**Insertion Point**: Section 5.3 (computational performance)

---

## PHASE 4: RESULTS INTEGRATION

### 4.1 Update Section 5 (Results) with Real Data

**Manual steps**:

1. **Open**: `docs/paper 1/PAPER_DRAFT_SECTIONS_4-7.md`
2. **Replace Table 1** (line ~180):
   - Delete placeholder
   - Copy-paste content from `outputs/paper_results/TABLE_1_cost_breakdown.md`
3. **Replace Table 2** (line ~200):
   - Delete placeholder
   - Copy-paste content from `outputs/paper_results/TABLE_2_energy_flows.md`
4. **Replace Table 3** (line ~280):
   - Delete placeholder
   - Copy-paste content from `outputs/paper_results/TABLE_3_solver_stats.md`
5. **Add Figures**:
   - After Section 5.1: Embed `Figure_1_cost_comparison.png`
   - After Section 5.2: Embed `Figure_2_dispatch_comparison.png` and `Figure_3_storage_comparison.png`
   - After Section 5.3: Embed `Figure_4_pipe_losses.png` and `Figure_5_runtime_scaling.png`

**Markdown embedding**:
```markdown
![Cost Comparison](../../outputs/paper_results/Figure_1_cost_comparison.png)
*Figure 1: Annual cost breakdown comparison across L1 (copperplate), L2 (simplified), and L3 (realistic) topology levels.*
```

### 4.2 Update Section 6 (Discussion) with Actual Findings

1. Review discovery differences between expected (Sections 4–7 draft) vs. actual results
2. Adjust narrative interpretation if results differ by >5%
3. Update sensitivity analysis commentary (Section 5.3) with real numbers

---

## PHASE 5: VALIDATION & QUALITY ASSURANCE

### 5.1 Sanity Checks

- [ ] All L1 costs < L2 < L3 costs? (Expected: L1 ~€3.3M < L2 ~€3.27M < L3 ~€3.32M)
- [ ] Solver times scale as ~4–6× per model size increase? (Expected: L1 ~2 min, L2 ~8–10 min, L3 ~15–20 min)
- [ ] MIP gaps <1% for all three? (Expected: L1 <0.1%, L2 <0.5%, L3 <1%)
- [ ] Total fuel within ±2% across levels? (Expected: ~163.5 GWh ±3.2 GWh)
- [ ] Network losses L1=0, L2≈26 GWh, L3≈26 GWh? (Expected: L1 always zero by design)

### 5.2 Figure Quality Checks

- [ ] All figures 300 DPI minimum
- [ ] Text readable at 50% zoom
- [ ] Color scheme printer-friendly (no red-green-only distinguishable colors)
- [ ] Axes labeled, units included
- [ ] Legend visible and non-overlapping with data

### 5.3 Table Formatting Checks

- [ ] Column headers clear and concise
- [ ] Units in parentheses or separate row
- [ ] Numerical values: consistent decimal places
- [ ] Markdown rendering looks good in GitHub/preview

---

## PHASE 6: PREPARE FOR PUBLICATION

### 6.1 Create Publication Package

```powershell
# Create output directory
mkdir outputs/paper_publication_v1

# Copy final documents
Copy-Item docs/paper\ 1/PAPER_DRAFT_SECTIONS_1-3.md outputs/paper_publication_v1/
Copy-Item docs/paper\ 1/PAPER_DRAFT_SECTIONS_4-7.md outputs/paper_publication_v1/
Copy-Item docs/paper\ 1/APPENDIX_EQUATIONS_AND_PROOFS.md outputs/paper_publication_v1/

# Copy all figures and tables
Copy-Item outputs/paper_results/Figure_*.png outputs/paper_publication_v1/
Copy-Item outputs/paper_results/TABLE_*.csv outputs/paper_publication_v1/

# Create README
echo "# CALION Paper v1.0 — Publication Package
> Joint Investment-Operation Optimization for Electrified Industrial Heat Networks

- Sections 1-3: Methodology, formulation, linearization proofs
- Sections 4-7: Case study, results, discussion, conclusion
- Appendix: Mathematical proofs, implementation details
- Figures: 5 publication-ready plots (300 DPI)
- Tables: 5 data tables (CSV + Markdown)

Total word count: ~12,500 words
" > outputs/paper_publication_v1/README.md
```

### 6.2 Final Pre-Submission Review

- [ ] All 34 equations numbered and referenced (Sections 1–3)
- [ ] All 5 theorems listed with page references (Appendix A.2)
- [ ] All 5 tables embedded and numbered
- [ ] All 5 figures embedded and numbered
- [ ] References formatted consistently (APA or journal style)
- [ ] Abstract <300 words (if required)
- [ ] Keywords 5–10 terms
- [ ] Author affiliations and conflict-of-interest statements

---

## TROUBLESHOOTING GUIDE

### Problem: "Config file not found"
**Solution**: Verify paths in `run_all_levels.py`:
```python
configs = {
    "L1": "configs/paper/L1_copperplate_dispatch.yaml",
    "L2": "configs/paper/L2_simplified_dispatch.yaml",
    "L3": "configs/paper/L3_detailed_dispatch.yaml",
}
```

### Problem: "Memory error during L3 solve"
**Solution**: Reduce temporal resolution:
1. Modify config: `time_horizon: 4392` (seasonal instead of annual)
2. Run script: `python scripts/paper/run_all_levels.py --horizon 4392`
3. Note: Results will shift ±2–3% due to missing shoulder seasons

### Problem: "HiGHS solver timeout (>1 hour)"
**Solution**: Relax MIP optimality:
1. Edit config: `termination.mip_gap: 0.05` (0.5% instead of 0.1%)
2. Typical impact: Cost within ±0.5% of true optimum
3. Solve time drops to ~10–15 min for L3

### Problem: "Figures don't generate"
**Solution**: Check matplotlib and seaborn:
```powershell
pip install matplotlib seaborn --upgrade
python scripts/paper/plot_cost_comparison.py --verbose
```

### Problem: "Table extraction fails"
**Solution**: Verify result CSV files exist:
```powershell
Get-ChildItem outputs/paper_results/L*_results.csv
```
If missing, re-run `run_all_levels.py` and check for solver errors.

---

## EXECUTION TIMELINE

| Phase | Task | Estimated Time | Cumulative |
|-------|------|--------|----------|
| 1 | Environment check | 5 min | 5 min |
| 2a | L1 optimization | 2 min | 7 min |
| 2b | L2 optimization | 9 min | 16 min |
| 2c | L3 optimization | 17 min | 33 min |
| 3a–3e | Extract tables + generate figures | 5 min | 38 min |
| 4 | Manual results integration into paper | 30 min | 68 min |
| 5 | Validation & QA checks | 15 min | 83 min |
| 6 | Create publication package | 10 min | 93 min |

**Total estimated time**: ~1.5–2 hours for complete publication-ready package

---

## NEXT EXECUTABLE COMMAND

Once all 6 phases complete, run this final check:

```powershell
# Verify all publication files ready
Get-Item outputs/paper_publication_v1/* | Format-Table Name, Length, LastWriteTime

# Count words in final document
(Get-Content docs/paper\ 1/PAPER_DRAFT_SECTIONS_1-3.md | Measure-Object -Word).Words
(Get-Content docs/paper\ 1/PAPER_DRAFT_SECTIONS_4-7.md | Measure-Object -Word).Words
# Total should be ~12,500 words

echo "✓ Paper package ready for journal submission!"
```

---

## PUBLICATION CHECKLIST (Final)

Before submitting to Energy Conversion & Management:

- [ ] Paper complete: Sections 1–7 + Appendix (~12,500 words)
- [ ] All 34 equations numbered and referenced
- [ ] All 5 tables embedded (300 rows each minimum)
- [ ] All 5 figures at 300+ DPI, printer-ready
- [ ] References: 20+ citations, formatted per journal style
- [ ] Author statement: Contributions, funding, conflicts
- [ ] Supplementary: Appendix equations, proofs, algorithms
- [ ] Cover letter: Addressed to Editor-in-Chief, positioning vs. prior work
- [ ] Highlights: 3–5 bullet points of key findings
- [ ] Data availability: Code + configs in GitHub, data pseudonymized

---

**Document Version**: 1.0  
**Last Updated**: April 1, 2026  
**Status**: Ready to execute
