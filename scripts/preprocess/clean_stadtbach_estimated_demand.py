"""Reconstruct ALL estimated Stadtbach consumer demand (energy-balance method).

WHY THIS EXISTS
---------------
`merge_acron_sb.py` estimates the 17 unmetered stations by distributing a
zone-total demand (from pump-station flow) across stations weighted by each
station's supply-return dT. That method produces two physically impossible
artefacts, both of which break the hydraulic (pressure/velocity) model:

  1. Netz-West summer inversion: Q_west = cp*PSW_flow*dT, and PSW pump flow is
     ~10.7x higher in August (recirculation) than January -> fake summer demand,
     corr(demand, outdoor_temp) flips POSITIVE.
  2. All-zone peak spikes: dividing a zone residual by a small per-station dT
     explodes individual-hour shares, giving estimated consumers peak/mean
     ratios of 6-8 (vs 2.7-3.9 for the metered ones) and peaks that exceed their
     real DN125-DN150 connection pipes for hundreds-to-thousands of hours
     (Josefinum peak 32 MW on a 4.9 MW pipe, Kreissparkasse 24 MW, ...). With a
     physical velocity cap (2.5 m/s) these flows are infeasible.

The 7 metered stations (direct Waermeleistung meters) are trustworthy and left
untouched. This script reconstructs the 17 estimated stations.

METHOD (user-approved 2026-07-09: energy-balance + pipe-capacity + temperature)
-------------------------------------------------------------------------------
1. total_production(t): sum of the 6 modeled Stadtbach producers (HKW, GT-Ost,
   BMHKW, HWW, AVA direct heat meters; Heizwerk-Sued via cp*flow*dT). All 6 have
   a connection pipe in Stadtbach_topo.yaml, so the balance is over the modeled
   network boundary. corr(total_production, outdoor_temp) = -0.83 (trustworthy).
   ASSUMPTION: all measured production is delivered to the 24 modeled consumers
   (the topology models these producers as feeding only this network).
2. estimated-demand residual (delivered heat):
      Q_est(t) = ( (1 - LOSS_FRAC) * total_production(t) - measured_7(t) ).clip(0)
   i.e. total delivered demand minus the metered consumers.
3. Distribute Q_est across the 17 estimated consumers by connection-pipe
   hydraulic capacity (pipe sized to peak demand -> capacity is the best
   available size proxy for an unmetered consumer). Every consumer inherits
   Q_est's temperature-correct hourly shape -> realistic peak/mean (~2.6),
   de-duplicated series, and uniform pipe utilisation < 100% (feasible for the
   velocity/pressure model by construction).

Reads pipe diameters straight from the topo so nothing is hard-coded. Writes
`stadtbach_acron_combined_cleaned.xlsx` (original kept for audit) and recomputes
the `Waermebedarf MW` total column.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
import yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ACR = ROOT / "data" / "Stadtbach" / "11_Messwerte_Acron"
TOPO = ROOT / "configs" / "stadtbach" / "Stadtbach_topo.yaml"
COMBINED_IN = ROOT / "data" / "Stadtbach" / "stadtbach_acron_combined.xlsx"
COMBINED_OUT = ROOT / "data" / "Stadtbach" / "stadtbach_acron_combined_cleaned.xlsx"

CP_J = 4186.0       # J/(kg K)
CP_FLOW = 1.163e-3  # MWh/(m3 K) for flow in m3/h
RHO = 971.8         # kg/m3 at ~80 C
V_DESIGN = 3.0      # m/s design velocity (matches max_velocity_m_s)
DT_DESIGN = 39.0    # K design supply-return (99/60)
LOSS_FRAC = 0.10    # generation->delivery network heat loss
MU = 3.5e-4         # dynamic viscosity of water ~80 C [Pa s]
# Round-trip pressure-head budget available to a leaf pipe (bar): producer setpoint
# (16) minus a return-pressure + trunk-share + safety allowance. The reconstruction
# weights are RELATIVE, so the exact value mainly sets the feasibility headroom.
PRESSURE_BUDGET_BAR = 11.0

TS = pd.date_range("2025-01-01", periods=8760, freq="h")

# 7 metered consumers (direct Waermeleistung) -- kept exactly as-is.
MEASURED = ["August-Wessels-Str_MW", "Klinikum_MW", "KUKA_MW", "Lechhauser_Str_MW",
            "MAN_MW", "SIGMA_Technopark_MW", "UNI_MW"]

# 17 estimated consumers -> their consumer node id in the topo (to look up the
# incoming connection pipe's diameter).
ESTIMATED = {
    "Fraunhofer_MW": "j_fraunhofer", "Josefinum_MW": "j_josefinum",
    "Kreissparkasse_MW": "j_kreissparkasse",
    "Hoher_Weg_MW": "j_hoher_weg", "Schlettererstr_MW": "j_schlettererstr",
    "Theodor-Heuss-Platz_MW": "j_theodor_heuss_platz",
    "Lise-Meitner-Str_MW": "j_lise_meitner_str",
    "Kurt-Schumacher-Str_MW": "j_kurt_schumacher_str",
    "Am_Mittleren_Moos_MW": "j_am_mittleren_moos", "Beethovenpark_MW": "j_beethovenpark",
    "Don_Bosco_MW": "j_don_bosco", "Fuggerstr_MW": "j_fuggerstr",
    "Grasiger_Weg_MW": "j_grasiger_weg", "Hans-Boeckler-Str_MW": "j_hans_boeckler_str",
    "Hooverstr_MW": "j_hooverstr", "Hunoldsgraben_MW": "j_hunoldsgraben",
    "Siegfried-Aufhaeuser-Str_MW": "j_siegfried_aufhaeuser_str",
}


def _read_acron(station: str, fname: str) -> pd.Series | None:
    fp = ACR / station / fname
    if not fp.exists():
        return None
    df = pd.read_excel(fp, skiprows=2, header=0)
    d = pd.to_datetime(df["Datum"]).dt.normalize()
    h = (df["Zeit"].astype(str).str.strip().str.split("-").str[0]
         .str.split(":").str[0].astype(int))
    s = pd.Series(pd.to_numeric(df["Wert"], errors="coerce").values,
                  index=d + pd.to_timedelta(h, unit="h")).groupby(level=0).first()
    return s.reindex(TS).ffill().bfill().fillna(0.0)


def total_production() -> pd.Series:
    prod = {}
    for st, fn in [("HKW", "HKW_Waermeleistung.xlsx"),
                   ("GT-Ost", "GT-Ost_Waermeleistung.xlsx"),
                   ("BMHKW", "BMHKW_Waermeleistung.xlsx"),
                   ("HWW_Kessel", "HWW_Waermeleistung_Kessel.xlsx"),
                   ("AVA", "AVA_Waermeleistung.xlsx")]:
        x = _read_acron(st, fn)
        if x is not None:
            prod[st] = x.clip(lower=0)
    flow = _read_acron("Heizwerk_Sued", "Heizwerk_Sued_Durchfluss.xlsx")
    tvl = _read_acron("Heizwerk_Sued", "Heizwerk_Sued_Temp_VL.xlsx")
    trl = _read_acron("Heizwerk_Sued", "Heizwerk_Sued_Temp_RL.xlsx")
    if flow is not None and tvl is not None and trl is not None:
        prod["HWS"] = (CP_FLOW * flow * (tvl - trl).clip(lower=0)).clip(lower=0)
    print("Producers (annual GWh):",
          {k: round(v.sum() / 1e3) for k, v in prod.items()})
    return sum(prod.values())


def _dp_1way_bar(diam_m: float, length_m: float, mdot: float, eps_m: float) -> float:
    """Darcy-Weisbach one-way pressure drop [bar] for a mass flow through a pipe."""
    area = np.pi * (diam_m / 2) ** 2
    v = mdot / (RHO * area)
    if v <= 0:
        return 0.0
    re = RHO * v * diam_m / MU
    f = 0.25 / (np.log10(eps_m / (3.7 * diam_m) + 5.74 / re ** 0.9)) ** 2
    return f * length_m / diam_m * RHO * v ** 2 / 2 / 1e5


def pipe_capacities() -> dict[str, float]:
    """Pressure-DELIVERABLE heat capacity [MW] of each estimated consumer.

    The earlier version weighted demand by pipe cross-section (velocity capacity ∝ D²),
    which ignores pipe LENGTH. Many Stadtbach leaves are long AND thin (e.g. Don_Bosco
    DN125/3490 m, Josefinum DN125/2070 m): their velocity capacity is fine but their
    *pressure*-deliverable capacity is a fraction of a short DN125, because Darcy Δp ∝ L.
    Distributing demand by cross-section therefore over-allocated heat to these consumers
    far beyond what the 16-bar producer setpoint can push through — the real source of the
    pressure infeasibility. Here the weight is the heat each consumer can actually receive
    within the round-trip head budget: bisect the mass flow so the summed Δp along the
    plant→consumer path (×2 for supply+return) equals PRESSURE_BUDGET_BAR, then convert to
    heat at the design ΔT. Also capped by the velocity limit (fat/short pipes).
    """
    from collections import deque
    net = yaml.safe_load(open(TOPO, encoding="utf-8"))["network"]
    pipes = net["pipes"]
    eps_m = net["pipe_roughness_mm"] / 1000.0
    primary = net.get("primary_producer", "j_hkw")
    # undirected adjacency: node -> [(neighbour, pipe_id)]
    adj: dict[str, list[tuple[str, str]]] = {}
    for pid, p in pipes.items():
        adj.setdefault(p["from"], []).append((p["to"], pid))
        adj.setdefault(p["to"], []).append((p["from"], pid))

    def path_to(dst: str) -> list[str]:
        q = deque([(primary, [])]); seen = {primary}
        while q:
            n, pp = q.popleft()
            if n == dst:
                return pp
            for nb, pid in adj.get(n, []):
                if nb not in seen:
                    seen.add(nb); q.append((nb, pp + [pid]))
        return []

    caps = {}
    for col, node in ESTIMATED.items():
        path = path_to(node)
        geom = [(pipes[pid]["diameter_mm"] / 1000.0, pipes[pid]["length_m"]) for pid in path]
        # bisect mdot so round-trip path Δp == budget
        lo, hi = 0.0, 500.0
        for _ in range(50):
            mid = (lo + hi) / 2
            dp = sum(2 * _dp_1way_bar(d, L, mid, eps_m) for d, L in geom)
            if dp > PRESSURE_BUDGET_BAR:
                hi = mid
            else:
                lo = mid
        mdot_press = lo
        # velocity cap on the consumer's own connection pipe (last on path)
        d_leaf = geom[-1][0] if geom else 0.1
        mdot_vel = RHO * V_DESIGN * np.pi * (d_leaf / 2) ** 2
        caps[col] = min(mdot_press, mdot_vel) * CP_J * DT_DESIGN / 1e6
    return caps


def main() -> None:
    df = pd.read_excel(COMBINED_IN)
    T = pd.to_numeric(df["outdoor_temp_C"], errors="coerce").values
    corr = lambda s: float(np.corrcoef(np.asarray(s, float), np.nan_to_num(T))[0, 1])
    m1, m8 = TS.month == 1, TS.month == 8

    tot = total_production().values
    measured = sum(pd.to_numeric(df[c], errors="coerce").fillna(0.0).values
                   for c in MEASURED)
    q_est = np.clip((1 - LOSS_FRAC) * tot - measured, 0.0, None)

    caps = pipe_capacities()
    cap_sum = sum(caps.values())
    print(f"\ntotal production   : {tot.sum()/1e3:.0f} GWh "
          f"(Jan {tot[m1].mean():.0f} / Aug {tot[m8].mean():.0f} MW peak {tot.max():.0f})")
    print(f"measured 7 (kept)  : {measured.sum()/1e3:.0f} GWh")
    print(f"estimated residual : {q_est.sum()/1e3:.0f} GWh  corr(temp)={corr(q_est):+.2f}  "
          f"peak {q_est.max():.0f} MW")
    print(f"\n{'consumer':30s} {'pipe_cap':>8} {'ann_GWh':>8} {'Jan':>6} {'Aug':>6} "
          f"{'pk/mn':>6} {'corr':>6} {'peak':>6} {'%pipe':>6}")
    for col, cap in sorted(caps.items(), key=lambda kv: -kv[1]):
        s = q_est * (cap / cap_sum)
        df[col] = s
        mean = s.mean()
        print(f"{col:30s} {cap:7.1f}  {s.sum()/1e3:7.1f} {s[m1].mean():6.2f} "
              f"{s[m8].mean():6.2f} {s.max()/mean:6.1f} {corr(s):+.2f} {s.max():6.1f} "
              f"{s.max()/cap*100:5.0f}%")

    all_cons = MEASURED + list(ESTIMATED.keys())
    total_demand = sum(pd.to_numeric(df[c], errors="coerce").fillna(0.0).values
                       for c in all_cons)
    dcol = [c for c in df.columns if "rmebedarf" in c]
    if dcol:
        df[dcol[0]] = total_demand

    df.to_excel(COMBINED_OUT, index=False)
    n_exceed = sum(int((pd.to_numeric(df[c]).values > caps[c]).sum()) for c in ESTIMATED)
    print(f"\nWROTE {COMBINED_OUT.name}")
    print(f"  total modeled demand: {total_demand.sum()/1e3:.0f} GWh  "
          f"(implied loss vs production: {(1-total_demand.sum()/tot.sum())*100:.0f}%)")
    print(f"  estimated-consumer hours over pipe capacity: {n_exceed} (must be 0)")


if __name__ == "__main__":
    main()
