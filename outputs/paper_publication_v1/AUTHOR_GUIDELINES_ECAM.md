# Author Guidelines: Energy Conversion & Management (ECaM)

**Journal**: Energy Conversion & Management  
**Impact Factor**: 7.2–8.5 (top-tier energy journal)  
**Publisher**: Elsevier  
**Website**: https://www.journals.elsevier.com/energy-conversion-and-management

---

## SUBMISSION REQUIREMENTS

### Scope & Acceptance Criteria

**Suitable topics**:
- ✅ Energy systems optimization
- ✅ MILP/optimization methodologies
- ✅ Thermal network modeling
- ✅ District heating/cooling systems
- ✅ Computational efficiency improvements
- ✅ Real-world applications with reproducible results

**NOT suitable**:
- ❌ Pure theoretical work without real applications
- ❌ Incremental improvements without novelty
- ❌ Unreproducible results or missing data
- ❌ Patents or proprietary algorithms

---

## MANUSCRIPT FORMATTING

### Structure & Sections

**Required structure** (in this order):

| Section | Max Length | Status |
|---------|-----------|--------|
| **Title** | 15 words max | ✅ Complete |
| **Abstract** | 150–250 words | ✅ Include |
| **Keywords** | 4–6 terms | ✅ Add before submit |
| **1. Introduction** | 1,500–2,000 words | ✅ Section 1-3 |
| **2. Literature Review** | 1,500–2,000 words | ✅ Section 1-3 |
| **3. Methodology** | 5,000–7,000 words | ✅ Section 1-3 |
| **4. Case Study** | 1,000–1,500 words | ✅ Section 4-7 |
| **5. Results** | 1,500–2,000 words | ✅ Section 4-7 |
| **6. Discussion** | 1,000–1,500 words | ✅ Section 4-7 |
| **7. Conclusion** | 300–500 words | ✅ Section 4-7 |
| **Appendix** | Unlimited | ✅ Include (proofs) |
| **References** | 30–60 items | ✅ 25+ provided |
| **Total** | 8,000–18,000 words | ✅ 17,700 words |

### Title

**Current title** (15 words):
> *Network Topology Abstraction Impact on Operational Dispatch Optimization: A Piecewise-Linear Thermo-Hydraulic MILP Approach*

✅ **Acceptable** — Clear, specific, contains keywords

**Alternative shorter titles** (if space-constrained):
- "Topology Abstraction in Heat System Optimization: MILP Framework"
- "Network Simplification Effects on District Heat Dispatch Optimization"

### Abstract

**Required structure** (150–250 words):
1. Problem statement (2–3 sentences)
2. Proposed solution (2–3 sentences)
3. Key results (3–4 sentences)
4. Implications (1–2 sentences)

**Template to use**:
> [Problem]: District heat system designers face a fundamental trade-off between model detail and computational tractability.
> [Solution]: We developed three MILP models of increasing complexity to systematically assess how topology abstraction affects optimal dispatch.
> [Results]: Results show that simplified 5-node models capture $\geq 95\%$ of physical realism with 2–3× faster computation.
> [Impact]: Framework enables practitioners to confidently select model abstraction based on accuracy/speed trade-offs.

**Keywords** (4–6 terms):
- Mixed-Integer Linear Programming
- District heating optimization
- Network topology abstraction
- Thermo-hydraulic modeling
- Operational dispatch optimization
- Energy system design

### Headings & Subsections

**Heading hierarchy** (use markdown or LaTeX format):

```
# 1. Introduction              (Level 1 — single #)
## 1.1 Problem Statement       (Level 2 — double ##)
### 1.1.1 Background           (Level 3 — triple ### — avoid if possible)

# 2. Literature Review
## 2.1 MILP Applications in Energy
## 2.2 Network Simplification Methods
...
```

✅ **Your paper structure** is compliant.

---

## TEXT FORMATTING

### Font & Spacing

- **Font**: Times New Roman (non-monospace), 12pt body text
- **Line spacing**: Double-spaced (1.5 minimum)
- **Margins**: 2.54 cm (1 inch) all sides
- **Page format**: A4 (210 × 297 mm)
- **File format**: DOCX or PDF preferred; Markdown acceptable if converted to DOCX

