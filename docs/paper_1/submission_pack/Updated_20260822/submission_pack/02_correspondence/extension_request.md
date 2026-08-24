# Extension request — to Editor-in-Chief, Applied Energy

**Manuscript:** APEN-D-26-15734
**Title (revised):** Estimation Bias versus Decision Regret in District-Heating Dispatch
Optimisation: Loss Visibility, not Network Topology, Sets the Fidelity Requirement
**Current revision deadline:** 29 August 2026
**Requested new deadline:** _[author to set / on hold — not being finalised here]_

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
- Reviewer 2.4 concerns hydraulic validation. We are strengthening it with real
  component data: manufacturer pump characteristics (installed capacity vs the
  network's actual hydraulic pumping need), a reconstruction of the demand side down
  to the individual transmission stations and their service laterals from the network
  DXF plans, and an independent cross-check of the linearised hydraulics against a
  nonlinear pipe-flow solver. This clarifies the supply and return circuits,
  substations, pressure requirements and pump characteristics, and explains the
  pumping-energy magnitude physically rather than by calibration.
- Reviewer 2.5 concerns the synthetic study. We are running the complete balanced
  factorial with a single consistent taxonomy and a variance-based statistical
  analysis.

Together these additions — a new control model, a new evaluation metric with its own
validated forward simulator, station-resolved hydraulics validated on real component
data, and the complete 135-cell synthetic factorial — constitute a substantial revision
that we would rather deliver thoroughly than rush. We therefore request an extension to
_[DATE — author to set before sending]_.

We would be grateful for confirmation, and we are happy to provide a more detailed
point-by-point plan in advance if that would help.

With thanks and best regards,

Lukas Ruess (on behalf of the authors)
