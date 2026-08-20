from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SK = ROOT / "docs/paper_1/submission_pack/01_latex_build/paper_source_skeleton.tex"
t = SK.read_text(encoding="utf-8")


def fig(path, cap, lab):
    return ("\\begin{figure}[t]\n  \\centering\n"
            f"  \\includegraphics[width=\\linewidth]{{{path}}}\n"
            f"  \\caption{{{cap}}}\n  \\label{{{lab}}}\n\\end{{figure}}")


F_decomp = fig("figures/F_decomp",
    "Exact decomposition of the copperplate-to-baseline cost gap into a loss main effect, a "
    "spatial-topology main effect and their interaction, for Memmingen (left) and as a distribution "
    "across the 135 synthetic networks (right). The additive identity closes to machine precision, so "
    "the three terms are measured rather than fitted.", "fig:decomp")

F_regret = fig("figures/F_regret",
    "Estimation bias against decision regret for every level, as a percentage of the baseline operating "
    "cost. For the copperplate and the topology-only control the two carry \\emph{opposite signs}: a "
    "schedule that appears cheaper on paper is markedly more expensive to execute. Loss-aware levels "
    "show regret approximately equal to bias.", "fig:regret")

F_val = "\n\n".join([
    fig("figures/validation/stage1_scatter_Tsupply_farend",
        "Simulated against measured supply temperature at the network far end, evaluated on the "
        "temperature-propagating formulation. The residuals are almost entirely one-signed -- the mean "
        "absolute error and the bias coincide -- the signature of a fixed instrument offset rather than "
        "model error: the sensor sits downstream of a three-way mixing valve.", "fig:val_farend"),
    fig("figures/validation/mixing_valve_offset",
        "The mixing-valve offset that bounds what the temperature field can be validated against. "
        "Consumer sensors are billing instruments installed downstream of the valve, so the metered "
        "temperature sits systematically below the primary junction temperature.", "fig:mixingvalve"),
    fig("figures/validation/spatial_profile_test",
        "Spatial temperature profile along the network. Nodes used in the loss calibration are shown "
        "separately from those that were not, so the comparison is not read as an in-sample fit.",
        "fig:val_spatial"),
])

F_drift = fig("figures/F_drift",
    "Drift of a frozen loss adder against trunk pipe length across the 135 synthetic networks. An adder "
    "calibrated on any one network mis-estimates the loss burden on others by a mean of 23.5 and up to "
    "40.1 percentage points of cost, which is why the node-resolved model -- computing the loss "
    "endogenously -- is the transferable one.", "fig:drift")

F_tsup = fig("figures/F_tsup",
    "Supply-temperature flexibility. Lowering the plant supply temperature reduces thermal loss but "
    "shrinks the temperature difference, so flow and pumping rise. The cost-optimal reduction is "
    "17.5\\,K; beyond 20\\,K the pipe velocity limit binds, and hydraulics change from a negligible cost "
    "into the binding constraint.", "fig:tsup")

repl = [
    ("%% Figure F6(a,b)", F_decomp),
    ("%% Figure F6(c)", F_regret),
    ("%% Figures F3, F4, F5, F11", F_val),
    ("%% Figures F_drift, F7, F8, F15", F_drift),
    ("%% Figure F12", F_tsup),
]
for marker, block in repl:
    lines = t.split("\n")
    for i, ln in enumerate(lines):
        if marker in ln:
            lines[i] = block
            t = "\n".join(lines)
            print(f"  [WIRE] {marker}")
            break
    else:
        print(f"  [MISS] {marker}")

SK.write_text(t, encoding="utf-8")
