# Extension request — to Editor-in-Chief, Applied Energy

**Manuscript:** APEN-D-26-15734 (submission-file header reads APEN-S-26-20346 —
please confirm which record the revision should be uploaded against)
**Title:** Topology Resolution Dominates Dispatch Accuracy in District Heating
Networks with Industrial Demands: A Five-Level MILP Comparison
**Current revision deadline:** 29 August 2026
**Requested new deadline:** 24 October 2026  ← author to confirm exact date

---

Dear Prof. Sun,

Thank you, and please pass our thanks to both reviewers, for a constructive and
detailed set of comments. We intend to revise and resubmit, and we are writing to
request an extension of the revision deadline.

Responding properly to the reviewers' central comments requires more than an
incremental revision. In particular:

- Reviewer 2's comment 2 asks for a copperplate model incorporating calibrated
  aggregate heat losses, so that the effects of topology resolution and thermal
  losses can be separated. We are adding this control condition and an exact
  additive decomposition of the cost difference into loss, topology, and
  interaction terms.
- Reviewers 1.2 and 1.3 / 2.3 concern what our comparison actually measures and
  the confounding of linearisation with transport delay. We are (i) introducing a
  decision-regret evaluation — re-simulating each model's dispatch schedule under a
  common high-fidelity forward model — to separate estimation bias from decision
  quality, and (ii) adding an intermediate formulation that isolates the
  linearisation error from the transport-delay effect, with results reported as
  rigorous optimality bounds rather than raw objective differences.
- Reviewer 2.4 concerns hydraulic validation. We are validating the hydraulic
  model against measured supply- and return-side pressure data from a second, larger
  real district-heating network, and transferring the validated parameterisation to
  the original case.
- Reviewer 2.5 concerns the synthetic study. We are running the complete balanced
  factorial with a single consistent taxonomy and a variance-based statistical
  analysis.

Together these additions — a new control model, a new evaluation metric with its
own validated forward simulator, a second real network with measured pressure data,
and the full synthetic factorial — constitute a substantial revision that we would
rather deliver thoroughly than rush. We therefore request an extension to
24 October 2026.

We would be grateful for confirmation, and we are happy to provide a more detailed
point-by-point plan in advance if that would help.

With thanks and best regards,

Lukas Ruess (on behalf of the authors)
