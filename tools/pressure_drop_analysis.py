"""
Post-hoc Darcy-Weisbach pressure drop analysis for Stadtbach BC-SB at peak demand.

Since pressure_drop: false in the YAML, dp_Pa = 0 in all model outputs.
This script computes analytical pressure drops from:
  - pipe geometry (pipes.csv)
  - mass flows derived from per-node demand at t=1135 (peak: Feb 17 07:00)
  - node supply temperatures (node_temperatures.csv)
"""

import pandas as pd
import numpy as np

# ─── Pipe topology (corrected DNs from WV640/WV660 PDFs, updated 2026-06-20) ─
# Sources: WV640 Bl.3 (pump circulation data), WV660 armature table
corrected_pipes = {
    # pipe_id: (length_m, diameter_mm)
    # BACKBONE
    "hkw_to_pps":              (1000, 400),  # DN400 — carries south zone total
    "hkw_to_psw":              ( 800, 400),  # DN400 — carries west zone total
    # SOUTH zone backbone
    "pps_to_hws":              ( 600, 400),  # DN400 — PSS pump 858 m3/h (WV640)
    "bmhkw_to_pps":            ( 400, 200),  # DN200 — BMHKW 14.5 MW max
    # WEST zone backbone
    "psw_to_hww":              ( 700, 350),  # DN350 — PSW pump 700 m3/h (WV640)
    # NETZ-MITTE spurs from j_hkw
    "hkw_to_klinikum":         ( 300, 250),  # DN250 — UKA large hospital
    "hkw_to_uni":              ( 500, 200),  # DN200 — university campus
    "hkw_to_kuka":             ( 900, 200),  # DN200 — KUKA industrial
    "hkw_to_man":              (1100, 200),  # DN200 — MAN industrial
    "hkw_to_sigma":            ( 700, 200),  # DN200 — SIGMA Technopark (upgraded)
    "hkw_to_fraunhofer":       ( 600, 200),  # DN200 — Fraunhofer (upgraded from DN150)
    "hkw_to_josefinum":        ( 450, 200),  # DN200 — Josefinum hospital (upgraded from DN125!)
    "hkw_to_kreissparkasse":   ( 350, 200),  # DN200 — Kreissparkasse (upgraded from DN125!)
    # NETZ-SUD spurs
    "pps_to_hoher_weg":        ( 500, 150),  # DN150
    "pps_to_kurt_schumacher":  ( 600, 200),  # DN200 — (upgraded from DN125!)
    "hws_to_schlettererstr":   ( 400, 200),  # DN200 — (upgraded from DN150)
    "hws_to_theodor_heuss":    ( 350, 150),  # DN150 — (upgraded from DN125)
    "hws_to_lise_meitner":     ( 650, 150),  # DN150 — (upgraded from DN125)
    "hws_to_lechhauser":       ( 850, 125),  # DN125 — ACRON measured ~2 MW, OK
    # NETZ-WEST spurs from j_hww
    "hww_to_grasiger_weg":     ( 400, 200),  # DN200 — WV660 armature 797.1 = DN200
    "hww_to_hooverstr":        ( 550, 250),  # DN250 — WV660 armature 620.1 = DN250
    "hww_to_hunoldsgraben":    ( 700, 150),  # DN150
    "hww_to_beethovenpark":    ( 800, 200),  # DN200 — (upgraded from DN150)
    "hww_to_am_mittleren_moos":( 1000, 150), # DN150 — (upgraded from DN125)
    "hww_to_don_bosco":        ( 900, 150),  # DN150 — (upgraded from DN125)
    # NETZ-WEST spurs from j_psw
    "psw_to_siegfried_aufhaeuser":( 500, 200), # DN200 — WV660 armature 850.1 = DN200
    "psw_to_hans_boeckler":    ( 400, 200),  # DN200 — WV660 armature 816.1 = DN200
    "psw_to_august_wessels":   ( 650, 150),  # DN150 — WV660 armature 850.3 = DN150
    "psw_to_fuggerstr":        ( 550, 250),  # DN250 — WV660 armature 613.1 = DN250
}

