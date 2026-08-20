import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SK = ROOT / "docs/paper_1/submission_pack/01_latex_build/paper_source_skeleton.tex"
t = SK.read_text(encoding="utf-8")

# wrap each bare \input{sections/X} in \new{...}, except the author front matter
def repl(m):
    name = m.group(1)
    if name == "front_matter_v2":
        return m.group(0)
    return "\\new{\\input{sections/%s}}" % name

t = re.sub(r"(?<!\{)\\input\{sections/([a-z0-9_]+)\}", repl, t)
print("sections wrapped in \\new:", t.count("\\new{\\input{sections/"))

legend = (
    "\\ifmarkup\n\\begin{center}\\footnotesize\\fbox{\\parbox{0.9\\linewidth}{%\n"
    "\\textbf{Marked-up copy.} \\textcolor[HTML]{1A5FB4}{Blue} marks material new in this revision;\n"
    "\\textcolor[HTML]{0F7A5A}{green} marks text carried from the original submission and materially\n"
    "rewritten; \\textcolor[HTML]{9A9996}{grey} marks deletions we judged a reader would want flagged.\n"
    "Unmarked text is unchanged. Because the manuscript was restructured and the model levels renamed,\n"
    "marking is at paragraph rather than sentence granularity.}}\n\\end{center}\n\\fi\n")
if "Marked-up copy." not in t:
    t = t.replace("\\maketitle", "\\maketitle\n\n" + legend, 1)
    print("legend inserted")

SK.write_text(t, encoding="utf-8")
