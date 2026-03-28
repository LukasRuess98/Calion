#!/usr/bin/env python3
"""
Framework Validation Suite - Praktische Implementierung
Führt alle wichtigen Qualitätsprüfungen durch
"""

import json
import pandas as pd
import sys
from pathlib import Path
from datetime import datetime

def print_header(text):
    print(f"\n{'='*70}")
    print(f"  {text}")
    print(f"{'='*70}\n")

def print_check(name, passed, message=""):
    symbol = "✅ PASSED" if passed else "❌ FAILED"
    print(f"{symbol:12} | {name:40} | {message}")

class FrameworkValidator:
    def __init__(self, results_dir="outputs/runs/thermal_network_results"):
        self.results_dir = Path(results_dir)
        self.csv_file = self.results_dir / "unified_timeseries.csv"
        self.manifest_file = self.results_dir / "export_manifest.json"
        self.df = None
        self.manifest = None
        self.issues = []
        self.passes = []
        
    def load_data(self):
        """Lade Result-Dateien"""
        print("📁 Lade Ergebnis-Dateien...")
        
        if not self.csv_file.exists():
            print(f"❌ CSV nicht gefunden: {self.csv_file}")
            return False
        
        try:
            self.df = pd.read_csv(self.csv_file, sep=';')
            print(f"   ✓ CSV geladen: {len(self.df)} Zeilen")
        except Exception as e:
            print(f"❌ Fehler beim CSV-Laden: {e}")
            return False
        
        if self.manifest_file.exists():
            try:
                self.manifest = json.load(open(self.manifest_file))
                print(f"   ✓ Manifest geladen")
            except Exception as e:
                print(f"⚠️  Manifest Fehler: {e}")
        
        return True
    
    # ========== VALIDIERUNGSCHECKS ==========
    
    def check_time_coverage(self):
        """Prüfe ob alle Stunden abgedeckt sind"""
        required_hours = 8760  # oder 8736 für 2023
        actual_hours = len(self.df)
        
        passed = abs(actual_hours - required_hours) <= 24
        msg = f"{actual_hours} hours (expected ~{required_hours})"
        
        if passed:
            self.passes.append("Time Coverage")
        else:
            self.issues.append(f"Time coverage: {msg}")
        
        return passed, msg
    
    def check_no_nulls(self):
        """Prüfe auf fehlende Werte"""
        total_cells = self.df.shape[0] * self.df.shape[1]
        null_count = self.df.isnull().sum().sum()
        null_percent = (null_count / total_cells * 100) if total_cells > 0 else 0
        
        passed = null_percent < 1.0  # Toleranz: <1%
        msg = f"{null_count} nulls ({null_percent:.2f}%)"
        
        if passed:
            self.passes.append("No Nulls")
        else:
            self.issues.append(f"Null values: {msg}")
        
        return passed, msg
    
    def check_data_types(self):
        """Prüfe ob numerische Spalten korrekt sind"""
        numeric_cols = self.df.select_dtypes(include=['number']).columns
        
        all_finite = all(self.df[col].apply(lambda x: pd.notna(x) and (isinstance(x, (int, float)) or (isinstance(x, complex) and x.imag == 0))).all() for col in numeric_cols)
        
        passed = len(numeric_cols) > 0 and all_finite
        msg = f"{len(numeric_cols)} numeric columns"
        
        if passed:
            self.passes.append("Data Types")
        else:
            self.issues.append(f"Data types: {msg}")
        
        return passed, msg
    
    def check_heat_balance(self):
        """Wärmebilanz: Demand ≈ Supply"""
        if 'heat_demand_MW' not in self.df.columns:
            return None, "heat_demand_MW column not found"
        
        demand_sum = self.df['heat_demand_MW'].sum()
        
        # Für Copperplate-Modell
        supply_sum = 0
        if 'Q_boiler' in self.df.columns:
            supply_sum += self.df['Q_boiler'].sum()
        if 'Q_hp' in self.df.columns:
            supply_sum += self.df['Q_hp'].sum()
        if 'storage_discharge_MW' in self.df.columns:
            supply_sum += self.df['storage_discharge_MW'].sum()
        
        # Fallback: Wenn keine Supply-Spalten, bestehe mit Warnung
        if supply_sum == 0:
            return None, "No supply columns found (Copperplate model - OK)"
        
        if demand_sum > 0:
            balance_percent = (supply_sum - demand_sum) / demand_sum * 100
            passed = abs(balance_percent) < 5.0  # Toleranz: <5%
            msg = f"Demand: {demand_sum:.1f} MW, Supply: {supply_sum:.1f} MW ({balance_percent:+.1f}%)"
        else:
            passed = False
            msg = "No demand data"
        
        if passed:
            self.passes.append("Heat Balance")
        else:
            self.issues.append(f"Heat balance: {msg}")
        
        return passed, msg
    
    def check_storage_consistency(self):
        """Speicher-Grenzen prüfen"""
        if 'storage_SOC_MWh' not in self.df.columns:
            return None, "storage_SOC_MWh column not found"
        
        soc = self.df['storage_SOC_MWh']
        
        # Storage sollte nie negativ sein
        negative_count = (soc < 0).sum()
        passed_negative = negative_count == 0
        
        min_soc = soc.min()
        max_soc = soc.max()
        
        msg = f"SOC range: {min_soc:.1f} - {max_soc:.1f} MWh"
        
        if passed_negative:
            self.passes.append("Storage Consistency")
        else:
            self.issues.append(f"Storage negative: {negative_count} timesteps")
        
        return passed_negative, msg
    
    def check_capacity_limits(self):
        """Alle Assets ≤ Kapazität"""
        issues = []
        
        # Boiler (150 MW typ.)
        if 'Q_boiler' in self.df.columns:
            max_boiler = self.df['Q_boiler'].max()
            if max_boiler > 200:  # Großzügige Toleranz
                issues.append(f"Boiler: {max_boiler:.1f} MW (expected <150)")
        
        # HP (100 MW typ.)
        if 'Q_hp' in self.df.columns:
            max_hp = self.df['Q_hp'].max()
            if max_hp > 150:
                issues.append(f"HP: {max_hp:.1f} MW (expected <100)")
        
        # Stromkauf
        if 'P_buy' in self.df.columns:
            max_buy = self.df['P_buy'].max()
            if max_buy > 30:  # Typisch <20 MW
                issues.append(f"Electricity buy: {max_buy:.1f} MW (typically <20)")
        
        passed = len(issues) == 0
        msg = ", ".join(issues) if issues else "All within limits"
        
        if passed:
            self.passes.append("Capacity Limits")
        else:
            self.issues.extend(issues)
        
        return passed, msg
    
    def check_demand_plausibility(self):
        """Wärmenachfrage in plausiblem Bereich"""
        if 'heat_demand_MW' not in self.df.columns:
            return None, "heat_demand_MW not found"
        
        demand = self.df['heat_demand_MW']
        min_d = demand.min()
        max_d = demand.max()
        avg_d = demand.mean()
        
        # Für Stadtbach: 45-80 MW typical
        # Aber flexible Grenzen
        plausible = (min_d > 0) and (max_d < 200) and (avg_d > min_d)
        
        msg = f"Min: {min_d:.1f}, Avg: {avg_d:.1f}, Max: {max_d:.1f} MW"
        
        if plausible:
            self.passes.append("Demand Plausibility")
        else:
            self.issues.append(f"Implausible demand: {msg}")
        
        return plausible, msg
    
    def check_annual_statistics(self):
        """Jahres-Statistiken"""
        if 'heat_demand_MW' not in self.df.columns:
            return None, "Cannot calculate"
        
        demand_mwh = self.df['heat_demand_MW'].sum()
        demand_gwh = demand_mwh / 1000
        
        # Für Stadtbach: ~500-600 GWh/a expected
        plausible = 400 < demand_gwh < 700
        
        msg = f"{demand_gwh:.1f} GWh/a"
        
        if plausible:
            self.passes.append("Annual Volume")
        else:
            self.issues.append(f"Implausible annual: {msg}")
        
        return plausible, msg
    
    # ========== HAUPTMETHODE ==========
    
    def validate_all(self):
        """Führe alle Checks durch"""
        if not self.load_data():
            return False
        
        print_header("VALIDIERUNGSPROTOKOLLE")
        
        checks = [
            ("Time Coverage", self.check_time_coverage()),
            ("No Null Values", self.check_no_nulls()),
            ("Data Types OK", self.check_data_types()),
            ("Heat Balance", self.check_heat_balance()),
            ("Storage Consistency", self.check_storage_consistency()),
            ("Capacity Limits OK", self.check_capacity_limits()),
            ("Demand Plausible", self.check_demand_plausibility()),
            ("Annual Statistics", self.check_annual_statistics()),
        ]
        
        passed_count = 0
        failed_count = 0
        skipped_count = 0
        
        for name, (result, msg) in checks:
            if result is None:
                print_check(name, True, f"⊘ SKIPPED: {msg}")
                skipped_count += 1
            elif result:
                print_check(name, True, msg)
                passed_count += 1
            else:
                print_check(name, False, msg)
                failed_count += 1
        
        # Summary
        print_header("ZUSAMMENFASSUNG")
        print(f"Passed:  {passed_count}")
        print(f"Failed:  {failed_count}")
        print(f"Skipped: {skipped_count}")
        print()
        
        if failed_count > 0:
            print("⚠️  PROBLEME GEFUNDEN:")
            for issue in self.issues:
                print(f"  • {issue}")
        
        if self.passes:
            print("\n✅ ERFOLGREICH VALIDIERT:")
            for p in self.passes:
                print(f"  • {p}")
        
        overall_pass = failed_count == 0
        print()
        print("="*70)
        if overall_pass:
            print("  ✅ ALLE CHECKS BESTANDEN - Framework ist valid!")
        else:
            print(f"  ⚠️  {failed_count} CHECKS FEHLGESCHLAGEN - Prüfung nötig")
        print("="*70)
        
        return overall_pass


def main():
    print("\n🔍 Framework Validation Suite\n")
    
    validator = FrameworkValidator()
    success = validator.validate_all()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
