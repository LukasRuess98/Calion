# Publication Export Guide

This guide explains how to generate publication-ready outputs from the Heat Planning Framework for submission to scientific journals like **Applied Energies**, **Energy Conversion and Management**, or similar energy systems journals.

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Export Types](#export-types)
- [Configuration](#configuration)
- [Generated Outputs](#generated-outputs)
- [Journal-Specific Guidelines](#journal-specific-guidelines)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

---

## Overview

The publication export system provides:

- **High-resolution plots** (300-600 DPI) in multiple formats (PNG, PDF, EPS)
- **LaTeX tables** ready for insertion into your manuscript
- **KPI summaries** in JSON and CSV formats
- **Statistical analyses** for supplementary material
- **Colorblind-friendly visualizations** following scientific best practices

### Key Features

✓ Publication-quality figures with professional styling
✓ Multiple export formats for different submission requirements
✓ LaTeX tables with booktabs styling
✓ Comprehensive KPI summaries
✓ Technology comparison plots
✓ Economic analysis (CAPEX vs OPEX)
✓ Environmental metrics (CO₂ emissions)
✓ System performance analysis (COP, efficiency)

---

## Quick Start

### 1. Basic Usage

Enable publication exports in your configuration file:

```yaml
export:
  enable_publication_exports: true
  publication_dpi: 300
  publication_formats:
    - png
    - pdf
  latex_table_style: "booktabs"
```

### 2. Run Your Analysis

```bash
python examples/standalone_heat_planning_example.py \
  --config configs/publication_export_config.yaml
```

### 3. Find Your Outputs

Generated files will be in:
- `exports/publication_plots/` - High-resolution figures
- `exports/publication_latex/` - LaTeX tables
- `exports/kpi_summary.json` - Complete metrics
- `exports/kpi_summary.csv` - Metrics for Excel

---

## Export Types

### 1. Publication Plots

#### Heat Balance
**File:** `heat_balance_publication.{png,pdf,eps}`

Shows heat supply from all sources (heat pumps, boilers, storage, waste heat) stacked against heat demand.

**Usage in paper:**
- Methods section: System configuration
- Results section: Operational dispatch strategy

**LaTeX example:**
```latex
\begin{figure}[htbp]
\centering
\includegraphics[width=\columnwidth]{figures/heat_balance_publication.pdf}
\caption{Hourly heat supply and demand balance for the optimized system.
Heat pumps (HP1-4) provide base load, with gas boilers and thermal storage
covering peak demands.}
\label{fig:heat_balance}
\end{figure}
```

#### Electric Balance
**File:** `electric_balance_publication.{png,pdf,eps}`

Shows electricity consumption by heat pumps and P2H units, along with grid import/export.

**Usage in paper:**
- Results section: Grid interaction analysis
- Discussion: Peak demand reduction strategies

#### Storage Operation
**File:** `storage_operation_publication.{png,pdf,eps}`

Displays thermal storage state of charge and charge/discharge power over time.

**Usage in paper:**
- Results section: Storage utilization
- Discussion: Flexibility provision

#### Cost Breakdown
**File:** `cost_breakdown_publication.{png,pdf,eps}`

Horizontal bar chart showing cost components (energy, fuel, CAPEX, CO₂, etc.).

**Usage in paper:**
- Results section: Economic analysis
- Discussion: Cost drivers

#### COP Analysis
**File:** `cop_analysis_publication.{png,pdf,eps}`

Heat pump Coefficient of Performance over time, showing efficiency variations.

**Usage in paper:**
- Results section: Technology performance
- Methods section: Validation of COP assumptions

#### Emissions Analysis
**File:** `emissions_publication.{png,pdf,eps}`

Annual CO₂ emissions breakdown.

**Usage in paper:**
- Results section: Environmental impact
- Discussion: Decarbonization potential

#### Load Duration Curve
**File:** `load_duration_curve_publication.{png,pdf,eps}`

Sorted heat demand showing peak, base, and average loads.

**Usage in paper:**
- Methods section: System sizing rationale
- Results section: Capacity factor analysis

#### Monthly Aggregation
**File:** `monthly_demand_publication.{png,pdf,eps}`

Monthly heat demand aggregation showing seasonal patterns.

**Usage in paper:**
- Results section: Seasonal analysis
- Discussion: Seasonal storage potential

#### Technology Comparison
**File:** `technology_comparison_publication.{png,pdf,eps}`

Bar chart comparing heat production by different technologies.

**Usage in paper:**
- Results section: Technology mix
- Discussion: Optimal portfolio

#### CAPEX vs OPEX
**File:** `capex_opex_publication.{png,pdf,eps}`

Capital expenditure vs operational expenditure comparison.

**Usage in paper:**
- Results section: Economic analysis
- Discussion: Investment vs operational trade-offs

---

### 2. LaTeX Tables

#### KPI Summary Table
**File:** `publication_latex/kpi_summary.tex`

Key performance indicators in a publication-ready table.

**Metrics included:**
- Total system cost [EUR]
- Energy cost [EUR]
- Investment cost [EUR]
- CO₂ emissions [t]
- Grid import [MWh]
- Peak demand [MW]

**LaTeX preamble requirements:**
```latex
\usepackage{booktabs}
\usepackage{siunitx}
```

**Usage:**
```latex
\input{tables/kpi_summary.tex}
```

#### Cost Breakdown Table
**File:** `publication_latex/cost_breakdown.tex`

Detailed cost breakdown with absolute values and percentages.

**Columns:**
- Cost Component
- Value [EUR]
- Share [%]

**Usage in paper:**
- Results section: Economic analysis
- Supplementary material: Detailed cost data

#### Design Decisions Table
**File:** `publication_latex/design_decisions.tex`

Optimal system design (capacities and build decisions).

**Rows:**
- Heat Pump 1-4 capacities [MW]
- Storage capacity [MWh]
- Storage power [MW]

**Usage in paper:**
- Results section: Optimal configuration
- Methods section: Technology options

---

### 3. Data Exports

#### KPI Summary JSON
**File:** `kpi_summary.json`

Complete metrics in structured JSON format for further processing.

**Sections:**
- `economic`: All cost components
- `environmental`: Emissions data
- `grid`: Grid interaction metrics
- `heat_pumps`: Individual HP performance
- `storage`: Storage metrics
- `system`: Overall system performance

**Example content:**
```json
{
  "economic": {
    "total_cost_EUR": 1234567.89,
    "energy_cost_EUR": 456789.12,
    "investment_cost_EUR": 234567.89
  },
  "environmental": {
    "total_co2_emissions_t": 1234.56
  },
  "heat_pumps": {
    "HP1": {
      "capacity_MW": 10.5,
      "average_cop": 3.45
    }
  }
}
```

#### KPI Summary CSV
**File:** `kpi_summary.csv`

Flattened metrics for easy import into Excel or other tools.

**Format:**
```csv
Metric;Value
economic.total_cost_EUR;1234567.89
economic.energy_cost_EUR;456789.12
environmental.total_co2_emissions_t;1234.56
```

---

## Configuration

### Minimal Configuration

```yaml
export:
  enable_publication_exports: true
```

### Full Configuration

```yaml
export:
  enable_publication_exports: true
  publication_dpi: 600  # 300 or 600 for print
  publication_formats:
    - png  # Raster (Word, PowerPoint)
    - pdf  # Vector (LaTeX, preferred)
    - eps  # Vector (some publishers require EPS)
  latex_table_style: "booktabs"  # or "simple" or "ieee"

  # Selective plot generation
  publication_plot_types:
    - heat_balance
    - cost_breakdown
    - cop_analysis
    - emissions
    - technology_comparison
```

### Configuration via Environment Variables

You can also enable publication exports via environment variables:

```bash
export ENABLE_PUBLICATION_EXPORTS=1
export PUBLICATION_DPI=600
export PUBLICATION_FORMATS="png,pdf,eps"

python examples/standalone_heat_planning_example.py
```

---

## Generated Outputs

After running with publication exports enabled, you'll find:

```
exports/
├── publication_plots/          # High-resolution figures
│   ├── heat_balance_publication.png
│   ├── heat_balance_publication.pdf
│   ├── electric_balance_publication.png
│   ├── electric_balance_publication.pdf
│   ├── storage_operation_publication.png
│   ├── storage_operation_publication.pdf
│   ├── cost_breakdown_publication.png
│   ├── cost_breakdown_publication.pdf
│   ├── cop_analysis_publication.png
│   ├── cop_analysis_publication.pdf
│   ├── emissions_publication.png
│   ├── emissions_publication.pdf
│   ├── load_duration_curve_publication.png
│   ├── load_duration_curve_publication.pdf
│   ├── monthly_demand_publication.png
│   ├── monthly_demand_publication.pdf
│   ├── technology_comparison_publication.png
│   ├── technology_comparison_publication.pdf
│   ├── capex_opex_publication.png
│   └── capex_opex_publication.pdf
│
├── publication_latex/          # LaTeX tables
│   ├── kpi_summary.tex
│   ├── cost_breakdown.tex
│   └── design_decisions.tex
│
├── kpi_summary.json           # Complete metrics (JSON)
├── kpi_summary.csv            # Metrics for Excel
└── README_publication.md      # Usage guide
```

---

## Journal-Specific Guidelines

### Applied Energies

**Figure requirements:**
- Format: PDF or EPS (vector preferred)
- Resolution: 300-600 DPI for raster images
- Width: 90mm (single column) or 190mm (double column)
- Font size: Minimum 8pt

**Recommended config:**
```yaml
export:
  publication_dpi: 600
  publication_formats: [pdf, eps]
```

**Figure placement:**
- Use `\columnwidth` for single-column figures
- Use `\textwidth` for double-column figures

```latex
\includegraphics[width=\textwidth]{figures/heat_balance_publication.pdf}
```

### Energy Conversion and Management

**Figure requirements:**
- Similar to Applied Energies
- Prefer vector formats (PDF, EPS)
- High contrast for black & white printing

**Recommended config:**
```yaml
export:
  publication_dpi: 600
  publication_formats: [pdf, eps]
```

### Applied Thermal Engineering

**Figure requirements:**
- Resolution: Minimum 300 DPI
- Format: TIFF, EPS, or PDF
- Color: RGB for online, CMYK for print

**Recommended config:**
```yaml
export:
  publication_dpi: 600
  publication_formats: [pdf, eps, png]
```

---

## Best Practices

### 1. Figure Design

✓ **Use vector formats** (PDF, EPS) whenever possible
✓ **Choose appropriate size**: Single vs double column
✓ **Keep fonts readable**: Minimum 8pt after scaling
✓ **Use colorblind-friendly palettes**: Enabled by default
✓ **Include clear labels**: All axes must have units
✓ **Add descriptive captions**: Explain what, how, why

### 2. Table Formatting

✓ **Use booktabs style**: Professional appearance
✓ **Align numbers correctly**: Use siunitx for LaTeX
✓ **Include units**: Either in column headers or with values
✓ **Round appropriately**: 2-3 significant figures usually sufficient
✓ **Add table notes**: Explain abbreviations and assumptions

### 3. Data Reporting

✓ **Report all relevant metrics**: Use KPI summary
✓ **Include uncertainty**: If available from sensitivity analysis
✓ **Document assumptions**: Use metadata section
✓ **Provide raw data**: Use supplementary CSV exports
✓ **Ensure reproducibility**: Include configuration files

### 4. Manuscript Structure

**Suggested figure placement:**

- **Introduction**: Load duration curve (motivation for storage)
- **Methods**: System schematic (not auto-generated, draw manually)
- **Results - System Design**: Design decisions table, technology comparison
- **Results - Operation**: Heat balance, electric balance, storage operation
- **Results - Economics**: Cost breakdown, CAPEX vs OPEX
- **Results - Environment**: Emissions analysis
- **Discussion**: COP analysis, monthly aggregation

---

## Troubleshooting

### Issue: Plots not generated

**Symptoms:** No plots in `publication_plots/` directory

**Solutions:**
1. Check if matplotlib is installed: `pip install matplotlib`
2. Verify config: `enable_publication_exports: true`
3. Check logs for error messages
4. Ensure data is available (series must contain results)

### Issue: LaTeX tables have formatting errors

**Symptoms:** Compilation errors in LaTeX

**Solutions:**
1. Ensure required packages: `\usepackage{booktabs}`, `\usepackage{siunitx}`
2. Check for special characters in component names
3. Try `latex_table_style: "simple"` for basic tables
4. Verify table was generated successfully (check file exists)

### Issue: Figures too small/large in PDF

**Solutions:**
1. Adjust figure size in LaTeX:
   ```latex
   \includegraphics[width=0.8\textwidth]{figure.pdf}
   ```
2. Use appropriate figure size constant in config
3. For single-column: `width=\columnwidth`
4. For double-column: `width=\textwidth`

### Issue: Missing metrics in KPI summary

**Symptoms:** Some expected metrics are null or missing

**Solutions:**
1. Verify optimization completed successfully
2. Check if components are enabled in config
3. Ensure summary_sections contains required data
4. Review orchestrator logs for export warnings

### Issue: Export takes too long

**Symptoms:** Publication export adds significant runtime

**Solutions:**
1. Reduce DPI (300 instead of 600)
2. Limit formats (only PNG and PDF)
3. Select specific plot types instead of all:
   ```yaml
   publication_plot_types:
     - heat_balance
     - cost_breakdown
   ```
4. Disable publication exports during development, enable for final runs

---

## Advanced Usage

### Custom Plot Styling

For advanced users, you can modify plot styling by editing `energis/io/publication_plotter.py`:

```python
class PublicationConfig:
    # Modify colors
    COLORS_QUALITATIVE = ['#4477AA', '#EE6677', ...]

    # Modify font sizes
    FONT_SIZE_MEDIUM = 12  # Default: 10

    # Modify figure sizes
    FIGSIZE_DOUBLE_COLUMN = (8.0, 5.0)  # Default: (7.0, 4.5)
```

### Adding Custom Plots

To add your own publication plot:

1. Create function in `publication_plotter.py`:
   ```python
   def _my_custom_plot(outdir, timestamps, table, series, dpi, formats):
       fig, ax = plt.subplots(...)
       # Your plotting code here
       return _save_figure(fig, outdir, "my_custom_plot", dpi, formats)
   ```

2. Register in `export_publication_plots`:
   ```python
   plot_functions = {
       ...
       "my_custom": lambda: _my_custom_plot(...),
   }
   ```

3. Add to config:
   ```yaml
   publication_plot_types:
     - my_custom
   ```

---

## Citation

If you use the Heat Planning Framework in your publication, please cite:

```bibtex
@article{YourPaper2024,
  title={Multi-Objective Optimization of District Heating Systems},
  author={Your Name and Co-Authors},
  journal={Applied Energy},
  year={2024},
  volume={XXX},
  pages={XXX-XXX},
  doi={10.1016/j.apenergy.2024.XXXXX}
}
```

---

## Support

For issues or questions:

1. Check this documentation
2. Review example configuration: `configs/publication_export_config.yaml`
3. Open an issue on GitHub
4. Contact: [your-email@example.com]

---

## Changelog

### Version 2.0 (2024)
- Initial publication export system
- 10 standard publication plots
- LaTeX table generation
- KPI summary exports
- Colorblind-friendly default colors
- Multiple export format support
