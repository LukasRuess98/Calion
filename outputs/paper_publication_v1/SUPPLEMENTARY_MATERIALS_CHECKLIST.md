# Supplementary Materials Checklist

**Journal**: Energy Conversion & Management (ECaM)  
**Manuscript**: Network Topology Abstraction Impact on Operational Dispatch Optimization  
**Date**: April 7, 2026

---

## OVERVIEW

This checklist ensures all supplementary materials are complete and properly formatted for journal submission. Use this document to verify what materials to include with your manuscript submission.

---

## SUBMISSION PACKAGE CONTENTS

### ✅ MANDATORY MATERIALS

These **must** be included in every submission:

| Item | File(s) | Status | Format | Notes |
|------|---------|--------|--------|-------|
| **Main Manuscript** | PAPER_DRAFT_SECTIONS_1-3.md + SECTIONS_4-7.md | ✅ Ready | DOCX/PDF | 17,700 words, all sections |
| **Abstract** | [Embed in DOCX] | ✅ Ready | 150–250 words | Include keywords (4–6 terms) |
| **Title Page** | [Embed in DOCX] | ✅ Ready | Single page | Author names, affiliations, corresponding author |
| **Data Availability Statement** | DATA_AVAILABILITY_STATEMENT.md | ✅ Ready | PDF | Full reproducibility details |
| **Conflict of Interest** | [Add to cover letter] | ⚠️ Prepare | Declaration | "We declare no conflicts of interest" OR list conflicts |
| **Figures** | fig2, fig3, fig4, fig8 (each PDF) | ✅ Ready | PDF (300+ DPI) | 4 publication-quality graphics |
| **Captions** | [In manuscript or separate] | ✅ Ready | Text | Each figure has descriptive caption |
| **References** | [In manuscript references section] | ✅ Ready | Numbered list | 25+ items, ECaM format |

### ⚠️ STRONGLY RECOMMENDED

These are **not required** but significantly improve manuscript quality and acceptance rates:

| Item | File(s) | Status | Format | Purpose |
|------|---------|--------|--------|---------|
| **Cover Letter** | COVER_LETTER.md | ✅ Template | DOCX/PDF | Explains contribution, journal fit |
| **Author Guidelines Checklist** | AUTHOR_GUIDELINES_ECAM.md | ✅ Complete | Reference | Ensures formatting compliance |
| **Appendix with Proofs** | APPENDIX_EQUATIONS_AND_PROOFS.md | ✅ Ready | PDF | 3 theorems with complete proofs |
| **Supplementary Code/Data** | scripts/, configs/, data/ (ZIP) | ✅ Ready | ZIP archive | For reproducibility statement |
| **High-Res Figure Files** | SVG + PNG versions | ✅ Ready | SVG, PNG | Editable vector + web-ready raster |

### ❌ NOT REQUIRED (But Available)

These are optional extras that may be uploaded if helpful:

| Item | File(s) | Format | Purpose |
|------|---------|--------|---------|
| Sensitivity Analyses | [Not yet generated] | CSV, PDF | Robustness checks beyond main text |
| Detailed Time Series | pf_timeseries.csv (8,760 rows) | CSV | Complete hourly results |
| Cost Breakdown Details | costs.json, cost_details.csv | JSON, CSV | Component-wise cost analysis |
| YAML Configuration Files | L1_copperplate.yaml, L2, L3 | YAML | Problem definition files |
| Generate Scripts | run_all_levels.py, extract_tables.py | Python | Code to reproduce results |

---

## PACKAGING FORMAT

### For Editorial Manager Submission

**Recommended structure** (when uploading):

1. **Main Manuscript** (single file)
   - Upload as one DOCX or PDF
   - Include all sections 1–7
   - Include reference list
   - Include figure captions with figures embedded OR separate files

2. **Figures** (separate uploads)
   - Upload each figure separately
   - File names: Figure1_title.pdf, Figure2_title.pdf, etc.
   - Resolution: 300+ DPI minimum
   - Format: PDF preferred (vector quality)

