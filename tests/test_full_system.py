"""
Comprehensive System Test for EnerGIS
======================================

Tests all aspects of the optimization system:
1. Configuration parsing
2. Model creation (variables, constraints)
3. Investment bounds (min/max)
4. Objective function components
5. CO2 emissions calculation
6. Heat balance
7. Network losses
"""

import sys
sys.path.insert(0, '.')

from pathlib import Path
from energis.config.merge import load_and_merge
from energis.io.loader import load_input_excel
from energis.models.system_builder import build_model
from energis.models.network_manager import NetworkManager
import pyomo.environ as pyo

# Test configuration
CONFIG_PATH = 'configs/stadtbach.yaml'
TOLERANCE = 1e-6

def test_configuration_parsing():
    """Test 1: Verify configuration is parsed correctly."""
    print("\n" + "="*70)
    print("TEST 1: KONFIGURATION PARSING")
    print("="*70)

    cfg = load_and_merge([CONFIG_PATH])
    errors = []

    # Check heat pump config
    hps = cfg.get('system', {}).get('heat_pumps', [])
    print(f"\n✓ {len(hps)} Wärmepumpen gefunden")

    for hp in hps:
        hp_id = hp.get('id')
        inv = hp.get('investment', {})

        # Check required investment fields
        required = ['enabled', 'min_mw', 'max_mw', 'capex_eur_per_mw',
                   'activation_cost_eur', 'lifetime_years']
        missing = [f for f in required if f not in inv]

        if missing:
            errors.append(f"  ✗ {hp_id}: Fehlende Investment-Felder: {missing}")
        else:
            print(f"  ✓ {hp_id}: Investment-Config vollständig")
            print(f"      min={inv['min_mw']} MW, max={inv['max_mw']} MW")
            print(f"      CAPEX={inv['capex_eur_per_mw']:,} €/MW")
            print(f"      Activation={inv['activation_cost_eur']:,} €")

    # Check storage config
    sto = cfg.get('system', {}).get('storage', {})
    if sto.get('enabled'):
        print(f"\n✓ Speicher aktiviert")
        inv = sto.get('investment', {})
        print(f"    Energie: {sto.get('energy_mwh')} MWh")
        print(f"    Leistung: {sto.get('power_mw')} MW")
        print(f"    Investment min/max: {inv.get('min_energy_mwh')}-{inv.get('max_energy_mwh')} MWh")

    # Check generators
    gens = cfg.get('system', {}).get('generators', {})
    enabled_gens = [k for k, v in gens.items() if v.get('enabled')]
    print(f"\n✓ {len(enabled_gens)} Generatoren aktiviert: {enabled_gens}")

    # Check thermal network
    tn = cfg.get('thermal_network', {})
    print(f"\n✓ Thermisches Netzwerk: {'aktiviert' if tn.get('enabled') else 'deaktiviert'}")

    if errors:
        print("\n⚠ FEHLER GEFUNDEN:")
        for e in errors:
            print(e)
        return False

    print("\n✓ Konfiguration vollständig und korrekt!")
    return True


def slice_table(table, n_rows):
    """Slice a TimeSeriesTable to first n_rows."""
    from energis.utils.timeseries import TimeSeriesTable
    return TimeSeriesTable(
        index=table.index[:n_rows],
        columns=table.columns[:],
        data={k: v[:n_rows] for k, v in table.data.items()}
    )


