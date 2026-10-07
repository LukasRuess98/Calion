> **WITHDRAWN 2026-09-19 — DO NOT USE.** The reported ~10x TES-site spread is an incumbent-quality artifact (pairs with 55-96 % MIP gap, garbage max-size tanks); trustworthy tight-gap pairs sit at ~13.2 M EUR with no TES built. See MODEL_AND_DOE_CONTROL.md section 4r.

# Draft paragraph — Stadtbach TES-siting sensitivity (Study C / SB-S6-HK0)

*Manuscript-ready, ~150 words. Cite against `output/paper2_runs/_endog_enum/SB-S6-HK0_atmo/` (23/25 pairs
solved; 2 genuine no-incumbent gaps: j_man×j_man, j_psw×j_hkw) and the pairwise-enumeration methodology
of §4o/Study C (bypasses the monolithic endogenous-siting MILP's weak LP-relaxation bound). Numbers
validated against the current storage_geometry.yaml / atmospheric-TES configuration, 2026-09-15.*

---

For the Stadtbach network, exhaustive pairwise enumeration of heat-pump and storage sites (5×5 candidate
nodes, HK0) shows that total annual cost is governed almost entirely by *where the thermal storage is
sited*, not by the heat pump's location. Aggregating by storage node, mean system cost ranges from
€14.4M when storage is placed at node j_ost to €136.8M at j_psw — an order-of-magnitude spread — while
varying the heat-pump site alone, holding storage fixed, changes cost by at most a few percent. The
cheapest configuration overall places the heat pump at j_psw and the storage at j_ost (€12.28M/a). This
asymmetry is consistent across every heat-pump placement tested, indicating it reflects a structural
property of the storage node's local network position (hydraulic head, connectivity, distance from the
supply source) rather than an artifact of any one pairing. For planning purposes, this suggests storage
siting deserves materially more attention than heat-pump siting in networks with a comparable topology.

---

## Supporting numbers (for table/appendix)

| TES site | mean obj [€/a] | n pairs | min | max |
|---|---|---|---|---|
| j_ost | 14,437,918 | 5 | 12,275,477 | 18,426,018 |
| j_man | 34,130,080 | 4 | 29,057,652 | 38,918,272 |
| j_hkw | 60,610,900 | 4 | 31,466,103 | 77,342,710 |
| j_pss | 87,796,540 | 5 | 34,146,795 | 102,446,305 |
| j_psw | 136,793,570 | 5 | 104,166,292 | 253,172,708* |

\* includes one candidate-outlier pair (j_psw×j_psw, co-located) at ~2.5× its next-worst sibling in
the group — flagged for judgment, not automatically excluded (unlike the >800M€-class degenerate
artifacts seen elsewhere in this campaign, which were unambiguous numerical breakdowns).

Best overall pair: HP@j_psw × TES@j_ost = €12,275,477/a.
Two pairs returned no incumbent within the time budget (real data gaps, not invented/estimated):
j_man×j_man, j_psw×j_hkw.