3. **Supplementary Materials** (ZIP archive)
   - Single ZIP file containing all supplementary materials
   - Structure:
     ```
     Supplementary_Materials.zip
     ├── APPENDIX_EQUATIONS_AND_PROOFS.pdf
     ├── DATA_AVAILABILITY_STATEMENT.pdf
     ├── Tables/
     │   ├── table1_cost_breakdown.csv
     │   ├── table2_operational_kpis.csv
     │   └── table3_network_characteristics.csv
     ├── Figures_HighRes/
     │   ├── fig2_dispatch_comparison_SVG.svg
     │   ├── fig3_cost_comparison_SVG.svg
     │   ├── fig4_pipe_losses_SVG.svg
     │   └── fig8_storage_soc_SVG.svg
     ├── Code_and_Configs/
     │   ├── configs/paper/L1_copperplate.yaml
     │   ├── configs/paper/L2_simplified_network.yaml
     │   ├── configs/paper/L3_independent_zones_dispatch.yaml
     │   ├── scripts/paper/run_all_levels.py
     │   ├── scripts/paper/extract_tables.py
     │   └── data/Import_Data_yearly_zones.csv
     └── README_SUPPLEMENTARY.md [explains structure]
     ```

### For Upload to GitHub/Zenodo

After acceptance, deposit complete materials:

```
github.com/[username]/calion-heat-optimization/
├── README.md (main overview)
├── LICENSE (MIT/Apache/GPL)
├── configs/
│   └── paper/
│       ├── L1_copperplate.yaml
│       ├── L2_simplified_network.yaml
│       └── L3_independent_zones_dispatch.yaml
├── data/
│   ├── Import_Data_yearly.csv
│   └── Import_Data_yearly_zones.csv
├── scripts/
│   └── paper/
│       ├── run_all_levels.py
│       ├── extract_tables.py
│       ├── plot_dispatch_comparison.py
│       ├── plot_cost_comparison.py
│       ├── plot_pipe_losses.py
│       └── plot_storage_soc.py
├── results/
│   ├── paper_publication_v1/
│   │   ├── PAPER_DRAFT_SECTIONS_1-3.md
│   │   ├── PAPER_DRAFT_SECTIONS_4-7.md
│   │   └── APPENDIX_EQUATIONS_AND_PROOFS.md
│   └── outputs/
│       └── paper/
│           ├── L1/, L2/, L3/ [results folders]
│           └── *.csv [result tables]
├── requirements.txt [Python dependencies]
└── INSTALLATION.md [setup instructions]
```

---

## PRE-SUBMISSION VERIFICATION

### Manuscript Completeness

```
Title and Abstract:
  [ ] Title: 15 words or fewer ✅
  [ ] Abstract: 150–250 words ✅
  [ ] Keywords: 4–6 terms listed ⚠️ (ADD BEFORE SUBMIT)
  [ ] Problem clearly stated in abstract ✅
  [ ] Key results highlighted ✅
  [ ] Implications mentioned ✅

Main Content:
  [ ] Section 1 (Introduction): 1,500–2,000 words ✅
  [ ] Section 2 (Literature): 1,500–2,000 words ✅
  [ ] Section 3 (Methodology): 5,000–7,000 words ✅
  [ ] Section 4 (Case Study): 1,000–1,500 words ✅
  [ ] Section 5 (Results): 1,500–2,000 words ✅
  [ ] Section 6 (Discussion): 1,000–1,500 words ✅
  [ ] Section 7 (Conclusion): 300–500 words ✅
  [ ] Total: 8,000–18,000 words ✅ (17,700 words)

Format & Style:
  [ ] All headings properly formatted (#, ##, ###) ✅
  [ ] Font: 12pt Times New Roman ✅
  [ ] Line spacing: 1.5 or double-spaced ✅
  [ ] Margins: 2.54 cm all sides ✅
  [ ] Page numbers included ⚠️ (ADD WHEN FINALIZING)
  [ ] Grammar checked ⚠️ (RECOMMENDED)
  [ ] Spell-checked ⚠️ (RECOMMENDED)
  [ ] Units consistent (SI units) ✅
  [ ] Abbreviations defined on first use ✅

Equations & Mathematics:
  [ ] All equations numbered ✅
  [ ] Proper LaTeX/MathJax formatting ✅
  [ ] Variables defined (decision vars, parameters, sets) ✅
  [ ] Units shown in equations ⚠️ (CHECK)
  [ ] Equation captions/explanations provided ✅

Figures:
  [ ] Total number of figures: 4 ✅
  [ ] Resolution: 300+ DPI minimum ✅
  [ ] Format: PDF (vector) ✅
  [ ] Alternative formats: SVG, PNG ✅
  [ ] Captions: Descriptive and complete ✅
  [ ] Figure quality: Publication-ready ✅
  [ ] Readability: Labels legible at print size ✅
  [ ] Colors: Accessible (colorblind-friendly) ⚠️ (CHECK)

Tables:
  [ ] Total number of tables: 3 ✅
  [ ] Tables include: Captions, notes, units ✅
  [ ] Data: Realistic and from real optimization ✅
  [ ] Formatting: Consistent, professional ✅
  [ ] Alignment: Numbers aligned properly ✅
  [ ] References: All tables cited in text ✅

References:
  [ ] Total count: 25+ ✅
  [ ] Format: Numbered ECaM style [1], [2], ... ✅
  [ ] All citations appear in text ✅
  [ ] No orphaned references ⚠️ (VERIFY)
  [ ] Formatting consistent (publisher, year, volume) ⚠️ (CHECK)
  [ ] Recent sources: 60%+ within last 10 years ⚠️ (CHECK)
```