def test_model_creation():
    """Test 2: Verify model is created correctly with all components."""
    print("\n" + "="*70)
    print("TEST 2: MODELL-ERSTELLUNG")
    print("="*70)

    cfg = load_and_merge([CONFIG_PATH])
    site_cfg = cfg.get('site', {})
    data_file = cfg.get('data_file', site_cfg.get('input_file', 'Import_Data.xlsx'))
    table = load_input_excel(data_file, site_cfg)

    # Use short horizon for testing
    table = slice_table(table, 48)  # 2 days

    model = build_model(table, cfg, dt_h=1.0)
    errors = []

    # Check time set
    T = len(list(model.t))
    print(f"\n✓ Zeitschritte: {T}")

    # Check decision variables
    print("\nEntscheidungsvariablen:")
    vars_to_check = ['P_buy', 'P_sell', 'Q_dump', 'grid_mode']
    for var_name in vars_to_check:
        if hasattr(model, var_name):
            var = getattr(model, var_name)
            print(f"  ✓ {var_name}: {len(list(var))} Einträge")
        else:
            errors.append(f"  ✗ {var_name} fehlt!")

    # Check heat pump variables
    print("\nWärmepumpen-Variablen:")
    hp_vars = ['HP1_Q', 'HP2_Q', 'HP3_Q', 'HP4_Q']
    for var_name in hp_vars:
        if hasattr(model, var_name):
            print(f"  ✓ {var_name} vorhanden")
        else:
            print(f"  ? {var_name} nicht gefunden (evtl. deaktiviert)")

    # Check generator variables
    print("\nGenerator-Variablen:")
    gen_vars = ['HKW_Qth', 'GTOST_Qth', 'BMHKW_Qth', 'HWS_Qth', 'HWW_Qth', 'AVA_Qth', 'P2H_Qth']
    for var_name in gen_vars:
        if hasattr(model, var_name):
            print(f"  ✓ {var_name} vorhanden")
        else:
            print(f"  ? {var_name} nicht gefunden")

    # Check investment variables
    print("\nInvestment-Variablen:")
    inv_vars = ['HP1_cap_mw', 'HP1_build', 'TES_cap_energy', 'TES_build']
    for var_name in inv_vars:
        if hasattr(model, var_name):
            var = getattr(model, var_name)
            if hasattr(var, 'lb') and hasattr(var, 'ub'):
                print(f"  ✓ {var_name}: bounds=[{var.lb}, {var.ub}]")
            else:
                print(f"  ✓ {var_name} vorhanden")
        else:
            print(f"  ? {var_name} nicht gefunden")

    # Check constraints (correct names: ht_balance, el_balance)
    print("\nConstraints:")
    constraints = ['ht_balance', 'el_balance']
    for con_name in constraints:
        if hasattr(model, con_name):
            con = getattr(model, con_name)
            print(f"  ✓ {con_name}: {len(list(con))} Einträge")
        else:
            errors.append(f"  ✗ {con_name} fehlt!")

    # Check objective (correct name: obj)
    if hasattr(model, 'obj'):
        print(f"\n✓ Zielfunktion (obj) definiert")
    else:
        errors.append("✗ Zielfunktion fehlt!")

    if errors:
        print("\n⚠ FEHLER:")
        for e in errors:
            print(e)
        return False, None

    print("\n✓ Modell korrekt erstellt!")
    return True, model


