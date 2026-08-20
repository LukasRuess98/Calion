# Submission plan — APEN-D-26-15734
**Target: 29 August 2026** (17 days from 12 Aug) · Applied Energy, major revision
Markup style: **colour-highlighted rewrite** · Structure: **proposed below** · Edit depth: **full pass incl. voice**

---

## 1. What Elsevier needs on the day

Editorial Manager takes these as separate items. Anything marked ✗ does not exist yet.

| # | Item | Format | Status |
|---|---|---|---|
| 1 | **Manuscript, clean** | `.tex` + `.pdf` + all `\input` files | ⚠ body ~60 % written |
| 2 | **Manuscript, marked-up** | separate `.tex` → `.pdf`, changes in colour | ✗ |
| 3 | **Response to reviewers** | `.docx` or `.pdf` | ⚠ content good, needs final refs + conversion |
| 4 | **Highlights** | plain text, 3–5 bullets ≤85 chars | ✓ `highlights.txt` |
| 5 | **Graphical abstract** | image (from the `.pptx`) | ⚠ needs export + the asset-placement fix |
| 6 | **Figure source files** | PDF (vector) — already 600 dpi | ✓ |
| 7 | **Bibliography** | `Paper20_Literatur.bib` in `paper1_dh_fidelity/` | ✗ **not in place** |
| 8 | **CRediT statement** | in manuscript | ✗ placeholder |
| 9 | **Declaration of interests** | Elsevier form | ✗ |
| 10 | **AI-use declaration** | in manuscript | ✗ placeholder — pick one of the two template lines |
| 11 | **Acknowledgments / funding** | in manuscript | ✗ placeholder |

**Items 7–11 are author-only and take under an hour combined.** They are the cheapest
possible way to lose a week — do them first, not last.

### The markup version, concretely

Since the paper is substantially restructured, a `latexdiff` would mark almost every line
and tell the editor nothing. Instead: one preamble block, applied to `paper_COMPILE.tex`
saved as `paper_MARKUP.tex`.

```latex
\usepackage{xcolor}
\newcommand{\new}[1]{\textcolor{blue}{#1}}        % new or rewritten in revision
\newcommand{\chg}[1]{\textcolor{teal}{#1}}        % v1 text, materially edited
\newcommand{\gone}[1]{\textcolor{gray}{[removed: #1]}}
```

Rule: wrap at **paragraph** granularity, not sentence — sentence-level colouring on a
rewrite of this size is unreadable. Add a one-paragraph legend under the title. The clean
version is the same file with the three macros redefined to pass through, so the two
cannot drift apart. Build both from one source.

---

## 2. Proposed structure

The Senior Editor asked for the structure to be modified per recent Applied Energy papers.
Current layout is sound; the changes below are targeted, not a reorganisation for its own
sake.

| § | Section | Change |
|---|---|---|
| 1 | Introduction | Keep. Merge v1's motivation opening (v1 L186) ahead of the framing paragraph, then Related work as §1.1, contributions as §1.2. |
| 2 | Methodology | **Add §2.6 "Cost accounting: economic cost versus the solver objective."** It is promised in the response letter, referenced as §2.6, and does not exist. Renumber Validation protocol → §2.7, Implementation → §2.8. |
| 3 | Case studies | Keep as-is. |
| 4 | Results and discussion | **Split.** Twelve subsections in one section is the structural complaint. Results (validation, bias, regret, hydraulics, T_sup, linearisation) become §4; Discussion (implications, limitations) becomes §5. Recent Applied Energy papers overwhelmingly separate the two. |
| 5→6 | Conclusions | Renumber. No subheadings (editor). |

**Also:** promote the R1.6 clustering result out of the response letter into §4.4 with
`F_r16_clustering`. It is currently a reviewer answer only, and it independently
corroborates the central decomposition — that is worth a half-page in the body.

**Also:** strip every `R1.x` / `R2.x` marker from the manuscript body. They belong in the
response letter. Currently they appear in `tab_contrasts`, `tab_linearisation`,
`tab_criteria` and several section comments.

---

## 3. Work plan to 29 August