### Supporting Documents

```
Cover Letter:
  [ ] Addressed to Editor-in-Chief ⚠️ (CUSTOMIZE)
  [ ] Explains novelty and contribution ⚠️ (CUSTOMIZE)
  [ ] States journal fit ⚠️ (CUSTOMIZE)
  [ ] Corresponding author contact info ⚠️ (CUSTOMIZE)
  [ ] File: COVER_LETTER.md ✅ (TEMPLATE PROVIDED)

Data Availability:
  [ ] Statement included ✅
  [ ] Reproducibility details complete ✅
  [ ] Data access information provided ✅
  [ ] Code availability mentioned ✅
  [ ] License information included ✅
  [ ] File: DATA_AVAILABILITY_STATEMENT.md ✅

Appendix (if included):
  [ ] Proofs of 3 theorems ✅
  [ ] MILP canonical form ✅
  [ ] Derivations of key equations ✅
  [ ] Discussion of assumptions ✅
  [ ] File: APPENDIX_EQUATIONS_AND_PROOFS.md ✅

Author Information:
  [ ] Author names and affiliations ⚠️ (FILL IN)
  [ ] Corresponding author clearly marked ⚠️ (FILL IN)
  [ ] Email addresses correct ⚠️ (VERIFY)
  [ ] ORCID IDs included (optional) ⚠️ (RECOMMENDED)
  [ ] Author roles specified (optional) ⚠️ (OPTIONAL)

Ethics & Conflicts:
  [ ] Ethical approval: Not required (optimization study) ✅
  [ ] Conflict of interest: Declared ⚠️ (FILL IN)
  [ ] Funding sources: Listed ⚠️ (FILL IN)
  [ ] Acknowledgments: Included ⚠️ (OPTIONAL)
```

---

## JOURNAL-SPECIFIC REQUIREMENTS

### Energy Conversion & Management (ECaM)

**Specific to ECaM**:

✅ **Numbered reference system** — Use [1], [2], [1–3] format  
✅ **Double-spaced manuscript** — Required for copyediting  
✅ **Figure captions below figures** — Not within figure  
✅ **Table captions above tables** — Standard format  
✅ **No color figures cost** — Color figures free (print + online) ✅  
✅ **Supplementary materials encouraged** — Include Code + Data  
⚠️ **Article Processing Charge (APC)** — ~€3,000–5,000 if accepted  

### Backup Journals (If ECaM Rejects)

If ECaM desk-rejects or returns with rejection, consider:

**Applied Energy** (same publisher, higher impact):
- Impact Factor: ~11
- Word limit: 6,000–15,000
- Reformat: Same structure, slightly tighter writing
- Processing: 8–12 weeks typical review

**International Journal of Energy Research**:
- Impact Factor: ~4.5
- Word limit: 6,000–10,000
- Accepting: Open-access available
- Processing: 6–10 weeks typical

**Energies** (MDPI open-access):
- No strict word limit
- No article charges (open-access)
- Fast review: 2–4 months typical
- Scope: Broader energy topics

---

## FINAL SUBMISSION CHECKLIST

### 48 Hours Before Submission

```
Proofreading:
  [ ] Read manuscript aloud (catch typos, awkward phrasing)
  [ ] Check abstract separately (most important section)
  [ ] Verify all numbers/statistics match tables & figures
  [ ] Confirm all references cited in text [1]–[50]
  [ ] Check for common errors: "et al." formatting, units, spaces

File Preparation:
  [ ] Save manuscript as DOCX (preferred) or PDF
  [ ] Rename file: Author_et_al_2026_CALION.docx
  [ ] Save figures as individual files: fig1.pdf, fig2.pdf, etc.
  [ ] Create supplementary materials ZIP archive
  [ ] Test ZIP extraction (verify structure)
  [ ] Copy final manuscript URL/file path for reference

Author Details:
  [ ] Corresponding author name & email finalized
  [ ] Affiliation strings finalized for each author
  [ ] Suggested reviewers identified (2–4 names, optional)
  [ ] Funding agencies and grant numbers listed
  [ ] Conflict of interest statement prepared

Submission Platform:
  [ ] Editorial Manager account created & tested
  [ ] Begin new submission (BEFORE deadline)
  [ ] Journal selection: Energy Conversion & Management
  [ ] Article type: Research Article
  [ ] Estimated pages: 25–30 (with figures/tables)

Final Review:
  [ ] All spouse/competitor conflicts resolved
  [ ] Data availability statement proof-read
  [ ] Cover letter personalized & finalized
  [ ] One final grammar check (Grammarly)
  [ ] All materials saved locally as backup
```

