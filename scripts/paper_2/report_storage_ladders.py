"""Report the two atmospheric-TES size ladders EXACTLY as the model builds them.

Reads configs/paper_2/storage_geometry.yaml and reproduces geometric_storage.py's
ladder logic: MWh -> V (at the scenario's usable ΔT incl. eta_strat), the
v_min_realistic floor, N=ceil(V/unit), and the PER-TANK degressive cost
C = N·c0·((V/N)/v0)^b. Prints both networks for normal and hot charging, and the
CAPEX band for b in {0.65, 0.70, 0.776}. No solve; pure config arithmetic.
"""
from __future__ import annotations
import math
from pathlib import Path
import yaml

from calion.constants import RHO_WATER_HOT_KG_M3 as RHO, CP_WATER_HOT_KJ_PER_KGK as CP

ROOT = Path(__file__).resolve().parents[2]
GEOM = yaml.safe_load(open(ROOT / "configs/paper_2/storage_geometry.yaml", encoding="utf-8"))["storage_geometry"]

# Network operating points. min_supply_delta_T_k is read from each base config
# (BOTH set 15.0 — the VDI-6002 hydraulic floor; the scenario_runner DEFAULT of 10.0
# only applies if a config omits it, which neither does).
def _min_dt(cfg_path):
    c = yaml.safe_load(open(ROOT / cfg_path, encoding="utf-8"))
    return float(c.get("network", {}).get("min_supply_delta_T_k", 10.0))

NETS = {
    "Memmingen (tes_main)": dict(asset="tes_main", t_return=63.6, t_vl_min=74.0, t_vl_max=100.0, mean_mw=1.084,
                                 min_dt=_min_dt("configs/paper_2/Memmingen_P2_base.yaml")),
    "Stadtbach (tes_sb)":   dict(asset="tes_sb",   t_return=60.0, t_vl_min=70.0, t_vl_max=122.0, mean_mw=73.06,
                                 min_dt=_min_dt("configs/paper_2/Stadtbach_topo.yaml")),
}


def coeff_mwh_per_m3(delta_T, eta):
    return eta * RHO * CP * delta_T / 3.6e6


def build_ladder(energies, coeff, unit, v_min):
    e_list = sorted(set([0.0] + [float(e) for e in energies]))
    v_list = [e / coeff for e in e_list]
    kept = [(e, v) for e, v in zip(e_list, v_list) if e <= 0.0 or v >= v_min]
    e_list = [e for e, _ in kept]
    v_list = [v for _, v in kept]
    n_list = [0 if e <= 0 else max(1, math.ceil(v / unit)) for e, v in zip(e_list, v_list)]
    return e_list, v_list, n_list


def cost_per_rung(v, n, c0, v0, b):
    if v <= 0 or n <= 0:
        return 0.0
    v_per = v / n
    return n * c0 * (v_per / v0) ** b


def report(name, cfg):
    pa = GEOM["per_asset"][cfg["asset"]]
    unit = GEOM["unit_tank_m3"]; v_min = GEOM["v_min_realistic_m3"]
    c0 = GEOM["c0_eur"]; v0 = GEOM["v0_m3"]; eta = GEOM["eta_strat"]
    energies = pa["discrete_energies_mwh"]
    ceiling = GEOM["t_store_max_c"]

    dt_norm = max(cfg["t_vl_min"], cfg["t_return"] + cfg["min_dt"]) - cfg["t_return"]
    t_charge_hot = min(cfg["t_vl_max"], ceiling)
    dt_hot = t_charge_hot - cfg["t_return"]

    print(f"\n{'='*100}\n{name}   |  ΔT_normal={dt_norm:.1f} K   ΔT_hot(min(T_VLmax,{ceiling:.0f})−T_ret)={dt_hot:.1f} K"
          f"   mean load={cfg['mean_mw']:.2f} MW\n{'='*100}")
    for mode, dt in (("NORMAL", dt_norm), ("HOT", dt_hot)):
        coeff = coeff_mwh_per_m3(dt, eta)
        e_l, v_l, n_l = build_ladder(energies, coeff, unit, v_min)
        n_pos_in = len({float(e) for e in energies if e > 0})
        n_pos_out = len([e for e in e_l if e > 0])
        print(f"\n  {mode} charge  (usable {coeff*1000:.2f} kWh/m³ = eta {eta} × ρc_pΔT)  "
              f"— {n_pos_out} positive rungs, dropped {n_pos_in - n_pos_out} below {v_min:.0f} m³:")
        print(f"    {'E[MWh]':>8} {'hours':>6} {'V[m³]':>9} {'N':>3} {'v/N[m³]':>8} {'€/m³':>7} "
              f"{'C(b.65)':>10} {'C(b.70)':>10} {'C(b.776)':>10}")
        for e, v, n in zip(e_l, v_l, n_l):
            if e <= 0:
                print(f"    {0:>8.0f} {0:>6.1f} {0:>9.0f} {0:>3} {'-':>8} {'-':>7} {0:>10.0f} {0:>10.0f} {0:>10.0f}")
                continue
            c70 = cost_per_rung(v, n, c0, v0, 0.70)
            c65 = cost_per_rung(v, n, c0, v0, 0.65)
            c776 = cost_per_rung(v, n, c0, v0, 0.776)
            spec = c70 / v
            print(f"    {e:>8.1f} {e/cfg['mean_mw']:>6.1f} {v:>9.0f} {n:>3d} {v/n:>8.0f} {spec:>7.0f} "
                  f"{c65:>10.0f} {c70:>10.0f} {c776:>10.0f}")


if __name__ == "__main__":
    print("ATMOSPHERIC TES SIZE LADDERS — as the MILP builds them (per-tank degressive cost)")
    print(f"anchor c0={GEOM['c0_eur']:.0f}€ @ v0={GEOM['v0_m3']:.0f}m³ (=250€/m³), b=0.70, unit={GEOM['unit_tank_m3']:.0f}m³, "
          f"v_min={GEOM['v_min_realistic_m3']:.0f}m³, β=0 (turnkey), ceiling={GEOM['t_store_max_c']:.0f}°C")
    for name, cfg in NETS.items():
        report(name, cfg)
