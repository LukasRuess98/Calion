# Response to Reviewers

| **Manuscript ID:** APEN-D-26-15734R2
| **Title:** Loss Visibility versus Spatial Detail in Industrial District-Heating Dispatch Optimisation
| **Authors:** Lukas Ruess, Alexander Sauer

We thank both reviewers for their assessments. The revision is confined to the two points raised by Reviewer #2; no results, figures, data, or numerical values have changed, apart from one table caption and one rounding phrase in Section 3.3 (both noted under Comment 1). Quoted passages below are the added manuscript text verbatim. Page and line numbers refer to the marked-up copy.

---

## Reviewer #1

> *The author addressed my concerns and the paper can be accepted now.*

**Response.** We thank the reviewer for the constructive review of the previous version and for the recommendation. No further changes were requested, and none have been made in response to this report.

---

## Reviewer #2

> *The revision is thorough and responsive. The new CP+L control properly separates loss visibility from topology, and the decision-regret metric adds genuine value. The paper is now methodologically sound and clearly scoped. I recommend acceptance after minor revisions.*

We thank the reviewer for this assessment and for two suggestions that improved the paper. Both are implemented.

### Comment 1 --- Regret definition versus the value of the stochastic solution

> *The regret definition is non-standard. Please add a brief sentence in Section 2.4 explicitly contrasting it with the classical Value of the Stochastic Solution, explaining why negativity is possible.*

**Response.** We agree that this contrast belonged at the point of definition rather than only in the Introduction. A new paragraph, *Relation to the value of the stochastic solution*, has been added at the end of Section 2.4 (p. 11--12, ll. 507--523):

> The metric is the resolution-axis analogue of the value of the stochastic solution [53], and one structural difference between the two is worth stating explicitly, because it is what makes $r_\ell < 0$ possible. In the classical construction, $\mathrm{VSS} = \mathrm{EEV} - \mathrm{RP}$, the comparator is the optimum of the very programme under which both candidates are evaluated: the expected result of using the expected-value solution ($\mathrm{EEV}$) evaluates a solution that is feasible for, but generally suboptimal in, the stochastic programme whose optimum is the recourse problem value ($\mathrm{RP}$), so $\mathrm{VSS} \ge 0$ for a cost-minimisation problem by construction. Here the comparator is the forward-evaluated cost of the baseline *schedule*, and the baseline is optimal for its own formulation, not for the forward model, which is never optimised; both schedules are fixed decision vectors valued under a common evaluator, and any loss shortfall is priced as an overlay rather than removed by recourse. Nothing therefore makes the baseline a lower bound on forward-evaluated cost, and a coarser level can fall below it, either because its schedule was optimised against a slightly conservative loss representation that the native exponential decay then relaxes, or because its shortfall is valued more cheaply than the baseline's own provisioning of it, the first of which accounts for the values observed here; negative regret is admissible and is reported where it occurs (Table 9). It is informative rather than anomalous, identifying a level whose schedule happens to execute marginally better than the baseline's under the finer physics. Sign-definiteness would be recovered if the uncomputed high-fidelity optimum were taken as the comparator, which is precisely the quantity this construction is designed to avoid.

Two supporting edits accompany it. The symbols $b_\ell$ and $r_\ell$, already listed in the Nomenclature, are now attached to the defining sentence in Section 2.4 (p. 11, ll. 495--496), and the Introduction's existing remark on sign-definiteness carries a forward reference to Section 2.4 (p. 6, l. 297). The negative values the paragraph refers to are the CP+L rows of Table 9, at $-0.5$ % and $-0.6$ %; Table 9's caption now notes explicitly that negative regret is admissible under this construction.

For consistency with Table 9, the summary in Section 3.3 (p. 24, l. 906) now reads "to within about half a percent" in place of a single rounded figure; the underlying values are unchanged.

### Comment 2 --- Equivalent energy storage as a complementary abstraction

> *The introduction reviews model fidelity extensively but does not engage with a complementary simplification approach: representing network thermal inertia as equivalent energy storage. [...] A brief discussion of this line of work in the Introduction would help position the paper within the broader landscape of DH model reduction strategies, particularly since both approaches address what physics a dispatch model must retain.*

