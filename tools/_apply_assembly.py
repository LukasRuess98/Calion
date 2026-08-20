"""One-shot application of ASSEMBLY.md to the submission-pack skeleton.
Mechanical, reportable transforms only (marker->\\input wiring, section renames, front-matter
nomenclature, roadmap, and the unambiguous find/replace text edits). Complex insertions/reorders
are left for a content pass. Edits the SKELETON (never paper_COMPILE.tex)."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SK = ROOT / "docs/paper_1/submission_pack/01_latex_build/paper_source_skeleton.tex"
SEC = ROOT / "docs/paper_1/submission_pack/01_latex_build/sections"

# fix the one real \SI slip in a section file (ASSEMBLY.md §8)
rw = SEC / "related_work_v2.tex"
rw.write_text(rw.read_text(encoding="utf-8").replace(r"\SI{0.5}{\kelvin}", r"0.5\,K"), encoding="utf-8")

txt = SK.read_text(encoding="utf-8")
report = []


def line_replace(marker_substr, new_line, drop_next_if_contains=None):
    """Replace the whole line containing marker_substr with new_line; optionally also drop a
    following line that contains a given substring (for multi-line markers)."""
    global txt
    lines = txt.split("\n")
    out, i, done = [], 0, False
    while i < len(lines):
        if marker_substr in lines[i] and not done:
            out.append(new_line)
            done = True
            if drop_next_if_contains and i + 1 < len(lines) and drop_next_if_contains in lines[i + 1]:
                i += 1  # skip the continuation line
        else:
            out.append(lines[i])
        i += 1
    txt = "\n".join(out)
    report.append(("WIRE" if done else "MISS", marker_substr, new_line[:40]))


# --- §1 marker -> \input wiring ---
line_replace("<<KEEP:intro-motivation>>", r"\input{sections/introduction_opening_v2}")
line_replace("<<KEEP:rw-milp-topology>>", r"\input{sections/related_work_v2}")
line_replace("<<KEEP:objective>>", r"\input{sections/base_formulation_v2}", drop_next_if_contains="<<KEEP:storage>>")
line_replace("<<KEEP:pressure-drop>>", r"\input{sections/extended_physics_v2}")
line_replace("<<KEEP:stage1>>", r"\input{sections/validation_protocol_v2}")
line_replace("<<KEEP:implementation>>", r"\input{sections/computational_setup_v2}")
line_replace("<<KEEP:validation-results>>", r"\input{sections/validation_results_v2}")
line_replace("<<KEEP:computation>>", r"\input{sections/fidelity_vs_cost_v2}")
line_replace("<<KEEP:limitations-other>>", r"\input{sections/limitations_v2}")
line_replace("<<KEEP:cop>>", r"\input{sections/appendices_cited_v2}")
line_replace("<<KEEP:selling-price>>", r"\input{sections/appendices_optional_v2}")
line_replace("<<KEEP:nomenclature>>", r"%% [nomenclature moved to front matter after \\maketitle]")

# --- §3 front-matter nomenclature (after \maketitle) ---
if "\\input{sections/nomenclature_v2}" not in txt:
    txt = txt.replace("\\maketitle",
                      "\\maketitle\n\n\\section*{Nomenclature}\n\\input{sections/nomenclature_v2}", 1)
    report.append(("FRONT", "nomenclature after maketitle", ""))

# --- §2 section renames ---
renames = [
    (r"\section{Methodology}", r"\section{Experimental design and methodology}"),
    (r"\subsection{Fidelity ladder and decomposition controls}",
     r"\subsection{Experimental design: fidelity ladder and decomposition controls}"),
    (r"\subsection{Related work}", r"\subsection{Literature review and research gap}"),
    (r"\section{Case studies}", r"\subsection{Case studies and data}"),
    (r"\subsection{Memmingen}", r"\subsubsection{Memmingen}"),
    (r"\subsection{Synthetic factorial}", r"\subsubsection{Synthetic factorial}"),
]
for a, b in renames:
    n = txt.count(a)
    if n:
        txt = txt.replace(a, b)
    report.append(("RENAME" if n else "MISS", a, f"x{n}"))

# --- §4 roadmap paragraph (before the methodology section) ---
roadmap = (r"""The remainder of the paper is organised as follows.
Section~\ref{sec:methodology} sets out the experimental design -- the fidelity ladder, the
decomposition controls and the contrasts each isolates -- then the two case studies, the
formulations, the forward evaluator, the cost basis, the validation protocol and the
computational setup. Section~\ref{sec:results} reports and discusses the results in the
order of the research questions, beginning with what the measurements can and cannot
validate and ending with the limitations of the study.
Section~\ref{sec:conclusion} concludes.

""")
anchor = r"\section{Experimental design and methodology}"
if anchor in txt and "The remainder of the paper is organised" not in txt:
    txt = txt.replace(anchor, roadmap + anchor, 1)
    report.append(("ROADMAP", "inserted before methodology", ""))

# --- §5 unambiguous find/replace text edits ---
edits = [
    ("cheaper on the objective", "cheaper on operating cost"),           # 5.1
    ("no schedule could be more than one percent better proves",
     "no schedule could be more than one percent better establishes"),   # 5.8 (guarded form)
    (" proves that no schedule could be more than one percent better",
     " establishes that no schedule could be more than one percent better"),  # 5.8 alt
    ("omitted and that Reviewer~2 identified", "omitted"),               # 5.9
    ("which is the substance of the R2.4 reply", "rather than calibrated away"),
    ("nonlinear reference Reviewer~2 asked for", "nonlinear reference"),
    ("answers Reviewer~2's request for rigour", "bounds it rigorously"),
    ("artefact of the loss calibration R2.4 queried", "artefact of the loss calibration"),
    ("bias alone cannot give (R1.2):", "bias alone cannot give:"),
    ("Across the 42 synthetic networks", "Across the 135 synthetic networks"),  # 5.4 tail
]
for a, b in edits:
    n = txt.count(a)
    if n:
        txt = txt.replace(a, b)
    report.append(("EDIT" if n else "skip", a[:40], f"x{n}"))

SK.write_text(txt, encoding="utf-8")
for tag, a, b in report:
    print(f"  [{tag:7s}] {a}  {b}")
n_keep = len(re.findall(r"<<KEEP:", txt))
n_inp = txt.count("input{sections/")
print(f"\nremaining <<KEEP: markers: {n_keep}")
print(f"input-sections lines: {n_inp}")