**Phase 1 — author-only, day 1 (≈1 h, blocks nothing else but risks everything)**
Bibliography into place; VSS entries merged; CRediT; funding; AI declaration; declaration
of interests; graphical abstract exported with the asset-placement correction.

**Phase 2 — carry-over merge, days 1–5.** The bulk of the remaining writing. In risk order:

| Section | Source | Risk |
|---|---|---|
| Base formulation §2.2 | v1 L724 | **highest** — level names in every equation, all numbers predate the defensible-U recalibration |
| Extended physics §2.5 | v1 L967 | high — Darcy–Weisbach and temperature-propagation equations |
| Related work §1.1 | **done** — `related_work_v2.tex` | — |
| Validation protocol §2.7 | v1 L1138 | medium |
| Implementation §2.8 | v1 L1206 | low — update hardware to 66 cores / 180 GB |
| Introduction opening | v1 L186 | low |
| Validation results §4.1 | v1 L1449 | medium — must now carry the failed-threshold argument |
| Computational performance | v1 L1812 | low |
| Limitations | v1 L2085 | medium — several v1 limitations became v2 *results* |
| Nomenclature + appendices | v1 L2275–2860 | low but bulky |

Merge rule for all of them is in `LEVEL_CROSSWALK_v1_to_v2.md`: v1 `L1` = `CP`,
v1 `L3` = `L1`. Every number re-derived from the v2 CSVs, never transcribed.

**Phase 3 — figures, day 6.** Nine figures exist and one is wired. Insert F_decomp,
F_regret, F_drift, F_tsup, F_r16_clustering and the validation set at their marked
locations, write captions, check every `\ref`.

**Phase 4 — full voice pass, days 7–9.** Strip scaffolding language, enforce terminology
discipline ("accuracy" only of decisions), tighten. Verify every number against its CSV
one final time.

**Phase 5 — markup + response letter, days 10–11.** Generate both PDFs from one source.
Fill the final Table/Figure numbers into the response letter, convert to `.docx`.

**Phase 6 — reader test, days 12–13.** Fresh read against the reviewer comments with no
prior context, to catch what we have stopped being able to see.

**Days 14–17: buffer.** It will be used.

---

## 4. Review box-check

**Reviewer 1**

| # | Comment | Status |
|---|---|---|
| R1.1 | "dominates" overclaims | ✓ Title changed; restrictions became experimental factors; ring/bidirectional boundary stated concretely (signed-flow variables needed). Strong. |
| R1.2 | accuracy vs sensitivity | ✓ Regret is a decision quantity; reference roles defined §2.1; terminology held. |
| R1.3 | L3⁺/L3ᴺᴸ confounded | ✓ Delay isolated as L6 and measured at exactly 0.00 %; `tab_contrasts` shows one phenomenon per arrow. |
| R1.4 | pre-upgrade validation | ✓ Concedes first, then three reasons the comparative conclusions survive. In §3.1 and limitations. |
| R1.5 | assumptions constrain physics | ⚠ **Partly.** The T_sup study answers the heating-curve half well. Precomputed COP and sub-hourly dynamics still exist only as a comment under `<<KEEP:limitations-other>>`. **Phase 2.** |
| R1.6 | clustering arbitrariness | ✓ **Now answered with data** — 24 solves, 0.008 % spread at conserved ΣU·L, and the non-conserving case reported as a modelling hazard. Response letter rewritten this session. Still to promote into the body. |
| R1.7 | deterministic, hourly, no reserves | ✗ **Not written.** "Limitations expanded" — the expansion does not exist. **Phase 2, highest priority of the two gaps.** |

**Reviewer 2**

| # | Comment | Status |
|---|---|---|
| R2.1 | novelty | ✓ Concedes formulations are established, rests on two pillars plus the parameter-free rule. Strongest single addition. |
| R2.2 | topology/loss confound | ✓ Exactly the requested control; exact identity closing to 0 €; plus the drift result that stops CP+L making the ladder redundant. |
| R2.3 | linearisation not rigorous | ✓ All three remedies plus a *solved* nonlinear reference. Non-convergent full year and infeasible summer week reported as results — the right call. |
| R2.4 | validation / pumping energy | ✓ Physical explanation, pandapipes cross-check, DXF laterals, defensible U-values — and `tab_validation` now reports all five failed thresholds openly. That table went from a liability to an asset. |
| R2.5 | generality / filtering | ✓ Filtering **eliminated**: all 135 cells solved, balanced ANOVA, consistent taxonomy, out-of-sample test reported honestly including its degradation. |

