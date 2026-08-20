from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
files = [
    ROOT / "docs/paper_1/submission_pack/02_correspondence/response_letter.md",
    ROOT / "docs/paper_1/review_draft_1/response_letter_skeleton.md",
]
edits = [
    # R2.2 topology bound (conditional)
    ("topology within ±2.4 % on\nevery single network",
     "topology within $\\pm$0.6\\,% on every network of 5\\,km trunk length or more, and never above\n2.4\\,% even on the 1\\,km networks, whose entire cost gap is below 6\\,% of cost"),
    # R2.2 drift: remove the unverified 13-95 clause, keep the verified pts wording
    ("; short→long\npipe transfer under-provisions the true loss by 13–95 %)",
     ", so no single adder can track it)"),
    # R2.2 methods-note bias pair
    ("of every bias and regret figure are invariant to the CHP-CO₂ allocation. [§2.6, §4.2]",
     "of every bias and regret figure are invariant to the CHP-CO₂ allocation; the copperplate's "
     "estimation bias reads $-11.8$\\,% on the Gurobi objective and $-15.1$\\,% on the economic cost, "
     "the same finding diluted by a constant. [§2.5, §3.2]"),
]
for f in files:
    if not f.exists():
        continue
    t = f.read_text(encoding="utf-8"); ch = 0
    for a, b in edits:
        if a in t:
            t = t.replace(a, b, 1); ch += 1
    f.write_text(t, encoding="utf-8")
    print(f"{f.name}: {ch}/{len(edits)} corrections")