pipe_L = {k: v[0] for k, v in corrected_pipes.items()}
pipe_D = {k: v[1] / 1000 for k, v in corrected_pipes.items()}

print(f"Pipes in topology: {len(pipe_D)} (using corrected DNs from WV640/WV660)")

# ─── Load demand data ─────────────────────────────────────────────────────────
demand_file = "data/Stadtbach/stadtbach_acron_combined.xlsx"
df_d = pd.read_excel(demand_file, index_col=0)

# ─── Node temperatures ────────────────────────────────────────────────────────
nt = pd.read_csv("output/paper2_runs/BC-SB/node_temperatures.csv", index_col=0)

T_ret_C = 60.0    # return temp (°C, from config)
cp      = 4.18    # kJ/(kg·K)
rho     = 960.0   # kg/m³ (water at ~100°C)
nu      = 0.3e-6  # kinematic viscosity m²/s (water at ~100°C)
eps     = 0.05e-3 # pipe roughness 0.05 mm (DN steel/concrete)

# ─── Peak timestep (t=1135 in 1-based MILP = index 1134) ─────────────────────
t_idx = 1134
T_sup_row = nt.iloc[t_idx]
D_row    = df_d.iloc[t_idx]

# Supply temperature at each node
T_sup = {}
for col in T_sup_row.index:
    node = col.replace("T_node_", "")
    T_sup[node] = float(T_sup_row[col])

print("\nSupply temperatures at key nodes (t=1135, peak demand):")
for n in ["j_hkw", "j_pps", "j_hws", "j_hww", "j_psw", "j_bmhkw"]:
    print(f"  {n}: {T_sup.get(n, '?'):.1f} °C")

# ─── Per-consumer demand at t=1135 ───────────────────────────────────────────
# Column format: {StationName}_MW  →  node j_{station_name_lower}
demand = {}
for col in df_d.columns:
    if col.endswith("_MW"):
        node_key = "j_" + col[:-3].lower().replace("-", "_").replace(" ", "_")
        demand[node_key] = float(D_row[col])

print(f"\nPeak demand total (sum consumers): {sum(demand.values()):.1f} MW")

# ─── Pipe → carried load (MW) at t=1135 ──────────────────────────────────────
# Tree network: pipe load = sum of all downstream consumer demands
south_leaves = [
    "j_hoher_weg", "j_kurt_schumacher_str", "j_schlettererstr",
    "j_theodor_heuss_platz", "j_lise_meitner_str", "j_lechhauser_str",
]
hws_leaves = [
    "j_schlettererstr", "j_theodor_heuss_platz", "j_lise_meitner_str", "j_lechhauser_str",
]
hww_leaves = [
    "j_grasiger_weg", "j_hooverstr", "j_hunoldsgraben",
    "j_beethovenpark", "j_am_mittleren_moos", "j_don_bosco",
]
psw_direct = [
    "j_august_wessels_str", "j_fuggerstr",
    "j_hans_boeckler_str", "j_siegfried_aufhaeuser_str",
]
west_leaves = hww_leaves + psw_direct

def Q(nodes):
    return sum(demand.get(n, 0.0) for n in nodes)

