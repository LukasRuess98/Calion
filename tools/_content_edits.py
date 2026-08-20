from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SK = ROOT / "docs/paper_1/submission_pack/01_latex_build/paper_source_skeleton.tex"
t = SK.read_text(encoding="utf-8")

lam = (r"Zeroth, and most concretely: the decision can be made before any model is built. "
       r"Memmingen has a loss number of $\lambda=0.12$ from its pipe inventory alone, which the "
       r"design rule converts to a predicted copperplate error of 11\,\% -- above the threshold at "
       r"which a lumped representation is safe, and therefore an instruction to resolve the nodes. "
       r"The measured error is 15\,\%. A planner reaches that conclusion from pipe lengths, "
       r"insulation classes and an annual demand figure, without solving anything. ")

divergence = (r"rather than by optimal pre-planning. The schedules show this directly: the "
              r"copperplate runs the heat pump 2\,063 hours against the baseline's 2\,309 and gives "
              r"it 77.9\,\% of production against 87.8\,\% -- 246 fewer operating hours and ten "
              r"percentage points less share, the 46\,\% regret being that substitution priced. "
              r"Supplying the same")

edits = [
    # 5.8 proves -> establishes
    ("violation proves that no schedule", "violation establishes that no schedule"),
    # 5.4 42 -> 135 (estimation-bias body)
    ("not through routing. Across the 42", "not through routing. Across the 135"),
    # 5.7b decision-divergence numbers, inserted into the mechanistic sentence
    ("rather than by optimal pre-planning. Supplying the same", divergence),
    # 5.11 worked lambda example before "First, what a model must capture..."
    ("First, what a model must capture is the network loss",
     lam + "First, what a model must capture is the network loss"),
]
for a, b in edits:
    n = t.count(a)
    if n and b not in t:
        t = t.replace(a, b, 1)
    print(f"  [{'EDIT' if n else 'MISS'}] {a[:48]}  (x{n})")

SK.write_text(t, encoding="utf-8")