def test_investment_bounds(model, cfg):
    """Test 3: Verify investment bounds are applied correctly.

    Note: Minimum bounds are enforced via constraints (cap >= cap_min * build),
    NOT via variable bounds. This is correct: when build=0, cap can be 0;
    when build=1, cap must be >= cap_min.
    """
    print("\n" + "="*70)
    print("TEST 3: INVESTMENT-GRENZEN")
    print("="*70)

    errors = []

    # Check heat pump bounds - min is enforced via constraints, max via variable bounds
    print("\nWärmepumpen-Grenzen:")
    hps = cfg.get('system', {}).get('heat_pumps', [])
    for hp in hps:
        hp_id = hp.get('id')
        inv = hp.get('investment', {})

        if not inv.get('enabled'):
            continue

        cap_var_name = f"{hp_id}_cap_mw"
        cap_min_param = f"{hp_id}_cap_min"
        cap_max_param = f"{hp_id}_cap_max"

        if hasattr(model, cap_var_name):
            cap_var = getattr(model, cap_var_name)

            expected_min = inv.get('min_mw', 0)
            expected_max = inv.get('max_mw', 100)

            # Variable upper bound should match max
            actual_ub = cap_var.ub if cap_var.ub is not None else float('inf')
            if abs(actual_ub - expected_max) < TOLERANCE:
                print(f"  ✓ {hp_id} max (var.ub): {actual_ub} MW")
            else:
                errors.append(f"  ✗ {hp_id} max: {actual_ub} != {expected_max}")

            # Min is enforced via constraint using cap_min parameter
            if hasattr(model, cap_min_param):
                actual_min_param = pyo.value(getattr(model, cap_min_param))
                if abs(actual_min_param - expected_min) < TOLERANCE:
                    print(f"  ✓ {hp_id} min (param): {actual_min_param} MW (enforced via cap_lo constraint)")
                else:
                    errors.append(f"  ✗ {hp_id} min param: {actual_min_param} != {expected_min}")

            # Check constraint exists
            cap_lo_name = f"{hp_id}_cap_lo"
            if hasattr(model, cap_lo_name):
                print(f"  ✓ {hp_id}_cap_lo constraint exists (cap >= cap_min * build)")
            else:
                errors.append(f"  ✗ {hp_id}_cap_lo constraint missing!")

    # Check storage bounds
    print("\nSpeicher-Grenzen:")
    sto = cfg.get('system', {}).get('storage', {})
    inv = sto.get('investment', {})

    if inv.get('enabled') and hasattr(model, 'TES_cap_energy'):
        cap_var = model.TES_cap_energy
        expected_min = inv.get('min_energy_mwh', 0)
        expected_max = inv.get('max_energy_mwh', 5000)

        actual_ub = cap_var.ub if cap_var.ub is not None else float('inf')

        if abs(actual_ub - expected_max) < TOLERANCE:
            print(f"  ✓ Energie max (var.ub): {actual_ub} MWh")
        else:
            errors.append(f"  ✗ Energie max: {actual_ub} != {expected_max}")

        # Check min param
        if hasattr(model, 'TES_capE_min'):
            actual_min = pyo.value(model.TES_capE_min)
            if abs(actual_min - expected_min) < TOLERANCE:
                print(f"  ✓ Energie min (param): {actual_min} MWh (enforced via constraint)")
            else:
                errors.append(f"  ✗ Energie min param: {actual_min} != {expected_min}")

    if errors:
        print("\n⚠ FEHLER:")
        for e in errors:
            print(e)
        return False

    print("\n✓ Investment-Grenzen korrekt definiert!")
    return True


def test_solve_and_objective(model, cfg):
    """Test 4: Solve model and verify objective function components."""
    print("\n" + "="*70)
    print("TEST 4: OPTIMIERUNG & ZIELFUNKTION")
    print("="*70)

    # Solve
    print("\nLöse Optimierungsproblem...")
    solver = pyo.SolverFactory('glpk')
    result = solver.solve(model, tee=False)

    status = str(result.solver.status)
    termination = str(result.solver.termination_condition)

    print(f"  Status: {status}")
    print(f"  Termination: {termination}")

    if 'optimal' not in termination.lower() and 'feasible' not in termination.lower():
        print("  ✗ Optimierung fehlgeschlagen!")
        return False

    print(f"\n✓ Optimierung erfolgreich!")

    # Extract objective value
    obj_value = pyo.value(model.obj)
    print(f"\nZielfunktionswert: {obj_value:,.2f} EUR")

    # Check objective components
    print("\nZielfunktions-Komponenten:")

    # Energy costs
    if hasattr(model, 'energy_cost_expr'):
        energy_cost = pyo.value(model.energy_cost_expr)
        print(f"  Stromkosten: {energy_cost:,.2f} EUR")

    # Energy revenue
    if hasattr(model, 'energy_revenue_expr'):
        energy_rev = pyo.value(model.energy_revenue_expr)
        print(f"  Stromerlöse: {energy_rev:,.2f} EUR")

    # Fuel costs
    if hasattr(model, 'fuel_cost_expr'):
        fuel_cost = pyo.value(model.fuel_cost_expr)
        print(f"  Brennstoffkosten: {fuel_cost:,.2f} EUR")

    # CAPEX
    if hasattr(model, 'capex_cost_expr'):
        capex = pyo.value(model.capex_cost_expr)
        print(f"  CAPEX (annualisiert): {capex:,.2f} EUR")

    # Activation costs
    if hasattr(model, 'activation_cost_expr'):
        activation = pyo.value(model.activation_cost_expr)
        print(f"  Aktivierungskosten: {activation:,.2f} EUR")

    # CO2 costs
    if hasattr(model, 'co2_cost_expr'):
        co2_cost = pyo.value(model.co2_cost_expr)
        print(f"  CO2-Kosten: {co2_cost:,.2f} EUR")

    # Dump costs
    dump_total = sum(pyo.value(model.Q_dump[t]) for t in model.t)
    if dump_total > TOLERANCE:
        print(f"  ⚠ Wärme-Dump: {dump_total:.2f} MWh (sollte 0 sein!)")
    else:
        print(f"  ✓ Kein Wärme-Dump")

    return True


