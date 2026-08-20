import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SK = ROOT / "docs/paper_1/submission_pack/01_latex_build/paper_source_skeleton.tex"
t = SK.read_text(encoding="utf-8")

# front matter (author block) before \maketitle -- the skeleton has no \author
if "input{sections/front_matter_v2}" not in t:
    t = t.replace("\\maketitle", "\\input{sections/front_matter_v2}\n\n\\maketitle", 1)
    print("front_matter_v2 wired before \\maketitle")

# conclusions: replace the single-block prose (between the section header and Acknowledgments)
pat = re.compile(r"(\\section\{Conclusions\}[^\n]*\n)(.*?)(\n\\section\*\{Acknowledgments\})", re.DOTALL)
def repl(m):
    hdr = m.group(1)
    if "label{sec:conclusion}" not in hdr:
        hdr = hdr.rstrip("\n") + "\\label{sec:conclusion}\n"
    return hdr + "\\input{sections/conclusions_v2}\n" + m.group(3)
t, n = pat.subn(repl, t, count=1)
print(f"conclusions_v2 wired (block replaced: {n})")

SK.write_text(t, encoding="utf-8")
