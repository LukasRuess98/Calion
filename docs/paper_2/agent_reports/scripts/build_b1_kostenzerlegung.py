import json, csv

PAIRS = [
    ("SB-S1 c0x1.0 vs PIN0", "output/v7_final/SB-S0-HK0-PIN0/cost_breakdown.json",
     "output/v7_final/SB-S1-HK0/cost_breakdown.json"),
    ("SB-S1 c0x0.5 vs PIN0", "output/v7_final/SB-S0-HK0-PIN0/cost_breakdown.json",
     "output/_s2/sb_c0x05/paper2_runs/SB-S1-HK0/cost_breakdown.json"),
    ("SB-S1 c0x2.0 vs PIN0", "output/v7_final/SB-S0-HK0-PIN0/cost_breakdown.json",
     "output/_parallel_aa3/c0x2.0/paper2_runs/SB-S1-HK0/cost_breakdown.json"),
    ("SB-S2 vs PIN0", "output/v7_final/SB-S0-HK0-PIN0/cost_breakdown.json",
     "output/_s2/sb_s2_resolve2/paper2_runs/SB-S2-HK0/cost_breakdown.json"),
    ("SB-S1 SPREIZ15 vs own PIN0", "output/_z3b/sb_pin0_spreiz15/paper2_runs/SB-S1-HK0-PIN0-SPREIZ15/cost_breakdown.json",
     "output/_z3b/sb_free_spreiz15/paper2_runs/SB-S1-HK0-SPREIZ15/cost_breakdown.json"),
    ("SB-S1 SPREIZ20 vs own PIN0", "output/_z3b/sb_pin0_spreiz20/paper2_runs/SB-S1-HK0-PIN0-SPREIZ20/cost_breakdown.json",
     "output/_z3b/sb_free_spreiz20/paper2_runs/SB-S1-HK0-SPREIZ20/cost_breakdown.json"),
    ("MM-S1 vs PIN0", "output/v7_final/MM-S0-HK0-PIN0/cost_breakdown.json",
     "output/v7_final/MM-S1-HK0/cost_breakdown.json"),
]

LABELS = {
    "Capex_cost_EUR": "CAPEX (annuitaetisch, HP/EK/TES/Rohr)",
    "Activation_cost_EUR": "CAPEX Aktivierungsanteil (Start/Mindestlast)",
    "Fuel_cost_EUR": "Brennstoff",
    "Grid_energy_cost_EUR": "Strom (Bezug)",
    "Grid_sell_revenue_EUR": "Strom (KWK-Erloes, negativ)",
    "CO2_cost_EUR": "CO2 (brutto)",
    "Demand_charge_cost_EUR": "Netzentgelt (Lastspitze/Leistungspreis)",
    "OM_fixed_cost_EUR": "O&M fix",
    "OM_variable_cost_EUR": "O&M variabel",
}

rows = []
for label, pin0_path, free_path in PAIRS:
    try:
        pin0 = json.load(open(pin0_path, encoding="utf-8"))
        free = json.load(open(free_path, encoding="utf-8"))
    except FileNotFoundError as e:
        rows.append({"pair": label, "position": "FEHLER", "value": str(e)})
        continue
    pin0_tac = pin0["objective_total_EUR"]
    pin0_rc = pin0["real_costs_EUR"]
    free_rc = free["real_costs_EUR"]
    for key, label_de in LABELS.items():
        v_pin0 = pin0_rc.get(key, {}).get("value", 0.0)
        v_free = free_rc.get(key, {}).get("value", 0.0)
        delta = v_free - v_pin0
        rows.append({
            "pair": label, "position": label_de,
            "pin0_eur": round(v_pin0, 2), "free_eur": round(v_free, 2),
            "delta_eur_per_yr": round(delta, 2),
            "delta_pct_of_pin0_tac": round(100 * delta / pin0_tac, 4),
        })
    aux_delta = free.get("model_aux_terms_total_EUR", 0.0) - pin0.get("model_aux_terms_total_EUR", 0.0)
    obj_delta = free["objective_total_EUR"] - pin0_tac
    rows.append({
        "pair": label, "position": "Modellhilfsterme (Summe)",
        "pin0_eur": round(pin0.get("model_aux_terms_total_EUR", 0.0), 2),
        "free_eur": round(free.get("model_aux_terms_total_EUR", 0.0), 2),
        "delta_eur_per_yr": round(aux_delta, 2),
        "delta_pct_of_pin0_tac": round(100 * aux_delta / pin0_tac, 4),
    })
    rows.append({
        "pair": label, "position": "TOTAL (obj_eur Delta)",
        "pin0_eur": round(pin0_tac, 2), "free_eur": round(free["objective_total_EUR"], 2),
        "delta_eur_per_yr": round(obj_delta, 2),
        "delta_pct_of_pin0_tac": round(100 * obj_delta / pin0_tac, 4),
    })
    aux_share_of_delta = (aux_delta / obj_delta * 100) if abs(obj_delta) > 1e-6 else None
    stopp_flag = "STOPP (>20%)" if aux_share_of_delta is not None and abs(aux_share_of_delta) > 20 else "ok"
    rows.append({
        "pair": label, "position": f"Hilfsterm-Anteil am TOTAL-Delta [{stopp_flag}]",
        "pin0_eur": "", "free_eur": "",
        "delta_eur_per_yr": "",
        "delta_pct_of_pin0_tac": round(aux_share_of_delta, 2) if aux_share_of_delta is not None else "n/a",
    })
    # extra: Notkuehler / data_closure / dump
    for extra_key, extra_label in [("Emergency_cooler_MWh", "Notkuehler [MWh/a]"),
                                     ("data_closure_MWh", "data_closure [MWh/a]"),
                                     ("cost_dump_eur", "cost_dump_eur")]:
        if extra_key in free:
            rows.append({"pair": label, "position": extra_label,
                         "pin0_eur": pin0.get(extra_key, ""), "free_eur": free.get(extra_key, ""),
                         "delta_eur_per_yr": "", "delta_pct_of_pin0_tac": ""})
    rows.append({"pair": "", "position": "", "pin0_eur": "", "free_eur": "", "delta_eur_per_yr": "", "delta_pct_of_pin0_tac": ""})

out = "docs/paper_2/agent_reports/tables/B1_kostenzerlegung.csv"
fields = ["pair", "position", "pin0_eur", "free_eur", "delta_eur_per_yr", "delta_pct_of_pin0_tac"]
with open(out, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    for r in rows:
        w.writerow(r)
print(f"wrote {len(rows)} rows -> {out}")
