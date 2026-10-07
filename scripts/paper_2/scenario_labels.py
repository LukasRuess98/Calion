"""Single source of truth: internal scenario ID  <->  paper-facing semantic label.

WHY THIS FILE EXISTS
--------------------
Internal IDs (MM-S4-HK0, SB-S4-HK0, ...) are kept stable because ~15 scripts hardcode
them (figures, loaders, enumerators). But the internal scheme has a network-dependent
collision — MM-S4 = endogenous siting, SB-S4 = TES at Pumpstation Süd — so the IDs are
NOT safe to print in the paper. The manuscript uses the SEMANTIC labels below, and every
caption / table must resolve them through this ONE table. Keeping the mapping here (rather
than duplicating strings in DOE_TABLE.tex, gen_tables.py, figure captions, ...) prevents
the label/ID drift that already bit us once as j_1 vs j_9.

Regenerate DOE_TABLE.tex rows from `doe_rows()` so the table can never disagree with the
runner. `semantic_label("SB-S4-HK0") -> "FIX-REMOTE-A"`.

Factor levels per family (both networks identical unless a level is n.a.):
  invest   : none | HP+EK | TES | HP+EK+TES        (cumulative investment set)
  tes_site : - | central | at-HP | remote-A | remote-B | free
  charge   : - | normal | hot            (hot = HP charges at min(T_VL,max, 95°C ceiling))
  siting   : fixed | endogenous                      (L optimised?)
  coloc    : - | separate | co-located
"""
from __future__ import annotations

import re

# family key -> (semantic label, invest, tes_site, charge, siting, coloc, feeds)
# The family key is (network_or_"*", family_token). Network-specific first, "*" fallback.
FAMILIES: dict[tuple[str, str], dict] = {
    ("*",  "BC-TVLFIX"): dict(label="BASE-FIX",     invest="none",      tes_site="-",        charge="-",      siting="fixed",      coloc="-",          feeds="T3"),
    ("*",  "BC-HK0"):    dict(label="BASE-HK0",     invest="none",      tes_site="-",        charge="-",      siting="fixed",      coloc="-",          feeds="T3"),
    ("*",  "S0"):        dict(label="HP-ONLY",      invest="HP+EK",     tes_site="-",        charge="normal", siting="fixed",      coloc="-",          feeds="T3"),
    ("*",  "TESONLY"):   dict(label="TES-ONLY",     invest="TES",       tes_site="central",  charge="normal", siting="fixed",      coloc="-",          feeds="T3"),
    ("*",  "S1"):        dict(label="FIX-CENTRAL",  invest="HP+EK+TES", tes_site="central",  charge="normal", siting="fixed",      coloc="separate",   feeds="T3,F4"),
    ("*",  "S2"):        dict(label="FIX-HP",       invest="HP+EK+TES", tes_site="at-HP",    charge="normal", siting="fixed",      coloc="separate",   feeds="T3,F4"),
    ("*",  "S2-TVLFIX"): dict(label="FIX-HP-TVLFIX",invest="HP+EK+TES", tes_site="at-HP",    charge="normal", siting="fixed",      coloc="separate",   feeds="F3"),
    ("*",  "S3"):        dict(label="FIX-HP-HOT",   invest="HP+EK+TES", tes_site="at-HP",    charge="hot",    siting="fixed",      coloc="separate",   feeds="F3"),
    ("SB", "S4"):        dict(label="FIX-REMOTE-A", invest="HP+EK+TES", tes_site="remote-A", charge="normal", siting="fixed",      coloc="separate",   feeds="F4"),
    ("SB", "S5"):        dict(label="FIX-REMOTE-B", invest="HP+EK+TES", tes_site="remote-B", charge="normal", siting="fixed",      coloc="separate",   feeds="F4"),
    # FREE family: MM-S4 and SB-S6 are the SAME semantic level (endogenous, separate, normal)
    ("MM", "S4"):        dict(label="FREE",         invest="HP+EK+TES", tes_site="free",     charge="normal", siting="endogenous", coloc="separate",   feeds="F3,F4"),
    ("SB", "S6"):        dict(label="FREE",         invest="HP+EK+TES", tes_site="free",     charge="normal", siting="endogenous", coloc="separate",   feeds="F3,F4"),
    ("MM", "S4CO"):      dict(label="FREE-CO",      invest="HP+EK+TES", tes_site="free=HP",  charge="normal", siting="endogenous", coloc="co-located", feeds="F3,F4"),
    ("SB", "S6CO"):      dict(label="FREE-CO",      invest="HP+EK+TES", tes_site="free=HP",  charge="normal", siting="endogenous", coloc="co-located", feeds="F3,F4"),
    ("MM", "S5"):        dict(label="FREE-CO-HOT",  invest="HP+EK+TES", tes_site="free=HP",  charge="hot",    siting="endogenous", coloc="co-located", feeds="F3,F4"),
    ("SB", "S7"):        dict(label="FREE-CO-HOT",  invest="HP+EK+TES", tes_site="free=HP",  charge="hot",    siting="endogenous", coloc="co-located", feeds="F3,F4"),
}