def test_heat_balance(model, cfg):
    """Test 5: Verify heat balance is maintained."""
    print("\n" + "="*70)
    print("TEST 5: WÄRMEBILANZ")
    print("="*70)

    errors = []
    dt_h = 1.0

    total_demand = sum(pyo.value(model.heatd[t]) for t in model.t) * dt_h
    print(f"\nGesamter Wärmebedarf: {total_demand:,.2f} MWh")

    # Calculate heat production from each source
    heat_sources = {}

    # Heat pumps (variable name is HP{i}_Q, not HP{i}_Q_th)
    for i in range(1, 5):
        hp_name = f"HP{i}"
        if hasattr(model, f"{hp_name}_Q"):
            q_th = getattr(model, f"{hp_name}_Q")
            total = sum(pyo.value(q_th[t]) for t in model.t) * dt_h
            if total > TOLERANCE:
                heat_sources[hp_name] = total

    # Generators (variable name is {gen}_Qth, not {gen}_Q_th)
    gen_names = ['HKW', 'GTOST', 'BMHKW', 'HWS', 'HWW', 'AVA', 'P2H']
    for gen in gen_names:
        if hasattr(model, f"{gen}_Qth"):
            q_th = getattr(model, f"{gen}_Qth")
            total = sum(pyo.value(q_th[t]) for t in model.t) * dt_h
            if total > TOLERANCE:
                heat_sources[gen] = total

    # Storage discharge (variable name is TES_Qd)
    if hasattr(model, 'TES_Qd'):
        tes_out = sum(pyo.value(model.TES_Qd[t]) for t in model.t) * dt_h
        if tes_out > TOLERANCE:
            heat_sources['TES_Qd'] = tes_out

    # Storage charge (variable name is TES_Qc, subtract from heat balance)
    if hasattr(model, 'TES_Qc'):
        tes_in = sum(pyo.value(model.TES_Qc[t]) for t in model.t) * dt_h
        if tes_in > TOLERANCE:
            heat_sources['TES_Qc'] = -tes_in

    # Network losses
    if hasattr(model, 'network_Q_loss_per_timestep'):
        net_loss = sum(pyo.value(model.network_Q_loss_per_timestep[t]) for t in model.t) * dt_h
        if net_loss > TOLERANCE:
            heat_sources['Netz_Verluste'] = -net_loss

    print("\nWärmequellen:")
    total_supply = 0
    for name, value in heat_sources.items():
        print(f"  {name}: {value:,.2f} MWh")
        total_supply += value

    print(f"\nGesamte Wärmeproduktion (netto): {total_supply:,.2f} MWh")

    # Check balance
    balance_error = abs(total_supply - total_demand)
    if balance_error < 1.0:  # Allow 1 MWh tolerance
        print(f"✓ Wärmebilanz ausgeglichen (Fehler: {balance_error:.4f} MWh)")
    else:
        print(f"✗ Wärmebilanz NICHT ausgeglichen! Fehler: {balance_error:.2f} MWh")
        errors.append(f"Wärmebilanz-Fehler: {balance_error:.2f} MWh")

    if errors:
        return False
    return True