**Senior Editor**

| Item | Status |
|---|---|
| No lumped references | ⚠ Related work is de-lumped; the rest of the body has no citations yet. Verify after Phase 2. |
| Abstract one paragraph | ✓ |
| No subheadings in Conclusions | ✓ |
| Restructure per recent papers | ⚠ §2 above, Phase 2–3. |
| Source files not PDF | ⚠ blocked on the `.bib` only. |
| Highlights | ✓ |

**Two open boxes: R1.7 and the R1.5 remainder.** Both are limitations prose, both are
cheap, and both are the kind of thing a reviewer checks first because it is the easiest
promise to verify. They should not be left to the buffer.

---

## 5. What would most improve the draft

Beyond finishing it. In descending order of value per hour.

**1. Lead the abstract with the decision result, not the decomposition.** The 95.8/4.7
split is the mechanism; the finding a reader remembers is that a model can be 15 % *cheaper*
on paper and 46 % *dearer* to run. Opposite signs is the sentence that gets the paper cited.
It currently arrives fourth.

**2. Say what a practitioner should do differently on Monday.** §4.11 has the material but
frames it as observations. The λ rule is a genuine screening criterion — compute one number
from the pipe inventory, before any optimisation, and know whether a copperplate will do.
That deserves a worked Memmingen example: λ = 0.12 → predicted burden 11 % → "resolve the
nodes", confirmed at 15 %. Three sentences, and it converts a result into a tool.

**3. Resolve the CP+L tension in the reader's mind before they raise it.** A reader reaching
§4.3 sees CP+L at −0.6 % bias and −0.5 % regret and concludes the whole ladder is
unnecessary. The drift answer is two subsections later. Forward-reference it at the point
the tension appears, in one clause.

**4. The 15.1 % gap deserves a physical sanity check.** λ = 0.12 predicts 10.8 %; measured
is 15.1 %. That 4-point residual is the topology term plus the accounting. Saying so
explicitly makes the rule look tested rather than fitted.

**5. Cut the moderator section to three sentences.** §4.4 presently spends a paragraph
explaining that a question could not be answered. Under R1.1 that is honest and necessary;
at current length it reads as apology. State the null under central generation, state that
distributed generation needs signed-flow variables, move on.

**6. One decision-divergence metric.** Every regret number is a cost. A reader will ask
*what did the copperplate actually decide differently* — heat-pump hours, or CHP-vs-boiler
share. One row would make the abstraction concrete. The drafting note at §4.3 already asks
for this. Requires no new solve, only post-processing of schedules already on disk.

**7. Retire `decomposition.csv` and `decomposition_synth_poc.csv`.** Still in `data/`,
still uncited, and `superseded/` now exists. Same reasoning that moved the other five.

---

## 6. Standing risks

- **Sync integrity.** Three partial syncs this week, root-caused to `grep -c` breaking a
  `&&` chain. Fixed — but the failure mode was a table updating while its source CSV did
  not, which is undetectable by eye. Before submission, verify every number in every table
  against its CSV once more, mechanically.
- **`paper_source_skeleton.tex` divergence.** Edits made directly to `paper_COMPILE.tex`
  this session — the abstract topology bound, §4.2, §4.8 out-of-sample prose — must be
  mirrored into the skeleton or regenerated via `fill_paper.py`, or the next regeneration
  silently reverts them.
- **Level-name collision.** v1 `L1` = `CP` and v1 `L3` = `L1`. This will bite during the
  Phase 2 merge, silently and in the equations.
- **The reviewers hold v1.** They will read the response letter with v1's level names in
  front of them. The crosswalk note in `LEVEL_CROSSWALK_v1_to_v2.md` §"Numbers the
  reviewers quote" should become a short table at the top of the response letter.
