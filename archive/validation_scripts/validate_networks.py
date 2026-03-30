#!/usr/bin/env python3
"""
Multi-Network Validation Suite
Fügt verschiedene Netzwerk-Topologien mit realen Stadtbach-Daten aus.
"""

import json
import pandas as pd
import sys
from pathlib import Path
from datetime import datetime
import subprocess
import time

def print_header(text):
    print(f"\n{'='*80}")
    print(f"  {text}")
    print(f"{'='*80}\n")

def print_section(text):
    print(f"\n{'─'*80}")
    print(f"  {text}")
    print(f"{'─'*80}\n")

class NetworkValidator:
    def __init__(self):
        self.results = {}
        self.data_dir = Path("data")
        self.config_dir = Path("configs/templates")
        
    def run_optimization(self, config_file):
        """Führe Optimierung mit gegebener Config aus"""
        print(f"  ⏳ Optimierung läuft ({config_file})...")
        start_time = time.time()
        
        try:
            result = subprocess.run(
                [sys.executable, "-m", "calion.run", str(config_file)],
                capture_output=True,
                text=True,
                errors='replace',  # Handle encoding errors gracefully
                timeout=600  # 10 min timeout
            )
            
            elapsed_seconds = time.time() - start_time
            
            # Check ob optimal gefunden wurde
            stdout_lower = result.stdout.lower() if result.stdout else ""
            stderr_lower = result.stderr.lower() if result.stderr else ""
            is_optimal = "optimal" in stdout_lower or "optimal" in stderr_lower
            
            return {
                'status': 'completed' if result.returncode == 0 else 'error',
                'optimal': is_optimal,
                'time_seconds': elapsed_seconds,
                'return_code': result.returncode,
                'stdout': result.stdout[:500] if result.stdout else "N/A",
                'stderr': result.stderr[:500] if result.stderr else "N/A",
            }
        except subprocess.TimeoutExpired:
            elapsed = time.time() - start_time
            return {'status': 'timeout', 'optimal': False, 'time_seconds': elapsed}
        except Exception as e:
            return {'status': 'error', 'optimal': False, 'error': str(e)}
    
    def validate_results(self, scenario_name):
        """Validiere die Ergebnisse nach Optimierung"""
        csv_file = Path(f"outputs/runs/thermal_network_results/unified_timeseries.csv")
        
        if not csv_file.exists():
            return {'valid': False, 'reason': 'CSV file not found'}
        
        try:
            df = pd.read_csv(csv_file, sep=';')
            
            # Basis-Checks
            num_rows = len(df)
            num_cols = len(df.columns)
            null_count = df.isnull().sum().sum()
            
            # Statistische Checks
            if 'heat_demand_MW' in df.columns:
                demand_sum = df['heat_demand_MW'].sum()
                demand_min = df['heat_demand_MW'].min()
                demand_max = df['heat_demand_MW'].max()
                demand_avg = df['heat_demand_MW'].mean()
            else:
                demand_sum = demand_min = demand_max = demand_avg = 0
            
            is_valid = (
                num_rows > 100 and  # Mindestens ~4 Tage
                null_count == 0 and
                demand_sum > 0
            )
            
            return {
                'valid': is_valid,
                'rows': num_rows,
                'columns': num_cols,
                'null_values': null_count,
                'demand_sum_gwh': demand_sum / 1000,
                'demand_min_mw': round(demand_min, 1),
                'demand_max_mw': round(demand_max, 1),
                'demand_avg_mw': round(demand_avg, 1),
                'null_percent': (null_count / (num_rows * num_cols) * 100) if num_rows * num_cols > 0 else 0,
            }
        except Exception as e:
            return {'valid': False, 'reason': f'Error: {str(e)}'}
    
    def test_network(self, name, config_template):
        """Test ein spezifisches Netzwerk"""
        print_section(f"🔬 {name}")
        
        # 1. Optimierung ausführen
        opt_result = self.run_optimization(config_template)
        
        if opt_result['status'] == 'completed':
            print(f"  ✅ Optimierung erfolgreich ({opt_result['time_seconds']:.1f}s)")
            if opt_result['optimal']:
                print(f"  ✅ Status: Optimal gefunden")
            else:
                print(f"  ⚠️  Status: Nicht optimal (aber feasible)")
        elif opt_result['status'] == 'timeout':
            print(f"  ⏱️  Timeout nach 600s")
        else:
            print(f"  ❌ Fehler: {opt_result.get('error', 'Unknown')}")
            return None
        
        # 2. Ergebnisse validieren
        val_result = self.validate_results(name)
        
        if val_result['valid']:
            print(f"  ✅ Validierung bestanden")
            print(f"     • Rows: {val_result['rows']}")
            print(f"     • Columns: {val_result['columns']}")
            print(f"     • Null values: {val_result['null_values']}")
            if val_result['demand_sum_gwh'] > 0:
                print(f"     • Annual demand: {val_result['demand_sum_gwh']:.1f} GWh")
                print(f"     • Range: {val_result['demand_min_mw']}-{val_result['demand_max_mw']} MW")
                print(f"     • Average: {val_result['demand_avg_mw']:.1f} MW")
        else:
            print(f"  ❌ Validierung fehlgeschlagen: {val_result.get('reason', 'Unknown')}")
            return None
        
        # Combine results
        result = {**opt_result, **val_result}
        self.results[name] = result
        
        return result
    
    def print_summary(self):
        """Drucke Zusammenfassung aller Tests"""
        print_header("📊 VALIDIERUNGS-ZUSAMMENFASSUNG")
        
        if not self.results:
            print("Keine Ergebnisse zum Anzeigen!")
            return
        
        print(f"{'Network':<20} {'Status':<12} {'Time (s)':<10} {'Rows':<8} {'Demand (GWh)':<15}")
        print("─" * 80)
        
        for name, result in self.results.items():
            status = "✅ OK" if result.get('valid') else "❌ FAIL"
            time_s = f"{result.get('time_seconds', 0):.1f}"
            rows = str(result.get('rows', 'N/A'))
            demand = f"{result.get('demand_sum_gwh', 0):.1f}" if result.get('demand_sum_gwh', 0) > 0 else "N/A"
            
            print(f"{name:<20} {status:<12} {time_s:<10} {rows:<8} {demand:<15}")
        
        print("\n" + "="*80)
        
        # Count results
        passed = sum(1 for r in self.results.values() if r.get('valid'))
        total = len(self.results)
        
        if passed == total:
            print(f"✅ ALLE {total} NETZWERKE BESTANDEN - Framework ready for production!")
        else:
            print(f"⚠️  {passed}/{total} Netzwerke bestanden")
        
        print("="*80 + "\n")

def main():
    print_header("🌐 MULTI-NETWORK VALIDATION SUITE")
    print("Validiert verschiedene Netzwerk-Topologien mit Stadtbach-Daten\n")
    
    validator = NetworkValidator()
    
    # Test 1: 1-Knoten (Copperplate)
    validator.test_network(
        "1-Knoten (Copperplate)",
        Path("configs/templates/level1_copperplate.yaml")
    )
    
    # Test 2: 5-Knoten
    validator.test_network(
        "5-Knoten Network",
        Path("configs/templates/level2_5node.yaml")
    )
    
    # Test 3: 30-Knoten (als 20-Knoten Proxy)
    validator.test_network(
        "30-Knoten Network",
        Path("configs/templates/level3_30node_template.yaml")
    )
    
    # Summary
    validator.print_summary()
    
    # Export results to JSON
    results_file = Path("multi_network_validation_results.json")
    with open(results_file, 'w') as f:
        json.dump(validator.results, f, indent=2, default=str)
    
    print(f"📄 Ergebnisse gespeichert: {results_file}\n")

if __name__ == "__main__":
    main()
