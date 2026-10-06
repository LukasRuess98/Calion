"""Paper 2 artefact extractor.

Extends the Paper 1 extract_artefacts.py pattern with Paper 2-specific outputs:
- geometry.csv: V_TES, h_TES (derived), E_TES_max, p_betr
- dsm_hourly.csv: delta(t), dpos(t), dneg(t) per DSM consumer
- kpis.json: All 24 KPIs from spec Section 6
- economics.csv (extended): CAPEX breakdown by component

Mirrors the extract_all() interface from scripts/paper/extract_artefacts.py.
"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path

logger = logging.getLogger(__name__)

# Water properties
_RHO = 971.8
_CP = 4.189
_G = 9.81
_P_ATM = 1.013


def _try_get(wf_result, attr: str, default=None):
    """Safely extract attribute from workflow result."""
    try:
        pf = wf_result.pf_result
        if pf is None:
            return default
        return getattr(pf, attr, default)
    except Exception:
        return default


def _pyomo_val(var, default: float = 0.0) -> float:
    """Extract scalar value from a Pyomo variable."""
    try:
        import pyomo.environ as pyo
        return float(pyo.value(var))
    except Exception:
        return default


def write_meta_p2(outdir: Path, scen_id: str, cfg: dict, wf_result, solve_s: float) -> dict:
    """Write meta.json with solver stats and scenario metadata."""
    pf = getattr(wf_result, "pf_result", None)
    # 2026-07-08 (O-7): ScenarioResult has no `solver_status` attribute, so the
    # old getattr() always wrote "unknown". Read the real solver metadata dict
    # (termination_condition, status, solution_count) that solver.py populates,
    # and derive an honest status: "no_incumbent" when solution_count <= 0 so a
    # zero-cost / no-solution run is never silently recorded as a valid result.
    solver_meta = getattr(pf, "solver", {}) if pf is not None else {}
    if not isinstance(solver_meta, dict):
        solver_meta = {}
    term_cond = str(solver_meta.get("termination_condition", "")).strip()
    sol_count = solver_meta.get("solution_count", None)
    if sol_count is not None and sol_count <= 0:
        status = "no_incumbent"
    elif term_cond:
        status = term_cond            # e.g. "optimal", "maxTimeLimit"
    else:
        status = str(solver_meta.get("status", "unknown"))

    # Objective: read from the summary objective section (never fabricate 0);
    # force None when there is no incumbent.
    obj_eur = None
    if sol_count is None or sol_count > 0:
        summ = getattr(pf, "summary", {}) if pf is not None else {}
        obj_section = summ.get("objective", {}) if hasattr(summ, "get") else {}
        if isinstance(obj_section, dict):
            for _k in ("OBJ_value_EUR", "Model_OBJ_value_EUR"):
                if obj_section.get(_k) is not None:
                    obj_eur = float(obj_section[_k])
                    break

    meta = {
        "scenario_id": scen_id,
        "solver": cfg.get("run", {}).get("solver", "gurobi"),
        "solve_s": round(solve_s, 2),
        "status": status,
        "termination_condition": term_cond or None,
        "solution_count": sol_count,
        "mip_gap": solver_meta.get("mip_gap", _try_get(wf_result, "mip_gap")),
        "obj_eur": obj_eur,
        "n_vars": solver_meta.get("num_vars", _try_get(wf_result, "n_vars")),
        "n_constraints": solver_meta.get("num_constr", _try_get(wf_result, "n_constraints")),
    }
    outdir.mkdir(parents=True, exist_ok=True)
    with open(outdir / "meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    return meta


def write_geometry_p2(outdir: Path, wf_result, scen: dict) -> dict | None:
    """Write geometry.csv: TES volume, height (derived), capacity, pressure.

    Reads the geometry scalars captured by result_collector in
    summary["objective"]["tes_geometry"] (pf_result carries no model handle).
    Returns dict with geometry values of the investable TES, or None.
    """
    try:
        pf = wf_result.pf_result
        if pf is None:
            return None
        summary = getattr(pf, "summary", None) or {}
        obj_section = summary.get("objective", {}) if hasattr(summary, "get") else {}
        geo_map = obj_section.get("tes_geometry") or {}
        if not geo_map:
            return None

        rows = []
        # AUTHORITATIVE r_hd from storage_geometry.yaml (NOT a hardcoded 3.0 default, which
        # produced a pressurized-shaped h/p_betr in the atmospheric run — 2026-09-14).
        try:
            from scripts.paper_2.scenario_runner import _load_storage_geometry as _lsg
            _sg = _lsg({"__force__": True}) or {}
        except Exception:
            _sg = {}
        _scen_ov = {}
        for _acfg in (scen.get("overrides", {}) or {}).get("assets", {}).values():
            if isinstance(_acfg, dict) and "r_hd" in _acfg:
                _scen_ov["r_hd"] = float(_acfg["r_hd"])

        def _r_hd_for(comp: str) -> float:
            pa = (_sg.get("per_asset") or {}).get(comp, {})
            if "r_hd" in pa:
                return float(pa["r_hd"])
            if "r_hd" in _sg:
                return float(_sg["r_hd"])
            return _scen_ov.get("r_hd", 3.0)

        for comp, g in geo_map.items():
            r_hd = _r_hd_for(comp)
            V = float(g.get("V_m3") or 0.0)
            if V > 0:
                # V = pi/(4*r_hd^2) * h^3  ->  h = (V * 4 * r_hd^2 / pi)^(1/3)
                h = (V * 4.0 * r_hd**2 / math.pi) ** (1.0 / 3.0)
            else:
                h = 0.0
            p_betr = _P_ATM + _RHO * _G * h / 1e5 if h > 0 else _P_ATM
            rows.append({
                "component": comp,
                "build": round(float(g.get("build") or 0.0)),
                "V_TES_m3": round(V, 2),
                "h_TES_m": round(h, 2),
                "E_TES_max_MWh": round(float(g.get("E_max_MWh") or 0.0), 2),
                "cap_power_MW": round(float(g.get("cap_power_MW") or 0.0), 2),
                "p_betr_bar": round(p_betr, 3),
            })

        # Endogenous site choice (if present)
        endog_sites = {
            "endog_hp_site": obj_section.get("endog_hp_site"),
            "endog_tes_site": obj_section.get("endog_tes_site"),
        }

        if rows:
            import csv
            csv_path = outdir / "geometry.csv"
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                w.writeheader()
                w.writerows(rows)
            if any(v for v in endog_sites.values()):
                with open(outdir / "endog_sites.json", "w", encoding="utf-8") as f:
                    json.dump(endog_sites, f, indent=2)
            return rows[0]

    except Exception as exc:
        logger.warning("geometry.csv extraction failed: %s", exc)
    return None


def write_node_heat_audit(outdir: Path, wf_result) -> dict | None:
    """Diagnostic (2026-07-16): dump the per-node ht_out/ht_in audit captured
    by result_collector.py (objective['node_heat_audit']) to node_heat_audit.json.

    Used to distinguish a reporting gap (per-asset dispatch export missing a
    generator) from a real formulation gap (ht_out itself doesn't cover demand).
    """
    try:
        pf = wf_result.pf_result
        if pf is None:
            return None
        summary = getattr(pf, "summary", None) or {}
        obj_section = summary.get("objective", {}) if hasattr(summary, "get") else {}
        audit = obj_section.get("node_heat_audit")
        if not audit:
            return None
        payload = {
            "total_ht_out_MWh": obj_section.get("node_heat_audit_total_ht_out_MWh"),
            "per_node": audit,
        }
        with open(outdir / "node_heat_audit.json", "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        return payload
    except Exception as exc:
        logger.warning("node_heat_audit extraction failed: %s", exc)
    return None


# Positivliste "reale Kosten" (author-approved Step A, 2026-09-21): everything else is a
# "Modellhilfsterm" (dump penalty, tie-break/regularisation, terminal value, slack penalties).
# Start-/Mindestlastkosten: no separate objective term exists in this model (thermal_gen.py's
# startup_cost_eur is a stored, never-wired-in parameter; min_load only forces fuel consumption,
# already inside Fuel_cost_EUR) -- reported as 0 with that note, not omitted.
_REAL_COST_KEYS = {
    "Capex_cost_EUR": "CAPEX (annuitaetisch, HP/EK/TES/Rohr)",
    "Activation_cost_EUR": "CAPEX (fixer Aktivierungsanteil je Investitionsentscheidung)",
    "Fuel_cost_EUR": "Brennstoff (inkl. Mindestlast-Brennstoff)",
    "Grid_energy_cost_EUR": "Strom (Bezug)",
    # 2026-09-22 (B1d, author): explicitly KWK, verified -- in BOTH networks the ONLY assets with
    # P_el_out (electricity generation) are the CHP-type thermal_generators with el_eff configured
    # (MM: chp_main only; SB: hkw/gtost/bmhkw); HP/EK/P2H are pure electricity consumers, all other
    # thermal_generators (gasboiler/biomass/ava_feed/boilers) are heat-only. Grid_sell_revenue_EUR
    # is therefore 100% KWK-Stromerloes in this model, never a non-CHP source.
    "Grid_sell_revenue_EUR": "Strom (KWK-Erloes Verkauf, negativ)",
    # 2026-09-22 D0 (author decision): a CHP dump electricity-revenue clawback was tried and
    # REMOVED -- market revenue for CHP electricity stays full even when its heat is dumped; a
    # real KWK-Zuschlag stays outside the objective entirely (assumption, MODEL_AND_DOE_CONTROL.md
    # SS4as). No replacement key.
    "CO2_cost_EUR": "CO2 (brutto, = Modellwert; siehe CO2_selfuse_netting_adjustment_EUR fuer die genettete Emissions-KPI-Zuordnung)",
    "Demand_charge_cost_EUR": "Netzentgelt (Lastspitze)",
    # V3 (2026-09-30, docs SS4bw): fixed O&M, previously ABSENT for every technology (S1-Audit-
    # Befund, docs SS4bo). Gilt fuer investierbare (HP/EK/TES) UND Bestand-Anlagen (CHP/Kessel) --
    # O&M ist unabhaengig von capex_charged (reale laufende Wartung auch bei versunkenem CAPEX).
    "OM_fixed_cost_EUR": "Fixe Betriebskosten (O&M), technologiespezifisch (DEA-Quelle fuer HP/EK/Gaskessel, Ingenieurschaetzung fuer TES/Biomasse-KWK, siehe SS4bw)",
    # W2 (2026-09-30, docs SS4bw-W): variable O&M, EUR/MWh_th geliefert -- DEA-Quelle fuer HP/EK/
    # Gaskessel direkt, Gas-Motor/Biomasse-KWK-Kapitel als Proxy (auf thermische Basis umgerechnet,
    # gleiche Unsicherheit wie die zugehoerigen fixen O&M-Werte). Kein Storage-Wert gefunden.
    "OM_variable_cost_EUR": "Variable Betriebskosten (O&M), EUR/MWh_th geliefert, technologiespezifisch (siehe SS4bw)",
}
_AUX_COST_KEYS = {
    "Dump_cost_EUR": "Abregel-Strafpreis (Modellparameter, siehe B)",
    "Tie_breaker_cost_EUR": "Tie-Break-Regularisierung",
    "Storage_installation_cost_EUR": "Speicher-Installationsterm (einfacher StorageBlock-Pfad; 0 fuer geometric_storage/TES)",
    "Terminal_value_EUR": "Terminalwert-/-strafterm (Speicher-Endzustand)",
    "Demand_slack_cost_EUR": "Bedarfs-Slack-Strafe",
    "Return_anchor_cost_EUR": "Ruecklauftemperatur-Anker-Strafe",
    "Pressure_reg_cost_EUR": "Druck-Tie-Break-Regularisierung",
    "Lateral_tiebreak_cost_EUR": "Stich-Verlust-PWL-Tie-Break",
    "Pressure_slack_cost_EUR": "Druck-Entlastungs-Slack (Datenqualitaets-Ventil)",
    "Data_closure_epsilon_cost_EUR": (
        "I1 Epsilon-Tie-Break (0.01 EUR/MWh) auf den G3/H1-Datenschliessungsterm (docs SS4bc) -- "
        "NICHT real, dient nur der Residuum-Minimierung; bei voller 0.25%-Kappungsgrenze maximal "
        "ca. 16 EUR (SB), kann keine Investitionsentscheidung beeinflussen."
    ),
    # V5 (2026-09-30, docs SS4bw) REMOVED "CO2_selfuse_netting_adjustment_EUR" from this dict --
    # it existed only to cancel a mismatch caused by CO2_cost_EUR silently holding the CHP-selfuse-
    # NETTED figure while model.obj optimized GROSS. result_collector.py now reports CO2_cost_EUR
    # as genuinely gross (matching model.obj), so Objective_residual_EUR is expected to be small on
    # its own merits, without this cancellation term. The netted figure is preserved as its own
    # standalone KPI, CO2_cost_net_of_selfuse_EUR (see write_cost_breakdown_p2 below) -- NOT part
    # of real_costs_EUR/model_aux_terms_EUR, since it never was a real objective term.
}


def write_cost_breakdown_p2(outdir: Path, wf_result, scen_id: str) -> dict | None:
    """Every additive objective term, individually, categorised real/aux (2026-09-21 Step A).

    Source: calion.run.result_collector's objective dict (captured live from the solved Pyomo
    model in-process -- these Expression values cannot be reconstructed from a saved .sol file).
    Asserts (logs an error, does not raise) that sum(all 16 terms, +1 om_cost since V3, docs
    SS4bw) reproduces OBJ_value_EUR to within 1 EUR; result_collector.py already does the
    identical check and logs Objective_residual_EUR, this file re-verifies it independently
    at write time.
    """
    try:
        pf = wf_result.pf_result
        if pf is None:
            return None
        summary = getattr(pf, "summary", None) or {}
        obj = summary.get("objective", {}) if hasattr(summary, "get") else {}
        if not obj:
            return None
        real = {k: float(obj.get(k) or 0.0) for k in _REAL_COST_KEYS}
        # Sign fix (2026-09-22): Grid_sell_revenue_EUR is stored POSITIVE in the objective dict
        # (a revenue magnitude), but components_sum (result_collector.py) computes
        # `energy_cost - energy_revenue` -- i.e. revenue REDUCES net cost. Summing real.values()
        # naively double-counted it (found via sum_real_plus_aux_plus_residual_minus_objective_EUR
        # != 0: exactly 2x Grid_sell_revenue_EUR). Store it negative here so real_total is the true
        # net cost and the reconciliation sum is exact.
        real["Grid_sell_revenue_EUR"] = -real["Grid_sell_revenue_EUR"]
        aux = {k: float(obj.get(k) or 0.0) for k in _AUX_COST_KEYS}
        # V5 (2026-09-30, docs SS4bw): real["CO2_cost_EUR"] is now read directly -- as of
        # result_collector.py's V5 fix, obj["CO2_cost_EUR"] IS the gross, model.obj-matching
        # figure (previously it silently held the CHP-selfuse-NETTED figure, requiring the
        # swap-in + cancellation-term workaround this comment used to describe; see git history
        # / docs SS4bw for the removed code). The netted figure -- economics.csv's historical
        # cost_co2_eur convention -- is preserved as its own standalone KPI below, OUTSIDE the
        # real/aux reconciliation, since it was never a real objective term.
        _co2_net_of_selfuse = obj.get("CO2_cost_net_of_selfuse_EUR")
        obj_total = float(obj.get("OBJ_value_EUR") or 0.0)
        residual = float(obj.get("Objective_residual_EUR") or 0.0)
        real_total = sum(real.values())
        aux_total = sum(aux.values())
        recon_gap = (real_total + aux_total + residual) - obj_total
        payload = {
            "scenario_id": scen_id,
            "objective_total_EUR": obj_total,
            "residual_EUR": residual,
            "residual_note": (
                "V5 (docs SS4bw): residual_EUR is result_collector's raw obj-vs-components_sum gap, "
                "now computed with BOTH sides using the GROSS CO2 figure (previously "
                "components_sum used the CHP-selfuse-netted figure while OBJ_value_EUR did not, "
                "requiring a cancellation term below -- removed). Expect residual_EUR to be small "
                "(genuine floating-point/reporting noise only) on its own merits now."
            ),
            "co2_cost_net_of_selfuse_EUR": {
                "value": float(_co2_net_of_selfuse) if _co2_net_of_selfuse is not None else None,
                "label": (
                    "V5 (docs SS4bw): CHP-Eigenverbrauchsanteil-genettete CO2-Kosten (Paper-1-"
                    "Konvention, project_paper1_objective_residual) -- REINE Berichts-KPI, KEIN "
                    "Objektivterm, NICHT in real_costs_EUR/model_aux_terms_EUR enthalten. Vergleich: "
                    "real_costs_EUR.CO2_cost_EUR (brutto, = Modellwert)."
                ),
            },
            "reconciliation_check": "OK" if abs(recon_gap) <= 1.0 else "FAIL (>1 EUR: an objective term is still unaccounted)",
            "data_closure_dump_MWh": {
                "value": float(obj.get("Data_closure_dump_MWh") or 0.0),
                "pct_of_annual_demand": float(obj.get("Data_closure_dump_pct_of_demand") or 0.0),
                "label": (
                    "G3/H1 Datenschliessungsterm (docs SS4av-SS4ax): 0 EUR/MWh, NICHT in "
                    "real_costs_EUR oder model_aux_terms_EUR -- Pflicht-KPI (MWh und % des "
                    "Jahresbedarfs), nur unter CALION_DUMP_MODE=chp_only nonzero, netzweit hart "
                    "gedeckelt auf 0.25% des Jahresbedarfs (Constraint data_closure_cap; "
                    "ueberschritten => Lauf infeasible statt still toleriert). Warnung im Log ab "
                    "0.125%. Die Grenze ist ein Drift-Waechter, keine physikalische Schranke "
                    "(beobachtetes strukturelles Lieferresiduum: 0.08-0.13% des Jahresbedarfs)."
                ),
            },
            "real_costs_EUR": {k: {"value": v, "label": _REAL_COST_KEYS[k]} for k, v in real.items()},
            "real_costs_total_EUR": real_total,
            "model_aux_terms_EUR": {k: {"value": v, "label": _AUX_COST_KEYS[k]} for k, v in aux.items()},
            "model_aux_terms_total_EUR": aux_total,
            "sum_real_plus_aux_plus_residual_minus_objective_EUR": recon_gap,
            "_diagnostic_expr_vs_series_EUR": {  # TEMPORARY (2026-09-22 residual investigation)
                "energy_cost": {"series_recompute": real["Grid_energy_cost_EUR"] + real["Grid_sell_revenue_EUR"],
                                "live_expr": obj.get("_diag_energy_cost_expr_EUR")},
                "dump_cost": {"series_recompute": aux["Dump_cost_EUR"], "live_expr": obj.get("_diag_dump_cost_expr_EUR")},
                "fuel_cost": {"series_recompute": real["Fuel_cost_EUR"], "live_expr": obj.get("_diag_fuel_cost_expr_EUR")},
                "co2_cost": {"series_recompute": real["CO2_cost_EUR"], "live_expr": obj.get("_diag_co2_cost_expr_EUR")},
                "demand_cost": {"series_recompute": real["Demand_charge_cost_EUR"], "live_expr": obj.get("_diag_demand_cost_expr_EUR")},
            },
        }
        with open(outdir / "cost_breakdown.json", "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        if abs(recon_gap) > 1.0:
            logger.error("[%s] cost_breakdown.json: reconciliation gap=%.2f > 1 EUR tolerance "
                        "-- breakdown is INCOMPLETE, do not use for the real/aux split.", scen_id, recon_gap)
        return payload
    except Exception as exc:
        logger.warning("[%s] cost_breakdown extraction failed: %s", scen_id, exc)
    return None


def write_pressure_slack_audit_p2(outdir: Path, wf_result) -> dict | None:
    """Per-node, per-hour pressure-relief-slack audit (2026-09-22, B1b prep).

    Source: result_collector's objective['_pressure_slack_audit'] (captured live from
    model.pressure_slack_terms). Used to derive a FIXED per-node pressure-bound widening
    (thermal_node.py's CALION_PRESSURE_SLACK_MODE=preprocessed), which then replaces this
    slack mechanism entirely -- this file is the evidence base for that widening table.
    """
    try:
        pf = wf_result.pf_result
        if pf is None:
            return None
        summary = getattr(pf, "summary", None) or {}
        obj_section = summary.get("objective", {}) if hasattr(summary, "get") else {}
        audit = obj_section.get("_pressure_slack_audit")
        if not audit:
            return None
        with open(outdir / "pressure_slack_audit.json", "w", encoding="utf-8") as f:
            json.dump(audit, f, indent=2)
        return audit
    except Exception as exc:
        logger.warning("pressure_slack_audit extraction failed: %s", exc)
    return None


def write_dump_audit_p2(outdir: Path, wf_result) -> dict | None:
    """Per-node, per-hour Q_dump audit (2026-09-22, C2/C3 prep). See write_pressure_slack_audit_p2
    for the identical pattern; source is result_collector's objective['_dump_audit']."""
    try:
        pf = wf_result.pf_result
        if pf is None:
            return None
        summary = getattr(pf, "summary", None) or {}
        obj_section = summary.get("objective", {}) if hasattr(summary, "get") else {}
        audit = obj_section.get("_dump_audit")
        if not audit:
            return None
        with open(outdir / "dump_audit.json", "w", encoding="utf-8") as f:
            json.dump(audit, f, indent=2)
        return audit
    except Exception as exc:
        logger.warning("dump_audit extraction failed: %s", exc)
    return None


def write_dsm_hourly_p2(outdir: Path, wf_result) -> bool:
    """Write dsm_hourly.csv: delta(t), dpos(t), dneg(t) for each DSM consumer."""
    try:
        pf = wf_result.pf_result
        if pf is None:
            return False
        model = getattr(pf, "model", None)
        if model is None:
            return False

        rows = {}
        for attr_name in dir(model):
            if attr_name.endswith("_dpos"):
                comp = attr_name[:-5]
                dpos_var = getattr(model, attr_name)
                dneg_var = getattr(model, f"{comp}_dneg", None)
                if dneg_var is None:
                    continue
                for t in dpos_var:
                    rows.setdefault(t, {})[f"{comp}_dpos"] = round(_pyomo_val(dpos_var[t]), 4)
                    rows[t][f"{comp}_dneg"] = round(_pyomo_val(dneg_var[t]), 4)
                    rows[t][f"{comp}_delta"] = round(
                        _pyomo_val(dpos_var[t]) - _pyomo_val(dneg_var[t]), 4
                    )

        if rows:
            import csv
            sorted_ts = sorted(rows.keys())
            fieldnames = ["t"] + sorted(next(iter(rows.values())).keys())
            with open(outdir / "dsm_hourly.csv", "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=fieldnames)
                w.writeheader()
                for t in sorted_ts:
                    row = {"t": t, **rows[t]}
                    w.writerow(row)
            return True

    except Exception as exc:
        logger.warning("dsm_hourly.csv extraction failed: %s", exc)
    return False


def extract_all_p2(
    scen_id: str,
    cfg: dict,
    wf_result,
    solve_s: float,
    outdir: Path,
    scen: dict,
) -> Path:
    """Master extractor for Paper 2 artefacts.

    Calls all write_* functions and delegates economics/dispatch to
    the Paper 1 extract_artefacts module for reuse.
    """
    outdir.mkdir(parents=True, exist_ok=True)

    # Reuse Paper 1 extraction for standard artefacts.
    # NOTE (2026-07-08, O-7): the Paper 1 extractor ALSO writes meta.json (its
    # own write_meta), which used to clobber the P2 meta.json with a less
    # informative version. Run it FIRST, then write the authoritative P2
    # meta.json last so it wins.
    try:
        from scripts.paper.extract_artefacts import extract_all as extract_p1
        # Paper 1 extractor writes economics.csv, dispatch_hourly.csv, etc.
        _tmp_cfg_path = _write_tmp_yaml(cfg)
        try:
            extract_p1(scen_id, str(_tmp_cfg_path), wf_result, solve_s, outdir=outdir)
        except Exception as exc:
            logger.warning("[%s] Paper 1 extraction partial failure: %s", scen_id, exc)
        finally:
            try:
                _tmp_cfg_path.unlink()
            except OSError:
                pass
    except ImportError:
        logger.warning("Paper 1 extract_artefacts not importable — skipping standard artefacts")

    # Authoritative P2 meta.json (written AFTER P1 so it is not overwritten).
    meta = write_meta_p2(outdir, scen_id, cfg, wf_result, solve_s)
    logger.info("[%s] meta.json: status=%s, obj=%.0f €",
                scen_id, meta.get("status"), meta.get("obj_eur") or 0)

    # K1 (2026-09-27, docs SS4be): copy the unconditional full-solution dump (written by
    # calion/run/solver.py to the raw export_dir, keyed by a per-run hash the caller doesn't
    # otherwise know) into THIS scenario's curated OUT_BASE dir, so that CALION_WARMSTART_FROM
    # (which conventionally points at an OUT_BASE/<scen_id> dir, not the raw export dir) can
    # find it without the caller needing to track the hash. Copy, not move -- the raw export
    # dir keeps its own copy too.
    try:
        import shutil as _shutil_dump
        _export_dir = Path(cfg.get('output', {}).get('export_dir', ''))
        _src_dump = _export_dir / "full_solution_dump.json"
        if _src_dump.exists():
            _dst_dump = outdir / "full_solution_dump.json"
            _shutil_dump.copy2(str(_src_dump), str(_dst_dump))
            logger.info("[%s] full_solution_dump.json copied to %s (%.1f MB) -- available as a "
                        "COMPLETE warmstart source via CALION_WARMSTART_FROM=%s",
                        scen_id, _dst_dump, _dst_dump.stat().st_size / 1e6, outdir)
        else:
            logger.warning("[%s] no full_solution_dump.json found at %s -- warmstarting FROM "
                           "this run will fall back to the partial CSV-based hints.",
                           scen_id, _export_dir)
    except Exception as _dump_copy_err:
        logger.warning("[%s] could not copy full_solution_dump.json: %s", scen_id, _dump_copy_err)

    # Paper 2-specific artefacts
    geo = write_geometry_p2(outdir, wf_result, scen)
    if geo:
        logger.info("[%s] geometry.csv: V=%.1f m³, h=%.1f m, E=%.1f MWh, p=%.2f bar",
                    scen_id, geo["V_TES_m3"], geo["h_TES_m"],
                    geo["E_TES_max_MWh"], geo["p_betr_bar"])

    write_node_heat_audit(outdir, wf_result)

    write_pressure_slack_audit_p2(outdir, wf_result)

    write_dump_audit_p2(outdir, wf_result)

    write_cost_breakdown_p2(outdir, wf_result, scen_id)

    write_dsm_hourly_p2(outdir, wf_result)

    # Scenario metadata — include heat curve parameters for KPI calculator
    _HK_PARAMS = {
        "memmingen": {"HK0": (1.0, 74.0), "HK1": (0.8, 70.0), "HK2": (0.6, 66.0)},
        "stadtbach":  {"HK0": (1.0, 70.0), "HK1": (0.8, 65.0), "HK2": (0.6, 60.0)},
    }
    network = scen.get("network", "")
    hk_stage = scen.get("heat_curve_stage", "HK0")
    hk_data = _HK_PARAMS.get(network, {}).get(hk_stage)
    k_val, T_VL_min_val = hk_data if hk_data else (None, None)
    with open(outdir / "scenario_meta.json", "w", encoding="utf-8") as f:
        json.dump({
            "id": scen["id"],
            "network": network,
            "heat_curve_stage": hk_stage,
            "tes_node": scen.get("tes_node"),
            "baseline": scen.get("baseline", False),
            "k": k_val,
            "T_VL_min_c": T_VL_min_val,
        }, f, indent=2)

    return outdir


def _write_tmp_yaml(cfg: dict) -> "Path":
    import tempfile
    import yaml
    tmp = tempfile.NamedTemporaryFile(suffix=".yaml", delete=False, mode="w", encoding="utf-8")
    yaml.dump(cfg, tmp, allow_unicode=True, default_flow_style=False)
    tmp.flush()
    return Path(tmp.name)
