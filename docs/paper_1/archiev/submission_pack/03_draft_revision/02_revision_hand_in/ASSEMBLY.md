# Assembly specification — revised manuscript
**This folder is authoritative.** `01_latex_build/` and `02_correspondence/` are regenerated
by the coding agent and anything written there is transient.

`paper_COMPILE.tex` is a **generated artifact** (`fill_paper.py` builds it from
`paper_source_skeleton.tex`). Every edit below must therefore be applied to the
**skeleton**, not to the compiled file, or it will be lost at the next regeneration.

---

## 1. Section files to wire

Create `sections/` next to the manuscript and copy all fifteen files from this folder.
Then replace each marker in the skeleton with the corresponding `\input`.

| Marker in skeleton | Replace with |
|---|---|
| `<<KEEP:intro-motivation>>` | `\input{sections/introduction_opening_v2}` |
| `<<KEEP:rw-milp-topology>>` + `rw-thermohydraulic` + `rw-positioning` | `\input{sections/related_work_v2}` |
| `<<KEEP:objective>>`…`<<KEEP:emissions>>` (six) | `\input{sections/base_formulation_v2}` |
| `<<KEEP:pressure-drop>>` + `temp-prop` + `delay` | `\input{sections/extended_physics_v2}` (**before** the existing pump-reconciliation paragraph) |
| `<<KEEP:stage1>>` + `<<KEEP:stage2>>` | `\input{sections/validation_protocol_v2}` (**before** the existing validation-resolution paragraph) |
| `<<KEEP:implementation>>` | `\input{sections/computational_setup_v2}` (**before** the existing bound-reporting paragraph) |
| `<<KEEP:validation-results>>` | `\input{sections/validation_results_v2}` |
| `<<KEEP:computation>>` | `\input{sections/fidelity_vs_cost_v2}` |
| `<<KEEP:limitations-other>>` | `\input{sections/limitations_v2}` |
| `<<KEEP:nomenclature>>` | delete — moved to front matter, see §3 below |
| `<<KEEP:cop>> <<KEEP:components>> <<KEEP:pwl>> <<KEEP:taylor>>` | `\input{sections/appendices_cited_v2}` |
| `<<KEEP:selling-price>> <<KEEP:per-node-mae>> <<KEEP:hi>>` | `\input{sections/appendices_optional_v2}` |

**New subsections with no marker** — insert at the stated point:

| File | Insert |
|---|---|
| `cost_accounting_v2` | in Methodology, after the forward-evaluator subsection |
| `zone_clustering_v2` | in Results, after the decision-regret subsection |
| `physics_null_mechanisms_v2` | in Results, immediately before "Implications for modelling practice" |

