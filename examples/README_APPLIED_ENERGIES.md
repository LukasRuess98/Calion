# Applied Energies Publication Export - Examples

This directory contains examples for generating publication-ready outputs for Applied Energy journal submission.

## Quick Start

### Option 1: Python Script (Recommended)

```bash
# Run with Applied Energies configuration
python examples/applied_energies_export_example.py

# With custom config
python examples/applied_energies_export_example.py --config configs/your_config.yaml

# Custom DPI and formats
python examples/applied_energies_export_example.py --dpi 600 --formats pdf,eps,png
```

**Output:** `exports/applied_energies_run/`

### Option 2: Jupyter Notebook

```bash
# Start Jupyter
jupyter notebook notebooks/runner.ipynb

# Uncomment and run the export cell (Cell 11)
```

### Option 3: Direct Orchestrator Call

```python
from energis.run import orchestrator

# With Applied Energies config
result = orchestrator.run_all(
    ["configs/applied_energies_config.yaml"],
    overrides={
        "export": {
            "enable_publication_exports": True,
            "publication_dpi": 600,
            "publication_formats": ["pdf", "png", "eps"]
        }
    }
)

print(f"Exports in: {result['outdir']}")
```

---

## Files Generated

When using Applied Energies configuration:

### Main Directory: `exports/applied_energies_run/`

```
exports/applied_energies_run/
├── scenario.xlsx                   # Complete results workbook
├── pf_design.json                  # Design decisions
├── costs.json                      # Cost breakdown
├── summary.json                    # All KPIs
├── metadata.json                   # Run metadata
├── kpi_summary.json               # Complete KPI summary
├── kpi_summary.csv                # KPIs for Excel
│
├── publication_plots/              # All figures (600 DPI)
│   ├── heat_balance_publication.pdf
│   ├── heat_balance_publication.png
│   ├── heat_balance_publication.eps
│   ├── electric_balance_publication.{pdf,png,eps}
│   ├── storage_operation_publication.{pdf,png,eps}
│   ├── cost_breakdown_publication.{pdf,png,eps}
│   ├── cop_analysis_publication.{pdf,png,eps}
│   ├── emissions_publication.{pdf,png,eps}
│   ├── load_duration_curve_publication.{pdf,png,eps}
│   ├── monthly_demand_publication.{pdf,png,eps}
│   ├── technology_comparison_publication.{pdf,png,eps}
│   └── capex_opex_publication.{pdf,png,eps}
│
├── publication_latex/              # LaTeX tables
│   ├── kpi_summary.tex
│   ├── cost_breakdown.tex
│   └── design_decisions.tex
│
└── applied_energies/               # Journal-specific
    ├── graphical_abstract.pdf      ← REQUIRED
    ├── graphical_abstract.png
    ├── highlights.txt              ← REQUIRED
    ├── nomenclature.tex
    ├── manuscript_template.tex
    └── SUBMISSION_CHECKLIST.md
```

---

## Configuration

### Minimal Config (enable exports)

```yaml
# your_config.yaml
export:
  enable_publication_exports: true
```

### Full Applied Energies Config

See: `configs/applied_energies_config.yaml`

Key settings:
```yaml
export:
  enable_publication_exports: true
  publication_dpi: 600
  publication_formats: [pdf, png, eps]
  latex_table_style: "applied_energies"

applied_energies:
  generate_graphical_abstract: true
  generate_highlights: true
  generate_nomenclature: true
  generate_supplementary: true
```

---

## Environment Variables

You can also control exports via environment variables:

```bash
# Enable publication exports
export ENABLE_PUBLICATION_EXPORTS=1

# Set DPI
export PUBLICATION_DPI=600

# Set formats (comma-separated)
export PUBLICATION_FORMATS="pdf,eps,png"

# Run
python examples/applied_energies_export_example.py
```

---

## Example Scripts

### 1. `applied_energies_export_example.py`

**Purpose:** Complete Applied Energies publication export

**Features:**
- Uses `orchestrator.run_all()`
- Generates all journal-required materials
- Command-line arguments for customization
- Displays summary of generated files

**Usage:**
```bash
python examples/applied_energies_export_example.py [OPTIONS]

Options:
  --config PATH         Config file (default: configs/applied_energies_config.yaml)
  --export-dir PATH     Export directory (default: exports/applied_energies_run)
  --dpi INT            Figure DPI (default: 600)
  --formats STR        Formats, comma-separated (default: pdf,png)
  --help               Show help
```

**Example:**
```bash
# High-quality export for submission
python examples/applied_energies_export_example.py \
  --dpi 600 \
  --formats pdf,eps,png
```

### 2. `standalone_heat_planning_example.py`

**Purpose:** Standalone example with custom export logic

**Note:** This script does **NOT** use the publication export system.
It has its own export functions and generates basic Excel outputs only.

**To use publication exports with this workflow:**
- Modify to call `orchestrator.run_all()` instead of custom export functions
- Or use `applied_energies_export_example.py` instead

### 3. `custom_component_example.py`

**Purpose:** Demonstrates custom component development

**Note:** This is a development example, not for publication exports.

---

## Integration in Your Own Scripts

### Basic Integration