pipe_Q_MW = {
    # Direct Mitte spurs from j_hkw
    "hkw_to_klinikum":       demand.get("j_klinikum", 0),
    "hkw_to_uni":            demand.get("j_uni", 0),
    "hkw_to_kuka":           demand.get("j_kuka", 0),
    "hkw_to_man":            demand.get("j_man", 0),
    "hkw_to_fraunhofer":     demand.get("j_fraunhofer", 0),
    "hkw_to_sigma":          demand.get("j_sigma_technopark", 0),
    "hkw_to_josefinum":      demand.get("j_josefinum", 0),
    "hkw_to_kreissparkasse": demand.get("j_kreissparkasse", 0),
    # Backbone to south (HKW → PPS → south zone)
    "hkw_to_pps":            Q(south_leaves + ["j_hoher_weg", "j_kurt_schumacher_str"]),
    "bmhkw_to_pps":          0.0,  # BMHKW not dispatched at t=1135 (see pipe_state)
    "pps_to_hoher_weg":      demand.get("j_hoher_weg", 0),
    "pps_to_kurt_schumacher":demand.get("j_kurt_schumacher_str", 0),
    "pps_to_hws":            Q(hws_leaves),
    "hws_to_schlettererstr": demand.get("j_schlettererstr", 0),
    "hws_to_theodor_heuss":  demand.get("j_theodor_heuss_platz", 0),
    "hws_to_lise_meitner":   demand.get("j_lise_meitner_str", 0),
    "hws_to_lechhauser":     demand.get("j_lechhauser_str", 0),
    # Backbone to west (HKW → PSW → HWW + direct west consumers)
    "hkw_to_psw":            Q(west_leaves),
    "psw_to_hww":            Q(hww_leaves),
    "psw_to_august_wessels": demand.get("j_august_wessels_str", 0),
    "psw_to_fuggerstr":      demand.get("j_fuggerstr", 0),
    "psw_to_hans_boeckler":  demand.get("j_hans_boeckler_str", 0),
    "psw_to_siegfried_aufhaeuser": demand.get("j_siegfried_aufhaeuser_str", 0),
    # West consumer spurs from j_hww
    "hww_to_grasiger_weg":   demand.get("j_grasiger_weg", 0),
    "hww_to_hooverstr":      demand.get("j_hooverstr", 0),
    "hww_to_hunoldsgraben":  demand.get("j_hunoldsgraben", 0),
    "hww_to_beethovenpark":  demand.get("j_beethovenpark", 0),
    "hww_to_am_mittleren_moos": demand.get("j_am_mittleren_moos", 0),
    "hww_to_don_bosco":      demand.get("j_don_bosco", 0),
}

# ─── Darcy-Weisbach calculation ───────────────────────────────────────────────
def friction_factor(Re, D_m, eps_m=eps):
    if Re <= 0:
        return 0.025
    if Re < 2300:
        return 64 / Re
    eps_rel = eps_m / D_m
    # Swamee-Jain (explicit Colebrook approximation)
    return 0.25 / (np.log10(eps_rel / 3.7 + 5.74 / Re**0.9))**2

rows = []
for pipe_id, Q_mw in sorted(pipe_Q_MW.items(), key=lambda x: -x[1]):
    D = pipe_D.get(pipe_id)
    L = pipe_L.get(pipe_id)
    if D is None or L is None:
        print(f"  WARNING: no geometry for {pipe_id}")
        continue

    # From-node supply temperature → dT for mass flow estimate
    from_nodes = {
        "hkw_to_": "j_hkw", "pps_to_": "j_pps", "hws_to_": "j_hws",
        "hww_to_": "j_hww", "psw_to_": "j_psw", "bmhkw_to_": "j_bmhkw",
    }
    T_from = T_sup.get("j_hkw", 130.0)
    for prefix, node in from_nodes.items():
        if pipe_id.startswith(prefix):
            T_from = T_sup.get(node, 130.0)
            break

    dT = max(T_from - T_ret_C, 5.0)
    m_dot = Q_mw * 1000.0 / (cp * dT)  # kg/s
    A = np.pi * D**2 / 4.0
    v = m_dot / (rho * A) if m_dot > 0 else 0.0
    Re = v * D / nu if v > 0 else 0.0
    f = friction_factor(Re, D)
    dP_per_m = f * rho * v**2 / (2.0 * D)  # Pa/m
    dP_total_bar = dP_per_m * L / 1e5        # bar

    rows.append({
        "pipe": pipe_id, "D_mm": D * 1000, "L_m": L,
        "Q_MW": Q_mw, "m_dot_kg_s": m_dot, "v_m_s": v,
        "Re": Re, "f": f,
        "dP_per_m_Pa": dP_per_m, "dP_total_bar": dP_total_bar,
    })

