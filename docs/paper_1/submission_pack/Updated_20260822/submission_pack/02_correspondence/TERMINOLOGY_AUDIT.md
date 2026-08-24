# Terminology audit
Per the revision brief §11 and R1.2. Every occurrence of the flagged vocabulary in
`paper_COMPILE.tex`, assessed against what the evidence supports.

**Verdict: the manuscript is in good shape on this. One real overclaim, now fixed; one
unverified number living in comments; the rest is defensible and in several places
unusually careful.**

---

## Fixed

**`proves` — §2.6, station-resolved hydraulics.**
> "finding under one percent of extra cost with no feasibility violation **proves** that no
> schedule could be more than one percent better"

Changed to **establishes**. The claim itself is sound — forward re-costing genuinely
upper-bounds the regret — but "proves" is the single word R1.2 is most likely to seize on,
in the one subsection where we are making a bounding argument rather than a measurement.
The bound survives the weaker verb; the sentence does not survive a referee deciding we
overclaim.

---

## Clean, and deliberately so

**`dominates`** — appears only in build comments recording that it was removed. Zero
occurrences in body text or title. R1.1 satisfied.

**`accuracy`** — one body occurrence, §3.12:
> "estimation accuracy and control adequacy are different requirements and should be stated
> separately"

This is the sentence that *defines* the distinction rather than assuming it, and it is
immediately followed by the operational definitions. Keep.

**`ground truth`** — appears twice, both times to *reject* the framing:
> "the caveat that made a solved level an unsound ``ground truth'' in the original submission"

This is exactly what brief §21 asks for. Keep as is.

**`high-fidelity`** — used consistently of the forward evaluator, and the manuscript states
plainly in §2.1 and §2.5 that model-to-model differences are bias and that only regret
speaks to decision quality. The reference is positioned as a common benchmark, not as
truth. Defensible.

**`validated`** — heavily used, and correctly: it attaches to the annual energy and the
hydraulic component data (both genuinely validated) and is explicitly *withheld* from the
intermediate temperature field, where the manuscript says the quantity "cannot be
quantitatively validated". That asymmetry is the paper's argument, not sloppiness.

---

## Needs your attention

**`drift up to 95 % of true loss` — build comments, lines 55 and 157.**

Not body text, so it will not reach a referee as written. But it is the unverified figure
I have flagged repeatedly: no column in `frozen_adder_drift.csv` reaches 95 under any
reading, at either 42 or 135 networks. The verified figures are a mean of 23.5 and a
maximum of 40.1 percentage points for the most transferable adder.

The risk is that these comments are the specification a future regeneration writes from —
`fill_paper.py` and the abstract drafting notes both read from this block. Either supply
the normalisation that produces 95, or correct the comments to 23.5 / 40.1 so the number
cannot propagate back into the text.

---

## One addition worth making

Brief §21 recommends stating the reference model's status explicitly rather than leaving it
implied. The manuscript does this well in §2.1, but a single sentence in the abstract or
early Introduction would inoculate against the R1.2 reading at the point where most readers
form their impression. Something close to:

> The forward evaluator is not treated as ground truth; it provides a common benchmark
> against which the sensitivity of dispatch decisions to model fidelity is measured.

Fourteen words, placed once, and the terminology objection has nowhere to land.
