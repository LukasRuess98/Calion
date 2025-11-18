# EnerGIS Paper - Applied Energy Submission

**Status:** In Preparation
**Target Journal:** Applied Energy (Elsevier)
**Expected Submission:** TBD (after case study completion)

---

## Directory Structure

```
paper/
├── README.md                          # This file
├── SUBMISSION_CHECKLIST.md            # Pre-submission checklist
├── manuscript.md                      # Main manuscript (DRAFT)
├── formulation.tex                    # Mathematical formulation (LaTeX)
├── references.bib                     # Bibliography (BibTeX format)
├── case_study_requirements.md         # Data and execution requirements
│
├── figures/                           # Publication-ready figures
│   ├── figure_styles.py               # Matplotlib style configuration
│   ├── create_paper_figures.py        # Script to generate all figures
│   ├── figure1_architecture.pdf       # (generated)
│   ├── figure2_rolling_horizon.pdf    # (generated)
│   ├── ...                            # Other figures
│   └── graphical_abstract.png         # High-res graphical abstract
│
├── supplementary/                     # Supplementary material
│   ├── S1_complete_formulation.md     # Complete MILP formulation
│   ├── S2_parameter_tables.md         # All parameter tables
│   ├── S3_validation_results.md       # (to be created)
│   └── S4_benchmark_comparison.md     # (to be created)
│
├── benchmarking/                      # Benchmarking framework
│   ├── benchmark_framework.py         # EnerGIS vs. oemof comparison
│   ├── results/                       # Benchmark results (generated)
│   └── README.md                      # Benchmarking documentation
│
└── results/                           # Case study results (generated)
    ├── planning_framework/            # PF results
    ├── rolling_horizon/               # RH results
    ├── sensitivity/                   # Sensitivity analysis
    └── validation/                    # Validation against historical data
```

---

## Manuscript Status

### Current Word Count
- **Target:** 7,000-8,000 words
- **Current:** ~3,000 words (structure + Abstract + partial Introduction)
- **Remaining:** ~4,500 words (Methodology, Results, Discussion, Conclusion)

### Completion Status

| Section | Status | Progress | Target Words |
|---------|--------|----------|--------------|
| Abstract | ✅ Complete | 247/250 | 200-250 |
| Keywords | ✅ Complete | 6/6 | 6 max |
| Highlights | ✅ Complete | 5/5 | 3-5 |
| 1. Introduction | ⚠️ Partial | ~800/1,500 | 1,500 |
| 2. Literature Review | 📝 Outline | 0/2,000 | 2,000 |
| 3. Methodology | 📝 Outline | 0/2,500 | 2,500 |
| 4. Case Study | 📝 Outline | 0/1,000 | 1,000 |
| 5. Results | 📝 Outline | 0/1,500 | 1,500 |
| 6. Discussion | 📝 Outline | 0/1,200 | 1,200 |
| 7. Conclusions | 📝 Outline | 0/600 | 600 |
| References | ⚠️ Partial | 50+ refs | 40-60 refs |

**Legend:**
- ✅ Complete and ready
- ⚠️ Partial - needs expansion
- 📝 Outline only - needs writing
- ❌ Not started

---

## Figures Status

### Required Figures (Main Manuscript)

| Figure | Status | File | Description |
|--------|--------|------|-------------|
| Graphical Abstract | 📝 Script ready | `graphical_abstract.png` | Workflow diagram |
| Figure 1 | 📝 Script ready | `figure1_architecture.pdf` | Framework architecture |
| Figure 2 | 📝 Script ready | `figure2_rolling_horizon.pdf` | RH schematic |
| Figure 3 | 📝 Script ready | `figure3_cost_breakdown.pdf` | Cost breakdown |
| Figure 4 | 📝 Script ready | `figure4_typical_week.pdf` | Dispatch time series |
| Figure 5 | 📝 Script ready | `figure5_performance.pdf` | Benchmark comparison |
| Figure 6 | 📝 Script ready | `figure6_co2_sensitivity.pdf` | CO₂ sensitivity |

**Note:** Scripts are ready with synthetic data. Final figures require actual case study results.

### Generating Figures

```bash
cd paper/figures/

# Generate all figures
python create_paper_figures.py --all

# Generate specific figure
python create_paper_figures.py --figure 1

# Generate graphical abstract
python create_paper_figures.py --figure graphical_abstract
```

---

## Supplementary Material Status

| File | Status | Description |
|------|--------|-------------|
| S1: Complete Formulation | ✅ Ready | Mathematical formulation (reference to formulation.tex) |
| S2: Parameter Tables | ✅ Ready | All component parameters |
| S3: Validation Results | ❌ Pending | Needs case study execution |
| S4: Benchmark Comparison | ❌ Pending | Needs benchmark runs |
| S5: Configuration Files | ✅ Ready | Link to repository configs |

---

## References

**Current Status:** 50+ references collected
**Target:** 40-60 high-quality references

**Bibliography File:** `references.bib` (BibTeX format)

### Key Reference Categories

1. **Open-Source Frameworks:** oemof, PyPSA, Calliope, OSeMOSYS (10 refs)
2. **District Heating:** 4GDH, planning methods, reviews (8 refs)
3. **Heat Pumps:** Integration, COP modeling, P2H (6 refs)
4. **Storage:** TES review, optimization, seasonal storage (5 refs)
5. **Optimization Methods:** MILP, unit commitment, rolling horizon (8 refs)
6. **Multi-Energy Systems:** Energy hubs, sector coupling (4 refs)
7. **Waste Heat:** Industrial symbiosis, potential studies (3 refs)
8. **Software & Reproducibility:** Best practices, open science (4 refs)
9. **Policy & Targets:** EU heating strategy, decarbonization (3 refs)
10. **Pyomo & Solvers:** Pyomo documentation (2 refs)

