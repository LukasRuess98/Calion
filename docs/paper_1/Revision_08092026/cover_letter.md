| Lukas Ruess
| University of Stuttgart
| Allmandring 35
| 70569 Stuttgart

| 8 September 2026

| Editor-in-Chief
| Applied Energy
| Elsevier

Dear Editor-in-Chief,

Please find enclosed the second revision of our manuscript (Manuscript ID: APEN-D-26-15734R2), "Loss Visibility versus Spatial Detail in Industrial District-Heating Dispatch Optimisation," submitted for further consideration in *Applied Energy*.

We are grateful to both reviewers. Reviewer #1 confirms that the previous revision addressed their concerns and recommends acceptance. Reviewer #2 judges the revision thorough and responsive and recommends acceptance after two minor revisions. We have implemented both, and we thank Reviewer #2 in particular for two suggestions that improved the paper.

**Changes in this revision.** The revision is confined to the two points raised. No results, figures, tables of results, data, or numerical values have changed, apart from one table caption and one rounding phrase in Section 3.3, both noted in the response letter.

* *Positioning of the regret metric (Reviewer #2, comment 1).* Section 2.4 now contains a short paragraph contrasting our decision-regret metric with the classical value of the stochastic solution at the point of definition. It states the standard construction, VSS = EEV − RP, notes that it is non-negative for a cost-minimisation problem because both candidates are evaluated under the stochastic programme whose optimum is RP, and explains why our metric carries no such guarantee: the comparator is the forward-evaluated cost of the baseline *schedule*, the baseline is optimal for its own formulation rather than for the forward evaluator, and any loss shortfall is priced as an overlay rather than removed by recourse. Negative regret is therefore admissible, and the paragraph points to the values already reported in the manuscript.

* *Equivalent energy storage (Reviewer #2, comment 2).* The literature review now engages with the representation of network thermal inertia as equivalent energy storage, a reduction strategy complementary to spatial aggregation. Three references have been added. We use the paragraph to sharpen our positioning rather than only to broaden it: spatial aggregation asks how much of a network's structure a dispatch model may discard, equivalent storage how much of its dynamics a single state can carry. We note that our loss-supplied copperplate control is analogous in discarding explicit topology while retaining aggregate loss visibility, and identify the mechanism behind why it does not reproduce the dynamic thermal-inertia representation of an equivalent store: that representation's storage capacity arises from a supply-temperature degree of freedom that the prescribed heating curve used here removes, so that the two are presented as related topology-free reductions rather than as equivalent formulations.

Two smaller edits follow from the first point: the bias and regret symbols already listed in the Nomenclature are now attached to their defining sentence in Section 2.4, and the Introduction carries a forward reference to that paragraph. The new references are additionally linked to the discussion of pipe thermal inertia and sub-hourly operation in Section 3.14, so that this literature informs both the positioning and the limitations of the study rather than being cited only in passing.

All changes are marked in the accompanying marked-up manuscript and answered point by point in the Response to Reviewers.

**Declarations.** The declarations submitted with the previous revision are unchanged and are restated for completeness. The manuscript has not been published previously and is not under consideration elsewhere. All authors have read and approved the submitted version. The authors declare no conflicts of interest. This work was funded by the German Federal Ministry for Economic Affairs and Energy (BMWE) under grant number 03EN6057B (project eProNet). During manuscript preparation, Claude Opus 5 (Anthropic) was used for language improvement, manuscript structuring and editing, and code generation and debugging; all content was reviewed and edited by the authors, who take full responsibility for the publication. The optimisation model source code and configuration files are available on Zenodo under a Creative Commons Attribution 4.0 International license; input time series are subject to a non-disclosure agreement, and anonymised summary statistics are included.

We hope the manuscript is now suitable for publication and thank you for your handling of the review.

Sincerely,

| Lukas Ruess
| Fraunhofer Institute for Manufacturing Engineering and Automation IPA
| Institute for Energy Efficiency in Production EEP, University of Stuttgart
| lukas.ruess@ipa.fraunhofer.de
