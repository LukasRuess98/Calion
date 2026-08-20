from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SP = ROOT / "docs/paper_1/submission_pack/01_latex_build"
SK = SP / "paper_source_skeleton.tex"
t = SK.read_text(encoding="utf-8")

BOUND = (r"$\pm$0.6\,\% on every network of 5\,km trunk length or more, never exceeding "
         r"2.4\,\% even on the shortest, where the entire gap is below 6\,\% of cost")

edits = [
    # §1/§2/§3 conditional topology bound (3 places; drops the \result macro for the literal claim)
    (r"$\pm\result{synth_topo_absmax}$\,\% on every network. The distinction",
     BOUND + r". The distinction"),
    (r"within $\pm\result{synth_topo_absmax}$\,\% on \emph{every} network",
     "within " + BOUND),
    (r"effect stays within $\pm\result{synth_topo_absmax}$\,\% on every network,",
     r"effect stays within " + BOUND + r","),
    # §8: drop the heating-curve marker (keep l2-zones)
    ("%% <<KEEP:heating-curve>> <<KEEP:l2-zones>>  -- assets in Zone A (j1)",
     "%% <<KEEP:l2-zones>>  -- assets in Zone A (j1)"),
]
for a, b in edits:
    n = t.count(a)
    if n:
        t = t.replace(a, b, 1)
    print(f"  [{'EDIT' if n else 'MISS'}] {a[:52]}  (x{n})")
SK.write_text(t, encoding="utf-8")

# fix the bibtex parse error: a commented author line inside an entry
bib = SP / "paper1_dh_fidelity/Paper20_Literatur.bib"
bt = bib.read_text(encoding="utf-8", errors="replace")
before = bt.count("%  author  = {Mancarella")
bt = bt.replace("%  author  = {Mancarella, P.},\n", "").replace("%  author  = {Mancarella, P.},", "")
bib.write_text(bt, encoding="utf-8")
print(f"  [BIB] removed commented Mancarella author line (x{before})")