df = pd.DataFrame(rows)

# ─── Print results table ──────────────────────────────────────────────────────
header = f"{'Pipe':<30} {'DN':>4} {'L(m)':>6} {'Q(MW)':>7} {'m(kg/s)':>8} {'v(m/s)':>7} {'dP/m(Pa)':>9} {'dP(bar)':>8}"
print("\n" + "=" * 85)
print("Pressure drop analysis — Stadtbach BC-SB, t=1135 (peak demand)")
print("=" * 85)
print(header)
print("-" * 85)
for _, r in df.iterrows():
    flag = " *** HIGH VELOCITY" if r["v_m_s"] > 3.0 else ""
    print(
        f"{r['pipe']:<30} {r['D_mm']:>4.0f} {r['L_m']:>6.0f} "
        f"{r['Q_MW']:>7.2f} {r['m_dot_kg_s']:>8.1f} {r['v_m_s']:>7.2f} "
        f"{r['dP_per_m_Pa']:>9.1f} {r['dP_total_bar']:>8.4f}{flag}"
    )

print("\n" + "=" * 85)
print("CRITICAL PIPES by pressure drop per meter (top 8)")
print("=" * 85)
crit = df.nlargest(8, "dP_per_m_Pa")
for _, r in crit.iterrows():
    print(
        f"  {r['pipe']:<35}  v={r['v_m_s']:.2f} m/s  dP/m={r['dP_per_m_Pa']:.0f} Pa/m"
        f"  DN{r['D_mm']:.0f}  L={r['L_m']:.0f}m  total={r['dP_total_bar']:.3f} bar"
    )

print("\n" + "=" * 85)
print("CRITICAL PATH PRESSURE (supply-line cumulative from HKW)")
print("=" * 85)
# Path 1: HKW → PPS → HWS → Lechhauser (far south)
path_south = ["hkw_to_pps", "pps_to_hws", "hws_to_lechhauser"]
dp_south = sum(df.loc[df["pipe"] == p, "dP_total_bar"].values[0] for p in path_south if p in df["pipe"].values)
print(f"  HKW -> PPS -> HWS -> Lechhauser_Str: {dp_south:.3f} bar (supply side)")

# Path 2: HKW -> PSW -> HWW -> Am_Mittleren_Moos (far west)
path_west = ["hkw_to_psw", "psw_to_hww", "hww_to_am_mittleren_moos"]
dp_west = sum(df.loc[df["pipe"] == p, "dP_total_bar"].values[0] for p in path_west if p in df["pipe"].values)
print(f"  HKW -> PSW -> HWW -> Am_Mittleren_Moos: {dp_west:.3f} bar (supply side)")

# Path 3: HKW -> MAN (far east Mitte)
path_man = ["hkw_to_man"]
dp_man = sum(df.loc[df["pipe"] == p, "dP_total_bar"].values[0] for p in path_man if p in df["pipe"].values)
print(f"  HKW -> MAN: {dp_man:.3f} bar")

print(f"\n  Total (supply + return, roundtrip ~ x2):")
print(f"    South path: {dp_south*2:.3f} bar total differential")
print(f"    West path:  {dp_west*2:.3f} bar total differential")
print(f"\n  DH design standard: 3-6 bar differential (pump head)")
print(f"  Note: results use estimated pipe sizes (Bug 6: real DNs needed for final Paper 2)")

# ─── Save ─────────────────────────────────────────────────────────────────────
df.to_csv("output/paper2_runs/BC-SB/pressure_drop_analysis.csv", index=False)
print("\nSaved: output/paper2_runs/BC-SB/pressure_drop_analysis.csv")