### Text Standards

**Language**:
- English (either US or British; be consistent)
- Spell-check before submission
- Grammar check recommended (Grammarly, etc.)

**Abbreviations**:
- Define on first use: "Mixed-Integer Linear Programming (MILP)"
- Common abbreviations acceptable after first use: MILP, MWh, EUR, etc.
- Avoid abbreviations in title/abstract if possible

**Units**:
- Use SI units: MWh, EUR, °C, seconds, etc.
- Non-SI acceptable if clearly justified: MWth (thermal megawatts)
- Consistent throughout

### Mathematical Content

#### Equations

**Formatting standard**:

Displayed equation (centered, numbered):
$$\min_{x,y} \sum_{t=1}^{T} C_t(x_t, y_t)$$

Inline equation: $\mathbf{A}x = \mathbf{b}$

**Numbering**:
- Number important equations
- Example: Equations (1)–(34) for 34 numbered equations
- Reference as "Eq. (5)" or "Equation (5)"

**LaTeX/MathJax support**:
- ECaM uses MathJax/LaTeX rendering
- Use standard LaTeX syntax: `$$...$$` for display, `$...$` for inline
- Avoid Word equation editor if possible (use LaTeX instead)

#### Variables & Notation

**Standard conventions**:
- Decision variables: lowercase bold ($\mathbf{x}$, $\mathbf{y}$)
- Parameters: lowercase or Greek ($c_t, \alpha, \beta$)
- Sets/indices: uppercase or calligraphic ($\mathcal{T}$, $S$)
- Scalars: regular (non-bold)
- Vectors: bold ($\mathbf{v}$)
- Matrices: uppercase bold ($\mathbf{A}$, $\mathbf{M}$)

**Your convention** (consistent throughout):
- ✅ Dispatch variables: $p_t$, $q_t$, $\phi_t$
- ✅ Parameters: $c_{grid}$, $\eta_{HP}$
- ✅ Sets: $\mathcal{T}$ (time), $\mathcal{N}$ (nodes)

### Figure & Table Guidelines

#### Figures

**Resolution**:
- Minimum: 300 DPI for print publication
- Preferred: 600 DPI for top-tier journals
- Format: PDF (vector), PNG (raster), SVG (editable vector)
- ✅ **Your figures**: 300+ DPI, all three formats provided

**Figure Captions** (below figure):

Format:
> **Figure 2.** Comparison of heat dispatch patterns across three model abstractions (L1: copperplate, L2: 5-node simplified, L3: full 30-node network) for the coldest week in winter (Jan 15–22, 2023). Stacked area chart shows contribution of boiler (blue), CHP (orange), heat pump (green), and grid import (red) to meet demand. Week selected to highlight differences under high-load conditions. Data from annual MILP optimization with HiGHS solver.

**Caption requirements**:
- ✅ Sufficient detail to explain figure without main text
- ✅ Indicate data source
- ✅ Explain any abbreviations
- ✅ Relevant time period / conditions

#### Tables

**Format**: Simple, professional, publication-ready

**Table Captions** (above table):

> **Table 1.** Annual system cost breakdown for three model abstraction levels. Costs shown in EUR million, with percentage change vs. L1 copperplate baseline. Grid electricity cost based on €35/MWh; natural gas €45/MWh; CO₂ emissions €100/t. Network losses included in L2/L3 costs.

**Requirements**:
- ✅ Descriptive title above table
- ✅ Units clearly indicated (EUR, MWh, h, %, etc.)
- ✅ Notes section below if needed: "*Note: Values rounded to nearest 0.01 EUR million. HP = heat pump; CHP = combined heat & power.*"
- ✅ Clear column headers
- ✅ Reasonable number of rows (10–30 preferred; avoid 100-row tables in main text)

**Table conversion**:
- Excel/CSV → QTable Word format
- All values aligned consistently
- No alternating row colors in ECaM format (discouraged for print)

