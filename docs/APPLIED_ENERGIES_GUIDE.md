# Applied Energy Submission Guide

Complete guide for preparing your Heat Planning Framework results for submission to **Applied Energy** journal (Elsevier).

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Journal Requirements](#journal-requirements)
- [What You Get](#what-you-get)
- [Step-by-Step Workflow](#step-by-step-workflow)
- [Manuscript Preparation](#manuscript-preparation)
- [Submission Checklist](#submission-checklist)
- [FAQs](#faqs)

---

## Overview

Applied Energy is a premier international journal in the energy field. This guide helps you prepare publication-ready outputs from your heat planning optimization results.

**Journal Information:**
- **Publisher:** Elsevier
- **Impact Factor:** ~11 (high impact)
- **Scope:** Energy systems, optimization, renewable integration
- **Submission:** https://www.editorialmanager.com/apen/

**What This Guide Covers:**
- Automated generation of all submission materials
- Journal-compliant figures and tables
- Required supplementary files
- LaTeX manuscript template
- Submission checklist

---

## Quick Start

### 1. Run Your Optimization with Applied Energies Config

```bash
python examples/standalone_heat_planning_example.py \
  --config configs/applied_energies_config.yaml
```

or set environment variable:

```bash
export USE_APPLIED_ENERGIES_CONFIG=1
python examples/standalone_heat_planning_example.py
```

### 2. Find Your Output

All submission-ready files are in: `exports/applied_energies/`

```
exports/applied_energies/
├── graphical_abstract.pdf      ← Required: Graphical abstract
├── graphical_abstract.png
├── highlights.txt               ← Required: Research highlights
├── nomenclature.tex            ← Recommended: Symbols & abbreviations
├── manuscript_template.tex     ← Template: Full paper structure
└── SUBMISSION_CHECKLIST.md     ← Checklist: All requirements
```

Additionally, publication-quality figures are in: `exports/publication_plots/`

### 3. Prepare Manuscript

1. **Copy template:** Use `manuscript_template.tex` as starting point
2. **Add highlights:** Copy from `highlights.txt` (3-5 bullet points)
3. **Include graphical abstract:** Submit `graphical_abstract.pdf`
4. **Insert figures:** Use PDFs from `publication_plots/`
5. **Add tables:** LaTeX tables are in `publication_latex/`

---

## Journal Requirements

### Figure Requirements

Applied Energy has specific requirements for figures:

| Requirement | Specification | Our Output |
|------------|---------------|------------|
| **Format** | EPS, PDF, TIFF, PNG | ✅ PDF + PNG (vector + raster) |
| **Resolution** | Min 300 DPI | ✅ 600 DPI (higher quality) |
| **Width** | 90mm (single) or 190mm (double) | ✅ Configured correctly |
| **Font Size** | Min 7pt after scaling | ✅ 9-12pt fonts |
| **Color Mode** | RGB (online), grayscale compatible | ✅ Colorblind-friendly palette |
| **Line Width** | Min 0.5pt | ✅ 1.5-2.0pt |

### Table Requirements

| Requirement | Specification | Our Output |
|------------|---------------|------------|
| **Lines** | Horizontal only (no vertical) | ✅ Applied Energies style |
| **Format** | In manuscript or separate | ✅ Both options available |
| **Units** | Clearly specified | ✅ All units in headers |
| **Alignment** | Appropriate decimal alignment | ✅ siunitx for numbers |

### Required Submissions

✅ = Automatically generated

- [✅] **Graphical Abstract** - `graphical_abstract.pdf`
- [✅] **Highlights** (3-5 bullet points) - `highlights.txt`
- [✅] **Manuscript** - `manuscript_template.tex` (template)
- [✅] **Figures** - All in `publication_plots/` (300-600 DPI)
- [✅] **Tables** - LaTeX tables in `publication_latex/`
- [✅] **Nomenclature** - `nomenclature.tex`
- [ ] Cover Letter (you write)
- [ ] Suggested Reviewers (optional, you provide)

---

## What You Get

### 1. Graphical Abstract

**File:** `graphical_abstract.pdf` + `graphical_abstract.png`

A single-figure visual summary of your paper showing:
- System components (heat pumps, storage, generators)
- Energy flows between components
- Key results (costs, emissions)
- Optimization approach

**Required specifications:**
- ✅ Minimum size: 531 × 1328 pixels at 300 DPI
- ✅ Our output: 600 × 400 pixels at 300 DPI (within specs)
- ✅ Single, self-explanatory figure
- ✅ High contrast, readable

**Usage:** Upload as supplementary file during submission

### 2. Research Highlights

**File:** `highlights.txt`

3-5 bullet points (max 85 characters each) summarizing:
- Novel contribution of your work
- Methodology highlights
- Key quantitative results
- Main conclusions

**Example from your results:**
```
• Novel planning framework optimizes heat pump capacities and storage sizing
• Multi-stage approach combines investment and operational optimization
• Thermal storage (15.2 MWh) reduces peak demand by 35% and grid costs by 23%
• Heat pump COP varies between 2.8-4.5 depending on operating conditions
• System achieves 72% CO2 reduction compared to fossil baseline scenario
```

**Usage:** Copy-paste into online submission form

### 3. Publication-Quality Figures

**Directory:** `exports/publication_plots/`

All figures in multiple formats (PDF, PNG) at 600 DPI:

| Figure | Filename | Description | Typical Use |
|--------|----------|-------------|-------------|
| Fig. 1 | `heat_balance_publication.pdf` | Heat supply/demand | Results: System operation |
| Fig. 2 | `electric_balance_publication.pdf` | Grid interaction | Results: Grid coupling |
| Fig. 3 | `storage_operation_publication.pdf` | Storage SOC & power | Results: Storage utilization |
| Fig. 4 | `cop_analysis_publication.pdf` | Heat pump efficiency | Results: Technology performance |
| Fig. 5 | `load_duration_curve_publication.pdf` | Load characteristics | Methods: System sizing |
| Fig. 6 | `cost_breakdown_publication.pdf` | Cost components | Results: Economics |
| Fig. 7 | `capex_opex_publication.pdf` | Investment vs operation | Results: Cost structure |
| Fig. 8 | `technology_comparison_publication.pdf` | Technology mix | Results: Optimal portfolio |
| Fig. 9 | `emissions_publication.pdf` | CO₂ emissions | Results: Environmental impact |
| Fig. 10 | `monthly_demand_publication.pdf` | Seasonal patterns | Results/Discussion |

**LaTeX Integration:**
```latex
\begin{figure}[htbp]
\centering
\includegraphics[width=\textwidth]{figures/heat_balance_publication.pdf}
\caption{Hourly heat supply and demand balance for the optimized district
heating system. Heat pumps provide base load, thermal storage provides
flexibility, and backup generators cover peak demands.}
\label{fig:heat_balance}
\end{figure}
```

### 4. LaTeX Tables

**Directory:** `exports/publication_latex/`

Three ready-to-use LaTeX tables:

#### Table 1: KPI Summary (`kpi_summary.tex`)

Key performance indicators:
- Total system cost [EUR]
- Energy cost [EUR]
- Investment cost [EUR]
- CO₂ emissions [t/a]
- Grid import [MWh/a]
- Peak demand [MW]

**LaTeX Integration:**
```latex
\input{tables/kpi_summary.tex}
```

#### Table 2: Cost Breakdown (`cost_breakdown.tex`)

Detailed cost breakdown:
- Electricity cost
- Fuel cost
- Investment cost (CAPEX)
- Installation cost
- O&M cost
- CO₂ cost
- Demand charges

**Shows:** Absolute values [EUR] and percentage share [%]

#### Table 3: Design Decisions (`design_decisions.tex`)

Optimal system design:
- Heat Pump 1-4 capacities [MW]
- Thermal storage capacity [MWh]
- Thermal storage power [MW]
- Build decisions (Yes/No)

### 5. Nomenclature

**File:** `nomenclature.tex`

Complete symbol table for your paper:
- Greek symbols (η, Δt, etc.)
- Latin uppercase (C, COP, E, P, Q, T)
- Latin lowercase (t, x)
- Subscripts (el, th, HP, TES, max, min)
- Abbreviations (CAPEX, COP, MILP, OPEX, TES)

**LaTeX Integration:**
```latex
% After abstract, before introduction
\input{nomenclature.tex}
```

### 6. Manuscript Template

**File:** `manuscript_template.tex`

Complete LaTeX manuscript using `elsarticle` document class (Elsevier's official template):

**Includes:**
- Proper journal formatting
- Line numbers (required for review)
- Author/affiliation blocks
- Abstract structure
- Highlights section
- Keywords
- All standard sections (Intro, Methods, Results, Discussion, Conclusions)
- Bibliography setup
- Appendix for supplementary material

**Usage:** Fill in your content, compile with `pdflatex`

### 7. Submission Checklist

**File:** `SUBMISSION_CHECKLIST.md`

Interactive checklist covering:
- Required files
- Manuscript formatting
- Figure quality
- Table quality
- Content requirements
- Supplementary material
- Pre-submission checks

---

## Step-by-Step Workflow

### Phase 1: Run Analysis

1. **Configure for Applied Energy:**
   ```yaml
   # configs/applied_energies_config.yaml already configured
   export:
     enable_publication_exports: true
     publication_dpi: 600
     publication_formats: [pdf, png]

   applied_energies:
     generate_graphical_abstract: true
     generate_highlights: true
     generate_nomenclature: true
   ```

2. **Run optimization:**
   ```bash
   python examples/standalone_heat_planning_example.py \
     --config configs/applied_energies_config.yaml
   ```

3. **Verify outputs:**
   ```bash
   ls exports/applied_energies/
   ls exports/publication_plots/
   ls exports/publication_latex/
   ```

### Phase 2: Prepare Manuscript

4. **Start from template:**
   ```bash
   cd exports/applied_energies/
   cp manuscript_template.tex my_paper.tex
   ```

5. **Edit metadata:**
   - Update title
   - Add authors and affiliations
   - Update abstract
   - Copy highlights from `highlights.txt`
   - Verify keywords

6. **Insert figures:**
   ```latex
   % Copy figures to your latex working directory
   % In my_paper.tex:
   \includegraphics[width=\textwidth]{../publication_plots/heat_balance_publication.pdf}
   ```

7. **Insert tables:**
   ```latex
   \input{../publication_latex/kpi_summary.tex}
   \input{../publication_latex/cost_breakdown.tex}
   \input{../publication_latex/design_decisions.tex}
   ```

8. **Add nomenclature:**
   ```latex
   % After abstract
   \input{nomenclature.tex}
   ```

9. **Write content:**
   - Introduction: Motivation, gap, contribution
   - Methods: System description, model formulation, optimization
   - Results: Present figures and tables
   - Discussion: Interpret results, compare to literature
   - Conclusions: Summarize findings, implications, future work

### Phase 3: Prepare Submission Package

10. **Compile manuscript:**
    ```bash
    pdflatex my_paper.tex
    bibtex my_paper
    pdflatex my_paper.tex
    pdflatex my_paper.tex
    ```

11. **Organize submission files:**
    ```
    submission_package/
    ├── my_paper.pdf              # Main manuscript
    ├── my_paper.tex              # LaTeX source (optional)
    ├── figures/                  # All figures
    │   ├── Fig1.pdf
    │   ├── Fig2.pdf
    │   └── ...
    ├── graphical_abstract.pdf    # Required
    ├── highlights.txt            # Required
    ├── cover_letter.pdf          # You write this
    ├── supplementary.pdf         # Time series, parameters
    └── references.bib            # Your bibliography
    ```

12. **Prepare supplementary material:**
    - Full time series data → `exports/kpi_summary.csv`
    - Model parameters → `exports/merged_config.json`
    - Additional figures → `exports/publication_plots/` (extras)

### Phase 4: Submit

13. **Go to submission portal:**
    https://www.editorialmanager.com/apen/

14. **Upload files in this order:**
    - Cover letter (PDF)
    - Manuscript (PDF, with line numbers)
    - Figures (separate PDFs, named Fig1, Fig2, etc.)
    - Tables (if separate from manuscript)
    - Graphical abstract (PDF/PNG)
    - Supplementary material (PDF or ZIP)

15. **Fill in online forms:**
    - Copy highlights from `highlights.txt`
    - Paste keywords
    - Add author details
    - Suggest reviewers (optional, 3-5 experts)

16. **Review and submit!**

---

## Manuscript Preparation

### Recommended Structure

#### 1. Title
Clear, descriptive, includes key concepts (e.g., "optimization", "district heating", "heat pumps")

**Example:**
> Multi-Objective Optimization of District Heating Systems with Heat Pumps and Thermal Energy Storage: A Novel Planning Framework

#### 2. Abstract (max 150 words)

**Structure:**
- **Background:** (1-2 sentences) Problem and motivation
- **Methods:** (1-2 sentences) Your approach
- **Results:** (2-3 sentences) Key quantitative findings
- **Conclusions:** (1-2 sentences) Main implications

**Example:**
> **Background:** District heating systems face challenges in decarbonization while maintaining economic viability.
> **Methods:** This paper presents a novel planning framework combining mixed-integer linear programming for capacity optimization with rolling horizon scheduling for operational dispatch.
> **Results:** Applied to a municipal case study, the framework identifies optimal heat pump capacities (42.5 MW total) and thermal storage sizing (15.2 MWh) that reduce total system costs by 18% and CO₂ emissions by 72% compared to a fossil baseline. Heat pump COP ranges from 2.8-4.5 depending on operating conditions.
> **Conclusions:** The integrated approach demonstrates technical and economic feasibility of heat pump-based district heating with significant decarbonization potential.

#### 3. Highlights (3-5 bullet points, max 85 chars each)

**Template:**
- Novel contribution: "Novel [method] for [problem]"
- Methodology: "[Approach] combines [technique A] and [technique B]"
- Quantitative result: "[Component] reduces [metric] by X% [context]"
- Performance: "[Technology] achieves [performance metric] under [conditions]"
- Impact: "System achieves [outcome] compared to [baseline]"

#### 4. Keywords (6-8)

**Mix of:**
- General: District heating, Energy systems, Optimization
- Specific: Heat pumps, Thermal energy storage, Rolling horizon
- Methodological: Mixed-integer programming, Multi-objective
- Application: Decarbonization, Renewable integration

#### 5. Nomenclature

Use `nomenclature.tex` - organize as:
- Greek symbols
- Latin uppercase
- Latin lowercase
- Subscripts
- Superscripts
- Abbreviations

#### 6. Introduction

**Structure:**
- Context: District heating and decarbonization challenge
- Literature review: Previous optimization approaches
- Gap: Limitations of existing methods
- Contribution: What your work adds (3-4 specific points)
- Paper organization: Brief outline

**Length:** 3-4 pages

#### 7. Methodology

**Subsections:**
- 2.1 System Description
  - Components (heat pumps, storage, generators, grid)
  - Operating modes
  - Reference `Fig1_system_schematic` (draw this manually)

- 2.2 Mathematical Model
  - Decision variables
  - Objective function
  - Constraints (energy balance, capacity, ramping, etc.)
  - Use equations, reference nomenclature

- 2.3 Optimization Approach
  - Planning Framework (PF) stage
  - Rolling Horizon (RH) stage
  - Solver settings (reference config)

- 2.4 Case Study Data
  - Heat demand profile → reference `load_duration_curve_publication.pdf`
  - Technology parameters → Table in supplementary
  - Economic parameters → Table or in text

**Length:** 5-7 pages

#### 8. Results

**Subsections:**
- 3.1 Optimal System Design
  - Capacity decisions → `design_decisions.tex` (Table)
  - Technology selection rationale → `technology_comparison_publication.pdf` (Figure)

- 3.2 System Operation
  - Typical day/week operation → `heat_balance_publication.pdf` (Figure)
  - Grid interaction → `electric_balance_publication.pdf` (Figure)
  - Storage utilization → `storage_operation_publication.pdf` (Figure)

- 3.3 Economic Analysis
  - Total costs → `cost_breakdown_publication.pdf` (Figure)
  - CAPEX vs OPEX → `capex_opex_publication.pdf` (Figure)
  - Cost breakdown → `cost_breakdown.tex` (Table)

- 3.4 Environmental Performance
  - CO₂ emissions → `emissions_publication.pdf` (Figure)
  - Comparison to baseline

- 3.5 Sensitivity Analysis (if performed)
  - CO₂ price sensitivity
  - Electricity price sensitivity

**Length:** 6-8 pages

#### 9. Discussion

**Topics:**
- Interpret key findings
- Compare to literature (quantitative when possible)
- Explain unexpected results
- Discuss limitations
- Practical implications
- Policy recommendations

**Length:** 3-4 pages

#### 10. Conclusions

**Structure:**
- Main findings (3-4 bullet points)
- Contributions to knowledge
- Practical implications
- Limitations
- Future research directions

**Length:** 1-2 pages

#### 11. Acknowledgments

- Funding sources
- Data providers
- Computational resources
- Helpful discussions

#### 12. References

- Use numbered citation style (elsarticle-num)
- Minimum 30-40 references for Applied Energy
- Mix of classics and recent (last 5 years)
- Include methodology papers, case studies, policy documents

#### 13. Appendix / Supplementary Material

**Include:**
- Complete parameter tables
- Full time series data (CSV)
- Additional validation results
- Extended sensitivity analysis
- Model equations (if too long for main text)

---

## Submission Checklist

Use `SUBMISSION_CHECKLIST.md` for complete checklist. Key items:

### Required Files
- [ ] Main manuscript PDF (with line numbers)
- [ ] Graphical abstract (`graphical_abstract.pdf`)
- [ ] Highlights (copy from `highlights.txt`)
- [ ] All figures (separate files: Fig1.pdf, Fig2.pdf, ...)
- [ ] Cover letter
- [ ] Suggested reviewers (optional)
- [ ] Supplementary material (if applicable)

### Figure Quality
- [ ] All figures minimum 300 DPI (ours are 600 DPI ✅)
- [ ] Vector formats used (PDF) ✅
- [ ] Font size readable after scaling ✅
- [ ] Color figures work in grayscale ✅
- [ ] All axes labeled with units ✅
- [ ] Figure captions self-explanatory
- [ ] Files named Fig1.pdf, Fig2.pdf, etc.

### Table Quality
- [ ] Horizontal lines only (no vertical) ✅
- [ ] Units clearly specified ✅
- [ ] Decimal alignment appropriate ✅
- [ ] Table captions above tables

### Manuscript Format
- [ ] Line numbers enabled ✅ (in template)
- [ ] Page numbers enabled ✅
- [ ] Abstract ≤150 words
- [ ] Highlights: 3-5 bullet points, ≤85 chars each ✅
- [ ] Keywords: 6-8 keywords
- [ ] Nomenclature section included ✅
- [ ] All figures cited in text
- [ ] All tables cited in text
- [ ] References formatted correctly
- [ ] SI units throughout

### Content
- [ ] Data availability statement
- [ ] Funding acknowledgment
- [ ] Conflict of interest statement
- [ ] Author contributions (CRediT)
- [ ] Ethics approval (if applicable)

---

## FAQs

### Q: How do I enable Applied Energies exports?

**A:** Use the provided config:
```bash
python your_script.py --config configs/applied_energies_config.yaml
```

Or add to your existing config:
```yaml
export:
  enable_publication_exports: true

applied_energies:
  generate_graphical_abstract: true
  generate_highlights: true
  generate_nomenclature: true
```

### Q: Can I customize the graphical abstract?

**A:** Yes! The generated abstract is a starting point. You can:
1. Edit the code in `energis/io/applied_energies_exporter.py`
2. Or create your own using the generated one as reference
3. Or use graphics software (Inkscape, Adobe Illustrator)

Most authors customize the graphical abstract to match their specific system.

### Q: What if I don't use LaTeX?

**A:** You can still use all outputs:
- Figures: Insert PDFs/PNGs into Word
- Tables: Export data to Excel, format manually
- Highlights: Copy from `highlights.txt`
- Graphical abstract: Use the PNG version
- Nomenclature: Create table in Word

But LaTeX is **strongly recommended** for Applied Energy (better formatting, easier revisions).

### Q: How many figures should I include?

**A:** Applied Energy typically allows 8-12 figures. We generate 10 standard plots. Choose the most relevant ones:

**Essential (6-7 figures):**
- Heat balance
- Cost breakdown
- Technology comparison
- Load duration curve
- At least one economic figure (CAPEX/OPEX)
- At least one performance figure (COP or emissions)

**Optional (3-4 more):**
- Electric balance
- Storage operation
- Monthly aggregation
- Sensitivity analysis

### Q: Should I include all tables?

**A:** Use judgment:
- **KPI summary**: Excellent for Introduction or Results
- **Cost breakdown**: Good for Results or Discussion
- **Design decisions**: Essential for Results

Consider moving detailed parameter tables to supplementary material.

### Q: What goes in supplementary material?

**A:**
- Complete time series data (`kpi_summary.csv`)
- All model parameters (`merged_config.json`)
- Extended sensitivity analysis
- Additional figures not in main text
- Validation data
- Additional case studies

Keep supplementary focused and organized!

### Q: How do I cite the framework in my paper?

**A:** In Methods section:
> "The optimization was performed using an open-source heat planning framework [YOUR_REFERENCE] implemented in Python with Pyomo [PYOMO_REFERENCE] and solved using [SOLVER_NAME]."

Add repository URL in Data Availability statement.

### Q: What if reviewers request changes to figures?

**A:** Easy! Just:
1. Modify your config (colors, layout, etc.)
2. Re-run the export
3. Get updated figures in minutes

This is a huge advantage of automated figure generation!

### Q: Can I use different colors?

**A:** Yes, edit `publication_plotter.py`:
```python
class PublicationConfig:
    COLORS_QUALITATIVE = ['#yourcolor1', '#yourcolor2', ...]
```

Our defaults are colorblind-friendly and grayscale-compatible, which reviewers appreciate.

### Q: How long does review typically take at Applied Energy?

**A:** Typical timeline:
- Editor assignment: 1-2 weeks
- First decision: 6-12 weeks
- Revision submission: Your timeline
- Final decision: 4-8 weeks

Total: 4-6 months for accepted papers

### Q: What's the acceptance rate?

**A:** Applied Energy: ~20-25% acceptance rate (selective, high quality)

### Q: Should I suggest reviewers?

**A:** Yes! Suggest 3-5 experts who:
- Work in energy systems optimization
- Have published on heat pumps, district heating, or related topics
- Are NOT your collaborators
- Are from different institutions
- Have recent publications (last 5 years)

Check their Applied Energy publications for relevance.

---

## Additional Resources

### Elsevier Resources
- Author guidelines: https://www.elsevier.com/journals/applied-energy/0306-2619/guide-for-authors
- Submission portal: https://www.editorialmanager.com/apen/
- LaTeX templates: https://www.elsevier.com/authors/policies-and-guidelines/latex-instructions
- Figure guidelines: https://www.elsevier.com/authors/tools-and-resources/visual-abstract

### Paper Writing
- "How to Write a Great Research Paper" (Microsoft Research)
- "The Science of Scientific Writing" (Gopen & Swan)
- "Ten Simple Rules for Writing Research Papers" (PLOS Computational Biology)

### LaTeX Help
- Overleaf Applied Energy template: https://www.overleaf.com/latex/templates/tagged/applied-energy
- elsarticle documentation: https://www.elsevier.com/__data/assets/pdf_file/0007/56842/elsdoc-1.pdf

---

## Support

For framework-specific questions:
- Check documentation: `docs/PUBLICATION_EXPORTS.md`
- Review examples: `examples/standalone_heat_planning_example.py`
- Open GitHub issue: [repository]/issues

For journal-specific questions:
- Contact Applied Energy editorial office
- Check author guidelines
- Ask your colleagues who published there

---

## Good Luck with Your Submission! 🚀

Remember:
- Start early (preparation takes time)
- Follow guidelines exactly (journals are strict)
- Get feedback from colleagues before submission
- Write clearly (clear writing = clear thinking)
- Be thorough but concise
- Highlight your novelty and contributions
- Show quantitative results
- Compare to literature
- Discuss limitations honestly

**Your optimization results deserve to be published!**