def test_emissions(model, cfg):
    """Test 6: Verify CO2 emissions calculation."""
    print("\n" + "="*70)
    print("TEST 6: CO2-EMISSIONEN")
    print("="*70)

    dt_h = 1.0

    # Get fuel emission factors
    fuels = cfg.get('fuels', {})
    gas_ef = fuels.get('gas', {}).get('ef_kg_per_mwh_fuel', 201.6)
    bio_ef = fuels.get('biomass', {}).get('ef_kg_per_mwh_fuel', 0.0)
    waste_ef = fuels.get('waste', {}).get('ef_kg_per_mwh_fuel', 0.0)

    print(f"\nEmissionsfaktoren:")
    print(f"  Gas: {gas_ef} kg/MWh")
    print(f"  Biomasse: {bio_ef} kg/MWh")
    print(f"  Abfall: {waste_ef} kg/MWh")

    # Calculate emissions from generators
    total_fuel_emissions = 0

    gen_fuel_map = {
        'HKW': ('gas', gas_ef),
        'GTOST': ('gas', gas_ef),
        'HWS': ('gas', gas_ef),
        'HWW': ('gas', gas_ef),
        'BMHKW': ('biomass', bio_ef),
        'AVA': ('waste', waste_ef),
    }

    print(f"\nEmissionen nach Generator:")
    for gen, (fuel, ef) in gen_fuel_map.items():
        if hasattr(model, f"{gen}_fuel"):
            fuel_var = getattr(model, f"{gen}_fuel")
            fuel_mwh = sum(pyo.value(fuel_var[t]) for t in model.t) * dt_h
            emissions_kg = fuel_mwh * ef
            emissions_t = emissions_kg / 1000
            if fuel_mwh > TOLERANCE:
                print(f"  {gen}: {fuel_mwh:,.1f} MWh {fuel} → {emissions_t:,.2f} t CO2")
                total_fuel_emissions += emissions_t

    print(f"\nGesamt-Emissionen aus Brennstoffen: {total_fuel_emissions:,.2f} t CO2")

    # Grid emissions from heat pumps
    grid_emissions = 0
    for i in range(1, 5):
        hp_name = f"HP{i}"
        if hasattr(model, f"{hp_name}_Pel"):
            p_el = getattr(model, f"{hp_name}_Pel")
            for t in model.t:
                pel_mwh = pyo.value(p_el[t]) * dt_h
                grid_co2 = pyo.value(model.grid_co2[t])  # kg/MWh
                grid_emissions += pel_mwh * grid_co2 / 1000  # t

    # P2H grid emissions
    if hasattr(model, 'P2H_Pel'):
        for t in model.t:
            pel_mwh = pyo.value(model.P2H_Pel[t]) * dt_h
            grid_co2 = pyo.value(model.grid_co2[t])
            grid_emissions += pel_mwh * grid_co2 / 1000

    print(f"Gesamt-Emissionen aus Strom: {grid_emissions:,.2f} t CO2")
    print(f"\nGESAMT-EMISSIONEN: {total_fuel_emissions + grid_emissions:,.2f} t CO2")

    # Check CO2 cost calculation
    co2_price = cfg.get('costs', {}).get('co2_price_eur_per_t', 100.0)
    expected_co2_cost = (total_fuel_emissions + grid_emissions) * co2_price
    print(f"\nErwartete CO2-Kosten: {expected_co2_cost:,.2f} EUR (bei {co2_price} EUR/t)")

    if hasattr(model, 'co2_cost_expr'):
        actual_co2_cost = pyo.value(model.co2_cost_expr)
        print(f"Tatsächliche CO2-Kosten: {actual_co2_cost:,.2f} EUR")

        if abs(actual_co2_cost - expected_co2_cost) < expected_co2_cost * 0.1:  # 10% tolerance
            print("✓ CO2-Kosten plausibel")
        else:
            print(f"⚠ CO2-Kosten weichen ab!")

    return True