### Day of Submission

```
Technical Checks:
  [ ] Internet connection stable
  [ ] All files available and accessible
  [ ] File sizes reasonable (<20 MB per file)
  [ ] Manuscript opens correctly in PDF viewer
  [ ] Figures display correctly

Upload Process:
  1. [ ] Log into Editorial Manager
  2. [ ] Click "New Submission"
  3. [ ] Select article type: "Research Article"
  4. [ ] Upload main manuscript (DOCX)
  5. [ ] Upload figures separately (PDF format)
  6. [ ] Upload supplementary ZIP archive (optional)
  7. [ ] Enter author information (all co-authors)
  8. [ ] Select corresponding author
  9. [ ] Enter keywords (4–6 terms: "MILP", "district heating", etc.)
  10. [ ] Paste abstract into system field
  11. [ ] Declare funding + conflicts of interest
  12. [ ] Select 2–4 suggested reviewers (optional)
  13. [ ] Write brief cover letter message (in EM)
  14. [ ] Review submission summary one final time
  15. [ ] Click "SUBMIT"
  16. [ ] Confirm submission received (email notification)
  17. [ ] Save manuscript number (usually ECM-YYMM-XXXXX)

Immediate After:
  [ ] Screenshot confirmation page
  [ ] Save confirmation email
  [ ] Note submission date
  [ ] Expected review timeline: 2–4 months
```

---

## POST-SUBMISSION TIMELINE

| Date | Expected Event | Action |
|------|---|---|
| **Day 0** | Submitted | Save MS number for reference |
| **Days 1–7** | Desk review by editor | Monitor email for updates |
| **Days 7–14** | Results of desk review | ACCEPT, INVITE REVISION, or DESK REJECT |
| **Weeks 2–4** | Reviewer invitation | Editors contact peer reviewers |
| **Weeks 4–8** | Peer review | Wait for reviewer feedback |
| **Weeks 8–10** | Decision letter arrives | Review comments, initiate revisions (likely) |
| **Weeks 10–16** | Revision preparation | Rewrite sections, respond to reviews |
| **Weeks 16–18** | Resubmit revised manuscript | Upload revised version + Response Letter |
| **Weeks 18–20** | Second round review | Some reviewers re-assess revisions |
| **Weeks 20–24** | Final decision | ACCEPT, MAJOR REVISION again, or REJECT |
| **Weeks 24–26** | Accepted! | Proofs provided (1–2 days to review) |
| **Weeks 26–28** | Proofread & approve | Return minor corrections |
| **Weeks 28–30** | Published online | Article appears in journal with DOI |

---

## COMMON REVISION REQUESTS

Typical reviewer comments & how to address them:

| Review Comment | Typical Action |
|---|---|
| "Case study is based on synthetic data. Is it realistic?" | Add section comparing assumptions to published DH systems. Cite 2–3 real projects. |
| "MILP time limits seem arbitrary. How sensitive are results?" | Add sensitivity analysis: what if time limit is 1800s? Cost should change <5%. |
| "Why only 3 models? What about L2.5 variant?" | Explain design rationale: 3 models selected to cover key abstraction levels. |
| "Network topology assumptions unclear." | Add detailed figure of network structure (nodes, pipes, connectivity). |
| "References are dated. Need more recent work." | Add 5–8 references from 2022–2025 (renewable energy, DH optimization, MILP). |
| "Results differences between L2/L3 are small. So what?" | Emphasize computational trade-off: L2 is 3× faster. For practitioners planning new systems, L2 sufficient. |

---

## CONTACT INFORMATION

**Energy Conversion & Management**

- **Website**: https://www.journals.elsevier.com/energy-conversion-and-management
- **Editorial Manager**: https://www.editorialmanager.com/ecam/
- **Email Editor**: editors@ecam.elsevier.com
- **Managing Editor**: [listed on website]
- **Impact Factor**: 7.2–8.5
- **Review Time**: 8–14 weeks typical

---

**Document prepared**: April 7, 2026  
**Status**: Ready for submission  
**Next step**: Customize cover letter, fill in author details, submit