**Action Items:**
- [ ] Verify all DOIs
- [ ] Add 2024-2025 recent papers
- [ ] Ensure all citations are in manuscript

---

## Case Study Requirements

**See:** `case_study_requirements.md` for detailed requirements

### Critical Data Needs

- [ ] Full-year heat demand (8760h)
- [ ] Electricity prices (8760h)
- [ ] Grid CO₂ intensity (8760h)
- [ ] Component parameters validated
- [ ] Waste heat source characterization

### Execution Status

- [ ] Planning Framework run (full year)
- [ ] Rolling Horizon run (365 windows)
- [ ] Benchmark comparison (EnerGIS vs. oemof)
- [ ] Sensitivity analysis (CO₂, elec price, etc.)
- [ ] Validation against historical data (if available)

---

## Pre-Submission Checklist

**See:** `SUBMISSION_CHECKLIST.md` for complete checklist

### Critical Items (Must Complete Before Submission)

1. [ ] Manuscript complete (7,000-8,000 words)
2. [ ] All figures publication-ready (300 DPI)
3. [ ] Supplementary material complete
4. [ ] References verified and complete
5. [ ] Code repository public with DOI (Zenodo)
6. [ ] Data availability statement finalized
7. [ ] All author contributions documented
8. [ ] Internal review completed
9. [ ] English language check
10. [ ] Applied Energy formatting verified

---

## Timeline

### Phase 1: Data & Execution (4-6 weeks)
**Target Completion:** TBD
- Collect all required data
- Run all case studies
- Complete benchmarking
- Perform sensitivity analyses

### Phase 2: Writing (4-6 weeks)
**Target Completion:** TBD
- Complete all manuscript sections
- Create all final figures
- Finalize supplementary material
- Internal reviews and revisions

### Phase 3: Finalization (2 weeks)
**Target Completion:** TBD
- Address review comments
- Final formatting check
- Submission package preparation

### Target Submission Date: TBD
*(Dependent on data availability)*

---

## Tools and Scripts

### Manuscript Tools

**LaTeX Compilation:**
```bash
cd paper/
pdflatex formulation.tex
bibtex formulation
pdflatex formulation.tex
pdflatex formulation.tex
```

**Word Count:**
```bash
# Markdown word count
wc -w manuscript.md

# For specific sections
grep -A 100 "## 1. Introduction" manuscript.md | wc -w
```

### Figure Generation

```bash
# Set publication style
python figures/figure_styles.py

# Generate all figures
python figures/create_paper_figures.py --all

# Generate specific figure
python figures/create_paper_figures.py --figure 3
```

### Benchmarking

```bash
cd benchmarking/

# Run parity check
python benchmark_framework.py --test parity

# Run full benchmark suite
python benchmark_framework.py --full --export results/comparison.csv
```

---

## Applied Energy Submission Requirements

### Article Requirements

- **Length:** 6,000-8,000 words (or max 25 pages, one-column, 11pt)
- **Abstract:** Concise and factual
- **Keywords:** Maximum 6
- **Highlights:** 3-5 bullet points (max 85 characters each)
- **Graphical Abstract:** Encouraged (min 531×1328 pixels)

### Data & Code Requirements

> "This journal encourages and enables you to share data that supports your research publication where appropriate. To facilitate reproducibility and data reuse, this journal also encourages you to share your software, code, models, algorithms, protocols, methods and other useful materials related to the project."

**Our Plan:**
- ✅ Code: Public GitHub + Zenodo DOI
- ⚠️ Data: Anonymized when possible, synthetic alternative provided
- ✅ Methods: Complete formulation in supplementary material

### Article Processing Charge (APC)

- **Cost:** $4,210 USD (excluding taxes)
- **Payment:** Upon acceptance
- **Open Access:** Optional but encouraged

---

## Contact and Collaboration

**Primary Author:** [Your Name]
**Corresponding Author:** [Your Email]

**Repository:** https://github.com/LukasRuess98/Planing-Framework-for-Heat
**Zenodo DOI:** [To be assigned upon submission]

---

## Version History

- **v1.0 (2025-11-18):** Initial structure, templates, and outlines created
- **v1.1 (TBD):** First complete draft
- **v2.0 (TBD):** Final version for submission

---

## Notes for Authors

### Writing Guidelines

1. **Be concise:** Applied Energy values clear, direct writing
2. **Emphasize novelty:** Clearly state what's new compared to existing frameworks
3. **Show validation:** Strong empirical validation is critical
4. **Discuss limitations:** Be transparent about assumptions and limitations
5. **Highlight practical impact:** Show relevance to practitioners and policymakers

### Common Pitfalls to Avoid

- ❌ Insufficient validation with real data
- ❌ No comparison with existing tools
- ❌ Unclear novelty/contribution
- ❌ Missing sensitivity analyses
- ❌ Poor figure quality (low DPI)
- ❌ Incomplete data availability statement
- ❌ No code repository

### Strengths to Emphasize

- ✅ Open-source with comprehensive documentation
- ✅ Modular, extensible architecture
- ✅ Dual-phase optimization (unique)
- ✅ Validated against real network
- ✅ Benchmarked against oemof
- ✅ Publication-ready code and data

---

## Additional Resources

- **Applied Energy Homepage:** https://www.elsevier.com/journals/applied-energy/0306-2619
- **Author Guidelines:** https://www.elsevier.com/journals/applied-energy/0306-2619/guide-for-authors
- **LaTeX Template:** Available from Elsevier (optional, can submit in Word)
- **Formatting Tool:** Overleaf has Applied Energy template

---

**Last Updated:** 2025-11-18
**Next Review:** Upon case study completion
