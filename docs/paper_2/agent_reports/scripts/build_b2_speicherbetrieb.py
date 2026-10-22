import csv, json, statistics
from collections import defaultdict

RUNS = [
    ("SB-S1-HK0 (c0x1.0)", "output/v7_final/SB-S1-HK0"),
    ("SB-S1-HK0-SPREIZ20", "output/_z3b/sb_free_spreiz20/paper2_runs/SB-S1-HK0-SPREIZ20"),
]

E_TES_MAX = 438.0  # MWh, from geometry.csv (both runs use the same TES size at c0x1.0 cost anchor)
CAP_POWER = 109.5  # MW

out_rows = []
monthly_rows = []
summary_lines = []

for label, path in RUNS:
    with open(f"{path}/dispatch_hourly.csv", encoding="utf-8") as f:
        r = csv.DictReader(f)
        rows = list(r)

    charge = [float(row["Q_storage_charge_MW"]) for row in rows]
    discharge = [float(row["Q_storage_discharge_MW"]) for row in rows]
    soc = [float(row["SOC_MWh"]) for row in rows]
    t_supply = [float(row["T_supply_C"]) for row in rows]
    lambda_buy = [float(row["lambda_buy_eur_MWh"]) for row in rows]
    q_chp = [float(row["Q_chp_MW"]) for row in rows]
    q_biomass = [float(row["Q_biomass_MW"]) for row in rows]
    q_gasboiler = [float(row["Q_gasboiler_MW"]) for row in rows]
    months = [row["timestamp"][5:7] for row in rows]

    total_charge_mwh = sum(charge)
    total_discharge_mwh = sum(discharge)
    full_cycles = total_discharge_mwh / E_TES_MAX if E_TES_MAX else 0

    # implied net loss per energy balance: charge_in - discharge_out - delta_SOC = loss (incl eta_strat + standing loss, not separable)
    delta_soc_total = soc[-1] - soc[0]
    implied_net_loss = total_charge_mwh - total_discharge_mwh - delta_soc_total

    hours_at_charge_limit = sum(1 for c in charge if c >= CAP_POWER - 0.05)
    hours_at_discharge_limit = sum(1 for d in discharge if d >= CAP_POWER - 0.05)
    hours_charging = sum(1 for c in charge if c > 0.01)
    hours_discharging = sum(1 for d in discharge if d > 0.01)
    hours_mask_blocked = sum(1 for t in t_supply if t > 95.0)  # discharge-mask ceiling trigger proxy

    soc_sorted = sorted(soc)
    n = len(soc_sorted)
    p5 = soc_sorted[int(0.05 * n)]
    p50 = soc_sorted[int(0.50 * n)]
    p95 = soc_sorted[int(0.95 * n)]

    # correlation proxies for mechanism (Pearson r, simple)
    def pearson(a, b):
        n = len(a)
        ma, mb = sum(a) / n, sum(b) / n
        cov = sum((x - ma) * (y - mb) for x, y in zip(a, b))
        va = sum((x - ma) ** 2 for x in a)
        vb = sum((y - mb) ** 2 for y in b)
        return cov / (va * vb) ** 0.5 if va > 0 and vb > 0 else 0.0

    corr_charge_price = pearson(charge, lambda_buy)
    corr_discharge_price = pearson(discharge, lambda_buy)
    corr_charge_chp = pearson(charge, q_chp)
    corr_charge_biomass = pearson(charge, q_biomass)

    out_rows.append({
        "run": label,
        "full_cycles_per_yr": round(full_cycles, 3),
        "total_charge_MWh_per_yr": round(total_charge_mwh, 1),
        "total_discharge_MWh_per_yr": round(total_discharge_mwh, 1),
        "implied_net_loss_MWh_per_yr": round(implied_net_loss, 1),
        "SOC_P5_MWh": round(p5, 1), "SOC_P50_MWh": round(p50, 1), "SOC_P95_MWh": round(p95, 1),
        "hours_charging": hours_charging, "hours_discharging": hours_discharging,
        "hours_at_charge_limit_cap_power": hours_at_charge_limit,
        "hours_at_discharge_limit_cap_power": hours_at_discharge_limit,
        "hours_T_supply_gt_95C_mask_proxy": hours_mask_blocked,
        "corr_charge_vs_price": round(corr_charge_price, 3),
        "corr_discharge_vs_price": round(corr_discharge_price, 3),
        "corr_charge_vs_chp": round(corr_charge_chp, 3),
        "corr_charge_vs_biomass": round(corr_charge_biomass, 3),
    })

    # monthly profile
    m_charge, m_discharge, m_soc, m_count = defaultdict(float), defaultdict(float), defaultdict(list), defaultdict(int)
    for mo, c, d, s in zip(months, charge, discharge, soc):
        m_charge[mo] += c
        m_discharge[mo] += d
        m_soc[mo].append(s)
        m_count[mo] += 1
    for mo in sorted(m_charge.keys()):
        monthly_rows.append({
            "run": label, "month": mo,
            "charge_MWh": round(m_charge[mo], 1),
            "discharge_MWh": round(m_discharge[mo], 1),
            "mean_SOC_MWh": round(statistics.mean(m_soc[mo]), 1),
        })

# write B2 summary CSV
with open("docs/paper_2/agent_reports/tables/B2_speicherbetrieb_summary.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
    w.writeheader()
    for r in out_rows:
        w.writerow(r)

with open("docs/paper_2/agent_reports/tables/B2_speicherbetrieb_monatsprofil.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(monthly_rows[0].keys()))
    w.writeheader()
    for r in monthly_rows:
        w.writerow(r)

print("wrote B2_speicherbetrieb_summary.csv and B2_speicherbetrieb_monatsprofil.csv")
for r in out_rows:
    print(r)