---

## REFERENCES & CITATIONS

### Citation Style: Numbered System

ECaM uses **numbered citations** (like IEEE, not Harvard).

**Format**:
- In text: `[1]`, `[2]`, `[1–3]`, `[5, 7, 9]`
- Reference list: numbered 1, 2, 3, ... in order of appearance

**Example text**:
> MILP methods have been successfully applied to energy system optimization[1–3]. Recent work by Smith et al.[4] demonstrated the effectiveness of network aggregation for reducing computational burden, though topology abstraction introduces approximation errors[5].

**Reference list format**:

```
[1] Author A, Author B. Title of journal article. Journal Name. 2020; 45(3): 123–134.

[2] Author C. Title of Book. 2nd ed. Publisher; 2019.

[3] Organization Name. Title of Report. Report No. NR/2021/042; 2021.

[4] Author D, et al. Title. Conf. Proc. Energy Conf. 2021. IEEE; 2021. p. 456–461.
```

### Your References

**Current status**: 25+ reference citations in manuscript + Appendix

**Action items**:
1. ✅ Verify all [1]–[50] references are properly cited in Sections 1–3
2. ✅ Verify all [51]–[65] references are properly cited in Sections 4–7
3. ✅ Check no orphaned references (cited but not listed)
4. Ensure consistent formatting:
   - Author initials only (not full names)
   - Year in parentheses: (2020) ✓ or 2020? ✓
   - Journal title: full name (not abbreviation)
   -Capitalization: sentence case for article titles (only first word capitalized)

**Example correct entries**:

```
[12] Smith AB, Johnson CD, Brown EF. Optimization of district heating systems using mixed-integer linear programming. Energy Convers Manag. 2021; 239: 114265.

[18] ISO/IEC. ISO/IEC 10149:2019 Energy management systems. 2019.

[22] NREL. HOMER Pro software documentation. https://www.nrel.gov/homer/; Accessed Apr 7, 2026.
```

---

## SUBMISSION PROCESS

### Before Submitting

**Checklist**:
- [ ] Manuscript: 8,000–18,000 words (target 17,700) ✅
- [ ] Figures: All 4 figures, 300+ DPI, captions complete ✅
- [ ] Tables: All 3 tables with captions and notes ✅
- [ ] References: All 25+ citations formatted correctly
- [ ] Abstract: 150–250 words, keywords listed
- [ ] Language: Grammar, spelling, units consistent
- [ ] Ethics: No human subjects/animals (not required for optimization studies)
- [ ] Data: Available statement included ✅
- [ ] Conflict of Interest: Declared (or none stated)
- [ ] Cover Letter: Addressed to Editor ✅

### Submission Platform

**ECaM uses**: Editorial Manager (EM)  
**Website**: https://www.editorialmanager.com/ecam/

**Registration & submission**:
1. Create Editorial Manager account
2. "New Submission" → Select article type (Research Article)
3. Upload main manuscript (DOCX or PDF)
4. Upload figures separately (PDF/PNG for each)
5. List authors + corresponding author contact
6. Select keywords (4–6 terms)
7. Enter funding information (if applicable)
8. Leave reviewer suggestions (optional, 2–4 suggested reviewers)
9. Submit

### What to Upload

| File | Format | Name |
|------|--------|------|
| Main manuscript | DOCX, PDF | `Author_etal_2026_CALION_MILP.docx` |
| Figure 2 | PDF | `Figure2_dispatch_comparison.pdf` |
| Figure 3 | PDF | `Figure3_cost_comparison.pdf` |
| Figure 4 | PDF | `Figure4_pipe_losses.pdf` |
| Figure 8 | PDF | `Figure8_storage_soc.pdf` |
| Supplementary: Tables CSV | ZIP | `Tables_supplementary.zip` |
| Supplementary: Data Availability | DOCX/PDF | `DATA_AVAILABILITY_STATEMENT.pdf` |
| Supplementary: Appendix | DOCX/PDF | `APPENDIX_EQUATIONS_PROOFS.pdf` |

---

## POST-SUBMISSION

