from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
files = [
    ROOT / "docs/paper_1/submission_pack/02_correspondence/response_letter.md",
    ROOT / "docs/paper_1/review_draft_1/response_letter_skeleton.md",
]

bridge = """
## Level nomenclature bridge (v1 → v2)

The reviewers hold the original submission, in which the level names mean different things.
All three of `L1`, `L2`, `L3` were reassigned in the revision; the point-by-point responses
below use the v2 names.

| v1 | v1 meaning | v2 |
|---|---|---|
| L1 | copperplate, no loss | **CP** |
| L2 | 7 aggregated zones | **ZN** |
| L1_topo | routing, no loss (synthetic auxiliary) | **ND⁰** |
| L3 | 15 nodes + trunk loss | **L1** (baseline) |
| L3⁺ | + pressure, temperature, delay bundled | split into **L2**, **L3** |
| L3ᴺᴸ | native nonlinear, delay active | split into **L6**, **NL** |

Thus R1.2's "13 % between L1 and L3" is the CP→L1 gap in v2 terms, now −11.8 % on the Gurobi
objective and −15.1 % on the economic cost. We note honestly that v1 already contained
`L1_topo` (routing without losses, today's `ND⁰`) as a synthetic-only auxiliary; R2.2's
confound objection stands for the primary results, and we say so rather than leaving R2 to
find it.

---
"""

held_out_old = ("For **additional out-of-sample validation** we (i) split the spatial\n"
                "validation into fitted and held-out node sets, and (ii) test the a-priori bias estimator on\n"
                "held-out synthetic networks beyond the fitted pipe-length range, as R2.5 also requests.")
held_out_new = ("On further examination we found that a held-out node split cannot be constructed on this\n"
                "network for the same reason the temperature gates cannot be met: with consumer sensors\n"
                "downstream of mixing valves, no node provides a junction-temperature reference against which\n"
                "a held-out prediction could be scored. Rather than report a split we cannot defend, we added a\n"
                "first-difference comparison, which is immune to a fixed valve offset and tests whether the\n"
                "model reproduces the network's variation: flow level $r=0.91$ and day-to-day change $r=0.80$,\n"
                "demand $0.93$ and $0.89$. The held-out evidence in the paper is therefore the synthetic\n"
                "out-of-sample test, reported including its degradation beyond the fitted range (as R2.5 also requests).")

for f in files:
    if not f.exists():
        print("skip (missing):", f.name); continue
    t = f.read_text(encoding="utf-8")
    ch = []
    if "Level nomenclature bridge" not in t and "## Reviewer 2" in t:
        t = t.replace("## Reviewer 2", bridge + "\n## Reviewer 2", 1); ch.append("bridge")
    if held_out_old in t:
        t = t.replace(held_out_old, held_out_new, 1); ch.append("held-out")
    f.write_text(t, encoding="utf-8")
    print(f"{f.name}: {ch}")
