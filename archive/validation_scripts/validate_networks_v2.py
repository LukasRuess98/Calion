#!/usr/bin/env python3
"""
Enhanced Multi-Network Validation
Robust testing with real Stadtbach data for different topologies
"""

import json
import pandas as pd
import sys
from pathlib import Path
from datetime import datetime
import subprocess
import time

print_enabled = True

def print_header(text):
    if print_enabled:
        print(f"\n{'='*80}")
        print(f"  {text}")
        print(f"{'='*80}\n")

def print_section(text):
    if print_enabled:
        print(f"\n{'─'*80}")
        print(f"  {text}")
        print(f"{'─'*80}\n")

class NetworkValidator:
    def __init__(self):
        self.results = {}
        
    def run_optimization(self, config_name, config_path):
        """Führe Optimierung ohnefehlerhafte Subprocess-Logging aus"""
        print(f"  ⏳ Testing: {config_name}...")
        start_time = time.time()
        
        try:
            # Einfacher Subprocess-Aufruf ohne capture_output
            proc = subprocess.Popen(
                [sys.executable, "-m", "calion.run", str(config_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=False,  # Binary mode
            )
            
            # Warte auf Completion mit Timeout
            try:
                stdout_bytes, stderr_bytes = proc.communicate(timeout=300)
                # Dekodiere mit error-tolerance
                stdout = stdout_bytes.decode('utf-8', errors='replace')
                stderr = stderr_bytes.decode('utf-8', errors='replace')
            except subprocess.TimeoutExpired:
                proc.kill()
                return {
                    'status': 'timeout',
                    'optimal': False,
                    'time_seconds': time.time() - start_time,
                }
            
            elapsed_seconds = time.time() - start_time
            
            # Check auf Erfolg
            success = proc.returncode == 0
            is_optimal = "optimal" in stdout.lower()
            
            return {
                'status': 'completed' if success else 'partial',
                'optimal': is_optimal,
                'time_seconds': elapsed_seconds,
                'return_code': proc.returncode,
                'output_snippet': stdout[-200:] if stdout else "N/A",
            }
        except Exception as e:
            return {
                'status': 'error',
                'optimal': False,
                'error': str(e),
                'time_seconds': time.time() - start_time,
            }
    
    def validate_exports(self, scenario_name):
        """Prüfe ob Export-Dateien vorhanden sind"""
        results_dir = Path("outputs/runs/thermal_network_results")
        
        exports = {
            'lp': results_dir / "*.lp",
            'mps': results_dir / "*.mps",
            'sol': results_dir / "*.sol",
            'csv': results_dir / "unified_timeseries.csv",
            'manifest': results_dir / "export_manifest.json",
        }
        
        found = {}
        for fmt, pattern in exports.items():
            if fmt in ['csv', 'manifest']:
                found[fmt] = pattern.exists()
            else:
                found[fmt] = len(list(results_dir.glob(pattern.name))) > 0
        
        return found
    
    def validate_csv(self):
        """Validiere CSV-Daten wenn vorhanden"""
        csv_file = Path("outputs/runs/thermal_network_results/unified_timeseries.csv")
        
        if not csv_file.exists():
            return None
        
        try:
            df = pd.read_csv(csv_file, sep=';')
            
            return {
                'rows': len(df),
                'columns': len(df.columns),
                'null_values': int(df.isnull().sum().sum()),
                'columns_list': list(df.columns),
                'demand_sum_gwh': round(df['heat_demand_MW'].sum() / 1000, 2) if 'heat_demand_MW' in df.columns else None,
            }
        except Exception as e:
            return {'error': str(e)}
    
    def test_network(self, name, config_path):
        """Test ein spezifisches Netzwerk"""
        print_section(f"🔬 {name}")
        
        # 1. Optimierung
        opt_result = self.run_optimization(name, config_path)
        
        print(f"  Status: {opt_result['status']} ({opt_result['time_seconds']:.1f}s)")
        
        if opt_result['status'] == 'completed':
            print(f"  ✅ Solver: {'Optimal' if opt_result['optimal'] else 'Feasible'}")
        elif opt_result['status'] == 'timeout':
            print(f"  ⏱️  Timeout nach 300s")
            self.results[name] = opt_result
            return
        elif opt_result['status'] == 'error':
            print(f"  ❌ Error: {opt_result.get('error', 'Unknown')}")
            self.results[name] = opt_result
            return
        
        # 2. Export-Check
        exports = self.validate_exports(name)
        print(f"  Exports:")
        for fmt, present in exports.items():
            print(f"    {'✅' if present else '❌'} {fmt.upper()}")
        
        # 3. CSV-Validierung
        csv_info = self.validate_csv()
        if csv_info and 'error' not in csv_info:
            print(f"  CSV Data:")
            print(f"    • Rows: {csv_info['rows']}")
            print(f"    • Columns: {csv_info['columns']}")
            print(f"    • Null values: {csv_info['null_values']}")
            if csv_info.get('demand_sum_gwh'):
                print(f"    • Annual demand: {csv_info['demand_sum_gwh']} GWh")
            opt_result['csv'] = csv_info
        elif csv_info:
            print(f"  ⚠️  CSV Error: {csv_info.get('error')}")
        
        opt_result['exports'] = exports
        self.results[name] = opt_result
        
        return opt_result
    
    def print_summary(self):
        """Drucke die Zusammenfassung"""
        print_header("📊 MULTI-NETWORK VALIDATION SUMMARY")
        
        if not self.results:
            print("❌ Keine Ergebnisse gefunden!")
            return
        
        # Tabelle
        print(f"{'Network':<25} {'Status':<12} {'Time':<10} {'Optimal':<10} {'CSV':<10}")
        print("─" * 80)
        
        for name, result in self.results.items():
            status = result.get('status', 'unknown').upper()
            time_s = f"{result.get('time_seconds', 0):.1f}s"
            optimal = "✅ Yes" if result.get('optimal') else "⚠️ No"
            csv_ok = "✅" if result.get('csv') else "❌"
            
            print(f"{name:<25} {status:<12} {time_s:<10} {optimal:<10} {csv_ok:<10}")
        
        # Statistik
        total = len(self.results)
        completed = sum(1 for r in self.results.values() if r.get('status') == 'completed')
        optimal = sum(1 for r in self.results.values() if r.get('optimal'))
        
        print("\n" + "="*80)
        print(f"Tests: {completed}/{total} completed | {optimal}/{total} optimal")
        
        if completed == total:
            print("✅ Framework validation successful!")
        else:
            print(f"⚠️  {total - completed} tests did not complete")
        
        print("="*80 + "\n")


def main():
    print_header("🌐 MULTI-NETWORK VALIDATION SUITE v2")
    print("Testing 1-node, 5-node, and 30-node topologies with Stadtbach data\n")
    
    validator = NetworkValidator()
    
    # Test 1: 1-Knoten
    validator.test_network(
        "1-Node (Copperplate)",
        Path("configs/templates/level1_copperplate.yaml")
    )
    
    # Test 2: 5-Knoten
    validator.test_network(
        "5-Node Network",
        Path("configs/templates/level2_5node.yaml")
    )
    
    # Test 3: 30-Knoten
    validator.test_network(
        "30-Node Network",
        Path("configs/templates/level3_30node_template.yaml")
    )
    
    # Summary
    validator.print_summary()
    
    # Save results
    results_file = Path("multi_network_validation_results.json")
    with open(results_file, 'w') as f:
        # Convert to serializable format
        export_results = {}
        for name, result in validator.results.items():
            export_results[name] = {k: v for k, v in result.items() if not callable(v)}
        json.dump(export_results, f, indent=2)
    
    print(f"💾 Results saved to: {results_file}\n")


if __name__ == "__main__":
    main()
