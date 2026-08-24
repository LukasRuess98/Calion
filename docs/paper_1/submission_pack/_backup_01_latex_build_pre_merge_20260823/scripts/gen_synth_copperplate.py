"""
gen_synth_copperplate.py
========================
Generates copperplate (single-node, no-network) L1 YAML variants for every
synthetic config in synth_configs/.

For each  synth_XXXX.yaml  →  synth_XXXX_L1cp.yaml

The copperplate variant:
  - Single node  j_1  with demand_fraction=1.0
  - All assets from all original nodes moved to j_1
  - No pipes
  - Physics: heat_loss=False, pressure_drop=False, transport_delay=False
  - scenario.name updated with "(L1-copperplate)"

Output: synth_configs/  (same directory, _L1cp suffix)

Usage:
    python tools/gen_synth_copperplate.py
    python tools/gen_synth_copperplate.py --dry-run
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

try:
    import yaml
except ImportError:
    print("[ERROR] PyYAML not installed. Run: pip install pyyaml")
    sys.exit(1)


def _collect_assets(nodes: dict) -> list[str]:
    """Collect all asset references across all nodes."""
    seen, result = set(), []
    for ndata in nodes.values():
        for a in ndata.get("assets", []):
            if a not in seen:
                seen.add(a)
                result.append(a)
    return result


def _make_copperplate(cfg: dict, stem: str) -> dict:
    """Return a new config dict with copperplate topology."""
    import copy
    cp = copy.deepcopy(cfg)

    net = cp.setdefault("network", {})
    nodes_orig = net.get("nodes", {})

    # Collect all assets from all nodes
    all_assets = _collect_assets(nodes_orig)

    # Single copperplate node — demand_fraction=1.0 (all demand)
    cp_node: dict = {"consumers": [{"column": None, "demand_fraction": 1.0}]}
    if all_assets:
        cp_node["assets"] = all_assets

    # Find the demand column used (should be same for all consumers)
    col = None
    for ndata in nodes_orig.values():
        for cons in ndata.get("consumers", []):
            if "column" in cons:
                col = cons["column"]
                break
        if col:
            break
    if col:
        cp_node["consumers"][0]["column"] = col
    else:
        cp_node["consumers"][0].pop("column", None)
        cp_node["consumers"][0]["demand_fraction"] = 1.0

    # Replace topology
    net["nodes"] = {"j_1": cp_node}
    net.pop("pipes", None)

    # Disable all network physics
    net.setdefault("physics", {})
    net["physics"].update({
        "heat_loss":       False,
        "pressure_drop":   False,
        "transport_delay": False,
    })

    # Update scenario name
    scen = cp.setdefault("scenario", {})
    scen["name"] = scen.get("name", stem) + " (L1-copperplate)"

    return cp


def main(dry_run: bool = False) -> None:
    synth_dir = ROOT / "synth_configs"
    configs = sorted(synth_dir.glob("synth_*.yaml"))

    # Exclude already-generated copperplate files
    configs = [p for p in configs if "_L1cp" not in p.stem]

    if not configs:
        print(f"[WARN] No synth_*.yaml found in {synth_dir}")
        return

    print(f"Generating copperplate variants for {len(configs)} configs"
          f"{'  [DRY RUN]' if dry_run else ''}")

    created = 0
    for src in configs:
        with open(src, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)

        cp_cfg = _make_copperplate(cfg, src.stem)
        out_path = synth_dir / f"{src.stem}_L1cp.yaml"

        if dry_run:
            nodes = list(cp_cfg["network"]["nodes"].keys())
            pipes = list(cp_cfg["network"].get("pipes", {}).keys())
            phys  = cp_cfg["network"]["physics"]
            print(f"  [DRY] {out_path.name}  nodes={nodes}  pipes={pipes}  physics={phys}")
        else:
            class _IndentedDumper(yaml.Dumper):
                def increase_indent(self, flow=False, **_):
                    return super().increase_indent(flow=flow, indentless=False)

            out_path.write_text(
                yaml.dump(cp_cfg, Dumper=_IndentedDumper, allow_unicode=True,
                          default_flow_style=False, sort_keys=False),
                encoding="utf-8",
            )
            created += 1

    if not dry_run:
        print(f"  Created {created} copperplate configs in {synth_dir}")
        print("  Next step:")
        print("    python tools/run_synth_copperplate.py")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