```python
from energis.run import orchestrator

# Your configuration
config_files = ["configs/applied_energies_config.yaml"]

# Run with publication exports enabled
result = orchestrator.run_all(
    config_files,
    overrides={
        "export": {
            "enable_publication_exports": True,
            "publication_dpi": 600,
            "publication_formats": ["pdf", "png"]
        }
    }
)

# Access outputs
outdir = result["outdir"]
plots = result.get("publication_plots", {})
tables = result.get("publication_files", {}).get("latex_tables", {})
ae_bundle = result.get("publication_files", {}).get("applied_energies", {})

print(f"✅ Exports completed: {outdir}")
```

### Advanced Integration

```python
from energis.run import orchestrator
from energis.io import (
    export_publication_plots,
    export_applied_energies_bundle,
    generate_graphical_abstract
)

# 1. Run optimization (without auto-exports)
config = load_and_merge(["configs/your_config.yaml"])
result = orchestrator.run_optimization(config)

# 2. Custom processing of results
# ... your analysis ...

# 3. Generate publication exports manually
outdir = "exports/custom/"

# Generate plots
plots = export_publication_plots(
    outdir + "plots/",
    result["table"],
    result["series"],
    result["summary"],
    dpi=600,
    formats=["pdf", "eps"],
    plot_types=["heat_balance", "cost_breakdown"]  # Select specific plots
)

# Generate Applied Energies bundle
ae_bundle = export_applied_energies_bundle(
    outdir + "applied_energies/",
    result["summary"],
    config
)

print(f"Custom exports: {outdir}")
```

---

## Troubleshooting

### Problem: "Matplotlib not available"

**Solution:**
```bash
pip install matplotlib
```

### Problem: "No publication exports generated"

**Check:**
1. Is `enable_publication_exports: true` in config?
2. Using `orchestrator.run_all()`? (required)
3. Check logs for errors

**Debug:**
```python
result = orchestrator.run_all(...)
print("Publication plots:", result.get("publication_plots"))
print("Publication files:", result.get("publication_files"))
```

### Problem: "Applied Energies bundle not generated"

**Check:**
1. Config has `applied_energies` section?
2. Flags are enabled: `generate_graphical_abstract: true`, etc.

**Minimal config:**
```yaml
export:
  enable_publication_exports: true

applied_energies:
  generate_graphical_abstract: true
  generate_highlights: true
```

### Problem: "Figures too large/small"

**Solution:** Adjust DPI
```yaml
export:
  publication_dpi: 300  # Standard
  # or
  publication_dpi: 600  # High quality
```

### Problem: "Wrong table style"

**Solution:**
```yaml
export:
  latex_table_style: "applied_energies"  # Horizontal lines only
  # or
  latex_table_style: "booktabs"          # Professional style
```

---

## Comparison: Scripts vs Orchestrator

| Feature | `standalone_example.py` | `applied_energies_export_example.py` | `orchestrator.run_all()` |
|---------|-------------------------|--------------------------------------|--------------------------|
| **Runs optimization** | ✅ Yes | ✅ Yes | ✅ Yes |
| **Basic Excel export** | ✅ Yes | ✅ Yes | ✅ Yes |
| **Publication plots** | ❌ No | ✅ Yes | ✅ Yes |
| **LaTeX tables** | ❌ No | ✅ Yes | ✅ Yes |
| **Graphical abstract** | ❌ No | ✅ Yes (if configured) | ✅ Yes (if configured) |
| **Highlights** | ❌ No | ✅ Yes (if configured) | ✅ Yes (if configured) |
| **Nomenclature** | ❌ No | ✅ Yes (if configured) | ✅ Yes (if configured) |
| **Uses orchestrator** | ❌ No | ✅ Yes | ✅ Yes (direct) |
| **Standalone** | ✅ Yes | ❌ No (needs orchestrator) | ❌ No |
| **Good for learning** | ✅ Yes | ⚠️ Medium | ❌ No |
| **Good for publications** | ❌ No | ✅ Yes | ✅ Yes |

**Recommendation:** Use `applied_energies_export_example.py` or direct `orchestrator.run_all()` for publication exports.

---

## Next Steps

1. **Run example:**
   ```bash
   python examples/applied_energies_export_example.py
   ```

2. **Review outputs:**
   ```bash
   ls -la exports/applied_energies_run/applied_energies/
   ```

3. **Read submission guide:**
   ```bash
   open docs/APPLIED_ENERGIES_GUIDE.md
   ```

4. **Customize config:**
   ```bash
   cp configs/applied_energies_config.yaml configs/my_paper.yaml
   # Edit my_paper.yaml with your metadata
   ```

5. **Run with your config:**
   ```bash
   python examples/applied_energies_export_example.py --config configs/my_paper.yaml
   ```

---

## Documentation

- **Complete Guide:** `docs/APPLIED_ENERGIES_GUIDE.md`
- **Publication Exports:** `docs/PUBLICATION_EXPORTS.md`
- **Config Reference:** `configs/applied_energies_config.yaml`
- **Main README:** `README.md`

---

## Support

For issues:
1. Check this README
2. Review `docs/APPLIED_ENERGIES_GUIDE.md`
3. Check example output in `exports/`
4. Open GitHub issue

---

Happy Publishing! 🚀📄