**Do not carry over** `<<KEEP:bcm>>` (v1's BCM calibration) — it documents the ×1.330 trunk
multiplier and the 4.7× terminal concentration, both removed from this lineage and the
second being exactly what R2.4 objected to.

---

## 2. Structure: five sections → four

Matching the Applied Energy exemplar (Akter et al. 2024).

| Change | Action |
|---|---|
| `\section{Methodology}` | → `\section{Experimental design and methodology}` |
| `\subsection{Fidelity ladder and decomposition controls}` | → `\subsection{Experimental design: fidelity ladder and decomposition controls}` |
| `\subsection{Related work}` | → `\subsection{Literature review and research gap}` |
| `\section{Case studies}` | → `\subsection{Case studies and data}` (demote) |
| `\subsection{Memmingen}` | → `\subsubsection{Memmingen}` |
| `\subsection{Synthetic factorial}` | → `\subsubsection{Synthetic factorial}` |

Optional improvement: move the case-study subsection up to directly follow the experimental
design, so data precedes equations as in the exemplar. Currently it lands last in §2.

---

## 3. Front matter: nomenclature

After `\maketitle`:

```latex
\section*{Nomenclature}
\input{sections/nomenclature_v2}
```

Delete the appendix nomenclature block. The new file adds a first table giving the fidelity
levels against their T×P codes and the evaluation quantities (bias, regret, λ, L_t, κ),
which the original did not have.

---

## 4. Roadmap paragraph

Immediately before `\section{Experimental design and methodology}`:

> The remainder of the paper is organised as follows.
> Section~\ref{sec:methodology} sets out the experimental design -- the fidelity ladder, the
> decomposition controls and the contrasts each isolates -- then the two case studies, the
> formulations, the forward evaluator, the cost basis, the validation protocol and the
> computational setup. Section~\ref{sec:results} reports and discusses the results in the
> order of the research questions, beginning with what the measurements can and cannot
> validate and ending with the limitations of the study.
> Section~\ref{sec:conclusion} concludes.

---

## 5. Text edits lost in the regeneration

Each is located by a distinctive fragment. Apply to the **skeleton**; where the skeleton
carries a `\result{...}` macro instead of a literal number, keep the macro.

### 5.1 Abstract — factual error

Find: `cheaper on the objective`
The −15.1 % figure is the **economic** cost; the objective figure is −11.8 %.
Replace with: `cheaper on operating cost`.

### 5.2 Abstract — reorder to lead with the decision result

The findings currently open with the 95.8/4.7 decomposition and reach the opposite-signs
result fourth. Reorder so the passage beginning "Loss visibility, not spatial topology, sets
the fidelity requirement" is preceded by the decision finding:

> Judged by decisions rather than by objective values, a copperplate is a biased estimator
> \emph{and} an incompetent controller at once: its schedule looks 15.1\,\% cheaper on
> operating cost yet costs 46.1\,\% more to execute, the two carrying opposite signs,
> whereas loss-aware levels are physically deliverable. What separates them is loss
> visibility, not spatial topology. The copperplate-to-baseline cost gap decomposes …

### 5.3 Abstract — reference-model status (R1.2 inoculation)

After the parenthesis defining the forward evaluator, add:

> That forward model is not treated as ground truth; it is a common benchmark against which
> the sensitivity of dispatch \emph{decisions} to model fidelity is measured.

### 5.4 Topology bound — three places

The bound became ±2.38 % when the grid filled to 135. Stated as "on every network" it reads
weakly. Replace in the **abstract**, **§ estimation bias** and **§ generalisability** with:

> within ±0.6\,\% on every network of 5\,km trunk length or more, and never exceeding
> 2.4\,\% even on the shortest, where the entire gap is below 6\,\% of cost

All eight exceedances are at 1 km trunk length, where the total gap is 3.2–5.9 % of cost —
topology is a larger share of a far smaller quantity. Also update `tab_decomposition`'s
synthetic column to `±0.6 % (L≥5 km); ≤2.4 % at 1 km`.

Also in the estimation-bias subsection: `Across the 42 synthetic networks` → `135`.

### 5.5 Out-of-sample prose — now contradicted by its own table

Find: `to within a couple of percentage points` / `≈14\,\%`.
The regenerated table says 7 pts at 30 km, 20 pts at 50 km, MAPE 19 %. Replace with:

> It degrades materially there: the 30\,km networks are under-predicted by 7 percentage
> points and the 50\,km networks by 20, a held-out mean absolute percentage error of 19\,\%.
> We report the outcome as given rather than refitting, since a committed-in-advance
> prediction is more informative than a post-hoc curve whether it succeeds or fails -- and
> the direction of failure is itself informative, the fitted regression systematically
> under-stating the burden once extrapolated, which is the behaviour the parameter-free rule
> below corrects.

### 5.6 Fidelity-rule residual

After `its 11\,\% predicted burden close to the 15\,\% measured`, add:

> The residual four points are informative rather than error: they are the topology main
> effect, which the rule by construction does not contain, together with the accounting
> difference of Section~\ref{subsec:costacct} -- so the rule under-predicts by about the size
> of the term it omits, which is what a correctly specified first-principles bound should do.

### 5.7 Decision-regret subsection — three changes

**(a)** `(\Ltwo--\Lsix) reach regret $\approx$ bias with no calibration.` →

> the loss-aware node-resolved levels (\Lone, \Lthree, \Lsix) reach regret $\approx$ bias
> with no calibration -- as expected, since with no ignored loss to top up the
> forward-minus-economic residual is a near-constant pump offset, so the decision-relevant
> content is the copperplate's asymmetry rather than this near-equality. Temperature
> propagation (\Ltwo) is forward-evaluated rather than solved
> (Sections~\ref{subsec:evaluator} and~\ref{subsec:linearisation}), its free-variable form
> being degenerate.

**(b)** Decision-divergence, after "The asymmetry … is mechanistic":

> and the schedules show the mechanism directly rather than only its price. The copperplate
> runs the heat pump for 2\,063 hours against the baseline's 2\,309, and gives it 77.9\,\% of
> production against 87.8\,\% -- some 246 fewer operating hours and ten percentage points
> less share. Having never seen the network losses, it provisions the cheap unit for a demand
> that is too small; under execution the missing heat must then be covered by topping up at
> the marginal or peak unit, in the winter hours it never planned for, rather than by optimal
> pre-planning. The 46\,\% regret is that substitution priced.

**(c)** CP+L forward reference. Find `collapses both bias and regret to ≈ -0.54 %` and
continue:

> Taken alone this would make the ladder redundant, and it is worth saying immediately that
> it does not: the adder is calibrated ex post on this network …

**(d) NEW — add after (c).** `tab_regret` now shows CP+L at a heat-pump share of 78.2 %
against the baseline's 87.8 %:

> The control is also decision-divergent even where it is cost-equivalent: supplied with the
> right aggregate loss, it reproduces the cost to within half a percent while still running a
> materially different generation mix -- a heat-pump share of 78.2\,\% against 87.8\,\%. It
> gets the money right and the dispatch wrong, which is a second and independent reason to
> treat it as a diagnostic rather than a substitute.

### 5.8 "proves" → "establishes"

In the station-hydraulics justification: `no feasibility violation proves that no schedule
could be more than one percent better` → `establishes`. The bound survives the weaker verb;
the sentence may not survive a referee who decides we overclaim.

### 5.9 Strip reviewer markers from the body (six)

They belong in the response letter, not the manuscript.

| Find | Replace |
|---|---|
| `omitted and that Reviewer~2 identified` | `omitted` |
| `which is the substance of the R2.4 reply` | `rather than calibrated away` |
| `nonlinear reference Reviewer~2 asked for` | `nonlinear reference` |
| `answers Reviewer~2's request for rigour` | `bounds it rigorously` |
| `artefact of the loss calibration R2.4 queried` | `artefact of the loss calibration` |
| `bias alone cannot give (R1.2):` | `bias alone cannot give:` |

### 5.10 Moderator subsection — trim

At full-paragraph length an unanswered question reads as apology. Replace the whole
paragraph with:

> One scope condition attaches to the routing null. All generation in Memmingen sits at a
> single node, and the synthetic factorial's central-generation arm is built the same way, so
> the null is established for centrally-supplied networks rather than for district-heating
> networks in general. Whether resolution matters more when generation is distributed --
> making which source serves which demand a live choice -- cannot be answered by a radial
> generator that injects all heat at the primary producer: a non-root source is structurally
> stranded, and admitting one requires the signed-flow formulation discussed in the
> limitations. We therefore leave distributed generation, with meshed and bidirectional
> topologies, to the companion study.

### 5.11 Implications — worked λ example

Insert before `First, what a model must capture is the network loss`:

> Zeroth, and most concretely: the decision can be made before any model is built. Memmingen
> has a loss number of $\lambda = 0.12$ from its pipe inventory alone, which the design rule
> converts to a predicted copperplate error of 11\,\% -- above the threshold at which a lumped
> representation is safe, and therefore an instruction to resolve the nodes. The measured
> error is 15\,\%. A planner reaches that conclusion from pipe lengths, insulation classes and
> an annual demand figure, without solving anything.

### 5.12 Conclusions — four paragraphs

The editor asked for no subheadings and the exemplar uses four coherent paragraphs: what was
developed and tested; what was found; what it means for model selection; scope and
extension. The current single block should be split accordingly, with the λ criterion
leading the third paragraph — it is the most portable result in the paper and is presently
buried mid-sentence — and the fourth stating that each assumption closes a channel, so the
nulls are conservative lower bounds, with the supply-temperature study as the evidence.

Full replacement text is in `conclusions_v2.tex` in this folder.

---

## 6. Figure wiring

Six `%% Figure Fx` comments become real floats. Captions in `figures_v2.md` in this folder.

| Location | Figure |
|---|---|
| after the decomposition table | `F_decomp` |
| after the regret table | `F_regret` |
| validation subsection | `validation/stage1_scatter_Tsupply_farend`, `validation/mixing_valve_offset`, `validation/spatial_profile_test` |
| generalisability subsection | `F_drift` |
| supply-temperature subsection | `F_tsup` |
| clustering subsection | `F_r16_clustering` (already inside `zone_clustering_v2.tex`) |

Leave the linearisation and solve-time panels as comments; `tab:linearisation` and
`tab:computation` carry that content and eight figures is right for the length.

---

## 7. Markup and clean builds

Preamble:

```latex
\usepackage{xcolor}
\newif\ifmarkup \markuptrue          % \markupfalse for the clean build
\ifmarkup
  \newcommand{\new}[1]{\textcolor[HTML]{1A5FB4}{#1}}
  \newcommand{\chg}[1]{\textcolor[HTML]{0F7A5A}{#1}}
  \newcommand{\gone}[1]{\textcolor[HTML]{9A9996}{[removed: #1]}}
\else
  \newcommand{\new}[1]{#1}\newcommand{\chg}[1]{#1}\newcommand{\gone}[1]{}
\fi
```

Wrap at **paragraph** granularity. `\new` for the fifteen merged files and the four new
subsections; `\chg` for transcribed v1 material and numbers that moved with the 135-net
grid; `\gone` for exactly three removals — the BCM cross-check, v1's linearisation/delay
confound limitation, and the physics-scope mapping table. Legend text is in
`MARKUP_BUILD_NOTES.md`.

---

## 8. Package constraints

`cas-dc` does not load `siunitx` or `mhchem`. Every file in this folder uses plain units —
`CO$_2$`, `°C`, `2.5\,K`, `\,\%`. Do not reintroduce `\SI{}{}`, `\si{}` or `\ce{}`.

---

## 9. Still open

- Response-letter section pointers, against the final numbering. Currently off by one from
  the linearisation subsection onward.
- Author-confirm placeholders: acknowledgments and funding, CRediT roles, the AI-declaration
  line, declaration of interests.
- `Paper20_Literatur.bib` into `paper1_dh_fidelity/`, VSS entries merged or the
  `\bibliography` line extended.
- Graphical abstract exported with the asset-placement correction.