def _parse(scenario_id: str) -> tuple[str, str]:
    """Return (network, family_token) for a raw scenario id.

    network is "MM" or "SB"; family_token keys into FAMILIES.
    """
    sid = scenario_id.upper()
    net = "MM" if sid.startswith("MM") or sid == "BC-MM" or sid.startswith("BC-MM") else \
          ("SB" if sid.startswith("SB") or sid.startswith("BC-SB") else "?")
    # Baselines
    if sid.startswith("BC"):
        return net, ("BC-HK0" if "HK0" in sid else "BC-TVLFIX")
    # Strip network prefix and trailing heat-curve token
    body = re.sub(r"^(MM|SB)-", "", sid)
    body = re.sub(r"-(HK[012]|TVLFIX)$", "", body) if not body.endswith("S2-TVLFIX") else body
    # Family tokens, longest/most-specific first
    for token in ("TESONLY", "S2-TVLFIX", "S4CO", "S6CO", "S0",
                  "S1", "S2", "S3", "S4", "S5", "S6", "S7"):
        if body == token or body.startswith(token + "-") or body == token:
            return net, token
    # S2-TVLFIX arrives as body "S2-TVLFIX"
    if body == "S2-TVLFIX":
        return net, "S2-TVLFIX"
    return net, body


def factors(scenario_id: str) -> dict:
    """Full factor record for a scenario id (raises KeyError if unmapped)."""
    net, token = _parse(scenario_id)
    rec = FAMILIES.get((net, token)) or FAMILIES.get(("*", token))
    if rec is None:
        raise KeyError(f"scenario_labels: no mapping for {scenario_id!r} (net={net}, token={token})")
    return dict(rec, network=net)


def semantic_label(scenario_id: str) -> str:
    """Paper-facing label, e.g. 'SB-S4-HK0' -> 'FIX-REMOTE-A'."""
    return factors(scenario_id)["label"]


def doe_rows() -> list[dict]:
    """Deduplicated family rows for regenerating DOE_TABLE.tex (semantic order)."""
    seen: dict[str, dict] = {}
    order: list[str] = []
    for (net, token), rec in FAMILIES.items():
        lab = rec["label"]
        if lab not in seen:
            seen[lab] = dict(rec, networks=set())
            order.append(lab)
        seen[lab]["networks"].add("MM" if net in ("*", "MM") else net)
        if net == "SB":
            seen[lab]["networks"].add("SB")
        if net == "*":
            seen[lab]["networks"].update({"MM", "SB"})
    return [seen[l] for l in order]


if __name__ == "__main__":
    # Self-check: every scenario in scenarios.yaml resolves to a label.
    import sys
    from pathlib import Path
    import yaml
    cfg = yaml.safe_load(open(Path(__file__).resolve().parents[2]
                              / "configs/paper_2/scenarios.yaml", encoding="utf-8"))
    bad = []
    for s in cfg["scenarios"]:
        try:
            print(f"{s['id']:20s} -> {semantic_label(s['id'])}")
        except KeyError as e:
            bad.append(str(e))
    if bad:
        print("\nUNMAPPED:", *bad, sep="\n  ")
        sys.exit(1)
    print(f"\nOK: all {len(cfg['scenarios'])} scenarios resolve to semantic labels.")