### Review Timeline

**Typical ECaM review process**:
- **Initial desk review**: 1–2 weeks (editors check scope/quality)
- **Reviewer assignment**: 2–3 weeks
- **Peer review**: 4–8 weeks (2–3 reviewers)
- **Decision notification**: 2–4 weeks after review
- **Total**: 2–4 months from submission to decision

**Possible outcomes**:
1. **Accept** — Published (rare, ~5% of submissions)
2. **Major Revisions** — Most common (~60%); resubmit with detailed response letter
3. **Minor Revisions** — Good sign (~25%); address reviewer comments
4. **Reject** — Lower-tier work (~10%); consider backup journals

### After Acceptance

- Proofs provided for final check (1–2 days to review)
- Article published online (3–5 days after proofs approved)
- Issue assignment — appears in issue with DOI
- Article processing charge (APC): ~€3,000–5,000 (depending on funding)

---

## JOURNAL ALTERNATIVES

If ECaM rejects, **backup submission targets**:

| Journal | Impact Factor | Word Limit | Focus | Fit |
|---------|---|---|---|---|
| **Applied Energy** | ~11 (higher) | 6,000–15,000 | Renewable energy, optimization | Very good |
| **International Journal of Energy Research** | ~4.5 | 6,000–10,000 | Energy systems | Good |
| **Energies** (MDPI, open-access) | ~3.2 | No strict limit | Broad energy topics | Good |
| **Journal of Energy Storage** | ~6–7 | 6,000–12,000 | Storage + optimization | Good |

---

## FINAL CHECKLIST BEFORE SUBMISSION

```
✅ = Ready for submission
⚠️  = Needs attention
❌ = Not included

Manuscript Preparation:
✅ Manuscript: 17,700 words (Sections 1–3 + Sections 4–7 + Appendix)
✅ Abstract: 150–250 words, keywords listed
✅ Title: 15 words, clear and specific
✅ Headings: Proper hierarchy (#, ##, ###)
✅ Figures: 4 figures, 300+ DPI, with full captions
✅ Tables: 3 tables, with captions and notes
✅ Equations: 34 numbered, proper LaTeX formatting
✅ References: 25+ citations, proper ECaM format

Content Quality:
✅ Introduction: Problem well-motivated, knowledge gaps clear
✅ Literature Review: 25+ recent sources, positioning clear
✅ Methodology: All three models (L1/L2/L3) fully described
✅ Case Study: Network details, data sources, solver settings
✅ Results: Tables + figures integrated, results explained
✅ Discussion: Findings contextualized, limitations noted
✅ Conclusion: Summary + future work directions

Reproducibility:
✅ Data Availability Statement: Complete details provided
✅ Solver: HiGHS open-source, settings documented
✅ Code: Scripts available (GitHub or supplementary)
✅ All inputs: YAML configs, CSV data, initial conditions

Formatting:
✅ Units: SI units throughout (MWh, EUR, °C)
✅ Abbreviations: Defined on first use
✅ Spell-check: English grammar correct
✅ Style: Consistent font, spacing, formatting
✅ Figures/Tables: Professional quality, no overlapping text

Administrative:
⚠️  Cover Letter: Template provided, customize with author details
✅ Data Availability: Included in package
❌ Suggested Reviewers: Add 2–4 names (optional)
❌ Funding Statement: Fill in funding sources/grant numbers
❌ Ethics Approval: Not required (optimization study)
❌ Conflict of Interest: Declare or state "None"
```

---

## CONTACT JOURNAL EDITORS

**Energy Conversion & Management**

**Editor-in-Chief**: [Current Editor Name]  
**Email**: editors@energy.elsevier.com  
**Managing Editor**: EJmanager@elsevier.com  
**Journal Home**: https://www.journals.elsevier.com/energy-conversion-and-management

**For questions during preparation**:
- Scope fit: Contact editor informally before submission
- Technical issues: EJmanager@elsevier.com
- After submission: Check Editorial Manager system for notifications

---

**Document prepared**: April 7, 2026  
**Status**: Ready for manuscript formatting & submission
