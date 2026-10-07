"""F2 — Case-study network maps (2 panels).

Panel A Stadtbach (meshed), Panel B Memmingen (radial). Node role is encoded by
shape + colour + selective label (never colour alone — dataviz secondary
encoding); TES candidate sites S1–S5 are ringed in Fraunhofer green and tagged,
the WP/EK site is a blue triangle, producers are dark squares.

No geographic coordinates exist in the configs, so a schematic graph layout
(Kamada–Kawai, spring fallback) is used — the spec explicitly permits this.
Topology (which node connects to which) is exact; absolute positions are not
geographic.

Usage:  python scripts/paper_2/figures/fig_f2_network_maps.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.lines as mlines
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _style  # noqa: E402

_ROOT = Path(__file__).resolve().parents[3]
SCENARIOS_YAML = _ROOT / "configs" / "paper_2" / "scenarios.yaml"

NETWORKS = {
    "stadtbach": {
        "title": "Stadtbach — 32 nodes, meshed",
        "config": _ROOT / "configs" / "stadtbach" / "Stadtbach_topo.yaml",
    },
    "memmingen": {
        "title": "Memmingen — 15 nodes, radial (real pipe lengths)",
        "config": _ROOT / "configs" / "paper_2" / "Memmingen_P2_base.yaml",
    },
}

# Short, human-readable labels for the nodes we annotate (producers, WP, TES).
SHORT = {
    "j_hkw": "HKW", "j_gtost": "GT-Ost", "j_bmhkw": "BM-HKW", "j_ava": "AVA",
    "j_pss": "PS-Süd", "j_psw": "PS-West", "j_hws": "HW-Süd", "j_hww": "HW-West",
    "j_man": "MAN", "j_ost": "Ost",
    "j_1": "Zentrale", "j_12": "Abwärme", "j_3": "j_3", "j_5": "j_5",
    "j_9": "j_9", "j_13": "j_13",
}


_HALO = dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.72)


def _load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _node_role(spec: dict) -> str:
    spec = spec or {}
    has_a, has_c = bool(spec.get("assets")), bool(spec.get("consumers"))
    if has_a and has_c:
        return "mixed"
    if has_a:
        return "producer"
    if has_c:
        return "consumer"
    return "junction"


def _build_graph(cfg: dict):
    import networkx as nx
    G = nx.Graph()
    roles = {}
    for nid, spec in (cfg.get("network", {}).get("nodes", {}) or {}).items():
        roles[nid] = _node_role(spec)
        G.add_node(nid)
    bidir = set()
    for pid, p in (cfg.get("network", {}).get("pipes", {}) or {}).items():
        u, v = p.get("from"), p.get("to")
        if u and v:
            G.add_edge(u, v)
            if p.get("bidirectional"):
                bidir.add((u, v))
    return G, roles, bidir


def _layout(G):
    import networkx as nx
    try:
        return nx.kamada_kawai_layout(G)          # cleanest for small graphs
    except Exception:
        return nx.spring_layout(G, seed=42, k=0.9)  # deterministic fallback


def _metric_tree_layout(cfg: dict, root: str, fan_deg: float = 250.0):
    """Radial tree layout where radial distance = real cumulative pipe length.

    The Memmingen DXF has no per-model-node coordinates (only raw polylines +
    generic shafts), but the pipe *lengths* are DXF-calibrated — so a radial
    tree rooted at the Zentrale, with radius = cumulative real length and
    leaf-proportional angular spread, is geographic in the metric sense
    (relative distances are real) without inventing false UTM positions.
    """
    import math
    from collections import deque

    import networkx as nx
    G = nx.Graph()
    length: dict[tuple[str, str], float] = {}
    for p in (cfg.get("network", {}).get("pipes", {}) or {}).values():
        u, v = p.get("from"), p.get("to")
        if u and v:
            G.add_edge(u, v)
            length[(u, v)] = length[(v, u)] = float(p.get("length_m", 100.0))
    for n in (cfg.get("network", {}).get("nodes", {}) or {}):
        G.add_node(n)
    if root not in G or not nx.is_connected(G):
        return None

    parent = {root: None}
    order = [root]
    dq = deque([root])
    while dq:
        u = dq.popleft()
        for w in sorted(G.neighbors(u)):
            if w not in parent:
                parent[w] = u
                order.append(w)
                dq.append(w)
    children: dict[str, list[str]] = {n: [] for n in order}
    for n in order:
        if parent[n] is not None:
            children[parent[n]].append(n)
    leaves: dict[str, int] = {}
    for n in reversed(order):
        leaves[n] = 1 if not children[n] else sum(leaves[c] for c in children[n])
    radius = {root: 0.0}
    for n in order:
        if parent[n] is not None:
            radius[n] = radius[parent[n]] + length.get((parent[n], n), 100.0)

    ang: dict[str, float] = {}
    span = {root: (math.radians(-fan_deg / 2), math.radians(fan_deg / 2))}

    def assign(n):
        lo, hi = span[n]
        ang[n] = (lo + hi) / 2
        kids = children[n]
        if kids:
            total = sum(leaves[c] for c in kids)
            cur = lo
            for c in kids:
                w = (hi - lo) * (leaves[c] / total)
                span[c] = (cur, cur + w)
                cur += w
                assign(c)

    assign(root)
    return {n: (radius[n] * math.sin(ang[n]), radius[n] * math.cos(ang[n]))
            for n in order}


_ROLE_STYLE = {
    "producer": dict(marker="s", s=70, c=_style.INK_SOFT, ec="white", lw=0.6, z=3),
    "mixed":    dict(marker="s", s=90, c=_style.INK, ec="white", lw=0.6, z=3),
    "consumer": dict(marker="o", s=26, c="#c9c7c2", ec="white", lw=0.4, z=2),
    "junction": dict(marker="o", s=14, c=_style.INK_MUTED, ec="none", lw=0, z=2),
}


def _panel(ax, net_key: str, scen_cfg: dict) -> None:
    cfg = _load_yaml(NETWORKS[net_key]["config"])
    G, roles, bidir = _build_graph(cfg)
    # Memmingen: geographic-metric radial tree (real DXF-calibrated pipe lengths);
    # Stadtbach (meshed, no length-consistent coords): schematic Kamada–Kawai.
    pos = None
    if net_key == "memmingen":
        pos = _metric_tree_layout(cfg, cfg.get("network", {}).get("primary_producer", "j_1"))
    if pos is None:
        pos = _layout(G)

    import networkx as nx
    # edges — grey; bidirectional trunk thicker + darker
    normal = [e for e in G.edges() if e not in bidir and (e[1], e[0]) not in bidir]
    nx.draw_networkx_edges(G, pos, edgelist=normal, ax=ax,
                           edge_color=_style.GRID, width=1.1)
    if bidir:
        nx.draw_networkx_edges(G, pos, edgelist=list(bidir), ax=ax,
                               edge_color=_style.INK_SOFT, width=2.2)

    # nodes by role
    for role, st in _ROLE_STYLE.items():
        pts = [n for n in G.nodes() if roles.get(n) == role]
        if not pts:
            continue
        ax.scatter([pos[n][0] for n in pts], [pos[n][1] for n in pts],
                   marker=st["marker"], s=st["s"], c=st["c"],
                   edgecolors=st["ec"], linewidths=st["lw"], zorder=st["z"])

    # WP/EK site (blue triangle)
    hp_map = scen_cfg.get("hp_nodes", {}).get(net_key, {})
    wp_node = next(iter(hp_map.values()), None)
    if wp_node and wp_node in pos:
        ax.scatter(*pos[wp_node], marker="^", s=150, c=_style.FHG_BLUE,
                   edgecolors="white", linewidths=0.8, zorder=5)

    # TES candidate sites (green ring + S# tag), de-duplicated by node
    tes_map = scen_cfg.get("tes_nodes", {}).get(net_key, {})
    seen: dict[str, list[str]] = {}
    for s_id, node in tes_map.items():
        seen.setdefault(node, []).append(s_id)
    for node, s_ids in seen.items():
        if node not in pos:
            continue
        ax.scatter(*pos[node], marker="o", s=230, facecolors="none",
                   edgecolors=_style.FHG_GREEN, linewidths=2.0, zorder=6)
        # S# sits directly ABOVE its own ring (centred) so it can never be read
        # as belonging to a neighbouring node when the layout packs sites close.
        ax.annotate("/".join(sorted(s_ids)), pos[node],
                    textcoords="offset points", xytext=(0, 15), ha="center",
                    fontsize=7.5, fontweight="bold", color=_style.FHG_GREEN,
                    zorder=8, bbox=_HALO)

    # labels for the nodes worth naming (producers, mixed, WP, TES sites)
    to_label = {n for n in G.nodes() if roles.get(n) in ("producer", "mixed")}
    to_label |= set(seen) | ({wp_node} if wp_node else set())
    for n in to_label:
        if n in pos:
            ax.annotate(SHORT.get(n, n), pos[n], textcoords="offset points",
                        xytext=(0, -12), ha="center", fontsize=6.6,
                        color=_style.INK, zorder=7, bbox=_HALO)

    ax.set_title(NETWORKS[net_key]["title"], fontsize=9.5, pad=6)
    ax.set_axis_off()
    ax.margins(0.12)


def build_f2() -> None:
    print("F2 — network maps:")
    try:
        import networkx  # noqa: F401
    except ImportError:
        print("  [SKIP] F2 needs networkx — pip install networkx")
        return
    _style.apply_rcparams()
    scen_cfg = _load_yaml(SCENARIOS_YAML)

    fig, axes = plt.subplots(1, 2, figsize=(_style.COL_DOUBLE_IN, 3.7))
    _panel(axes[0], "stadtbach", scen_cfg)
    _panel(axes[1], "memmingen", scen_cfg)

    # shared legend
    handles = [
        mlines.Line2D([], [], marker="s", ls="none", ms=8, mfc=_style.INK,
                      mec="white", label="Producer / mixed node"),
        mlines.Line2D([], [], marker="o", ls="none", ms=6, mfc="#c9c7c2",
                      mec="white", label="Consumer node"),
        mlines.Line2D([], [], marker="o", ls="none", ms=4, mfc=_style.INK_MUTED,
                      mec="none", label="Junction"),
        mlines.Line2D([], [], marker="^", ls="none", ms=11, mfc=_style.FHG_BLUE,
                      mec="white", label="WP/EK site"),
        mlines.Line2D([], [], marker="o", ls="none", ms=12, mfc="none",
                      mec=_style.FHG_GREEN, mew=2, label="TES candidate site (S1–S5)"),
        mlines.Line2D([], [], color=_style.INK_SOFT, lw=2.2,
                      label="Bidirectional trunk"),
    ]
    fig.legend(handles=handles, loc="lower center", ncol=3, fontsize=7.5,
               bbox_to_anchor=(0.5, -0.02))
    fig.suptitle("District-heating case-study networks and TES candidate sites",
                 fontsize=10.5, y=1.0)
    fig.subplots_adjust(bottom=0.12, wspace=0.05)
    _style.save(fig, "fig_F2_network_maps")


if __name__ == "__main__":
    build_f2()
