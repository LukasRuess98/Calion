# LaTeX Paper Draft — Overleaf Upload Package

**Journal**: Energy Conversion & Management (Elsevier)  
**Template**: Elsevier CAS single-column (`cas-sc`)  
**Status**: Draft v1 — replace all `[TODO]` fields before submission

## Files

| File | Purpose |
|------|---------|
| `main.tex` | Full paper (7 sections + appendix) |
| `references.bib` | BibTeX bibliography (~35 entries) |
| `cas-sc.cls` | Elsevier CAS single-column document class |
| `cas-common.sty` | Shared Elsevier CAS style macros |
| `cas-model2-names.bst` | Bibliography style (author-year) |
| `figures/` | SVG figures (convert to PDF for final submission) |

## How to Upload to Overleaf

1. Select all files in this folder (including `figures/` subfolder)
2. Zip them: `zip -r paper_calion.zip .`
3. Go to [overleaf.com](https://www.overleaf.com) → **New Project** → **Upload Project**
4. Upload the zip file
5. Set compiler to **pdfLaTeX** and main document to `main.tex`

## Figure Notes

Figures are currently in SVG format. For the Overleaf compile and final
journal submission, convert them to PDF:

```bash
# Using Inkscape (recommended)
inkscape figures/fig2_dispatch_comparison.svg --export-pdf=figures/fig2_dispatch_comparison.pdf
inkscape figures/fig3_cost_comparison.svg     --export-pdf=figures/fig3_cost_comparison.pdf
inkscape figures/fig4_pipe_losses.svg         --export-pdf=figures/fig4_pipe_losses.pdf
inkscape figures/fig8_storage_soc.svg         --export-pdf=figures/fig8_storage_soc.svg
```

Then update the `\includegraphics` calls in `main.tex` by removing the
extension (LaTeX will auto-pick PDF over SVG).

## TODO Before Submission

- [ ] Fill in author names, emails, ORCIDs, affiliations
- [ ] Add funding statement and acknowledgements
- [ ] Replace placeholder Table 5.1 cost numbers with final solver output
- [ ] Convert SVG figures to PDF (min 300 DPI for raster elements)
- [ ] Add CRediT author contributions
- [ ] Verify all `[1]`–`[50]` reference numbers in text match `.bib` keys
- [ ] Add GitHub URL in Data Availability section upon acceptance
- [ ] Run spell-check and grammar check
- [ ] Confirm word count 8,000–18,000 words (target ~12,500)
