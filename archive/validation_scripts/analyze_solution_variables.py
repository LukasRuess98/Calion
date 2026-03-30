"""
Extract and analyze variables from solution file
"""

from pathlib import Path
import re

sol_path = Path("outputs/runs/thermal_network_results/solver/gurobi_solution.sol")

print("="*70)
print("VARIABLE ANALYSIS FROM SOLUTION FILE")
print("="*70)

if sol_path.exists():
    variables = {}
    
    with open(sol_path, 'r') as f:
        for line in f:
            # Skip comments
            if line.startswith('#'):
                continue
            
            # Extract variable name and value
            match = re.match(r'(\w+)\[.*\]\s+([\d\.\-e]+)', line)
            if match:
                var_name = match.group(1)
                value = float(match.group(2))
                
                if var_name not in variables:
                    variables[var_name] = {'values': [], 'min': value, 'max': value, 'sum': 0}
                
                variables[var_name]['values'].append(value)
                variables[var_name]['min'] = min(variables[var_name]['min'], value)
                variables[var_name]['max'] = max(variables[var_name]['max'], value)
                variables[var_name]['sum'] += value
    
    print(f"\nTotal unique variables: {len(variables)}\n")
    
    # Sort by variable name
    for var_name in sorted(variables.keys()):
        info = variables[var_name]
        n_values = len(info['values'])
        avg = info['sum'] / n_values if n_values > 0 else 0
        
        print(f"{var_name:20} count={n_values:5}  min={info['min']:12.4f}  max={info['max']:12.4f}  avg={avg:12.4f}  sum={info['sum']:15.2f}")

else:
    print("Solution file not found!")