**Response.** We thank the reviewer for directing us to this literature, which sharpened our positioning rather than merely broadening it. A new passage has been added to Section 1.1 (Literature review and research gap), immediately after the spatial-aggregation discussion (p. 4, ll. 215--241):

> A complementary reduction strategy sets the spatial dimension aside altogether and abstracts the network's thermal capacity into an equivalent store. Because the transport delay through the pipe water inventory decouples source output from load over a horizon of hours --- an internal heat-migration process distinct from the capacitive buffering of a building envelope --- the network can itself be dispatched as storage: Li et al. [31] exploit this pipeline energy storage to decouple heat and power output in combined-heat-and-power dispatch, and Vandermeulen et al. [32] review the control strategies that release the resulting flexibility. Yang et al. [33] carry the idea to its reduced-order limit for integrated electricity--heat systems, representing the district-heating system as an equivalent energy store whose parameters are identified by a hybrid machine-learning estimator, and report an improvement of about 20 % in the computational performance of the economic dispatch. The abstraction runs along the temporal rather than the spatial axis, and is complementary to the one studied here: spatial aggregation asks how much of a network's *structure* a dispatch model may discard, equivalent storage how much of its *dynamics* a single state can carry. Both answer the same underlying question, which physics a dispatch model must retain; Yang et al. [33] draw the same taxonomic line in their own review of network-simplification models, citing Falay et al. [18] alongside a thermal-inertia aggregation study.
>
> The loss-supplied copperplate control CP+L used here is analogous in removing explicit topology while retaining aggregate loss visibility, but it does not reproduce the dynamic thermal-inertia representation of an equivalent store, whose storage capacity arises from the supply-temperature degree of freedom that the prescribed heating curve used here removes (Section 3.7). Yang et al. [33] adopt constant-flow, variable-temperature (qualitative) regulation, so their equivalent-storage capacity is created by this temperature degree of freedom; the formulation used here instead prescribes supply and return temperatures and makes mass flow linear in pipe heat flow (quantitative regulation, Eq. (14)), which is precisely why the network itself carries no storable state here, independently of the dedicated thermal store (Eq. (11), Table 5). The two are therefore related topology-free abstractions rather than dynamically equivalent ones. So far as the analogy carries, the result reported below, that loss visibility rather than spatial structure accounts for almost all of the copperplate gap, offers one reason why topology-free abstractions can perform as well as they do. Yang et al. [33] quantify agreement as a generator-output match of about 95 % between the reduced and resolved dispatch models; the cost of executing the reduced model's schedule on the network it was reduced from, which this paper measures, is a distinct question.

This passage identifies the mechanism rather than merely asserting the caveat, and does so without contradicting Eq. (11): whether the network carries dynamic storage *state* turns on the flow/temperature regulation regime, not on the presence of the dedicated 500 MWh thermal store already in the model (Table 5), which is a separate, explicit state variable unaffected by this discussion. We deliberately stop short of claiming that an equivalent store and the CP+L control occupy the same position: the two are presented as related topology-free reductions rather than as dynamically equivalent formulations.

We have additionally linked the new references to the discussion of pipe thermal inertia and sub-hourly operation in Section 3.14, *Uncertainty, reserves and sub-hourly operation* (p. 35, ll. 1199--1201), so that this literature informs both the positioning and the limitations of the study rather than being cited only in passing. There, each reference is now attached to a single, distinct claim rather than jointly cited for one statement: the pipeline-energy-storage mechanism is attributed to Li et al. [31] alone, and the equivalent-storage reduction it is designed to represent is attributed to Yang et al. [33] alone.

---

## References added in this revision

Z. Li, W. Wu, M. Shahidehpour, J. Wang, B. Zhang, Combined heat and power dispatch considering pipeline energy storage of district heating network, *IEEE Transactions on Sustainable Energy* 7 (1) (2016) 12--22. doi:10.1109/TSTE.2015.2467383

A. Vandermeulen, B. van der Heijde, L. Helsen, Controlling district heating and cooling networks to unlock flexibility: A review, *Energy* 151 (2018) 103--115. doi:10.1016/j.energy.2018.03.034

M. Yang, T. Ding, X. Chang, Y. Xue, H. Ge, W. Jia, S. Du, H. Zhang, Analysis of equivalent energy storage for integrated electricity-heat system, *Energy* 303 (2024) 131892. doi:10.1016/j.energy.2024.131892
