#!/usr/bin/env python3
"""Test publication exporter with new cost fields."""

from energis.run import rolling_horizon as rh
from energis.io.publication_exporter import export_latex_tables
import os

# Run with test configuration
config_paths = [
    "configs/base.yaml",
    "configs/systems/baseline.system.yaml",
    "configs/scenarios/test_1week.scenario.yaml",
    "configs/sites/default.site.yaml"
]

print("=" * 80)
print("PUBLICATION EXPORTS TEST - Updated Cost Fields")
print("=" * 80)
print()

# Enable publication exports
overrides = {
    "export": {
        "enable_publication_exports": True,
        "publication_formats": ["png", "pdf"],
        "latex_table_style": "booktabs"
    }
}

workflow = rh.run_workflow(config_paths, overrides=overrides)
result = rh.export_workflow_results(workflow)

print("\n=== RESULT ===")
print(f"Output directory: {result['outdir']}")
print()

# Check if publication files were generated
pub_files = result.get('publication_files', {})
if pub_files:
    print("✅ Publication files generated:")
    for key, value in pub_files.items():
        if isinstance(value, dict):
            print(f"\n  {key}:")
            for sub_key, sub_value in value.items():
                print(f"    - {sub_key}: {sub_value}")
        else:
            print(f"  - {key}: {value}")
else:
    print("⚠️  No publication files generated")

# Check LaTeX tables specifically
latex_dir = os.path.join(result['outdir'], 'publication_latex')
if os.path.exists(latex_dir):
    latex_files = os.listdir(latex_dir)
    print(f"\n✅ LaTeX files in {latex_dir}:")
    for f in sorted(latex_files):
        file_path = os.path.join(latex_dir, f)
        size = os.path.getsize(file_path)
        print(f"  - {f} ({size} bytes)")

        # Show first few lines of cost tables
        if 'cost' in f.lower():
            print(f"\n    Preview of {f}:")
            with open(file_path, 'r') as handle:
                lines = handle.readlines()[:15]
                for line in lines:
                    print(f"      {line.rstrip()}")
else:
    print(f"\n⚠️  LaTeX directory not found: {latex_dir}")

print("\n" + "=" * 80)
print("✅ Publication export test completed!")
print("=" * 80)
