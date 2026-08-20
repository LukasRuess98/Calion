from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SP = ROOT / "docs/paper_1/submission_pack/01_latex_build"
sk = SP / "paper_source_skeleton.tex"
t = sk.read_text(encoding="utf-8")

# add \label to the subsections the section files cross-reference
adds = [
    (r"\subsection{Extended thermo-hydraulic formulation}",
     r"\subsection{Extended thermo-hydraulic formulation}\label{sec:extended}"),
    (r"\subsection{Validation}",
     r"\subsection{Validation}\label{subsec:validation}"),
    (r"\subsection{Copperplate with aggregate losses}",
     r"\subsection{Copperplate with aggregate losses}\label{subsec:lumped}"),
    (r"\subsection{Estimation bias: loss visibility versus spatial resolution}",
     r"\subsection{Estimation bias: loss visibility versus spatial resolution}\label{subsec:decomp}"),
]
for a, b in adds:
    if b not in t and a in t:
        t = t.replace(a, b, 1)
        print("labelled:", a[:45])
    else:
        print("skip:", a[:45])
sk.write_text(t, encoding="utf-8")

# fix table-ref mismatches in the section files (label defined elsewhere with a different key)
fixes = {"tab:val_targets": "tab:valtargets"}
for f in (SP / "sections").glob("*.tex"):
    ft = f.read_text(encoding="utf-8")
    orig = ft
    for a, b in fixes.items():
        ft = ft.replace(a, b)
    if ft != orig:
        f.write_text(ft, encoding="utf-8")
        print("ref-fixed in", f.name)
