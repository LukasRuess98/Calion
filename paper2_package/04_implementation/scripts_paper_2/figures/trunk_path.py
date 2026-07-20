"""F8 — algorithmic trunk-path derivation (spec F8, explicit "Arbeitsauftrag an
den Agenten": the representative trunk for the spatial T/p profile figure must
be derived algorithmically from the topology, not chosen by hand).

Per network, builds the weighted pipe graph from the topology YAML and finds
the hydraulically longest plant -> farthest-consumer path two ways:
  (a) max cumulative pipe length
  (b) max cumulative ΔT_pipe, using the SAME formula as the model's own
      spatial-temperature offset (scenario_runner._apply_spatial_temperature_offsets,
      Implementation Statement §A.4.3) so the F8 trunk numbers are consistent
      with what the model actually applies.

If several candidate paths are within 5% of the longest (by either metric),
ALL of them are listed — per spec, this script does not auto-pick one.

This is a PROPOSAL for user sign-off. It does not modify
`fig_p2_campaign.py::_TRUNK` (still hand-set) — wire the confirmed path in only
after the user has reviewed the printed candidates + the overview figure.

Usage:  python scripts/paper_2/figures/trunk_path.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import networkx as nx
import numpy as np
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _style  # noqa: E402

_ROOT = Path(__file__).resolve().parents[3]

NETWORKS = {
    "stadtbach": _ROOT / "configs" / "stadtbach" / "Stadtbach_topo.yaml",
    "memmingen": _ROOT / "configs" / "paper_2" / "Memmingen_P2_base.yaml",
}

# Physical constants and design-flow assumption — identical to
# scenario_runner._apply_spatial_temperature_offsets, so ΔT_pipe here matches
# the model's own injected T_supply_offset_c.
_CP = 4186.0        # J/(kg K)
_RHO = 971.8        # kg/m3 (~75 C)
_V_DESIGN = 1.0     # m/s representative design velocity


def _load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _pipe_drop_k(p: dict, T_avg: float, T_ground: float) -> float:
    L = float(p.get("length_m", 0.0) or 0.0)
    d_mm = float(p.get("diameter_mm", 0.0) or 0.0)
    U = float(p.get("u_value_supply_w_per_m_k", 0.32) or 0.32)
    if L <= 0 or d_mm <= 0:
        return 0.0
    A = np.pi / 4.0 * (d_mm / 1000.0) ** 2
    m_dot = max(_RHO * A * _V_DESIGN, 0.5)
    q_loss_w = U * L * max(T_avg - T_ground, 0.0)
    return q_loss_w / (m_dot * _CP)


def _build_graph(cfg: dict) -> nx.Graph:
    net = cfg.get("network", {})
    nodes = net.get("nodes", {}) or {}
    pipes = net.get("pipes", {}) or {}
    T_avg = float(net.get("supply_temp_c", 90.0))     # same fallback as the model uses
    T_ground = float(net.get("ground_temp_c", 10.0))
    G = nx.Graph()
    for n in nodes:
        G.add_node(n)
    for pid, p in pipes.items():
        u, v = p.get("from"), p.get("to")
        if not u or not v:
            continue
        G.add_edge(u, v, pipe=pid,
                   length_m=float(p.get("length_m", 0.0) or 0.0),
                   delta_t_k=_pipe_drop_k(p, T_avg, T_ground))
    return G


def _consumer_leaves(cfg: dict, G: nx.Graph) -> list[str]:
    """Degree-1 nodes that are actual demand endpoints (consumer or mixed)."""
    nodes = cfg.get("network", {}).get("nodes", {}) or {}
    leaves = [n for n in G.nodes() if G.degree(n) == 1
              and bool((nodes.get(n) or {}).get("consumers"))]
    return leaves or [n for n in G.nodes() if G.degree(n) == 1]


def _path_metrics(G: nx.Graph, path: list[str]) -> tuple[float, float]:
    length = sum(G[u][v]["length_m"] for u, v in zip(path, path[1:]))
    dT = sum(G[u][v]["delta_t_k"] for u, v in zip(path, path[1:]))
    return length, dT


def derive_trunk(network_key: str, cfg_path: Path) -> dict:
    cfg = _load_yaml(cfg_path)
    root = cfg.get("network", {}).get("primary_producer")
    G = _build_graph(cfg)
    if root not in G:
        raise ValueError(f"{network_key}: primary_producer {root!r} not found in graph")

    leaves = _consumer_leaves(cfg, G)
    candidates: list[dict] = []
    for leaf in leaves:
        # cheap: these networks have at most one cycle (Stadtbach's one
        # bidirectional trunk), so all_simple_paths never blows up
        for path in nx.all_simple_paths(G, root, leaf):
            length, dT = _path_metrics(G, path)
            candidates.append({"leaf": leaf, "path": path,
                               "length_m": length, "delta_t_k": dT})

    if not candidates:
        return {"network": network_key, "root": root,
                "candidates_by_length": [], "candidates_by_dT": []}

    max_len = max(c["length_m"] for c in candidates)
    max_dT = max(c["delta_t_k"] for c in candidates)
    by_length = sorted((c for c in candidates if c["length_m"] >= 0.95 * max_len),
                       key=lambda c: -c["length_m"])
    by_dT = sorted((c for c in candidates if c["delta_t_k"] >= 0.95 * max_dT),
                   key=lambda c: -c["delta_t_k"])
    return {"network": network_key, "root": root,
            "candidates_by_length": by_length, "candidates_by_dT": by_dT}


def _print_report(result: dict) -> None:
    print(f"\n=== {result['network']} (root={result['root']}) ===")
    print("-- candidates by cumulative pipe LENGTH (within 5% of the longest) --")
    for c in result["candidates_by_length"]:
        print(f"  {c['length_m']:8.0f} m   dT_pipe={c['delta_t_k']:.3f} K   "
              f"-> {' -> '.join(c['path'])}")
    print("-- candidates by cumulative delta_T_pipe (within 5% of the largest) --")
    for c in result["candidates_by_dT"]:
        print(f"  dT_pipe={c['delta_t_k']:.3f} K   {c['length_m']:8.0f} m   "
              f"-> {' -> '.join(c['path'])}")
    if len(result["candidates_by_length"]) > 1 or len(result["candidates_by_dT"]) > 1:
        print("  NOTE: multiple candidates within 5% - needs explicit user choice, "
              "not auto-picked.")


def _overview_figure(results: dict[str, dict]) -> None:
    """Small confirmation figure: the longest-by-length candidate trunk(s)
    highlighted on the same schematic layout used by F2."""
    import matplotlib.pyplot as plt

    import fig_f2_network_maps as f2  # reuse the existing layout/graph builders

    _style.apply_rcparams()
    fig, axes = plt.subplots(1, len(results), figsize=(_style.COL_DOUBLE_IN, 3.8),
                             squeeze=False)
    for ax, (net_key, result) in zip(axes[0], results.items()):
        cfg = f2._load_yaml(NETWORKS[net_key])
        G, roles, bidir = f2._build_graph(cfg)
        pos = None
        if net_key == "memmingen":
            pos = f2._metric_tree_layout(cfg, cfg.get("network", {}).get("primary_producer", "j_1"))
        if pos is None:
            pos = f2._layout(G)
        nx.draw_networkx_edges(G, pos, ax=ax, edge_color=_style.GRID, width=1.0)
        nx.draw_networkx_nodes(G, pos, ax=ax, node_size=16, node_color=_style.INK_MUTED)
        for c in result["candidates_by_length"]:
            path = c["path"]
            nx.draw_networkx_edges(G, pos, edgelist=list(zip(path, path[1:])), ax=ax,
                                   edge_color=_style.FHG_ORANGE, width=2.4, alpha=0.85)
            nx.draw_networkx_nodes(G, pos, nodelist=path, ax=ax, node_size=30,
                                   node_color=_style.FHG_ORANGE)
        n_cand = len(result["candidates_by_length"])
        ax.set_title(f"{net_key} — candidate trunk"
                     f"{'s' if n_cand > 1 else ''} by length (n={n_cand})", fontsize=9)
        ax.set_axis_off()
    fig.suptitle("F8 trunk-path candidates — FOR USER CONFIRMATION, not final",
                fontsize=10, y=1.02)
    _style.save(fig, "fig_F8_trunk_candidates_DRAFT")


def main() -> None:
    results = {}
    for net_key, cfg_path in NETWORKS.items():
        results[net_key] = derive_trunk(net_key, cfg_path)
        _print_report(results[net_key])
    try:
        _overview_figure(results)
    except Exception as exc:  # noqa: BLE001
        print(f"[SKIP] overview figure: {type(exc).__name__}: {exc}")
    print("\n>>> Candidates above are a PROPOSAL. Confirm the trunk per network "
          "before wiring into fig_p2_campaign.py's _TRUNK (currently hand-set). <<<")


if __name__ == "__main__":
    main()
