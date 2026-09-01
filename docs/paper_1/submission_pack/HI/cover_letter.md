Lukas Ruess
Fraunhofer IPA
Nobelstr. 12
70569 Stuttgart, Germany

August 27, 2026

Editor-in-Chief
Applied Energy
Elsevier

Dear Editor-in-Chief,

We are pleased to submit a revised version of our manuscript (Manuscript ID: APEN-D-26-15734), originally entitled "Topology Resolution Dominates Dispatch Accuracy in District Heating Networks with Industrial Demands: A Five-Level MILP Comparison," for further consideration in Applied Energy.

We thank you and the reviewers for the careful and constructive review of the original submission. The comments were detailed, fair, and substantially improved the paper. We have revised the manuscript thoroughly in response. Every comment is answered point by point in the accompanying Response to Reviewers, and all changes are shown in the accompanying marked-up manuscript.

**Summary of the revision.** The revision reframes the study around the question the reviewers found most valuable and tightens every claim to the evidence:

* The title is now "Loss Visibility versus Spatial Detail in District-Heating Dispatch Optimisation," which removes the overstated "dominates" and states the finding precisely.
* A control condition (a copperplate supplied with the aggregate loss it cannot itself compute) now separates thermal-loss visibility from spatial topology, so the two effects are priced independently rather than confounded.
* The evaluation is decision-oriented: each model's schedule is re-costed under a common high-fidelity forward model, distinguishing estimation bias from a forward-valued decision-regret gap.
* The synthetic study is expanded to a balanced 135-network factorial, and hydraulic plausibility is checked against real pump data and an independent pandapipes solve.

**Main findings** (within the tested scope of radial, centrally supplied networks with fixed capacities and hourly dispatch):

* The copperplate underestimates operating cost by 15.1%, yet its schedule carries a +46.1% forward-valued decision regret: it is both a biased estimator and an inadequate controller.
* Thermal-loss visibility accounts for 95.8% of the copperplate-to-baseline cost gap, while spatial topology alone, with physics held fixed, adds 0.25%.
* Extended thermo-hydraulic detail (trunk pressure and station-resolved hydraulics) changes forward-evaluated cost by under 1%.

**Fit with journal scope.** The manuscript addresses Applied Energy's interest in energy-systems optimisation, district heating, and mathematical programming for operational planning. The controlled separation of loss visibility from spatial resolution, and the decision-oriented evaluation of model fidelity, may be of practical relevance to researchers and practitioners selecting model complexity for network dispatch problems.

**Novelty and limitations.** To our knowledge, no prior study has isolated thermal-loss visibility from spatial topology as independent experimental factors in a district-heating dispatch setting, nor evaluated the resulting schedules under a common high-fidelity reference rather than by objective values alone. We are careful to state that these findings rest on one validated industrial case supplemented by synthetic networks, and that the scope is limited to radial, centrally supplied trees with a fixed heating curve. Ring topologies, distributed generation, and variable supply temperature are identified as priority follow-up work.

**Declarations.**

* This manuscript has not been published previously and is not under consideration for publication elsewhere.
* All authors have read and approved the submitted version.
* The authors declare no conflicts of interest.
* This work was funded by the German Federal Ministry for Economic Affairs and Energy (BMWE) under grant number 03EN6057B (project eProNet).
* During manuscript preparation, generative AI tools (Claude, Anthropic) were used for language improvement and code support. All content was reviewed and edited by the authors, who take full responsibility for the publication.
* The optimisation model source code and configuration files are available on Zenodo under a Creative Commons Attribution 4.0 International license. Input time series are subject to NDA; anonymised summary statistics are included.

Sincerely,

Lukas Ruess
Fraunhofer Institute for Manufacturing Engineering and Automation IPA
Institute for Energy Efficiency in Production EEP, University of Stuttgart
lukas.ruess@ipa.fraunhofer.de