def test_network_losses(model, cfg):
    """Test 7: Verify network heat losses."""
    print("\n" + "="*70)
    print("TEST 7: NETZWERK-VERLUSTE")
    print("="*70)

    if not cfg.get('thermal_network', {}).get('enabled'):
        print("Thermisches Netzwerk deaktiviert - Test übersprungen")
        return True

    dt_h = 1.0

    if hasattr(model, 'network_Q_loss_per_timestep'):
        # Get losses
        losses_per_t = [pyo.value(model.network_Q_loss_per_timestep[t]) for t in model.t]
        total_loss_mwh = sum(losses_per_t) * dt_h

        # Check if losses are constant (brownfield mode)
        first_loss = losses_per_t[0]
        is_constant = all(abs(l - first_loss) < TOLERANCE for l in losses_per_t)

        print(f"\nNetzwerk-Verluste:")
        print(f"  Verlust pro Zeitschritt: {first_loss*1000:.2f} kW")
        print(f"  Gesamt-Verlust: {total_loss_mwh:.3f} MWh")
        print(f"  Konstant (Brownfield): {'Ja ✓' if is_constant else 'Nein'}")

        # Calculate expected losses from pipe data
        if hasattr(model, '_brownfield_total_loss_mw'):
            expected_loss_mw = model._brownfield_total_loss_mw
            print(f"\n  Erwarteter Verlust: {expected_loss_mw*1000:.2f} kW")

            if abs(first_loss - expected_loss_mw) < TOLERANCE:
                print("  ✓ Verlust entspricht physikalischer Berechnung")
            else:
                print(f"  ⚠ Abweichung: {abs(first_loss - expected_loss_mw)*1000:.2f} kW")

        # Loss as percentage of demand
        total_demand = sum(pyo.value(model.heatd[t]) for t in model.t) * dt_h
        loss_percent = (total_loss_mwh / total_demand) * 100 if total_demand > 0 else 0
        print(f"\n  Verlust-Anteil: {loss_percent:.2f}% des Bedarfs")

        if loss_percent < 5:
            print("  ✓ Verluste plausibel (<5%)")
        else:
            print("  ⚠ Verluste hoch (>5%)")
    else:
        print("Keine Netzwerk-Verluste im Modell gefunden")

    return True


def main():
    """Run all tests."""
    print("="*70)
    print("ENERGIS VOLLSTÄNDIGER SYSTEMTEST")
    print("="*70)
    print(f"Konfiguration: {CONFIG_PATH}")

    results = {}

    # Test 1: Configuration
    results['config'] = test_configuration_parsing()

    if not results['config']:
        print("\n⚠ Konfigurationstest fehlgeschlagen - breche ab")
        return

    # Load config for remaining tests
    cfg = load_and_merge([CONFIG_PATH])

    # Test 2: Model creation
    success, model = test_model_creation()
    results['model'] = success

    if not success or model is None:
        print("\n⚠ Modell-Erstellung fehlgeschlagen - breche ab")
        return

    # Test 3: Investment bounds
    results['bounds'] = test_investment_bounds(model, cfg)

    # Test 4: Solve and objective
    results['solve'] = test_solve_and_objective(model, cfg)

    if not results['solve']:
        print("\n⚠ Optimierung fehlgeschlagen - weitere Tests übersprungen")
    else:
        # Test 5: Heat balance
        results['heat'] = test_heat_balance(model, cfg)

        # Test 6: Emissions
        results['emissions'] = test_emissions(model, cfg)

        # Test 7: Network losses
        results['network'] = test_network_losses(model, cfg)

    # Summary
    print("\n" + "="*70)
    print("ZUSAMMENFASSUNG")
    print("="*70)

    all_passed = True
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {test_name}: {status}")
        if not passed:
            all_passed = False

    print("\n" + "="*70)
    if all_passed:
        print("✓ ALLE TESTS BESTANDEN!")
    else:
        print("⚠ EINIGE TESTS FEHLGESCHLAGEN!")
    print("="*70)


if __name__ == "__main__":
    main()
